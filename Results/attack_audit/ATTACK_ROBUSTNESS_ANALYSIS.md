# Attack Robustness Analysis

## Reconstruction basis

All numbers below were recomputed from `attack_predictions.csv`, not copied from the published report. Classification metrics matched the published per-seed tables exactly (max absolute difference `0.000e+00`). ROC-AUC and PR-AUC differed by at most `4.367e-03` and `1.786e-03` because the prediction CSV stores probabilities with `%.7g` precision while the published AUCs were computed from unrounded probabilities. Clean baselines matched to within `3.810e-06`.

## Clean baseline and degradation by condition

`delta_macro_f1 = attacked_macro_f1 - clean_macro_f1`; more negative means larger degradation. Seed intervals are t-intervals over 5 model seeds and quantify model-seed variability only.

| architecture | cond | clean_macro_f1 | attacked_macro_f1 | delta_macro_f1 | delta_ci_low | delta_ci_high | relative_drop_pct | worst_attacked_macro_f1_seedwise | attacked_recall | attacked_fpr | mean_esr |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cnn | multimodal:both | 0.9753 | 0.8165 | -0.1588 | -0.1775 | -0.1401 | -16.2825 | 0.4167 | 0.8252 | 0.1244 | 0.1632 |
| gru | multimodal:both | 0.9917 | 0.8685 | -0.1232 | -0.1849 | -0.0615 | -12.4222 | 0.4167 | 0.9737 | 0.2382 | 0.0255 |
| lstm | multimodal:both | 0.9937 | 0.8825 | -0.1112 | -0.1452 | -0.0772 | -11.1878 | 0.4167 | 0.9643 | 0.1920 | 0.0323 |
| ft_transformer | multimodal:both | 0.9997 | 0.9184 | -0.0813 | -0.0900 | -0.0726 | -8.1300 | 0.4167 | 0.9691 | 0.1227 | 0.0308 |
| mlp | multimodal:both | 0.9988 | 0.9394 | -0.0594 | -0.0674 | -0.0515 | -5.9491 | 0.4167 | 0.9710 | 0.0757 | 0.0282 |
| resmlp | multimodal:both | 0.9985 | 0.9455 | -0.0530 | -0.0558 | -0.0501 | -5.3046 | 0.4167 | 0.9792 | 0.0760 | 0.0199 |
| gru | multimodal:network | 0.9917 | 0.9075 | -0.0842 | -0.1398 | -0.0286 | -8.4907 | 0.5611 | 0.9802 | 0.1744 | 0.0189 |
| lstm | multimodal:network | 0.9937 | 0.9141 | -0.0796 | -0.1254 | -0.0337 | -8.0068 | 0.6190 | 0.9684 | 0.1386 | 0.0280 |
| cnn | multimodal:network | 0.9753 | 0.9111 | -0.0642 | -0.0762 | -0.0522 | -6.5831 | 0.6727 | 0.9364 | 0.0939 | 0.0500 |
| ft_transformer | multimodal:network | 0.9997 | 0.9633 | -0.0364 | -0.0515 | -0.0214 | -3.6412 | 0.7435 | 0.9923 | 0.0733 | 0.0076 |
| mlp | multimodal:network | 0.9988 | 0.9749 | -0.0239 | -0.0313 | -0.0165 | -2.3910 | 0.8390 | 0.9851 | 0.0337 | 0.0141 |
| resmlp | multimodal:network | 0.9985 | 0.9794 | -0.0191 | -0.0238 | -0.0144 | -1.9139 | 0.8595 | 0.9903 | 0.0333 | 0.0085 |
| cnn | multimodal:radio | 0.9753 | 0.9111 | -0.0641 | -0.0812 | -0.0471 | -6.5773 | 0.6753 | 0.8912 | 0.0092 | 0.0901 |
| gru | multimodal:radio | 0.9917 | 0.9733 | -0.0183 | -0.0618 | 0.0251 | -1.8492 | 0.8685 | 0.9948 | 0.0539 | 0.0039 |
| lstm | multimodal:radio | 0.9937 | 0.9862 | -0.0075 | -0.0198 | 0.0048 | -0.7511 | 0.9538 | 0.9869 | 0.0079 | 0.0087 |
| ft_transformer | multimodal:radio | 0.9997 | 0.9971 | -0.0026 | -0.0064 | 0.0011 | -0.2643 | 0.9810 | 0.9966 | 0.0000 | 0.0031 |
| mlp | multimodal:radio | 0.9988 | 0.9971 | -0.0017 | -0.0033 | -0.0000 | -0.1655 | 0.9800 | 0.9967 | 0.0000 | 0.0021 |
| resmlp | multimodal:radio | 0.9985 | 0.9974 | -0.0011 | -0.0016 | -0.0006 | -0.1086 | 0.9856 | 0.9971 | 0.0003 | 0.0014 |
| gru | network:network | 0.9637 | 0.7921 | -0.1716 | -0.2494 | -0.0938 | -17.8069 | 0.3421 | 0.8067 | 0.1491 | 0.1779 |
| lstm | network:network | 0.9651 | 0.8318 | -0.1334 | -0.1954 | -0.0714 | -13.8205 | 0.4148 | 0.8786 | 0.1631 | 0.1036 |
| ft_transformer | network:network | 0.9906 | 0.8839 | -0.1067 | -0.1252 | -0.0883 | -10.7751 | 0.4167 | 0.9431 | 0.1565 | 0.0520 |
| resmlp | network:network | 0.9951 | 0.9180 | -0.0771 | -0.0905 | -0.0637 | -7.7508 | 0.3778 | 0.9518 | 0.0943 | 0.0439 |
| mlp | network:network | 0.9954 | 0.9198 | -0.0756 | -0.0844 | -0.0669 | -7.5985 | 0.3389 | 0.9413 | 0.0744 | 0.0543 |
| cnn | network:network | 0.8712 | 0.8063 | -0.0649 | -0.0870 | -0.0427 | -7.4458 | 0.4167 | 0.8521 | 0.1818 | 0.0625 |
| cnn | radio:radio | 0.9879 | 0.8446 | -0.1434 | -0.1689 | -0.1178 | -14.5142 | 0.2610 | 0.9025 | 0.1931 | 0.0975 |
| gru | radio:radio | 0.9942 | 0.8828 | -0.1114 | -0.1670 | -0.0558 | -11.2064 | 0.3389 | 0.9210 | 0.1336 | 0.0786 |
| resmlp | radio:radio | 0.9896 | 0.8835 | -0.1061 | -0.1146 | -0.0976 | -10.7234 | 0.2968 | 0.8778 | 0.0549 | 0.1192 |
| ft_transformer | radio:radio | 0.9921 | 0.8894 | -0.1027 | -0.1230 | -0.0824 | -10.3519 | 0.3778 | 0.9343 | 0.1380 | 0.0641 |
| mlp | radio:radio | 0.9939 | 0.8943 | -0.0996 | -0.1115 | -0.0876 | -10.0168 | 0.2221 | 0.8802 | 0.0393 | 0.1185 |
| lstm | radio:radio | 0.9954 | 0.8986 | -0.0968 | -0.1289 | -0.0648 | -9.7286 | 0.3000 | 0.9276 | 0.1109 | 0.0722 |

