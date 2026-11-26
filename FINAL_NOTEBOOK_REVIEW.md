# Final Notebook Audit — `06_inference_time_telemetry_attacks_final.ipynb`

## Overall verdict

**READY AFTER FIXES**

The notebook is structurally valid, syntactically clean, and contains all requested corrections from the prior review. Static inspection confirms the checkpoint, preprocessing, reproduction-gate, finite-value, metadata-boundary, attack-evaluation, metric, and verification logic is substantially correct. However, several medium/low-severity issues remain: a misleading reproduction-failure flag, a failure-mode `idxmin`/`idxmax` crash, stale embedded outputs with a broken execution-count sequence, destructive overwrite behavior for existing attack results, and a scientific-wording nuance around test-set-based reproduction gating. These should be fixed before a fresh authoritative run.

## Executive summary

- **Static structure:** 36 cells (19 Markdown, 17 non-empty code cells). JSON parses successfully and all 17 code cells compile with Python `compile()`. No notebook cell was executed for this audit.
- **Corrections present:** finite checks, strict reproduction gate (tolerance **and** zero threshold flips), metadata-derived feature boundaries, prediction shape/finite assertions, `CUBLAS_WORKSPACE_CONFIG` before `import torch`, bytecode-write prevention, removal of the tautological output-directory check, inclusion of `clean_reproduction_check.csv` in expected outputs, and consistent `thr` use in `scenario_rows()`.
- **Existing evidence inspected statically:** 18 checkpoint files exist; saved config records CPU, threshold 0.5 and seeds `[101, 202, 303, 404, 505]`; `test_predictions.csv` has 72,180 test rows; `Results/inference_time_attacks/clean_reproduction_check.csv` contains 90 `OK` rows with max difference `0.0` and max threshold flips `0.0`. These are evidence from a previous run, not a fresh verification.
- **Main remaining risks:** stale outputs cannot be trusted as proof of the current source, existing outputs will be overwritten, and failure-mode aggregation can raise `KeyError` if a whole architecture/modality is excluded by reproduction gating.
- **No execution performed:** no cell was run, no model was loaded for inference by this audit, no training was performed, no packages were installed, and no project file other than this report was modified.

### Cell-numbering convention

- `cell N` = 0-based position in the notebook JSON.
- `CN` = Nth non-empty code cell in execution order.
- Mapping: C1=cell 2, C2=cell 4, C3=cell 6, C4=cell 8, C5=cell 10, C6=cell 12, C7=cell 14, C8=cell 16, C9=cell 18, C10=cell 20, C11=cell 22, C12=cell 24, C13=cell 26, C14=cell 28, C15=cell 30, C16=cell 33, C17=cell 34.

## Findings table

