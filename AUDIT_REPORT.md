# Static Code Audit Report — `06_inference_time_telemetry_attacks.ipynb`

**Project:** *When One Sensor Lies: Robust Multimodal Intrusion Detection Against Inference-Time Telemetry Manipulation in 5G Open RAN*

**Audited notebook:** `06_inference_time_telemetry_attacks.ipynb`
**Reference implementation:** `Models/deep_learning/comparison/dl_comparison_models.py`
**Supporting evidence inspected statically:** `05_deep_learning_comparison.ipynb`, `Results/split_manifest.csv`, `Results/deep_learning_comparison/feature_names_and_preprocessing.json`, `Results/deep_learning_comparison/test_predictions.csv`, `Results/deep_learning_comparison/configuration_used.json`, `Results/deep_learning_comparison/deep_learning_comparison_report.md`, and the 18 checkpoint filenames under `Models/deep_learning/comparison/`.

## Audit method and limits

This was a **static-only** review. No notebook cell was executed; no model was trained; no inference was run; no experiment was launched; no package was installed; no existing project file was modified.

**Cell numbering convention used throughout:** cells are numbered by their 0-based position in the notebook JSON. `Ck` means the kth code cell in execution order. Mapping:

| Notebook cell | Code cell | Content |
|---:|---:|---|
| 0 | — | Markdown: objective, threat model, run instructions |
| 2 | C1 | Imports, root discovery, checkpoint path construction |
| 4 | C2 | Config, device/determinism flags, output directory |
| 6 | C3 | `stable_seed()`, protected-file hashes |
| 8 | C4 | Dataset/manifest/test split/feature metadata loading |
| 10 | C5 | Checkpoint loading, preprocessing cross-checks, model factory, `predict_Z()` |
| 12 | C6 | Clean inputs and clean prediction reproduction gate |
| 14 | C7 | Attack grid and `perturb_block()` |
| 16 | C8 | Perturbation cache, multimodal index mapping, `attacked_input()` |
| 18 | C9 | Metrics, prediction writer, `run_condition()` |
| 20 | C10 | Network-model experiments |
| 22 | C11 | Radio-model experiments |
| 24 | C12 | Multimodal experiments |
| 26 | C13 | Aggregation and ranking |
| 28 | C14 | Plots |
| 30 | C15 | Research-question analysis |
| 33 | C16 | Markdown report and reproduction-check CSV |
| 34 | C17 | Final verification |
| 35 | C18 | Empty code cell |

**Important:** outputs embedded in the notebook are prior execution artifacts. They were **not** reproduced, re-run, or independently verified in this audit. This report does **not** claim that clean prediction reproduction succeeded.

---

## 1. Executive summary

The notebook's core experimental design is consistent with the reference implementation: it constructs all 18 `<modality>_<architecture>.pt` checkpoint paths, validates five seeds in `ckpt["runs"]`, rebuilds models through `dlc.model_from_checkpoint(ckpt, seed)`, uses saved preprocessing from the checkpoints, applies sigmoid to the model's `(batch_size,)` logits, and compares those probabilities to `test_predictions.csv`. The attacks are label-independent, deterministic, and deliberately applied in standardised feature space. The multimodal network/radio split matches the saved metadata. Metrics follow the definitions used in notebook 05.

No CRITICAL defect was confirmed by static inspection. However, several issues should be corrected before a fresh full run: incomplete finite-value checking in a dataset with a near-zero saved scale, a clean-reproduction gate that records but does not enforce zero threshold flips, hardcoded feature-index boundaries that are defended only by assertions, no explicit 1-D/finite assertion on prediction output, incomplete CUDA determinism setup, and a tautological final verification. There are also efficiency risks from caching 90 reconstructed models and writing a very large prediction CSV.

**Overall readiness verdict: READY AFTER MINOR FIXES.**

The fixes are localized and mostly defensive; none requires redesign of the experiment. A fresh full run should not be treated as trustworthy until the HIGH/MEDIUM items below are applied and the smoke-test plan passes.

---

## 2. Overall readiness verdict

### READY AFTER MINOR FIXES

Conditions for changing the verdict to READY:

1. Apply the finite-value and reproduction-gate corrections (`F-01`, `F-02`).
2. Derive the network/radio boundaries from saved metadata rather than hardcoded constants (`F-03`).
3. Add explicit prediction-shape/finite assertions (`F-04`).
4. Add `CUBLAS_WORKSPACE_CONFIG` and disable bytecode writes (`F-05`, `F-06`).
5. Strengthen final output verification (`F-07`, `F-08`).
6. Complete the pre-execution smoke-test plan in section 9 without changing attack definitions, thresholds, or selection rules.

---

## 3. Critical issues

**No CRITICAL issue was confirmed through static inspection.**

Specifically, the audit did not find static evidence of:

- wrong checkpoint filenames or missing combinations;
- incorrect use of `dlc.model_from_checkpoint()`;
- training or fitting on test data;
- threshold tuning on test data;
- label-dependent attack generation;
- confusion of logits with probabilities in the main prediction path;
- a wrong positive-class definition.

