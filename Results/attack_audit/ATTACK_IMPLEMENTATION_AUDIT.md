# Attack Implementation Audit

## Scope and evidence

- Release notebook: `06_inference_time_telemetry_attacks_release.ipynb`; audit is static-only and did not execute notebook cells.
- Results directory: `Results/inference_time_attacks_release/`.
- Reconstructed from `D:\ds project\Robust-Multimodal-Intrusion-Detection-Git\Results\inference_time_attacks_release\attack_predictions.csv` (2,646,600 rows) and compared against the published per-seed and clean-baseline CSVs.
- Threshold: `0.5`. Master attack seed: `20260`. Standardized space: `standardised features z=(x-mean)/scale using the saved training statistics`.
- Published metadata claims `3,300` attack evaluations across `6` architectures, `3` model modalities, `5` seeds, `22` attacks and 5 target conditions.

## Verified attack grid

All 8 families and 22 configurations are present in `attack_configuration.json` and in the predictions. `severity_rank` is a within-family rank, not a global severity scale.

| family | configurations | exact severity strings | params |
|---|---:|---|---|
| `gaussian_noise` | 4 | `0.1`, `0.25`, `0.5`, `1.0` | {'sigma': 0.1}; {'sigma': 0.25}; {'sigma': 0.5}; {'sigma': 1.0} |
| `bias_pos` | 3 | `+0.5`, `+1`, `+2` | {'delta': 0.5, 'frac': 0.25}; {'delta': 1.0, 'frac': 0.25}; {'delta': 2.0, 'frac': 0.25} |
| `bias_neg` | 3 | `-0.5`, `-1`, `-2` | {'delta': -0.5, 'frac': 0.25}; {'delta': -1.0, 'frac': 0.25}; {'delta': -2.0, 'frac': 0.25} |
| `scaling` | 3 | `x0.5`, `x2`, `x4` | {'factor': 0.5, 'frac': 0.25}; {'factor': 2.0, 'frac': 0.25}; {'factor': 4.0, 'frac': 0.25} |
| `feature_corruption` | 3 | `10%`, `25%`, `50%` | {'frac': 0.1}; {'frac': 0.25}; {'frac': 0.5} |
| `sensor_dropout_partial` | 2 | `25%`, `50%` | {'frac': 0.25}; {'frac': 0.5} |
| `sensor_dropout_complete` | 1 | `100%` | {'frac': 1.0} |
| `combined` | 3 | `low`, `medium`, `high` | {'sigma': 0.1, 'delta': 0.5, 'bias_frac': 0.25, 'corr_frac': 0.1}; {'sigma': 0.25, 'delta': 1.0, 'bias_frac': 0.25, 'corr_frac': 0.25}; {'sigma': 0.5, 'delta': 2.0, 'bias_frac': 0.25, 'corr_frac': 0.5} |

## Perturbation semantics in standardized feature space

Verified in notebook cell 14 (`build_attack_grid`, `feature_subset`, `perturb_block`) and cell 16 (`attacked_input`, `get_pert`):

| family | exact transformation | direction/magnitude | affected features | clipping |
|---|---|---|---|---|
| `gaussian_noise` | `Z += sigma * eps`, `eps ~ N(0,1)` | zero-mean additive noise; sigma `0.1, 0.25, 0.5, 1.0` standard-deviation units | all features in targeted block | none |
| `bias_pos` / `bias_neg` | `Z[:, S] += delta` | constant shift on fixed subset; `+/-0.5, +/-1, +/-2` z units | `S` = fixed random 25% subset | none |
| `scaling` | `Z[:, S] *= factor` | multiplicative rescaling about standardized zero; `0.5, 2, 4` | fixed random 25% subset | none |
| `feature_corruption` | `Z[:, S] = u`, `u ~ N(0,1)` | replace selected values with standard-normal draws; `10%, 25%, 50%` | nested fixed subsets | none |
| `sensor_dropout_partial` | `Z[:, S] = Z_MEDIAN[S]` | replace selected values with saved training median in z units; `25%, 50%` | nested fixed subsets | none |
| `sensor_dropout_complete` | `Z[:, :] = Z_MEDIAN` | whole targeted block set to training median | all features in block | none |
| `combined` | bias -> corruption -> additive noise | `low=(sigma 0.1, delta +0.5, corr 10%)`, `medium=(0.25, +1, 25%)`, `high=(0.5, +2, 50%)` | bias/corruption subsets then all features receive noise | none |

