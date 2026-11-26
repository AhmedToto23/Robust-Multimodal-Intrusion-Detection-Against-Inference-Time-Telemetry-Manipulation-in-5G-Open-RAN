# Inference-Time Telemetry Attacks - Report

**Project:** *When One Sensor Lies: Robust Multimodal Intrusion Detection Against Inference-Time Telemetry Manipulation in 5G Open RAN*

> **All perturbations are synthetic, label-independent stress tests in standardised feature space. They are not validated physical 5G/O-RAN attacks. No model is declared robust by this report.**

## 1. Design

No model was retrained. 90 of 90 saved (architecture, modality, seed) runs reproduced the saved clean test predictions (max |diff| <= 1e-06; worst observed 0.00e+00) and were attacked. Test partition: 802 windows from 7 scenarios (573 attack, 229 benign; benign scenario(s): Benign4). Threshold fixed at 0.5. Master attack seed 20260. 22 attack configurations; conditions: network model/Network, radio model/Radio, multimodal model/Network, Radio or both. ESR = (clean-detected attack windows classified benign after manipulation) / (clean-detected attack windows); undefined if that denominator is 0.

## 2. Clean baseline (reproduced, mean over seeds)

| architecture | modality | accuracy | macro_f1 | recall | fpr | fnr | roc_auc | pr_auc |
|---|---|---|---|---|---|---|---|---|
| cnn | multimodal | 0.9793 | 0.9753 | 0.9721 | 0.0026 | 0.0279 | 0.9998 | 0.9999 |
| cnn | network | 0.8838 | 0.8712 | 0.8373 | 0.0000 | 0.1627 | 0.9995 | 0.9998 |
| cnn | radio | 0.9903 | 0.9879 | 1.0000 | 0.0341 | 0.0000 | 0.9960 | 0.9978 |
| ft_transformer | multimodal | 0.9998 | 0.9997 | 0.9997 | 0.0000 | 0.0003 | 1.0000 | 1.0000 |
| ft_transformer | network | 0.9923 | 0.9906 | 0.9892 | 0.0000 | 0.0108 | 1.0000 | 1.0000 |
| ft_transformer | radio | 0.9935 | 0.9921 | 0.9962 | 0.0131 | 0.0038 | 0.9996 | 0.9998 |
| gru | multimodal | 0.9933 | 0.9917 | 0.9979 | 0.0183 | 0.0021 | 0.9993 | 0.9997 |
| gru | network | 0.9681 | 0.9637 | 0.9606 | 0.0131 | 0.0394 | 0.9968 | 0.9988 |
| gru | radio | 0.9953 | 0.9942 | 0.9990 | 0.0140 | 0.0010 | 0.9954 | 0.9968 |
| lstm | multimodal | 0.9948 | 0.9937 | 0.9934 | 0.0017 | 0.0066 | 0.9999 | 1.0000 |
| lstm | network | 0.9693 | 0.9651 | 0.9623 | 0.0131 | 0.0377 | 0.9972 | 0.9986 |
| lstm | radio | 0.9963 | 0.9954 | 0.9997 | 0.0122 | 0.0003 | 0.9965 | 0.9969 |
| mlp | multimodal | 0.9990 | 0.9988 | 0.9986 | 0.0000 | 0.0014 | 1.0000 | 1.0000 |
| mlp | network | 0.9963 | 0.9954 | 0.9948 | 0.0000 | 0.0052 | 0.9999 | 1.0000 |
| mlp | radio | 0.9950 | 0.9939 | 0.9979 | 0.0122 | 0.0021 | 0.9994 | 0.9997 |
| resmlp | multimodal | 0.9988 | 0.9985 | 0.9983 | 0.0000 | 0.0017 | 1.0000 | 1.0000 |
| resmlp | network | 0.9960 | 0.9951 | 0.9944 | 0.0000 | 0.0056 | 0.9988 | 0.9996 |
| resmlp | radio | 0.9915 | 0.9896 | 0.9941 | 0.0148 | 0.0059 | 0.9982 | 0.9991 |

## 3. Mean over all attack configurations (mean +/- std over seeds of the per-seed mean)

