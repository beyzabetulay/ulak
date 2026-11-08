# Kia recording-grouped validation: timing ablation and small parameter check

This is a real-data, **inner-validation-only** comparison on the local HCRL Kia
feature parquet. No new outer-test predictions were made for this analysis.
Earlier outer-test outcomes had already been inspected and motivated the
experiment; these results are exploratory, not an untouched final evaluation.
Run commands and feature definitions are in `experiments/kia_decision_tree/XGBOOST.md`.

Four variants share ID, DLC and byte features: A standard, B adds `iat_id`, C
adds `iat_bus`, D adds both. The tree uses depth 6 and seed 42, matching the
original tree; XGBoost uses 100 estimators, learning rate 0.1, depths 3/6,
threshold 0.5 and otherwise the baseline settings. Existing XGBoost A and D
validation results were reused; B/C and all tree results were newly computed.
All ten output files have matching input, outer-manifest and validation-manifest
hashes. The earlier manifests do not bind individual index arrays by hash.
No normalizing or model fitting uses validation rows; indices remain grouped by
recording. The official release fold and all outer test predictions were skipped.

## Mean attack F1 on inner validation

Each cell is the unweighted mean of four fold F1 values. XGBoost cells report
depth 3 / depth 6; tree cells use depth 6. A row identifies the attack held out
from the *outer* training data. That attack is therefore absent from the row's
inner validation; for example, the Injection row does not measure Injection
detection. Different rows cannot be interpreted as per-attack scores.

| Outer holdout | Model | A: standard | B: + iat_id | C: + iat_bus | D: + both |
|---|---|---:|---:|---:|---:|
| DoS | XGBoost | 0.418 / 0.495 | 0.668 / 0.560 | 0.453 / 0.418 | 0.566 / 0.572 |
| DoS | Tree | 0.497 | 0.389 | 0.487 | 0.400 |
| Injection | XGBoost | 0.005 / 0.001 | 0.456 / 0.270 | 0.016 / 0.059 | 0.346 / 0.339 |
| Injection | Tree | 0.002 | 0.483 | 0.054 | 0.330 |
| Spoofing | XGBoost | 0.472 / 0.467 | 0.413 / 0.472 | 0.467 / 0.569 | 0.574 / 0.647 |
| Spoofing | Tree | 0.304 | 0.262 | 0.403 | 0.497 |
| Replay | XGBoost | 0.373 / 0.529 | 0.372 / 0.541 | 0.386 / 0.528 | 0.371 / 0.588 |
| Replay | Tree | 0.466 | 0.418 | 0.307 | 0.418 |

No variant dominates all outer settings. The four folds are built from very few
recordings; some have only 130 attacks and session independence is unverified.
These means do not demonstrate that a model generalizes to the outer holdout.

## Injection-held-out inner validation: false alarms and fold variation

XGBoost depth is chosen by highest mean F1 among 3/6 separately for each
variant. Tree depth is fixed at 6. Precision, recall and FPR below are pooled
over validation frames; mean F1 is unweighted across folds and should not be
reconstructed from pooled precision/recall. Four fold F1 scores show variation.

| Model | Variant | Depth | Mean F1 | Pooled recall | Pooled precision | Pooled FPR | Fold F1 |
|---|---|---:|---:|---:|---:|---:|---|
| XGBoost | A | 3 | 0.005 | 0.003 | 0.013 | 0.028 | 0.000 / 0.000 / 0.000 / 0.019 |
| XGBoost | B | 3 | 0.456 | 0.376 | 0.842 | 0.009 | 0.084 / 0.987 / 0.000 / 0.754 |
| XGBoost | C | 6 | 0.059 | 0.043 | 0.143 | 0.033 | 0.000 / 0.000 / 0.000 / 0.237 |
| XGBoost | D | 3 | 0.346 | 0.202 | 0.743 | 0.009 | 0.089 / 0.522 / 0.000 / 0.772 |
| Tree | A | 6 | 0.002 | 0.001 | 0.007 | 0.012 | 0.000 / 0.000 / 0.000 / 0.007 |
| Tree | B | 6 | 0.483 | 0.465 | 0.696 | 0.026 | 0.268 / 0.932 / 0.000 / 0.731 |
| Tree | C | 6 | 0.054 | 0.018 | 0.180 | 0.011 | 0.000 / 0.000 / 0.000 / 0.215 |
| Tree | D | 6 | 0.330 | 0.223 | 0.575 | 0.021 | 0.242 / 0.287 / 0.001 / 0.787 |

For this validation setting B has the highest mean F1 for both models. The tree
has higher pooled recall but about 2.9 times the normal-frame FPR of XGBoost B.
Fold 3 contains only 130 attack frames and receives zero attack F1 for both B
models. These results describe the validation recordings, not Injection.

## Small parameter follow-up on XGBoost B, depth 3

Positive class weight 1 or 3 is applied during training; the same fold model's
probabilities are evaluated at all three fixed thresholds. The grid was chosen
after initial results, and only two weights and three thresholds are explored.
F1 is mean per fold; precision, recall and FPR are pooled across frames.

| Weight | Threshold | Mean F1 | Pooled recall | Pooled precision | Pooled FPR | False alarms |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.3 | 0.433 | 0.425 | 0.673 | 0.0267 | 50,365 |
| 1 | 0.5 | 0.456 | 0.376 | 0.842 | 0.0091 | 17,229 |
| 1 | 0.7 | 0.186 | 0.144 | 0.844 | 0.0034 | 6,482 |
| 3 | 0.3 | 0.377 | 0.431 | 0.524 | 0.0505 | 95,378 |
| 3 | 0.5 | 0.431 | 0.411 | 0.686 | 0.0243 | 45,941 |
| 3 | 0.7 | 0.458 | 0.376 | 0.842 | 0.0091 | 17,133 |

The tiny 0.002 mean-F1 difference between weight 3/threshold 0.7 and weight
1/threshold 0.5 is not evidence of a reliable winner. Lower thresholds trade
more recall for false alarms. No operational false-alarm budget was defined.
Weight-1/threshold-0.5 reproduced all 16 earlier B validation fold metrics
exactly. No outer test was revisited after selecting these candidates.
