# Network Data Report - NetsLab-5GORAN-IDD (Version 1)

**Project:** *When One Sensor Lies* - robust multimodal intrusion detection in 5G Open RAN
**Part:** 1 - dataset investigation and network preprocessing
**Produced by:** `01-network-packet-level-analysis.ipynb` (investigation) and `02a_network_windows_cleaning_augmentation.ipynb` (cleaning, window dataset, augmentation)
**Source of every number below:** the executed outputs of those two notebooks (Kaggle run, 35/35 packet CSVs found).

---

## 1. Summary

- The network side of V1 holds **28,803,972 packets** in **35 scenarios** (6 Benign, 29 attack). All work is done from the per-scenario **packet CSVs**; the `.db` file holds flows, not packets.
- The modelling unit is the **1-second window**, aligned to whole UTC seconds so it can be joined to the 1 Hz radio telemetry. This gives **4,190 clean real windows** (1,189 Benign, 3,001 attack; ratio 2.52 : 1).
- **2,621,848 exact duplicate packets (9.1 %)** were removed; no timestamp failed to parse.
- Windows are described by **29 features** with no identifiers, no time, no `tcp.stream` and no tool fingerprints (TTL, TCP window).
- **Augmentation** (phase-shifted re-windowing) was built and tested. It gave **no measurable gain** over class weights in a scenario-held-out check, so the recommended default is real windows + class weights; the augmented rows are kept as an optional ablation.
- Three things need care downstream: **Benign comes from only 6 captures**, **PortScan has only 8 windows (6 of them partial)**, and the **time-zone label is confounded with the attack type** (section 6).

---

## 2. Why windows, not flows or packets

| Unit | Benign | Attack | Ratio | Problem |
|---|---|---|---|---|
| Packets | 1,606,805 | 27,197,167 | 16.9 : 1 | 28.8 M rows; non-monotonic timestamps (462,955 backward steps); GTP-tunnelled multi-valued header fields in 19.8 M rows; `tcp.stream` restarts per capture; one packet says little about a flood |
| Flows | 92 | ~204,700 | ~2,200 : 1 | Floods collapse into a handful of rows (e.g. SYN1 = 3 flows holding 3.9 M packets); 22 of 35 captures have <= 12 flow rows; the flow CSV schema has no timestamp column, so flows cannot be time-aligned with radio data |
| **1-s windows** | **1,201** (before cleaning) | **3,053** | **2.5 : 1** | none of the above; matches the 1 Hz radio data |

The flow files were kept only as a cross-check (flow rows in the files sum to the 204,775 rows of the flow database).

---

## 3. Cleaning

| Step | Rule | Result |
|---|---|---|
| Read | one streaming pass per capture, 400,000-row chunks | 28,803,972 packets read in 796 s |
| Time parsing | `frame.time` parsed with its time-zone label | 0 unparseable rows; labels seen: `GMT`, `IST` |
| Duplicates | exact duplicate rows over all 23 packet columns, removed per capture | **2,621,848 removed (9.1 %)** |
| Empty seconds | no packets -> no window row | benign captures contain 302 idle seconds (notebook 01) |
| Partial edge windows | dropped, except in captures with fewer than 10 full windows | 4,254 -> **4,190** windows (64 dropped = 2 per capture in the 32 long captures) |
| Hard checks | no NaN / inf / negative values; fractions in [0, 1]; flag fractions <= TCP fraction; min <= mean <= max length; unique window ids; pkts > 0 | **all passed (0 violations)**; no constant feature |

**Duplicate pattern.** Duplicates are not random. About **20 %** of the rows are exact duplicates in TCP1-3, UDP1-5, DDoS-UDP1-2, ICMP2-3 and PortScan1-3 (19.8-20.0 %), 14.3 % in DDoS-UDP3, and 2-12 % in the rest. In contrast DDoS-TCP2/3, SYN1-3 and DDoS-ICMP1-3 have none. Several exports also end at round row counts (DDoS-TCP2 = 200,000; DDoS-TCP3 = 400,000; DDoS-UDP2 = 1,000,000; DDoS-UDP3 = 350,000), which suggests capped or truncated exports. This was not verified against the dataset authors; it is reported as an observation.

**Note on notebook 01.** Notebook 01 counted duplicates on five columns only (`frame.time, ip.id, ip.src, ip.dst, frame.len`), so its counts differ for the Benign captures (e.g. Benign1: 854 there, 347 here). The stricter all-column definition is used here; for attack captures the two agree almost exactly.

---

## 4. The window dataset

**Definition.** Windows are 1 s long and start on whole UTC seconds (`window_start_epoch_utc`). Packets are binned into 0.25 s sub-bins, which are then added up to a window; this is insensitive to the out-of-order timestamps. Protocol comes from `frame.protocols` (innermost of TCP / UDP / ICMP), because `ip.proto` of a GTP packet starts with the outer UDP value. Tunnelled header fields use the **inner** value (`FIELD_PICK = "last"`).

**Features (29, raw values, no scaling).**