`Z_MEDIAN = (training median - training mean) / training scale` is computed from saved preprocessing statistics. Cell 14 self-check confirms that dropout replacement equals applying the saved preprocessing pipeline to raw NaNs. Cell 14 also confirms determinism and noise scale. The release outputs report clean tails up to `|z| = 34.31` for network and `|z| = 7.59` for radio; because no clipping is applied, perturbed values can leave the training range and should be described as synthetic stress tests, not physically valid sensor values.

## Feature-selection verification

`feature_subset` uses `default_rng(stable_seed(ATTACK_SEED, block, family, "subset")).permutation(F)` and takes the first `max(1, round(frac*F))` sorted indices. The selected feature counts in the configuration are therefore:

| attack_id | network_n | radio_n |
|---|---|---|
| gaussian_noise|0.1 | 29 | 32 |
| gaussian_noise|0.25 | 29 | 32 |
| gaussian_noise|0.5 | 29 | 32 |
| gaussian_noise|1.0 | 29 | 32 |
| bias_pos|+0.5 | 7 | 8 |
| bias_pos|+1 | 7 | 8 |
| bias_pos|+2 | 7 | 8 |
| bias_neg|-0.5 | 7 | 8 |
| bias_neg|-1 | 7 | 8 |
| bias_neg|-2 | 7 | 8 |
| scaling|x0.5 | 7 | 8 |
| scaling|x2 | 7 | 8 |
| scaling|x4 | 7 | 8 |
| feature_corruption|10% | 3 | 3 |
| feature_corruption|25% | 7 | 8 |
| feature_corruption|50% | 14 | 16 |
| sensor_dropout_partial|25% | 7 | 8 |
| sensor_dropout_partial|50% | 14 | 16 |
| sensor_dropout_complete|100% | 29 | 32 |
| combined|low | 29 | 32 |
| combined|medium | 29 | 32 |
| combined|high | 29 | 32 |

Nominal percentages are not exact: for network (`F=29`), 10% -> 3 features (10.3%), 25% -> 7 (24.1%), 50% -> 14 (48.3%); for radio (`F=32`), 10% -> 3 (9.4%), 25% -> 8 (25.0%), 50% -> 16 (50.0%). Subsets are nested within a family and fixed before evaluation; they are not chosen using labels, predictions, or test performance.

## Label independence

Verified in cells 13 and 14: `perturb_block` receives only `Zb`, `spec`, `block`, `ATTACK_SEED` and string stream names. `attacked_input` receives only clean standardized inputs, target blocks, block slices and cached perturbations. Test labels enter only evaluation (`clf_metrics`, `shift_metrics`, `scenario_rows`) and reproduction screening in cell 12. Saved clean test predictions are used as an exact-reproduction gate (cell 12: max absolute difference and threshold flips), not to choose attacks, severities, subsets or the threshold. This notebook cannot verify upstream model-selection decisions in `05_deep_learning_comparison.ipynb`; the no-selection claim must be scoped to this attack notebook.

## Consistency across modalities and models

- Cell 16 caches perturbations by `(block, attack_id)`, then uses the same manipulated block for every architecture and every model seed. This is verified structurally in the code and is not a label-dependent per-model attack.
- Five conditions are evaluated: `network:network`, `radio:radio`, `multimodal:network`, `multimodal:radio`, `multimodal:both`.
- For multimodal inputs, only the targeted block is replaced; the untargeted block is asserted bit-identical to clean in cell 16.
- Clean and attacked probabilities are stored for the same `window_id` in each row. Reconstruction checks: `True` all groups have 802 rows, `True` all groups have 802 unique window IDs, labels match the split manifest for `1.000000` of prediction rows, clean threshold agreement is `1.000000`, attacked threshold agreement is `1.000000`.
- Clean reproduction is `100.0%` of 90 saved runs with zero reported threshold flips.

