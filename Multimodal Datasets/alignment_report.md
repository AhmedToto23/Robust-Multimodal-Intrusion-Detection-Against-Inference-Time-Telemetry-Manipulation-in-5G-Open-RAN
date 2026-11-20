# Alignment Report — 03 Modality Alignment
**NetsLab-5G-ORAN-IDD V1 · Window-Level Network × Radio Telemetry**

---

## 1. Overview

This notebook (`03_modality_alignment.ipynb`) joins two cleaned modalities into a single paired dataset:

| Modality | Source | Granularity |
|---|---|---|
| **Network** | `network_clean.csv` | 1-s windows (packet capture aggregated by `01b`) |
| **Radio** | `radio_clean.csv` | Per-UE ~1 Hz telemetry rows (from `02b`) |

**Output:** `multimodal_dataset.csv` — 4,139 rows × 77 columns

---

## 2. Alignment Design

### 2.1 Join Key

```
network window  ⟷  radio second
     scenario  ×  timestamp_s         (UTC epoch seconds)
```

Both sides are keyed on `(scenario, timestamp_s)` where `timestamp_s = ⌊timestamp_ms / 1000⌋`.

### 2.2 Join Type: Inner (No Zero-Fill)

An **inner join** is used deliberately. Network windows that have no radio measurement in the same UTC second are **excluded** rather than zero-filled.

> [!IMPORTANT]
> Zero-filling would create a spurious "silence = benign" signal — a shortcut the classifier could exploit rather than learning genuine attack signatures.

**Result:** 4,190 network windows → **4,139 paired rows** (51 windows excluded, 1.2% loss).

### 2.3 Radio Aggregation (Multi-UE → 1 row/second)

Benign and DDoS scenarios have **2–3 UEs active simultaneously**, producing multiple radio rows per second. Before joining, radio is aggregated per `(scenario_net, timestamp_s)`:

| Radio column group | Aggregation |
|---|---|
| KPI measurements (rsrp, rssi, rsrq, sinr, cqi, dlMcs, ulMcs, dlBler, ulBler, ri, phr, pcmax, pucchSnr, puschSnr) | `mean` + `std` across UEs |
| `dlBytes_delta`, `ulBytes_delta` | `sum` across UEs → `dlBytes_per_s`, `ulBytes_per_s` |
| UE identifiers | `nunique` → `ue_count` |

**Post-aggregation radio shape:** 4,590 seconds × 37 columns.

### 2.4 Byte Counter Handling

`dlBytes` and `ulBytes` are **cumulative counters** (max observed: 13.9 GB dl, 2.9 GB ul). Raw values would leak session duration and attack identity, so **per-second deltas** are computed:

```python
radio[f"{col}_delta"] = (
    radio.groupby(["scenario", "ue_id"])[col]
         .diff()
         .clip(lower=0)   # counter reset / new session → treat as 0
)
```

Deltas are then summed across UEs within each second.

### 2.5 Duplicate Removal

Radio contains **70 flagged duplicate rows** (exactly 2 per scenario × 35 scenarios = 1 pair per scenario). All are exact duplicates on `(scenario, ue_id, timestamp_ms)`. One copy of each pair is dropped **before** aggregation.

```
Rows before dedup : 7,490
Rows after  dedup : 7,455  (removed 35 duplicates)
```

### 2.6 Scenario Name Mapping

Radio uses underscore notation for DDoS scenarios; network does not:

| Radio name | Network name |
|---|---|
| `DDOS_ICMP1` | `DDOSICMP1` |
| `DDOS_SYN1` | `DDOSSYN1` |
| `DDOS_TCP1` | `DDOSTCP1` |
| `DDOS_UDP1` | `DDOSUDP1` |
| All others | Identical |

Fix: `s.replace("DDOS_", "DDOS")` applied to all radio scenario names before joining. Without this, all 12 DDoS scenarios (≈37% of radio rows) would be silently lost.

**Post-mapping coverage:** 35 / 35 scenarios matched, 0 missing, 0 extra. ✅

### 2.7 Timezone: IST +1 h

Benign captures were recorded in IST (UTC+1). The `+1 h` correction is already applied in `network_clean.csv`. Verification:

```
Network Benign UTC span : 2025-04-14 12:34:44 → 13:19:02 UTC
Radio   Benign UTC span : 2025-04-14 12:34:37 → 13:19:01 UTC
Overlap OK              : True ✅
```

### 2.8 PortScan Partial Windows

`network_clean.csv` retains 6 `is_partial == 1` windows for PortScan (edge seconds at capture boundaries). These are **kept** — filtering them would leave PortScan with only 2 paired windows instead of 8.

---

## 3. Per-Scenario Alignment Results

