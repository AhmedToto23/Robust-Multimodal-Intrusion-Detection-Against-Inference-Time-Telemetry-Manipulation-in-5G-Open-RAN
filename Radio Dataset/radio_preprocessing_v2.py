#!/usr/bin/env python3
"""
radio_preprocessing_v2.py  --  Member 2, Phase 1: Radio telemetry preprocessing V2
===========================================================================

Project : When One Sensor Lies: Robust Multimodal Intrusion Detection Against
          Inference-Time Telemetry Manipulation in 5G Open RAN

Input   : Radio Dataset/radio_clean.csv            (read-only, never modified)
Outputs : radio_window_features_v2.csv             one row per (scenario, timestamp_s)
          radio_feature_columns_v2.json            column roles + model feature profiles
          radio_quality_report_v2.md               report generated from this run
          radio_duplicate_removal_log_v2.csv       every removed duplicate record
          radio_counter_diagnostics_v2.csv         per-record byte-counter diagnostics
          (radio_duplicate_conflicts_v2.csv        ONLY written if conflicting duplicates exist)

Dependencies: Python 3, pandas, numpy.  Nothing else.

Run:
    python radio_preprocessing_v2.py
    python radio_preprocessing_v2.py --input "Radio Dataset/radio_clean.csv" --output-dir "Radio Dataset"

Exit codes: 0 = all hard assertions passed, 1 = a validation assertion failed,
            2 = conflicting duplicate records found (pipeline stopped, conflicts reported).

Design rules (see report for the rationale):
  * No labels are used to clean, flag or transform any observation.
  * Raw values are never altered; quality problems become flags, never deletions.
  * Missing values are preserved (no imputation, no zero-filling).
  * Counter resets are NOT clipped to zero; they become NaN + a reset flag.
  * No network-radio alignment happens here; no timezone conversion is applied to radio.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PREPROCESSING_VERSION = "radio_preprocessing_v2.0.0"

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = SCRIPT_DIR / "radio_clean.csv"
DEFAULT_OUTDIR = SCRIPT_DIR

OUT_WINDOW = "radio_window_features_v2.csv"
OUT_JSON = "radio_feature_columns_v2.json"
OUT_REPORT = "radio_quality_report_v2.md"
OUT_DUPLOG = "radio_duplicate_removal_log_v2.csv"
OUT_COUNTERS = "radio_counter_diagnostics_v2.csv"
OUT_CONFLICTS = "radio_duplicate_conflicts_v2.csv"

# --------------------------------------------------------------------------- #
# Schema and parameters
# --------------------------------------------------------------------------- #
KPIS = ["rsrp", "rssi", "rsrq", "sinr", "cqi", "dlMcs", "ulMcs",
        "dlBler", "ulBler", "ri", "phr", "pcmax", "pucchSnr", "puschSnr"]
COUNTERS = ["dlBytes", "ulBytes"]
OOB_COLS = [f"{k}_flag_oob" for k in KPIS]
LABEL_COLS = ["family", "mode", "class_fm", "is_attack", "ddos"]

REQUIRED_COLUMNS = (
    ["scenario", "folder", "family", "mode", "class_fm", "is_attack", "ddos",
     "ue_id", "timestamp_ms", "timestamp_s", "time_utc", "radio_window_id"]
    + KPIS + COUNTERS
    + ["rnti", "rnti_int", "cellid", "pmi", "pmi_0", "pmi_1", "in_sync", "is_duplicate"]
    + OOB_COLS + ["source_fmt", "file_row", "file_order_desc"]
)

STR_COLS = ["scenario", "folder", "family", "mode", "class_fm", "time_utc",
            "radio_window_id", "rnti", "pmi", "source_fmt"]

# Plausibility ranges, copied from 02b (cell 2) so that the existing *_flag_oob columns
# can be independently re-derived.  They are used for verification only.
PHYS = {
    "rsrp": (-140, -40), "rssi": (-120, 0), "rsrq": (-30, 0), "sinr": (-20, 40),
    "cqi": (0, 15), "dlMcs": (0, 28), "ulMcs": (0, 28), "dlBler": (0, 1), "ulBler": (0, 1),
    "ri": (1, 4), "phr": (-23, 40), "pcmax": (-30, 33), "pucchSnr": (-30, 60), "puschSnr": (-30, 60),
}

DUP_KEY = ["scenario", "ue_id", "timestamp_ms"]
PROVENANCE_COLS = ["file_row", "file_order_desc", "is_duplicate"]
# Measurement payload: what decides "identical vs conflicting" duplicates.
PAYLOAD_COLS = KPIS + COUNTERS + ["rnti", "cellid", "pmi", "in_sync"]

STATS = ("mean", "std", "min", "max")          # std uses ddof = 0
STD_DDOF = 0
GAP_THRESHOLD_S = 1.5                          # delta interval > 1.5 s is a "large gap"
NOMINAL_INTERVAL_S = 1.0
PUSCH_SATURATION_CODE = 63.5                   # = 127 * 0.5 (7-bit, half-dB field)
PHR_PLAUSIBLE_MAX = 40                         # project plausibility ceiling (02b)
PHR_INDEX_MAX = 63                             # largest value of a 6-bit index
ETA_HIGH = 0.5                                 # report threshold for between-scenario dependence
ALL_ZERO_UL_FIELDS = ["pcmax", "phr", "pucchSnr", "dlMcs", "ulMcs"]
# KPIs for which an "excluding all-zero UL reports" sensitivity variant is exported
NZ_KPIS = ["dlMcs", "ulMcs", "pcmax", "phr", "pucchSnr", "puschSnr"]
NZ_SUFFIX = "_nz"
PLAUSIBLE_UTC_START = pd.Timestamp("2025-01-01", tz="UTC")
PLAUSIBLE_UTC_END = pd.Timestamp("2025-12-31 23:59:59", tz="UTC")

# Feature profiles (KPI level; every KPI contributes mean/std/min/max columns)
CORE_KPIS = ["rsrq", "dlMcs", "ulMcs", "dlBler", "ulBler", "pcmax", "pucchSnr", "puschSnr"]
EXTENDED_ADDITIONAL_KPIS = ["sinr", "cqi"]
SESSION_SHIFT_CAUTION_KPIS = ["sinr", "cqi"]
HELD_OUT_KPIS = ["rsrp", "rssi", "ri", "phr"]

# Validation TARGETS from the audit.  Used only for comparison/reporting, never in logic.
EXPECTED_TARGETS = {
    "input_rows": 7490, "input_columns": 53, "scenarios": 35,
    "duplicate_extra_copies": 35, "rows_after_dedup": 7455, "ue_series": 60,
    "dl_negative_deltas": 21, "ul_negative_deltas": 21, "radio_second_buckets": 4590,
}


class DuplicateConflictError(RuntimeError):
    def __init__(self, message: str, conflicts: pd.DataFrame):
        super().__init__(message)
        self.conflicts = conflicts


class SchemaError(RuntimeError):
    pass


class Checks:
    """Collects validation results.  kind='assert' = hard check, 'target' = audit target."""

    def __init__(self):
        self.items: list[dict] = []

    def add(self, name: str, passed: bool, detail: str = "", kind: str = "assert"):
        self.items.append({"name": name, "passed": bool(passed), "detail": str(detail), "kind": kind})

    def failed(self) -> list[dict]:
        return [c for c in self.items if c["kind"] == "assert" and not c["passed"]]

    def discrepancies(self) -> list[dict]:
        return [c for c in self.items if c["kind"] == "target" and not c["passed"]]

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.items, columns=["name", "passed", "detail", "kind"])


# --------------------------------------------------------------------------- #
# Small utilities
# --------------------------------------------------------------------------- #
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fmt(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)) or v is pd.NA:
        return "NaN"
    if isinstance(v, (bool, np.bool_)):
        return "yes" if v else "no"
    if isinstance(v, (int, np.integer)):
        return f"{int(v):,}"
    if isinstance(v, (float, np.floating)):
        v = float(v)
        if v == int(v) and abs(v) < 1e15:
            return f"{int(v):,}"
        return f"{v:,.3f}" if abs(v) < 1e6 else f"{v:.4e}"
    return str(v)


def md_table(df: pd.DataFrame, index: bool = False) -> str:
    if index:
        df = df.reset_index()
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join(_fmt(v) for v in row) + " |")
    return "\n".join(lines)


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    raise TypeError(f"not serialisable: {type(o)}")


# --------------------------------------------------------------------------- #
# Step 0/1: loading, schema, types, scenarios, missing values
# --------------------------------------------------------------------------- #
def load_radio_clean(path: Path) -> pd.DataFrame:
    # RNTI / PMI are hexadecimal-looking identifiers and must stay text.
    dtype = {c: "string" for c in ["rnti", "pmi"]}
    df = pd.read_csv(path, dtype=dtype)
    for c in ["rnti", "pmi"]:
        df[c] = df[c].astype(object)
    return df


def validate_schema_and_types(df: pd.DataFrame, checks: Checks) -> dict:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    extra = [c for c in df.columns if c not in REQUIRED_COLUMNS]
    checks.add("schema: all required columns present", not missing,
               f"missing={missing}" if missing else f"{len(REQUIRED_COLUMNS)} required columns present")
    if missing:
        raise SchemaError(f"radio_clean.csv is missing required columns: {missing}")
    checks.add("schema: no unexpected extra columns (informational)", not extra,
               f"extra={extra}" if extra else "none", kind="target")

    numeric_cols = (KPIS + COUNTERS + OOB_COLS
                    + ["ue_id", "timestamp_ms", "timestamp_s", "rnti_int", "cellid",
                       "in_sync", "is_duplicate", "file_row", "is_attack", "ddos"])
    bad_dtype = [c for c in numeric_cols if not pd.api.types.is_numeric_dtype(df[c])]
    checks.add("types: numeric columns are numeric dtype", not bad_dtype, f"non-numeric={bad_dtype}")

    non_finite = {c: int((~np.isfinite(df[c].astype(float))).sum() - df[c].isna().sum())
                  for c in numeric_cols if c not in bad_dtype}
    non_finite = {c: n for c, n in non_finite.items() if n}
    checks.add("types: no +/-inf values in numeric columns", not non_finite, f"{non_finite}" if non_finite else "none")

    int_like = ["ue_id", "timestamp_ms", "timestamp_s", "file_row"]
    bad_int = [c for c in int_like if not pd.api.types.is_integer_dtype(df[c])]
    checks.add("types: key/time columns are integer dtype", not bad_int, f"not integer={bad_int}")

    key_nulls = df[["scenario", "ue_id", "timestamp_ms"]].isna().sum().to_dict()
    checks.add("types: no nulls in key columns (scenario, ue_id, timestamp_ms)",
               sum(key_nulls.values()) == 0, f"{key_nulls}")
    return {"extra_columns": extra}


def validate_scenarios(df: pd.DataFrame, checks: Checks) -> pd.DataFrame:
    meta_cols = LABEL_COLS + ["folder", "source_fmt", "file_order_desc"]
    nun = df.groupby("scenario")[meta_cols].nunique(dropna=False)
    inconsistent = nun.columns[(nun > 1).any()].tolist()
    checks.add("scenarios: scenario-level metadata constant within each scenario",
               not inconsistent, f"inconsistent={inconsistent}" if inconsistent else f"{df.scenario.nunique()} scenarios")
    per_ue = df.groupby("scenario")["ue_id"].nunique()
    checks.add("scenarios: every scenario has at least one UE", bool((per_ue >= 1).all()), f"min UEs={int(per_ue.min())}")
    rnti_ok = (df["rnti_int"] == df["rnti"].map(lambda s: int(str(s), 16))).all()
    checks.add("types: rnti_int equals int(rnti, 16) for every row", bool(rnti_ok))
    return df.groupby("scenario")[meta_cols].first()


def missing_value_table(df: pd.DataFrame) -> pd.DataFrame:
    n = df.isna().sum()
    t = pd.DataFrame({"missing": n, "missing_pct": 100.0 * n / max(len(df), 1)})
    t.index.name = "column"
    return t


# --------------------------------------------------------------------------- #
# Step 1b: chronological sort, duplicate analysis and exact de-duplication
# --------------------------------------------------------------------------- #
def sort_chronologically(df: pd.DataFrame) -> pd.DataFrame:
    # file_row is used ONLY as the last tie-breaker so that the choice among identical
    # (scenario, ue_id, timestamp_ms) records is deterministic.  It never decides order
    # between different timestamps.
    return df.sort_values(DUP_KEY + ["file_row"], kind="mergesort").reset_index(drop=True)


def analyse_duplicates(df_sorted: pd.DataFrame) -> dict:
    flagged_mask = df_sorted.duplicated(DUP_KEY, keep=False)
    d = df_sorted[flagged_mask]
    rows = []
    if len(d):
        for col in PAYLOAD_COLS:
            nun = d.groupby(DUP_KEY)[col].nunique(dropna=False)
            for k in nun[nun > 1].index:
                rows.append({"scenario": k[0], "ue_id": k[1], "timestamp_ms": k[2],
                             "conflicting_column": col, "n_distinct_values": int(nun[k])})
    conflicts = pd.DataFrame(rows, columns=["scenario", "ue_id", "timestamp_ms",
                                            "conflicting_column", "n_distinct_values"])
    return {
        "n_rows_in_duplicate_groups": int(flagged_mask.sum()),
        "n_duplicate_groups": int(d.groupby(DUP_KEY).ngroups) if len(d) else 0,
        "n_extra_copies": int(df_sorted.duplicated(DUP_KEY, keep="first").sum()),
        "conflicts": conflicts,
        "conflict_rows": (d.merge(conflicts[DUP_KEY].drop_duplicates(), on=DUP_KEY)
                          if len(conflicts) else d.iloc[0:0]),
    }


def remove_exact_duplicates(df_sorted: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Remove later copies of identical-payload duplicates.  Caller must have verified
    there are no conflicts.  Returns (deduplicated frame, removal log)."""
    key = DUP_KEY
    extra_mask = df_sorted.duplicated(key, keep="first")
    removed = df_sorted[extra_mask]
    if removed.empty:
        cols = ["scenario", "ue_id", "timestamp_ms", "timestamp_s", "removed_file_row", "kept_file_row",
                "folder", "source_fmt", "file_order_desc", "input_is_duplicate_flag", "rnti",
                "n_rows_in_key_group", "measurement_payload_identical",
                "all_non_provenance_columns_identical", "is_first_sample_of_ue_series", "reason"]
        return df_sorted.copy(), pd.DataFrame(columns=cols)

    kept_file_row = df_sorted.loc[~extra_mask].set_index(key)["file_row"]
    group_size = df_sorted.groupby(key)["file_row"].transform("size")
    in_dup = df_sorted[df_sorted.duplicated(key, keep=False)]
    non_prov = [c for c in df_sorted.columns if c not in PROVENANCE_COLS + key]
    all_identical = (in_dup.groupby(key)[non_prov].nunique(dropna=False).max(axis=1) == 1)
    first_ts = df_sorted.groupby(["scenario", "ue_id"])["timestamp_ms"].transform("min")

    mi = pd.MultiIndex.from_frame(removed[key])
    log = pd.DataFrame({
        "scenario": removed["scenario"].values,
        "ue_id": removed["ue_id"].values,
        "timestamp_ms": removed["timestamp_ms"].values,
        "timestamp_s": removed["timestamp_s"].values,
        "removed_file_row": removed["file_row"].values,
        "kept_file_row": kept_file_row.reindex(mi).values,
        "folder": removed["folder"].values,
        "source_fmt": removed["source_fmt"].values,
        "file_order_desc": removed["file_order_desc"].values,
        "input_is_duplicate_flag": removed["is_duplicate"].values,
        "rnti": removed["rnti"].values,
        "n_rows_in_key_group": group_size.loc[removed.index].values,
        "measurement_payload_identical": True,
        "all_non_provenance_columns_identical": all_identical.reindex(mi).values,
        "is_first_sample_of_ue_series": (removed["timestamp_ms"] == first_ts.loc[removed.index]).values,
        "reason": "exact duplicate of earlier record with identical measurement payload",
    })
    return df_sorted.loc[~extra_mask].reset_index(drop=True), log.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Step 2: timestamp validation
