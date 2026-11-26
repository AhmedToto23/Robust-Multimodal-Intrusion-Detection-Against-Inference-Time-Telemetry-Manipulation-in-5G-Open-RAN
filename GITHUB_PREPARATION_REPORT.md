# GitHub Preparation Report

Repository: `[LOCAL_PATH_REDACTED]`
Branch: `member-3-baseline-members` (upstream `origin/member-3-baseline-members`, in sync)
Project: *When One Sensor Lies: Robust Multimodal Intrusion Detection Against Inference-Time Telemetry Manipulation in 5G Open RAN*

Preparation was static-only: no notebook was executed, no model was retrained, no experiment was rerun, and no package was installed. Nothing was staged, committed, amended, reset or pushed.

## 1. Summary of cleanup

- Removed exactly one disposable generated file: a Python 3.12 bytecode cache (21,308 bytes) and its then-empty `__pycache__` directory.
- Added a root `.gitignore` covering Python/Jupyter caches, OS/editor artefacts, local virtual environments and `.env` files. It does **not** exclude datasets, checkpoints, model weights, run caches, results, figures or notebooks.
- Replaced the one-line `README.md` with a factual project guide: structure, dataset/model/result folder descriptions, notebook lineage, reproducibility notes and provenance pointers. No experimental numbers were invented; all claims refer to files already in the repository.
- Preserved every source file, notebook, dataset, checkpoint, cache, result, figure and report, including both inference-time attack output directories.
- Security scan found no API keys, tokens, passwords, credentials or personal absolute paths.
- Two raw prediction CSVs remain above GitHub's 100 MB per-file limit. They are research outputs and were deliberately not removed; Git LFS is not installed or configured.

## 2. Files removed and reasons

| File | Size | Reason | Safe because |
|---|---:|---|---|
| `Models/deep_learning/comparison/__pycache__/dl_comparison_models.cpython-312.pyc` | 21,308 bytes | Generated Python bytecode cache for `dl_comparison_models.py`. | Fully regenerable from the preserved source; untracked; not research data. |
| `Models/deep_learning/comparison/__pycache__/` (directory) | empty after file removal | Empty generated cache directory. | Nothing of value remained; Python recreates it if needed. |

No other file was deleted or moved. No notebook, dataset, checkpoint, model, result, figure or report was modified by cleanup.

## 3. Files preserved

| Category | Count / size | Notes |
|---|---:|---|
| Essential research files | 13 notebooks, 3 Python modules, README, 3 static-review reports | Notebooks: `04`, `05`, four `06_*` variants, and seven tracked dataset-preparation notebooks. |
| Essential datasets | 31 files, 17.30 MiB | `Multimodal Datasets/` 5.17 MiB; `Network Dataset/` 4.14 MiB; `Radio Dataset/` 7.99 MiB. Includes v1/v2 tables, feature manifests, alignment reports and cleaning notebooks. |
| Essential model checkpoints | 18 `.pt` files, 14.40 MiB | `Models/deep_learning/comparison/`: 6 architectures x 3 modalities. |
| Additional model artefacts | 3 `.pkl`, 0.68 MiB | `Results/Models/` baseline models. |
| Training-run cache | 90 `.pt` files, 15.20 MiB | `Results/deep_learning_comparison/run_cache/`; preserved because it is part of the recorded training provenance. |
| Essential results and figures | 166 files, 529.75 MiB | Includes `split_manifest.csv`, clean-comparison metrics/figures, attack configurations, metrics, figures and per-window predictions. |
| Both attack directories | 22 files each, 252.79 MiB each | `Results/inference_time_attacks/` and `Results/inference_time_attacks_release/` are both intact. Their `attack_predictions.csv` files are byte-identical (SHA-256 `0D3D449403CF1D21592523B3536AEB7F4941D9BB49CD9B87E777CBF5904DFCCA`); this was not used as a reason to delete either directory. |

## 4. Repository structure

```text
.
├── .gitignore                                  (new)
├── README.md                                   (expanded)
├── GITHUB_PREPARATION_REPORT.md                (this report)
├── 04_baseline_models.ipynb
├── 05_deep_learning_comparison.ipynb
├── 06_inference_time_telemetry_attacks.ipynb
├── 06_inference_time_telemetry_attacks_reviewed.ipynb
├── 06_inference_time_telemetry_attacks_final.ipynb
├── 06_inference_time_telemetry_attacks_release.ipynb
├── AUDIT_REPORT.md
├── FINAL_NOTEBOOK_REVIEW.md
├── RELEASE_NOTEBOOK_REVIEW.md
├── Multimodal Datasets/                        aligned v1/v2 windows, manifests, reports, 03/03b notebooks
├── Network Dataset/                            cleaning/analysis notebooks, cleaned + engineered CSVs, report
├── Radio Dataset/                              analysis/cleaning/v2 preprocessing, CSVs, manifests, diagnostics
├── Models/
│   └── deep_learning/comparison/               dl_comparison_models.py + 18 .pt checkpoints
└── Results/
    ├── Models/                                 3 baseline .pkl artefacts
    ├── deep_learning_comparison/               metrics, figures, config, preprocessing JSON, 90-file run_cache/
    ├── inference_time_attacks/                 original attack outputs (22 files)
    └── inference_time_attacks_release/         release-path attack outputs (22 files)
```

