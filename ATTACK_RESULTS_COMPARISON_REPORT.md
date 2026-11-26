# Attack Results Comparison Report

Comparison of `Results/inference_time_attacks/` (referred to as **original**) and `Results/inference_time_attacks_release/` (**release**).

Scope: read-only, static forensic audit. No notebook was executed, no model retrained, no experiment rerun, no package installed, no Git LFS installed, and no Git configuration, branch, staging area or history changed. No research file was deleted, moved, renamed or overwritten. The only file created by this task is this report.

## Overall verdict: EQUIVALENT

- **20 of 22** corresponding artifacts are byte-for-byte identical (SHA-256 match), including all seven CSVs, all 13 PNG figures, every aggregate metric table and the 256,376,704-byte per-window prediction file.
- The two non-identical files are `attack_configuration.json` and `attack_report.md`.
  - `attack_configuration.json`: parsed experimental content is **identical**; the release copy adds three publication-status keys (`run_status`, `verification_checks_passed`, `verified_outputs`). Removing those keys makes the parsed JSON objects exactly equal.
  - `attack_report.md`: only two lines differ. Spearman rho values are printed to three decimals in release instead of two (all release values round to the original two-decimal values), and the test-result wording is clarified from “not selected using test results” to “not selected using test performance; saved test predictions were used only for exact reproduction screening”.
- No numerical result, metric, figure, seed, attack definition, threshold, architecture, modality, condition or prediction differs between the two directories.
- Provenance of the release *notebook execution* is **inconclusive**: current embedded outputs indicate a completed run, but `RELEASE_NOTEBOOK_REVIEW.md` claims the notebook contained no stored outputs. See the notebook lineage section.

Therefore the directories are **scientifically equivalent**, not byte-identical. The release directory is the recommended authoritative publication copy because it carries explicit completion metadata and clarified wording; the original must still be preserved locally/archived as provenance until an explicit decision is made.

## 1. Method

- Enumerated all files in both directories and compared names, byte sizes and SHA-256 hashes.
- CSVs: compared hashes, shapes, column order, inferred dtypes, missing-value masks, duplicate-row counts and cell-by-cell numeric/object differences. The 2.65 M-row prediction file was streamed rather than fully materialised.
- JSON: parsed both files and recursively compared all keys and values, ignoring formatting.
- Markdown: line-level unified diff and manual interpretation of changed claims.
- PNG: parsed IHDR width/height and compared SHA-256 hashes.
- Experiment consistency: extracted configurations from JSON/CSV artifacts and cross-checked clean probabilities against `Results/deep_learning_comparison/test_predictions.csv`.
- Notebooks: parsed JSON source cells and embedded outputs only; no cell was executed.

## 2. File-by-file comparison

A = `Results/inference_time_attacks/`, B = `Results/inference_time_attacks_release/`.

