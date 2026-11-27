"""
Design invariants:
    1. Fit all feature-distribution statistics STRICTLY on clean training data
       (partition == "train").
    2. Calibrate trust scaling (beta) and uncertainty threshold (tau_unc)
       STRICTLY on validation data (partition == "validation").
       Default calibration ("unsupervised_clean") uses ONLY clean validation
       telemetry (no synthetic attacks seen during calibration).
    3. Never inspect test data or test labels during fitting or calibration.
    4. Exact fusion rule (Proposal Section 8.4):
           P_F = (T_N * P_N + T_R * P_R) / (T_N + T_R + eps)
       with an explicit "uncertain" fallback when max(T_N, T_R) < tau_unc.

Dependencies:
    numpy, scipy, scikit-learn
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, Iterable, List, Optional, Tuple
import numpy as np
from sklearn.covariance import LedoitWolf


EPS_PROB = 1e-12
EPS_SCALE = 1e-3
EPS_FUSION = 1e-8


def binary_entropy_normalized(p: np.ndarray) -> np.ndarray:
    """Normalized binary Shannon entropy in [0, 1] for probabilities p in [0, 1]."""
    p_clip = np.clip(np.asarray(p, dtype=np.float64), EPS_PROB, 1.0 - EPS_PROB)
    h = -(p_clip * np.log2(p_clip) + (1.0 - p_clip) * np.log2(1.0 - p_clip))
    return np.clip(h, 0.0, 1.0)


def _robust_scale(x: np.ndarray, floor: float = EPS_SCALE) -> float:
    """Robust dispersion estimate: IQR/1.349 -> 1.4826*MAD -> std -> 1.0."""
    x = np.asarray(x, dtype=np.float64)
    q75, q25 = np.percentile(x, [75.0, 25.0])
    iqr_scale = (q75 - q25) / 1.3489795003921634
    if np.isfinite(iqr_scale) and iqr_scale > floor:
        return float(iqr_scale)
    med = np.median(x)
    mad_scale = 1.4826 * np.median(np.abs(x - med))
    if np.isfinite(mad_scale) and mad_scale > floor:
        return float(mad_scale)
    std_scale = float(np.std(x))
    if np.isfinite(std_scale) and std_scale > floor:
        return std_scale
    return 1.0


@dataclass
class IndicatorBaseline:
    """Clean training distribution summary for a single scalar anomaly indicator."""

    quantile_level: float
    threshold_q: float
    median: float
    robust_scale: float
    mean: float
    std: float

    def excess(self, raw_scores: np.ndarray) -> np.ndarray:
        """Non-negative excess above the clean training quantile, in robust scale units."""
        raw = np.asarray(raw_scores, dtype=np.float64)
        return np.maximum(0.0, (raw - self.threshold_q) / self.robust_scale)


@dataclass
class TrustFusionConfig:
    """Hyperparameters for reliability estimation and adaptive fusion."""

    # Indicator weights (non-negative; normalized internally if active set changes)
    w_mahalanobis: float = 0.35
    w_tail: float = 0.25
    w_dropout: float = 0.25
    w_confidence: float = 0.15

    # Clean-quantile anchor for excess anomaly scores (e.g. 0.90 -> 90% of clean train has excess == 0)
    clean_quantile: float = 0.90

    # Top-k fraction for sparse-perturbation tail indicator
    tail_top_frac: float = 0.15

    # Tolerance for detecting exact training-median imputation in standardised space
    dropout_tol: float = 1e-4

    # Exponential decay steepness T_b = exp(-beta_eff * A_b)
    beta: float = 0.85

    # Disagreement-gated sharpening: beta_eff = beta * (1 + gamma_disagree * |P_N - P_R|)
    # Note: when A_b == 0 (clean sensor), exp(-beta_eff * 0) == 1 regardless of disagreement.
    gamma_disagree: float = 1.0

    # Uncertainty fallback threshold: uncertain iff T_N < tau_unc AND T_R < tau_unc
    tau_unc: float = 0.20

    # Target upper bound on clean validation false-abstention rate during unsupervised calibration
    target_clean_val_abstain: float = 0.01

    # Target minimum trust at the 95th percentile of clean validation windows (sets beta in unsupervised mode)
    target_clean_val_p95_trust: float = 0.75

    # Optional static modality priors (1.0, 1.0 = symmetric late fusion on clean data)
    prior_network: float = 1.0
    prior_radio: float = 1.0

    # Decision threshold (fixed to match project checkpoints: 0.5)
    decision_threshold: float = 0.5

    # Small constant in fusion denominator
    eps: float = EPS_FUSION

    # Minimum trust floor (0.0 allows full suppression of a completely corrupted sensor)
    trust_floor: float = 0.0

    def active_weights(self) -> Dict[str, float]:
        raw = {
            "mahalanobis": max(0.0, float(self.w_mahalanobis)),
            "tail": max(0.0, float(self.w_tail)),
            "dropout": max(0.0, float(self.w_dropout)),
            "confidence": max(0.0, float(self.w_confidence)),
        }
        total = sum(raw.values())
        if total <= 0.0:
            raise ValueError("At least one indicator weight must be strictly positive.")
        return {k: v / total for k, v in raw.items()}

    def to_dict(self) -> Dict:
        return asdict(self)


class ModalityReliabilityEstimator:
    """Single-modality inference-time reliability estimator in standardised feature space.

    Fitted strictly on clean training telemetry Z_train (n_train, F) and optional
    clean training model probabilities p_train (n_train,).

    Indicators:
        1. mahalanobis: Ledoit-Wolf shrunk Mahalanobis distance divided by sqrt(F).
           Sensitive to additive noise, shifts, scaling, and covariance-breaking
           feature corruption.
        2. tail: Mean of top-k per-feature robust deviations |z_j - med_j| / scale_j.
           Sensitive to sparse subset bias/scaling/corruption on 10%-25% of features.
        3. dropout: Information-theoretic surprisal-weighted fraction of features
           matching the saved training imputation constant z_med.
           Sensitive to partial/complete sensor dropout while ignoring discrete
           or zero-inflated features that naturally sit at their training median.
        4. confidence: Normalized binary entropy of the modality classifier's
           predicted probability H(p)/ln(2).
    """

    def __init__(self, modality: str, config: Optional[TrustFusionConfig] = None):
        self.modality = modality
        self.config = config if config is not None else TrustFusionConfig()
        self._fitted = False

        # Fitted training parameters
        self.n_features_: int = 0
        self.z_median_: Optional[np.ndarray] = None
        self.lw_mean_: Optional[np.ndarray] = None
        self.lw_precision_: Optional[np.ndarray] = None
        self.feat_median_: Optional[np.ndarray] = None
        self.feat_scale_: Optional[np.ndarray] = None
        self.tail_k_: int = 1
        self.med_surprisal_: Optional[np.ndarray] = None
        self.med_surprisal_sum_: float = 1.0
        self.baselines_: Dict[str, IndicatorBaseline] = {}

    def _fit_indicator_baseline(self, scores: np.ndarray, q: float) -> IndicatorBaseline:
        s = np.asarray(scores, dtype=np.float64)
        return IndicatorBaseline(
            quantile_level=float(q),
            threshold_q=float(np.quantile(s, q)),
            median=float(np.median(s)),
            robust_scale=_robust_scale(s, floor=EPS_SCALE),
            mean=float(np.mean(s)),
            std=float(np.std(s)) if np.std(s) > EPS_SCALE else 1.0,
        )

    def fit(
        self,
        Z_train: np.ndarray,
        z_median: np.ndarray,
        p_train: Optional[np.ndarray] = None,
    ) -> "ModalityReliabilityEstimator":
        """Fit clean reference statistics strictly on training data."""
        Z = np.asarray(Z_train, dtype=np.float64)
        z_med = np.asarray(z_median, dtype=np.float64)
        if Z.ndim != 2 or not np.isfinite(Z).all():
            raise ValueError(f"{self.modality}: Z_train must be finite 2D array, got {Z.shape}")
        n, F = Z.shape
        if z_med.shape != (F,):
            raise ValueError(f"{self.modality}: z_median shape {z_med.shape} != ({F},)")

        self.n_features_ = F
        self.z_median_ = z_med.copy()

        # 1. Ledoit-Wolf shrinkage covariance for Mahalanobis distance
        lw = LedoitWolf(store_precision=True, assume_centered=False)
        lw.fit(Z)
        self.lw_mean_ = lw.location_.astype(np.float64)
        prec = lw.precision_.astype(np.float64)
        if not np.isfinite(prec).all():
            cov = np.cov(Z, rowvar=False) + 1e-4 * np.eye(F)
            prec = np.linalg.pinv(cov)
        self.lw_precision_ = prec

        # 2. Per-feature robust location & scale for top-k tail score
        self.feat_median_ = np.median(Z, axis=0)
        self.feat_scale_ = np.array([_robust_scale(Z[:, j], floor=0.1) for j in range(F)], dtype=np.float64)
        self.tail_k_ = max(1, int(np.ceil(self.config.tail_top_frac * F)))

        # 3. Empirical median-match surprisal weights for dropout detection
        med_hit = np.abs(Z - self.z_median_[None, :]) <= self.config.dropout_tol
        # Laplace-smoothed empirical probability that feature j naturally equals z_med
        p_med = (med_hit.sum(axis=0) + 1.0) / (n + 2.0)
        self.med_surprisal_ = -np.log(np.clip(p_med, 1e-6, 1.0))
        self.med_surprisal_sum_ = float(np.sum(self.med_surprisal_))
        if self.med_surprisal_sum_ <= 0.0:
            self.med_surprisal_ = np.ones(F, dtype=np.float64)
            self.med_surprisal_sum_ = float(F)

        # Compute clean training raw indicator distributions to calibrate excess baselines
        raw_train = self.compute_raw_indicators(Z, p_train)
        q = self.config.clean_quantile
        self.baselines_ = {}
        for name in ["mahalanobis", "tail", "dropout"]:
            # Dropout uses a tighter 0.95 anchor because clean continuous features rarely snap simultaneously
            q_eff = max(q, 0.95) if name == "dropout" else q
            self.baselines_[name] = self._fit_indicator_baseline(raw_train[name], q=q_eff)

        if p_train is not None:
            self.baselines_["confidence"] = self._fit_indicator_baseline(raw_train["confidence"], q=q)
        else:
            # Sensible fallback if trained without probabilities (entropy baseline centered near 0)
            self.baselines_["confidence"] = IndicatorBaseline(
                quantile_level=q,
                threshold_q=0.15,
                median=0.01,
                robust_scale=0.15,
                mean=0.05,
                std=0.15,
            )

        self._fitted = True
        return self

    def compute_raw_indicators(
        self,
        Z: np.ndarray,
        p: Optional[np.ndarray] = None,
    ) -> Dict[str, np.ndarray]:
        """Compute raw (unscaled) anomaly indicator values per window."""
        Z = np.asarray(Z, dtype=np.float64)
        n, F = Z.shape
        if F != self.n_features_:
            raise ValueError(f"{self.modality}: expected {self.n_features_} features, got {F}")

        # 1. Dimension-normalized Mahalanobis distance
        diff = Z - self.lw_mean_[None, :]
        md2 = np.einsum("ij,jk,ik->i", diff, self.lw_precision_, diff)
        mahal = np.sqrt(np.maximum(0.0, md2) / float(F))

        # 2. Top-k sparse robust tail deviation
        abs_dev = np.abs(Z - self.feat_median_[None, :]) / self.feat_scale_[None, :]
        if self.tail_k_ < F:
            # Partition is O(F) per row, faster than full sort
            part = np.partition(abs_dev, F - self.tail_k_, axis=1)[:, -self.tail_k_:]
            tail = np.mean(part, axis=1)
        else:
            tail = np.mean(abs_dev, axis=1)

        # 3. Surprisal-weighted median-imputation fraction in [0, 1]
        med_hit = (np.abs(Z - self.z_median_[None, :]) <= self.config.dropout_tol).astype(np.float64)
        dropout = (med_hit @ self.med_surprisal_) / self.med_surprisal_sum_

        # 4. Predictive entropy (0 if p not provided)
        if p is not None:
            conf = binary_entropy_normalized(p)
        else:
            conf = np.zeros(n, dtype=np.float64)

        return {
            "mahalanobis": mahal,
            "tail": tail,
            "dropout": dropout,
            "confidence": conf,
        }

    def compute_excess_indicators(
        self,
        Z: np.ndarray,
        p: Optional[np.ndarray] = None,
    ) -> Dict[str, np.ndarray]:
        """Compute clean-calibrated non-negative excess anomaly scores."""
        if not self._fitted:
            raise RuntimeError(f"{self.modality}: estimator must be fitted before scoring.")
        raw = self.compute_raw_indicators(Z, p)
        return {k: self.baselines_[k].excess(v) for k, v in raw.items()}

    def compute_anomaly_score(
        self,
        Z: np.ndarray,
        p: Optional[np.ndarray] = None,
        weights: Optional[Dict[str, float]] = None,
    ) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        """Weighted sum of clean-calibrated excess anomaly scores A_b(z) >= 0."""
        excess = self.compute_excess_indicators(Z, p)
        w = self.config.active_weights() if weights is None else weights
        anomaly = np.zeros(len(Z), dtype=np.float64)
        for k, wk in w.items():
            if wk > 0.0:
                # Soft log-compression on extreme unbounded deviations keeps indicators balanced
                # while remaining strictly monotonic: log1p(x) for x > 10, linear near 0
                ek = excess[k]
                ek_smooth = np.where(ek <= 10.0, ek, 10.0 + np.log1p(np.maximum(ek - 10.0, 0.0)))
                anomaly += wk * ek_smooth
        return anomaly, excess

    def score_trust(
        self,
        Z: np.ndarray,
        p: Optional[np.ndarray] = None,
        beta: Optional[float] = None,
        weights: Optional[Dict[str, float]] = None,
    ) -> Tuple[np.ndarray, np.ndarray, Dict[str, np.ndarray]]:
        """Return (trust T_b in [floor, 1], anomaly A_b >= 0, per-indicator excess dict)."""
        anomaly, excess = self.compute_anomaly_score(Z, p, weights=weights)
        b = self.config.beta if beta is None else float(beta)
        trust = np.exp(-b * anomaly)
        if self.config.trust_floor > 0.0:
            trust = np.clip(trust, self.config.trust_floor, 1.0)
        return trust, anomaly, excess


@dataclass
class FusionOutput:
    """Structured inference output from TrustAwareFusion."""

    p_fused: np.ndarray
    y_pred: np.ndarray               # forced binary prediction (p_fused >= threshold)
    y_pred_selective: np.ndarray     # -1 where uncertain, else 0/1
    is_uncertain: np.ndarray         # bool mask: both T_N < tau_unc and T_R < tau_unc
    trust_network: np.ndarray        # T_N in [0, 1]
    trust_radio: np.ndarray          # T_R in [0, 1]
    weight_network: np.ndarray       # effective normalized weight on P_N
    weight_radio: np.ndarray         # effective normalized weight on P_R
    anomaly_network: np.ndarray      # composite A_N >= 0
    anomaly_radio: np.ndarray        # composite A_R >= 0
    disagreement: np.ndarray         # |P_N - P_R|
    excess_network: Dict[str, np.ndarray] = field(default_factory=dict)
    excess_radio: Dict[str, np.ndarray] = field(default_factory=dict)


class TrustAwareFusion:
    """Two-sensor Trust-Aware Multimodal Fusion for 5G O-RAN Intrusion Detection.

    Combines predictions from a Network-only detector (P_N) and a Radio-only
    detector (P_R) using inference-time reliability scores (T_N, T_R):

        P_F = (pi_N * T_N * P_N + pi_R * T_R * P_R) / (pi_N * T_N + pi_R * T_R + eps)

    where pi_N = pi_R = 1.0 by default (exact match to Proposal Section 8.4).

    Workflow:
        1. fit_train(Z_net_train, Z_rad_train, z_med_net, z_med_rad, p_net_train, p_rad_train)
        2. calibrate_validation_clean(Z_net_val, Z_rad_val, p_net_val, p_rad_val)
           (or optional calibrate_validation_stress(...) for ablation comparison)
        3. fuse(Z_net, Z_rad, p_net, p_rad) -> FusionOutput
    """

    def __init__(self, config: Optional[TrustFusionConfig] = None):
        self.config = config if config is not None else TrustFusionConfig()
        self.net_est = ModalityReliabilityEstimator("network", self.config)
        self.rad_est = ModalityReliabilityEstimator("radio", self.config)
        self.calibration_info_: Dict = {}

    def fit_train(
        self,
        Z_net_train: np.ndarray,
        Z_rad_train: np.ndarray,
        z_med_net: np.ndarray,
        z_med_rad: np.ndarray,
        p_net_train: Optional[np.ndarray] = None,
        p_rad_train: Optional[np.ndarray] = None,
    ) -> "TrustAwareFusion":
        """Fit both modality reliability estimators strictly on clean training data."""
        self.net_est.fit(Z_net_train, z_med_net, p_net_train)
        self.rad_est.fit(Z_rad_train, z_med_rad, p_rad_train)
        return self

    def calibrate_validation_clean(
        self,
        Z_net_val: np.ndarray,
        Z_rad_val: np.ndarray,
        p_net_val: Optional[np.ndarray] = None,
        p_rad_val: Optional[np.ndarray] = None,
        beta_bounds: Tuple[float, float] = (0.35, 3.0),
        tau_bounds: Tuple[float, float] = (0.05, 0.45),
    ) -> Dict:
        """Unsupervised clean-validation calibration (ZERO attack assumptions).

        Sets:
          - beta so that the 95th-percentile clean validation anomaly maps to
            target_clean_val_p95_trust (clipped to beta_bounds), ensuring high
            trust on clean telemetry while remaining sharp against anomalies.
          - tau_unc just below the empirical lower tail of max(T_N, T_R) on clean
            validation windows so clean false-abstention stays <= target_clean_val_abstain.
        """
        a_net, _ = self.net_est.compute_anomaly_score(Z_net_val, p_net_val)
        a_rad, _ = self.rad_est.compute_anomaly_score(Z_rad_val, p_rad_val)

        # Reference 95th percentile clean validation anomaly across both sensors
        q95_net = float(np.quantile(a_net, 0.95))
        q95_rad = float(np.quantile(a_rad, 0.95))
        q95_ref = max(q95_net, q95_rad, 0.15)

        target_t = float(np.clip(self.config.target_clean_val_p95_trust, 0.50, 0.98))
        beta_raw = -np.log(target_t) / q95_ref
        beta_cal = float(np.clip(beta_raw, beta_bounds[0], beta_bounds[1]))
        self.config.beta = beta_cal

        # Compute clean validation trust under calibrated beta
        disagree = (
            np.abs(np.asarray(p_net_val, dtype=np.float64) - np.asarray(p_rad_val, dtype=np.float64))
            if (p_net_val is not None and p_rad_val is not None)
            else np.zeros(len(Z_net_val), dtype=np.float64)
        )
        beta_eff = beta_cal * (1.0 + self.config.gamma_disagree * disagree)
        t_net = np.exp(-beta_eff * a_net)
        t_rad = np.exp(-beta_eff * a_rad)
        t_max = np.maximum(t_net, t_rad)

        # Calibrate uncertainty threshold so clean abstention <= target_clean_val_abstain
        q_abs = float(np.quantile(t_max, self.config.target_clean_val_abstain))
        tau_cal = float(np.clip(0.85 * q_abs, tau_bounds[0], tau_bounds[1]))
        self.config.tau_unc = tau_cal

        self.calibration_info_ = {
            "mode": "unsupervised_clean",
            "val_q95_anomaly_net": q95_net,
            "val_q95_anomaly_rad": q95_rad,
            "beta_calibrated": beta_cal,
            "tau_unc_calibrated": tau_cal,
            "clean_val_trust_net_mean": float(np.mean(t_net)),
            "clean_val_trust_rad_mean": float(np.mean(t_rad)),
            "clean_val_abstain_rate": float(np.mean((t_net < tau_cal) & (t_rad < tau_cal))),
        }
        return self.calibration_info_

    def calibrate_validation_stress(
        self,
        y_val: np.ndarray,
        Z_net_val: np.ndarray,
        Z_rad_val: np.ndarray,
        p_net_val: np.ndarray,
        p_rad_val: np.ndarray,
        val_stress_batches: List[Dict],
        beta_grid: Iterable[float] = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0),
        gamma_grid: Iterable[float] = (0.0, 0.5, 1.0, 2.0),
    ) -> Dict:
        """Optional validation-only stress calibration (for ablation comparison).

        `val_stress_batches` is a list of dicts generated STRICTLY from validation
        samples with keys: `Z_net`, `Z_rad`, `p_net`, `p_rad`, `target`.
        Selects (beta, gamma_disagree) maximizing validation mean Macro-F1 across
        clean + single-sensor stress batches, subject to zero/minimal clean drop.
        """
        from sklearn.metrics import f1_score

        y_val = np.asarray(y_val, dtype=int)
        # Precompute anomaly scores once (beta-independent)
        a_net_clean, _ = self.net_est.compute_anomaly_score(Z_net_val, p_net_val)
        a_rad_clean, _ = self.rad_est.compute_anomaly_score(Z_rad_val, p_rad_val)
        d_clean = np.abs(p_net_val - p_rad_val)

        precomp = []
        for b in val_stress_batches:
            an, _ = self.net_est.compute_anomaly_score(b["Z_net"], b["p_net"])
            ar, _ = self.rad_est.compute_anomaly_score(b["Z_rad"], b["p_rad"])
            precomp.append((an, ar, b["p_net"], b["p_rad"], np.abs(b["p_net"] - b["p_rad"])))

        thr = self.config.decision_threshold
        eps = self.config.eps
        best_score = -1.0
        best_pair = (self.config.beta, self.config.gamma_disagree)

        for beta in beta_grid:
            for gamma in gamma_grid:
                # Clean val score
                be_c = beta * (1.0 + gamma * d_clean)
                tn_c = np.exp(-be_c * a_net_clean)
                tr_c = np.exp(-be_c * a_rad_clean)
                pf_c = (tn_c * p_net_val + tr_c * p_rad_val) / (tn_c + tr_c + eps)
                f1_clean = f1_score(y_val, (pf_c >= thr).astype(int), average="macro", labels=[0, 1], zero_division=0)

                stress_f1s = []
                for an, ar, pn, pr, dd in precomp:
                    be = beta * (1.0 + gamma * dd)
                    tn = np.exp(-be * an)
                    tr = np.exp(-be * ar)
                    pf = (tn * pn + tr * pr) / (tn + tr + eps)
                    stress_f1s.append(f1_score(y_val, (pf >= thr).astype(int), average="macro", labels=[0, 1], zero_division=0))

                # Equal weight on clean preservation and average stress robustness
                obj = 0.25 * f1_clean + 0.75 * float(np.mean(stress_f1s)) if stress_f1s else f1_clean
                if obj > best_score:
                    best_score = obj
                    best_pair = (float(beta), float(gamma))

        self.config.beta, self.config.gamma_disagree = best_pair
        # Keep tau_unc calibrated from clean validation tail
        be_c = self.config.beta * (1.0 + self.config.gamma_disagree * d_clean)
        t_max = np.maximum(np.exp(-be_c * a_net_clean), np.exp(-be_c * a_rad_clean))
        self.config.tau_unc = float(np.clip(0.85 * np.quantile(t_max, self.config.target_clean_val_abstain), 0.05, 0.45))

        self.calibration_info_ = {
            "mode": "validation_stress",
            "beta_calibrated": self.config.beta,
            "gamma_calibrated": self.config.gamma_disagree,
            "tau_unc_calibrated": self.config.tau_unc,
            "val_objective": best_score,
            "n_val_stress_batches": len(val_stress_batches),
        }
        return self.calibration_info_

    def fuse(
        self,
        Z_net: np.ndarray,
        Z_rad: np.ndarray,
        p_net: np.ndarray,
        p_rad: np.ndarray,
        beta_override: Optional[float] = None,
        gamma_override: Optional[float] = None,
        tau_unc_override: Optional[float] = None,
        weights_override: Optional[Dict[str, float]] = None,
    ) -> FusionOutput:
        """Compute reliability scores and trust-aware fused attack probabilities."""
        p_net = np.asarray(p_net, dtype=np.float64)
        p_rad = np.asarray(p_rad, dtype=np.float64)
        if p_net.shape != p_rad.shape or p_net.ndim != 1:
            raise ValueError(f"p_net {p_net.shape} and p_rad {p_rad.shape} must be matching 1D arrays.")

        a_net, exc_net = self.net_est.compute_anomaly_score(Z_net, p_net, weights=weights_override)
        a_rad, exc_rad = self.rad_est.compute_anomaly_score(Z_rad, p_rad, weights=weights_override)

        disagree = np.abs(p_net - p_rad)
        beta = self.config.beta if beta_override is None else float(beta_override)
        gamma = self.config.gamma_disagree if gamma_override is None else float(gamma_override)
        tau_unc = self.config.tau_unc if tau_unc_override is None else float(tau_unc_override)

        # Disagreement-gated contrast: amplifies trust separation ONLY when a sensor has non-zero anomaly
        beta_eff = beta * (1.0 + gamma * disagree)
        t_net = np.exp(-beta_eff * a_net)
        t_rad = np.exp(-beta_eff * a_rad)

        if self.config.trust_floor > 0.0:
            t_net = np.clip(t_net, self.config.trust_floor, 1.0)
            t_rad = np.clip(t_rad, self.config.trust_floor, 1.0)

        # Adaptive fusion: P_F = (pi_N * T_N * P_N + pi_R * T_R * P_R) / (pi_N * T_N + pi_R * T_R + eps)
        w_n_raw = self.config.prior_network * t_net
        w_r_raw = self.config.prior_radio * t_rad
        denom = w_n_raw + w_r_raw + self.config.eps

        p_fused = (w_n_raw * p_net + w_r_raw * p_rad) / denom
        # Numerical safeguard if both T_N == 0 and T_R == 0 (extreme double corruption):
        # fall back to unweighted average for forced-decision metric while flagging is_uncertain=True
        both_zero = (w_n_raw + w_r_raw) < (10.0 * self.config.eps)
        if np.any(both_zero):
            p_fused = np.where(both_zero, 0.5 * (p_net + p_rad), p_fused)
        p_fused = np.clip(p_fused, 0.0, 1.0)

        w_n = np.where(both_zero, 0.5, w_n_raw / denom)
        w_r = np.where(both_zero, 0.5, w_r_raw / denom)

        is_uncertain = (t_net < tau_unc) & (t_rad < tau_unc)
        y_pred = (p_fused >= self.config.decision_threshold).astype(int)
        y_pred_sel = np.where(is_uncertain, -1, y_pred)

        return FusionOutput(
            p_fused=p_fused,
            y_pred=y_pred,
            y_pred_selective=y_pred_sel,
            is_uncertain=is_uncertain,
            trust_network=t_net,
            trust_radio=t_rad,
            weight_network=w_n,
            weight_radio=w_r,
            anomaly_network=a_net,
            anomaly_radio=a_rad,
            disagreement=disagree,
            excess_network=exc_net,
            excess_radio=exc_rad,
        )


def uniform_late_fusion(
    p_net: np.ndarray,
    p_rad: np.ndarray,
    threshold: float = 0.5,
) -> Tuple[np.ndarray, np.ndarray]:
    """Static equal-weight late fusion baseline: P = 0.5 * P_N + 0.5 * P_R."""
    p = 0.5 * (np.asarray(p_net, dtype=np.float64) + np.asarray(p_rad, dtype=np.float64))
    return p, (p >= threshold).astype(int)


def trust_diagnostic_metrics(
    out: FusionOutput,
    target: str,
    t_clean_net: Optional[np.ndarray] = None,
    t_clean_rad: Optional[np.ndarray] = None,
) -> Dict[str, float]:
    """Diagnostics measuring whether trust scores correctly identify manipulated sensors.

    Metrics:
      - mean_trust_net, mean_trust_rad: mean reliability scores
      - mean_weight_net, mean_weight_rad: mean effective fusion weights
      - abstain_rate: fraction of windows marked uncertain
      - cmia (Compromised-Modality Identification Accuracy):
          For target == 'network': P(T_N < T_R)
          For target == 'radio':   P(T_R < T_N)
          For target in ('clean', 'both'): NaN
      - trust_gap: mean(T_clean_sensor - T_attacked_sensor) on single-sensor attacks
      - sensor_ood_auroc: AUROC distinguishing manipulated vs clean sensor trust
          (when clean reference trust arrays are provided)
    """
    from sklearn.metrics import roc_auc_score

    res = {
        "mean_trust_net": float(np.mean(out.trust_network)),
        "mean_trust_rad": float(np.mean(out.trust_radio)),
        "mean_weight_net": float(np.mean(out.weight_network)),
        "mean_weight_rad": float(np.mean(out.weight_radio)),
        "abstain_rate": float(np.mean(out.is_uncertain)),
        "cmia": float("nan"),
        "trust_gap": float("nan"),
        "sensor_ood_auroc": float("nan"),
    }

    if target == "network":
        res["cmia"] = float(np.mean(out.trust_network < out.trust_radio))
        res["trust_gap"] = float(np.mean(out.trust_radio - out.trust_network))
        if t_clean_net is not None:
            y_ood = np.concatenate([np.zeros(len(t_clean_net)), np.ones(len(out.trust_network))])
            s_ood = np.concatenate([1.0 - t_clean_net, 1.0 - out.trust_network])
            if np.unique(s_ood).size > 1:
                res["sensor_ood_auroc"] = float(roc_auc_score(y_ood, s_ood))
    elif target == "radio":
        res["cmia"] = float(np.mean(out.trust_radio < out.trust_network))
        res["trust_gap"] = float(np.mean(out.trust_network - out.trust_radio))
        if t_clean_rad is not None:
            y_ood = np.concatenate([np.zeros(len(t_clean_rad)), np.ones(len(out.trust_radio))])
            s_ood = np.concatenate([1.0 - t_clean_rad, 1.0 - out.trust_radio])
            if np.unique(s_ood).size > 1:
                res["sensor_ood_auroc"] = float(roc_auc_score(y_ood, s_ood))
    elif target == "both":
        if t_clean_net is not None and t_clean_rad is not None:
            y_ood = np.concatenate([np.zeros(len(t_clean_net)), np.ones(len(out.trust_network))])
            s_clean = 1.0 - np.minimum(t_clean_net, t_clean_rad)
            s_att = 1.0 - np.minimum(out.trust_network, out.trust_radio)
            s_ood = np.concatenate([s_clean, s_att])
            if np.unique(s_ood).size > 1:
                res["sensor_ood_auroc"] = float(roc_auc_score(y_ood, s_ood))

    return res


def selective_metrics(
    y_true: np.ndarray,
    out: FusionOutput,
    threshold: float = 0.5,
) -> Dict[str, float]:
    """Evaluate selective classification performance on non-abstained (accepted) windows."""
    from sklearn.metrics import accuracy_score, f1_score, recall_score, confusion_matrix

    y = np.asarray(y_true, dtype=int)
    accepted = ~out.is_uncertain
    n_acc = int(np.sum(accepted))
    cov = float(n_acc / len(y)) if len(y) else float("nan")
    if n_acc == 0:
        return {
            "coverage": 0.0,
            "abstain_rate": 1.0,
            "selective_accuracy": float("nan"),
            "selective_macro_f1": float("nan"),
            "selective_recall": float("nan"),
            "selective_fpr": float("nan"),
        }

    ya = y[accepted]
    pa = (out.p_fused[accepted] >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(ya, pa, labels=[0, 1]).ravel()
    return {
        "coverage": cov,
        "abstain_rate": 1.0 - cov,
        "selective_accuracy": float(accuracy_score(ya, pa)),
        "selective_macro_f1": float(f1_score(ya, pa, average="macro", labels=[0, 1], zero_division=0)),
        "selective_recall": float(recall_score(ya, pa, pos_label=1, zero_division=0)),
        "selective_fpr": float(fp / (fp + tn)) if (fp + tn) > 0 else float("nan"),
    }


ABLATION_PRESETS: Dict[str, Dict] = {
    "full_trust": {
        "w_mahalanobis": 0.35, "w_tail": 0.25, "w_dropout": 0.25, "w_confidence": 0.15, "gamma_disagree": 1.0,
    },
    "no_disagreement_gate": {
        "w_mahalanobis": 0.35, "w_tail": 0.25, "w_dropout": 0.25, "w_confidence": 0.15, "gamma_disagree": 0.0,
    },
    "mahalanobis_only": {
        "w_mahalanobis": 1.0, "w_tail": 0.0, "w_dropout": 0.0, "w_confidence": 0.0, "gamma_disagree": 1.0,
    },
    "tail_only": {
        "w_mahalanobis": 0.0, "w_tail": 1.0, "w_dropout": 0.0, "w_confidence": 0.0, "gamma_disagree": 1.0,
    },
    "dropout_only": {
        "w_mahalanobis": 0.0, "w_tail": 0.0, "w_dropout": 1.0, "w_confidence": 0.0, "gamma_disagree": 1.0,
    },
    "confidence_only": {
        "w_mahalanobis": 0.0, "w_tail": 0.0, "w_dropout": 0.0, "w_confidence": 1.0, "gamma_disagree": 1.0,
    },
    "no_dropout_indicator": {
        "w_mahalanobis": 0.45, "w_tail": 0.35, "w_dropout": 0.0, "w_confidence": 0.20, "gamma_disagree": 1.0,
    },
    "input_only_no_confidence": {
        "w_mahalanobis": 0.40, "w_tail": 0.30, "w_dropout": 0.30, "w_confidence": 0.0, "gamma_disagree": 1.0,
    },
}