| ID | Severity | Location / cell | Issue | Recommended fix |
|---|---|---|---|---|
| A-01 | MEDIUM | cell 4 (C2), cell 12 (C6) | `CONFIG["stop_on_repro_failure"] = True` does **not** stop on failure. Code raises only when the flag is `False`; with the default `True`, failed runs are excluded and execution continues. The name/comment are inverted relative to behavior. | Rename to `exclude_repro_failures=True`, or invert the condition so `stop_on_repro_failure=True` actually raises. Update the comment and section 7 text to match. |
| A-02 | MEDIUM | cell 30 (C15), cell 33 (C16) | If reproduction gating removes every run for an architecture/modality, `cs()` returns all-NaN series; `tbl[c].idxmin()`, `tbl[c].idxmax()`, `rec[c].idxmax()` and `ARCH_LABEL[...]` can raise `KeyError`/produce invalid report text. | Guard empty/all-NaN groups before `idxmin`/`idxmax`; restrict labels to observed architectures or emit `n/a`. |
| A-03 | MEDIUM | all executed cells | Embedded outputs are from an earlier execution and do not prove the current source ran successfully. Execution counts jump from 13 to 15 (no count 14), indicating deleted/rerun cells. Cell 8 output still prints hardcoded `network[0:29] + radio[29:61]` although its source is now dynamic. | Clear all outputs/execution counts before release, or regenerate them in an authorized fresh run. Do not cite embedded outputs as current evidence. |
| A-04 | MEDIUM | cells 4, 16, 18, 26, 28, 33 | Existing `Results/inference_time_attacks/` artifacts will be overwritten: `attack_predictions.csv` is explicitly unlinked; CSVs, JSON, Markdown and PNGs are written with overwrite semantics. A crash can leave partial outputs. | Back up the output directory or write to a fresh timestamped directory. Make overwrites explicit in the run instructions. |
| A-05 | LOW | cell 12 (C6) | Human-readable reproduction display shows only `ok` and `max_abs_diff`; it omits `pred_flips_vs_saved`. The CSV and final check record flips, but the displayed table under-reports the strict gate. | Add `flip_count` to the groupby display or print a separate flip summary. |
| A-06 | LOW | cell 34 (C17) | Stored output contains `DtypeWarning: Columns (12: severity) have mixed types`, caused by heterogeneous severity labels in the prediction CSV. | Read with `dtype={"severity": str}` or `low_memory=False`; this is log cleanliness, not a metric error. |
| A-07 | LOW | cell 4 (C2) | Determinism is only partially guaranteed: `CUBLAS_WORKSPACE_CONFIG` uses `setdefault` (an existing incompatible value is preserved), and `torch.use_deterministic_algorithms(True, warn_only=True)` is advisory. Device auto-selects GPU if available while saved predictions were produced on CPU. | Pin `DEVICE = cpu` for strict reproduction, or document that GPU runs may fail the 1e-6 gate; set the CUBLAS variable unconditionally if needed. |
| A-08 | LOW | cell 2 (C1) | `N_FEATURES = {"network": 29, ...}` remains hardcoded. It is now only a cross-check against metadata-derived `NET_N`/`RAD_N`, not the boundary source, but it is still a second source of truth. | Optionally derive `N_FEATURES` from `feature_names_and_preprocessing.json` after loading metadata. |
| A-09 | LOW | cell 33 (C16) | Report text says no model was selected using test results, but the reproduction gate uses saved test predictions to exclude runs. That is reproducibility screening, not performance tuning, but the wording is too absolute. | Say: “No model/attack/threshold was selected using test *performance*; runs were screened only for exact reproduction of saved predictions.” |
| A-10 | LOW | cell 16 (C8) | `attack_configuration.json` is written before experiments complete. A later crash leaves a config that looks complete. | Write configuration after successful final verification or include a `run_status` field. |
| A-11 | LOW | cell 28 (C14) | Fourteen plot images are displayed inline and saved to disk; this bloats the notebook and can slow saving/rendering. | Clear outputs or display thumbnails only. |

## Verified items

### 1. Cells and execution order

- All 36 cells are present: Markdown sections 1–16 and 17 non-empty code cells.
- Code cells appear in logical dependency order: imports/config → seeds/hashes → data/split → checkpoints → clean reproduction → attacks → metrics helpers → experiments → aggregation → plots → discussion → export → verification.
- Execution counts are increasing (`8,9,10,11,12,13,15,...,25`) but not contiguous; the missing `14` is a stale-execution artifact (finding A-03), not a source-order error.

### 2. Python syntax and obvious static runtime hazards

- JSON parsed successfully; `nbformat=4`, `nbformat_minor=5`.
- All 17 non-empty code cells compiled successfully with `compile(..., "exec")`.
- Static review found no unconditional syntax/name error on the default all-runs-reproduce path. The main conditional runtime hazard is A-02 under reproduction failures.

### 3. Checkpoint loading and `dl_comparison_models.py` compatibility

- 18 expected paths `<modality>_<architecture>.pt` exist for 6 architectures × 3 modalities.
- Cell 2 asserts required helper APIs exist: `load_checkpoint`, `model_from_checkpoint`, `apply_preprocessing`, `invert_preprocessing`, `predict_proba`, `build_model`, `REGISTRY`.
- Helper source confirms:
  - `load_checkpoint()` uses `torch.load(..., weights_only=True, map_location="cpu")`.
  - `model_from_checkpoint()` builds from `ckpt["architecture"]`, `len(ckpt["feature_names"])`, `ckpt["model_config"]`, then loads `ckpt["runs"][seed]["state_dict"]`.
  - `apply_preprocessing()` uses saved `feature_names`, median imputation, mean and scale, returning float32.
- Cell 10 asserts each checkpoint’s `architecture`, `modality`, `feature_names`, preprocessing feature names, seed set and threshold `0.5`.
- Binary state-dict loading was **not** executed in this audit; compatibility is verified from source and metadata only.

### 4. Saved preprocessing and feature ordering

- `feature_names_and_preprocessing.json` statically confirms `n_features = {network: 29, radio: 32, multimodal: 61}` and `multimodal == network + radio`.
- Cell 4 reads `NET_N`/`RAD_N` from `feat_json["n_features"]`; feature lengths and order are asserted against `features_in_order`.
- Cell 10 asserts preprocessing statistics are identical across architectures for each modality and that multimodal statistics equal concatenated network+radio statistics.
- Metadata columns (`is_attack`, `scenario`, `window_id`, `timestamp_s`, etc.) are explicitly excluded from model inputs.
- Clean inputs are produced only with saved preprocessing; no scaler/imputer is fitted.

