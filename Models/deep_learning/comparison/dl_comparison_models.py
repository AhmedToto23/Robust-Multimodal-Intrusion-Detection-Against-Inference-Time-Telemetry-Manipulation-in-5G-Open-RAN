"""dl_comparison_models.py - architectures and inference helpers for the deep-learning comparison (Member 3 -> Member 4).

Exported by 05_deep_learning_comparison.ipynb (single source of truth: the notebook embeds exactly this text).
Requires torch >= 2.0, numpy, pandas. Nothing here trains a model or reads the project datasets.

    import dl_comparison_models as dlc
    ckpt = dlc.load_checkpoint("Models/deep_learning/comparison/multimodal_ft_transformer.pt")
    p = dlc.predict_proba(ckpt, raw_features_df)                 # attack probability (raw telemetry in, 'primary' seed)
    Z = dlc.apply_preprocessing(raw_features_df, ckpt["preprocessing"])   # model-space (imputed + standardised) array
    raw_again = dlc.invert_preprocessing(Z, ckpt["preprocessing"])        # back to raw units (for perturbation studies)
"""
import math
import numpy as np
import pandas as pd
import torch
from torch import nn
import torch.nn.functional as tnf

# ==== MLP ====
class MLP(nn.Module):
    """Linear -> BatchNorm -> ReLU -> Dropout blocks, then a Linear layer with ONE logit.  (B, F) -> (B,)"""

    def __init__(self, n_features, hidden_dims=(256, 128, 64), dropout=0.3):
        super().__init__()
        layers, d = [], n_features
        for h in hidden_dims:
            layers += [nn.Linear(d, h), nn.BatchNorm1d(h), nn.ReLU(), nn.Dropout(dropout)]
            d = h
        layers.append(nn.Linear(d, 1))
        self.net = nn.Sequential(*layers)

    def forward(self, x):                      # x: (B, F)
        return self.net(x).squeeze(-1)

