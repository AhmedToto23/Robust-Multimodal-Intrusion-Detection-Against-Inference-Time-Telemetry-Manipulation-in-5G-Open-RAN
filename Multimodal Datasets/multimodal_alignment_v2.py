#!/usr/bin/env python3
"""
multimodal_alignment_v2.py  --  Member 2, Phase 2: Validated multimodal alignment V2
=====================================================================================

Project : When One Sensor Lies: Robust Multimodal Intrusion Detection Against
          Inference-Time Telemetry Manipulation in 5G Open RAN

Exact inputs (all read-only):
    Network Dataset/network_clean.csv
    Network Dataset/network_feature_columns.json
    Radio Dataset/radio_window_features_v2.csv
    Radio Dataset/radio_feature_columns_v2.json
NOT used as inputs: network_features.csv (augmented/shuffled), radio_clean.csv, multimodal_dataset.csv.
(multimodal_dataset.csv is only opened, key columns only, for an optional "previous keys" comparison.)

Outputs (new V2 files, default folder = Multimodal Datasets/):
    multimodal_dataset_v2.csv, multimodal_feature_columns_v2.json, alignment_report_v2.md,
    alignment_report_v2.csv, timezone_validation_v2.csv, unmatched_windows_v2.csv
    (alignment_collisions_v2.csv only if a key collision stops the run)

Join: exact one-to-one inner join on (scenario_normalized, timestamp_s). No nearest-neighbour,
no approximate matching, no fabricated observations, no imputation.  The result is TEMPORAL
alignment at 1-second resolution; it is NOT packet-to-UE or flow-to-UE correspondence.

Run:   python multimodal_alignment_v2.py [--output-dir DIR] [--network-csv P] [--network-json P]
                                         [--radio-csv P] [--radio-json P] [--skip-repro-check]
Exit codes: 0 = all hard validations passed; 1 = a validation failed (run stopped);
            2 = duplicate-key collision found (run stopped).
Dependencies: Python >= 3.9 (zoneinfo + system tzdata), pandas, numpy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

VERSION = "multimodal_alignment_v2.0.0"

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
DEFAULT_NETWORK_CSV = REPO_DIR / "Network Dataset" / "network_clean.csv"
DEFAULT_NETWORK_JSON = REPO_DIR / "Network Dataset" / "network_feature_columns.json"
DEFAULT_RADIO_CSV = REPO_DIR / "Radio Dataset" / "radio_window_features_v2.csv"
DEFAULT_RADIO_JSON = REPO_DIR / "Radio Dataset" / "radio_feature_columns_v2.json"
PREVIOUS_MULTIMODAL = REPO_DIR / "Multimodal Datasets" / "multimodal_dataset.csv"

OUT_DATASET = "multimodal_dataset_v2.csv"
OUT_JSON = "multimodal_feature_columns_v2.json"
OUT_REPORT = "alignment_report_v2.md"
OUT_REPORT_CSV = "alignment_report_v2.csv"
OUT_TZ = "timezone_validation_v2.csv"
OUT_UNMATCHED = "unmatched_windows_v2.csv"
OUT_COLLISIONS = "alignment_collisions_v2.csv"

NET_LABELS = ["family", "mode", "class_fm", "is_attack"]
RADIO_LABELS = ["class_fm", "family", "mode", "is_attack", "ddos"]
DUBLIN = ZoneInfo("Europe/Dublin")
SCENARIO_RULE = (r"^DDOS_", "DDOS")             # documented normalisation: leading "DDOS_" -> "DDOS"
PLAUSIBLE_START = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp())
PLAUSIBLE_END = int(datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc).timestamp())

# Audit/user targets: compared and reported, never used in logic.
EXPECTED_TARGETS = {
    "scenario_mappings": 35, "network_windows": 4190, "radio_windows": 4590,
    "matched_windows": 4139, "unmatched_network_windows": 51, "unmatched_radio_windows": 451,
    "network_feature_count": 29, "radio_profile_A_count": 32, "radio_profile_B_count": 40,
    "profile_A_total": 61, "profile_B_total": 69,
}

NET_REQUIRED = ["window_id", "scenario", "family", "mode", "class_fm", "is_attack", "window_start_epoch_utc",
                "window_start_utc", "window_start_wall_epoch", "tz_label", "tz_offset_assumed_s", "t_rel_s",
                "coverage_s", "is_partial", "pkts"]
RADIO_REQUIRED = ["scenario", "timestamp_s", "first_timestamp_ms", "last_timestamp_ms", "radio_window_id",
                  "family", "mode", "class_fm", "is_attack", "ddos", "n_records", "n_ue_reporting", "puschSnr_n"]
RADIO_OPTIONAL_DIAG = ["dlBytes_delta_sum", "ulBytes_delta_sum", "delta_interval_start_ms_min",
                       "delta_interval_end_ms_max"]          # read ONLY for report diagnostics, never joined

DIAG_COLUMN_MAP = {"n_records": "radio_n_records", "n_ue_reporting": "radio_n_ue_reporting",
                   "puschSnr_n": "radio_pusch_valid_reports"}


class AlignmentCollisionError(RuntimeError):
    def __init__(self, message, collisions: pd.DataFrame):
        super().__init__(message)
        self.collisions = collisions


class SchemaError(RuntimeError):
    pass


class Checks:
    def __init__(self):
        self.items: list[dict] = []

    def add(self, name, passed, detail="", kind="assert"):
        self.items.append({"name": name, "passed": bool(passed), "detail": str(detail), "kind": kind})

    def failed(self):
        return [c for c in self.items if c["kind"] == "assert" and not c["passed"]]

    def discrepancies(self):
        return [c for c in self.items if c["kind"] == "target" and not c["passed"]]

    def frame(self):
        fr = pd.DataFrame(self.items, columns=["name", "passed", "detail", "kind"])
        fr["result"] = np.where(fr["passed"], "PASS", np.where(fr["kind"] == "assert", "FAIL", "DISCREPANCY"))
        return fr


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fmt(v) -> str:
    if v is None or v is pd.NA or (isinstance(v, float) and np.isnan(v)):
        return ""
    if isinstance(v, (bool, np.bool_)):
        return "yes" if v else "no"
    if isinstance(v, (int, np.integer)):
        return f"{int(v):,}" if abs(int(v)) < 10**10 else str(int(v))
    if isinstance(v, (float, np.floating)):
        v = float(v)
        if v == int(v) and abs(v) < 1e10:
            return f"{int(v):,}"
        return f"{v:,.2f}" if abs(v) < 1e6 else f"{v:.4e}"
    return str(v)


def md_table(df: pd.DataFrame, index=False) -> str:
    if index:
        df = df.reset_index()
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join(_fmt(v) for v in row) + " |")
    return "\n".join(lines)


def utc_str(ts: pd.Series) -> pd.Series:
    return pd.to_datetime(ts, unit="s", utc=True).dt.strftime("%Y-%m-%d %H:%M:%S")


def normalize_scenario(name: str) -> str:
    return re.sub(SCENARIO_RULE[0], SCENARIO_RULE[1], name)


def dublin_info(epoch: int) -> tuple[str, int]:
    d = datetime.fromtimestamp(int(epoch), tz=DUBLIN)
    return d.tzname(), int(d.utcoffset().total_seconds())


def dublin_transitions(start: int, end: int) -> list[int]:
    """UTC epochs (hour resolution) at which Europe/Dublin's UTC offset changes within [start, end]."""
    start -= start % 3600                      # align the scan grid to whole UTC hours
    out, prev = [], dublin_info(start)[1]
    for t in range(start, end + 1, 3600):
        off = dublin_info(t)[1]
        if off != prev:
            out.append(t)
            prev = off
    return out


def _runs(missing: list[int]) -> dict[int, tuple[int, int]]:
    """map each missing second -> (run_start, run_length) for runs of consecutive seconds"""
    res, i = {}, 0
    while i < len(missing):
        j = i
        while j + 1 < len(missing) and missing[j + 1] == missing[j] + 1:
            j += 1
        for t in missing[i:j + 1]:
            res[t] = (missing[i], j - i + 1)
        i = j + 1
    return res


def _frames_equal(a, b) -> bool:
    try:
        pd.testing.assert_frame_equal(a, b, check_exact=False, rtol=1e-12, atol=1e-12)
        return True
    except AssertionError:
        return False