| File | A bytes | B bytes | Byte-identical | Structural / content comparison | Conclusion |
|---|---:|---:|---|---|---|
| `attack_configuration.json` | 44,910 | 45,823 | No | Parsed content identical after removing B-only keys `run_status="completed"`, `verification_checks_passed=38`, `verified_outputs` (22 filenames). All experimental fields equal. A SHA-256 `6174397990954D5B51A09940AD31A3639FEDAE2B4A6073D37F4B56DD0095D685`; B SHA-256 `100556499E1BB992694B24D529F609280D2BC60F00F48CBAE20CCE1B3F84A6A5`. | Equivalent; release adds completion metadata only |
| `attack_predictions.csv` | 256,376,704 | 256,376,704 | Yes | 2,646,600 rows x 13 columns; 0 duplicate rows; 0 empty fields; identical header/order/dtypes. SHA-256 `0D3D449403CF1D21592523B3536AEB7F4941D9BB49CD9B87E777CBF5904DFCCA` in both. | Identical |
| `attack_report.md` | 14,192 | 14,278 | No | Two changed lines (153 and 163): rho precision and test-result wording. No changed conclusion. A SHA-256 `F5EFE68A1FF6A776430F6EA58D99872173A279855F5574BD5E375FDC40CBA2C4`; B differs only by 86 bytes. | Equivalent; release wording is more precise |
| `attack_results_per_seed.csv` | 1,914,892 | 1,914,892 | Yes | 3,300 x 46; identical columns/dtypes; 0 missing, 0 duplicates; 0 differing cells across 39 numeric and 7 object columns. | Identical |
| `attack_results_summary.csv` | 550,420 | 550,420 | Yes | 660 x 54; identical columns/dtypes; 0 missing, 0 duplicates; 0 differing cells across 48 numeric and 6 object columns. | Identical |
| `clean_baseline_metrics.csv` | 15,732 | 15,732 | Yes | 90 x 17; identical columns/dtypes; 0 missing, 0 duplicates; 0 differing cells. | Identical |
| `clean_reproduction_check.csv` | 3,031 | 3,031 | Yes | 90 x 7; all 90 rows `OK`, `max_abs_diff=0.0`, `pred_flips_vs_saved=0`, `n_saved=802`; 0 duplicates. | Identical |
| `fig_clean_vs_manipulated_macro_f1.png` | 70,115 | 70,115 | Yes | 2849x497; SHA-256 `F38DF4BDCEFA07930D9D30C9ADD94C5E6D83676D389CA178958CDD22D0670D97`. | Identical |
| `fig_evasion_success_rate.png` | 37,087 | 37,087 | Yes | 1419x515; SHA-256 `320A74263D2C13550B7E6FFC7FDDD382F2F63B4884E7EC45408024B0D1750BA5`. | Identical |
| `fig_fnr_clean_vs_manipulated.png` | 64,752 | 64,752 | Yes | 2849x497; SHA-256 `28ACED04C5E2019CEB540C0F660A16A835C9546344ED83F8B2CB757D8C5C688D`. | Identical |
| `fig_fpr_clean_vs_manipulated.png` | 71,131 | 71,131 | Yes | 2849x497; SHA-256 `854EDE666A3F89413DE11C3F9DF943BCED100E5BF31FDF088ADCA9ECD857D51E`. | Identical |
| `fig_heatmap_delta_macro_f1.png` | 202,390 | 202,390 | Yes | 3059x485; SHA-256 `5FBEFC95C049D43865D3E5F8CE2BA9079D71F6951045FD0946122FE9AD6E1FCC`. | Identical |
| `fig_heatmap_esr.png` | 175,583 | 175,583 | Yes | 3049x485; SHA-256 `C604B954D8C0F94E098B0FCAC4230F5C92ABE5E4E677238FB1EC38A25E232DD5`. | Identical |
| `fig_heatmap_macro_f1.png` | 221,799 | 221,799 | Yes | 3059x485; SHA-256 `A8A53A4B23A64A2B146BC0C96C917D6B3E0372210914CBC13303755692DF635C`. | Identical |
| `fig_multimodal_sensor_specific.png` | 124,951 | 124,951 | Yes | 2189x872; SHA-256 `4C31562C3C7818EA85A160A5D7251F238E2B3B855679FF9DCEB50B5202AA71B5`. | Identical |
| `fig_network_vs_radio_manipulation.png` | 41,225 | 41,225 | Yes | 1419x516; SHA-256 `A2F42708640113A1BD242754DFE0AC0302B1485ADFA4EDBA9925268C7AF2BF72`. | Identical |
| `fig_per_seed_variability.png` | 132,349 | 132,349 | Yes | 2849x497; SHA-256 `C6C4A8B503940B0FDA1390855B026FE3BFE13652E4677AAFE438D2901D6DDE7D`. | Identical |
| `fig_sensor_dropout_macro_f1.png` | 70,832 | 70,832 | Yes | 2849x476; SHA-256 `D48F1431646DE3B2DA449AF9DF63B5BE4C27FEAF0D1141DCB7D512B81E83A9ED`. | Identical |
| `fig_severity_vs_attack_recall.png` | 380,065 | 380,065 | Yes | 2630x1622; SHA-256 `06C17F259F15B277CE307DDCB4E3B2C76E15EDFDE061D0A4765CF4B084322724`. | Identical |
| `fig_severity_vs_macro_f1.png` | 452,455 | 452,455 | Yes | 2630x1622; SHA-256 `B0862CB9B953F54F79F6A96524960C1CA09EF9FAA728E4C3F49DCF8E5A4A5030`. | Identical |
| `robustness_ranking.csv` | 8,167 | 8,167 | Yes | 30 x 19; identical columns/dtypes; 0 missing, 0 duplicates; 0 differing cells. | Identical |
| `scenario_level_attack_results.csv` | 4,091,907 | 4,091,907 | Yes | 23,100 x 20; identical columns/dtypes; identical NaN mask (3,300 undefined `esr` cells in both, at identical positions); 0 duplicates; 0 differing values where defined. | Identical |