Items that could become critical only under runtime conditions are listed as HIGH/MEDIUM risks below and are explicitly marked as requiring execution to verify.

---

## 4. Major issues

### F-01 — Incomplete NaN/infinity safety

**Severity: HIGH**
**Status: confirmed by static inspection; actual runtime values require execution to verify**
**Cells:** 10 (C5), 12 (C6), 14 (C7), 16 (C8), 18 (C9)

`dl_comparison_models.py:179-187` handles NaNs with the saved median but does **not** reject `±inf`:

```python
A = X[names].to_numpy(dtype=np.float64)
A = np.where(np.isnan(A), np.asarray(pre["median"], dtype=np.float64), A)
return ((A - mean) / scale).astype(np.float32)
```

The saved network scale for `other_frac` is approximately `6.7649e-18` (`feature_names_and_preprocessing.json:233-263`). Dividing raw values by such a small scale can produce very large finite values or overflow to infinity for unusual inputs. The notebook checks only `np.isnan(...)` at cell 12 (C6), and cell 14 (C7) checks `not np.isnan(_got).any()` for one dropout self-test. Neither `perturb_block()` nor `attacked_input()` explicitly asserts that all arrays are finite.

**Risk:** `roc_auc_score`, `average_precision_score`, `confusion_matrix`, and thresholding may fail or produce misleading results if an infinity appears in clean or attacked probabilities. With the currently saved data, stored outputs show finite z-ranges, but this audit does not verify that independently.

**Recommended correction:**

```python
assert all(
    Z_CLEAN[m].shape == (len(idx_test), N_FEATURES[m])
    and np.isfinite(Z_CLEAN[m]).all()
    for m in MODALITIES
)
```

and inside `perturb_block()` before return:

```python
Z = Z.astype(np.float32)
assert Z.shape == Zb.shape and np.isfinite(Z).all()
```

Also assert `np.isfinite(p).all()` on the output of `predict_Z()`.

---

### F-02 — Clean reproduction gate ignores threshold flips

**Severity: HIGH**
**Status: confirmed by static inspection**
**Cells:** 12 (C6)

The notebook computes `pred_flips_vs_saved` but only uses the probability tolerance to mark a run as OK:

```python
row["pred_flips_vs_saved"] = int(
    ((p >= THR).astype(int) != g["y_pred"].to_numpy()).sum()
)
if d.max() <= CONFIG["repro_tolerance"]:
    row["status"] = "OK"
    CLEAN_P[(a, m, s)] = p
```

A probability difference below `1e-6` can still cross the fixed threshold `0.5`, producing a different clean prediction. In that case the run would be accepted as reproduced while its clean labels differ from the saved `y_pred`.

**Recommended correction:**

```python
repro_ok = (
    d.max() <= CONFIG["repro_tolerance"]
    and row["pred_flips_vs_saved"] == 0
)
if repro_ok:
    row["status"] = "OK"
    CLEAN_P[(a, m, s)] = p
```

This is a localized fix and does not relax the original tolerance.

---

### F-03 — Hardcoded feature-index boundaries

**Severity: MEDIUM**
**Status: confirmed by static inspection**
**Cells:** 2 (C1), 12 (C6), 16 (C8)

The notebook hardcodes:

```python
N_FEATURES = {"network": 29, "radio": 32, "multimodal": 61}
NET_SL, RAD_SL = slice(0, 29), slice(29, 61)
BLOCK_SLICE = {
    "network": {"network": slice(0, 29)},
    "radio": {"radio": slice(0, 32)},
    "multimodal": {"network": NET_SL, "radio": RAD_SL},
}
```

Cells 8 (C4) and 10 (C5) do assert that `FEATURES["multimodal"] == FEATURES["network"] + FEATURES["radio"]` and that counts are 29/32/61, so the current saved metadata is protected. Nevertheless, the user requirement is to verify indices from saved feature metadata, not assumptions.

**Recommended correction:**

```python
NET_N = len(FEATURES["network"])
RAD_N = len(FEATURES["radio"])
NET_SL = slice(0, NET_N)
RAD_SL = slice(NET_N, NET_N + RAD_N)
assert NET_N + RAD_N == len(FEATURES["multimodal"])
assert Z_CLEAN["multimodal"][:, NET_SL].shape == Z_CLEAN["network"].shape
assert Z_CLEAN["multimodal"][:, RAD_SL].shape == Z_CLEAN["radio"].shape
```

---

### F-04 — No explicit shape/finite validation of prediction output

**Severity: MEDIUM**
**Status: confirmed by static inspection**
**Cells:** 10 (C5), 18 (C9)

`predict_Z()` returns `np.concatenate(out)` without asserting that the result is 1-D, has length `len(Z)`, or is finite. Downstream metric helpers assume 1-D probability arrays. The reference implementation states that architecture logits have shape `(batch_size,)` and `dlc.predict_proba()` returns sigmoid probabilities; the notebook applies `torch.sigmoid(model(zb).double())`, which is semantically correct, but the contract is not enforced.