| Scenario | Class | Net windows | Radio agg-s | Paired | Unmatched | % Matched |
|---|---|---|---|---|---|---|
| Benign1 | Benign | 122 | 128 | 121 | 1 | 99.2% |
| Benign2 | Benign | 235 | 319 | 235 | 0 | **100%** |
| Benign3 | Benign | 178 | 303 | 177 | 1 | 99.4% |
| Benign4 | Benign | 230 | 305 | 229 | 1 | 99.6% |
| Benign5 | Benign | 153 | 156 | 152 | 1 | 99.3% |
| Benign6 | Benign | 271 | 304 | 270 | 1 | 99.6% |
| DDOSICMP1 | ICMP_DDoS | 101 | 107 | 101 | 0 | **100%** |
| DDOSICMP2 | ICMP_DDoS | 108 | 115 | 108 | 0 | **100%** |
| DDOSICMP3 | ICMP_DDoS | 109 | 114 | 109 | 0 | **100%** |
| DDOSSYN1 | SYN_DDoS | 101 | 106 | 101 | 0 | **100%** |
| DDOSSYN2 | SYN_DDoS | 106 | 111 | 106 | 0 | **100%** |
| DDOSSYN3 | SYN_DDoS | 107 | 114 | 107 | 0 | **100%** |
| DDOSTCP1 | TCP_DDoS | 100 | 107 | 100 | 0 | **100%** |
| DDOSTCP2 | TCP_DDoS | 107 | 114 | 107 | 0 | **100%** |
| DDOSTCP3 | TCP_DDoS | 108 | 116 | 108 | 0 | **100%** |
| DDOSUDP1 | UDP_DDoS | 101 | 108 | 101 | 0 | **100%** |
| DDOSUDP2 | UDP_DDoS | 109 | 115 | 109 | 0 | **100%** |
| DDOSUDP3 | UDP_DDoS | 106 | 112 | 106 | 0 | **100%** |
| ICMP1 | ICMP_DoS | 103 | 102 | 98 | 5 | 95.1% |
| ICMP2 | ICMP_DoS | 128 | 124 | 124 | 4 | 96.9% |
| ICMP3 | ICMP_DoS | 135 | 128 | 128 | 7 | 94.8% |
| PortScan1 | PortScan | 2 | 8 | 2 | 0 | **100%** |
| PortScan2 | PortScan | 4 | 8 | 4 | 0 | **100%** |
| PortScan3 | PortScan | 2 | 7 | 2 | 0 | **100%** |
| SYN1 | SYN_DoS | 123 | 125 | 121 | 2 | 98.4% |
| SYN2 | SYN_DoS | 124 | 124 | 121 | 3 | 97.6% |
| SYN3 | SYN_DoS | 123 | 123 | 120 | 3 | 97.6% |
| TCP1 | TCP_DoS | 129 | 124 | 124 | 5 | 96.1% |
| TCP2 | TCP_DoS | 119 | 123 | 119 | 0 | **100%** |
| TCP3 | TCP_DoS | 119 | 123 | 119 | 0 | **100%** |
| UDP1 | UDP_DoS | 122 | 128 | 122 | 0 | **100%** |
| UDP2 | UDP_DoS | 123 | 126 | 123 | 0 | **100%** |
| UDP3 | UDP_DoS | 123 | 128 | 123 | 0 | **100%** |
| UDP4 | UDP_DoS | 120 | 118 | 120 | 0 | **100%** |
| UDP5 | UDP_DoS | 122 | 117 | 122 | 0 | **100%** |

**Overall: 4,139 / 4,190 paired = 98.8% match rate.**

---

## 4. Per-Scenario Lag (Network start − Radio start)

Lag = `network_t0 − radio_t0`. Positive = network tap starts after radio begins; negative = reverse.

| Group | Lag range | Interpretation |
|---|---|---|
| Benign | +3.5 s to +10.5 s | Network tap starts a few seconds after UE association |
| DDoS (all families) | +2.1 s to +4.1 s | Very consistent; attack traffic begins quickly |
| DoS ICMP | −5.6 s to +2.4 s | Small negative lag for ICMP2/3 — harmless at 1-s join resolution |
| DoS SYN / TCP / UDP | −3.5 s to +3.5 s | Symmetric spread ≤ ±4 s |
| PortScan | +1.6 s to +2.6 s | Short captures, lag within expected range |

> [!NOTE]
> Lags stay within ±11 s across all scenarios. The 1-second equi-join absorbs this gracefully — only the edge seconds at the start/end of each capture are exposed, which explains the small `unmatched_net` counts.

---

## 5. Output Dataset Summary

### 5.1 Shape and Column Groups

```
multimodal_dataset.csv : 4,139 rows × 77 columns
```

| Column group | Count | Columns |
|---|---|---|
| Identifiers & labels | 6 | `window_id, scenario, family, mode, class_fm, is_attack` |
| Time | 9 | `timestamp_s, window_start_epoch_utc, window_start_utc, ...` |
| **Network features** | **29** | `pkts, bytes, mean_len, ..., top_dport_share` |
| **Radio KPI means** | **14** | `rsrp_mean, rssi_mean, ..., puschSnr_mean` |
| **Radio KPI stds** | **14** | `rsrp_std, rssi_std, ..., puschSnr_std` |
| **Radio bytes** | **2** | `dlBytes_per_s, ulBytes_per_s` |
| Diagnostic | 3 | `ue_count, diag_ttl_mean, diag_tcp_win_mean` *(exclude from models)* |
| **Total model features** | **59** | — |