# --------------------------------------------------------------------------- #
# pipeline
# --------------------------------------------------------------------------- #
class AlignmentPipeline:
    def __init__(self, network_csv=DEFAULT_NETWORK_CSV, network_json=DEFAULT_NETWORK_JSON,
                 radio_csv=DEFAULT_RADIO_CSV, radio_json=DEFAULT_RADIO_JSON, output_dir=SCRIPT_DIR,
                 repro_check=True):
        self.paths = {"network_csv": Path(network_csv).resolve(), "network_json": Path(network_json).resolve(),
                      "radio_csv": Path(radio_csv).resolve(), "radio_json": Path(radio_json).resolve()}
        self.output_dir = Path(output_dir).resolve()
        self.repro_check = repro_check
        self.checks = Checks()
        self.written: list[Path] = []
        self.blocked = False

    # ---- Step 1: load + schema + key uniqueness --------------------------------
    def step1_load_and_validate(self):
        for name, path in self.paths.items():
            if self.output_dir in path.parents and path.name in {OUT_DATASET, OUT_JSON, OUT_REPORT, OUT_REPORT_CSV,
                                                                 OUT_TZ, OUT_UNMATCHED}:
                raise RuntimeError(f"input {path} collides with an output name")
        self.input_sha = {k: sha256_file(p) for k, p in self.paths.items()}
        self.input_stat = {k: (p.stat().st_size, p.stat().st_mtime_ns) for k, p in self.paths.items()}
        self.net = pd.read_csv(self.paths["network_csv"]).copy()
        self.radio = pd.read_csv(self.paths["radio_csv"]).copy()
        self.net_meta = json.load(open(self.paths["network_json"], encoding="utf-8"))
        self.radio_meta = json.load(open(self.paths["radio_json"], encoding="utf-8"))
        ck = self.checks

        self.net_features = list(self.net_meta["feature_cols"])
        prof = self.radio_meta["model_feature_profiles"]
        self.radio_A = list(prof["A_conservative_core"])
        self.radio_B = list(prof["B_extended_candidate"])
        self.profile_A = self.net_features + self.radio_A
        self.profile_B = self.net_features + self.radio_B

        miss_n = [c for c in NET_REQUIRED + self.net_features if c not in self.net.columns]
        miss_r = [c for c in RADIO_REQUIRED + self.radio_B if c not in self.radio.columns]
        ck.add("schema: network_clean.csv has every required column and every listed feature column", not miss_n,
               f"missing={miss_n}" if miss_n else f"{self.net.shape[0]:,} rows x {self.net.shape[1]} columns")
        ck.add("schema: radio_window_features_v2.csv has every required column and every Profile B column",
               not miss_r, f"missing={miss_r}" if miss_r else f"{self.radio.shape[0]:,} rows x {self.radio.shape[1]} columns")
        if miss_n or miss_r:
            raise SchemaError(f"schema validation failed (network missing {miss_n}, radio missing {miss_r})")
        ck.add("schema: network feature list has no duplicate names", len(set(self.net_features)) == len(self.net_features))
        ck.add("schema: Profile A is a subset of Profile B (radio side)", set(self.radio_A) <= set(self.radio_B))
        ck.add("schema: network feature names and radio feature names are disjoint",
               not (set(self.net_features) & set(self.radio_B)),
               f"overlap={sorted(set(self.net_features) & set(self.radio_B))}")

        # key uniqueness (before any joining)
        coll = []
        d = self.net[self.net.duplicated(["scenario", "window_start_epoch_utc"], keep=False)]
        if len(d):
            coll.append(d.assign(collision="network (scenario, window_start_epoch_utc)"))
        d = self.net[self.net.duplicated("window_id", keep=False)]
        if len(d):
            coll.append(d.assign(collision="network window_id"))
        d = self.radio[self.radio.duplicated(["scenario", "timestamp_s"], keep=False)]
        if len(d):
            coll.append(d.assign(collision="radio (scenario, timestamp_s)"))
        if coll:
            c = pd.concat(coll, ignore_index=True)
            self.output_dir.mkdir(parents=True, exist_ok=True)
            c.to_csv(self.output_dir / OUT_COLLISIONS, index=False, lineterminator="\n")
            raise AlignmentCollisionError(f"{len(c)} rows participate in duplicate alignment keys; run stopped", c)
        ck.add("keys: network (scenario, window_start_epoch_utc) and window_id are unique", True,
               f"{len(self.net):,} unique network windows")
        ck.add("keys: radio (scenario, timestamp_s) is unique", True, f"{len(self.radio):,} unique radio windows")
        return self

    # ---- Step 2: scenario normalisation -----------------------------------------
    def step2_normalize_scenarios(self):
        ck = self.checks
        radio_names = sorted(self.radio["scenario"].unique())
        net_names = sorted(self.net["scenario"].unique())
        mapping = {r: normalize_scenario(r) for r in radio_names}
        self.mapping = mapping
        mapped = list(mapping.values())
        collisions = {v: [k for k, x in mapping.items() if x == v] for v in set(mapped) if mapped.count(v) > 1}
        ck.add("scenarios: normalisation is injective (no two radio scenarios collapse to one name)",
               not collisions, f"collisions={collisions}" if collisions else f"{len(radio_names)} radio names -> {len(set(mapped))} distinct")
        ck.add("scenarios: every radio scenario maps onto a network scenario (none dropped)",
               set(mapped) <= set(net_names), f"radio-only after mapping={sorted(set(mapped) - set(net_names))}")
        ck.add("scenarios: every network scenario is produced by exactly one radio scenario (none dropped)",
               set(net_names) <= set(mapped), f"network-only={sorted(set(net_names) - set(mapped))}")
        ck.add("scenarios: mapping is one-to-one (bijection between radio and network names)",
               not collisions and set(mapped) == set(net_names) and len(radio_names) == len(net_names),
               f"{len(radio_names)} radio / {len(net_names)} network scenarios")
        changed = {k: v for k, v in mapping.items() if k != v}
        bad_rule = [k for k, v in changed.items() if not k.startswith("DDOS_") or v != "DDOS" + k[len("DDOS_"):]]
        ck.add("scenarios: only names starting with 'DDOS_' are changed, and only by dropping the underscore",
               not bad_rule, f"{len(changed)} names changed")
        ck.add("scenarios: normalised radio names are unique", len(set(mapped)) == len(mapped))
        self.radio = self.radio.assign(scenario_norm=self.radio["scenario"].map(mapping))
        k = self.radio.duplicated(["scenario_norm", "timestamp_s"], keep=False)
        if k.any():
            c = self.radio[k].assign(collision="radio normalised (scenario_norm, timestamp_s)")
            self.output_dir.mkdir(parents=True, exist_ok=True)
            c.to_csv(self.output_dir / OUT_COLLISIONS, index=False, lineterminator="\n")
            raise AlignmentCollisionError("normalised radio keys collide; run stopped", c)
        ck.add("keys: radio (scenario_normalized, timestamp_s) is unique", True)
        self.scenario_table = pd.DataFrame({"radio_scenario": radio_names,
                                            "network_scenario": [mapping[r] for r in radio_names]})
        return self

    # ---- Step 3: timestamps ------------------------------------------------------
    def step3_timestamps(self):
        ck, n, r = self.checks, self.net, self.radio
        e = n["window_start_epoch_utc"]
        finite = np.isfinite(e.astype(float)).all()
        integral = bool((e == e.round()).all())
        ck.add("timestamps: network window_start_epoch_utc is finite and integer-valued epoch seconds",
               bool(finite and integral), f"non-integer values={int((e != e.round()).sum())}")
        n["timestamp_s"] = e.round().astype("int64")
        ck.add("timestamps: network epochs lie in the plausible 2025 UTC range",
               bool(n["timestamp_s"].between(PLAUSIBLE_START, PLAUSIBLE_END).all()))
        ck.add("timestamps: radio timestamp_s has an integer dtype", bool(pd.api.types.is_integer_dtype(r["timestamp_s"])),
               f"dtype={r['timestamp_s'].dtype}")
        ck.add("timestamps: radio timestamp_s lies in the plausible 2025 UTC range",
               bool(r["timestamp_s"].between(PLAUSIBLE_START, PLAUSIBLE_END).all()))
        same_sec = ((r["first_timestamp_ms"] // 1000 == r["timestamp_s"]) & (r["last_timestamp_ms"] // 1000 == r["timestamp_s"]))
        ck.add("timestamps: radio first/last timestamp_ms fall inside the second given by timestamp_s",
               bool(same_sec.all()), f"mismatches={int((~same_sec).sum())}")
        # Member 1's conversion is VALIDATED, never modified or repeated
        ck.add("timestamps: network wall epoch - UTC epoch equals tz_offset_assumed_s on every row (conversion consistent)",
               bool(((n["window_start_wall_epoch"] - n["window_start_epoch_utc"]) == n["tz_offset_assumed_s"]).all()))
        ck.add("timestamps: window_start_utc text equals the UTC decoding of the epoch",
               bool((pd.to_datetime(n["window_start_utc"], utc=True, format="ISO8601") ==
                     pd.to_datetime(n["timestamp_s"], unit="s", utc=True)).all()))
        k = n["window_id"].str.split("@").str[1].astype("int64")
        ck.add("timestamps: window_id suffix equals 4 x epoch (quarter-second window index) on every row",
               bool((k == 4 * n["timestamp_s"]).all()))
        ck.add("timestamps: network windows are whole-second aligned (no fractional second)", integral)
        return self

    # ---- Step 4: timezone validation ---------------------------------------------
    def step4_timezone(self):
        ck, n = self.checks, self.net
        lo, hi = int(n["timestamp_s"].min()) - 14 * 86400, int(n["timestamp_s"].max()) + 14 * 86400
        self.transitions = dublin_transitions(lo, hi)
        epochs = n["timestamp_s"].unique()
        info = {int(t): dublin_info(t) for t in epochs}
        n["_exp_label"] = n["timestamp_s"].map(lambda t: info[int(t)][0])
        n["_exp_off"] = n["timestamp_s"].map(lambda t: info[int(t)][1])
        rows = []
        for scn, g in n.groupby("scenario", sort=True):
            first, last = int(g["timestamp_s"].min()), int(g["timestamp_s"].max())
            labels = sorted(g["tz_label"].unique())
            rec = labels[0] if len(labels) == 1 else "|".join(labels)
            n_match = int((g["tz_label"] == g["_exp_label"]).sum())
            exp_offs = sorted(g["_exp_off"].unique())
            applied = sorted(g["tz_offset_assumed_s"].unique())
            wall_minus_utc = sorted((g["window_start_wall_epoch"] - g["window_start_epoch_utc"]).astype(int).unique())
            dist = min([abs(t - first) for t in self.transitions] + [abs(t - last) for t in self.transitions]) / 86400 \
                if self.transitions else np.nan
            spans = any(first <= t <= last for t in self.transitions)
            ok = (len(labels) == 1 and n_match == len(g) and exp_offs == applied == wall_minus_utc and not spans)
            rows.append({
                "scenario": scn,
                "capture_date_utc": utc_str(pd.Series([first])).iloc[0][:10],
                "capture_date_dublin": datetime.fromtimestamp(first, tz=DUBLIN).strftime("%Y-%m-%d"),
                "first_window_utc": utc_str(pd.Series([first])).iloc[0],
                "last_window_utc": utc_str(pd.Series([last])).iloc[0],
                "n_windows": len(g),
                "recorded_tz_label": rec,
                "expected_tz_label_first_window": info[first][0],
                "expected_tz_label_last_window": info[last][0],
                "windows_matching_expected_label": n_match,
                "expected_utc_offset_s": exp_offs[0] if len(exp_offs) == 1 else "|".join(map(str, exp_offs)),
                "applied_offset_s": applied[0] if len(applied) == 1 else "|".join(map(str, applied)),
                "wall_minus_utc_s": wall_minus_utc[0] if len(wall_minus_utc) == 1 else "|".join(map(str, wall_minus_utc)),
                "sign_and_offset_consistent": bool(exp_offs == applied == wall_minus_utc),
                "spans_dst_transition": bool(spans),
                "days_to_nearest_dst_transition": round(float(dist), 1) if dist == dist else np.nan,
                "validation_result": "PASS" if ok else "FAIL",
            })
        self.tz = pd.DataFrame(rows)
        n.drop(columns=["_exp_label", "_exp_off"], inplace=True)
        ck.add("timezone: every network scenario was examined", set(self.tz["scenario"]) == set(n["scenario"]),
               f"{len(self.tz)} of {n['scenario'].nunique()} scenarios")
        ck.add("timezone: each scenario carries exactly one tz_label", bool((~self.tz["recorded_tz_label"].str.contains(r"\|")).all()))
        ck.add("timezone: recorded tz_label equals the Europe/Dublin abbreviation for every window of every scenario",
               bool((self.tz["windows_matching_expected_label"] == self.tz["n_windows"]).all()),
               f"{int((self.tz['validation_result'] == 'PASS').sum())} of {len(self.tz)} scenarios PASS")
        ck.add("timezone: applied offset has the correct sign and size (UTC = wall - offset, offset = Dublin UTC offset)",
               bool(self.tz["sign_and_offset_consistent"].all()))
        ck.add("timezone: no scenario spans a Europe/Dublin clock change", not bool(self.tz["spans_dst_transition"].any()),
               f"transitions in range (UTC): {[datetime.fromtimestamp(t, tz=timezone.utc).strftime('%Y-%m-%d %H:%M') for t in self.transitions]}")
        ck.add("timezone: all scenario results are PASS", bool((self.tz["validation_result"] == "PASS").all()))
        return self

    # ---- Step 5: label validation (scenario level; network is authoritative) ------
    def step5_labels(self):
        ck, n, r = self.checks, self.net, self.radio
        nlab = n.groupby("scenario")[NET_LABELS].nunique()
        ck.add("labels: network labels are constant within each scenario", bool((nlab == 1).all().all()))
        ck.add("labels: no missing network labels", bool(n[NET_LABELS].notna().all().all()),
               f"nulls={n[NET_LABELS].isna().sum().to_dict()}")
        rlab = r.groupby("scenario_norm")[RADIO_LABELS].nunique()
        ck.add("labels: radio labels are constant within each scenario", bool((rlab == 1).all().all()))
        nl = n.groupby("scenario")[NET_LABELS].first()
        rl = r.groupby("scenario_norm")[RADIO_LABELS].first().reindex(nl.index)
        rows = []
        for scn in nl.index:
            row = {"scenario": scn}
            for f in ["class_fm", "family", "mode", "is_attack"]:
                row[f"network_{f}"] = nl.loc[scn, f]
                row[f"radio_{f}"] = rl.loc[scn, f]
                row[f"{f}_match"] = bool(nl.loc[scn, f] == rl.loc[scn, f])
            exp_ddos = int(nl.loc[scn, "mode"] == "DDoS")
            row["network_mode_is_DDoS"] = exp_ddos
            row["radio_ddos"] = int(rl.loc[scn, "ddos"])
            row["ddos_match"] = bool(exp_ddos == int(rl.loc[scn, "ddos"]))
            rows.append(row)
        self.label_table = pd.DataFrame(rows)
        for f in ["class_fm", "family", "mode", "is_attack", "ddos"]:
            ck.add(f"labels: radio {f} agrees with the network side for every scenario"
                   + (" (ddos compared with network mode == 'DDoS')" if f == "ddos" else ""),
                   bool(self.label_table[f"{f}_match"].all()),
                   f"mismatching scenarios={self.label_table.loc[~self.label_table[f'{f}_match'], 'scenario'].tolist()}")
        return self

    # ---- Step 5b: profile membership / leakage ------------------------------------
    def validate_profiles(self):
        ck, rm = self.checks, self.radio_meta
        for nm, got, exp_key in (("network feature count", len(self.net_features), "network_feature_count"),
                                 ("radio Profile A column count", len(self.radio_A), "radio_profile_A_count"),
                                 ("radio Profile B column count", len(self.radio_B), "radio_profile_B_count"),
                                 ("multimodal Profile A total", len(self.profile_A), "profile_A_total"),
                                 ("multimodal Profile B total", len(self.profile_B), "profile_B_total")):
            ck.add(f"profiles: {nm}", got == EXPECTED_TARGETS[exp_key],
                   f"expected {EXPECTED_TARGETS[exp_key]}, observed {got}", kind="target")
        banned_radio = set()
        for sec in ("identifiers", "labels", "timestamps", "diagnostic_features", "quality_flags",
                    "sensitivity_only_features", "held_out_features", "excluded_features"):
            banned_radio |= set(rm[sec]["columns"])
        banned_radio |= {"dlBytes", "ulBytes", "dlBytes_delta_sum", "ulBytes_delta_sum"}
        leak = sorted(set(self.radio_B) & banned_radio)
        ck.add("leakage: Profile columns contain no radio identifier/label/timestamp/diagnostic/quality-flag/held-out/"
               "sensitivity-only/excluded/byte column", not leak, f"offending={leak}")
        banned_net = set(self.net_meta["meta_cols"]) | set(self.net_meta["diag_cols_not_for_models"]) \
            | {"tz_label", "tz_offset_assumed_s", "window_start_utc", "window_start_wall_epoch", "coverage_s", "t_rel_s",
               "is_partial", "window_id", "scenario", "timestamp_s", "window_start_epoch_utc"}
        leak_n = sorted(set(self.net_features) & banned_net)
        ck.add("leakage: network features contain no metadata/diagnostic/time/label column", not leak_n, f"offending={leak_n}")
        held = set(rm["held_out_features"]["columns"])
        ck.add("leakage: no held-out radio KPI column in either profile", not (held & set(self.profile_B)))
        ck.add("leakage: no byte-counter column (dlBytes/ulBytes*) in either profile",
               not any(re.match(r"^(dl|ul)Bytes", c) for c in self.profile_B))
        ck.add("leakage: radio profile columns are exactly <KPI>_{mean,std,min,max}",
               all(re.match(r"^[A-Za-z]+_(mean|std|min|max)$", c) for c in self.radio_B))
        ck.add("leakage: label/scenario/time names are absent from the Profile columns",
               not ({"family", "mode", "class_fm", "is_attack", "ddos", "scenario", "timestamp_s"} & set(self.profile_B)))
        return self

    # ---- Step 6: join ---------------------------------------------------------------
    def step6_join(self):
        ck, n, r = self.checks, self.net.copy(), self.radio.copy()
        n["scenario_normalized"] = n["scenario"]
        r["scenario_normalized"] = r["scenario_norm"]
        keys = ["scenario_normalized", "timestamp_s"]
        rcols = (["scenario", "scenario_normalized", "timestamp_s", "radio_window_id"] + list(DIAG_COLUMN_MAP)
                 + self.radio_B + [f"{c}" for c in RADIO_LABELS])
        rr = r[rcols].rename(columns={**DIAG_COLUMN_MAP, "scenario": "radio_scenario",
                                      **{c: f"radio_label_{c}" for c in RADIO_LABELS}})
        joined = n.merge(rr, on=keys, how="inner", validate="one_to_one")
        joined = joined.sort_values(["timestamp_s", "scenario", "window_id"], kind="mergesort").reset_index(drop=True)
        self.joined_full = joined

        # anti-joins (exact keys only)
        nk = n[keys].assign(_n=1)
        rk = r[keys].assign(_r=1)
        outer = nk.merge(rk, on=keys, how="outer")
        self.net_only_keys = outer[outer["_r"].isna()][keys].reset_index(drop=True)
        self.radio_only_keys = outer[outer["_n"].isna()][keys].reset_index(drop=True)
        ck.add("join: one-to-one inner join succeeded (pandas validate='one_to_one')", True, f"{len(joined):,} matched windows")
        ck.add("join: inner-join rows equal the exact-key intersection from the outer merge",
               len(joined) == int(outer["_n"].notna().mul(outer["_r"].notna()).sum()))

        # window-level label consistency on matched rows
        mism = {}
        for f in ["class_fm", "family", "mode", "is_attack"]:
            mism[f] = int((joined[f] != joined[f"radio_label_{f}"]).sum())
        mism["ddos"] = int(((joined["mode"] == "DDoS").astype(int) != joined["radio_label_ddos"]).sum())
        ck.add("labels: radio labels equal network labels on every matched window", sum(mism.values()) == 0,
               f"mismatching matched windows={mism}")
        return self

    # ---- Step 7: unmatched observations ----------------------------------------------
    def step7_unmatched(self):
        n, r = self.net, self.radio
        nspan = n.groupby("scenario")["timestamp_s"].agg(["min", "max"])
        rspan = r.groupby("scenario_norm")["timestamp_s"].agg(["min", "max"])
        nsets = n.groupby("scenario")["timestamp_s"].apply(lambda s: set(s.tolist())).to_dict()
        rsets = r.groupby("scenario_norm")["timestamp_s"].apply(lambda s: set(s.tolist())).to_dict()
        class_of = n.groupby("scenario")["class_fm"].first().to_dict()
        raw_of = {v: k for k, v in self.mapping.items()}
        nidx = n.set_index(["scenario", "timestamp_s"])
        ridx = r.set_index(["scenario_norm", "timestamp_s"])

        def classify(t, lo, hi):
            if t < lo:
                return "before_other_modality_start", "boundary", lo - t
            if t > hi:
                return "after_other_modality_end", "boundary", t - hi
            return "inside_other_modality_span", "interior", 0

        rows = []
        for modality, keys_df, other_span, other_sets in (("network_only", self.net_only_keys, rspan, rsets),
                                                          ("radio_only", self.radio_only_keys, nspan, nsets)):
            gap_runs = {}
            for scn in keys_df["scenario_normalized"].unique():
                lo, hi = int(other_span.loc[scn, "min"]), int(other_span.loc[scn, "max"])
                missing = [t for t in range(lo, hi + 1) if t not in other_sets[scn]]
                gap_runs[scn] = _runs(missing)
            for scn, t in keys_df.sort_values(["scenario_normalized", "timestamp_s"]).itertuples(index=False):
                t = int(t)
                lo, hi = int(other_span.loc[scn, "min"]), int(other_span.loc[scn, "max"])
                pos, bi, dist = classify(t, lo, hi)
                row = {"modality": modality, "scenario": scn, "source_scenario": raw_of[scn] if modality == "radio_only" else scn,
                       "class_fm_network_label": class_of[scn], "timestamp_s": t,
                       "utc_time": datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                       "other_modality_span_start_s": lo, "other_modality_span_end_s": hi,
                       "position_relative_to_other_modality": pos, "boundary_or_interior": bi,
                       "seconds_outside_other_span": int(dist)}
                if bi == "interior":
                    rs, rl = gap_runs[scn][t]
                    row["gap_run_start_s"], row["gap_run_length_s"] = rs, rl
                if modality == "network_only":
                    w = nidx.loc[(scn, t)]
                    row.update({"network_pkts": w["pkts"], "network_is_partial": int(w["is_partial"]),
                                "network_coverage_s": round(float(w["coverage_s"]), 6)})
                    row["assessment"] = ("boundary: radio capture does not cover this second" if bi == "boundary" else
                                         "interior: radio window absent inside the radio span (no UE record in this second)")
                else:
                    w = ridx.loc[(scn, t)]
                    row.update({"radio_n_records": int(w["n_records"]), "radio_n_ue_reporting": int(w["n_ue_reporting"])})
                    row["assessment"] = ("boundary: network capture does not cover this second" if bi == "boundary" else
                                         "interior: no network window for this second = no packet captured by the network "
                                         "sensor (01b emits only pkts>0 windows); NOT evidence that the UE was idle")
                rows.append(row)
        cols = ["modality", "scenario", "source_scenario", "class_fm_network_label", "timestamp_s", "utc_time",
                "other_modality_span_start_s", "other_modality_span_end_s", "position_relative_to_other_modality",
                "boundary_or_interior", "seconds_outside_other_span", "gap_run_start_s", "gap_run_length_s",
                "network_pkts", "network_is_partial", "network_coverage_s", "radio_n_records", "radio_n_ue_reporting",
                "assessment"]
        self.unmatched = pd.DataFrame(rows, columns=cols)
        for c in ["gap_run_start_s", "gap_run_length_s", "network_is_partial"]:
            self.unmatched[c] = self.unmatched[c].astype("Int64")
        self.nspan, self.rspan, self.nsets, self.rsets = nspan, rspan, nsets, rsets

        # per-scenario coverage
        m = self.joined_full.groupby("scenario_normalized").size()
        cov = pd.DataFrame({"network_scenario": n.groupby("scenario").size().index})
        cov["radio_scenario"] = cov["network_scenario"].map(raw_of)
        cov["class_fm"] = cov["network_scenario"].map(class_of)
        cov["tz_label"] = cov["network_scenario"].map(n.groupby("scenario")["tz_label"].first())
        cov["network_windows"] = cov["network_scenario"].map(n.groupby("scenario").size())
        cov["radio_windows"] = cov["network_scenario"].map(r.groupby("scenario_norm").size())
        cov["matched"] = cov["network_scenario"].map(m).fillna(0).astype(int)
        cov["unmatched_network"] = cov["network_windows"] - cov["matched"]
        cov["unmatched_radio"] = cov["radio_windows"] - cov["matched"]
        cov["network_retention_pct"] = (100.0 * cov["matched"] / cov["network_windows"]).round(4)
        cov["radio_retention_pct"] = (100.0 * cov["matched"] / cov["radio_windows"]).round(4)
        u = self.unmatched
        for mod, side in (("network_only", "network"), ("radio_only", "radio")):
            for kind in ("boundary", "interior"):
                s = u[(u["modality"] == mod) & (u["boundary_or_interior"] == kind)].groupby("scenario").size()
                cov[f"unmatched_{side}_{kind}"] = cov["network_scenario"].map(s).fillna(0).astype(int)
        cov["network_start_s"] = cov["network_scenario"].map(nspan["min"])
        cov["network_end_s"] = cov["network_scenario"].map(nspan["max"])
        cov["radio_start_s"] = cov["network_scenario"].map(rspan["min"])
        cov["radio_end_s"] = cov["network_scenario"].map(rspan["max"])
        cov["radio_lead_s"] = cov["network_start_s"] - cov["radio_start_s"]
        cov["radio_trail_s"] = cov["radio_end_s"] - cov["network_end_s"]
        cov["labels_consistent"] = cov["network_scenario"].map(
            self.label_table.set_index("scenario")[[f"{f}_match" for f in ["class_fm", "family", "mode", "is_attack", "ddos"]]].all(axis=1))
        cov["timezone_check"] = cov["network_scenario"].map(self.tz.set_index("scenario")["validation_result"])
        cov.insert(0, "row_type", "scenario")
        tot = {"row_type": "total", "network_scenario": "ALL", "radio_scenario": "ALL", "class_fm": "", "tz_label": "",
               "network_windows": int(cov["network_windows"].sum()), "radio_windows": int(cov["radio_windows"].sum()),
               "matched": int(cov["matched"].sum()), "unmatched_network": int(cov["unmatched_network"].sum()),
               "unmatched_radio": int(cov["unmatched_radio"].sum())}
        tot["network_retention_pct"] = round(100.0 * tot["matched"] / tot["network_windows"], 4)
        tot["radio_retention_pct"] = round(100.0 * tot["matched"] / tot["radio_windows"], 4)
        for c in [c for c in cov.columns if c.startswith("unmatched_") and c.split("_")[-1] in ("boundary", "interior")]:
            tot[c] = int(cov[c].sum())
        tot["labels_consistent"] = bool(cov["labels_consistent"].all())
        tot["timezone_check"] = "PASS" if (cov["timezone_check"] == "PASS").all() else "FAIL"
        self.coverage = pd.concat([cov, pd.DataFrame([tot])], ignore_index=True)
        for c in ["network_start_s", "network_end_s", "radio_start_s", "radio_end_s", "radio_lead_s", "radio_trail_s"]:
            self.coverage[c] = self.coverage[c].astype("Int64")

        ck = self.checks
        ck.add("unmatched: network windows = matched + unmatched network", len(n) == len(self.joined_full) + len(self.net_only_keys),
               f"{len(n)} = {len(self.joined_full)} + {len(self.net_only_keys)}")
        ck.add("unmatched: radio windows = matched + unmatched radio", len(r) == len(self.joined_full) + len(self.radio_only_keys),
               f"{len(r)} = {len(self.joined_full)} + {len(self.radio_only_keys)}")
        ck.add("unmatched: unmatched_windows_v2 rows reconcile with both anti-joins",
               len(self.unmatched) == len(self.net_only_keys) + len(self.radio_only_keys))
        ck.add("unmatched: every unmatched row is classified boundary or interior",
               bool(self.unmatched["boundary_or_interior"].isin(["boundary", "interior"]).all()))
        self._zero_packet_investigation()
        self._counter_interval_geometry()
        return self

    def _zero_packet_investigation(self):
        n, r, u = self.net, self.radio, self.unmatched
        res = {"min_pkts_in_network_clean": float(n["pkts"].min()), "n_zero_pkt_windows": int((n["pkts"] == 0).sum())}
        absent_in_span = {}
        for scn, g in n.groupby("scenario"):
            lo, hi = int(g["timestamp_s"].min()), int(g["timestamp_s"].max())
            absent_in_span[scn] = [t for t in range(lo, hi + 1) if t not in self.nsets[scn]]
        res["in_span_absent_total"] = int(sum(len(v) for v in absent_in_span.values()))
        interior_radio = u[(u["modality"] == "radio_only") & (u["boundary_or_interior"] == "interior")]
        res["in_span_absent_with_radio_window"] = len(interior_radio)
        res["in_span_absent_without_radio_window"] = res["in_span_absent_total"] - len(interior_radio)
        rows = []
        for scn, g in interior_radio.groupby("scenario"):
            runs = g.drop_duplicates("gap_run_start_s")["gap_run_length_s"].astype(int)
            rows.append({"scenario": scn, "absent_seconds_inside_network_span": len(absent_in_span[scn]),
                         "of_which_with_radio_window": len(g), "gap_runs": len(runs),
                         "median_run_s": float(runs.median()), "max_run_s": int(runs.max())})
        res["per_scenario"] = pd.DataFrame(rows)
        # supplementary, descriptive radio volume during network-absent seconds (not joined, not allocated)
        if {"dlBytes_delta_sum", "ulBytes_delta_sum"} <= set(r.columns) and len(interior_radio):
            r2 = r.set_index(["scenario_norm", "timestamp_s"])
            absent_idx = pd.MultiIndex.from_frame(interior_radio[["scenario", "timestamp_s"]])
            present_idx = pd.MultiIndex.from_frame(self.joined_full[["scenario_normalized", "timestamp_s"]])
            drows = []
            for scn in sorted(interior_radio["scenario"].unique()):
                a = r2.loc[[i for i in absent_idx if i[0] == scn]]
                p = r2.loc[[i for i in present_idx if i[0] == scn]]
                row = {"scenario": scn, "n_absent": len(a), "n_matched": len(p)}
                for c, nm in (("ulBytes_delta_sum", "UL"), ("dlBytes_delta_sum", "DL")):
                    row[f"{nm}_median_absent"] = float(a[c].median())
                    row[f"{nm}_median_matched"] = float(p[c].median())
                    row[f"{nm}_share_zero_absent"] = float((a[c].dropna() == 0).mean())
                drows.append(row)
            res["radio_volume"] = pd.DataFrame(drows)
            allabs = r2.loc[list(absent_idx)]
            res["radio_volume_overall"] = {
                "n": len(allabs),
                "UL_nonzero_share": float((allabs["ulBytes_delta_sum"].dropna() > 0).mean()),
                "DL_nonzero_share": float((allabs["dlBytes_delta_sum"].dropna() > 0).mean()),
            }
        self.zero_packet = res
        self.checks.add("zero-packet: network_clean contains no window with pkts == 0 (so absence cannot be separated from "
                        "zero-packet seconds inside the file)", res["n_zero_pkt_windows"] == 0,
                        f"min pkts = {res['min_pkts_in_network_clean']:g}")

    def _counter_interval_geometry(self):
        r = self.radio
        if not {"delta_interval_start_ms_min", "delta_interval_end_ms_max"} <= set(r.columns):
            self.interval_geometry = None
            return
        d = r.dropna(subset=["delta_interval_start_ms_min", "delta_interval_end_ms_max"]).copy()
        start = d["delta_interval_start_ms_min"].astype("float64")
        end = d["delta_interval_end_ms_max"].astype("float64")
        length = end - start
        inside_end_second = end - d["timestamp_s"] * 1000.0
        frac = (inside_end_second / length).clip(0, 1)
        self.interval_geometry = {
            "n_windows_with_delta_interval": len(d),
            "share_start_in_previous_second": float((start < d["timestamp_s"] * 1000.0).mean()),
            "interval_length_ms": length.describe(),
            "fraction_inside_end_second": frac.describe(percentiles=[.05, .25, .5, .75, .95]),
        }

    # ---- Step 8: dataset assembly + metadata -------------------------------------------
    def step8_build_dataset(self):
        j = self.joined_full.copy()
        j["window_start_epoch_utc"] = j["timestamp_s"].astype("int64")
        role = {
            "identifiers": ["window_id", "scenario", "radio_scenario", "radio_window_id"],
            "timestamps": ["timestamp_s", "window_start_epoch_utc", "window_start_utc", "t_rel_s"],
            "labels": list(NET_LABELS),
            "diagnostics": ["is_partial", "coverage_s"] + list(DIAG_COLUMN_MAP.values()),
        }
        role["network_features"] = list(self.net_features)
        role["radio_features"] = list(self.radio_B)
        ordered = [c for k in ("identifiers", "timestamps", "labels", "diagnostics", "network_features", "radio_features")
                   for c in role[k]]
        self.role = role
        self.dataset = j[ordered].copy()
        self.dataset["is_partial"] = self.dataset["is_partial"].astype("int64")
        self.dataset["is_attack"] = self.dataset["is_attack"].astype("int64")
        return self

    def build_metadata(self) -> dict:
        rm = self.radio_meta
        role = self.role
        grp = lambda k: list(rm[k]["columns"])
        meta = {
            "version": {"alignment": VERSION, "python": platform.python_version(), "pandas": pd.__version__,
                        "numpy": np.__version__,
                        "inputs": {k: {"file": self.paths[k].name, "sha256": v} for k, v in self.input_sha.items()}},
            "join": {"key": ["scenario_normalized (== network scenario)", "timestamp_s"], "type": "exact one-to-one inner join",
                     "scenario_normalization": f"{SCENARIO_RULE[0]} -> {SCENARIO_RULE[1]}",
                     "network_key_source": "window_start_epoch_utc (Member 1's UTC epoch, validated, not modified)",
                     "radio_key_source": "timestamp_s = floor(timestamp_ms / 1000) from radio_window_features_v2.csv",
                     "sort_order": ["timestamp_s", "scenario", "window_id"],
                     "not_used": ["nearest-neighbour joins", "approximate joins", "fabricated rows", "imputation"],
                     "meaning": "second-level temporal alignment only; NOT packet-to-UE or flow-to-UE correspondence"},
            "identifiers": {"columns": role["identifiers"]},
            "timestamps": {"columns": role["timestamps"]},
            "labels": {"description": "Network labels (authoritative). Never model features. Radio-side labels are NOT carried.",
                       "columns": role["labels"]},
            "diagnostics": {"description": "Network partial-window indicators and radio report counts. Never model features.",
                            "columns": role["diagnostics"]},
            "network_features": {"source": "network_feature_columns.json: feature_cols", "columns": role["network_features"]},
            "radio_profile_columns": {"source": "radio_feature_columns_v2.json: model_feature_profiles",
                                      "A_conservative_core": self.radio_A, "B_extended_candidate": self.radio_B,
                                      "session_shift_caution_features": list(rm["model_feature_profiles"]["session_shift_caution_features"])},
            "profiles": {
                "A": {"network_columns": self.net_features, "radio_columns": self.radio_A, "columns": self.profile_A,
                      "count": len(self.profile_A)},
                "B": {"network_columns": self.net_features, "radio_columns": self.radio_B, "columns": self.profile_B,
                      "count": len(self.profile_B)},
            },
            "not_in_dataset": {
                "description": "Available only in radio_window_features_v2.csv / network_clean.csv; deliberately NOT joined.",
                "radio_held_out_kpis": grp("held_out_features"),
                "radio_sensitivity_only": grp("sensitivity_only_features"),
                "radio_quality_flags": grp("quality_flags"),
                "radio_diagnostics_not_carried": [c for c in grp("diagnostic_features") if c not in DIAG_COLUMN_MAP],
                "radio_labels": rm["labels"]["columns"],
                "radio_byte_counter_deltas": ["dlBytes_delta_sum", "ulBytes_delta_sum", "delta_interval_start_ms_min",
                                              "delta_interval_end_ms_max"],
                "network_not_for_models": list(self.net_meta["diag_cols_not_for_models"]),
            },
            "notes": [
                "puschSnr_* NaN values are preserved exactly as in the radio window table (no imputation).",
                "Radio byte-counter deltas cover (previous timestamp, current timestamp] and are NOT part of this join; "
                "an interval-allocation decision is required first.",
                "The network column 'bytes' is a per-window packet-byte feature of the network sensor, not a radio counter.",
            ],
            "exported_columns": list(self.dataset.columns),
        }
        return meta

    # ---- Step 9: post-join integrity + validation ---------------------------------------
    def step9_validate(self):
        ck, ds, n, r = self.checks, self.dataset, self.net, self.radio
        meta = self.meta = self.build_metadata()
        key = ["scenario", "timestamp_s"]
        ck.add("integrity: no duplicate (scenario, timestamp_s) keys in the final dataset", not ds.duplicated(key).any(),
               f"{len(ds):,} rows")
        ck.add("integrity: window_id and radio_window_id are unique in the final dataset",
               not ds["window_id"].duplicated().any() and not ds["radio_window_id"].duplicated().any())
        ck.add("integrity: no missing network labels in the final dataset", bool(ds[NET_LABELS].notna().all().all()))
        ck.add("integrity: dataset sorted by network UTC time (timestamp_s, scenario, window_id)",
               bool((ds[["timestamp_s", "scenario", "window_id"]].reset_index(drop=True)
                     .equals(ds[["timestamp_s", "scenario", "window_id"]].sort_values(["timestamp_s", "scenario", "window_id"], kind="mergesort").reset_index(drop=True)))))
        ck.add("integrity: window_start_epoch_utc equals timestamp_s and is int64",
               bool((ds["window_start_epoch_utc"] == ds["timestamp_s"]).all() and ds["timestamp_s"].dtype == "int64"))
        nk = set(zip(n["scenario"], n["timestamp_s"]))
        rk = set(zip(r["scenario_norm"], r["timestamp_s"]))
        dk = set(zip(ds["scenario"], ds["timestamp_s"]))
        ck.add("integrity: no fabricated rows (every dataset key exists in BOTH inputs)", dk <= nk and dk <= rk and dk == (nk & rk),
               f"dataset keys={len(dk)}, intersection={len(nk & rk)}")
        # values copied unchanged
        src_n = n.set_index("window_id")[self.net_features].reindex(ds["window_id"]).reset_index(drop=True)
        ck.add("integrity: network feature values identical to network_clean.csv",
               _frames_equal(ds[self.net_features].reset_index(drop=True), src_n))
        r_idx = r.assign(_k=list(zip(r["scenario_norm"], r["timestamp_s"]))).set_index("_k")
        src_r = r_idx.reindex(list(zip(ds["scenario"], ds["timestamp_s"])))[self.radio_B].reset_index(drop=True)
        ck.add("integrity: radio feature values (including NaN positions) identical to radio_window_features_v2.csv",
               _frames_equal(ds[self.radio_B].reset_index(drop=True), src_r))
        nan_ds = int(ds[self.radio_B].isna().sum().sum())
        nan_src = int(src_r.isna().sum().sum())
        pusch_cols = [c for c in self.radio_B if c.startswith("puschSnr_")]
        ck.add("missing values: NaN cells preserved, none imputed (dataset NaN count == source NaN count for the same rows)",
               nan_ds == nan_src, f"radio feature NaN cells={nan_ds}; PUSCH NaN cells={int(ds[pusch_cols].isna().sum().sum())}")
        ck.add("missing values: network feature columns contain no NaN", int(ds[self.net_features].isna().sum().sum()) == 0
               or int(ds[self.net_features].isna().sum().sum()) == int(src_n.isna().sum().sum()))
        # leakage / exclusions in the final dataset
        cols = set(ds.columns)
        ck.add("exclusions: no radio byte-counter column (dlBytes*/ulBytes*) in the dataset",
               not any(re.match(r"^(dl|ul)Bytes", c) for c in ds.columns))
        ck.add("exclusions: no radio-side label, held-out KPI, sensitivity-only or quality-flag column in the dataset",
               not (cols & (set(meta["not_in_dataset"]["radio_held_out_kpis"]) | set(meta["not_in_dataset"]["radio_sensitivity_only"])
                            | set(meta["not_in_dataset"]["radio_quality_flags"]) | {f"radio_label_{c}" for c in RADIO_LABELS})))
        ck.add("exclusions: no network diagnostic-only column (diag_*) in the dataset",
               not any(c.startswith("diag_") for c in ds.columns))
        ck.add("profiles: every Profile A and Profile B feature exists in the final dataset",
               set(self.profile_B) <= cols and set(self.profile_A) <= cols)
        ck.add("profiles: Profile A has no duplicate columns", len(set(self.profile_A)) == len(self.profile_A))
        ck.add("profiles: Profile B has no duplicate columns", len(set(self.profile_B)) == len(self.profile_B))
        ck.add("profiles: Profile A is a subset of Profile B", set(self.profile_A) <= set(self.profile_B))
        non_feature = set(self.role["identifiers"] + self.role["timestamps"] + self.role["labels"] + self.role["diagnostics"])
        ck.add("leakage: no identifier/timestamp/label/diagnostic column inside Profile A or B",
               not (non_feature & set(self.profile_B)))
        roles_flat = [c for k in ("identifiers", "timestamps", "labels", "diagnostics", "network_features", "radio_features")
                      for c in self.role[k]]
        ck.add("metadata: every exported column has exactly one role", sorted(roles_flat) == sorted(ds.columns),
               f"{len(ds.columns)} columns")
        ck.add("metadata: JSON exported_columns equals the dataset columns", meta["exported_columns"] == list(ds.columns))

        # previous-run comparison (optional, key columns only; NOT a source of truth)
        self.prev_cmp = None
        if PREVIOUS_MULTIMODAL.exists():
            prev = pd.read_csv(PREVIOUS_MULTIMODAL, usecols=["scenario", "timestamp_s"])
            pk = set(zip(prev["scenario"], prev["timestamp_s"]))
            self.prev_cmp = {"previous_rows": len(pk), "only_in_previous": len(pk - dk), "only_in_v2": len(dk - pk),
                             "identical_keys": pk == dk}
            ck.add("comparison: V2 matched keys vs previous multimodal_dataset.csv keys (comparison only)",
                   pk == dk, f"previous={len(pk):,}, V2={len(dk):,}, only previous={len(pk - dk)}, only V2={len(dk - pk)}",
                   kind="target")

        # targets
        obs = {"scenario_mappings": len(self.mapping), "network_windows": len(n), "radio_windows": len(r),
               "matched_windows": len(ds), "unmatched_network_windows": len(self.net_only_keys),
               "unmatched_radio_windows": len(self.radio_only_keys)}
        self.target_table = pd.DataFrame({"target": list(obs), "expected": [EXPECTED_TARGETS[k] for k in obs],
                                          "observed": [obs[k] for k in obs]})
        self.target_table["status"] = np.where(self.target_table["expected"] == self.target_table["observed"], "match", "DIFFERENT")
        for k in obs:
            ck.add(f"audit target: {k}", obs[k] == EXPECTED_TARGETS[k], f"expected {EXPECTED_TARGETS[k]:,}, observed {obs[k]:,}",
                   kind="target")

        # independent re-execution (in memory) must reproduce the dataset exactly
        if self.repro_check:
            p2 = AlignmentPipeline(self.paths["network_csv"], self.paths["network_json"], self.paths["radio_csv"],
                                   self.paths["radio_json"], self.output_dir, repro_check=False)
            p2.step1_load_and_validate().step2_normalize_scenarios().step3_timestamps().step4_timezone().step5_labels()
            p2.validate_profiles()
            p2.step6_join().step7_unmatched().step8_build_dataset()
            ck.add("reproducibility: independent in-memory re-execution reproduces dataset, unmatched table and coverage exactly",
                   _frames_equal(ds.reset_index(drop=True), p2.dataset.reset_index(drop=True))
                   and p2.unmatched.equals(self.unmatched) and p2.coverage.equals(self.coverage))
        ck.add("inputs: input files unchanged (SHA-256, size, mtime) after processing",
               all(sha256_file(p) == self.input_sha[k] and (p.stat().st_size, p.stat().st_mtime_ns) == self.input_stat[k]
                   for k, p in self.paths.items()))
        return self

    # ---- Step 10: outputs ------------------------------------------------------------------
    def write_outputs(self, partial=False):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        out = {k: self.output_dir / v for k, v in (("tz", OUT_TZ), ("report", OUT_REPORT))}
        self.written = []
        if hasattr(self, "tz"):
            self.tz.to_csv(out["tz"], index=False, lineterminator="\n")
            self.written.append(out["tz"])
        if not partial:
            out.update({k: self.output_dir / v for k, v in (("dataset", OUT_DATASET), ("json", OUT_JSON),
                                                            ("csv", OUT_REPORT_CSV), ("unmatched", OUT_UNMATCHED))})
            for p in out.values():
                if p.resolve() in {q.resolve() for q in self.paths.values()}:
                    raise RuntimeError("refusing to overwrite an input file")
            self.dataset.to_csv(out["dataset"], index=False, lineterminator="\n")
            with open(out["json"], "w", encoding="utf-8") as fh:
                json.dump(self.meta, fh, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o))
                fh.write("\n")
            self.coverage.to_csv(out["csv"], index=False, lineterminator="\n")
            self.unmatched.to_csv(out["unmatched"], index=False, lineterminator="\n")
            back = pd.read_csv(out["dataset"])
            ok_shape = back.shape == self.dataset.shape and list(back.columns) == list(self.dataset.columns)
            num = [c for c in self.dataset.columns if pd.api.types.is_numeric_dtype(self.dataset[c])]
            ok_vals = all(np.allclose(back[c].astype(float), self.dataset[c].astype(float), rtol=1e-12, atol=1e-12, equal_nan=True)
                          for c in num)
            self.checks.add("outputs: dataset CSV round-trips (shape, column order, numeric values incl. NaN)", ok_shape and ok_vals,
                            f"{back.shape[0]:,} rows x {back.shape[1]} columns")
            self.checks.add("outputs: unmatched_windows_v2.csv row count equals the two anti-joins",
                            len(pd.read_csv(out["unmatched"])) == len(self.unmatched))
            self.written += [out["dataset"], out["json"], out["csv"], out["unmatched"]]
        out["report"].write_text(render_report(self, partial=partial), encoding="utf-8")
        self.written.append(out["report"])
        return self.written

    def run(self):
        self.step1_load_and_validate().step2_normalize_scenarios()
        if self.checks.failed():                      # scenario mapping is the basis of every later step
            self.blocked = True
            self.write_outputs(partial=True)
            return self
        self.step3_timestamps().step4_timezone().step5_labels()
        self.validate_profiles()
        if self.checks.failed():                      # blocking validation failure: stop BEFORE joining
            self.blocked = True
            self.write_outputs(partial=True)
            return self
        self.step6_join()
        if self.checks.failed():
            self.blocked = True
            self.write_outputs(partial=True)
            return self
        self.step7_unmatched().step8_build_dataset().step9_validate()
        self.write_outputs()
        return self


# --------------------------------------------------------------------------- #
# report
# --------------------------------------------------------------------------- #
def render_report(p: AlignmentPipeline, partial=False) -> str:
    L: list[str] = []
    A = L.append
    A("# Multimodal Alignment Report V2")
    A("")
    A(f"Generated by `multimodal_alignment_v2.py` ({VERSION}). Every number below is computed in this run. "
      "The result is **second-level temporal alignment** of two sensors inside one capture. It does **not** establish "
      "packet-to-UE or flow-to-UE correspondence: no shared packet identifier or UE-to-flow mapping exists, and several UEs "
      "are pooled into one radio window.")
    A("")
    A("## 1. Inputs")
    A("")
    A(md_table(pd.DataFrame([{"input": k, "file": p.paths[k].name, "sha256": v} for k, v in p.input_sha.items()])))
    A("")
    A(f"Python {platform.python_version()}, pandas {pd.__version__}, numpy {np.__version__}. Not used as inputs: "
      "`network_features.csv`, `radio_clean.csv`, `multimodal_dataset.csv` (the last is opened read-only, key columns only, "
      "solely for the comparison in section 2).")
    A("")
    if partial:
        A("## RUN STOPPED: validation failed before the dataset was created")
        A("")
        A("A blocking validation failed, so `multimodal_dataset_v2.csv` was **not** written. Failed checks:")
        A("")
        fr = p.checks.frame()
        A(md_table(fr[fr["result"] == "FAIL"][["name", "detail"]]))
        A("")
        A("All checks run so far:")
        A("")
        A(md_table(fr[["result", "name", "detail"]]))
        A("")
        return "\n".join(L)

    n, r, ds = p.net, p.radio, p.dataset
    cov = p.coverage[p.coverage["row_type"] == "scenario"]
    tot = p.coverage[p.coverage["row_type"] == "total"].iloc[0]
    u = p.unmatched

    # 2 ---------------------------------------------------------------------------
    A("## 2. Alignment statistics")
    A("")
    st = pd.DataFrame([
        ("Network windows (network_clean.csv)", len(n)), ("Radio windows (radio_window_features_v2.csv)", len(r)),
        ("Matched windows (one-to-one inner join)", len(ds)),
        ("Network windows without a radio match", len(p.net_only_keys)),
        ("Radio windows without a network match", len(p.radio_only_keys)),
        ("Matched as % of network windows", round(100.0 * len(ds) / len(n), 4)),
        ("Matched as % of radio windows", round(100.0 * len(ds) / len(r), 4)),
        ("Scenarios aligned", int(ds["scenario"].nunique())),
    ], columns=["quantity", "value"])
    A(md_table(st))
    A("")
    A("Comparison with the audit targets (reported, never used in logic):")
    A("")
    A(md_table(p.target_table))
    A("")
    diff = p.target_table[p.target_table["status"] != "match"]
    if diff.empty:
        A("**All six alignment targets are reproduced exactly.**")
        if p.prev_cmp is not None and p.prev_cmp["identical_keys"]:
            A("")
            A("Why the counts are identical: the exact-key set of V2 equals the key set of the previous alignment (see the key "
              "comparison below), i.e. both use the same normalised scenario names and the same UTC-second keys. V2 changes the "
              "radio feature table (new aggregation and columns) and the validation around the join, not which seconds can pair.")
    else:
        A("**Differences from the audit targets:** " + "; ".join(
            f"{x.target}: expected {x.expected:,}, observed {x.observed:,}" for x in diff.itertuples()) + ".")
    if p.prev_cmp is not None:
        c = p.prev_cmp
        A("")
        A(f"Key-level comparison with the previous `multimodal_dataset.csv` (comparison only): previous rows {c['previous_rows']:,}; "
          f"keys only in the previous file: {c['only_in_previous']}; keys only in V2: {c['only_in_v2']}; identical key set: "
          f"{'yes' if c['identical_keys'] else 'no'}.")
        if not c["identical_keys"]:
            A("The key sets differ; see `unmatched_windows_v2.csv` and the scenario table for the exact rows.")
    A("")

    # 3 ---------------------------------------------------------------------------
    A("## 3. Timestamp validation")
    A("")
    ts_rows = p.checks.frame()
    A(md_table(ts_rows[ts_rows["name"].str.startswith(("timestamps", "keys"))][["result", "name", "detail"]]))
    A("")
    A("The network join key is derived from Member 1's `window_start_epoch_utc` (integer-valued UTC seconds); its timezone "
      "conversion is validated here, not repeated or modified. Radio `timestamp_s` is `floor(timestamp_ms / 1000)` and is "
      "joined as-is.")
    A("")

    # 4 ---------------------------------------------------------------------------
    A("## 4. Scenario normalisation")
    A("")
    ch = p.scenario_table[p.scenario_table["radio_scenario"] != p.scenario_table["network_scenario"]]
    A(f"Rule: leading `DDOS_` -> `DDOS`. {len(p.scenario_table)} radio scenarios map onto {p.scenario_table['network_scenario'].nunique()} "
      f"distinct network scenarios; {len(ch)} names change, {len(p.scenario_table) - len(ch)} are identical. The full mapping is in "
      "`alignment_report_v2.csv` (columns `radio_scenario`, `network_scenario`).")
    A("")
    A(md_table(ch))
    A("")

    # 5 ---------------------------------------------------------------------------
    A("## 5. Timezone validation (Europe/Dublin via `zoneinfo`; all scenarios)")
    A("")
    tz = p.tz
    A(f"Scenarios examined: {len(tz)}; PASS: {int((tz['validation_result'] == 'PASS').sum())}; FAIL: {int((tz['validation_result'] == 'FAIL').sum())}. "
      "Every window of every scenario was converted from its UTC epoch to Europe/Dublin and the abbreviation compared with the recorded "
      "`tz_label`; the applied offset (and its sign, `UTC = wall - offset`) was compared with the Dublin UTC offset.")
    A("")
    A(f"Dublin clock changes within the capture range (UTC): {', '.join(datetime.fromtimestamp(t, tz=timezone.utc).strftime('%Y-%m-%d %H:%M') for t in p.transitions) or 'none'}.")
    A("")
    A(md_table(tz[["scenario", "capture_date_utc", "recorded_tz_label", "expected_tz_label_first_window",
                   "expected_tz_label_last_window", "windows_matching_expected_label", "n_windows", "applied_offset_s",
                   "expected_utc_offset_s", "days_to_nearest_dst_transition", "validation_result"]]))
    A("")
    A("This is a validation step only; Member 1's network data was not modified. Agreement of the label with Dublin local time is "
      "consistent evidence that the label is a Europe/Dublin abbreviation and that the sign is right; it does not by itself prove "
      "clock synchronisation between the packet capture and the radio logger.")
    A("")

    # 6 ---------------------------------------------------------------------------
    A("## 6. Label consistency (network labels are authoritative)")
    A("")
    lt = p.label_table
    rows = []
    for f in ["class_fm", "family", "mode", "is_attack", "ddos"]:
        rows.append({"field": f, "scenarios_compared": len(lt), "scenarios_mismatching": int((~lt[f"{f}_match"]).sum()),
                     "note": "radio ddos compared with network mode == 'DDoS' (no network ddos column)" if f == "ddos" else ""})
    A(md_table(pd.DataFrame(rows)))
    A("")
    lab = p.checks.frame()
    A(md_table(lab[lab["name"].str.startswith("labels")][["result", "name", "detail"]]))
    A("")
    A("Labels were not used to choose records or clean measurements. Radio-side labels are not carried into the dataset.")
    A("")

    # 7 ---------------------------------------------------------------------------
    A("## 7. Per-scenario coverage")
    A("")
    t7 = cov[["network_scenario", "class_fm", "tz_label", "network_windows", "radio_windows", "matched", "unmatched_network",
              "unmatched_radio", "network_retention_pct", "radio_retention_pct"]]
    A(md_table(pd.concat([t7, pd.DataFrame([{"network_scenario": "ALL", "class_fm": "", "tz_label": "",
                                             "network_windows": tot["network_windows"], "radio_windows": tot["radio_windows"],
                                             "matched": tot["matched"], "unmatched_network": tot["unmatched_network"],
                                             "unmatched_radio": tot["unmatched_radio"],
                                             "network_retention_pct": tot["network_retention_pct"],
                                             "radio_retention_pct": tot["radio_retention_pct"]}])])))
    A("")
    cls = ds.groupby("class_fm").size().rename("matched").to_frame().join(n.groupby("class_fm").size().rename("network_windows"))
    cls["network_retention_pct"] = (100.0 * cls["matched"] / cls["network_windows"]).round(2)
    A("Retention by network label (reporting only):")
    A("")
    A(md_table(cls[["network_windows", "matched", "network_retention_pct"]], index=True))
    A("")
    A("Recording-start offsets between the two sensors (network start - radio start, seconds; positive = radio started first) "
      f"range from {int(cov['radio_lead_s'].min())} to {int(cov['radio_lead_s'].max())} across scenarios; end offsets "
      f"(radio end - network end) from {int(cov['radio_trail_s'].min())} to {int(cov['radio_trail_s'].max())}. These vary by scenario, "
      "so they are not a constant clock offset.")
    A("")

    # 8 ---------------------------------------------------------------------------
    A("## 8. Unmatched observations")
    A("")
    summ = u.groupby(["modality", "boundary_or_interior"]).size().unstack(fill_value=0)
    summ["total"] = summ.sum(axis=1)
    A(md_table(summ, index=True))
    A("")
    A("### 8.1 Network windows without radio matches")
    A("")
    un = u[u["modality"] == "network_only"]
    A(f"{len(un)} windows in {un['scenario'].nunique()} scenarios. Position: "
      + ", ".join(f"{k}: {v}" for k, v in un["position_relative_to_other_modality"].value_counts().items()) + ".")
    A("")
    A(md_table(un.groupby("scenario").agg(unmatched=("timestamp_s", "size"),
                                          boundary=("boundary_or_interior", lambda s: int((s == "boundary").sum())),
                                          interior=("boundary_or_interior", lambda s: int((s == "interior").sum()))), index=True))
    A("")
    A("### 8.2 Radio windows without network matches")
    A("")
    ur = u[u["modality"] == "radio_only"]
    A(f"{len(ur)} windows in {ur['scenario'].nunique()} scenarios. Position: "
      + ", ".join(f"{k}: {v}" for k, v in ur["position_relative_to_other_modality"].value_counts().items()) + ".")
    A("")
    A(md_table(ur.groupby("scenario").agg(unmatched=("timestamp_s", "size"),
                                          boundary=("boundary_or_interior", lambda s: int((s == "boundary").sum())),
                                          interior=("boundary_or_interior", lambda s: int((s == "interior").sum()))), index=True))
    A("")
    A("Full per-row detail (time, position, boundary/interior, distance from the other modality's span, gap-run length) is in "
      "`unmatched_windows_v2.csv`. Per-scenario counts and retention percentages are in section 7 and `alignment_report_v2.csv`.")
    A("")
    A("### 8.3 Do missing network windows correspond to zero-packet seconds?")
    A("")
    z = p.zero_packet
    A(f"- `01b - Network cleaning.ipynb` keeps a window only if `pkts > 0` (window-building cell, filter `W[\"pkts\"] > 0`). "
      f"Consequently `network_clean.csv` contains **no** window with zero packets (observed: {z['n_zero_pkt_windows']} zero-packet windows, "
      f"minimum packets per window = {z['min_pkts_in_network_clean']:g}). A missing network second therefore means *no window was emitted*; "
      "from this file alone it cannot be told apart from other causes of a missing window.")
    A(f"- Seconds missing from the network window sequence *inside* each scenario's network span: {z['in_span_absent_total']}; of these, "
      f"{z['in_span_absent_with_radio_window']} have a radio window (radio-only interior) and {z['in_span_absent_without_radio_window']} "
      "have no radio window either (both sensors silent, e.g. a joint outage).")
    if len(z["per_scenario"]):
        A("")
        A(md_table(z["per_scenario"]))
        A("")
    if "radio_volume" in z:
        ov = z["radio_volume_overall"]
        A("- Supplementary, **descriptive only** (the radio byte deltas are not part of the dataset and are not allocated to windows; see section 10): "
          f"in the {ov['n']} radio-only interior seconds the radio byte-counter delta is non-zero for {100 * ov['UL_nonzero_share']:.1f}% (UL) "
          f"and {100 * ov['DL_nonzero_share']:.1f}% (DL) of seconds.")
        if len(z["per_scenario"]):
            top = z["per_scenario"].sort_values("max_run_s", ascending=False).iloc[0]
            A(f"- Longest contiguous run of network-absent seconds: {int(top['max_run_s'])} s ({top['scenario']}); this is a stretch with no "
              "network window at all, not an isolated missing second.")
        A("")
        A(md_table(z["radio_volume"]))
        A("")
    if "radio_volume" in z:
        ov = z["radio_volume_overall"]
        vol_txt = (f"the radio byte-counter delta is non-zero in {100 * ov['UL_nonzero_share']:.1f}% (UL) and "
                   f"{100 * ov['DL_nonzero_share']:.1f}% (DL) of these seconds")
    else:
        vol_txt = "no radio volume diagnostic was available"
    A(f"**Assessment.** The network sensor emitted no window, i.e. captured no packet, in those seconds. Radio-side activity is not ruled out ({vol_txt}), "
      "so the data does **not** show that the UE was idle, and nothing here supports calling these seconds benign. They are labelled "
      "`no network window (no packet captured by the network sensor)`; the cause cannot be verified without the raw packet files.")
    A("")
    A("Radio-side gaps: radio windows absent inside the radio span are reported as network-only interior rows; their cause "
      "(no UE record in that second) is not verifiable from the window table. No missing radio value was filled with zeros, and no "
      "observation was created.")
    A("")

    # 9 ---------------------------------------------------------------------------
    A("## 9. Feature profiles")
    A("")
    prof = pd.DataFrame([
        ("A", len(p.net_features), len(p.radio_A), len(p.profile_A)),
        ("B", len(p.net_features), len(p.radio_B), len(p.profile_B)),
    ], columns=["profile", "network_columns", "radio_columns", "total_columns"])
    A(md_table(prof))
    A("")
    A("- Network columns come from `network_feature_columns.json: feature_cols`; radio columns come from "
      "`radio_feature_columns_v2.json: model_feature_profiles` (A = conservative core, B = core + SINR + CQI). No column was invented or renamed.")
    A("- Excluded from both profiles (and, apart from the listed diagnostics, from the dataset): identifiers, labels, timestamps, diagnostics, "
      "quality flags, held-out KPIs (rsrp, rssi, ri, phr), sensitivity-only variables, raw byte counters and their deltas.")
    A(f"- `puschSnr_*` NaN cells in the dataset: {int(ds[[c for c in p.radio_B if c.startswith('puschSnr_')]].isna().sum().sum())} "
      f"(in {int(ds[[c for c in p.radio_B if c.startswith('puschSnr_')]].isna().any(axis=1).sum())} windows). They are kept as NaN; nothing is imputed.")
    A("- SINR and CQI (Profile B only) form the session-shift caution group defined in the radio metadata; scenario dependence is not unique to them "
      "(see `radio_quality_report_v2.md`, section 4).")
    A("")

    # 10 --------------------------------------------------------------------------
    A("## 10. Radio byte counters are not part of this join")
    A("")
    A("A byte-counter delta covers the interval `(previous timestamp_ms, timestamp_ms]`. The radio window table attributes it to the second "
      "containing the *end* of that interval (`timestamp_s`). That end-second label does **not** show that the delta belongs entirely to that "
      "one-second network window `[t, t+1)`: the interval is about one second long and starts at the previous sample's millisecond phase, so it "
      "normally overlaps two consecutive network windows.")
    g = p.interval_geometry
    if g:
        fr = g["fraction_inside_end_second"]
        A("")
        A(f"Measured on {g['n_windows_with_delta_interval']:,} radio windows that have a valid delta: the interval begins in the previous "
          f"second in {100 * g['share_start_in_previous_second']:.1f}% of them; the fraction of the interval lying inside the end second has "
          f"min {fr['min']:.3f}, 5th percentile {fr['5%']:.3f}, median {fr['50%']:.3f}, 95th percentile {fr['95%']:.3f}, max {fr['max']:.3f}. "
          "With several UEs the window combines intervals with different phases, so the union is slightly longer than one second.")
    A("")
    A("No allocation method is invented here. `dlBytes_delta_sum`, `ulBytes_delta_sum` and the interval bounds remain in "
      "`radio_window_features_v2.csv` / `radio_counter_diagnostics_v2.csv` for a future sensitivity experiment that first fixes an "
      "interval-allocation rule. They are excluded from `multimodal_dataset_v2.csv`.")
    A("")

    # 11 --------------------------------------------------------------------------
    A("## 11. Limitations")
    A("")
    A("1. Temporal co-occurrence at 1-second resolution only. There is no packet ID or UE-to-flow mapping; several UEs are pooled per radio window. "
      "No packet-to-UE correspondence is claimed.")
    A("2. The two sensors may have a residual clock skew of a few seconds that cannot be resolved from these files; no correction and no "
      "fuzzy matching were applied. The start/end offsets in section 7 differ per scenario.")
    A("3. Missing network windows are seconds without a captured packet; their relation to UE activity is unknown (section 8.3).")
    A("4. Inner-join retention differs by scenario (section 7); unmatched rows are reported, never repaired.")
    A("5. Timezone agreement validates Member 1's conversion against Europe/Dublin rules; it does not prove logger/capture clock synchronisation.")
    A("6. The radio feature columns inherit the open questions listed in `radio_quality_report_v2.md` (scenario/session dependence, held-out "
      "KPI semantics, treatment of all-zero UL reports).")
    A("7. Class and capture date are confounded in the source captures, so scenario-level evaluation splits and a radio-only baseline are still needed "
      "before any detection claim.")
    A("8. The raw packet and radio source files are not in the repository, so none of the above could be checked at source.")
    A("")

    # 12 --------------------------------------------------------------------------
    A("## 12. Validation assertions")
    A("")
    fr = p.checks.frame()
    A(md_table(fr[["result", "name", "detail"]]))
    A("")
    A(f"Hard assertions: {int((fr['kind'] == 'assert').sum())}; failed: **{len(p.checks.failed())}**. "
      f"Target/comparison discrepancies: {len(p.checks.discrepancies())}.")
    A("")
    return "\n".join(L)


# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Multimodal alignment V2 (Member 2, Phase 2)")
    ap.add_argument("--network-csv", default=str(DEFAULT_NETWORK_CSV))
    ap.add_argument("--network-json", default=str(DEFAULT_NETWORK_JSON))
    ap.add_argument("--radio-csv", default=str(DEFAULT_RADIO_CSV))
    ap.add_argument("--radio-json", default=str(DEFAULT_RADIO_JSON))
    ap.add_argument("--output-dir", default=str(SCRIPT_DIR))
    ap.add_argument("--skip-repro-check", action="store_true")
    a = ap.parse_args(argv)
    p = AlignmentPipeline(a.network_csv, a.network_json, a.radio_csv, a.radio_json, a.output_dir,
                          repro_check=not a.skip_repro_check)
    try:
        p.run()
    except AlignmentCollisionError as e:
        print(f"STOPPED (key collision): {e}", file=sys.stderr)
        print(e.collisions.head(20).to_string(index=False), file=sys.stderr)
        return 2
    except SchemaError as e:
        print(f"STOPPED (schema): {e}", file=sys.stderr)
        return 1
    for c in p.checks.items:
        tag = "PASS" if c["passed"] else ("FAIL" if c["kind"] == "assert" else "DISCREPANCY")
        print(f"  [{tag}] {c['name']}  ({c['detail']})")
    if p.blocked:
        print("STOPPED: a validation failed before/while joining; dataset NOT written. See alignment_report_v2.md.", file=sys.stderr)
        return 1
    print(f"matched {len(p.dataset):,} | network-only {len(p.net_only_keys)} | radio-only {len(p.radio_only_keys)} | "
          f"Profile A {len(p.profile_A)} | Profile B {len(p.profile_B)}")
    for f in p.written:
        print("  wrote", f)
    nfail = len(p.checks.failed())
    print(f"hard assertions failed: {nfail}; target/comparison discrepancies: {len(p.checks.discrepancies())}")
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