**macro_f1**

| architecture | multimodal:both | multimodal:network | multimodal:radio | network:network | radio:radio |
|---|---|---|---|---|---|
| mlp | 0.939 +/- 0.006 | 0.975 +/- 0.005 | 0.997 +/- 0.001 | 0.920 +/- 0.007 | 0.894 +/- 0.010 |
| cnn | 0.816 +/- 0.018 | 0.911 +/- 0.007 | 0.911 +/- 0.023 | 0.806 +/- 0.019 | 0.845 +/- 0.019 |
| lstm | 0.883 +/- 0.030 | 0.914 +/- 0.038 | 0.986 +/- 0.020 | 0.832 +/- 0.043 | 0.899 +/- 0.025 |
| gru | 0.868 +/- 0.055 | 0.907 +/- 0.047 | 0.973 +/- 0.045 | 0.792 +/- 0.031 | 0.883 +/- 0.044 |
| resmlp | 0.946 +/- 0.002 | 0.979 +/- 0.004 | 0.997 +/- 0.000 | 0.918 +/- 0.011 | 0.883 +/- 0.007 |
| ft_transformer | 0.918 +/- 0.007 | 0.963 +/- 0.012 | 0.997 +/- 0.004 | 0.884 +/- 0.015 | 0.889 +/- 0.015 |

**recall**

| architecture | multimodal:both | multimodal:network | multimodal:radio | network:network | radio:radio |
|---|---|---|---|---|---|
| mlp | 0.971 +/- 0.008 | 0.985 +/- 0.006 | 0.997 +/- 0.001 | 0.941 +/- 0.030 | 0.880 +/- 0.014 |
| cnn | 0.825 +/- 0.036 | 0.936 +/- 0.017 | 0.891 +/- 0.031 | 0.852 +/- 0.023 | 0.903 +/- 0.049 |
| lstm | 0.964 +/- 0.041 | 0.968 +/- 0.039 | 0.987 +/- 0.023 | 0.879 +/- 0.048 | 0.928 +/- 0.035 |
| gru | 0.974 +/- 0.021 | 0.980 +/- 0.013 | 0.995 +/- 0.010 | 0.807 +/- 0.038 | 0.921 +/- 0.058 |
| resmlp | 0.979 +/- 0.005 | 0.990 +/- 0.003 | 0.997 +/- 0.001 | 0.952 +/- 0.019 | 0.878 +/- 0.025 |
| ft_transformer | 0.969 +/- 0.019 | 0.992 +/- 0.006 | 0.997 +/- 0.004 | 0.943 +/- 0.031 | 0.934 +/- 0.040 |

**esr**

| architecture | multimodal:both | multimodal:network | multimodal:radio | network:network | radio:radio |
|---|---|---|---|---|---|
| mlp | 0.028 +/- 0.009 | 0.014 +/- 0.006 | 0.002 +/- 0.001 | 0.054 +/- 0.030 | 0.118 +/- 0.014 |
| cnn | 0.163 +/- 0.033 | 0.050 +/- 0.012 | 0.090 +/- 0.023 | 0.063 +/- 0.025 | 0.097 +/- 0.049 |
| lstm | 0.032 +/- 0.034 | 0.028 +/- 0.032 | 0.009 +/- 0.014 | 0.104 +/- 0.043 | 0.072 +/- 0.035 |
| gru | 0.026 +/- 0.020 | 0.019 +/- 0.013 | 0.004 +/- 0.008 | 0.178 +/- 0.038 | 0.079 +/- 0.058 |
| resmlp | 0.020 +/- 0.005 | 0.009 +/- 0.003 | 0.001 +/- 0.001 | 0.044 +/- 0.019 | 0.119 +/- 0.024 |
| ft_transformer | 0.031 +/- 0.019 | 0.008 +/- 0.006 | 0.003 +/- 0.004 | 0.052 +/- 0.029 | 0.064 +/- 0.038 |

**flip_rate**