**Recommended correction:**

```python
p = np.concatenate(out)
assert p.shape == (len(Z),) and np.isfinite(p).all()
return p
```

---

### F-05 — CUDA determinism configuration incomplete

**Severity: MEDIUM**
**Status: execution risk; cannot be verified statically**
**Cells:** 2 (C1), 4 (C2)

Cell 4 sets `torch.use_deterministic_algorithms(True, warn_only=True)` and CUDA backend flags, but the notebook never sets:

```python
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
```

Notebook 05 uses this convention. On GPU, deterministic cuBLAS operations may require the environment variable before CUDA context creation. With `warn_only=True`, nondeterminism may be tolerated silently, and the strict `1e-6` clean-reproduction gate could fail for device-level floating-point differences.

**Recommended correction:** set the environment variable before importing torch, immediately after `import os`.

---

### F-06 — Import can write bytecode outside the declared output folder

**Severity: LOW**
**Status: confirmed by static inspection**
**Cells:** 0 (markdown), 2 (C1)

Cell 0 states that the notebook writes only to `Results/inference_time_attacks/`. Cell 2 inserts `CKPT_DIR` into `sys.path` and imports `dl_comparison_models`; without `sys.dont_write_bytecode = True`, Python may create or update `__pycache__` under `Models/deep_learning/comparison/`.

**Recommended correction:**

```python
sys.dont_write_bytecode = True
sys.path.insert(0, str(CKPT_DIR))
import dl_comparison_models as dlc
```

Place the flag before third-party imports if the "writes only to OUT" claim is intended literally.

---

### F-07 — Tautological final output-location check

**Severity: LOW**
**Status: confirmed by static inspection**
**Cells:** 34 (C17)

The final verification uses:

```python
chk(
    "output written only inside Results/inference_time_attacks/",
    all(p.parent == OUT for p in OUT.iterdir() if p.is_file()),
)
```

This is true by construction for every direct file inside `OUT` and cannot detect writes elsewhere.

**Recommended correction:** replace with a real before/after file-path snapshot outside `OUT`, or remove the misleading check and rely on the protected-file hash check plus explicit output-path declarations.

---

### F-08 — `clean_reproduction_check.csv` is written and listed but not verified

**Severity: LOW**
**Status: confirmed by static inspection**
**Cells:** 33 (C16), 34 (C17)

Cell 33 writes `clean_reproduction_check.csv` and lists it in the report's file section. Cell 34's `expected_files` omits it.

**Recommended correction:** add it to `expected_files`:

```python
expected_files += ["clean_reproduction_check.csv"]
```

---

### F-09 — All 90 reconstructed models are cached simultaneously

**Severity: MEDIUM**
**Status: execution risk; stored prior run suggests it was feasible on CPU**
**Cells:** 10 (C5)

`_MODELS` caches one model per `(architecture, modality, seed)` on `DEVICE`. This avoids repeated state-dict loading but keeps 90 `nn.Module` instances resident. On CPU this is probably manageable; on GPU it increases memory pressure and may interact badly with other processes.

**Options:** keep the cache if memory is sufficient, or use a smaller LRU cache / rebuild per run. Do not change this during the audit; decide before a fresh run based on available memory.

---

## 5. Minor issues

### F-10 — Large prediction output and reduced numeric precision

**Severity: LOW**
**Status: confirmed by static inspection**
**Cells:** 18 (C9), 34 (C17)

`SAVE_ALL_SEED_PREDICTIONS=True` writes about 2.65 million rows. Probabilities are written with `float_format="%.7g"`, and cell 34's stored output shows a pandas mixed-type warning for `severity`. This does not invalidate the experiment but affects disk use, downstream precision, and log cleanliness.

---

### F-11 — `scenario_rows()` hardcodes the global threshold

**Severity: LOW**
**Status: confirmed by static inspection**
**Cells:** 18 (C9)

The function signature is `scenario_rows(base, y, p_clean, p_att, thr=THR)`, but internally it uses `THR` rather than `thr`. All current calls use the default, so behavior is correct today.

**Recommended correction:** use `thr` consistently.

---

### F-12 — Misleading flag name `stop_on_repro_failure`

**Severity: LOW**
**Status: confirmed by static inspection**
**Cells:** 4 (C2), 12 (C6), 11 (markdown)

When reproduction failures occur, the notebook excludes them and continues; it does not stop. The documentation accurately says "excluded", but the flag name suggests the opposite. Rename to `exclude_repro_failures` if touched.

---

### F-13 — Section numbering drift

**Severity: LOW**
**Status: confirmed by static inspection**
**Cells:** 17 (markdown), 23 (markdown), 31 (markdown)

Cell 17 is labelled "13a" but appears before sections 10–12; cell 23 says the clean/clean baseline is "section 13". Cosmetic only.

---