## 3. Numerical differences

### 3.1 Between the two directories

None. Every numeric cell in every CSV pair is identical, and all PNG bytes are identical. The only numeric-looking difference is report formatting:

| Report line | Original | Release | Interpretation |
|---|---|---|---|
| 153, Spearman rho (10 values) | 2 decimals: 0.77, 0.59, 0.71, 0.50, 0.77, 0.82, 0.94, 0.79, 0.66, 0.33 | 3 decimals: 0.771, 0.586, 0.714, 0.499, 0.771, 0.816, 0.943, 0.792, 0.657, 0.329 | Every release value rounds to the corresponding original value at 2 decimals; no claim changes. Release is more precise. |
| 163, test-result wording | “No attack, severity, threshold or model was selected using test results.” | “No model, attack, severity or threshold was selected using test performance; saved test predictions were used only for exact reproduction screening.” | Clarification consistent with `FINAL_NOTEBOOK_REVIEW.md` finding A-09; no result change. |

### 3.2 Cross-check against upstream clean predictions

- `Results/deep_learning_comparison/test_predictions.csv` contains 72,180 test rows (6 architectures x 3 modalities x 5 seeds x 802 windows).
- All 2,646,600 rows in each directory's `attack_predictions.csv` map to one of those keys: 0 missing keys.
- `clean_prediction` in the attack tables equals the upstream `y_pred` in **2,646,600 / 2,646,600** rows.
- `attacked_prediction` equals `(attacked_probability >= 0.5)` in all rows, and `clean_prediction` equals `(clean_probability >= 0.5)` in all rows, confirming the fixed 0.5 threshold.
- `clean_probability` in the attack tables is written with about 7 significant digits, while upstream `y_probability` stores full precision. Maximum absolute difference is `4.9999e-08` (well below the documented `1e-6` reproduction tolerance), with 0 threshold flips. This is a serialization-precision effect, not a scientific discrepancy.
- `clean_reproduction_check.csv` records 90/90 `OK`, `max_abs_diff = 0.0`, `pred_flips_vs_saved = 0`, `n_saved = 802`, identical in both directories.

## 4. Experiment consistency

Both directories use the same experimental design. Values below were extracted from the parsed configurations and CSVs; because the underlying CSVs are byte-identical, these values are shared.

