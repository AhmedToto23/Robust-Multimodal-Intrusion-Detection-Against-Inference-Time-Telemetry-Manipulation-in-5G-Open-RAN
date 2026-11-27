# Trust-Aware Multimodal Fusion — Experimental Report

**Project:** *When One Sensor Lies: Robust Multimodal Intrusion Detection Against Inference-Time Telemetry Manipulation in 5G Open RAN*

> All perturbations are synthetic, label-independent stress tests in standardised feature space (`ATTACK_SEED = 20260`). Reliability estimators were fitted strictly on `train` (2,702 windows) and calibrated strictly on clean `validation` (635 windows); `test` (802 windows) was never used for fitting or tuning.

## 1. Clean-Data Performance (RQ5)

| method | accuracy | macro_f1 | recall | fpr | pr_auc | abstain_rate |
|---|---|---|---|---|---|---|
| network_only | 0.9676 | 0.9635 | 0.9564 | 0.0044 | 0.9995 | n/a |
| radio_only | 0.9936 | 0.9922 | 0.9978 | 0.0167 | 0.9984 | n/a |
| early_fusion | 0.9941 | 0.9929 | 0.9933 | 0.0038 | 0.9999 | n/a |
| uniform_late_fusion | 0.9968 | 0.9962 | 0.9957 | 0.0003 | 1.0000 | n/a |
| trust_aware_fusion | 0.9968 | 0.9961 | 0.9999 | 0.0109 | 0.9999 | 0.0042 |

## 2. Overall Robustness Under Telemetry Manipulation (RQ4)

| attack_target | method | macro_f1 | delta_macro_f1 | recall | fpr | esr | cmia | abstain_rate | selective_macro_f1 |
|---|---|---|---|---|---|---|---|---|---|
| both | early_fusion | 0.8951 | -0.0978 | 0.9471 | 0.1382 | 0.0500 | n/a | n/a | n/a |
| both | network_only | 0.8586 | -0.1049 | 0.8956 | 0.1365 | 0.0824 | n/a | n/a | n/a |
| both | radio_only | 0.8822 | -0.1100 | 0.9072 | 0.1116 | 0.0917 | n/a | n/a | n/a |
| both | trust_aware_fusion | 0.9075 | -0.0886 | 0.9398 | 0.1021 | 0.0602 | n/a | 0.5597 | 0.9617 |
| both | uniform_late_fusion | 0.9084 | -0.0878 | 0.9312 | 0.0803 | 0.0662 | n/a | n/a | n/a |
| network | early_fusion | 0.9417 | -0.0512 | 0.9754 | 0.0912 | 0.0212 | n/a | n/a | n/a |
| network | network_only | 0.8586 | -0.1049 | 0.8956 | 0.1365 | 0.0824 | n/a | n/a | n/a |
| network | radio_only | 0.9922 | 0.0000 | 0.9978 | 0.0167 | 0.0000 | n/a | n/a | n/a |
| network | trust_aware_fusion | 0.9940 | -0.0021 | 0.9989 | 0.0143 | 0.0011 | 0.9278 | 0.0080 | 0.9958 |
| network | uniform_late_fusion | 0.9662 | -0.0299 | 0.9699 | 0.0227 | 0.0275 | n/a | n/a | n/a |
| radio | early_fusion | 0.9770 | -0.0159 | 0.9772 | 0.0119 | 0.0182 | n/a | n/a | n/a |
| radio | network_only | 0.9635 | 0.0000 | 0.9564 | 0.0044 | 0.0000 | n/a | n/a | n/a |
| radio | radio_only | 0.8822 | -0.1100 | 0.9072 | 0.1116 | 0.0917 | n/a | n/a | n/a |
| radio | trust_aware_fusion | 0.9829 | -0.0133 | 0.9824 | 0.0076 | 0.0176 | 0.8616 | 0.1302 | 0.9987 |
| radio | uniform_late_fusion | 0.9735 | -0.0227 | 0.9711 | 0.0077 | 0.0252 | n/a | n/a | n/a |

## 3. Ablation Study Summary

| ablation | clean | network | radio | both |
|---|---|---|---|---|
| confidence_only | 0.9976 | 0.9742 | 0.9789 | 0.9121 |
| dropout_only | 0.9956 | 0.9688 | 0.9713 | 0.9050 |
| full_trust | 0.9961 | 0.9940 | 0.9829 | 0.9075 |
| input_only_no_confidence | 0.9950 | 0.9932 | 0.9743 | 0.8930 |
| mahalanobis_only | 0.9946 | 0.9927 | 0.9716 | 0.8808 |
| no_disagreement_gate | 0.9961 | 0.9943 | 0.9838 | 0.9083 |
| no_dropout_indicator | 0.9960 | 0.9938 | 0.9817 | 0.9071 |
| tail_only | 0.9896 | 0.9718 | 0.9613 | 0.8937 |
| validation_stress_calibrated | 0.9960 | 0.9943 | 0.9833 | 0.9068 |

## 4. Inference Latency Benchmark (CPU, single-thread, RQ5)

| architecture | early_fusion_us_per_window | trust_scoring_us_per_window | trust_fusion_total_us_per_window | overhead_vs_early_ratio | trust_overhead_vs_late_pct |
|---|---|---|---|---|---|
| mlp | 2.12 | 2.11 | 5.77 | 2.73 | 57.59 |
| cnn | 39.50 | 2.42 | 40.82 | 1.03 | 6.29 |
| lstm | 66.05 | 2.95 | 73.46 | 1.11 | 4.18 |
| gru | 88.55 | 2.44 | 73.83 | 0.83 | 3.41 |
| resmlp | 2.83 | 2.09 | 7.54 | 2.67 | 38.42 |
| ft_transformer | 472.10 | 2.38 | 402.22 | 0.85 | 0.59 |

## 5. Limitations

* Only 35 scenarios exist in total; the test partition contains 1 benign scenario (229 benign windows, 573 attack windows), so test FPR resolution is 1/229.
* Capture date/session is confounded with class in the underlying dataset; scenario-based splitting does not eliminate session confounding.
* All manipulations are synthetic stress tests in standardised space and are not validated physical 5G O-RAN attacks.
* When BOTH sensors are severely corrupted simultaneously, no honest modality remains to recover ground truth; the uncertainty fallback is intended to abstain rather than force an unreliable prediction.