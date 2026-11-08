# Kia validation: payload transitions and CatBoost

Real-data, recording-grouped **inner validation only**. No new outer-test
predictions were generated. Prior outer-test results and the 130-frame
Spoofing recording were inspected before choosing these features, so this is an
exploratory comparison rather than an independent estimate. The outer held-out
attack does not appear in that row's inner validation; rows are not attack-type
scores. The official release fold was not evaluated.

The baseline is ID, DLC, bytes and `iat_id`. The sequence variant adds changed
bit count and a repeat indicator relative to the preceding same-ID message,
within each recording and stable timestamp order. Repeat is derived from the
bit count and adds no independent information. Missing transitions and input
bytes use -1. Label changes do not affect feature calculation, and tests check
row-position alignment and recording boundaries. The sequence feature code
hash is stored in the ignored result JSON. Timestamp ordering does not prove
live acquisition order, and individual split arrays are not hash-bound.

XGBoost and CatBoost are compared using identical numeric inputs, including a
numeric CAN ID. Both use 100 trees, depths 3/6, learning rate 0.1, seed 42,
four CPU threads, class weight 1 and threshold 0.5. CatBoost 1.2.10 uses Plain
boosting and Logloss, with file writing disabled. Other library defaults and
tree construction differ. This does not test CatBoost's categorical-ID handling
or ordered boosting. Prior XGBoost baseline metrics were reused after checking
input and manifest hashes; all four XGBoost sequence and CatBoost settings were
newly evaluated. Outputs remain in ignored `local_outputs/ablation_*.json`.

## Mean validation F1

Each cell is depth 3 / depth 6, unweighted across four folds. Folds have unequal
class supports, only a few recordings and no verified session independence.
FPR is reported separately below; mean F1 is not pooled-frame F1.

| Outer held out | XGBoost + iat_id | XGBoost + sequence | CatBoost + iat_id |
|---|---:|---:|---:|
| DoS | 0.668 / 0.560 | 0.572 / 0.656 | 0.508 / 0.674 |
| Injection | 0.456 / 0.270 | 0.305 / 0.225 | 0.493 / 0.373 |
| Spoofing | 0.413 / 0.472 | 0.717 / 0.650 | 0.332 / 0.421 |
| Replay | 0.372 / 0.541 | 0.590 / 0.393 | 0.347 / 0.382 |

For Injection-held-out inner validation at depth 3, pooled normal FPR is 0.91%
for XGBoost baseline, 0.47% for XGBoost sequence and 1.09% for CatBoost. Mean
F1 is 0.456, 0.305 and 0.493 respectively. CatBoost's 0.037 F1 advantage over
the baseline is based on only four unequal folds and is not a proven general
improvement. The attack type Injection is absent from these validation rows.

In the inner fold containing the 130 final-first Spoofing attack frames, all
three variants at both depths still detect 0/130. These frames contributed to
feature design before this experiment, and even a positive result on them would
not be an untouched validation result. A single record cannot establish whether
sequence features or CatBoost are broadly useful. Depth changes can trade F1
against false alarms differently across folds.

Run `python experiments/kia_validation_ablation.py --model xgboost --variant sequence`
and `python experiments/kia_validation_ablation.py --model catboost --variant iat_id`.
The earlier baseline is `--model xgboost --variant iat_id`. The script verifies
input and manifest hashes, row partition coverage and recording separation.
Detailed per-fold support, precision, recall, F1, FPR, parameters and versions
are in local ignored JSON files. Results do not justify choosing a deployment
model or tuning against previously inspected outer tests.
