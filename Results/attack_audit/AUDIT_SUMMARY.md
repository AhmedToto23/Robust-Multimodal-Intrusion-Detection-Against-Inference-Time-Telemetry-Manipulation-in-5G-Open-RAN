# Attack Audit Summary

- Reconstructed groups: 3,300
- Prediction rows: 2,646,600
- Max classification-metric difference vs published per-seed metrics: 0.000e+00
- Max ROC-AUC / PR-AUC difference vs published per-seed metrics: 4.367e-03 / 1.786e-03 (due to `%.7g` probability serialization)
- Max difference vs published clean metrics: 3.810e-06
- Holm-significant paired t tests: 24/30
- All-scenario bootstrap mean delta accuracy: -0.0540 [-0.0677, -0.0432]
- Attack-scenario bootstrap mean delta accuracy: -0.0477 [-0.0540, -0.0417]

## Files

- ATTACK_IMPLEMENTATION_AUDIT.md
- ATTACK_ROBUSTNESS_ANALYSIS.md
- ATTACK_STATISTICAL_ANALYSIS.md
- reconstructed_clean_vs_attacked_metrics.csv
- fig_attack_severity_curves.png
- fig_degradation_by_condition.png
- fig_worst_configurations.png
- fig_multimodal_vs_unimodal.png
- fig_benign_fpr_under_attack.png