# --------------------------------------------------------------------------- #
def validate_timestamps(df: pd.DataFrame, dedup: pd.DataFrame, checks: Checks) -> dict:
    ts = df["timestamp_ms"]
    checks.add("timestamps: timestamp_ms is integer and positive",
               bool(pd.api.types.is_integer_dtype(ts) and (ts > 0).all()))
    ndig = ts.astype(str).str.len()
    checks.add("timestamps: every timestamp_ms has 13 digits (epoch milliseconds)",
               bool((ndig == 13).all()), f"digit counts={ndig.value_counts().to_dict()}")
    utc = pd.to_datetime(ts, unit="ms", utc=True)
    in_range = (utc >= PLAUSIBLE_UTC_START) & (utc <= PLAUSIBLE_UTC_END)
    checks.add("timestamps: all values decode to a UTC date in the plausible range",
               bool(in_range.all()), f"decoded range {utc.min()} .. {utc.max()}")
    floor_s = ts // 1000
    checks.add("timestamps: timestamp_s == floor(timestamp_ms / 1000) for every row",
               bool((floor_s == df["timestamp_s"]).all()),
               f"mismatches={int((floor_s != df['timestamp_s']).sum())}")
    parsed = pd.to_datetime(df["time_utc"], utc=True, format="ISO8601")
    checks.add("timestamps: time_utc column equals the UTC decoding of timestamp_ms",
               bool((parsed == utc).all()), f"mismatches={int((parsed != utc).sum())}")
    checks.add("timestamps: time_utc strings carry an explicit +00:00 (UTC) offset",
               bool(df["time_utc"].astype(str).str.endswith("+00:00").all()))
    wid = df["scenario"] + "@" + df["timestamp_s"].astype(str)
    wid_ok = (wid == df["radio_window_id"]).all()
    checks.add("timestamps: radio_window_id == scenario@timestamp_s", bool(wid_ok))

    step = dedup.groupby(["scenario", "ue_id"])["timestamp_ms"].diff().dropna()
    checks.add("timestamps: strictly increasing within every (scenario, ue_id) after sort + dedup",
               bool((step > 0).all()), f"non-positive steps={int((step <= 0).sum())}")
    per_scn = df.groupby("scenario")["timestamp_ms"].agg(["min", "max"])
    per_scn["start_utc"] = pd.to_datetime(per_scn["min"], unit="ms", utc=True)
    per_scn["end_utc"] = pd.to_datetime(per_scn["max"], unit="ms", utc=True)
    return {"per_scenario_time": per_scn}


# --------------------------------------------------------------------------- #
# Step 3: counter engineering
# --------------------------------------------------------------------------- #
def compute_counters(d: pd.DataFrame) -> pd.DataFrame:
    """d must be sorted chronologically and de-duplicated.  Adds delta/interval columns.
    No clipping, no zero filling: invalid deltas are NaN."""
    d = d.copy()
    g = d.groupby(["scenario", "ue_id"], sort=False)
    d["series_row"] = g.cumcount()
    d["is_first_observation"] = d["series_row"] == 0
    prev_ts = g["timestamp_ms"].shift(1)
    d["interval_start_ms"] = prev_ts                    # delta covers (prev_ts, timestamp_ms]
    d["interval_end_ms"] = d["timestamp_ms"].astype(float)
    d["dt_s"] = (d["timestamp_ms"] - prev_ts) / 1000.0
    d["large_gap"] = d["dt_s"] > GAP_THRESHOLD_S
    d["rnti_prev"] = g["rnti"].shift(1)
    d["rnti_changed"] = d["rnti_prev"].notna() & (d["rnti"] != d["rnti_prev"])
    for col, p in (("dlBytes", "dl"), ("ulBytes", "ul")):
        d[f"{col}_prev"] = g[col].shift(1)
        raw = d[col] - d[f"{col}_prev"]
        d[f"{p}_delta_raw"] = raw
        d[f"{p}_reset"] = raw < 0
        valid = (~d["is_first_observation"]) & raw.notna() & (raw >= 0) & (~d["large_gap"])
        d[f"{p}_delta_valid"] = valid
        d[f"{p}_delta"] = raw.where(valid)              # NaN for first obs / reset / large gap
    d["counter_reset"] = d["dl_reset"] | d["ul_reset"]
    d["any_delta_valid"] = d["dl_delta_valid"] | d["ul_delta_valid"]
    return d


def file_order_negative_deltas(df_raw: pd.DataFrame) -> dict:
    """Supplementary diagnostic: negative differences if records were differenced in
    ORIGINAL FILE ORDER instead of chronologically.  Shows why chronological sorting matters."""
    s = df_raw.sort_values(["scenario", "ue_id", "file_row"], kind="mergesort")
    g = s.groupby(["scenario", "ue_id"], sort=False)
    return {"dl": int(((s["dlBytes"] - g["dlBytes"].shift(1)) < 0).sum()),
            "ul": int(((s["ulBytes"] - g["ulBytes"].shift(1)) < 0).sum()),
            "scenarios_newest_first": int(df_raw.groupby("scenario")["file_order_desc"].first().sum())}


