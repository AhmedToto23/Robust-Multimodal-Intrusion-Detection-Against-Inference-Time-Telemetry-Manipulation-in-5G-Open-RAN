# Attack Statistical Analysis

## Units of analysis and dependence

- The experiment has 5 model seeds, 7 scenarios (6 attack, 1 benign), 802 test windows, 22 attack configurations and 5 conditions.
- Individual windows are paired within an attack but are not independent experimental scenarios. Windows from the same capture/session are clustered, and scenario is confounded with class.
- Seed variability measures training-checkpoint variation, not scenario sampling or real-world attack variability.
- All 22 attack configurations are averaged within seed before seed-level statistics; this avoids treating configurations as independent experimental units.

## Suitable paired tests

For condition-level clean-versus-attacked comparisons, the natural paired unit is the model seed: each seed has a clean macro-F1 and an attack-averaged attacked macro-F1. Suitable tests are:

1. paired t-test on 5 seed-level differences;
2. Wilcoxon signed-rank test on the same 5 differences, with very low power at n=5;
3. exact two-sided sign test, whose smallest achievable two-sided p-value with 5 nonzero differences is `0.0625`.

For scenario dependence, the appropriate approach is cluster-level resampling over scenarios or mixed-effects models with scenario as a random effect. With 7 scenarios (6 attack scenarios and 1 benign scenario), such estimates are unstable and cannot support strong inference.

## Seed-level paired results

Holm adjustment is applied across the 30 architecture-condition paired t-tests and separately across Wilcoxon tests.

| architecture | cond | n_seeds | clean_mean | attacked_mean | delta_mean | delta_ci_low | delta_ci_high | negative_seed_count | paired_t_p | paired_t_p_holm | wilcoxon_p | wilcoxon_p_holm | sign_p |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cnn | multimodal:both | 5 | 0.9753 | 0.8165 | -0.1588 | -0.1775 | -0.1401 | 5 | 0.0000 | 0.0005 | 0.0625 | 1.0000 | 0.0625 |
| ft_transformer | multimodal:both | 5 | 0.9997 | 0.9184 | -0.0813 | -0.0900 | -0.0726 | 5 | 0.0000 | 0.0004 | 0.0625 | 1.0000 | 0.0625 |
| gru | multimodal:both | 5 | 0.9917 | 0.8685 | -0.1232 | -0.1849 | -0.0615 | 5 | 0.0052 | 0.0408 | 0.0625 | 1.0000 | 0.0625 |
| lstm | multimodal:both | 5 | 0.9937 | 0.8825 | -0.1112 | -0.1452 | -0.0772 | 5 | 0.0008 | 0.0131 | 0.0625 | 1.0000 | 0.0625 |
| mlp | multimodal:both | 5 | 0.9988 | 0.9394 | -0.0594 | -0.0674 | -0.0515 | 5 | 0.0000 | 0.0008 | 0.0625 | 1.0000 | 0.0625 |
| resmlp | multimodal:both | 5 | 0.9985 | 0.9455 | -0.0530 | -0.0558 | -0.0501 | 5 | 0.0000 | 0.0000 | 0.0625 | 1.0000 | 0.0625 |
| cnn | multimodal:network | 5 | 0.9753 | 0.9111 | -0.0642 | -0.0762 | -0.0522 | 5 | 0.0001 | 0.0024 | 0.0625 | 1.0000 | 0.0625 |
| ft_transformer | multimodal:network | 5 | 0.9997 | 0.9633 | -0.0364 | -0.0515 | -0.0214 | 5 | 0.0026 | 0.0307 | 0.0625 | 1.0000 | 0.0625 |
| gru | multimodal:network | 5 | 0.9917 | 0.9075 | -0.0842 | -0.1398 | -0.0286 | 5 | 0.0137 | 0.0683 | 0.0625 | 1.0000 | 0.0625 |
| lstm | multimodal:network | 5 | 0.9937 | 0.9141 | -0.0796 | -0.1254 | -0.0337 | 5 | 0.0086 | 0.0514 | 0.0625 | 1.0000 | 0.0625 |
| mlp | multimodal:network | 5 | 0.9988 | 0.9749 | -0.0239 | -0.0313 | -0.0165 | 5 | 0.0008 | 0.0131 | 0.0625 | 1.0000 | 0.0625 |
| resmlp | multimodal:network | 5 | 0.9985 | 0.9794 | -0.0191 | -0.0238 | -0.0144 | 5 | 0.0003 | 0.0062 | 0.0625 | 1.0000 | 0.0625 |
| cnn | multimodal:radio | 5 | 0.9753 | 0.9111 | -0.0641 | -0.0812 | -0.0471 | 5 | 0.0005 | 0.0081 | 0.0625 | 1.0000 | 0.0625 |
| ft_transformer | multimodal:radio | 5 | 0.9997 | 0.9971 | -0.0026 | -0.0064 | 0.0011 | 5 | 0.1229 | 0.3688 | 0.0625 | 1.0000 | 0.0625 |
| gru | multimodal:radio | 5 | 0.9917 | 0.9733 | -0.0183 | -0.0618 | 0.0251 | 5 | 0.3063 | 0.3688 | 0.0625 | 1.0000 | 0.0625 |
| lstm | multimodal:radio | 5 | 0.9937 | 0.9862 | -0.0075 | -0.0198 | 0.0048 | 5 | 0.1675 | 0.3688 | 0.0625 | 1.0000 | 0.0625 |
| mlp | multimodal:radio | 5 | 0.9988 | 0.9971 | -0.0017 | -0.0033 | -0.0000 | 4 | 0.0470 | 0.1882 | 0.1250 | 1.0000 | 0.3750 |
| resmlp | multimodal:radio | 5 | 0.9985 | 0.9974 | -0.0011 | -0.0016 | -0.0006 | 5 | 0.0041 | 0.0396 | 0.0625 | 1.0000 | 0.0625 |
| cnn | network:network | 5 | 0.8712 | 0.8063 | -0.0649 | -0.0870 | -0.0427 | 5 | 0.0012 | 0.0161 | 0.0625 | 1.0000 | 0.0625 |
| ft_transformer | network:network | 5 | 0.9906 | 0.8839 | -0.1067 | -0.1252 | -0.0883 | 5 | 0.0001 | 0.0020 | 0.0625 | 1.0000 | 0.0625 |
| gru | network:network | 5 | 0.9637 | 0.7921 | -0.1716 | -0.2494 | -0.0938 | 5 | 0.0036 | 0.0396 | 0.0625 | 1.0000 | 0.0625 |
| lstm | network:network | 5 | 0.9651 | 0.8318 | -0.1334 | -0.1954 | -0.0714 | 5 | 0.0039 | 0.0396 | 0.0625 | 1.0000 | 0.0625 |
| mlp | network:network | 5 | 0.9954 | 0.9198 | -0.0756 | -0.0844 | -0.0669 | 5 | 0.0000 | 0.0005 | 0.0625 | 1.0000 | 0.0625 |
| resmlp | network:network | 5 | 0.9951 | 0.9180 | -0.0771 | -0.0905 | -0.0637 | 5 | 0.0001 | 0.0020 | 0.0625 | 1.0000 | 0.0625 |
| cnn | radio:radio | 5 | 0.9879 | 0.8446 | -0.1434 | -0.1689 | -0.1178 | 5 | 0.0001 | 0.0021 | 0.0625 | 1.0000 | 0.0625 |
| ft_transformer | radio:radio | 5 | 0.9921 | 0.8894 | -0.1027 | -0.1230 | -0.0824 | 5 | 0.0001 | 0.0028 | 0.0625 | 1.0000 | 0.0625 |
| gru | radio:radio | 5 | 0.9942 | 0.8828 | -0.1114 | -0.1670 | -0.0558 | 5 | 0.0051 | 0.0408 | 0.0625 | 1.0000 | 0.0625 |
| lstm | radio:radio | 5 | 0.9954 | 0.8986 | -0.0968 | -0.1289 | -0.0648 | 5 | 0.0011 | 0.0155 | 0.0625 | 1.0000 | 0.0625 |
| mlp | radio:radio | 5 | 0.9939 | 0.8943 | -0.0996 | -0.1115 | -0.0876 | 5 | 0.0000 | 0.0005 | 0.0625 | 1.0000 | 0.0625 |
| resmlp | radio:radio | 5 | 0.9896 | 0.8835 | -0.1061 | -0.1146 | -0.0976 | 5 | 0.0000 | 0.0001 | 0.0625 | 1.0000 | 0.0625 |