### F-14 — Stored outputs are stale relative to any future edits

**Severity: LOW**
**Status: static/hygiene note**
**Cells:** embedded outputs throughout, especially 34 (C17)

The notebook contains prior outputs such as "reproduction OK: 90/90" and "ALL 38 CHECKS PASSED". These are not evidence for the current audit and must not be cited as independent validation. Clear or regenerate outputs only through a real user-controlled run.

---

## 6. Detailed findings by audit checklist

### 1. Checkpoint compatibility

**Overall: PASS, with runtime verification still required.**
**Cells:** 2 (C1), 10 (C5)
**Severity: PASS** (static schema/path audit); runtime load not executed.

- `ARCHS` has six names and `MODALITIES` has three; `ckpt_files` forms all 18 combinations.
- Path pattern `f"{m}_{a}.pt"` matches notebook 05, which writes `MODELS_OUT / f"{m}_{a}.pt"` (`05_deep_learning_comparison.ipynb` export cell).
- All 18 expected checkpoint filenames exist under `Models/deep_learning/comparison/`.
- Cell 10 (C5) loads each file with `dlc.load_checkpoint()` and asserts:
  - `ck["architecture"] == a`;
  - `ck["modality"] == m`;
  - `ck["feature_names"] == FEATURES[m]`;
  - `ck["preprocessing"]["feature_names"] == FEATURES[m]`;
  - `sorted(ck["runs"]) == SEEDS`;
  - threshold equals `THR = 0.5`.
- `get_model()` calls `dlc.model_from_checkpoint(CKPTS[(arch, modality)], seed)`, which is correct: the reference implementation builds the saved architecture with `ckpt["model_config"]`, `len(ckpt["feature_names"])`, and loads `ckpt["runs"][seed]["state_dict"]` (`dl_comparison_models.py:200-204`).
- Saved architecture configurations are preserved because the notebook never rebuilds models from its own hard-coded hyperparameters; it delegates to the checkpoint.
- Five seeds are accessed explicitly through the checkpoint keys and are also asserted. If a runtime reproduction failure occurs, that run is excluded; this is documented but means a fresh run must report the final count of reproduced seeds.

**Cannot be determined statically:** whether all `torch.load()` calls succeed in the current environment, whether state dicts are complete, and whether runtime reproduction passes for all seeds.

---

### 2. Preprocessing

**Overall: PASS, with HIGH finite-value safety gap (`F-01`).**
**Cells:** 8 (C4), 10 (C5), 12 (C6), 14 (C7)
**Severity: PASS for saved-statistics usage; HIGH for infinity handling.**

- Feature order is loaded from `feature_names_and_preprocessing.json`, which statically shows 29 network, 32 radio, 61 multimodal features and `multimodal = network + radio` in that order.
- Cell 10 (C5) takes `PREP` directly from checkpoints and verifies identical `median`, `mean`, and `scale` across architectures for each modality.
- Cell 12 (C6) calls only `dlc.apply_preprocessing(df.iloc[idx_test][FEATURES[m]], PREP[m])`; no imputer/scaler is fitted on test data.
- `dlc.apply_preprocessing()` reorders columns by `pre["feature_names"]`, applies saved median imputation, and standardises with saved mean/scale.
- Cell 14 (C7) constructs dropout values from saved median/mean/scale and checks equivalence against `dlc.apply_preprocessing()` on injected NaNs.
- No `fit`, `fit_transform`, `StandardScaler`, or `SimpleImputer` call exists in the notebook.

**Issue:** only NaNs are checked, not infinities; see `F-01`. The saved `other_frac` scale is approximately `6.76e-18`, making this a real defensive concern.

**Cannot be determined statically:** whether the current clean or attacked arrays contain infinities at runtime.

---

### 3. Clean prediction reproduction

**Overall: structurally PASS; success cannot be claimed.**
**Cells:** 10 (C5), 12 (C6), 18 (C9), 34 (C17)
**Severity: PASS for dimensional logic; HIGH for gate issue (`F-02`); MEDIUM for prediction-output validation (`F-04`).**

- `predict_Z()` applies `torch.sigmoid()` to the model's `(batch_size,)` logits and returns a 1-D probability array. This matches the semantics of `dlc.predict_proba()` (`dl_comparison_models.py:216-222`), which also applies sigmoid to `(B,)` logits. No logit is mistaken for a probability.
- Input to `predict_Z()` is model-space `Z`, not a raw DataFrame; this is appropriate for attacking standardised features.
- Saved predictions are read from `test_predictions.csv`, filtered to `partition == "test"`, grouped by `(architecture, modality, seed)`, restricted to exact `row_index` values, and aligned in dataset order via `g.loc[idx_test]`.
- `window_id` and `y_true` are compared to the manifest-derived test metadata.
- The probability comparison is dimensionally correct: 802 predicted probabilities versus 802 saved `y_probability` values.
- The saved positive-class convention matches the checkpoint (`positive_class = 1`) and `y_pred = (p >= 0.5)` in notebook 05.
- Tolerance `1e-6` is stricter than the maximum difference recorded in notebook 05's report (`5.84e-09`) and is therefore appropriate in principle.