def summarize_counters(c: pd.DataFrame, checks: Checks) -> dict:
    s: dict = {}
    s["n_records"] = len(c)
    s["n_series"] = int(c.groupby(["scenario", "ue_id"]).ngroups)
    s["n_first_observations"] = int(c["is_first_observation"].sum())
    s["dl_resets"] = int(c["dl_reset"].sum())
    s["ul_resets"] = int(c["ul_reset"].sum())
    s["both_resets"] = int((c["dl_reset"] & c["ul_reset"]).sum())
    s["either_resets"] = int(c["counter_reset"].sum())
    s["n_rnti_changes"] = int(c["rnti_changed"].sum())
    s["reset_and_rnti_change"] = int((c["counter_reset"] & c["rnti_changed"]).sum())
    s["reset_without_rnti_change"] = int((c["counter_reset"] & ~c["rnti_changed"]).sum())
    s["rnti_change_without_reset"] = int((c["rnti_changed"] & ~c["counter_reset"]).sum())
    s["n_large_gaps"] = int(c["large_gap"].sum())
    s["dt_median_s"] = float(c["dt_s"].median())
    s["dt_min_s"] = float(c["dt_s"].min())
    s["dt_max_s"] = float(c["dt_s"].max())
    s["dt_describe"] = c["dt_s"].describe()
    s["dl_valid"] = int(c["dl_delta_valid"].sum())
    s["ul_valid"] = int(c["ul_delta_valid"].sum())
    s["dl_invalid"] = int((~c["dl_delta_valid"]).sum())
    s["ul_invalid"] = int((~c["ul_delta_valid"]).sum())
    s["dl_zero_valid"] = int((c["dl_delta"] == 0).sum())
    s["ul_zero_valid"] = int((c["ul_delta"] == 0).sum())
    r = c[c["counter_reset"]]
    s["post_reset_dl"] = r["dlBytes"].describe() if len(r) else pd.Series(dtype=float)
    s["pre_reset_dl"] = r["dlBytes_prev"].describe() if len(r) else pd.Series(dtype=float)
    s["post_reset_ul"] = r["ulBytes"].describe() if len(r) else pd.Series(dtype=float)
    s["first_obs_dl"] = c.loc[c["is_first_observation"], "dlBytes"].describe()
    s["valid_dl_delta"] = c["dl_delta"].describe()
    s["valid_ul_delta"] = c["ul_delta"].describe()
    s["reset_rows"] = r[["scenario", "ue_id", "timestamp_ms", "rnti_prev", "rnti", "dt_s",
                         "dlBytes_prev", "dlBytes", "ulBytes_prev", "ulBytes"]].copy()
    s["resets_per_scenario"] = c[c["counter_reset"]].groupby("scenario").size()
    s["largest_gaps"] = c.nlargest(10, "dt_s")[["scenario", "ue_id", "timestamp_ms", "dt_s"]]

    checks.add("counters: nominal sampling interval is ~1 s (median dt within 0.9-1.1 s)",
               abs(s["dt_median_s"] - NOMINAL_INTERVAL_S) < 0.1, f"median dt={s['dt_median_s']:.3f} s")
    checks.add("counters: first observation of every UE series has NaN delta (not 0)",
               bool(c.loc[c["is_first_observation"], ["dl_delta", "ul_delta"]].isna().all().all()))
    checks.add("counters: reset rows keep NaN delta (never clipped to zero)",
               bool(c.loc[c["dl_reset"], "dl_delta"].isna().all() and c.loc[c["ul_reset"], "ul_delta"].isna().all()))
    checks.add("counters: no negative value survives in model-facing deltas",
               bool((c["dl_delta"].dropna() >= 0).all() and (c["ul_delta"].dropna() >= 0).all()))
    checks.add("counters [dataset-specific]: every counter reset coincides with an RNTI change",
               s["reset_without_rnti_change"] == 0,
               f"{s['reset_and_rnti_change']} of {s['either_resets']} resets coincide with an RNTI change; "
               f"{s['reset_without_rnti_change']} do not")
    checks.add("counters [dataset-specific]: every RNTI change coincides with a counter reset",
               s["rnti_change_without_reset"] == 0,
               f"{s['rnti_change_without_reset']} of {s['n_rnti_changes']} RNTI changes show no reset")
    return s