Most degraded conditions by mean delta macro-F1:

| architecture | cond | clean_macro_f1 | attacked_macro_f1 | delta_macro_f1 | attacked_recall | mean_esr |
|---|---|---|---|---|---|---|
| gru | network:network | 0.9637 | 0.7921 | -0.1716 | 0.8067 | 0.1779 |
| cnn | multimodal:both | 0.9753 | 0.8165 | -0.1588 | 0.8252 | 0.1632 |
| cnn | radio:radio | 0.9879 | 0.8446 | -0.1434 | 0.9025 | 0.0975 |
| lstm | network:network | 0.9651 | 0.8318 | -0.1334 | 0.8786 | 0.1036 |
| gru | multimodal:both | 0.9917 | 0.8685 | -0.1232 | 0.9737 | 0.0255 |
| gru | radio:radio | 0.9942 | 0.8828 | -0.1114 | 0.9210 | 0.0786 |
| lstm | multimodal:both | 0.9937 | 0.8825 | -0.1112 | 0.9643 | 0.0323 |
| ft_transformer | network:network | 0.9906 | 0.8839 | -0.1067 | 0.9431 | 0.0520 |
| resmlp | radio:radio | 0.9896 | 0.8835 | -0.1061 | 0.8778 | 0.1192 |
| ft_transformer | radio:radio | 0.9921 | 0.8894 | -0.1027 | 0.9343 | 0.0641 |