| Property | Verified value |
|---|---|
| Architectures | `cnn`, `ft_transformer`, `gru`, `lstm`, `mlp`, `resmlp` |
| Modalities | `network`, `radio`, `multimodal` |
| Conditions | `network:network`, `radio:radio`, `multimodal:network`, `multimodal:radio`, `multimodal:both` (`attack_target` values `network`, `radio`, `both` combined with model modality) |
| Seeds | `101, 202, 303, 404, 505` (5 per checkpoint; `n_seeds = 5` in summaries) |
| Attack seed | `20260` |
| Attack IDs | 22: `gaussian_noise|0.1/0.25/0.5/1.0`; `bias_pos|+0.5/+1/+2`; `bias_neg|-0.5/-1/-2`; `scaling|x0.5/x2/x4`; `feature_corruption|10%/25%/50%`; `sensor_dropout_partial|25%/50%`; `sensor_dropout_complete|100%`; `combined|low/medium/high` |
| Attack families | gaussian noise, positive bias, negative bias, scaling, feature corruption, partial dropout, complete dropout, combined |
| Combined order | `bias -> feature corruption -> additive Gaussian noise` |
| Space | `standardised features z=(x-mean)/scale using the saved training statistics` |
| Feature blocks | network 29 features, radio 32 features, multimodal boundary `network [0,29]`, `radio [29,61]` |
| Threshold | `0.5`, confirmed from config and from prediction labels |
| Reproduction tolerance | `1e-6` with zero threshold flips required |
| Test partition | 802 windows from 7 scenarios; identical `window_id` sets in both prediction files |
| Evaluation metrics | Identical column sets and values in all metric CSVs: accuracy, precision, recall, F1, macro-F1, ROC-AUC, PR-AUC, FPR, FNR, flip rate, probability shifts, ESR, deltas and confusion counts |
| Disclaimer | Synthetic, label-independent inference-time stress tests in standardised space; not validated physical 5G/O-RAN attacks; no model declared robust |

Both configurations also record the same target mapping (`network_model -> network`, `radio_model -> radio`, `multimodal_model -> network/radio/both`) and the same affected-feature lists. The release copy additionally records `run_status="completed"`, `verification_checks_passed=38` and a 22-file `verified_outputs` list.

## 5. Notebook lineage

### 5.1 Current notebook states

| Notebook | Code source SHA-256 prefix | Non-empty code cells | Stored outputs | Executed cells | Notes |
|---|---|---:|---:|---:|---|
| `06_inference_time_telemetry_attacks.ipynb` | `22cec4d715e5e166` | 17 | 50 | 17 | Original; stale outputs; known audit findings F-01..F-14. Output contains a redacted personal temporary kernel path in a DtypeWarning. |
| `06_inference_time_telemetry_attacks_reviewed.ipynb` | `fa522adbda3f7533` | 17 | 50 | 17 | Intermediate; adds bytecode/determinism fixes but keeps stale outputs and original output dir. Same personal temp path in output. |
| `06_inference_time_telemetry_attacks_final.ipynb` | `dd5d3270da1cb0b3` | 17 | 50 | 17 | Applies A-01..A-08 style fixes from `FINAL_NOTEBOOK_REVIEW.md`; still writes to original dir, overwrites predictions, and has stale outputs with personal temp path. |
| `06_inference_time_telemetry_attacks_release.ipynb` | `a2e936423a39f128` | 17 | **49** | **17** | Latest reviewed source; writes to release dir, CPU-pinned, strict determinism, no-overwrite guard, clarified wording, NaN-safe reporting, `run_status` lifecycle. **Currently has stored outputs despite the review report saying it has none.** Outputs show 90/90 reproduction and `ALL 38 CHECKS PASSED`, with no personal-path string detected. |

### 5.2 Latest reviewed version and safest publication candidate

- `AUDIT_REPORT.md` (modified 08:23) reviews the original notebook.
- `FINAL_NOTEBOOK_REVIEW.md` (08:41) reviews the `final` notebook.
- `RELEASE_NOTEBOOK_REVIEW.md` (08:57) reviews the `release` notebook and documents fixes A-01..A-10.
- The `release` notebook file was last modified at 09:06, after its review, and its embedded outputs show execution counts 1-17. The review's statement “No stored outputs or execution counts remain in the release notebook” is therefore **no longer accurate for the current file**. The release configuration was written at 09:05, consistent with a post-review execution, but exact authorship/timing beyond file timestamps cannot be verified.

**Recommendation:** `06_inference_time_telemetry_attacks_release.ipynb` is the safest *source* publication candidate because it contains all documented fixes, uses a fresh output directory, and its outputs do not expose a personal username/path. Before committing, decide whether to keep its embedded outputs (they are consistent with release artifacts) or clear them; the older notebooks should not be published with their current outputs because those outputs contain personal Windows paths.