### 5. Clean prediction reproduction gate

- Cell 12 requires both conditions for `status == "OK"`:
  - `max |p_reproduced - p_saved| <= CONFIG["repro_tolerance"]` with `repro_tolerance = 1e-6`.
  - `pred_flips_vs_saved == 0`, computed from `(p >= THR)` versus saved `y_pred`.
- Failed runs are not added to `CLEAN_P`, so they are excluded from every `run_condition()` call.
- Final verification (cell 34) re-checks both conditions across all `OK` rows.
- Existing `Results/inference_time_attacks/clean_reproduction_check.csv` was inspected: 90 rows, all `OK`, max difference `0.0`, max flips `0.0`. This is prior-run evidence, not fresh verification.
- Caveat: the flag controlling exclusion is misleading (A-01), and the displayed table omits flip counts (A-05).

### 6. NaN/Inf handling

- `Z_CLEAN` asserts shape and `np.isfinite(...).all()` for all modalities.
- `perturb_block()` asserts input `Zb` finite and output `Z` finite; affected indices are sorted, unique and in range.
- `attacked_input()` asserts output shape and finiteness; `run_condition()` repeats the attacked-input check.
- `predict_Z()` asserts `p.shape == (len(Z),)` and `np.isfinite(p).all()`.
- `clf_metrics()` and `shift_metrics()` assert 1-D finite probability arrays and binary labels.
- Saved probabilities are not explicitly finite-asserted, but a NaN in `d` makes `d.max() <= tol` false, so it fails the gate.

### 7. Multimodal indexing

- `NET_SL`, `RAD_SL`, `BLOCK_SLICE`, `ATTACK_CONFIG["feature_blocks"]`, and the dropout self-test all use `NET_N`/`RAD_N` from saved metadata.
- No hardcoded slice boundaries remain in source. The only hardcoded `29`/`61` occurrence is a stale output string (A-03) and a cross-check constant (A-08).
- Boundary self-tests verify that attacking one block leaves the other block bit-identical.

### 8. Attacks, seeds and affected modalities

- `ATTACK_GRID` contains 22 attacks: Gaussian noise (4), positive bias (3), negative bias (3), scaling (3), feature corruption (3), partial dropout (2), complete dropout (1), combined (3).
- Master seed `20260`; all draws use `stable_seed()` from SHA-256 parts, independent of Python hash randomization.
- Subsets are deterministic per block/family and nested across severities, matching the documentation.
- Targets are correct: network→network, radio→radio, multimodal→network/radio/both.
- `ATTACK_CONFIG` records all affected indices and feature names for both blocks.
- Attack definitions, severities, threshold `0.5`, seed list and test split were not changed in this audit.

### 9. Metrics and aggregation

- `clf_metrics()` computes accuracy, precision, recall, F1, macro-F1, ROC-AUC, PR-AUC, FPR, FNR and confusion counts; `zero_division=0` is explicit.
- `shift_metrics()` computes flip rate, mean probability changes, and ESR as clean-detected attack windows flipped to benign over clean-detected attack windows.
- `scenario_rows()` uses the `thr` parameter consistently for both clean and attacked predictions.
- Clean deltas are joined per `(architecture, modality, seed)`; summaries average per seed first, then across seeds with `ddof=1` std.
- ESR undefined (`NaN`) is handled consistently and checked in final verification.
- Robustness ranking is explicitly descriptive, not a robustness certificate.
- Caveat: A-02 for all-NaN groups under reproduction failures.

### 10. Outputs and verification

- Output root is `Results/inference_time_attacks/`.
- Expected files include all required CSV/JSON/Markdown artifacts plus `clean_reproduction_check.csv`.
- Final verification checks: file existence/non-empty, protected-file hashes, grid completeness, targets, five seeds, test-sample identity, duplicate-free reproduction assertions, confusion-matrix sums, ESR bounds, probability bounds, prediction row count and label identity.
- Existing result counts were inspected statically: `clean_baseline_metrics.csv` 90 rows, `attack_results_per_seed.csv` 3,300, `attack_results_summary.csv` 660, `scenario_level_attack_results.csv` 23,100, `robustness_ranking.csv` 30, `attack_predictions.csv` 2,646,600. These counts are consistent with the source logic and prior outputs, but are not newly generated.
- Overwrite risk remains (A-04).

### 11. Limitations and interpretation

- Markdown section 16 (cell 31) and the generated report contain the required limitations: 35 scenarios, one benign test scenario, date/session confounding, CNN/LSTM/GRU representation caveat, synthetic/unclipped perturbations, UTC-second alignment caveat, no test-based tuning, and no robustness certification.
- The generated discussion text is computed from run variables rather than hardcoded numbers.