| architecture | multimodal:both | multimodal:network | multimodal:radio | network:network | radio:radio |
|---|---|---|---|---|---|
| mlp | 0.042 +/- 0.006 | 0.020 +/- 0.005 | 0.002 +/- 0.001 | 0.060 +/- 0.012 | 0.095 +/- 0.009 |
| cnn | 0.157 +/- 0.018 | 0.070 +/- 0.006 | 0.070 +/- 0.016 | 0.137 +/- 0.019 | 0.120 +/- 0.021 |
| lstm | 0.079 +/- 0.024 | 0.061 +/- 0.026 | 0.010 +/- 0.013 | 0.128 +/- 0.039 | 0.082 +/- 0.025 |
| gru | 0.084 +/- 0.031 | 0.061 +/- 0.027 | 0.015 +/- 0.026 | 0.176 +/- 0.033 | 0.093 +/- 0.043 |
| resmlp | 0.036 +/- 0.003 | 0.016 +/- 0.003 | 0.001 +/- 0.000 | 0.059 +/- 0.009 | 0.101 +/- 0.011 |
| ft_transformer | 0.057 +/- 0.007 | 0.027 +/- 0.006 | 0.002 +/- 0.003 | 0.085 +/- 0.016 | 0.084 +/- 0.016 |

## 4. Robustness ranking (descriptive)