# --------------------------------------------------------------------------- #
# Step 4: quality flags (label-free, flag-only: no row is deleted, no value altered)
# --------------------------------------------------------------------------- #
def add_quality_flags(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d["q_rssi_lt_rsrp"] = (d["rssi"] < d["rsrp"]).fillna(False)
    d["q_phr_gt_40"] = (d["phr"] > PHR_PLAUSIBLE_MAX).fillna(False)
    d["q_phr_gt_63"] = (d["phr"] > PHR_INDEX_MAX).fillna(False)
    d["q_pusch_saturated"] = (d["puschSnr"] == PUSCH_SATURATION_CODE).fillna(False)
    zero = pd.Series(True, index=d.index)
    for f in ALL_ZERO_UL_FIELDS:
        zero &= (d[f] == 0).fillna(False)
    d["q_all_zero_ul"] = zero
    d["oob_any"] = d[OOB_COLS].astype(int).sum(axis=1) > 0
    return d


def recompute_oob(d: pd.DataFrame) -> dict:
    out = {}
    for k, (lo, hi) in PHYS.items():
        calc = ((d[k] < lo) | (d[k] > hi)).astype(int)
        out[k] = int((calc != d[f"{k}_flag_oob"]).sum())
    return out


# --------------------------------------------------------------------------- #
# Step 5: per-second aggregation
# --------------------------------------------------------------------------- #
def _valid_mask(d: pd.DataFrame, kpi: str, exclude_all_zero_ul: bool) -> pd.Series:
    m = d[kpi].notna() & np.isfinite(d[kpi].astype(float))
    if kpi == "puschSnr":
        m &= ~d["q_pusch_saturated"]                  # saturated code is censored, not a measurement
    if exclude_all_zero_ul:
        m &= ~d["q_all_zero_ul"]
    return m


def _kpi_block(d: pd.DataFrame, kpi: str, mask: pd.Series, suffix: str, index: pd.MultiIndex) -> pd.DataFrame:
    sub = d.loc[mask, ["scenario", "timestamp_s", kpi]]
    g = sub.groupby(["scenario", "timestamp_s"])[kpi]
    out = pd.DataFrame({
        f"{kpi}_mean{suffix}": g.mean(),
        f"{kpi}_std{suffix}": g.std(ddof=STD_DDOF),
        f"{kpi}_min{suffix}": g.min(),
        f"{kpi}_max{suffix}": g.max(),
        f"{kpi}_n{suffix}": g.count(),
    }).reindex(index)
    out[f"{kpi}_n{suffix}"] = out[f"{kpi}_n{suffix}"].fillna(0).astype("int64")
    return out


def aggregate_windows(d: pd.DataFrame) -> pd.DataFrame:
    """One row per (scenario, timestamp_s).  d must contain counter + quality columns."""
    d = d.copy()
    d["timestamp_s"] = (d["timestamp_ms"] // 1000).astype("int64")
    keys = ["scenario", "timestamp_s"]
    g = d.groupby(keys, sort=True)
    base = g.agg(first_timestamp_ms=("timestamp_ms", "min"),
                 last_timestamp_ms=("timestamp_ms", "max"),
                 n_records=("ue_id", "size"),
                 n_ue_reporting=("ue_id", "nunique"))
    index = base.index

    parts = [base]
    for kpi in KPIS:                                              # primary (raw, saturation-masked)
        parts.append(_kpi_block(d, kpi, _valid_mask(d, kpi, False), "", index))
    for kpi in NZ_KPIS:                                           # sensitivity: also drop all-zero UL reports
        parts.append(_kpi_block(d, kpi, _valid_mask(d, kpi, True), NZ_SUFFIX, index))

    # byte-derived (sensitivity only): sum(min_count=1) keeps all-invalid seconds as NaN
    bytes_df = pd.DataFrame({
        "dlBytes_delta_sum": g["dl_delta"].sum(min_count=1),
        "ulBytes_delta_sum": g["ul_delta"].sum(min_count=1),
        "n_valid_dl_delta": g["dl_delta"].count(),
        "n_valid_ul_delta": g["ul_delta"].count(),
    })
    d["_ivs"] = d["interval_start_ms"].where(d["any_delta_valid"])
    d["_ive"] = d["interval_end_ms"].where(d["any_delta_valid"])
    g2 = d.groupby(keys, sort=True)
    bytes_df["delta_interval_start_ms_min"] = g2["_ivs"].min()
    bytes_df["delta_interval_end_ms_max"] = g2["_ive"].max()
    parts.append(bytes_df)

    diag = pd.DataFrame({
        "n_counter_reset": g2["counter_reset"].sum(),
        "n_large_gap": g2["large_gap"].sum(),
        "n_first_observation": g2["is_first_observation"].sum(),
    })
    parts.append(diag)

    flag_map = {"q_rssi_lt_rsrp": "n_q_rssi_lt_rsrp", "q_phr_gt_40": "n_q_phr_gt_40",
                "q_phr_gt_63": "n_q_phr_gt_63", "q_pusch_saturated": "n_q_pusch_saturated",
                "q_all_zero_ul": "n_q_all_zero_ul", "oob_any": "n_oob_any"}
    fl = d.groupby(keys, sort=True)[list(flag_map)].sum().rename(columns=flag_map)
    oob = d.groupby(keys, sort=True)[OOB_COLS].sum()
    oob.columns = [f"n_oob_{k}" for k in KPIS]
    parts += [fl, oob]

    win = pd.concat(parts, axis=1)
    for c in ["n_counter_reset", "n_large_gap", "n_first_observation", *flag_map.values(),
              *[f"n_oob_{k}" for k in KPIS], "n_valid_dl_delta", "n_valid_ul_delta"]:
        win[c] = win[c].astype("int64")
    for c in ["delta_interval_start_ms_min", "delta_interval_end_ms_max"]:
        win[c] = win[c].astype("Int64")
    win = win.reset_index()

    chk = d.groupby("scenario")[LABEL_COLS + ["source_fmt"]].nunique().max().max()
    if chk != 1:
        raise RuntimeError("scenario-level label/provenance columns are not constant within scenarios")
    scn = d.groupby("scenario")[LABEL_COLS + ["source_fmt"]].first().reset_index()
    win = win.merge(scn, on="scenario", how="left", validate="m:1")
    win["radio_window_id"] = win["scenario"] + "@" + win["timestamp_s"].astype(str)
    win["window_start_utc"] = pd.to_datetime(win["timestamp_s"], unit="s", utc=True).dt.strftime("%Y-%m-%d %H:%M:%S")
    return win


# --------------------------------------------------------------------------- #
# Step 6: column roles / feature metadata
# --------------------------------------------------------------------------- #
def _stat_cols(kpis, suffix=""):
    return [f"{k}_{s}{suffix}" for k in kpis for s in STATS]


def column_roles() -> dict:
    roles = {
        "identifiers": ["scenario", "radio_window_id"],
        "labels": list(LABEL_COLS),
        "timestamps": ["timestamp_s", "window_start_utc", "first_timestamp_ms", "last_timestamp_ms",
                       "delta_interval_start_ms_min", "delta_interval_end_ms_max"],
        "core": _stat_cols(CORE_KPIS),
        "extended_additional": _stat_cols(EXTENDED_ADDITIONAL_KPIS),
        "held_out": _stat_cols(HELD_OUT_KPIS),
        "sensitivity_only": (["dlBytes_delta_sum", "ulBytes_delta_sum"]
                             + [f"{k}_{s}{NZ_SUFFIX}" for k in NZ_KPIS for s in (*STATS, "n")]),
        "diagnostics": (["n_records", "n_ue_reporting", "n_valid_dl_delta", "n_valid_ul_delta",
                         "n_counter_reset", "n_large_gap", "n_first_observation", "source_fmt"]
                        + [f"{k}_n" for k in KPIS]),
        "quality_flags": (["n_q_rssi_lt_rsrp", "n_q_phr_gt_40", "n_q_phr_gt_63", "n_q_pusch_saturated",
                           "n_q_all_zero_ul", "n_oob_any"] + [f"n_oob_{k}" for k in KPIS]),
    }
    return roles


def build_feature_metadata(win: pd.DataFrame, input_path: Path, input_sha: str) -> dict:
    r = column_roles()
    core, add = r["core"], r["extended_additional"]
    caution = _stat_cols(SESSION_SHIFT_CAUTION_KPIS)
    meta = {
        "preprocessing_version": {
            "version": PREPROCESSING_VERSION,
            "input_file": input_path.name,
            "input_sha256": input_sha,
            "python": platform.python_version(),
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "notes": "Raw radio_clean.csv is never modified. No timezone conversion is applied to radio timestamps.",
        },
        "identifiers": {
            "description": "Record identifiers / join keys. Never model features.",
            "columns": r["identifiers"],
            "join_key": ["scenario", "timestamp_s"],
        },
        "labels": {
            "description": "Scenario-level labels carried through unchanged from radio_clean.csv. "
                           "Never used to clean, flag, aggregate or transform any value. Never model features.",
            "columns": r["labels"],
        },
        "timestamps": {
            "description": "Time metadata. Radio timestamps are Unix epoch milliseconds (UTC); no extra conversion "
                           "applied. delta_interval_* describe the (start, end] intervals of the byte-counter deltas "
                           "summed in the same row so alignment can choose the correct network window. "
                           "Never model features.",
            "columns": r["timestamps"],
        },
        "primary_candidate_features": {
            "profile": "A_conservative_core",
            "description": "Conservative core profile. Statistics over valid reports within the second; "
                          "puschSnr statistics exclude the saturation code.",
            "kpis": CORE_KPIS,
            "statistics": list(STATS),
            "columns": core,
        },
        "extended_candidate_features": {
            "profile": "B_extended_candidate",
            "description": "Core profile plus SINR and CQI. SINR and CQI form a session-shift caution group "
                           "(the audit found unusually strong separation between scenario groups); report results with "
                           "and without them. Scenario dependence is not unique to these two KPIs (see report section 4).",
            "kpis": CORE_KPIS + EXTENDED_ADDITIONAL_KPIS,
            "columns": core + add,
            "additional_columns_over_core": add,
            "session_shift_caution_columns": caution,
        },
        "held_out_features": {
            "description": "Aggregated and exported for audit and sensitivity experiments ONLY. Held out of both "
                           "profiles until measurement semantics and session effects are understood.",
            "kpis": HELD_OUT_KPIS,
            "columns": r["held_out"],
            "reasons": {
                "rsrp": "RSSI < RSRP quality flag (n_q_rssi_lt_rsrp); semantics pending source documentation.",
                "rssi": "RSSI < RSRP quality flag (n_q_rssi_lt_rsrp); semantics pending source documentation.",
                "ri": "Rank indicator; measurement semantics and session effect unresolved.",
                "phr": "Values above the plausibility ceiling; encoding unconfirmed; NO offset correction applied.",
            },
        },
        "sensitivity_only_features": {
            "description": "Never part of a primary profile. Byte-derived values are deltas of cumulative counters; "
                           "_nz variants exclude records flagged q_all_zero_ul.",
            "byte_derived": ["dlBytes_delta_sum", "ulBytes_delta_sum"],
            "all_zero_ul_excluded_variants": [c for c in r["sensitivity_only"] if c.endswith(tuple(f"_{s}{NZ_SUFFIX}" for s in (*STATS, "n")))],
            "columns": r["sensitivity_only"],
            "other_sensitivity_candidates_held_in_diagnostics": ["n_ue_reporting"],
        },
        "diagnostic_features": {
            "description": "Counts and provenance for audit. Never model features.",
            "columns": r["diagnostics"],
        },
        "excluded_features": {
            "description": "Raw radio_clean.csv columns NOT exported to the window table.",
            "columns": ["ue_id", "rnti", "rnti_int", "cellid", "pmi", "pmi_0", "pmi_1", "in_sync",
                        "is_duplicate", "file_row", "file_order_desc", "folder", "time_utc",
                        "dlBytes", "ulBytes"] + OOB_COLS,
            "reasons": {
                "ue_id": "identifier (disjoint value ranges across scenario groups)",
                "rnti / rnti_int": "transient session identifier",
                "cellid": "identifier",
                "pmi / pmi_0 / pmi_1": "categorical codebook index, not a continuous KPI; sensitivity candidate only",
                "in_sync": "link-state bookkeeping, not a measurement feature",
                "is_duplicate / file_row / file_order_desc": "file-layout provenance (kept in the removal log)",
                "folder / time_utc": "provenance / redundant with timestamp_s",
                "dlBytes / ulBytes": "raw cumulative counters; only per-interval deltas are exported (sensitivity only)",
                "*_flag_oob": "record-level indicators retained in radio_clean.csv; per-second counts exported as n_oob_*",
            },
        },
        "quality_flags": {
            "description": "Per-second counts of record-level quality flags. Diagnostic only; never silently model features.",
            "columns": r["quality_flags"],
            "definitions": {
                "n_q_rssi_lt_rsrp": "records with rssi < rsrp (RSSI is normally >= RSRP)",
                "n_q_phr_gt_40": f"records with phr > {PHR_PLAUSIBLE_MAX} (equals the phr_flag_oob high side)",
                "n_q_phr_gt_63": f"records with phr > {PHR_INDEX_MAX} (exceeds a 6-bit index range)",
                "n_q_pusch_saturated": f"records with puschSnr == {PUSCH_SATURATION_CODE} (saturation code, 127 * 0.5)",
                "n_q_all_zero_ul": "records where " + ", ".join(ALL_ZERO_UL_FIELDS) + " are ALL exactly 0",
                "n_oob_any": "records with at least one original *_flag_oob == 1",
                "n_oob_<kpi>": "records with the original <kpi>_flag_oob == 1 (ranges from 02b cell 2)",
            },
        },
        "aggregation_settings": {
            "group_keys": ["scenario", "timestamp_s"],
            "timestamp_s": "floor(timestamp_ms / 1000)",
            "statistics": list(STATS),
            "std_ddof": STD_DDOF,
            "n_reports": "<kpi>_n = number of valid reports used in the statistics",
            "valid_report_rule": "finite value; puschSnr additionally excludes the saturation code",
            "all_zero_ul_rule": "pcmax == phr == pucchSnr == dlMcs == ulMcs == 0 (all five, same record)",
            "sensitivity_nz_kpis": NZ_KPIS,
            "primary_statistics_include_all_zero_ul_reports": True,
            "missing_values": "preserved as NaN; no imputation, no zero filling",
            "byte_sum": "groupby.sum(min_count=1) over valid deltas; all-invalid seconds stay NaN",
            "byte_delta_interval": "each delta covers (previous timestamp_ms, timestamp_ms]",
            "gap_threshold_s": GAP_THRESHOLD_S,
            "pusch_saturation_code": PUSCH_SATURATION_CODE,
            "duplicate_key": DUP_KEY,
            "duplicate_rule": "remove later copies only if the measurement payload is identical; otherwise stop",
            "sort_order": DUP_KEY + ["file_row (tie-break among identical keys only)"],
        },
        "model_feature_profiles": {
            "A_conservative_core": core,
            "B_extended_candidate": core + add,
            "session_shift_caution_features": caution,
            "never_in_profiles": ["identifiers", "labels", "timestamps", "diagnostic_features",
                                  "quality_flags", "sensitivity_only_features", "held_out_features",
                                  "excluded_features"],
        },
        "exported_columns": list(win.columns),
    }
    return meta


# --------------------------------------------------------------------------- #
# Step 8: validation
# --------------------------------------------------------------------------- #
def core_compute(raw: pd.DataFrame):
    """Pure chain raw -> window table, used by the pipeline and by the order-independence test."""
    s = sort_chronologically(raw)
    dup = analyse_duplicates(s)
    if len(dup["conflicts"]):
        raise DuplicateConflictError("conflicting duplicate records", dup["conflicts"])
    dedup, log = remove_exact_duplicates(s)
    c = compute_counters(dedup)
    q = add_quality_flags(c)
    win = aggregate_windows(q)
    return s, dedup, log, q, win


def independent_recompute_check(q: pd.DataFrame, win: pd.DataFrame, n_samples: int = 300) -> tuple[bool, str]:
    """Recompute sampled buckets with plain NumPy on the record-level frame."""
    q = q.copy()
    q["timestamp_s"] = q["timestamp_ms"] // 1000
    idx = np.unique(np.linspace(0, len(win) - 1, min(n_samples, len(win))).astype(int))
    bad = []
    for i in idx:
        row = win.iloc[i]
        sub = q[(q["scenario"] == row["scenario"]) & (q["timestamp_s"] == row["timestamp_s"])]
        for kpi in KPIS:
            for nz in (False, True):
                if nz and kpi not in NZ_KPIS:
                    continue
                v = sub[kpi].to_numpy(dtype=float)
                keep = np.isfinite(v)
                if kpi == "puschSnr":
                    keep &= ~(sub["puschSnr"].to_numpy() == PUSCH_SATURATION_CODE)
                if nz:
                    keep &= ~sub["q_all_zero_ul"].to_numpy()
                v = v[keep]
                sfx = NZ_SUFFIX if nz else ""
                exp = [v.mean() if len(v) else np.nan, v.std(ddof=0) if len(v) else np.nan,
                       v.min() if len(v) else np.nan, v.max() if len(v) else np.nan, float(len(v))]
                got = [row[f"{kpi}_mean{sfx}"], row[f"{kpi}_std{sfx}"], row[f"{kpi}_min{sfx}"],
                       row[f"{kpi}_max{sfx}"], float(row[f"{kpi}_n{sfx}"])]
                if not np.allclose(np.array(exp, float), np.array(got, float), rtol=1e-9, atol=1e-9, equal_nan=True):
                    bad.append((row["scenario"], int(row["timestamp_s"]), kpi, nz))
        for p in ("dl", "ul"):
            dv = sub[f"{p}_delta"].to_numpy(dtype=float)
            dv = dv[np.isfinite(dv)]
            exp = dv.sum() if len(dv) else np.nan
            got = row[f"{p}Bytes_delta_sum"]
            if not np.allclose([exp], [got], rtol=1e-9, atol=1e-9, equal_nan=True):
                bad.append((row["scenario"], int(row["timestamp_s"]), f"{p}Bytes_delta_sum", False))
    return (not bad), f"{len(idx)} sampled buckets recomputed with plain NumPy; mismatches={len(bad)}"


def run_validations(p: "RadioPipeline") -> None:
    ck, win, q, raw, dedup = p.checks, p.win, p.q, p.raw, p.dedup
    keys = ["scenario", "timestamp_s"]
    ck.add("output: unique (scenario, timestamp_s) keys", not win.duplicated(keys).any(),
           f"{len(win):,} windows, duplicates={int(win.duplicated(keys).sum())}")
    ck.add("records: no duplicate (scenario, ue_id, timestamp_ms) keys remain", not dedup.duplicated(DUP_KEY).any())
    ck.add("records: no exact duplicate measurement payloads remain",
           not dedup.duplicated(DUP_KEY + PAYLOAD_COLS).any())
    ck.add("records: input rows - removed duplicates == retained rows",
           len(raw) - len(p.removal_log) == len(dedup), f"{len(raw)} - {len(p.removal_log)} = {len(dedup)}")
    ck.add("records: removed rows are a subset of rows flagged is_duplicate in the input",
           bool(p.sorted_raw.loc[p.sorted_raw.duplicated(DUP_KEY, keep="first"), "is_duplicate"].eq(1).all())
           if len(p.removal_log) else True)
    flagged_recalc = p.sorted_raw.duplicated(DUP_KEY, keep=False).astype(int)
    ck.add("records: input is_duplicate flag reproduces from the duplicate key",
           bool((flagged_recalc == p.sorted_raw["is_duplicate"]).all()),
           f"mismatches={int((flagged_recalc != p.sorted_raw['is_duplicate']).sum())}")
    ck.add("records: quality flags removed no rows", len(q) == len(dedup), f"{len(q)} == {len(dedup)}")
    ck.add("scenarios: every source scenario is represented in the window table",
           set(win["scenario"]) == set(raw["scenario"]),
           f"{win['scenario'].nunique()} of {raw['scenario'].nunique()} scenarios")
    ck.add("aggregation: sum(n_records) == retained records", int(win["n_records"].sum()) == len(dedup),
           f"{int(win['n_records'].sum())} == {len(dedup)}")
    ck.add("aggregation: n_ue_reporting <= n_records everywhere", bool((win["n_ue_reporting"] <= win["n_records"]).all()))

    oob_diff = recompute_oob(dedup)
    ck.add("quality: original *_flag_oob columns reproduce from the 02b plausibility ranges",
           sum(oob_diff.values()) == 0, f"mismatching rows per KPI (non-zero shown)={ {k: v for k, v in oob_diff.items() if v} }")
    ck.add("quality: q_phr_gt_40 equals the high side of phr_flag_oob",
           bool((q["q_phr_gt_40"].astype(int) == ((q["phr"] > PHYS['phr'][1]).astype(int))).all()))

    # raw data unchanged
    ck.add("raw data: in-memory input frame unchanged by the pipeline",
           _frames_equal(p.raw, p.raw_snapshot))
    ck.add("raw data: input file SHA-256 identical before and after the run",
           sha256_file(p.input_path) == p.input_sha, p.input_sha[:16] + "...")

    # reproducibility
    ok, detail = independent_recompute_check(q, win)
    ck.add("reproducibility: independent NumPy recomputation of sampled buckets", ok, detail)
    if p.run_order_test:
        shuffled = raw.sample(frac=1.0, random_state=20250101).reset_index(drop=True)
        _, _, _, q2, win2 = core_compute(shuffled)
        same = _frames_equal(win.sort_values(keys).reset_index(drop=True), win2.sort_values(keys).reset_index(drop=True))
        cols = ["scenario", "ue_id", "timestamp_ms", "dl_delta", "ul_delta", "counter_reset"]
        same_c = _frames_equal(q[cols].sort_values(cols[:3]).reset_index(drop=True),
                               q2[cols].sort_values(cols[:3]).reset_index(drop=True))
        ck.add("reproducibility: results independent of original file order (shuffled-input rerun)",
               same and same_c, f"window table identical={same}; counter deltas identical={same_c}")

    # counters not turned into zero traffic
    dl_bad = q[(q["dl_reset"] | q["is_first_observation"]) & q["dl_delta"].notna()]
    ul_bad = q[(q["ul_reset"] | q["is_first_observation"]) & q["ul_delta"].notna()]
    ck.add("counters: a counter's reset / first-observation records contribute no value to that counter's byte sum",
           dl_bad.empty and ul_bad.empty,
           f"offending DL records={len(dl_bad)}, UL records={len(ul_bad)}")
    no_valid = win["n_valid_dl_delta"] == 0
    ck.add("counters: seconds with zero valid DL deltas have NaN (not 0) dlBytes_delta_sum",
           bool(win.loc[no_valid, "dlBytes_delta_sum"].isna().all()),
           f"{int(no_valid.sum())} such seconds")
    no_valid_u = win["n_valid_ul_delta"] == 0
    ck.add("counters: seconds with zero valid UL deltas have NaN (not 0) ulBytes_delta_sum",
           bool(win.loc[no_valid_u, "ulBytes_delta_sum"].isna().all()))

    # missing values preserved
    bad_missing = []
    for k in KPIS:
        for sfx in ([""] + ([NZ_SUFFIX] if k in NZ_KPIS else [])):
            n0 = win[f"{k}_n{sfx}"] == 0
            nan_stats = win[[f"{k}_{s}{sfx}" for s in STATS]].isna().all(axis=1)
            partial = win[[f"{k}_{s}{sfx}" for s in STATS]].isna().any(axis=1) & ~nan_stats
            if not ((n0 == nan_stats).all() and not partial.any()):
                bad_missing.append(f"{k}{sfx}")
    ck.add("missing values: statistics are NaN exactly where there are zero valid reports (no imputation)",
           not bad_missing, f"violations={bad_missing}" if bad_missing else "consistent for all KPI blocks")
    sat_max_ok = bool((win["puschSnr_max"].dropna() < PUSCH_SATURATION_CODE).all())
    ck.add("quality: PUSCH saturation code never enters puschSnr statistics", sat_max_ok)
    nz_n_ok = all((win[f"{k}_n{NZ_SUFFIX}"] <= win[f"{k}_n"]).all() for k in NZ_KPIS)
    ck.add("quality: _nz sensitivity variants never use more reports than the primary statistics", nz_n_ok)
    ck.add("quality: primary statistics are computed from raw values (all-zero UL reports kept)",
           bool((win["dlMcs_n"] >= win["dlMcs_n" + NZ_SUFFIX]).all()))

    # metadata <-> columns, leakage
    r = column_roles()
    exported_roles = [c for k in ("identifiers", "labels", "timestamps", "core", "extended_additional",
                                  "held_out", "sensitivity_only", "diagnostics", "quality_flags") for c in r[k]]
    dup_roles = pd.Series(exported_roles)[pd.Series(exported_roles).duplicated()].tolist()
    ck.add("metadata: no exported column is assigned to two roles", not dup_roles, f"{dup_roles}")
    ck.add("metadata: every exported column has a role",
           set(win.columns) == set(exported_roles),
           f"unassigned={sorted(set(win.columns) - set(exported_roles))}; "
           f"missing_in_export={sorted(set(exported_roles) - set(win.columns))}")
    prof = p.meta["model_feature_profiles"]
    banned = set()
    for k in ("identifiers", "labels", "timestamps", "diagnostics", "quality_flags", "sensitivity_only", "held_out"):
        banned |= set(r[k])
    banned |= set(p.meta["excluded_features"]["columns"])
    allowed_kpis = set(CORE_KPIS + EXTENDED_ADDITIONAL_KPIS)
    pat_ok = all(any(c == f"{k}_{s}" for k in allowed_kpis for s in STATS)
                 for c in prof["A_conservative_core"] + prof["B_extended_candidate"])
    ck.add("leakage: no identifier/label/timestamp/diagnostic/flag/held-out/byte/excluded column in model profiles",
           not (banned & set(prof["A_conservative_core"] + prof["B_extended_candidate"])))
    ck.add("leakage: profile columns are only <KPI>_{mean,std,min,max} of allowed KPIs", pat_ok)
    ck.add("leakage: held-out KPIs (rsrp, rssi, ri, phr) absent from both profiles",
           not any(c.split("_")[0] in HELD_OUT_KPIS for c in prof["A_conservative_core"] + prof["B_extended_candidate"]))
    ck.add("leakage: profile columns all exist in the exported window table",
           set(prof["B_extended_candidate"]) <= set(win.columns))
    ck.add("leakage: profile A is a subset of profile B",
           set(prof["A_conservative_core"]) <= set(prof["B_extended_candidate"]))

    # audit targets (reported, never hard-coded in logic)
    t = EXPECTED_TARGETS
    obs = {
        "input_rows": len(raw), "input_columns": raw.shape[1], "scenarios": raw["scenario"].nunique(),
        "duplicate_extra_copies": len(p.removal_log), "rows_after_dedup": len(dedup),
        "ue_series": p.counter_stats["n_series"], "dl_negative_deltas": p.counter_stats["dl_resets"],
        "ul_negative_deltas": p.counter_stats["ul_resets"], "radio_second_buckets": len(win),
    }
    p.target_table = pd.DataFrame({"target": list(t), "audit_expected": [t[k] for k in t],
                                   "observed": [obs[k] for k in t]})
    p.target_table["status"] = np.where(p.target_table["audit_expected"] == p.target_table["observed"], "match", "DISCREPANCY")
    for k in t:
        ck.add(f"audit target: {k}", obs[k] == t[k], f"expected {t[k]:,}, observed {obs[k]:,}", kind="target")


def _frames_equal(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    try:
        pd.testing.assert_frame_equal(a, b, check_exact=False, rtol=1e-12, atol=1e-12)
        return True
    except AssertionError:
        return False


# --------------------------------------------------------------------------- #
# Pipeline orchestration (each step is callable on its own, e.g. from the notebook)
# --------------------------------------------------------------------------- #
class RadioPipeline:
    def __init__(self, input_path=DEFAULT_INPUT, output_dir=DEFAULT_OUTDIR, run_order_test: bool = True):
        self.input_path = Path(input_path).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.run_order_test = run_order_test
        self.checks = Checks()
        self.stats: dict = {}
        self.written: list[Path] = []

    # ---- Step 1 ------------------------------------------------------------
    def step1_integrity(self):
        self.input_sha = sha256_file(self.input_path)
        self.input_stat = (self.input_path.stat().st_size, self.input_path.stat().st_mtime_ns)
        self.raw = load_radio_clean(self.input_path)
        self.raw_snapshot = self.raw.copy(deep=True)
        self.stats["schema"] = validate_schema_and_types(self.raw, self.checks)
        self.scenario_meta = validate_scenarios(self.raw, self.checks)
        self.missing = missing_value_table(self.raw)
        self.sorted_raw = sort_chronologically(self.raw)
        self.dup = analyse_duplicates(self.sorted_raw)
        if len(self.dup["conflicts"]):
            self.output_dir.mkdir(parents=True, exist_ok=True)
            path = self.output_dir / OUT_CONFLICTS
            self.dup["conflict_rows"].to_csv(path, index=False, lineterminator="\n")
            raise DuplicateConflictError(
                f"{self.dup['conflicts'][DUP_KEY].drop_duplicates().shape[0]} duplicate key(s) carry CONFLICTING "
                f"measurement values. Pipeline stopped; conflicts written to {path}.", self.dup["conflicts"])
        self.checks.add("duplicates: no conflicting measurement values within duplicate keys", True,
                        f"{self.dup['n_duplicate_groups']} duplicate groups, all payload-identical")
        self.dedup, self.removal_log = remove_exact_duplicates(self.sorted_raw)
        self.stats["file_order_negatives"] = file_order_negative_deltas(self.raw)
        self.rows_per_scenario = pd.DataFrame({
            "rows_in": self.raw.groupby("scenario").size(),
            "duplicates_removed": self.removal_log.groupby("scenario").size(),
            "rows_kept": self.dedup.groupby("scenario").size(),
        }).fillna(0).astype(int)
        return self

    # ---- Step 2 ------------------------------------------------------------
    def step2_timestamps(self):
        self.stats["time"] = validate_timestamps(self.sorted_raw, self.dedup, self.checks)
        return self

    # ---- Step 3 ------------------------------------------------------------
    def step3_counters(self):
        self.cdf = compute_counters(self.dedup)
        self.counter_stats = summarize_counters(self.cdf, self.checks)
        return self

    # ---- Step 4 ------------------------------------------------------------
    def step4_quality(self):
        self.q = add_quality_flags(self.cdf)
        return self

    # ---- Step 5 ------------------------------------------------------------
    def step5_aggregate(self):
        self.win = aggregate_windows(self.q)
        return self

    # ---- Step 6 ------------------------------------------------------------
    def step6_metadata(self):
        self.meta = build_feature_metadata(self.win, self.input_path, self.input_sha)
        return self

    # ---- Step 8 ------------------------------------------------------------
    def step8_validate(self):
        run_validations(self)
        return self

    # ---- Outputs -------------------------------------------------------------
    def counter_diagnostics_frame(self) -> pd.DataFrame:
        c = self.cdf
        out = pd.DataFrame({
            "scenario": c["scenario"], "ue_id": c["ue_id"], "series_row": c["series_row"],
            "timestamp_ms": c["timestamp_ms"], "timestamp_s": c["timestamp_ms"] // 1000,
            "interval_start_ms": c["interval_start_ms"].astype("Int64"),
            "interval_end_ms": c["interval_end_ms"].astype("int64"),
            "dt_s": c["dt_s"], "large_gap": c["large_gap"].astype(int),
            "rnti_prev": c["rnti_prev"], "rnti": c["rnti"], "rnti_changed": c["rnti_changed"].astype(int),
            "is_first_observation": c["is_first_observation"].astype(int),
            "dlBytes": c["dlBytes"], "dlBytes_prev": c["dlBytes_prev"].astype("Int64"),
            "dl_delta_raw": c["dl_delta_raw"], "dl_reset": c["dl_reset"].astype(int),
            "dl_delta_valid": c["dl_delta_valid"].astype(int), "dl_delta": c["dl_delta"],
            "ulBytes": c["ulBytes"], "ulBytes_prev": c["ulBytes_prev"].astype("Int64"),
            "ul_delta_raw": c["ul_delta_raw"], "ul_reset": c["ul_reset"].astype(int),
            "ul_delta_valid": c["ul_delta_valid"].astype(int), "ul_delta": c["ul_delta"],
            "counter_reset": c["counter_reset"].astype(int),
        })
        return out

    def write_outputs(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if self.output_dir / OUT_WINDOW == self.input_path:
            raise RuntimeError("refusing to overwrite the input file")
        p_win, p_json = self.output_dir / OUT_WINDOW, self.output_dir / OUT_JSON
        p_log, p_cnt = self.output_dir / OUT_DUPLOG, self.output_dir / OUT_COUNTERS
        self.win.to_csv(p_win, index=False, lineterminator="\n")
        with open(p_json, "w", encoding="utf-8") as fh:
            json.dump(self.meta, fh, indent=2, default=_json_default)
            fh.write("\n")
        self.removal_log.to_csv(p_log, index=False, lineterminator="\n")
        self.counter_diagnostics_frame().to_csv(p_cnt, index=False, lineterminator="\n")
        # post-write verification of the window table (round trip)
        back = pd.read_csv(p_win)
        same_shape = back.shape == self.win.shape and list(back.columns) == list(self.win.columns)
        num = [c for c in self.win.columns if pd.api.types.is_numeric_dtype(self.win[c])]
        same_vals = all(np.allclose(back[c].astype(float), self.win[c].astype(float), rtol=1e-12, atol=1e-12,
                                    equal_nan=True) for c in num)
        self.checks.add("outputs: window CSV round-trips (shape, columns, numeric values)", same_shape and same_vals,
                        f"{back.shape[0]:,} rows x {back.shape[1]} columns")
        meta_back = json.load(open(p_json, encoding="utf-8"))
        self.checks.add("outputs: feature-column JSON lists exactly the exported columns",
                        meta_back["exported_columns"] == list(back.columns))
        self.checks.add("outputs: input file untouched after writing (size, mtime, SHA-256)",
                        (self.input_path.stat().st_size, self.input_path.stat().st_mtime_ns) == self.input_stat
                        and sha256_file(self.input_path) == self.input_sha)
        self.written = [p_win, p_json, p_log, p_cnt]
        p_rep = self.output_dir / OUT_REPORT
        p_rep.write_text(render_report(self), encoding="utf-8")
        self.written.append(p_rep)
        return self.written

    def run(self):
        self.step1_integrity().step2_timestamps().step3_counters().step4_quality().step5_aggregate()
        self.step6_metadata().step8_validate()
        self.write_outputs()
        return self


# --------------------------------------------------------------------------- #
# Step 7: report (every number below is computed in this run)
# --------------------------------------------------------------------------- #
def render_report(p: RadioPipeline) -> str:
    raw, dd, q, win, cs = p.raw, p.dedup, p.q, p.win, p.counter_stats
    L: list[str] = []
    A = L.append
    A("# Radio Quality Report V2")
    A("")
    A(f"Generated by `radio_preprocessing_v2.py` ({PREPROCESSING_VERSION}). Every number in this report is computed "
      "from the actual run; the narrative text describes decisions, not results.")
    A("")
    A(f"- Input: `{p.input_path.name}` (SHA-256 `{p.input_sha}`)")
    A(f"- Python {platform.python_version()}, pandas {pd.__version__}, numpy {np.__version__}")
    A("- Labels were never used to clean, flag, aggregate or transform any value. Raw values are never altered; "
      "quality problems become flags, never deletions. No network-radio alignment and no timezone conversion of radio "
      "timestamps is performed here.")
    A("")

    # 1 ------------------------------------------------------------------
    A("## 1. Input and output row counts")
    A("")
    cnt = pd.DataFrame([
        ("Input rows", len(raw)), ("Input columns", raw.shape[1]), ("Scenarios", raw["scenario"].nunique()),
        ("Rows after exact de-duplication", len(dd)), ("UE series (scenario, ue_id)", cs["n_series"]),
        ("Output rows (radio-second windows)", len(win)), ("Output columns", win.shape[1]),
        ("Windows with exactly one reporting UE", int((win["n_ue_reporting"] == 1).sum())),
        ("Windows with two or more reporting UEs", int((win["n_ue_reporting"] >= 2).sum())),
    ], columns=["quantity", "value"])
    A(md_table(cnt))
    A("")
    A("Comparison with the previous audit's expected targets (reported, not hard-coded):")
    A("")
    A(md_table(p.target_table))
    A("")
    disc = p.target_table[p.target_table["status"] != "match"]
    A("All audit targets matched." if disc.empty else
      f"**{len(disc)} DISCREPANCY(IES) against the audit targets - see table above.**")
    A("")

    # 2 ------------------------------------------------------------------
    A("## 2. Duplicates")
    A("")
    lg = p.removal_log
    A(f"- Key: `(scenario, ue_id, timestamp_ms)`; rows in duplicate groups: {p.dup['n_rows_in_duplicate_groups']}; "
      f"groups: {p.dup['n_duplicate_groups']}; extra copies: {p.dup['n_extra_copies']}.")
    A(f"- Groups whose measurement payload ({', '.join(PAYLOAD_COLS)}) differs: **{len(p.dup['conflicts'])}** "
      "(a conflict would stop the pipeline and be written to `radio_duplicate_conflicts_v2.csv`).")
    if len(lg):
        A(f"- Removed: {len(lg)} records; payload identical in {int(lg['measurement_payload_identical'].sum())}; all "
          f"non-provenance columns identical in {int(lg['all_non_provenance_columns_identical'].sum())}; "
          f"copy is the first sample of its UE series in {int(lg['is_first_sample_of_ue_series'].sum())}; "
          f"adjacent file rows (kept = removed - 1) in {int((lg['removed_file_row'] - lg['kept_file_row']).abs().eq(1).sum())}.")
        A(f"- Source format of removed records: {lg['source_fmt'].value_counts().to_dict()}.")
    A("- Which copy is kept: the first in `(scenario, ue_id, timestamp_ms, file_row)` order. `file_row` is only a "
      "deterministic tie-break between identical keys; it never orders different timestamps.")
    A("- Cause: the source loader returns one source per scenario, so CSV/JSON overlap cannot create these rows. "
      "Whether the raw files contain them cannot be tested here (raw files are not in the repository).")
    A("")
    A(md_table(lg.groupby("scenario").size().rename("removed").reset_index().head(40)) if len(lg) else "No duplicates.")
    A("")

    # 3 ------------------------------------------------------------------
    A("## 3. Missing values")
    A("")
    mv = p.missing[p.missing["missing"] > 0]
    A(f"Input: {int((p.missing['missing'] > 0).sum())} of {raw.shape[1]} columns contain missing values "
      f"(total missing cells: {int(p.missing['missing'].sum())}).")
    if len(mv):
        A("")
        A(md_table(mv, index=True))
    A("")
    wm = win.isna().sum()
    wm = wm[wm > 0]
    A(f"Window table: {len(wm)} columns contain NaN (NaN means 'no valid report / no valid delta', never imputed).")
    if len(wm):
        A("")
        A(md_table(wm.rename("NaN windows").to_frame().rename_axis("column"), index=True))
    A("")

    # 4 ------------------------------------------------------------------
    A("## 4. KPI ranges and statistics (records after de-duplication)")
    A("")
    rows = []
    for k in KPIS + COUNTERS:
        s = dd[k]
        rows.append((k, int(s.notna().sum()), 100.0 * s.isna().mean(), s.min(), s.max(), s.mean(), s.std(), s.nunique()))
    A(md_table(pd.DataFrame(rows, columns=["column", "n", "missing_%", "min", "max", "mean", "std (ddof=1)", "distinct"])))
    A("")
    A("Between-scenario dependence (eta-squared = between-scenario sum of squares / total sum of squares, "
      "label-free; high values mean the KPI mostly reflects which capture it came from):")
    A("")
    eta = []
    for k in KPIS:
        v = dd[["scenario", k]].dropna()
        tot = ((v[k] - v[k].mean()) ** 2).sum()
        gm = v.groupby("scenario")[k].transform("mean")
        eta.append((k, float(((gm - v[k].mean()) ** 2).sum() / tot) if tot > 0 else np.nan))
    eta_df = pd.DataFrame(eta, columns=["kpi", "eta_squared_by_scenario"])
    A(md_table(eta_df))
    A("")
    high_eta = eta_df.loc[eta_df["eta_squared_by_scenario"] >= ETA_HIGH, "kpi"].tolist()
    in_core = [k for k in high_eta if k in CORE_KPIS]
    in_ext = [k for k in high_eta if k in EXTENDED_ADDITIONAL_KPIS]
    in_held = [k for k in high_eta if k in HELD_OUT_KPIS]
    A(f"KPIs with eta-squared >= {ETA_HIGH}: {', '.join(high_eta) or 'none'}. Of these, in the conservative core: "
      f"{', '.join(in_core) or 'none'}; in the extended additions (sinr, cqi): {', '.join(in_ext) or 'none'}; held out: "
      f"{', '.join(in_held) or 'none'}. Scenario dependence is therefore not unique to the caution group, and the "
      "conservative core is not session-free either.")
    A("")

    # 5 ------------------------------------------------------------------
    A("## 5. Original out-of-bound (OOB) flags")
    A("")
    oob_rows = []
    for k, (lo, hi) in PHYS.items():
        s = dd[k]
        oob_rows.append((k, f"[{lo}, {hi}]", int((s < lo).sum()), int((s > hi).sum()),
                         int(dd[f"{k}_flag_oob"].sum()), 100.0 * dd[f"{k}_flag_oob"].mean()))
    A(md_table(pd.DataFrame(oob_rows, columns=["kpi", "plausible range (02b)", "below", "above", "flag_oob rows", "% of rows"])))
    A("")
    A(f"Rows with at least one OOB flag: {int(q['oob_any'].sum())} of {len(q)}. The original flags are retained "
      "unchanged in `radio_clean.csv`; the window table carries per-second counts (`n_oob_<kpi>`, `n_oob_any`). "
      "No row is dropped because of a flag.")
    A("")

    # 6 ------------------------------------------------------------------
    A("## 6. Counter resets")
    A("")
    fo = p.stats["file_order_negatives"]
    ct = pd.DataFrame([
        ("UE series", cs["n_series"]), ("First observations (delta = NaN)", cs["n_first_observations"]),
        ("Negative DL deltas, chronological order", cs["dl_resets"]),
        ("Negative UL deltas, chronological order", cs["ul_resets"]),
        ("Records with a reset on both counters", cs["both_resets"]),
        ("Records with a reset on either counter", cs["either_resets"]),
        ("RNTI changes within a UE series", cs["n_rnti_changes"]),
        ("Resets that coincide with an RNTI change", cs["reset_and_rnti_change"]),
        ("Resets without an RNTI change", cs["reset_without_rnti_change"]),
        ("RNTI changes without a reset", cs["rnti_change_without_reset"]),
        ("Valid DL deltas (incl. zero deltas)", cs["dl_valid"]), ("Valid UL deltas (incl. zero deltas)", cs["ul_valid"]),
        ("Invalid DL deltas", cs["dl_invalid"]), ("Invalid UL deltas", cs["ul_invalid"]),
        ("Valid DL deltas equal to 0", cs["dl_zero_valid"]), ("Valid UL deltas equal to 0", cs["ul_zero_valid"]),
        ("Negative DL diffs if differenced in ORIGINAL FILE ORDER (supplementary)", fo["dl"]),
        ("Negative UL diffs if differenced in ORIGINAL FILE ORDER (supplementary)", fo["ul"]),
        ("Scenarios whose source file is stored newest-first", fo["scenarios_newest_first"]),
    ], columns=["quantity", "value"])
    A(md_table(ct))
    A("")
    A("Decision: deltas are first-order differences within `(scenario, ue_id)` in chronological order. The first "
      "observation, reset records and large-gap records get **NaN** (never 0, never clipped). Segments are NOT created "
      "from RNTI changes; instead the RNTI/reset relationship is tested and asserted for this dataset only. Each delta "
      "covers `(previous timestamp_ms, timestamp_ms]`; the start and end are kept in the diagnostics file "
      "(`interval_start_ms`, `interval_end_ms`) and, per second, as `delta_interval_start_ms_min` / "
      "`delta_interval_end_ms_max`.")
    A("")
    if len(cs["reset_rows"]):
        A("All reset records:")
        A("")
        A(md_table(cs["reset_rows"]))
        A("")
        A("Counter level around resets (DL): pre-reset value summary and post-reset value summary:")
        A("")
        A(md_table(pd.DataFrame({"pre_reset_dlBytes": cs["pre_reset_dl"], "post_reset_dlBytes": cs["post_reset_dl"]}).round(1).rename_axis("statistic"), index=True))
        A("")
    A("Resets per scenario: " + (", ".join(f"{k}: {v}" for k, v in cs["resets_per_scenario"].items()) or "none") + ".")
    A("")

    # 7 ------------------------------------------------------------------
    A("## 7. Time gaps")
    A("")
    A(f"Interval between consecutive records of a UE (seconds): median {cs['dt_median_s']:.3f}, min {cs['dt_min_s']:.3f}, "
      f"max {cs['dt_max_s']:.3f}. Gap threshold: {GAP_THRESHOLD_S} s. Records flagged `large_gap`: **{cs['n_large_gaps']}**.")
    A("")
    A(md_table(cs["dt_describe"].round(4).rename("dt_s").to_frame().rename_axis("statistic"), index=True))
    A("")
    A("Ten largest intervals:")
    A("")
    A(md_table(cs["largest_gaps"]))
    A("")

    # 8 ------------------------------------------------------------------
    A("## 8. PHR encoding concerns")
    A("")
    ph = dd["phr"]
    flagged_phr_scn = q.groupby("scenario")["q_phr_gt_40"].sum()
    flagged_phr_scn = flagged_phr_scn[flagged_phr_scn > 0]
    A(f"- PHR range observed: {ph.min():g} .. {ph.max():g}. Records with PHR > {PHR_PLAUSIBLE_MAX}: **{int(q['q_phr_gt_40'].sum())}**; "
      f"PHR > {PHR_INDEX_MAX} (outside a 6-bit index range): **{int(q['q_phr_gt_63'].sum())}**; records with PHR == 0: {int((ph == 0).sum())}.")
    top = ph[ph > PHR_PLAUSIBLE_MAX].value_counts().sort_index(ascending=False).head(12)
    A("- Values above the ceiling (value: count): " + (", ".join(f"{k:g}: {v}" for k, v in top.items()) or "none") + ".")
    A(f"- Scenarios with at least one PHR > {PHR_PLAUSIBLE_MAX}: {len(flagged_phr_scn)} of {dd['scenario'].nunique()}.")
    if len(flagged_phr_scn):
        ddos_vals = dd.groupby("scenario")["ddos"].first().reindex(flagged_phr_scn.index)
        A(f"- Observation (not a conclusion): the `ddos` scenario flag is 1 for {int(ddos_vals.sum())} of those "
          f"{len(flagged_phr_scn)} scenarios. Co-occurrence with a scenario group is an observation about how the data "
          "was captured; the flag itself is defined without labels and class separation is not evidence about attack physics.")
    A("- **No offset (e.g. subtracting 32) or rescaling is applied.** The encoding is unconfirmed; original values are "
      "preserved, flagged (`n_q_phr_gt_40`, `n_q_phr_gt_63`) and PHR statistics are exported as held-out features only.")
    A("")
    A("RSSI < RSRP check (RSSI is normally at least RSRP):")
    A("")
    r_scn = q.groupby("scenario")["q_rssi_lt_rsrp"].agg(["sum", "size"])
    r_scn = r_scn[r_scn["sum"] > 0]
    A(f"- Records flagged: **{int(q['q_rssi_lt_rsrp'].sum())}** of {len(q)}; scenarios with any flagged record: "
      f"{len(r_scn)} of {dd['scenario'].nunique()}; scenarios where EVERY record is flagged: {int((r_scn['sum'] == r_scn['size']).sum())}.")
    A("- Both columns are preserved untouched (no swap, no transform) and held out of the primary feature profiles pending source documentation.")
    A("")

    # 9 ------------------------------------------------------------------
    A("## 9. PUSCH SNR saturation")
    A("")
    sat = q["q_pusch_saturated"]
    nonsat_max = dd.loc[dd["puschSnr"] != PUSCH_SATURATION_CODE, "puschSnr"].max()
    A(f"- Saturation code: `{PUSCH_SATURATION_CODE}` (= 127 x 0.5, the top code of a 7-bit half-dB field - treated as a censored value, not a measurement).")
    A(f"- Saturated records: **{int(sat.sum())}** of {len(q)}; scenarios affected: {int((q.groupby('scenario')['q_pusch_saturated'].sum() > 0).sum())}; "
      f"largest non-saturated value: {nonsat_max:g}.")
    A(f"- Windows with at least one saturated report: {int((win['n_q_pusch_saturated'] > 0).sum())}; "
      f"windows where ALL reports are saturated (puschSnr statistics = NaN): {int((win['puschSnr_n'] == 0).sum())}.")
    A("- The raw value stays in the data; saturated reports are excluded from every `puschSnr_*` statistic (primary and `_nz`).")
    A("")

    # 10 -----------------------------------------------------------------
    A("## 10. All-zero uplink reports")
    A("")
    z = q["q_all_zero_ul"]
    A(f"- Rule: `{' == '.join(ALL_ZERO_UL_FIELDS)} == 0` on the same record. Flagged records: **{int(z.sum())}** of {len(q)}; "
      f"scenarios affected: {int((q.groupby('scenario')['q_all_zero_ul'].sum() > 0).sum())}.")
    A("- Single-column zeros are NOT reinterpreted as missing. Individual zero counts for context: " +
      ", ".join(f"{f}: {int((dd[f] == 0).sum())}" for f in ALL_ZERO_UL_FIELDS + ['puschSnr']) + ".")
    A(f"- Windows containing at least one such record: {int((win['n_q_all_zero_ul'] > 0).sum())}; windows where every record is such a report: "
      f"{int((win['n_q_all_zero_ul'] == win['n_records']).sum())}.")
    n_diff = int(sum((win[f'{k}_n'] != win[f'{k}_n{NZ_SUFFIX}']).sum() for k in NZ_KPIS[:1]))
    A(f"- Sensitivity representation: `<kpi>_<stat>{NZ_SUFFIX}` columns for {', '.join(NZ_KPIS)} exclude these records "
      f"(windows where the dlMcs report count changes: {n_diff}). Primary statistics keep them (raw values), so the effect can be measured.")
    A("")

    # 11 -----------------------------------------------------------------
    A("## 11. Per-scenario data-quality tables")
    A("")
    pt = p.stats["time"]["per_scenario_time"]
    s1 = p.rows_per_scenario.copy()
    s1["class_fm"] = p.scenario_meta["class_fm"]
    s1["ue_series"] = dd.groupby("scenario")["ue_id"].nunique()
    s1["windows"] = win.groupby("scenario").size()
    s1["counter_resets"] = q.groupby("scenario")["counter_reset"].sum()
    s1["start_utc"] = pt["start_utc"].dt.strftime("%m-%d %H:%M:%S")
    s1["end_utc"] = pt["end_utc"].dt.strftime("%H:%M:%S")
    s1 = s1[["class_fm", "rows_in", "duplicates_removed", "rows_kept", "ue_series", "windows", "counter_resets", "start_utc", "end_utc"]]
    A("Structure:")
    A("")
    A(md_table(s1, index=True))
    A("")
    s2 = q.groupby("scenario").agg(
        rssi_lt_rsrp=("q_rssi_lt_rsrp", "sum"), phr_gt_40=("q_phr_gt_40", "sum"), phr_gt_63=("q_phr_gt_63", "sum"),
        pusch_saturated=("q_pusch_saturated", "sum"), all_zero_ul=("q_all_zero_ul", "sum"), rows_any_oob=("oob_any", "sum"))
    s2.insert(0, "rows", dd.groupby("scenario").size())
    A("Quality flags (records):")
    A("")
    A(md_table(s2, index=True))
    A("")

    # 12 -----------------------------------------------------------------
    A("## 12. Feature inclusion / exclusion decisions")
    A("")
    prof = p.meta["model_feature_profiles"]
    dec = pd.DataFrame([
        ("A. Conservative core", ", ".join(CORE_KPIS), f"{len(prof['A_conservative_core'])} columns (mean/std/min/max)", "puschSnr excludes the saturation code"),
        ("B. Extended candidate", "core + " + ", ".join(EXTENDED_ADDITIONAL_KPIS), f"{len(prof['B_extended_candidate'])} columns", "sinr/cqi: session-shift caution group (flagged by the audit for strong separation between scenario groups; see the eta-squared note in section 4 - not unique to these two KPIs)"),
        ("Held out", ", ".join(HELD_OUT_KPIS), f"{len(p.meta['held_out_features']['columns'])} columns exported", "semantics / session effects unresolved; audit and sensitivity only"),
        ("Sensitivity only", "dlBytes/ulBytes deltas; *_nz variants", f"{len(p.meta['sensitivity_only_features']['columns'])} columns", "cumulative counters; suspicious-report exclusion"),
        ("Diagnostics", "n_records, n_ue_reporting, n_valid_*_delta, n_* counts, <kpi>_n, source_fmt", f"{len(p.meta['diagnostic_features']['columns'])} columns", "never features"),
        ("Quality flags", "n_q_*, n_oob_*", f"{len(p.meta['quality_flags']['columns'])} columns", "never silently features"),
        ("Identifiers / labels / timestamps", "scenario, radio_window_id; family, mode, class_fm, is_attack, ddos; time fields", "carried as metadata", "never features"),
        ("Not exported", "ue_id, rnti, rnti_int, cellid, pmi*, in_sync, file provenance, raw counters", "see radio_feature_columns_v2.json", "identifiers / provenance / categorical"),
    ], columns=["group", "members", "size", "rationale"])
    A(md_table(dec))
    A("")

    # 13 -----------------------------------------------------------------
    A("## 13. Limitations and unresolved questions")
    A("")
    A("1. The raw per-scenario CSV/JSON radio files and the dataset documentation are not in the repository, so "
      "duplicate causes, PHR/RSSI/RSRP semantics, counter semantics and logger/packet-capture clock synchronisation "
      "could not be verified at source.")
    A("2. The RNTI-change/reset relationship is verified for THIS dataset only; it is asserted, not assumed to be a general rule.")
    A("3. A byte delta covers `(previous timestamp_ms, timestamp_ms]`, whose position inside one-second network windows "
      "depends on the millisecond phase of each UE's sampling. Which network window a delta belongs to is therefore an "
      "alignment decision still to be made (the interval bounds are kept for it); the end-second bucket used here is a convention only.")
    A("4. Statistics over simultaneous UEs pool them: no UE-to-flow mapping exists, so this is temporal aggregation, not per-flow measurement. "
      "Std is 0 by construction when a second has one report; use `<kpi>_n` and `n_ue_reporting` to see this.")
    A("5. Primary statistics keep all-zero UL reports (raw values); the `_nz` variants are the sensitivity alternative. Which is "
      "appropriate depends on what such records mean, which is undocumented.")
    A(f"6. KPIs with eta-squared >= {ETA_HIGH} (section 4): {', '.join(high_eta) or 'none'}; "
      f"{len(in_core)} of them in the conservative core. Capture/session dependence cannot be removed by this preprocessing. "
      "Any later separation between scenario groups must not be read as attack evidence without controlling for it.")
    A("7. Windows with no valid PUSCH report have NaN `puschSnr_*`; downstream code must handle missing values explicitly.")
    A("")

    # 14 -----------------------------------------------------------------
    A("## 14. Validation assertions")
    A("")
    fr = p.checks.frame()
    fr["result"] = np.where(fr["passed"], "PASS", np.where(fr["kind"] == "assert", "FAIL", "DISCREPANCY"))
    A(md_table(fr[["result", "name", "detail"]]))
    A("")
    nfail = len(p.checks.failed())
    A(f"Hard assertions: {int((fr['kind'] == 'assert').sum())}; failed: **{nfail}**. Audit-target discrepancies: {len(p.checks.discrepancies())}.")
    A("")
    return "\n".join(L)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Radio preprocessing V2 (Member 2, Phase 1)")
    ap.add_argument("--input", default=str(DEFAULT_INPUT), help="path to radio_clean.csv (read-only)")
    ap.add_argument("--output-dir", default=str(DEFAULT_OUTDIR), help="directory for the V2 outputs")
    ap.add_argument("--skip-order-test", action="store_true", help="skip the shuffled-input reproducibility rerun")
    a = ap.parse_args(argv)
    p = RadioPipeline(a.input, a.output_dir, run_order_test=not a.skip_order_test)
    try:
        p.run()
    except DuplicateConflictError as e:
        print(f"STOPPED: {e}", file=sys.stderr)
        print(e.conflicts.to_string(index=False), file=sys.stderr)
        return 2
    except SchemaError as e:
        print(f"STOPPED: {e}", file=sys.stderr)
        return 1
    fr = p.checks.frame()
    print(f"input rows {len(p.raw):,} -> after dedup {len(p.dedup):,} -> windows {len(p.win):,} x {p.win.shape[1]} cols")
    for c in p.checks.items:
        tag = "PASS" if c["passed"] else ("FAIL" if c["kind"] == "assert" else "DISCREPANCY")
        print(f"  [{tag}] {c['name']}  ({c['detail']})")
    for f in p.written:
        print("  wrote", f)
    nfail = len(p.checks.failed())
    print(f"hard assertions failed: {nfail}; audit-target discrepancies: {len(p.checks.discrepancies())}")
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