## Evaluation verification

Verified in cell 18 and reconstructed from `attack_predictions.csv`:

- Classification threshold is fixed at `0.5`: `pred = (p >= thr).astype(int)`.
- The same 802 windows are compared before and after attack; paired probabilities are stored per row.
- Metrics include accuracy, precision, recall, F1, macro-F1, ROC-AUC, PR-AUC, FPR, FNR, TN/FP/FN/TP, flip rate, mean signed probability change (overall, attack rows, benign rows), mean absolute probability change and ESR.
- ESR numerator is clean-detected attack windows that become benign after attack; denominator is clean true positives. ESR is undefined when the denominator is zero.
- Scenario-level rows cover 7 scenarios: 6 attack scenarios and 1 benign scenario (`Benign4`, 229 windows). FPR is computed on the same benign windows under each attack; its resolution is `1/229 = 0.004367`.
- Aggregation in cell 26 averages attack configurations within seed before computing seed mean/std (`ddof=1`). This avoids treating the 22 configurations as independent seeds, but it still does not quantify scenario-level uncertainty.

## Reconstruction agreement

The independently reconstructed classification metrics agree exactly with the published tables. AUC discrepancies are caused by serialization precision: notebook cell 18 computes ROC-AUC/PR-AUC from unrounded in-memory probabilities, but writes `attack_predictions.csv` with `float_format="%.7g"`. Reconstruction from stored probabilities therefore differs only for rank-based AUC metrics.

| comparison | rows | max absolute difference |
|---|---:|---:|
| reconstructed per-seed classification metrics vs `attack_results_per_seed.csv` | 3,300 | 0.000e+00 |
| reconstructed per-seed ROC-AUC vs `attack_results_per_seed.csv` | 3,300 | 4.367e-03 |
| reconstructed per-seed PR-AUC vs `attack_results_per_seed.csv` | 3,300 | 1.786e-03 |
| reconstructed clean metrics vs `clean_baseline_metrics.csv` | 90 | 3.810e-06 |

## Questionable implementation/method choices

1. **Stream aliasing.** Cell 13 says perturbations depend on `(attack_seed, block, attack family)`, but cell 14 keys random streams by generic names (`"bias"`, `"noise"`, `"corruption"`, `"subset"`). `bias_pos`, `bias_neg` and `combined` share the bias draw; `gaussian_noise` and `combined` share the same noise draw scaled by sigma; `feature_corruption` and `combined` share corruption values. This is not label leakage, but attacks are correlated and should not be described as fully independent stress tests.
2. **No clipping/bounds.** Perturbed standardized values are not projected back to plausible raw-value ranges. This can produce physically inconsistent telemetry.
3. **Rounded subset fractions.** The markdown claims exact 10/25/50% feature fractions, but the implemented counts are rounded as shown above.
4. **ESR conditioning.** ESR is conditional on clean detection. A model with low clean recall can have a favorable ESR; ESR must always be reported with clean recall and attack recall.
5. **Unequal family averaging.** The condition averages use 22 configurations, so families with 4 severities contribute more than families with 1. Family-level comparisons are not equally weighted.
6. **Verification loophole.** The “all five seeds present” check is bypassed when reproduction failures exist. Here no failures are reported, so the released artifact is unaffected, but the check itself is weak.
7. **Single benign scenario.** FPR and benign-side metrics rest on one scenario and cannot characterize false positives across sessions.
8. **Scenario/session confounding.** Capture session is confounded with class; scenario-based splitting does not remove this. Perturbation sensitivity may reflect session artefacts.
9. **Model representation.** CNN/LSTM/GRU use feature-column inputs, not true temporal sequences; results must not be interpreted as temporal-model robustness.

## Verified vs assumed

- **Verified from code/config/stored predictions:** 8 families, 22 configurations, formulas, fixed feature subsets, no clipping, label-independent attack generation, paired samples, threshold 0.5, metric definitions, aggregation logic, 90/90 clean reproduction, reconstruction agreement.
- **Not verified:** physical realism of perturbations, causal robustness in a deployed 5G/O-RAN system, generalization beyond the stored test scenarios, and upstream model-selection independence.