# ==== CNN ====
class CNN1D(nn.Module):
    """1D CNN over the feature vector.  ASSUMPTION (not a fact about the data): neighbouring columns in the fixed schema order
    are treated as neighbouring positions. The convolution therefore learns local patterns over *adjacent columns*, NOT temporal patterns.
    (B, F) -> (B, 1, F) -> [Conv1d -> BatchNorm -> ReLU -> MaxPool(2)] x n -> (B, C, L) -> global average over positions -> (B, C) -> head -> (B,)"""

    def __init__(self, n_features, channels=(32, 64), kernel_size=3, dropout=0.3, head_dim=64):
        super().__init__()
        blocks, c_in, length = [], 1, n_features
        for c in channels:
            blocks += [nn.Conv1d(c_in, c, kernel_size, padding=kernel_size // 2), nn.BatchNorm1d(c), nn.ReLU(), nn.MaxPool1d(2)]
            c_in, length = c, length // 2
        if length < 1:
            raise ValueError("too many pooling stages for this number of features")
        self.conv = nn.Sequential(*blocks)
        self.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(c_in, head_dim), nn.ReLU(), nn.Dropout(dropout), nn.Linear(head_dim, 1))

    def forward(self, x):                      # x: (B, F)
        h = self.conv(x.unsqueeze(1))          # (B, C, L)
        return self.head(h.mean(dim=-1)).squeeze(-1)

# ==== LSTM ====
class SequenceRNN(nn.Module):
    """Recurrent classifier over a feature 'sequence' (shared by the LSTM and the GRU so the two are compared fairly).
    Tabular -> sequence mapping: the F features, in the fixed schema order, become F positions. Position i carries [x_i, e_i] where x_i is the
    standardised value and e_i is a learnable embedding of the feature's IDENTITY (so the network knows which feature it sees). These positions
    are NOT time steps: the order is an arbitrary schema order, so this architecture is exploratory and does not model temporal dependencies.
    (B, F) -> (B, F, 1 + E) -> RNN -> final hidden state (B, H) -> head -> (B,)"""

    def __init__(self, n_features, cell="lstm", hidden_size=64, num_layers=1, bidirectional=False, feature_embedding_dim=8, dropout=0.3, head_dim=32):
        super().__init__()
        self.cell = cell
        self.bidirectional = bidirectional
        self.feature_embedding = nn.Embedding(n_features, feature_embedding_dim)
        self.register_buffer("feature_ids", torch.arange(n_features), persistent=False)
        rnn_cls = nn.LSTM if cell == "lstm" else nn.GRU
        self.rnn = rnn_cls(input_size=1 + feature_embedding_dim, hidden_size=hidden_size, num_layers=num_layers, batch_first=True,
                           dropout=dropout if num_layers > 1 else 0.0, bidirectional=bidirectional)
        d = hidden_size * (2 if bidirectional else 1)
        self.head = nn.Sequential(nn.LayerNorm(d), nn.Dropout(dropout), nn.Linear(d, head_dim), nn.ReLU(), nn.Dropout(dropout), nn.Linear(head_dim, 1))

    def forward(self, x):                      # x: (B, F)
        emb = self.feature_embedding(self.feature_ids).unsqueeze(0).expand(x.shape[0], -1, -1)   # (B, F, E)
        seq = torch.cat([x.unsqueeze(-1), emb], dim=-1)                                          # (B, F, 1+E)
        _, h = self.rnn(seq)
        h_n = h[0] if self.cell == "lstm" else h                                                 # (layers*dirs, B, H)
        rep = torch.cat([h_n[-2], h_n[-1]], dim=-1) if self.bidirectional else h_n[-1]           # (B, H*dirs)
        return self.head(rep).squeeze(-1)


class LSTMClassifier(SequenceRNN):
    def __init__(self, n_features, hidden_size=64, num_layers=1, bidirectional=False, feature_embedding_dim=8, dropout=0.3, head_dim=32):
        super().__init__(n_features, "lstm", hidden_size, num_layers, bidirectional, feature_embedding_dim, dropout, head_dim)

# ==== GRU ====
class GRUClassifier(SequenceRNN):
    """GRU with exactly the same input representation, head and hyper-parameters as the LSTM (fair comparison)."""

    def __init__(self, n_features, hidden_size=64, num_layers=1, bidirectional=False, feature_embedding_dim=8, dropout=0.3, head_dim=32):
        super().__init__(n_features, "gru", hidden_size, num_layers, bidirectional, feature_embedding_dim, dropout, head_dim)

# ==== RESMLP ====
class ResidualBlock(nn.Module):
    """Pre-activation residual block: x + Linear(Dropout(ReLU(BN(Linear(Dropout(ReLU(BN(x))))))))."""

    def __init__(self, width, dropout):
        super().__init__()
        self.norm1, self.fc1 = nn.BatchNorm1d(width), nn.Linear(width, width)
        self.norm2, self.fc2 = nn.BatchNorm1d(width), nn.Linear(width, width)
        self.drop = nn.Dropout(dropout)

    def forward(self, x):
        h = self.fc1(self.drop(tnf.relu(self.norm1(x))))
        h = self.fc2(self.drop(tnf.relu(self.norm2(h))))
        return x + h


class ResidualMLP(nn.Module):
    """Linear(F -> width) -> n residual blocks -> BatchNorm -> ReLU -> Dropout -> Linear(width -> 1).  (B, F) -> (B,)"""

    def __init__(self, n_features, width=96, n_blocks=3, dropout=0.2):
        super().__init__()
        self.inp = nn.Linear(n_features, width)
        self.blocks = nn.ModuleList([ResidualBlock(width, dropout) for _ in range(n_blocks)])
        self.out_norm, self.drop, self.out = nn.BatchNorm1d(width), nn.Dropout(dropout), nn.Linear(width, 1)

    def forward(self, x):
        h = self.inp(x)
        for b in self.blocks:
            h = b(h)
        return self.out(self.drop(tnf.relu(self.out_norm(h)))).squeeze(-1)

# ==== FT ====
class FeatureTokenizer(nn.Module):
    """Numerical-feature tokenizer: feature i has its OWN learnable vector W_i and bias b_i, token_i = x_i * W_i + b_i.  (B, F) -> (B, F, d).
    Feature identity is carried by the per-feature parameters; no positional encoding is used."""

    def __init__(self, n_features, d_token):
        super().__init__()
        self.weight = nn.Parameter(torch.empty(n_features, d_token))
        self.bias = nn.Parameter(torch.empty(n_features, d_token))
        bound = 1.0 / math.sqrt(d_token)
        nn.init.uniform_(self.weight, -bound, bound)
        nn.init.uniform_(self.bias, -bound, bound)

    def forward(self, x):
        return x.unsqueeze(-1) * self.weight.unsqueeze(0) + self.bias.unsqueeze(0)


class FTTransformer(nn.Module):
    """FT-Transformer for numerical features (Gorishniy et al., 2021) with a binary head.
    (B, F) -> tokens (B, F, d) -> prepend learnable [CLS] -> (B, F+1, d) -> n x [pre-norm multi-head self-attention + feed-forward]
    -> (B, F+1, d) -> CLS vector (B, d) -> LayerNorm -> ReLU -> Linear -> logit (B,)."""

    def __init__(self, n_features, d_token=64, n_layers=2, n_heads=4, d_ffn=128, dropout=0.2):
        super().__init__()
        self.tokenizer = FeatureTokenizer(n_features, d_token)
        self.cls = nn.Parameter(torch.empty(1, 1, d_token))
        bound = 1.0 / math.sqrt(d_token)
        nn.init.uniform_(self.cls, -bound, bound)
        layer = nn.TransformerEncoderLayer(d_model=d_token, nhead=n_heads, dim_feedforward=d_ffn, dropout=dropout,
                                           activation="gelu", batch_first=True, norm_first=True)
        self.encoder = nn.TransformerEncoder(layer, num_layers=n_layers, enable_nested_tensor=False)
        self.head = nn.Sequential(nn.LayerNorm(d_token), nn.ReLU(), nn.Linear(d_token, 1))

    def forward(self, x):
        tokens = self.tokenizer(x)
        tokens = torch.cat([self.cls.expand(tokens.shape[0], -1, -1), tokens], dim=1)
        return self.head(self.encoder(tokens)[:, 0]).squeeze(-1)

# ==== HELPERS ====
REGISTRY = {"mlp": MLP, "cnn": CNN1D, "lstm": LSTMClassifier, "gru": GRUClassifier, "resmlp": ResidualMLP, "ft_transformer": FTTransformer}


def build_model(name, n_features, config):
    if name not in REGISTRY:
        raise ValueError(f"unknown architecture '{name}'; choose from {sorted(REGISTRY)}")
    return REGISTRY[name](n_features, **config)


def count_parameters(model):
    return int(sum(p.numel() for p in model.parameters() if p.requires_grad))


def apply_preprocessing(X, pre):
    """Training-fitted median imputation + standardisation. `pre` = plain lists (feature_names, median, mean, scale). Returns float32 (n, F)."""
    names = list(pre["feature_names"])
    missing = [c for c in names if c not in X.columns]
    if missing:
        raise KeyError(f"missing feature columns: {missing}")
    A = X[names].to_numpy(dtype=np.float64)
    A = np.where(np.isnan(A), np.asarray(pre["median"], dtype=np.float64), A)
    return ((A - np.asarray(pre["mean"], dtype=np.float64)) / np.asarray(pre["scale"], dtype=np.float64)).astype(np.float32)


def invert_preprocessing(Z, pre):
    """Model-space (standardised) values -> raw feature units, e.g. to express a perturbation in physical units."""
    return np.asarray(Z, dtype=np.float64) * np.asarray(pre["scale"], dtype=np.float64) + np.asarray(pre["mean"], dtype=np.float64)


def load_checkpoint(path):
    """Safe loading (weights_only=True): checkpoints contain only tensors, numbers, strings, lists and dicts."""
    return torch.load(path, map_location="cpu", weights_only=True)


def model_from_checkpoint(ckpt, seed=None):
    seed = ckpt["primary_seed"] if seed is None else seed
    model = build_model(ckpt["architecture"], len(ckpt["feature_names"]), ckpt["model_config"])
    model.load_state_dict(ckpt["runs"][seed]["state_dict"])
    return model.eval()


def predict_logits(ckpt, Z, seed=None, device="cpu"):
    """Logits from MODEL-SPACE input Z (n, F) as numpy array or torch tensor. Differentiable if Z is a tensor that requires grad
    (use model_from_checkpoint(...) directly for gradient-based studies)."""
    model = model_from_checkpoint(ckpt, seed).to(device)
    Zt = Z if torch.is_tensor(Z) else torch.from_numpy(np.asarray(Z, dtype=np.float32))
    with torch.set_grad_enabled(Zt.requires_grad):
        return model(Zt.to(device))


@torch.no_grad()
def predict_proba(ckpt, X, seed=None, device="cpu"):
    """Attack probability (attack = 1). Raw feature DataFrame in. seed=None -> primary seed; seed='all' -> matrix (n_seeds, n_rows)."""
    Z = torch.from_numpy(apply_preprocessing(X, ckpt["preprocessing"])).to(device)
    seeds = sorted(ckpt["runs"]) if seed == "all" else [ckpt["primary_seed"] if seed is None else seed]
    out = [torch.sigmoid(model_from_checkpoint(ckpt, s).to(device)(Z).double()).cpu().numpy() for s in seeds]
    return np.vstack(out) if seed == "all" else out[0]
