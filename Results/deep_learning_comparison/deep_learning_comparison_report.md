# Deep-Learning Architecture Comparison Report (Member 3)

**Project:** *When One Sensor Lies: Robust Multimodal Intrusion Detection Against Inference-Time Telemetry Manipulation in 5G Open RAN*

These are **dataset-specific, clean-data comparisons**. They do not show generalisation to unseen 5G deployments, and a high clean-data score does not show robustness to telemetry manipulation - the project's actual objective, which is **not** evaluated here. Network-radio alignment is at the UTC-second level only; no packet-to-UE correspondence is claimed.

## 1. Design

6 architectures (MLP, 1D CNN, LSTM, GRU, Residual MLP, FT-Transformer) x 3 modalities (network 29, radio Profile A 32, multimodal 61 features) x 5 seeds [101, 202, 303, 404, 505] = 90 runs. Exact existing split (`Results/split_manifest.csv`, SHA-256 `e9090530e0ee8b75...`): 22/6/7 scenarios, 2,702/635/802 windows. Imputation, standardisation and class weight (`pos_weight` 0.4044) are fitted on training rows only. AdamW, weighted BCE, early stopping on validation loss (patience 12, max 100 epochs), threshold 0.5. Hyper-parameters were fixed a priori (no tuning). Architectures are ranked with **validation metrics only**; the test partition was locked until a hash of all decisions and weights had been stored, and was never used for early stopping, tuning, architecture selection or thresholds.

**Resume cache:** 86 of 90 runs were restored from an on-disk cache of an earlier, interrupted execution (same configuration hash); `train_time_s` of restored runs is the originally measured time.

Environment: python 3.12.10, torch 2.15.0+cpu, device **cpu**.

|  |
||

## 2. Split and preprocessing

| index | scenarios | windows | benign_windows | attack_windows | benign_scenarios | attack_share |
|---|---|---|---|---|---|---|
| train | 22 | 2,702 | 778 | 1,924 | 4 | 0.7121 |
| validation | 6 | 635 | 177 | 458 | 1 | 0.7213 |
| test | 7 | 802 | 229 | 573 | 1 | 0.7145 |

| modality | features | missing cells TRAIN | missing cells VALIDATION | train mean of z (~0) | train std of z (~1) | max abs z TRAIN | max abs z VALIDATION | NaN left |
|---|---|---|---|---|---|---|---|---|
| network | 29 | 0 | 0 | 0.0000 | 1.0000 | 50.1000 | 148.7000 | 0 |
| radio | 32 | 0 | 8 | 0.0000 | 1.0000 | 16.7000 | 12.0000 | 0 |
| multimodal | 61 | 0 | 8 | 0.0000 | 1.0000 | 50.1000 | 148.7000 | 0 |

## 3. Architectures

| index | multimodal | network | radio |
|---|---|---|---|
| MLP | 57,985 | 49,793 | 50,561 |
| 1D CNN | 10,753 | 10,753 | 10,753 |
| LSTM | 21,929 | 21,673 | 21,697 |
| GRU | 17,129 | 16,873 | 16,897 |
| Residual MLP | 63,265 | 60,193 | 60,481 |
| FT-Transformer | 75,009 | 70,913 | 71,297 |

* **CNN:** neighbouring columns are *assumed* to be neighbours (architectural assumption); it does **not** learn temporal patterns. * **LSTM / GRU:** features become a sequence of positions `[value, feature-identity embedding]`; the positions are **not** time steps; exploratory only. * **FT-Transformer:** per-feature tokenizer + CLS token + 2 pre-norm encoder layers; no positional encoding.

## 4. Final comparison - ranked by VALIDATION metrics only

Rule (fixed in advance): validation macro-F1 (mean over seeds) > validation PR-AUC > best validation loss (lower) > fewer parameters. **The validation partition contains a single Benign scenario, so this ranking is fragile.**