**Issue:** the OK criterion ignores threshold flips (`F-02`).
**Issue:** no explicit assertion that `predict_Z()` returned a finite 1-D array of length 802 (`F-04`).

**Cannot be determined statically:** actual numerical agreement between current checkpoints and saved predictions. The embedded "90/90" output is a prior artifact and is not accepted as independent evidence here.

---

### 4. Attack implementation

**Overall: PASS on definitions and implementation logic.**
**Cells:** 14 (C7), 16 (C8), 18 (C9)
**Severity: PASS, with finite-value caveat (`F-01`).**

Static review of all seven attack families:

| Attack | Cell | Static finding |
|---|---|---|
| Gaussian noise | 14 (C7) | Four sigmas `0.1, 0.25, 0.5, 1.0`; one deterministic standard-normal draw per block scaled by sigma; affects all block features. Correct. |
| Bias manipulation | 14 (C7) | `+/-0.5, +/-1, +/-2`; 25% fixed subset via shared seeded permutation. Correct. |
| Scaling | 14 (C7) | Factors `0.5, 2, 4`; 25% fixed subset; scaling in standardised space about the training mean. Correct. |
| Random feature corruption | 14 (C7) | Fractions `10%, 25%, 50%`; nested subsets; deterministic standard-normal replacement values. Correct. |
| Partial sensor dropout | 14 (C7) | 25% and 50%; replaced by saved median in z-space; equivalence check against `dlc.apply_preprocessing()` on NaNs. Correct. |
| Full sensor dropout | 14 (C7) | 100%; all block features replaced by saved median z. Correct. |
| Combined | 14 (C7) | Low/medium/high `sigma=0.1/0.25/0.5`, `delta=0.5/1/2`, corruption `10%/25%/50%`, bias fraction fixed at 25%; order bias → corruption → noise. Correct. |

Additional static checks:

- `ATTACK_GRID` has 22 unique IDs, asserted in cell 14 (C7).
- `feature_subset()` returns sorted indices, and the returned `affected_features` are written to `attack_configuration.json` in cell 16 (C8).
- `noise()` and `corr_vals()` derive seeds from `stable_seed(ATTACK_SEED, block, stream, "eps"/"values")`; subset seeds derive from `stable_seed(ATTACK_SEED, block, family, "subset")`. Deterministic and independent of labels.
- No attack function reads `y_test`, `META`, or model outputs.
- `perturb_block()` copies `Zb`; `attacked_input()` copies `Z_CLEAN[modality]`. Clean source arrays are not mutated.
- Array shapes are conceptually preserved: `(n_test, F_block)` for blocks and `(n_test, 61)` for multimodal inputs.
- Boundary self-tests in cell 16 (C8) confirm that manipulating one multimodal block leaves the other bit-identical for the Gaussian-noise example.

**Caveat:** shape preservation is implemented by assignment, but finite-value preservation is not asserted (`F-01`).

---

### 5. Multimodal experiments

**Overall: PASS, with hardcoded-index caveat (`F-03`).**
**Cells:** 12 (C6), 16 (C8), 24 (C12), 26 (C13)
**Severity: PASS.**

- Clean/Clean: cell 26 (C13) builds `CLEAN_DF` from `CLEAN_P` for each multimodal model, i.e. the reproduced clean test predictions.
- Network manipulated + Radio clean: `run_condition("multimodal", "network")` in cell 24 (C12) replaces only `Z[:, NET_SL]`; boundary test confirms radio slice unchanged.
- Network clean + Radio manipulated: `run_condition("multimodal", "radio")` replaces only `Z[:, RAD_SL]`; boundary test confirms network slice unchanged.
- Both manipulated: `TARGET_BLOCKS["both"]` replaces both slices.
- Cell 12 (C6) verifies `Z_CLEAN["multimodal"][:, NET_SL]` equals standalone network z and `Z_CLEAN["multimodal"][:, RAD_SL]` equals standalone radio z.
- Saved metadata statically confirms the 29/32 boundary and multimodal ordering.

**Weakness:** the boundaries are hardcoded as `0:29` and `29:61` rather than derived from `FEATURES` lengths (`F-03`), although assertions currently guard them.

---

### 6. Evaluation methodology

**Overall: PASS on definitions; minor implementation caveats.**
**Cells:** 18 (C9), 26 (C13), 34 (C17)
**Severity: PASS for metric semantics; LOW/MEDIUM caveats below.**