## Most vulnerable models and modalities

- Network-target conditions show larger degradation than radio-target conditions for most architectures. This is a descriptive result on this fixed synthetic grid, not a general statement about sensor importance.
- Within `network:network`, the largest mean degradation is `gru` at `-0.1716`.
- Within `radio:radio`, the largest mean degradation is `cnn` at `-0.1434`.
- Within `multimodal:both`, the largest mean degradation is `cnn` at `-0.1588`.
- Attacked macro-F1 rankings are conditional on near-ceiling clean performance for several models; small absolute drops can dominate relative comparisons.

## Worst attack configurations

The following configurations have the lowest mean delta macro-F1 when averaged over architectures, model modalities and seeds. Because families have unequal numbers of severity levels, this is a configuration ranking, not a family ranking.

| attack_id | attack_type | severity | macro_f1 | recall | delta_macro_f1 | delta_recall | esr | n_evaluations |
|---|---|---|---|---|---|---|---|---|
| sensor_dropout_complete|100% | sensor_dropout_complete | 100% | 0.5626 | 0.8499 | -0.4243 | -0.1369 | 0.1491 | 150 |
| combined|high | combined | high | 0.7220 | 0.7666 | -0.2649 | -0.2202 | 0.2297 | 150 |
| feature_corruption|50% | feature_corruption | 50% | 0.7909 | 0.8709 | -0.1960 | -0.1160 | 0.1264 | 150 |
| combined|medium | combined | medium | 0.8433 | 0.8595 | -0.1436 | -0.1273 | 0.1353 | 150 |
| bias_pos|+2 | bias_pos | +2 | 0.8747 | 0.8953 | -0.1122 | -0.0915 | 0.1028 | 150 |
| bias_neg|-2 | bias_neg | -2 | 0.8821 | 0.9085 | -0.1048 | -0.0783 | 0.0818 | 150 |
| gaussian_noise|1.0 | gaussian_noise | 1.0 | 0.8877 | 0.9218 | -0.0992 | -0.0650 | 0.0726 | 150 |
| feature_corruption|25% | feature_corruption | 25% | 0.8906 | 0.9238 | -0.0963 | -0.0630 | 0.0704 | 150 |
| sensor_dropout_partial|50% | sensor_dropout_partial | 50% | 0.9438 | 0.9866 | -0.0431 | -0.0002 | 0.0101 | 150 |
| scaling|x4 | scaling | x4 | 0.9462 | 0.9636 | -0.0407 | -0.0233 | 0.0261 | 150 |
| combined|low | combined | low | 0.9599 | 0.9640 | -0.0270 | -0.0228 | 0.0322 | 150 |
| bias_neg|-1 | bias_neg | -1 | 0.9602 | 0.9665 | -0.0267 | -0.0203 | 0.0221 | 150 |
| gaussian_noise|0.5 | gaussian_noise | 0.5 | 0.9622 | 0.9706 | -0.0247 | -0.0163 | 0.0209 | 150 |
| bias_pos|+1 | bias_pos | +1 | 0.9683 | 0.9700 | -0.0186 | -0.0168 | 0.0251 | 150 |
| feature_corruption|10% | feature_corruption | 10% | 0.9704 | 0.9763 | -0.0165 | -0.0105 | 0.0195 | 150 |

## Severity curves

Reconstructed severity curves are in `fig_attack_severity_curves.png`. Curves use within-family `severity_rank` on the x-axis and macro-F1 averaged over architectures and seeds. These are descriptive; ranks are not a common physical severity scale across families.

## Multimodal versus unimodal comparison

Positive values mean the multimodal model degraded less than the corresponding unimodal network/radio model under the same attack and seed. This is a paired descriptive comparison, not proof of multimodal superiority, because architectures and input blocks differ and clean scores differ.