Interpretation:

- `24` of 30 condition-level paired t-tests remain below 0.05 after Holm adjustment.
- `0` of 30 Wilcoxon tests remain below 0.05 after Holm adjustment, with the caveat that n=5 is too small for reliable rank-based inference.
- The sign test cannot reach p < 0.05 with only 5 seeds; it should not be used as the primary evidence here.

## Scenario-cluster uncertainty

Scenario-level deltas were computed from `scenario_level_attack_results.csv` and resampled by scenario (10,000 bootstrap replicates). This preserves within-scenario window dependence.

| set | scenarios | mean delta accuracy | bootstrap 95% low | bootstrap 95% high |
|---|---:|---:|---:|---:|
| all test scenarios | 7 | -0.0540 | -0.0677 | -0.0432 |
| attack scenarios only | 6 | -0.0477 | -0.0540 | -0.0417 |

Per-scenario deltas:

| scenario_id | class | n_windows | mean_delta_accuracy | mean_flip_rate | mean_prob_change |
|---|---|---|---|---|---|
| DDOSTCP1 | attack | 100 | -0.0433 | 0.0970 | -0.0449 |
| DDOSTCP2 | attack | 107 | -0.0499 | 0.0501 | -0.0540 |
| PortScan1 | attack | 2 | -0.0555 | 0.0576 | -0.0557 |
| SYN2 | attack | 121 | -0.0435 | 0.0438 | -0.0475 |
| TCP3 | attack | 119 | -0.0357 | 0.0361 | -0.0377 |
| UDP3 | attack | 124 | -0.0584 | 0.0629 | -0.0616 |
| Benign4 | benign | 229 | -0.0914 | 0.0948 | 0.0936 |

These intervals are descriptive only. With 6 attack scenarios and 1 benign scenario, the bootstrap distribution is too coarse for strong confidence claims.

## Do the stored predictions support confidence intervals?

- **Seed-level CIs:** yes, over 5 model seeds, for model-seed variability. They do not include scenario, capture-session or adversary variability.
- **Scenario-cluster CIs:** technically computable, but only 7 clusters and one benign cluster make them fragile.
- **Window-level CIs:** not appropriate. Treating 802 windows as independent would understate uncertainty because windows share scenarios, capture sessions and class-correlated artefacts.
- **Attack-family CIs:** families have unequal numbers of severity levels and share random streams; family-level comparisons should not be treated as balanced independent groups.

## Limitations that must be disclosed

- Small number of model seeds (5) and scenarios (7) limits statistical power and generalization.
- One benign test scenario means FPR is effectively a single-scenario estimate with resolution `1/229`.
- Capture date/session is confounded with class; scenario splitting does not establish causal attack-specific behavior.
- Perturbations are synthetic and may be physically or protocol-inconsistent; unclipped z-values can leave the training range.
- Correlated random streams mean attack configurations within and across families are not fully independent.
- No claim of real-world robustness or multimodal superiority is statistically supported.