- `clf_metrics()` uses attack class `1` as positive, `p >= thr`, `confusion_matrix(..., labels=[0,1])`, and matches notebook 05's definitions.
- Accuracy, precision, recall, F1, macro-F1, ROC-AUC, PR-AUC, FPR, and FNR are all computed on binary labels and 1-D probability arrays.
- ROC-AUC and PR-AUC are guarded when the label vector contains one class, a safe refinement over notebook 05.
- FPR = `fp/(fp+tn)`, FNR = `fn/(fn+tp)`, with NaN when the denominator is zero.
- `shift_metrics()` computes flip rate, mean signed probability change, attack/benign-specific mean change, mean absolute change, and ESR.
- ESR denominator is attack windows with `y_true == 1` and clean prediction `>= 0.5`; numerator is those that become `< 0.5`. Undefined ESR is represented as NaN. Final verification checks `esr.isna() == (esr_denominator == 0)`.
- `scenario_rows()` uses the manifest-derived scenario labels, and cell 8 (C4) asserts label constancy per scenario.
- Cell 26 (C13) computes per-seed and mean/std summaries; standard deviation uses `ddof=1`, appropriate for seed variability.
- Confusion-matrix sums are verified against `n_test` in cell 34 (C17).

**Caveats:**

- No explicit finite/shape check on probabilities (`F-04`).
- `scenario_rows()` ignores its `thr` argument (`F-11`).
- Per-seed variability is initialisation variance only, not a confidence interval; this limitation is documented in cell 31 and in the upstream report.

---

### 7. Research integrity

**Overall: mostly sound; limitations appropriately acknowledged.**
**Cells:** 0, 8, 12, 14, 16, 30, 31, 33, 34
**Severity: PASS with unresolved process-level unknowns.**

Static evidence:

- No test-data fitting: preprocessing comes from checkpoints fitted on training rows only.
- No test-set threshold tuning: `THR = 0.5`, asserted against each checkpoint.
- No attack tuning on test results inside the notebook: attack grid and seeds are defined in cells 4/6/14 before any attack results are computed; display of clean z-ranges occurs after grid definition.
- No model selection using test data: model weights and `primary_seed` come from checkpoints selected on validation loss in notebook 05.
- Clean baseline is derived from the same saved test predictions used for reproduction, not from a separate optimistic source.
- Cell 31 explicitly states the known limitations: 35 scenarios, six benign scenarios overall, one benign test scenario, date/session confounding, non-temporal CNN/LSTM/GRU representations, synthetic/unvalidated attacks, UTC-second-level alignment, and no robustness certification.

**Research-integrity risks:**

- Text in cells 0/31/33 says test results were not used to choose attacks/severities/thresholds/models. The notebook order supports this, but a human decision process outside the notebook cannot be verified from files. Marked **UNVERIFIABLE**.
- FPR rests on one benign test scenario; seed spread does not quantify scenario uncertainty. This is a statistical weakness, not an implementation error.
- The notebook uses strong language such as "robustness ranking"; it repeatedly qualifies these as descriptive and not certification. This is acceptable, but should be preserved in any downstream reporting.
- `configuration_used.json` reports 86 of 90 runs restored from cache. This does not invalidate the checkpoints, but it means training-time values in checkpoint metadata partly describe an earlier execution. Not relevant to inference-time attacks except for provenance.

**Cannot be determined statically:** whether real attacker capabilities are plausible; whether the synthetic perturbations correspond to physically/protocol-consistent telemetry changes; whether the human research process involved any unrecorded test-informed choices.

---

### 8. Efficiency

**Overall: mostly reasonable, with two notable risks.**
**Cells:** 10 (C5), 16 (C8), 18 (C9), 26 (C13), 34 (C17)

Efficient choices:

- Checkpoints are loaded once into `CKPTS`; not reloaded per attack.
- Models are cached in `_MODELS`; state dicts are not repeatedly read from disk.
- Perturbations are generated once per `(block, attack)` in `PERT` and reused across architectures/seeds.
- Predictions are appended incrementally rather than accumulated in memory as one giant DataFrame.
- Final CSV verification is chunked.

Risks:

- `F-09`: 90 models resident on device.
- `F-10`: `attack_predictions.csv` can reach several hundred MB; `float_format="%.7g"` limits precision.
- Cell 26 builds `SCEN_DF` with 23,100 rows and `PER_SEED` with 3,300 rows; acceptable in memory.
- Cell 28 creates 13 figures and embeds images in the notebook; notebook file size can grow substantially if outputs are saved.

**No CRITICAL efficiency defect found.**

---

## 7. Findings register