### 5.2 Class Distribution

| Class | is_attack | Windows | Scenarios | Median ue_count |
|---|---|---|---|---|
| Benign | 0 | 1,184 | 6 | 2 |
| ICMP_DDoS | 1 | 318 | 3 | 2 |
| ICMP_DoS | 1 | 350 | 3 | 1 |
| PortScan | 1 | 8 | 3 | 1 |
| SYN_DDoS | 1 | 314 | 3 | 2 |
| SYN_DoS | 1 | 362 | 3 | 1 |
| TCP_DDoS | 1 | 315 | 3 | 2 |
| TCP_DoS | 1 | 362 | 3 | 1 |
| UDP_DDoS | 1 | 316 | 3 | 2 |
| UDP_DoS | 1 | 610 | 5 | 1 |

**Total: 4,139 windows across 10 classes, 35 scenarios.**

### 5.3 ue_count Distribution

`ue_count` perfectly separates DoS (1 UE) from DDoS (2–3 UEs) — it is a **diagnostic column only** and must not be used as a model feature:

| Class | ue_count=1 | ue_count=2 | ue_count=3 |
|---|---|---|---|
| Benign | 32 | 1,152 | 0 |
| ICMP_DDoS | 0 | 290 | 28 |
| ICMP_DoS | 350 | 0 | 0 |
| PortScan | 8 | 0 | 0 |
| SYN_DDoS | 0 | 314 | 0 |
| SYN_DoS | 362 | 0 | 0 |
| TCP_DDoS | 2 | 313 | 0 |
| TCP_DoS | 362 | 0 | 0 |
| UDP_DDoS | 0 | 278 | 38 |
| UDP_DoS | 610 | 0 | 0 |

### 5.4 Integrity Checks (All Passed ✅)

```
PASS  paired rows > 0
PASS  no null window_id
PASS  no null scenario
PASS  no null class_fm
PASS  no null timestamp_s
PASS  is_attack in {0, 1}
PASS  NaN in net feature cols
PASS  NaN in radio KPI mean cols
PASS  no negative ue_count
PASS  all classes represented
```

---

## 6. Restrictions & Modeling Guidance

### 6.1 PortScan — Severe Class Imbalance

> [!WARNING]
> PortScan has **only 8 paired windows** across 3 scenarios (2–4 per scenario). The network captures last 1–2.4 s, so almost no overlap seconds exist. PortScan **cannot be reliably classified** in a standard train/test split. Report its results separately and interpret with caution.

### 6.2 Train / Test Split — Use GroupKFold by Scenario

> [!CAUTION]
> Do **not** use random splits. Rows from the same scenario share the same timestamp range and traffic pattern. A random split leaks scenario identity into both train and test sets, inflating all metrics.

Use `GroupKFold` with `groups=df.scenario`:

```python
from sklearn.model_selection import GroupKFold

gkf = GroupKFold(n_splits=5)
for tr, te in gkf.split(df, groups=df.scenario):
    X_train = df.iloc[tr][FEATURE_COLS]
    X_test  = df.iloc[te][FEATURE_COLS]
```

### 6.3 Columns to Exclude from Models

| Column | Reason |
|---|---|
| `ue_count` | Directly encodes DoS (1 UE) vs DDoS (2–3 UEs) — data leakage |
| `ue_id`, `rnti_int`, `cellid` | Capture/UE identity, not traffic features |
| `diag_ttl_mean`, `diag_tcp_win_mean` | Diagnostic only, not cleaned features |
| `window_id`, `scenario`, `family`, `mode` | Identifiers |
| All time columns | Timestamp leakage |

The `multimodal_feature_columns.json` file encodes the exact 59-column feature list (`multimodal_feature_cols` key) that is safe to pass to any classifier.

### 6.4 Class Imbalance

Benign (1,184) is ≈2–4× larger than most attack classes. UDP_DoS (610) has 5 scenarios vs 3 for others. Consider:
- Stratified sampling by `class_fm` within GroupKFold folds
- Class-weighted loss in tree/neural models
- Reporting macro-averaged metrics alongside per-class results

### 6.5 Radio Zeros (Known Issue)

`pucchSnr`, `puschSnr`, `phr`, and `pcmax` have minimum = 0 in the raw radio data. Zero may mean "not reported" rather than a true measurement. The std columns (`_std`) will be 0 for single-UE scenarios (DoS) where only one UE exists per second — this is expected and valid.

### 6.6 ICMP_DoS — Lower Match Rate

ICMP1–3 show 94.8–96.9% match rates (worst of any class). The radio telemetry only covers 82% of ICMP1's seconds (known gap in raw data). The 7 unmatched ICMP3 windows are edge seconds that fall outside the radio span — they are excluded from the paired dataset, which is the correct behavior.

---

## 7. Output Files

| File | Description |
|---|---|
| `multimodal_dataset.csv` | Main paired dataset — 4,139 × 77 |
| `multimodal_feature_columns.json` | Column metadata and 59-feature list for downstream notebooks |
| `alignment_report.csv` | Per-scenario match stats |
| `multimodal_class_counts.png` | Bar chart of windows per class |