### 5.3 Did older versions contain important methodology absent from release?

No scientific change was lost. Static cell comparison shows:

- Experiment execution cells (network, radio, multimodal conditions, aggregation, plotting) are byte-identical across all four notebooks.
- Cell 14 (attack grid / perturbation helpers) changed only through defensive finite-value and metadata/assertion fixes; the 22 attack IDs and parameters are unchanged.
- Release vs final source differences are limited to: output directory switch; CPU pinning and strict determinism; renamed reproduction-failure flag; no-overwrite guard; metadata-derived feature counts; flip-count display; `run_status`/`verified_outputs` lifecycle; NaN-safe report formatting; and clarified test-performance wording.
- Cell 0 and cell 31 wording changes clarify the threat model, run instructions and limitations; they do not add or remove experimental results.
- Older notebooks' unique content is stale embedded output (prior-run evidence, not reproducible proof) and unfixed defensive weaknesses. None should be treated as a more authoritative experiment source.
- `04_baseline_models.ipynb` and `05_deep_learning_comparison.ipynb` contain embedded outputs with personal Linux and Windows paths respectively; these are publication hygiene issues independent of the attack-result equivalence.

## 6. Authoritative results directory recommendation

Use `Results/inference_time_attacks_release/` as the **publication-facing authoritative directory**:

- It is the only directory with explicit completion metadata (`run_status`, 38 checks, 22 verified outputs).
- Its generated report has the clarified test-performance wording and more precise rho values.
- Its notebook source is the reviewed release candidate and its output directory is protected against accidental overwrite.
- All scientific content is identical to the original, so no result is lost by designating release as primary.

Keep `Results/inference_time_attacks/` intact locally and archive it outside GitHub as provenance. Do not delete either directory until an explicit decision is made and the external archive is verified.

## 7. GitHub storage recommendation

### Option evaluation

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| Keep one copy in Git LFS | Raw predictions remain versioned next to code; one duplicate avoided | 244.5 MiB blob in LFS storage and history; requires LFS install/config and client setup; slower clones; LFS quota/cost; not installed here | Acceptable only if a journal/coauthor requires versioned raw predictions and quota is confirmed |
| Store detailed predictions as an external downloadable research artifact | Keeps Git small; academic norm (DOI-based archive); one canonical copy; checksum can be recorded in repo | Requires manual upload and link maintenance; external availability depends on archive | **Recommended** |
| Exclude detailed predictions from GitHub, retain aggregates + reproducibility docs | Minimal, fast repository; aggregate tables and figures already sufficient for reported claims | Loses per-window auditability unless an external artifact exists | Recommended **in combination with** the external-artifact option, not alone |

**Recommendation:** publish code, dataset descriptors, split, preprocessing manifests, checkpoints, aggregate result tables, figures, configuration, reports and reproducibility instructions in GitHub. Publish one canonical `attack_predictions.csv` as an external research artifact with a DOI/permanent URL and record its SHA-256 (`0D3D449403CF1D21592523B3536AEB7F4941D9BB49CD9B87E777CBF5904DFCCA`) and byte size (256,376,704) in the README. Do **not** commit either 244.5 MiB copy. If LFS is later mandated, track only one copy and only after explicit approval; do not install LFS in this task.

### Classification

**A. Must be committed to GitHub (minimal professional core)**