| architecture | condition | clean_macro_f1_mean | attacked_macro_f1_mean | attacked_macro_f1_std_over_seeds | worst_case_macro_f1_mean | mean_delta_macro_f1 | attacked_recall_mean | mean_esr | rank_attacked_macro_f1 | rank_attacked_recall |
|---|---|---|---|---|---|---|---|---|---|---|
| resmlp | multimodal:both | 0.9985 | 0.9455 | 0.0023 | 0.4167 | -0.0530 | 0.9792 | 0.0199 | 1.0000 | 1.0000 |
| mlp | multimodal:both | 0.9988 | 0.9394 | 0.0058 | 0.4167 | -0.0594 | 0.9710 | 0.0282 | 2.0000 | 3.0000 |
| ft_transformer | multimodal:both | 0.9997 | 0.9184 | 0.0071 | 0.4167 | -0.0813 | 0.9691 | 0.0308 | 3.0000 | 4.0000 |
| lstm | multimodal:both | 0.9937 | 0.8825 | 0.0303 | 0.4167 | -0.1112 | 0.9643 | 0.0323 | 4.0000 | 5.0000 |
| gru | multimodal:both | 0.9917 | 0.8685 | 0.0552 | 0.4167 | -0.1232 | 0.9737 | 0.0255 | 5.0000 | 2.0000 |
| cnn | multimodal:both | 0.9753 | 0.8165 | 0.0175 | 0.4167 | -0.1588 | 0.8252 | 0.1632 | 6.0000 | 6.0000 |
| resmlp | multimodal:network | 0.9985 | 0.9794 | 0.0038 | 0.8595 | -0.0191 | 0.9903 | 0.0085 | 1.0000 | 2.0000 |
| mlp | multimodal:network | 0.9988 | 0.9749 | 0.0055 | 0.8390 | -0.0239 | 0.9851 | 0.0141 | 2.0000 | 3.0000 |
| ft_transformer | multimodal:network | 0.9997 | 0.9633 | 0.0116 | 0.7435 | -0.0364 | 0.9923 | 0.0076 | 3.0000 | 1.0000 |
| lstm | multimodal:network | 0.9937 | 0.9141 | 0.0379 | 0.6190 | -0.0796 | 0.9684 | 0.0280 | 4.0000 | 5.0000 |
| cnn | multimodal:network | 0.9753 | 0.9111 | 0.0066 | 0.6727 | -0.0642 | 0.9364 | 0.0500 | 5.0000 | 6.0000 |
| gru | multimodal:network | 0.9917 | 0.9075 | 0.0471 | 0.5611 | -0.0842 | 0.9802 | 0.0189 | 6.0000 | 4.0000 |
| resmlp | multimodal:radio | 0.9985 | 0.9974 | 0.0004 | 0.9856 | -0.0011 | 0.9971 | 0.0014 | 1.0000 | 1.0000 |
| mlp | multimodal:radio | 0.9988 | 0.9971 | 0.0008 | 0.9800 | -0.0017 | 0.9967 | 0.0021 | 2.0000 | 2.0000 |
| ft_transformer | multimodal:radio | 0.9997 | 0.9971 | 0.0037 | 0.9810 | -0.0026 | 0.9966 | 0.0031 | 3.0000 | 3.0000 |
| lstm | multimodal:radio | 0.9937 | 0.9862 | 0.0201 | 0.9538 | -0.0075 | 0.9869 | 0.0087 | 4.0000 | 5.0000 |
| gru | multimodal:radio | 0.9917 | 0.9733 | 0.0452 | 0.8685 | -0.0183 | 0.9948 | 0.0039 | 5.0000 | 4.0000 |
| cnn | multimodal:radio | 0.9753 | 0.9111 | 0.0226 | 0.6753 | -0.0641 | 0.8912 | 0.0901 | 6.0000 | 6.0000 |
| mlp | network:network | 0.9954 | 0.9198 | 0.0070 | 0.3389 | -0.0756 | 0.9413 | 0.0543 | 1.0000 | 3.0000 |
| resmlp | network:network | 0.9951 | 0.9180 | 0.0112 | 0.3778 | -0.0771 | 0.9518 | 0.0439 | 2.0000 | 1.0000 |
| ft_transformer | network:network | 0.9906 | 0.8839 | 0.0151 | 0.4167 | -0.1067 | 0.9431 | 0.0520 | 3.0000 | 2.0000 |
| lstm | network:network | 0.9651 | 0.8318 | 0.0431 | 0.4148 | -0.1334 | 0.8786 | 0.1036 | 4.0000 | 4.0000 |
| cnn | network:network | 0.8712 | 0.8063 | 0.0189 | 0.4167 | -0.0649 | 0.8521 | 0.0625 | 5.0000 | 5.0000 |
| gru | network:network | 0.9637 | 0.7921 | 0.0314 | 0.3421 | -0.1716 | 0.8067 | 0.1779 | 6.0000 | 6.0000 |
| lstm | radio:radio | 0.9954 | 0.8986 | 0.0252 | 0.3000 | -0.0968 | 0.9276 | 0.0722 | 1.0000 | 2.0000 |
| mlp | radio:radio | 0.9939 | 0.8943 | 0.0097 | 0.2221 | -0.0996 | 0.8802 | 0.1185 | 2.0000 | 5.0000 |
| ft_transformer | radio:radio | 0.9921 | 0.8894 | 0.0155 | 0.3778 | -0.1027 | 0.9343 | 0.0641 | 3.0000 | 1.0000 |
| resmlp | radio:radio | 0.9896 | 0.8835 | 0.0074 | 0.2968 | -0.1061 | 0.8778 | 0.1192 | 4.0000 | 6.0000 |
| gru | radio:radio | 0.9942 | 0.8828 | 0.0438 | 0.3389 | -0.1114 | 0.9210 | 0.0786 | 5.0000 | 3.0000 |
| cnn | radio:radio | 0.9879 | 0.8446 | 0.0192 | 0.2610 | -0.1434 | 0.9025 | 0.0975 | 6.0000 | 4.0000 |

Ranks order architectures by measured Macro-F1 / recall under *this* stress-test set only; a high rank is not a certificate of robustness.

## 5. Research questions (generated from the measurements)

**Which architecture is most sensitive to Network manipulation?**

* network:network: most sensitive = GRU (mean change in Macro-F1 -0.172); least affected = 1D CNN (-0.065)
* multimodal:network: most sensitive = GRU (mean change in Macro-F1 -0.084); least affected = Residual MLP (-0.019)

**Which architecture is most sensitive to Radio manipulation?**

* radio:radio: most sensitive = 1D CNN (mean change in Macro-F1 -0.143); least affected = LSTM (-0.097)
* multimodal:radio: most sensitive = 1D CNN (mean change in Macro-F1 -0.064); least affected = Residual MLP (-0.001)

**Does manipulating one sensor affect multimodal performance?**