| modality | validation_rank | architecture | val macro-F1 | val PR-AUC | val ROC-AUC | val FPR | val FNR | best val loss | parameters | train time (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| network | 1 | FT-Transformer | 0.9915 +/- 0.0042 | 0.9993 +/- 0.0007 | 0.9975 +/- 0.0023 | 0.0000 +/- 0.0000 | 0.0096 +/- 0.0048 | 0.0162 +/- 0.0079 | 70,913 | 72.6000 |
| network | 2 | 1D CNN | 0.9895 +/- 0.0044 | 0.9998 +/- 0.0001 | 0.9994 +/- 0.0004 | 0.0034 +/- 0.0031 | 0.0105 +/- 0.0047 | 0.0144 +/- 0.0042 | 10,753 | 10.7000 |
| network | 3 | Residual MLP | 0.9891 +/- 0.0017 | 0.9992 +/- 0.0010 | 0.9974 +/- 0.0035 | 0.0000 +/- 0.0000 | 0.0122 +/- 0.0020 | 0.0196 +/- 0.0020 | 60,193 | 3.5000 |
| network | 4 | MLP | 0.9884 +/- 0.0000 | 0.9998 +/- 0.0003 | 0.9995 +/- 0.0007 | 0.0000 +/- 0.0000 | 0.0131 +/- 0.0000 | 0.0203 +/- 0.0019 | 49,793 | 2.4000 |
| network | 5 | LSTM | 0.9880 +/- 0.0044 | 0.9994 +/- 0.0005 | 0.9982 +/- 0.0015 | 0.0023 +/- 0.0031 | 0.0127 +/- 0.0039 | 0.0450 +/- 0.0295 | 21,673 | 9.7000 |
| network | 6 | GRU | 0.9824 +/- 0.0127 | 0.9989 +/- 0.0008 | 0.9965 +/- 0.0030 | 0.0000 +/- 0.0000 | 0.0201 +/- 0.0148 | 0.0352 +/- 0.0038 | 16,873 | 13.8000 |
| radio | 1 | LSTM | 0.9984 +/- 0.0009 | 1.0000 +/- 0.0000 | 1.0000 +/- 0.0000 | 0.0000 +/- 0.0000 | 0.0017 +/- 0.0010 | 0.0030 +/- 0.0008 | 21,697 | 20.9000 |
| radio | 2 | GRU | 0.9980 +/- 0.0014 | 1.0000 +/- 0.0000 | 1.0000 +/- 0.0000 | 0.0000 +/- 0.0000 | 0.0022 +/- 0.0015 | 0.0039 +/- 0.0017 | 16,897 | 23.8000 |
| radio | 3 | FT-Transformer | 0.9973 +/- 0.0011 | 1.0000 +/- 0.0000 | 1.0000 +/- 0.0000 | 0.0000 +/- 0.0000 | 0.0031 +/- 0.0012 | 0.0042 +/- 0.0008 | 71,297 | 120.4000 |
| radio | 4 | MLP | 0.9969 +/- 0.0011 | 1.0000 +/- 0.0000 | 1.0000 +/- 0.0000 | 0.0000 +/- 0.0000 | 0.0035 +/- 0.0012 | 0.0039 +/- 0.0006 | 50,561 | 3.7000 |
| radio | 5 | 1D CNN | 0.9965 +/- 0.0021 | 1.0000 +/- 0.0000 | 1.0000 +/- 0.0001 | 0.0000 +/- 0.0000 | 0.0039 +/- 0.0024 | 0.0085 +/- 0.0018 | 10,753 | 8.0000 |
| radio | 6 | Residual MLP | 0.9957 +/- 0.0009 | 1.0000 +/- 0.0000 | 1.0000 +/- 0.0000 | 0.0000 +/- 0.0000 | 0.0048 +/- 0.0010 | 0.0054 +/- 0.0006 | 60,481 | 4.2000 |
| multimodal | 1 | FT-Transformer | 0.9980 +/- 0.0014 | 1.0000 +/- 0.0000 | 1.0000 +/- 0.0000 | 0.0000 +/- 0.0000 | 0.0022 +/- 0.0015 | 0.0048 +/- 0.0027 | 75,009 | 315.0000 |
| multimodal | 2 | GRU | 0.9980 +/- 0.0014 | 1.0000 +/- 0.0000 | 1.0000 +/- 0.0000 | 0.0011 +/- 0.0025 | 0.0017 +/- 0.0010 | 0.0028 +/- 0.0028 | 17,129 | 29.7000 |
| multimodal | 3 | 1D CNN | 0.9969 +/- 0.0011 | 1.0000 +/- 0.0000 | 1.0000 +/- 0.0000 | 0.0000 +/- 0.0000 | 0.0035 +/- 0.0012 | 0.0046 +/- 0.0013 | 10,753 | 13.2000 |
| multimodal | 4 | Residual MLP | 0.9953 +/- 0.0022 | 1.0000 +/- 0.0000 | 1.0000 +/- 0.0000 | 0.0000 +/- 0.0000 | 0.0052 +/- 0.0025 | 0.0045 +/- 0.0023 | 63,265 | 4.6000 |
| multimodal | 5 | LSTM | 0.9950 +/- 0.0070 | 0.9999 +/- 0.0003 | 0.9996 +/- 0.0009 | 0.0000 +/- 0.0000 | 0.0057 +/- 0.0080 | 0.0072 +/- 0.0112 | 21,929 | 29.5000 |
| multimodal | 6 | MLP | 0.9930 +/- 0.0022 | 1.0000 +/- 0.0000 | 1.0000 +/- 0.0000 | 0.0000 +/- 0.0000 | 0.0079 +/- 0.0025 | 0.0057 +/- 0.0027 | 57,985 | 3.1000 |

Mean validation rank across modalities (lower = better):

| architecture | mean_validation_rank | best_rank | mean_val_macro_f1 |
|---|---|---|---|
| FT-Transformer | 1.6667 | 1 | 0.9956 |
| 1D CNN | 3.3333 | 2 | 0.9943 |
| GRU | 3.3333 | 2 | 0.9928 |
| LSTM | 3.6667 | 1 | 0.9938 |
| Residual MLP | 4.3333 | 3 | 0.9934 |
| MLP | 4.6667 | 4 | 0.9927 |

Top-ranked architecture per modality by validation macro-F1: network: FT-Transformer (0.9915 +/- 0.0042); radio: LSTM (0.9984 +/- 0.0009); multimodal: FT-Transformer (0.9980 +/- 0.0014). These are *candidates for the next research stage*, not demonstrated winners: differences between neighbouring ranks are often within the seed standard deviation.

## 5. Test results (802 windows, 7 scenarios, 573 attack / 229 benign windows) - reported, NOT used for ranking

| modality | architecture | validation_rank | test accuracy | test macro-F1 | test PR-AUC | test ROC-AUC | test FPR | test FNR |
|---|---|---|---|---|---|---|---|---|
| network | FT-Transformer | 1 | 0.9923 +/- 0.0066 | 0.9906 +/- 0.0079 | 1.0000 +/- 0.0000 | 1.0000 +/- 0.0001 | 0.0000 +/- 0.0000 | 0.0108 +/- 0.0092 |
| network | 1D CNN | 2 | 0.8838 +/- 0.0020 | 0.8712 +/- 0.0021 | 0.9998 +/- 0.0003 | 0.9995 +/- 0.0007 | 0.0000 +/- 0.0000 | 0.1627 +/- 0.0029 |
| network | Residual MLP | 3 | 0.9960 +/- 0.0006 | 0.9951 +/- 0.0007 | 0.9996 +/- 0.0006 | 0.9988 +/- 0.0020 | 0.0000 +/- 0.0000 | 0.0056 +/- 0.0008 |
| network | MLP | 4 | 0.9963 +/- 0.0000 | 0.9954 +/- 0.0000 | 1.0000 +/- 0.0000 | 0.9999 +/- 0.0001 | 0.0000 +/- 0.0000 | 0.0052 +/- 0.0000 |
| network | LSTM | 5 | 0.9693 +/- 0.0498 | 0.9651 +/- 0.0550 | 0.9986 +/- 0.0015 | 0.9972 +/- 0.0027 | 0.0131 +/- 0.0082 | 0.0377 +/- 0.0697 |
| network | GRU | 6 | 0.9681 +/- 0.0484 | 0.9637 +/- 0.0530 | 0.9988 +/- 0.0005 | 0.9968 +/- 0.0014 | 0.0131 +/- 0.0076 | 0.0394 +/- 0.0706 |
| radio | LSTM | 1 | 0.9963 +/- 0.0015 | 0.9954 +/- 0.0019 | 0.9969 +/- 0.0036 | 0.9965 +/- 0.0035 | 0.0122 +/- 0.0037 | 0.0003 +/- 0.0008 |
| radio | GRU | 2 | 0.9953 +/- 0.0010 | 0.9942 +/- 0.0013 | 0.9968 +/- 0.0016 | 0.9954 +/- 0.0018 | 0.0140 +/- 0.0048 | 0.0010 +/- 0.0010 |
| radio | FT-Transformer | 3 | 0.9935 +/- 0.0028 | 0.9921 +/- 0.0035 | 0.9998 +/- 0.0001 | 0.9996 +/- 0.0002 | 0.0131 +/- 0.0053 | 0.0038 +/- 0.0047 |
| radio | MLP | 4 | 0.9950 +/- 0.0009 | 0.9939 +/- 0.0011 | 0.9997 +/- 0.0001 | 0.9994 +/- 0.0002 | 0.0122 +/- 0.0020 | 0.0021 +/- 0.0008 |
| radio | 1D CNN | 5 | 0.9903 +/- 0.0028 | 0.9879 +/- 0.0036 | 0.9978 +/- 0.0005 | 0.9960 +/- 0.0006 | 0.0341 +/- 0.0100 | 0.0000 +/- 0.0000 |
| radio | Residual MLP | 6 | 0.9915 +/- 0.0022 | 0.9896 +/- 0.0027 | 0.9991 +/- 0.0008 | 0.9982 +/- 0.0015 | 0.0148 +/- 0.0050 | 0.0059 +/- 0.0032 |
| multimodal | FT-Transformer | 1 | 0.9998 +/- 0.0006 | 0.9997 +/- 0.0007 | 1.0000 +/- 0.0000 | 1.0000 +/- 0.0000 | 0.0000 +/- 0.0000 | 0.0003 +/- 0.0008 |
| multimodal | GRU | 2 | 0.9933 +/- 0.0088 | 0.9917 +/- 0.0108 | 0.9997 +/- 0.0004 | 0.9993 +/- 0.0010 | 0.0183 +/- 0.0228 | 0.0021 +/- 0.0038 |
| multimodal | 1D CNN | 3 | 0.9793 +/- 0.0119 | 0.9753 +/- 0.0140 | 0.9999 +/- 0.0001 | 0.9998 +/- 0.0002 | 0.0026 +/- 0.0024 | 0.0279 +/- 0.0167 |
| multimodal | Residual MLP | 4 | 0.9988 +/- 0.0000 | 0.9985 +/- 0.0000 | 1.0000 +/- 0.0000 | 1.0000 +/- 0.0000 | 0.0000 +/- 0.0000 | 0.0017 +/- 0.0000 |
| multimodal | LSTM | 5 | 0.9948 +/- 0.0091 | 0.9937 +/- 0.0108 | 1.0000 +/- 0.0001 | 0.9999 +/- 0.0002 | 0.0017 +/- 0.0039 | 0.0066 +/- 0.0129 |
| multimodal | MLP | 6 | 0.9990 +/- 0.0010 | 0.9988 +/- 0.0013 | 1.0000 +/- 0.0000 | 1.0000 +/- 0.0000 | 0.0000 +/- 0.0000 | 0.0014 +/- 0.0015 |

PR-AUC chance level = attack prevalence of the test partition (0.714). Per-seed values: `per_seed_metrics.csv`; confusion matrices: `confusion_matrices.png`, `confusion_matrices_per_seed.csv`; per-scenario behaviour: `per_scenario_test.csv`; curves: `training_curves.png`; predictions: `test_predictions.csv`.

## 6. Targeted comparisons (validation, mean +/- std over seeds; differences are descriptive)

**MLP vs Residual MLP**

* network: validation macro-F1 MLP 0.9884 (std 0.0000) vs Residual MLP 0.9891 (std 0.0017); difference +0.0008; parameters 49,793 vs 60,193; mean training time 2.4s vs 3.5s
* radio: validation macro-F1 MLP 0.9969 (std 0.0011) vs Residual MLP 0.9957 (std 0.0009); difference -0.0012; parameters 50,561 vs 60,481; mean training time 3.7s vs 4.2s
* multimodal: validation macro-F1 MLP 0.9930 (std 0.0022) vs Residual MLP 0.9953 (std 0.0022); difference +0.0023; parameters 57,985 vs 63,265; mean training time 3.1s vs 4.6s

**CNN vs LSTM vs GRU** (feature order is an assumption, not a time axis)

* network: validation macro-F1 1D CNN 0.9895 (std 0.0044) vs LSTM 0.9880 (std 0.0044); difference -0.0015; parameters 10,753 vs 21,673; mean training time 10.7s vs 9.7s
* radio: validation macro-F1 1D CNN 0.9965 (std 0.0021) vs LSTM 0.9984 (std 0.0009); difference +0.0019; parameters 10,753 vs 21,697; mean training time 8.0s vs 20.9s
* multimodal: validation macro-F1 1D CNN 0.9969 (std 0.0011) vs LSTM 0.9950 (std 0.0070); difference -0.0019; parameters 10,753 vs 21,929; mean training time 13.2s vs 29.5s
* network: validation macro-F1 LSTM 0.9880 (std 0.0044) vs GRU 0.9824 (std 0.0127); difference -0.0056; parameters 21,673 vs 16,873; mean training time 9.7s vs 13.8s
* radio: validation macro-F1 LSTM 0.9984 (std 0.0009) vs GRU 0.9980 (std 0.0014); difference -0.0004; parameters 21,697 vs 16,897; mean training time 20.9s vs 23.8s
* multimodal: validation macro-F1 LSTM 0.9950 (std 0.0070) vs GRU 0.9980 (std 0.0014); difference +0.0031; parameters 21,929 vs 17,129; mean training time 29.5s vs 29.7s

**FT-Transformer vs the other architectures** (validation macro-F1, mean over seeds)

| modality | MLP | 1D CNN | LSTM | GRU | Residual MLP | FT-Transformer | FT minus best other |
|---|---|---|---|---|---|---|---|
| network | 0.9884 | 0.9895 | 0.9880 | 0.9824 | 0.9891 | 0.9915 | 0.0019 |
| radio | 0.9969 | 0.9965 | 0.9984 | 0.9980 | 0.9957 | 0.9973 | -0.0012 |
| multimodal | 0.9930 | 0.9969 | 0.9950 | 0.9980 | 0.9953 | 0.9980 | 0.0000 |

**Network vs Radio vs Multimodal** (validation macro-F1, mean over seeds)

| architecture | network | radio | multimodal |
|---|---|---|---|
| MLP | 0.9884 | 0.9969 | 0.9930 |
| 1D CNN | 0.9895 | 0.9965 | 0.9969 |
| LSTM | 0.9880 | 0.9984 | 0.9950 |
| GRU | 0.9824 | 0.9980 | 0.9980 |
| Residual MLP | 0.9891 | 0.9957 | 0.9953 |
| FT-Transformer | 0.9915 | 0.9973 | 0.9980 |

Modality differences are confounded with capture session (section 8) and must not be read as one modality being universally better.

## 7. Training time and model complexity

| index | parameters_min | parameters_max | train_time_s_mean | best_epoch_mean |
|---|---|---|---|---|
| MLP | 49,793 | 57,985 | 3.0840 | 18.1333 |
| 1D CNN | 10,753 | 10,753 | 10.6277 | 27.2000 |
| LSTM | 21,673 | 21,929 | 20.0390 | 30.8000 |
| GRU | 16,873 | 17,129 | 22.4497 | 32.0000 |
| Residual MLP | 60,193 | 63,265 | 4.1177 | 15.4000 |
| FT-Transformer | 70,913 | 75,009 | 169.3469 | 31.9333 |

Training time is machine-dependent (and restored runs keep their original times); see `fig_training_time_complexity.png`.

## 8. Limitations and interpretation

1. **35 scenarios, 6 Benign.** Benign scenarios per partition: train 4, validation 1 (Benign3, 177 windows), test 1 (Benign4, 229 windows). FPR resolution is 1/229 = 0.0044 on test; windows within a scenario are strongly dependent; seed spread is initialisation variance only, not a confidence interval.
2. **Date/session confounding.** Benign scenarios were captured on 2025-04-14; attack scenarios on 2025-02-27, 2025-03-06, 2025-04-03; dates shared by both classes: none. Grouped splitting cannot remove this. Labels are constant within each scenario.
3. **No claim of generalisation** to unseen 5G deployments; high accuracy does not demonstrate it.
4. **CNN / LSTM / GRU do not learn temporal dependencies here**; the feature order is a schema order. Results for these models are exploratory.
5. One split, a-priori hyper-parameters, no tuning; heavy-tailed features remain after standardisation (no clipping).
6. The research objective - robustness to inference-time telemetry manipulation - is **not** tested here; checkpoints store feature order, preprocessing, training-set feature ranges and all seeds' weights for that next stage.

## 9. Verification performed by the notebook

| passed | check | detail |
|---|---|---|
| yes | a1. all 18 experiments (6 architectures x 3 modalities) are present | 18 |
| yes | a2. every experiment has exactly the seeds [101, 202, 303, 404, 505] | 90 per-seed rows |
| yes | a3. training history covers epochs 1..epochs_run for every run |  |
| yes | a4. prediction file: every (architecture, modality, seed) has the full test partition |  |
| yes | a5. aggregated table has one row per experiment with n_seeds == len(SEEDS) |  |
| yes | b1. the manifest on disk is unchanged since the notebook started |  |
| yes | b2. every sample is in exactly one partition and no scenario spans two partitions |  |
| yes | b3. the indices used for training / validation / test equal the manifest's partitions | {'train': 2702, 'validation': 635, 'test': 802} |
| yes | c1. the test partition was never accessed before the UNLOCK event |  |
| yes | c2. the frozen decision record (best epochs, validation losses, primary seeds, weight hashes) is identical after test evaluation |  |
| yes | c3. best epoch = argmin validation loss; stopping after `patience` epochs without improvement (or at max epochs) |  |
| yes | c4. the training-history file contains no test columns | ['architecture', 'modality', 'seed', 'epoch', 'train_loss', 'val_loss', 'is_best_epoch'] |
| yes | c5. the primary seed of every experiment is the one with the lowest best validation loss |  |
| yes | c6. preprocessing equals a fresh fit on the manifest's TRAIN rows only |  |
| yes | c7. class weight equals n_benign_train / n_attack_train from the manifest |  |
| yes | d1. feature counts are 29 / 32 / 61 in every checkpoint |  |
| yes | d2. checkpoint feature names AND order equal the baseline feature lists |  |
| yes | d3. multimodal = network + radio, in that order |  |
| yes | d4. no forbidden / metadata column among the inputs of any checkpoint |  |
| yes | e1. every checkpoint reloads (weights_only=True) through the exported module and reproduces the saved test probabilities for all seeds | max |difference| = 5.84e-09 |
| yes | e2. the exported module is exactly the model source used in this notebook |  |
| yes | f1. for every run: window_id / scenario_id / y_true equal the manifest's test rows in order and y_pred == (y_probability >= 0.5) |  |
| yes | f2. the prediction file has the required columns |  |
| yes | f3. the model-input matrices contain no metadata: input width equals the approved feature count |  |
| yes | g1. all test metrics in the per-seed file are reproduced from the prediction file |  |
| yes | g2. aggregated mean/std recomputed from the per-seed file equal the saved table |  |
| yes | g3. the validation ranking recomputed from the saved table equals the ranking used (validation columns only) |  |
| yes | h1. re-running one run (MLP / network / first seed) reproduces history and weights exactly |  |
| yes | h2. all pre-existing project files are byte-identical (04_baseline_models.ipynb, baseline results, split manifest, datasets, classical models, earlier deep-learning outputs) | 44 files checked; changed=[]; added=[] |

## 10. Reproduction

```bash
# needs numpy, pandas, scipy, scikit-learn, matplotlib, torch (the notebook installs nothing)
# quick dry run (2 seeds, 2 epochs, temporary output folder; meaningless numbers)
DL_SMOKE_TEST=1 jupyter nbconvert --to notebook --execute --output /tmp/05_cmp_smoke.ipynb 05_deep_learning_comparison.ipynb
# full experiment (90 runs; long on CPU)
jupyter nbconvert --to notebook --execute --inplace 05_deep_learning_comparison.ipynb
```