Descriptions of each folder are also in the root `README.md`. Dataset provenance is documented in the dataset reports; split provenance is in `Results/split_manifest.csv`; model/preprocessing provenance is in `Results/deep_learning_comparison/configuration_used.json` and `feature_names_and_preprocessing.json`.

## 5. Large-file report

Worktree (excluding `.git`): **228 files, 603,953,969 bytes = 575.98 MiB** (includes this report).
`.git`: 4,515,142 bytes = 4.31 MiB. Total including `.git`: **608,469,111 bytes = 580.28 MiB**.

Files above GitHub's 100 MB per-file limit:

| File | Bytes | MiB | Status |
|---|---:|---:|---|
| `Results/inference_time_attacks/attack_predictions.csv` | 256,376,704 | 244.50 | Untracked, preserved, push blocker without LFS |
| `Results/inference_time_attacks_release/attack_predictions.csv` | 256,376,704 | 244.50 | Untracked, preserved, push blocker without LFS |

Largest 20 files (excluding `.git`):

| # | Bytes | MiB | Path |
|---:|---:|---:|---|
| 1 | 256,376,704 | 244.50 | `Results/inference_time_attacks_release/attack_predictions.csv` |
| 2 | 256,376,704 | 244.50 | `Results/inference_time_attacks/attack_predictions.csv` |
| 3 | 5,564,243 | 5.31 | `Results/deep_learning_comparison/test_predictions.csv` |
| 4 | 4,091,907 | 3.90 | `Results/inference_time_attacks_release/scenario_level_attack_results.csv` |
| 5 | 4,091,907 | 3.90 | `Results/inference_time_attacks/scenario_level_attack_results.csv` |
| 6 | 3,109,369 | 2.97 | `05_deep_learning_comparison.ipynb` |
| 7 | 2,887,639 | 2.75 | `Radio Dataset/radio_window_features_v2.csv` |
| 8 | 2,883,004 | 2.75 | `06_inference_time_telemetry_attacks_release.ipynb` |
| 9 | 2,880,168 | 2.75 | `06_inference_time_telemetry_attacks_final.ipynb` |
| 10 | 2,879,769 | 2.75 | `06_inference_time_telemetry_attacks_reviewed.ipynb` |
| 11 | 2,878,303 | 2.74 | `06_inference_time_telemetry_attacks.ipynb` |
| 12 | 2,559,859 | 2.44 | `Multimodal Datasets/multimodal_dataset.csv` |
| 13 | 2,344,917 | 2.24 | `Multimodal Datasets/multimodal_dataset_v2.csv` |
| 14 | 2,106,395 | 2.01 | `Radio Dataset/radio_clean.csv` |
| 15 | 1,933,229 | 1.84 | `Network Dataset/network_features.csv` |
| 16 | 1,914,892 | 1.83 | `Results/inference_time_attacks_release/attack_results_per_seed.csv` |
| 17 | 1,914,892 | 1.83 | `Results/inference_time_attacks/attack_results_per_seed.csv` |
| 18 | 1,835,185 | 1.75 | `Radio Dataset/02a-Radio analysis.ipynb` |
| 19 | 1,559,515 | 1.49 | `Models/deep_learning/comparison/multimodal_ft_transformer.pt` |
| 20 | 1,534,195 | 1.46 | `Network Dataset/network_clean.csv` |

Git LFS assessment: LFS is necessary only if the two 244.50 MiB prediction CSVs must be versioned in Git. All other files are below the limit and do not require LFS. LFS was **not** installed or configured; that requires an explicit decision.

## 6. Secret/security scan findings

Scanned text files (`*.py`, `*.md`, `*.json`, `*.txt`, `*.csv`) and the **source cells only** of all notebooks for: API keys, API secrets, passwords, AWS access keys, GitHub-style tokens, OpenAI-style `sk-` keys, bearer tokens, private-key headers, and absolute personal path patterns (Windows user-profile, macOS user-profile, and Linux home-directory forms).

Findings:

- No credentials, tokens, passwords or private keys were found.
- No personal absolute paths were found in notebook source, Python modules, JSON, Markdown or text files.
- Generic occurrences of the word "token" in the deep-learning notebooks refer to FT-Transformer learnable tokens and are not credentials.
- No `.env` or credential files exist in the worktree.
- `.git/config` contains a public HTTPS remote URL with no embedded credentials.
- Binary `.pt`/`.pkl` artefacts were not string-scanned; they are model weights and no evidence suggested embedded secrets. A manual binary scan is optional if the publication policy requires it.

## 7. Git status summary

At the initial audit: HEAD `de4f244`, branch in sync with upstream (`+0 -0`), **no tracked modifications**, nothing staged. All research outputs and the root notebooks/reviews were untracked.

After preparation:

- `M README.md` is the only tracked modification; it is the documented README expansion made by this task. Git reports a harmless LF-to-CRLF normalisation warning for this file.
- `.gitignore` and this report are new untracked files.
- The previously untracked research files remain untracked and visible; `git check-ignore` confirmed that representative dataset, checkpoint, run-cache, result and large-prediction paths are **not** ignored.
- Final `git status --short --untracked-files=all` has 197 entries: 1 tracked modification (`README.md`) and 196 untracked paths.
- Nothing is staged; no commit or push was made.

## 8. Potential GitHub push blockers

1. **Two files exceed GitHub's 100 MB hard limit** (`attack_predictions.csv` in both attack directories). Until they are tracked with Git LFS or excluded from Git with an approved external-storage plan, a push will be rejected.
2. **Total repository size is ~576 MiB of worktree data** (580 MiB including `.git`), so pushes/clones will be slow and may hit network or hosting-quota limits even after the per-file issue is solved.
3. **Two near-duplicate attack output directories** make the authoritative result ambiguous. Both are preserved by design; compare them before publication.
4. **Four `06_*` notebook versions** make the authoritative experiment notebook ambiguous. Recommendation: use `release` as the publication candidate, keep the others as provenance until a decision is made.
5. **README modification is unstaged** and includes a line-ending normalisation warning; review it before staging.
6. **Release notebook rerun guard**: `06_inference_time_telemetry_attacks_release.ipynb` intentionally refuses to write into a non-empty `Results/inference_time_attacks_release/`. This is not a push blocker, but it will block a fresh run.
7. No secret-related blocker was found.

## 9. Recommended files to keep

Keep all of the following unless a separate, documented decision says otherwise:

- All 31 dataset files and all feature-manifest JSON files.
- `Results/split_manifest.csv`, `configuration_used.json` and `feature_names_and_preprocessing.json` — required for reproducibility.
- All 18 `.pt` checkpoints, all 90 `run_cache/*.pt` files and the three baseline `.pkl` artefacts.
- All clean-comparison and attack metrics, figures, reports and configuration JSON files.
- **Both** `Results/inference_time_attacks/` and `Results/inference_time_attacks_release/` until the authoritative version is selected.
- All 13 notebooks, including the four `06_*` variants; retain `release` as the preferred publication notebook after comparison.
- `AUDIT_REPORT.md`, `FINAL_NOTEBOOK_REVIEW.md`, `RELEASE_NOTEBOOK_REVIEW.md`, the new `README.md`, `.gitignore` and this report.

After the authoritative comparison, the minimal publication set would keep one attack notebook (recommended: `release`) and one attack-output directory as primary, with the other retained as an archived provenance copy if hosting permits.

## 10. Remaining manual actions before pushing

1. Compare `Results/inference_time_attacks/` with `Results/inference_time_attacks_release/` (the raw prediction CSVs are already confirmed byte-identical) and decide which directory is authoritative. Do not delete either before that decision.
2. Decide whether the two 244.50 MiB CSVs should be tracked with Git LFS or hosted outside Git. Ask before installing or configuring LFS. If LFS is approved, track both files **before** staging them.
3. Review the expanded `README.md` and the new `.gitignore`.
4. Decide which `06_*` notebook is the publication version; keep the rest as provenance unless deliberately removed.
5. Optionally clear stale embedded outputs from the non-release notebooks — this modifies research notebooks and must be a separate decision.
6. Re-run `git status` and verify that all intended research files are visible and none are accidentally ignored.
7. Stage, review, commit and push using the commands in the final response. Do not push until items 1–2 are resolved.

## Appendix A — Categorized inventory (Phase 1)

1. **Essential research files:** 13 notebooks, 3 Python modules (`dl_comparison_models.py`, `multimodal_alignment_v2.py`, `radio_preprocessing_v2.py`), README and review reports.
2. **Essential datasets:** all CSV/JSON/report/figure files in `Multimodal Datasets/`, `Network Dataset/` and `Radio Dataset/`, including both v1 and v2 tables.
3. **Essential model checkpoints:** 18 `.pt` files in `Models/deep_learning/comparison/`, 3 baseline `.pkl` files in `Results/Models/`, and 90 cached `.pt` training runs in `Results/deep_learning_comparison/run_cache/`.
4. **Essential results and figures:** 166 files under `Results/`, including both attack directories and all generated PNGs, CSVs, JSONs and Markdown reports.
5. **Documentation:** root README, `AUDIT_REPORT.md`, `FINAL_NOTEBOOK_REVIEW.md`, `RELEASE_NOTEBOOK_REVIEW.md`, and dataset-specific reports under the dataset folders.
6. **Safe-to-remove temporary files:** one `.pyc` and its empty `__pycache__` directory (both removed); no `.ipynb_checkpoints`, `Thumbs.db`, `.DS_Store`, editor backups or disposable logs were present.
7. **Files requiring a decision:** the four `06_*` notebooks, the two attack-output directories, the two 244.50 MiB prediction CSVs (LFS vs external storage), and the stale embedded outputs in non-release notebooks.
8. **Files that may cause GitHub push problems:** the two `attack_predictions.csv` files (>100 MB each); the overall ~576 MiB worktree size; ambiguous duplicate notebooks/results (review issue, not a technical rejection).