* Mean Macro-F1 of the multimodal models: clean 0.993, Network manipulated 0.942, Radio manipulated 0.977 (averaged over architectures, attack configurations and seeds).
* Share of (architecture, seed, attack) cases where Macro-F1 falls by more than 0.05 (arbitrary descriptive cut-off): network: 27.7%, radio: 10.2%, both: 36.1%

**Is Network manipulation more damaging than Radio manipulation?**

* Multimodal: Network manipulation lowers mean Macro-F1 more than Radio manipulation for 6/6 architectures (Network -0.051 vs Radio -0.016 on average) and for 6/8 attack families.
* Per architecture, change in Macro-F1 - Network: MLP -0.024, 1D CNN -0.064, LSTM -0.080, GRU -0.084, Residual MLP -0.019, FT-Transformer -0.036 | Radio: MLP -0.002, 1D CNN -0.064, LSTM -0.007, GRU -0.018, Residual MLP -0.001, FT-Transformer -0.003

**Does manipulating both sensors increase degradation?**

* Manipulating both sensors gives a lower mean Macro-F1 than the worse single-sensor manipulation for 6/6 architectures (mean change: both -0.098, worse single -0.051).

**Which architecture maintains the highest attack recall?**

* network:network: highest mean attack recall under manipulation = Residual MLP (0.952); lowest = GRU (0.807)
* radio:radio: highest mean attack recall under manipulation = FT-Transformer (0.934); lowest = Residual MLP (0.878)
* multimodal:network: highest mean attack recall under manipulation = FT-Transformer (0.992); lowest = 1D CNN (0.936)
* multimodal:radio: highest mean attack recall under manipulation = Residual MLP (0.997); lowest = 1D CNN (0.891)
* multimodal:both: highest mean attack recall under manipulation = Residual MLP (0.979); lowest = 1D CNN (0.825)

**Does clean-data performance predict robustness?**

* Spearman correlation between clean Macro-F1 and mean Macro-F1 under manipulation (per condition): multimodal:both: arch-level rho=0.771 (n=6), run-level rho=0.586 (n=30); multimodal:network: arch-level rho=0.714 (n=6), run-level rho=0.499 (n=30); multimodal:radio: arch-level rho=0.771 (n=6), run-level rho=0.816 (n=30); network:network: arch-level rho=0.943 (n=6), run-level rho=0.792 (n=30); radio:radio: arch-level rho=0.657 (n=6), run-level rho=0.329 (n=30)
* With 6 architectures and clean scores close to each other, these correlations are weak evidence either way.

## 6. Limitations

* Only 35 scenarios exist; only six benign scenarios exist overall; the test partition contains 1 benign scenario(s) (229 benign windows), so FPR resolution is 1/229.
* Capture date/session is confounded with class; scenario-based splitting does not eliminate this confounding.
* CNN/LSTM/GRU use feature-column representations, not genuine temporal sequences.
* Perturbations are synthetic stress tests, not validated physical 5G attacks; unclipped values may leave the training range.
* Network and Radio alignment is at UTC-second level and does not establish packet-to-UE correspondence.
* No model, attack, severity or threshold was selected using test performance; saved test predictions were used only for exact reproduction screening. No claim of generalisation or real-world attack validity is made.

## 7. Files

`attack_configuration.json`, `clean_baseline_metrics.csv`, `attack_results_per_seed.csv`, `attack_results_summary.csv`, `attack_predictions.csv`, `scenario_level_attack_results.csv`, `robustness_ranking.csv`, `clean_reproduction_check.csv`, plots: `fig_clean_vs_manipulated_macro_f1.png`, `fig_fpr_clean_vs_manipulated.png`, `fig_fnr_clean_vs_manipulated.png`, `fig_severity_vs_macro_f1.png`, `fig_severity_vs_attack_recall.png`, `fig_sensor_dropout_macro_f1.png`, `fig_network_vs_radio_manipulation.png`, `fig_multimodal_sensor_specific.png`, `fig_heatmap_delta_macro_f1.png`, `fig_heatmap_macro_f1.png`, `fig_heatmap_esr.png`, `fig_evasion_success_rate.png`, `fig_per_seed_variability.png`