| ID | Severity | Status | Cells | Summary |
|---|---|---|---|---|
| F-01 | HIGH | Static-confirmed issue; runtime magnitude unknown | 10, 12, 14, 16, 18 | NaN-only checks; infinity not rejected despite near-zero saved scale |
| F-02 | HIGH | Static-confirmed issue | 12 | Clean reproduction OK ignores threshold flips |
| F-03 | MEDIUM | Static-confirmed issue | 2, 12, 16 | Feature boundaries hardcoded instead of derived from saved metadata |
| F-04 | MEDIUM | Static-confirmed issue | 10, 18 | No explicit 1-D/finite assertion on `predict_Z()` output |
| F-05 | MEDIUM | Execution risk | 2, 4 | Missing `CUBLAS_WORKSPACE_CONFIG` for deterministic CUDA |
| F-06 | LOW | Static-confirmed issue | 0, 2 | Import can write bytecode outside declared output folder |
| F-07 | LOW | Static-confirmed issue | 34 | Tautological output-location verification |
| F-08 | LOW | Static-confirmed issue | 33, 34 | `clean_reproduction_check.csv` not in expected files |
| F-09 | MEDIUM | Execution risk | 10 | 90 models cached simultaneously |
| F-10 | LOW | Static-confirmed issue | 18, 34 | Large prediction CSV, 7-digit probability formatting, severity dtype warning |
| F-11 | LOW | Static-confirmed issue | 18 | `scenario_rows()` ignores its `thr` argument |
| F-12 | LOW | Static-confirmed issue | 4, 11, 12 | Misleading `stop_on_repro_failure` flag name |
| F-13 | LOW | Static-confirmed issue | 17, 23, 31 | Section numbering drift |
| F-14 | LOW | Hygiene note | embedded outputs, 34 | Stored outputs are prior artifacts, not audit evidence |
| F-15 | PASS | Static-confirmed | 2, 10 | Checkpoint paths, 18 combos, five seeds, model reconstruction |
| F-16 | PASS | Static-confirmed | 8, 10, 12 | Saved preprocessing/order, no test fitting |
| F-17 | PASS | Static-confirmed | 12 | Clean comparison dimensional logic and tolerance |
| F-18 | PASS | Static-confirmed | 14, 16 | Attack definitions, indices, reproducibility, no label dependence |
| F-19 | PASS | Static-confirmed | 12, 16, 24 | Multimodal clean/one-sensor/both-sensor logic |
| F-20 | PASS | Static-confirmed | 18, 26 | Metric definitions match upstream methodology |
| F-21 | PASS | Static-confirmed | 0, 14, 30, 31, 33 | Documented limitations and no in-notebook test tuning |
| F-22 | UNVERIFIABLE | Requires execution | 12, 34 | Actual numeric clean reproduction success |
| F-23 | UNVERIFIABLE | Requires execution/process knowledge | 0, 14, 31 | Human attack-selection process and real-world validity |

---

## 8. Recommended corrections

Priority order for a future edited copy (this audit did not modify the notebook):

1. **Finite-value safety (F-01, F-04)**

```python
def predict_Z(arch, modality, seed, Z):
    model = get_model(arch, modality, seed)
    out = []
    for i in range(0, len(Z), CONFIG["eval_batch_size"]):
        zb = torch.from_numpy(
            np.ascontiguousarray(Z[i:i + CONFIG["eval_batch_size"]], dtype=np.float32)
        ).to(DEVICE)
        out.append(torch.sigmoid(model(zb).double()).cpu().numpy())
    p = np.concatenate(out)
    assert p.shape == (len(Z),) and np.isfinite(p).all()
    return p
```

```python
Z = Z.astype(np.float32)
assert Z.shape == Zb.shape and np.isfinite(Z).all()
```

2. **Reproduction gate (F-02)**

```python
repro_ok = (
    d.max() <= CONFIG["repro_tolerance"]
    and row["pred_flips_vs_saved"] == 0
)
if repro_ok:
    row["status"] = "OK"
    CLEAN_P[(a, m, s)] = p
else:
    row["status"] = (
        f"FAILED: max diff {d.max():.3e}, "
        f"threshold flips {row['pred_flips_vs_saved']}"
    )
```

3. **Metadata-derived boundaries (F-03)**

```python
NET_N = len(FEATURES["network"])
RAD_N = len(FEATURES["radio"])
NET_SL = slice(0, NET_N)
RAD_SL = slice(NET_N, NET_N + RAD_N)
assert NET_N + RAD_N == len(FEATURES["multimodal"])
```

4. **Determinism and bytecode hygiene (F-05, F-06)**

```python
import os, sys
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
sys.dont_write_bytecode = True
```

Place before torch and `dl_comparison_models` imports.

5. **Final verification (F-07, F-08)**

```python
expected_files = [
    ...,
    "attack_report.md",
    "clean_reproduction_check.csv",
]
```

Replace the tautological output-location check with a real before/after snapshot of file paths outside `OUT`, or remove it.

6. **Scenario threshold consistency (F-11)**

```python
def scenario_rows(base, y, p_clean, p_att, thr=THR):
    ...
    cp, ap = (pc >= thr).astype(int), (pa >= thr).astype(int)
```

---

## 9. Pre-execution smoke-test plan

Do not begin the full experiment until these pass. This is a plan only; none of it was executed during this audit.

1. **Environment and root check**
   - Start a fresh kernel with the project root as `cwd`.
   - Confirm root discovery in cell 2 (C1) resolves to the repository containing `Multimodal Datasets/multimodal_dataset_v2.csv` and `Results/split_manifest.csv`.
   - Confirm `torch`, `numpy`, `pandas`, `scikit-learn`, `matplotlib`, and `scipy` import.

