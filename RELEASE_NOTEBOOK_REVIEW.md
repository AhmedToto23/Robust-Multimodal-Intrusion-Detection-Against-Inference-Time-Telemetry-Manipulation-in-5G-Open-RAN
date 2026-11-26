# Release Notebook Review

Date: 2026-11-26
Source: `06_inference_time_telemetry_attacks_final.ipynb`
Release: `06_inference_time_telemetry_attacks_release.ipynb`
Review type: static-only audit; no notebook cells were executed, no model training/inference was run, and no packages were installed.
Verdict: **READY FOR A CONTROLLED RUN, subject to the static-only limitation below.**

## Scope and Guarantees

- Only `06_inference_time_telemetry_attacks_release.ipynb` was created and modified.
- The original, reviewed, and final notebooks were not modified.
- Checkpoints, `05_deep_learning_comparison.ipynb`, helper files, and existing `Results/` were not modified, deleted, or overwritten.
- The release notebook writes only to `Results/inference_time_attacks_release/`.
- Existing `Results/inference_time_attacks/` is never used as an output target.
- No stored outputs or execution counts remain in the release notebook.
- No claim of fresh numerical reproduction is made; runtime and output contents were not regenerated.

Cell convention: `cell N` is the 0-based notebook JSON cell index; `CN` is the Nth non-empty code cell.

## Fix Log

| ID | Requirement | Applied change | Evidence |
|---|---|---|---|
| A-01 | Make reproduction-failure flag behavior match its name | Renamed `stop_on_repro_failure` to `exclude_repro_failures` in config (`cell 4`, C2) and the reproduction gate (`cell 12`, C6). `True` excludes failed `(architecture, modality, seed)` triples from attack experiments; `False` raises `RuntimeError` and stops. | No `stop_on_repro_failure` remains. Config comment documents both branches. |
| A-02 | Guard empty/all-NaN extreme lookups | Added `fmt_num`, `fmt_pct`, `arch_label`, and `safe_extreme` helpers (`cell 30`, C15). Replaced direct `idxmin()`/`idxmax()`/`ARCH_LABEL[...]` uses in Q1/Q6 and routed Q3/Q4/Q5/Q7 formatting through the NaN-safe formatters. Missing cases now render `n/a`. | The only remaining `.idxmin()`/`.idxmax()` call is inside the guarded `safe_extreme` helper after `dropna()` and an `s.empty` check. |
| A-03 | Clear stale outputs | All code-cell `outputs` are `[]` and all `execution_count` values are `null`. | Validated across all 18 code cells. |
| A-04 | Use a fresh output directory without deleting/overwriting old results | `OUT` now points to `Results/inference_time_attacks_release/` (`cell 2`, C1), markdown run instructions were updated (`cell 0`), and a `FileExistsError` guard stops if the release output directory exists and is non-empty. Removed `PRED_PATH.unlink()` and replaced it with `assert not PRED_PATH.exists()` (`cell 18`, C9). | Release path and guards verified; old `Results/inference_time_attacks/` is not referenced as an output target. |
| A-05 | Show prediction flips in clean reproduction display | Reproduction groupby display now includes `max_pred_flips` from `pred_flips_vs_saved` (`cell 12`, C6). | `max_pred_flips` verified in source. |
| A-06 | Avoid mixed-type severity warning | `pd.read_csv(PRED_PATH, chunksize=500_000, dtype={"severity": str})` (`cell 34`, C17). | Explicit dtype verified. |
| A-07 | Pin CPU for strict reproduction | Replaced CUDA-conditional device selection with `DEVICE = torch.device("cpu")`, fixed `torch.set_num_threads(1)`, and changed deterministic algorithms to `warn_only=False` (`cell 4`, C2). CUDA-specific branches removed. | CPU device and strict deterministic setting verified; `1e-6` tolerance and zero-flip gate unchanged. |
| A-08 | Derive feature counts from saved metadata | Removed hardcoded global `N_FEATURES` (`cell 2`, C1). `cell 8` (C4) now derives `N_FEATURES = {m: int(feat_json["n_features"][m]) for m in MODALITIES}`, sets `NET_N`/`RAD_N` from it, and asserts multimodal count equals `NET_N + RAD_N` plus feature-order consistency. | No hardcoded `{"network": 29, "radio": 32, "multimodal": 61}` remains. |
| A-09 | Clarify no test-performance-driven design choices | Threat model (`cell 0`), limitations (`cell 31`), and generated report wording (`cell 33`, C16) now state that no model, attack, severity, subset, or threshold was selected using test performance, and saved test predictions were used only for exact reproduction screening. | Wording verified in markdown and code sources. |
| A-10 | Prevent early config from looking complete | Added `ATTACK_CONFIG["run_status"] = "in_progress"` at config creation (`cell 16`, C8). After all verification checks pass, `cell 34` (C17) sets `run_status = "completed"`, records `verification_checks_passed` and `verified_outputs`, and rewrites `attack_configuration.json`. | `in_progress` is initial state; `completed` is written only after `assert VERIFY.passed.all()`. |

`A-11` was not explicitly in scope, but clearing all stored outputs also removes the large embedded plot/text output from the release notebook. Plot-generation source code was otherwise unchanged.

## Validation Performed

- Notebook JSON parsed successfully.
- 36 cells total; 18 code cells; 17 non-empty code cells.
- Every non-empty code cell compiled with Python `compile(..., "exec")`.
- Static assertions confirmed:
  - no stored outputs or execution counts;
  - release output path and non-empty-directory guard;
  - renamed reproduction flag and documented behavior;
  - CPU-only deterministic configuration;
  - metadata-derived feature counts;
  - prediction-file no-overwrite guard;
  - prediction-flip display;
  - severity string dtype;
  - guarded extreme helpers;
  - in-progress/completed run-status lifecycle;
  - clarified A-09 wording.
- No cells were executed and no output files were generated.

## Research Design Preserved

- Seeds remain `[101, 202, 303, 404, 505]`.
- Decision threshold remains `0.5`.
- Repro tolerance remains `1e-6` with zero prediction flips required.
- Attack families, severities, conditions, test split, and checkpoint references were not changed.
- Saved clean predictions remain used only for exact reproduction screening.
- Research limitations and synthetic-threat-model disclaimer remain intact.

## Remaining Issues / Limitations

- Fresh numerical reproduction cannot be verified under static-only review. Runtime feasibility, actual CPU determinism in this environment, and the size/content of generated files remain unverified until the user runs the notebook.
- `torch.use_deterministic_algorithms(True, warn_only=False)` may fail early if a required operation lacks a deterministic implementation; this is intentional and will surface during execution rather than being silently relaxed.
- The release output directory must be empty or absent. A partially populated directory will stop the run by design.
- Reproducibility still depends on compatibility with the saved CPU-generated predictions; the tolerance was not relaxed.
- Plot-generation code is unchanged, so a full run will still produce the intended plots in the new release output directory.

## Final Status

`06_inference_time_telemetry_attacks_release.ipynb` is statically clean and ready for a controlled `Restart & Run All` by the user. No blocking static defect remains from `A-01` through `A-10`.