## Unverified items

- **Fresh numerical reproduction:** no cell was executed, so the current source has not been shown to reproduce saved predictions in this audit.
- **Binary checkpoint state loading:** existence and API compatibility were checked statically; `torch.load`/`model_from_checkpoint` was not called.
- **Final verification pass on current source:** the embedded “ALL 38 CHECKS PASSED” output is from an earlier run and is stale.
- **GPU behavior:** saved predictions were produced on CPU; GPU execution may exceed the 1e-6 gate. Not tested.
- **Strict determinism:** `warn_only=True` and `setdefault` for CUBLAS do not guarantee deterministic kernels; not tested.
- **Runtime/memory in the current environment:** timing/size estimates come from stale outputs and source inspection only.
- **No hidden test tuning:** code inspection supports label-independent, pre-registered attacks, but author intent outside the notebook cannot be proven.
- **Physical realism:** whether perturbations map to real 5G/O-RAN adversary capabilities cannot be determined statically.

## Scientific validity review

**Strengths**

- The exact existing scenario-grouped test partition is reused from `Results/split_manifest.csv`; no new split is created.
- All preprocessing statistics come from saved training artifacts; no test-fitted scaler/imputer is used.
- Attacks are label-independent, gradient-free, generated from a fixed master seed and recorded before evaluation.
- Both sensor blocks are manipulated independently and jointly; the other block is bit-identical to clean.
- The clean reproduction gate screens reproducibility before attack evaluation and does not relax tolerance.
- Metrics, ESR definition and scenario-level interpretation are documented.

**Limitations and interpretation risks**

- Only 35 scenarios exist and the test partition has 7 scenarios with a single benign scenario (`Benign4`, 229 windows). Test FPR and benign-side metrics have very coarse resolution and large uncertainty.
- Capture date/session is confounded with class; scenario splitting does not remove session artefacts. Robustness conclusions may reflect dataset artefacts.
- Network/Radio alignment is only UTC-second level; “one sensor clean, one manipulated” is a feature-block statement, not a per-UE physical guarantee.
- CNN/LSTM/GRU are feature-column models, not true temporal-sequence models; results must not be read as temporal robustness.
- Perturbations are synthetic, unclipped and standardized-space operations; they may be physically or protocol-inconsistent and can leave the training range.
- Reproducing saved predictions via saved test predictions is a reproducibility screen, not performance tuning, but wording claiming no use of test results at all is too strong (A-09).
- Architecture rankings are descriptive for this synthetic stress-test suite only; no model is certified robust.

## Execution risks

- **Memory:** 90 model instances can be cached in `_MODELS`; `PERT` caches 44 block-attack arrays; 2.65M prediction rows plus 23,100 scenario rows are accumulated/written. This is substantial but bounded.
- **Runtime:** stale output reports roughly 33s + 35s + 185s ≈ 4.2 minutes on CPU; current runtime is unverified.
- **CPU/GPU compatibility:** device auto-selects CUDA if available while saved predictions are from CPU; strict 1e-6 comparison may fail on GPU.
- **Determinism:** CUBLAS workspace config is set with `setdefault`; `warn_only=True` may allow nondeterministic kernels; CPU `set_num_threads(1)` favors repeatability over speed.
- **Output overwriting:** `attack_predictions.csv` is deleted at cell 18; other expected files and plots are overwritten. A failed rerun can destroy prior valid evidence.
- **Log/output bloat:** inline plots and the mixed-type severity warning inflate logs/notebook size.
- **Failure-mode parsing:** if reproduction excludes whole groups, cell 30/cell 33 can crash (A-02).

## Final recommendation

Exact next steps before running:

1. Fix **A-01**: rename/invert `stop_on_repro_failure` so the flag name, comment and behavior agree.
2. Fix **A-02**: guard all `idxmin`/`idxmax` and `ARCH_LABEL[...]` lookups against empty/all-NaN groups.
3. Fix **A-03**: clear stale outputs/execution counts or explicitly mark them historical; do not treat the printed `29`/`61` output or “ALL 38 CHECKS PASSED” as current evidence.
4. Address **A-04**: back up `Results/inference_time_attacks/` or redirect `OUT` to a fresh timestamped directory before rerunning.
5. Optionally address **A-05–A-11**: show flip counts in the reproduction table, set `dtype={"severity": str}`, pin CPU for strict reproduction, derive `N_FEATURES` from metadata, clarify the test-result wording, delay config export until final verification, and avoid inline plot bloat.
6. Only then run `Restart & Run All` in the project root, inspect the fresh reproduction table and final verification output, and re-audit the regenerated artifacts.