| Group | Features |
|---|---|
| Volume | `pkts`, `bytes` |
| Size | `mean_len`, `std_len`, `min_len`, `max_len` |
| Burstiness | `burst_cv` (CV of the four 0.25 s packet counts) |
| Protocol mix | `tcp_frac`, `udp_frac`, `icmp_frac`, `other_frac`, `gtp_frac` |
| TCP flags (fraction of packets) | `syn_frac`, `synack_frac`, `rst_frac`, `fin_frac`, `ackonly_frac` |
| Payload | `tcp_payload_mean`, `udp_len_mean` |
| Endpoint spread | `n_src`, `n_dst`, `n_sport`, `n_dport`, `ent_src`, `ent_dst`, `ent_dport`, `top_src_share`, `top_dst_share`, `top_dport_share` |

**Excluded from model inputs (leakage).** IP addresses, port identities, absolute time, `tcp.stream` (restarts per capture, a scenario id), TTL and TCP window size (tool / OS fingerprints; e.g. the most common TCP window is 501/509 in Benign, 0 in TCP-DoS, 1480 in several DDoS captures). TTL and window are kept only as `diag_ttl_mean` and `diag_tcp_win_mean` in `network_clean.csv`.

---

## 5. Class distribution and typical profiles (real windows)

| Class | Windows | Captures | Median pkts/s | Median mean length (B) | TCP | UDP | ICMP | SYN | Median `n_src` | Median `n_dport` |
|---|---|---|---|---|---|---|---|---|---|---|
| Benign | 1,189 | 6 | 23 | 154 | 1.00 | 0.00 | 0.00 | 0.00 | 4 | 2 |
| ICMP DoS | 366 | 3 | 12,640 | 344 | 0 | 0 | 1.00 | 0 | 4 | 1 |
| ICMP DDoS | 318 | 3 | 1,909 | 88 | 0 | 0 | 1.00 | 0 | 2 | 1 |
| SYN DoS | 370 | 3 | 31,764 | 100 | 1.00 | 0 | 0 | 1.00 | 1 | 1 |
| SYN DDoS | 314 | 3 | 7,068 | 80 | 1.00 | 0 | 0 | 0.56 | 5 | 3 |
| TCP DoS | 367 | 3 | 392 | 83 | 1.00 | 0 | 0 | 0.50 | 4 | 50 |
| TCP DDoS | 315 | 3 | 2,510 | 100 | 1.00 | 0 | 0 | 0.00 | 2 | 1 |
| UDP DoS | 627 | 5 | 3,694 | 1,090 | 0 | 1.00 | 0 | 0 | 4 | 1 |
| UDP DDoS | 316 | 3 | 2,904 | 66 | 0 | 1.00 | 0 | 0 | 4 | 1 |
| PortScan | **8** | 3 | 4,144 | 85 | 0.003 | 0.99 | 0 | 0 | 4 | 992 |
| **Total** | **4,190** | 35 | | | | | | | | |

Binary: 1,189 Benign (28.4 %) vs 3,001 attack windows = **2.52 : 1**. At window level Benign is the largest single class; the real minority is **PortScan**.

Observations:
- Benign is **two traffic regimes**: Benign1-3 are light (median ~10-30 pps), Benign4-6 are heavy with bursts up to ~27-31k pps, which overlaps the volume of several DDoS runs. Volume alone cannot separate Benign from DDoS; protocol mix, flags and endpoint spread do.
- The PortScan windows are almost entirely UDP (median `udp_frac` 0.99) with ~990 distinct destination ports per window.

---

## 6. Time and alignment (for Part 2)

- Windows start on whole UTC seconds, so they pair naturally with 1 Hz radio data. `window_start_epoch_utc` uses the assumed offsets `GMT/UTC = 0` and **`IST = +1 h`**. The +1 h value came from the earlier radio / packet overlap check; real IST would be +5 h 30 min. **This is unverified and must be confirmed by the alignment notebook.** `window_start_wall_epoch` holds the timestamp as written in the file so the offset can be re-derived.
- **The time-zone label is confounded with the attack type.** `IST` captures: all 6 Benign and all 12 DDoS captures. `GMT` captures: all DoS and all PortScan captures. Two consequences: (a) `tz_label`, the offset and absolute time must never be model inputs (they would separate DoS from DDoS/Benign); (b) a wrong offset would shift two of the three groups, so the alignment check should be done per group.
- Benign was captured on a single day (2025-04-14), different from the attack days (notebook 01); absolute time would leak the label.
- A **missing second means no packets**, not missing data. Benign captures contain 302 such seconds. When joining to radio data, absent network windows should be treated as zero traffic, not dropped as unmatched.
- Radio telemetry covers the same 1 Hz grid only for the whole-second windows; **augmented windows have no radio partner** (section 7).

---

## 7. Augmentation

**Method.** Phase-shifted re-windowing: the same real packets are re-cut into 1-s windows starting 0.25 / 0.5 / 0.75 s after the whole-second grid, for Benign and PortScan only. Every row is a real window; no feature value is invented. Rows are flagged `is_synthetic = 1` with `aug_phase_s`. This was chosen over range sampling, SMOTE or generative models because Benign is two regimes whose peaks overlap DDoS volume, which independent per-feature sampling would mix up.

