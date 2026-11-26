# When One Sensor Lies: Robust Multimodal Intrusion Detection Against Inference-Time Telemetry Manipulation in 5G Open RAN

Research repository for a single-capture, scenario-grouped study of network/radio/multimodal intrusion detection and inference-time telemetry manipulation in 5G Open RAN.

> **Scope of the evidence:** Results in this repository come from one captured dataset and a synthetic, label-independent attack suite in standardised feature space. Network and radio telemetry are aligned at UTC-second resolution only; no packet-to-UE correspondence is claimed. Rankings are descriptive stress-test outcomes, not robustness certificates. See the generated reports under `Results/` and the static reviews in the repository root for full caveats.

## Publication status

- The publication-facing attack experiment is `06_inference_time_telemetry_attacks_release.ipynb`; the authoritative attack-output directory is `Results/inference_time_attacks_release/`.
- `ATTACK_RESULTS_COMPARISON_REPORT.md` found the original and release attack directories scientifically equivalent. The original directory and the three earlier `06_*` notebooks are retained locally as provenance and archived outside GitHub; they are not part of the minimal publication set.
- Embedded outputs in the three publication notebooks were sanitized: local/absolute paths were redacted and one irrelevant warning output was removed. All notebook source cells are unchanged.
- The two 244.50 MiB `attack_predictions.csv` files are excluded from Git by exact-path rules in `.gitignore`. One canonical copy should be published as an external research artifact with a DOI/permanent URL; none is claimed here yet.
- No Git LFS was installed or configured.

## Repository structure

| Path | Contents |
|---|---|
| `04_baseline_models.ipynb` | Classical baseline modelling (network, radio, multimodal); publication notebook with sanitized outputs. |
| `05_deep_learning_comparison.ipynb` | Clean-data comparison of six architectures across three modalities and five seeds; publication notebook with sanitized outputs. |
| `06_inference_time_telemetry_attacks*.ipynb` | Inference-time manipulation experiment in four versions. `release` is publication-facing; the original, `reviewed`, and `final` versions are provenance archived outside GitHub. |
| `Network Dataset/` | Network-window analysis/cleaning notebooks (`01a`, `01b`), cleaned and engineered CSVs, feature-column manifest, data report and class-count figure. |
| `Radio Dataset/` | Radio analysis/cleaning/preprocessing notebooks (`02a`, `02b`, `02c`), cleaned and window-feature CSVs, Profile A/B feature-column manifests, diagnostics and v2 quality report. |
| `Multimodal Datasets/` | Alignment notebooks (`03`, `03b`), aligned window tables (`multimodal_dataset.csv` and `multimodal_dataset_v2.csv`), feature manifests, alignment reports, timezone validation and unmatched-window diagnostics. |
| `Models/deep_learning/comparison/` | Shared model implementation (`dl_comparison_models.py`) and 18 `<modality>_<architecture>.pt` checkpoints (6 architectures x 3 modalities). |
| `Results/Models/` | Three baseline model artefacts (`.pkl`). |
| `Results/deep_learning_comparison/` | Clean-data comparison metrics, figures, configuration and preprocessing metadata, plus a 90-file training-run cache. |
| `Results/inference_time_attacks/` | Original inference-time attack outputs; preserved locally as provenance and archived outside GitHub. |
| `Results/inference_time_attacks_release/` | Authoritative publication-facing attack outputs (configuration, metrics, per-seed/scenario tables, figures and report). `attack_predictions.csv` is excluded from Git. |
| `Results/split_manifest.csv` | Exact scenario-grouped train/validation/test assignment reused by all experiments. |
| `AUDIT_REPORT.md`, `FINAL_NOTEBOOK_REVIEW.md`, `RELEASE_NOTEBOOK_REVIEW.md` | Static-only audits of the attack notebook lineage. They document known issues and fixes; they are audit trail, not experimental results. |
| `GITHUB_PREPARATION_REPORT.md`, `ATTACK_RESULTS_COMPARISON_REPORT.md`, `FINAL_GITHUB_READINESS_REPORT.md` | Repository preparation, attack-directory equivalence, and final publication-readiness reports. |

## Notebook versions

- `06_inference_time_telemetry_attacks.ipynb` — original notebook; static audit is in `AUDIT_REPORT.md`.
- `06_inference_time_telemetry_attacks_reviewed.ipynb` — intermediate reviewed copy.
- `06_inference_time_telemetry_attacks_final.ipynb` — incorporates the audit fixes; review in `FINAL_NOTEBOOK_REVIEW.md`.
- `06_inference_time_telemetry_attacks_release.ipynb` — publication-facing reviewed version; writes only to `Results/inference_time_attacks_release/`. Review in `RELEASE_NOTEBOOK_REVIEW.md`.