2. **Protected-file baseline**
   - Confirm `HASH_BEFORE` in cell 6 (C3) contains all expected protected files, including 18 checkpoints and the model utility.
   - Ensure `Results/inference_time_attacks/` is either freshly created or intentionally empty/archived, so stale outputs cannot masquerade as new results.

3. **Checkpoint static validation**
   - Run only cells 2, 4, 6, 8, and 10 (C1–C5).
   - Confirm 18 checkpoints and five seeds per checkpoint.
   - Confirm `dlc.model_from_checkpoint()` succeeds for a small representative set: one architecture for network, radio, and multimodal, with both primary and non-primary seeds.
   - Confirm no checkpoint file hash changes.

4. **Preprocessing sanity**
   - For one modality, compare `dlc.apply_preprocessing(X, ckpt["preprocessing"])` against the notebook's `Z_CLEAN` slice.
   - Assert `np.isfinite(Z_CLEAN[m]).all()` for all modalities.
   - Confirm multimodal slices equal the standalone blocks exactly or within the stated tolerance.

5. **Clean reproduction mini-gate**
   - For one `(architecture, modality, seed)` per modality, compare `predict_Z()` against the corresponding rows of `test_predictions.csv`.
   - Require both `max_abs_diff <= 1e-6` and zero threshold flips.
   - Do not relax the tolerance or change the threshold.

6. **Attack-function unit checks**
   - Run cells 14 and 16 (C7, C8) self-tests.
   - Verify each of the 22 attack IDs returns shape `(n_test, F_block)` and finite values.
   - Verify affected indices are sorted, unique, and in range.
   - Verify the untouched multimodal block is bit-identical for each target.
   - Verify no clean source array changes identity/contents.

7. **Metrics unit checks**
   - Construct a tiny synthetic binary `y` and 1-D finite `p` locally in a scratch session (not part of the notebook) to verify confusion-matrix ordering and FPR/FNR.
   - Verify ESR is NaN when the denominator is zero.

8. **Output-path dry run**
   - Confirm all intended filenames are under `Results/inference_time_attacks/`.
   - Confirm `clean_reproduction_check.csv` is included in the verification list.
   - Decide whether to set `SAVE_ALL_SEED_PREDICTIONS=False` for an initial timing smoke run, then restore `True` for the full experiment. This is a temporary operational decision, not a change to attack/threshold methodology.

9. **Full run only after all above pass**
   - Restart kernel and run all cells once.
   - Do not manually rerun individual cells after inspecting intermediate results, because that would break cell-order provenance.
   - Preserve the executed notebook and output hashes.

---

## 10. Final checklist before running complete experiments

- [ ] Apply F-01: all clean and attacked arrays assert finite values.
- [ ] Apply F-02: reproduction requires zero threshold flips.
- [ ] Apply F-03: network/radio boundaries derived from saved feature metadata.
- [ ] Apply F-04: `predict_Z()` asserts 1-D, correct length, finite probabilities.
- [ ] Apply F-05: `CUBLAS_WORKSPACE_CONFIG` set before torch CUDA context.
- [ ] Apply F-06: `sys.dont_write_bytecode = True` before imports.
- [ ] Apply F-07/F-08: verification checks real file outputs, including `clean_reproduction_check.csv`.
- [ ] Confirm protected-file hashes are captured before any experiment cell.
- [ ] Confirm all 18 checkpoints and five seeds pass structural validation.
- [ ] Confirm threshold remains exactly `0.5` and is not tuned.
- [ ] Confirm attack grid remains the 22 pre-specified configurations.
- [ ] Confirm no attack uses labels, scenarios, or model outputs.
- [ ] Confirm multimodal mapping uses network `[0:29]` and radio `[29:61]` derived from metadata.
- [ ] Confirm sufficient disk space for a multi-hundred-MB `attack_predictions.csv`.
- [ ] Confirm sufficient memory for the model cache or revise caching strategy.
- [ ] Confirm output folder is clean or intentionally archived.
- [ ] Complete the smoke-test plan without modifying attack definitions or thresholds.
- [ ] Record final reproduction counts instead of relying on embedded prior outputs.
- [ ] Keep all limitations from cell 31 and the report in any downstream presentation.

---

## 11. Things that cannot be determined from available files

- Whether the current runtime reproduction of all 90 seed-specific clean predictions succeeds.
- Whether any clean or attacked array actually contains `±inf` in a fresh run.
- Whether GPU execution is deterministic without the suggested environment variable.
- Whether the prior execution's embedded outputs were produced by exactly the current source state.
- Whether human choices outside the notebook used test results to select attacks or severities.
- Whether the synthetic perturbations are physically or protocol feasible in a real O-RAN deployment.
- Whether conclusions generalise beyond the single, confounded dataset split.

---

## 12. Confirmation

No notebook cells were executed. No models were trained. No inference was performed. No experiments were run. No packages were installed. No existing project files were modified during this audit. The only file created for this task is `AUDIT_REPORT.md` in the project root.