- `README.md`, `.gitignore`, `GITHUB_PREPARATION_REPORT.md`, `ATTACK_RESULTS_COMPARISON_REPORT.md`.
- `04_baseline_models.ipynb`, `05_deep_learning_comparison.ipynb`, `06_inference_time_telemetry_attacks_release.ipynb` — **subject to output-sanitisation decision** for notebooks containing personal paths in outputs.
- `Multimodal Datasets/`, `Network Dataset/`, `Radio Dataset/` (all 31 files: data CSVs, feature manifests, cleaning/alignment notebooks and reports).
- `Models/deep_learning/comparison/dl_comparison_models.py` and all 18 `.pt` checkpoints.
- `Results/split_manifest.csv`, `Results/baseline_*`, `Results/*_test_predictions.csv`, `Results/tuning_log.csv`, `Results/Models/*.pkl`.
- `Results/deep_learning_comparison/` aggregate CSVs, figures, `configuration_used.json`, `feature_names_and_preprocessing.json` and report.
- `Results/inference_time_attacks_release/` **excluding** `attack_predictions.csv`: `attack_configuration.json`, `attack_report.md`, 6 aggregate CSVs and 13 PNGs.
- `AUDIT_REPORT.md`, `FINAL_NOTEBOOK_REVIEW.md`, `RELEASE_NOTEBOOK_REVIEW.md` — retain as audit trail, with this report clarifying the stale release-notebook output claim.

**B. Should be committed if storage permits**

- `Results/deep_learning_comparison/run_cache/*.pt` (90 files, 15.20 MiB) — training-run provenance; useful but not strictly required because final checkpoints are already committed.
- `Results/inference_time_attacks/` aggregate files (21 small files, excluding its prediction CSV) — duplicate of release aggregates; archive/commit only if preserving the original provenance in-repo is valued.
- A short `data Availability` section or `CITATION.cff` describing the external prediction artifact and checksum (to be created manually after the artifact exists).

**C. Should be archived outside GitHub**

- `Results/inference_time_attacks/attack_predictions.csv` — 244.5 MiB duplicate; archive or discard after one canonical external copy is verified.
- `Results/inference_time_attacks_release/attack_predictions.csv` — 244.5 MiB canonical raw artifact; host externally with DOI/checksum, not in Git.
- `06_inference_time_telemetry_attacks.ipynb`, `06_inference_time_telemetry_attacks_reviewed.ipynb`, `06_inference_time_telemetry_attacks_final.ipynb` — provenance versions; archive externally, especially because their outputs contain personal Windows paths.
- `Results/inference_time_attacks/` (all 22 files) if the release directory becomes authoritative — archive as a historical snapshot.
- `Results/deep_learning_comparison/run_cache/` if the 15.2 MiB is unwanted in Git.

**D. Can be safely removed after explicit approval (from GitHub/staging, not locally in this task)**

1. `Results/inference_time_attacks/attack_predictions.csv` — byte-identical duplicate of the release copy; remove from any publication staging after one external artifact is verified.
2. `Results/inference_time_attacks_release/attack_predictions.csv` — remove from Git publication entirely if the external-artifact option is chosen; keep locally until the DOI/checksum is recorded.
3. `Results/inference_time_attacks/` (all 22 files) — only after release is confirmed authoritative and the directory is archived externally.
4. `06_inference_time_telemetry_attacks.ipynb`, `06_inference_time_telemetry_attacks_reviewed.ipynb`, `06_inference_time_telemetry_attacks_final.ipynb` — only after archiving and deciding that the release notebook alone represents the experiment.
5. Stored outputs/execution counts inside committed notebooks — not separate files and not modified here; requires explicit approval before clearing.

Never remove datasets, checkpoints, split manifests, feature manifests, configuration JSONs or aggregate result tables.

## 8. Inconclusive items

- The exact authorship and execution time of the release notebook's embedded outputs cannot be verified from static files; mtimes only show the notebook was modified after its review.
- It cannot be determined whether the byte-identical `attack_predictions.csv` files were written by one execution and copied, or by two executions producing identical output. Both explanations fit the evidence.
- Whether any unrecorded human decision influenced attack selection outside the notebooks cannot be verified.
- Fresh numerical reproduction was not attempted; agreement is established from stored artifacts and static checks only.
- No external artifact DOI/URL exists yet; none is invented here.

## 9. Actions taken

- No research file was deleted, moved, renamed, overwritten, staged, committed or pushed.
- No Git configuration, branch, history, notebook, dataset, checkpoint or result was modified.
- Git LFS was not installed or configured.
- This report is the only new file created.