The comparison decision is applied: the `release` notebook and release output directory are authoritative. The other three notebooks and the original attack-output directory remain available locally as provenance, but are archived outside GitHub rather than included in the minimal publication set. The release notebook retains prior-run output evidence; local paths in those outputs were redacted and source cells were not modified.

## Main results

### Classical baselines

Selected by validation macro-F1 before the test partition was evaluated:

| Modality | Selected model | Test macro-F1 |
|---|---|---:|
| network | RandomForest (`max_depth=10`, `min_samples_leaf=1`) | 0.9939 |
| radio | XGBoost (`max_depth=3`, `learning_rate=0.1`) | 0.9863 |
| multimodal | LogisticRegression (`C=0.01`) | 1.0000 |

Full tables, tuning log and classification reports are in `Results/baseline_report.md` and adjacent CSVs. Near-ceiling scores and a single benign test scenario mean small differences are not meaningful model rankings.

### Deep-learning clean comparison

- 6 architectures x 3 modalities x 5 seeds `[101, 202, 303, 404, 505]` = 90 runs.
- Scenario-grouped split: 22/6/7 scenarios and 2,702/635/802 train/validation/test windows.
- Preprocessing statistics and class weight were fitted on training rows only; threshold was fixed at 0.5.
- Architectures were ranked on validation metrics only; clean test performance is not a robustness result.

See `Results/deep_learning_comparison/deep_learning_comparison_report.md`, `configuration_used.json`, and `feature_names_and_preprocessing.json`.

### Inference-time manipulation

- 22 label-independent attack configurations in standardised feature space; master attack seed `20260`; threshold fixed at 0.5.
- 90/90 saved runs reproduced the clean test predictions exactly under the recorded tolerance (`max |diff| = 0.0`); saved test predictions were used only for reproduction screening.
- Mean multimodal macro-F1: clean `0.993`, network-manipulated `0.942`, radio-manipulated `0.977` (averaged over architectures, attack configurations and seeds).
- Manipulating both sensors lowered mean macro-F1 more than the worse single-sensor manipulation for 6/6 architectures.
- These are descriptive synthetic stress-test outcomes, not validated physical 5G/O-RAN attacks and not robustness certificates.

Full results are in `Results/inference_time_attacks_release/attack_report.md`, its aggregate CSVs and figures.

## Reproducibility notes

1. Use the project root as the working directory; notebooks discover datasets and checkpoints relative to it.
2. The recorded environment in `Results/deep_learning_comparison/deep_learning_comparison_report.md` is Python 3.12.10 with torch 2.15.0+cpu. Confirm local package versions against `Results/deep_learning_comparison/configuration_used.json`.
3. The exact split is `Results/split_manifest.csv`; preprocessing statistics and feature order are in `Results/deep_learning_comparison/feature_names_and_preprocessing.json` and the per-dataset feature-column manifests. Model logic is in `Models/deep_learning/comparison/dl_comparison_models.py`.
4. Run order: `04` (baselines) -> `05` (deep-learning comparison) -> `06_inference_time_telemetry_attacks_release.ipynb` (attacks). Do not execute any notebook as part of routine repository use.
5. Before any rerun, read the corresponding review file. The release notebook refuses to write into a non-empty `Results/inference_time_attacks_release/`. Back up or relocate existing outputs first.
6. Attack configurations, decision threshold and seeds are fixed in the notebooks. Saved test predictions are used only for exact reproduction screening, not for model, attack, severity or threshold selection.
7. The two large `attack_predictions.csv` files are ignored by Git and must be obtained separately if per-window audit is required. Aggregate tables and figures are sufficient for the reported summaries.
8. No experimental result should be added to this README without regenerating it from an authorised run and recording the provenance.

## Data availability

The per-window attack prediction table contains 2,646,600 rows x 13 columns and is 256,376,704 bytes with SHA-256 `0D3D449403CF1D21592523B3536AEB7F4941D9BB49CD9B87E777CBF5904DFCCA`. Both preserved copies are byte-identical:

- `Results/inference_time_attacks/attack_predictions.csv` (ignored duplicate)
- `Results/inference_time_attacks_release/attack_predictions.csv` (canonical copy proposed for external hosting)

The canonical external artifact URL/DOI is pending; none is claimed in this repository, and its absence does not block this commit. Do not use Git LFS unless an explicit decision is made to version the 244.50 MiB file.

## Data and output provenance

Dataset descriptions, split construction and leakage controls are documented in `Results/baseline_report.md`, `Network Dataset/network_data_report.md`, `Radio Dataset/radio_quality_report_v2.md` and `Multimodal Datasets/alignment_report_v2.md`. Clean-model results are summarised in `Results/deep_learning_comparison/deep_learning_comparison_report.md`. The authoritative attack summary is `Results/inference_time_attacks_release/attack_report.md`; `ATTACK_RESULTS_COMPARISON_REPORT.md` records why the release directory was selected and why the original directory remains preserved as provenance.