| comparison | architecture | mean_delta_difference | ci_low | ci_high | p_seed_t |
|---|---|---|---|---|---|
| multimodal:network minus network:network | cnn | 0.0007 | -0.0157 | 0.0170 | 0.9154 |
| multimodal:network minus network:network | ft_transformer | 0.0703 | 0.0489 | 0.0918 | 0.0008 |
| multimodal:network minus network:network | gru | 0.0874 | -0.0089 | 0.1837 | 0.0654 |
| multimodal:network minus network:network | lstm | 0.0538 | -0.0045 | 0.1122 | 0.0626 |
| multimodal:network minus network:network | mlp | 0.0518 | 0.0372 | 0.0663 | 0.0006 |
| multimodal:network minus network:network | resmlp | 0.0580 | 0.0456 | 0.0705 | 0.0002 |
| multimodal:radio minus radio:radio | cnn | 0.0792 | 0.0595 | 0.0990 | 0.0004 |
| multimodal:radio minus radio:radio | ft_transformer | 0.1001 | 0.0788 | 0.1213 | 0.0002 |
| multimodal:radio minus radio:radio | gru | 0.0931 | 0.0170 | 0.1692 | 0.0274 |
| multimodal:radio minus radio:radio | lstm | 0.0894 | 0.0492 | 0.1295 | 0.0035 |
| multimodal:radio minus radio:radio | mlp | 0.0979 | 0.0858 | 0.1100 | 0.0000 |
| multimodal:radio minus radio:radio | resmlp | 0.1050 | 0.0966 | 0.1134 | 0.0000 |

For both-sensor manipulation relative to the worse single-sensor manipulation:

| architecture | n_seeds | mean | ci_low | ci_high | p_seed_t |
|---|---|---|---|---|---|
| cnn | 5 | -0.0673 | -0.0773 | -0.0574 | 0.0000 |
| ft_transformer | 5 | -0.0446 | -0.0582 | -0.0309 | 0.0008 |
| gru | 5 | -0.0325 | -0.0551 | -0.0100 | 0.0159 |
| lstm | 5 | -0.0299 | -0.0538 | -0.0061 | 0.0253 |
| mlp | 5 | -0.0353 | -0.0405 | -0.0300 | 0.0000 |
| resmlp | 5 | -0.0337 | -0.0386 | -0.0288 | 0.0000 |

## Benign false positives

FPR is computed on 229 benign windows from a single scenario (`Benign4`), so one false positive changes FPR by `0.004367`. The benign scenario is attacked too because perturbations are label-independent.

| cond | fpr_mean | fpr_max | delta_fpr_mean | delta_fpr_max | fp_max |
|---|---|---|---|---|---|
| multimodal:both | 0.1382 | 1.0000 | 0.1344 | 1.0000 | 229.0000 |
| multimodal:network | 0.0912 | 0.9956 | 0.0874 | 0.9956 | 228.0000 |
| multimodal:radio | 0.0119 | 1.0000 | 0.0081 | 0.9476 | 229.0000 |
| network:network | 0.1365 | 1.0000 | 0.1322 | 1.0000 | 229.0000 |
| radio:radio | 0.1116 | 1.0000 | 0.0949 | 0.9913 | 229.0000 |

## Figures

- `fig_attack_severity_curves.png`: reconstructed family severity curves.
- `fig_degradation_by_condition.png`: mean delta macro-F1 by architecture and condition.
- `fig_worst_configurations.png`: worst 12 configurations by mean delta macro-F1.
- `fig_multimodal_vs_unimodal.png`: paired multimodal minus unimodal degradation.
- `fig_benign_fpr_under_attack.png`: distribution of attacked FPR by condition.

## Results that can safely be reported

- These synthetic, label-independent standardized-feature attacks reduce macro-F1 and recall for all tested architectures/conditions on average; the magnitude depends strongly on attack family, severity and target block.
- Network-targeted manipulation generally causes larger degradation than radio-targeted manipulation in this released test set.
- Complete sensor dropout and high/gaussian-noise/combined configurations are among the most damaging in this grid.
- Multimodal models are less degraded than unimodal models under the same target block for several architectures, but this is conditional on this test partition, model set and attack implementation. Do not claim general multimodal superiority or real-world robustness.
- Benign FPR remains low under most attacks, but the estimate is based on one benign scenario and should not be generalized.