| Family | Real windows | Pool available | Target | Added | After |
|---|---|---|---|---|---|
| Benign | 1,189 | 3,544 | 3,001 (1 : 1 with attack) | 1,812 | 3,001 |
| PortScan | 8 | 5 | 150 | 5 | 13 |

`network_features.csv` therefore has 6,007 rows (4,190 real + 1,817 augmented).

**Does it help?** Random Forest (`class_weight="balanced_subsample"`), scenario-held-out GroupKFold, synthetic rows only in training folds:

| Training data | Family macro-F1 | Attack-vs-benign balanced acc. | Benign recall | PortScan recall |
|---|---|---|---|---|
| Real only | 0.942 | 0.996 | 0.992 | 0.750 |
| Real + augmented | 0.942 | 0.997 | 0.993 | 0.750 |

The differences (<= 0.001) are within what one run on 6 benign scenarios can resolve. **Conclusion: augmentation is not needed here.** Use real windows with class weights as the default; keep the augmented rows only for an ablation.

**Rules if they are used:** training folds only; keep all rows of a `scenario` on one side of the split; never in validation or test; network-only models only. Augmented windows overlap their parent window by 75 %, so they are correlated, not independent samples. Re-windowing cannot fix PortScan: its captures last 0.98-2.4 s.

---

## 8. Limitations and risks

1. **Benign comes from 6 captures** (two regimes). Cross-scenario results on Benign rest on 6 groups; report per-scenario results and avoid strong claims about benign generalisation.
2. **PortScan has 8 windows and 6 of them are partial.** The three captures last 1.38, 2.42 and 0.98 s, so only two whole-second windows are fully covered (both in PortScan2); the other six cover as little as 0.02 s. (Derived from the capture start/end times in notebook 01.) Count-based features of those windows (`pkts`, `bytes`, `n_*`) are under-estimated. The 0.75 PortScan recall (6 of 8 windows) is not a reliable estimate. Treat PortScan separately, or merge it for macro-F1 and say so.
3. **Endpoint-spread features reflect the testbed topology**: only a few distinct attackers (median `n_src` 1-5 in all attack classes). They separate attack types here but may not transfer to other networks.
4. **Duplicate and capped exports** (section 3): the cleaned counts are what the dataset gives after removing exact duplicates; the authors' intended counts are unknown.
5. **Time-zone confound and unverified IST offset** (section 6).
6. **Version 1 is flooding-centred** (DoS/DDoS plus one scan type); conclusions should not be extended to other attack categories.
7. Window features depend on the 1-s window length and on the inner-header choice for tunnelled packets (`FIELD_PICK`).

---

## 9. Files and columns

| File | Content |
|---|---|
| `network_clean.csv` | 4,190 real windows x 45 columns, **time-ordered**. Identifiers and labels (`window_id, scenario, family, mode, class_fm, is_attack`), time (`window_start_epoch_utc, window_start_utc, window_start_wall_epoch, tz_label, tz_offset_assumed_s, t_rel_s`), `coverage_s`, `is_partial`, the 29 features, and `diag_ttl_mean`, `diag_tcp_win_mean` (not for models) |
| `network_features.csv` | 6,007 rows x 40 columns, **shuffled** (seed 42): `window_id, scenario, family, mode, class_fm, is_attack, is_synthetic, aug_phase_s, window_start_epoch_utc, t_rel_s, is_partial` + the 29 features |
| `network_feature_columns.json` | feature list, metadata list, diagnostic columns and all settings used |
| `network_scan_summary.csv` | per-capture rows read, duplicates removed, time-zone label and offset |
| `network_window_class_counts.png` | class counts before / after augmentation |

**Labels.** `is_attack` (binary), `family` (6 classes: Benign, ICMP, PortScan, SYN, TCP, UDP), `class_fm` (10 classes: family + DoS/DDoS, PortScan as its own). Original scenario labels are preserved; `window_id = <scenario>@<sub-bin index>` is unique and is the key for joining with radio windows.

**Settings used.** 1 s window, 4 sub-bins per second, `DEDUP = True`, `FIELD_PICK = "last"`, `TZ_OFFSETS = {GMT: 0, UTC: 0, IST: 3600}`, `MIN_FULL_WINDOWS = 10`, `AUG_FAMILIES = [Benign, PortScan]`, `BENIGN_TO_ATTACK = 1.0`, `FAMILY_FLOOR = 150`, seed 42.

**Using them.**
1. Split the real windows by `scenario` (grouped folds), never randomly.
2. Use `FEATURE_COLS` only as model inputs; keep `diag_*`, time and `tz_label` out.
3. Prefer class weights; add `is_synthetic == 1` rows only to training folds if testing augmentation.
4. Report macro-F1, PR-AUC and false-positive rate on real windows, per scenario where possible.
5. Paired (multimodal) experiments use `network_clean.csv` / `is_synthetic == 0` rows only.
