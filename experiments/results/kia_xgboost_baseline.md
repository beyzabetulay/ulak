# Kia Soul XGBoost baseline: unseen attacks

Real-data experiment on the local HCRL Kia Soul feature parquet and its existing
recording-based outer splits. Run and environment details are in
`experiments/kia_decision_tree/XGBOOST.md`; no raw frames or generated split
indices are committed. This is not a synthetic-data performance result.

Python 3.14.5, NumPy 2.4.6, pandas 2.3.3, scikit-learn 1.9.0 and XGBoost
3.4.1. The selected depth maximizes mean attack F1 across four inner recording
folds from depths 3 and 6. Both use 100 estimators, learning rate 0.1, threshold
0.5 and standard ID/DLC/byte features; no timing or class weighting. The
four unseen-attack test sets were already inspected in earlier experiments.
The official release test is not evaluated here.

## Validation

Attack F1 per inner fold, in manifest order; each fold has both classes. Folds
have different recordings, attack types and supports, and the omitted attack
type is absent from the inner validation. Session independence is unverified.

| Held out | Depth | Fold 1 | Fold 2 | Fold 3 | Fold 4 | Mean |
|---|---:|---:|---:|---:|---:|---:|
| DoS | 3 | 0.000 | 0.927 | 0.121 | 0.623 | 0.418 |
| DoS | 6 | 0.000 | 0.940 | 0.695 | 0.345 | 0.495 |
| Injection | 3 | 0.000 | 0.000 | 0.000 | 0.019 | 0.005 |
| Injection | 6 | 0.000 | 0.000 | 0.000 | 0.005 | 0.001 |
| Spoofing | 3 | 0.000 | 0.910 | 0.977 | 0.000 | 0.472 |
| Spoofing | 6 | 0.000 | 0.918 | 0.951 | 0.000 | 0.467 |
| Replay | 3 | 0.984 | 0.000 | 0.000 | 0.506 | 0.373 |
| Replay | 6 | 0.996 | 0.636 | 0.000 | 0.486 | 0.529 |

Attack support by fold is respectively: DoS 155,640/119,551/71,850/21,743;
Injection 155,640/67,080/130/20,842; Spoofing 155,640/119,551/21,613/16,072;
Replay 119,551/67,080/130/42,455. Fold-level FPR and full confusion counts are
available in the ignored local JSON output. In the selected Injection model,
fold 4's false-positive rate was 7.73%; in the selected DoS model, fold 4's
was 9.44%. Selection by mean F1 does not impose a false-alarm constraint.

## Outer test comparison

Tree results are the committed notebook's prior fixed-depth-6 results, not a
tree tuned with the new validation procedure. Both models use the same feature
contract and outer recordings; their model-selection procedures differ. Values
are frame counts; FPR is false alarms divided by normal frames.

| Held out | Model | Depth | Attack TP / total | Recall | Precision | F1 | Normal FP / total | FPR |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| DoS | Tree | 6 | 0 / 16,072 | 0.000 | 0.000 | 0.000 | 0 / 103,928 | 0.0000 |
| DoS | XGBoost | 6 | 0 / 16,072 | 0.000 | 0.000 | 0.000 | 0 / 103,928 | 0.0000 |
| Injection | Tree | 6 | 76,713 / 141,164 | 0.543 | 0.994 | 0.703 | 437 / 462,836 | 0.0009 |
| Injection | XGBoost | 3 | 51,945 / 141,164 | 0.368 | 0.965 | 0.533 | 1,907 / 462,836 | 0.0041 |
| Spoofing | Tree | 6 | 37,447 / 71,980 | 0.520 | 0.997 | 0.684 | 117 / 708,908 | 0.0002 |
| Spoofing | XGBoost | 3 | 38,096 / 71,980 | 0.529 | 1.000 | 0.692 | 10 / 708,908 | 0.0000 |
| Replay | Tree | 6 | 0 / 155,640 | 0.000 | 0.000 | 0.000 | 0 / 410,698 | 0.0000 |
| Replay | XGBoost | 6 | 0 / 155,640 | 0.000 | 0.000 | 0.000 | 0 / 410,698 | 0.0000 |

Precision is conventionally reported as zero when a model predicts no attacks;
it is mathematically undefined in that case. Rounded FPR 0.0000 for Spoofing
XGBoost corresponds to 10 false alarms, not zero. This small model comparison
does not establish that boosting cannot detect DoS or Replay. Timing features,
other configurations and additional independent recordings remain untested.
