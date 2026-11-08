# Kia XGBoost baseline

This experiment compares two fixed XGBoost configurations against the same
Kia standard feature contract used by the decision-tree notebook. An optional
variant adds the `iat_id` and `iat_bus` timing features. It does not change the
notebook or inspect the official release test.

Install `experiments/requirements.txt`, prepare the Kia parquet and outer
manifest as described in `splits/README.md`, and generate the balanced inner
folds with `python splits/make_kia_validation.py`. Then run:

```sh
python experiments/kia_xgboost_baseline.py
python experiments/kia_xgboost_baseline.py --variant standard_timing
python experiments/kia_xgboost_baseline.py --variant iat_id --fold unseen_injection
```

The outputs are `experiments/kia_decision_tree/local_outputs/xgboost_standard.json`
and `xgboost_standard_timing.json`, which are ignored by Git. Use `--input`,
`--splits-dir`, and `--output` to override
paths. The input and outer manifest hashes are verified against the validation
manifest, and input row positions, recording separation and validation coverage
are checked before fitting. The JSON includes hashes, versions, configurations,
fold training and validation confusion counts, attack precision/recall/F1, normal false-positive rate,
and elapsed fitting plus prediction times. Index arrays are validated but not
cryptographically bound to their own hashes.

For each unseen attack outer split, use only its training rows for inner
validation. Compare max depth 3 and 6, both with 100 estimators, learning rate
0.1, histogram trees, four CPU threads, seed 42 and a fixed 0.5 decision
threshold. Choose the highest unweighted mean of the four validation attack F1
scores (the first configuration wins ties), refit on all outer training rows,
and evaluate once on that outer test. This is a small predefined comparison,
not a comprehensive hyperparameter search. There is no class weighting or
early stopping. The standard variant uses CAN ID, DLC and eight payload bytes,
as in the decision-tree notebook. The timing variant additionally uses time
since the previous frame on the bus and with the same ID, computed within each
recording. Missing values use -1. The `bus_count_100ms` feature is excluded.
Timing comparisons were planned after earlier test results were observed;
their outer test scores are exploratory rather than a pristine final evaluation.

## Validation-only feature ablation

The baseline runner also accepts `iat_id` and `iat_bus` variants and an optional
`--fold` to restrict evaluation to one unseen-attack outer setting. These commands
do evaluate the chosen outer test after validation selection; they differ from
the validation-only commands below. Variant outputs are saved separately.

Run `python experiments/kia_validation_ablation.py --model xgboost --variant iat_id`
and repeat with `iat_bus`, `standard` or `both` to compare the four feature
sets. Replace `xgboost` with `tree` to evaluate a depth-6 decision tree. XGBoost
uses both depths 3 and 6; a tree uses the existing notebook's depth 6. Each
command saves fold counts, precision, recall, F1, FPR, hashes and versions to
an ignored `local_outputs/ablation_<model>_<variant>.json` file. It uses only
the four inner validation folds from each unseen-attack outer training split;
it does not fit on or predict outer-test rows. The official split is skipped.
It verifies recording separation and partition coverage, but individual index
files are not cryptographically bound by the outer manifest.

Report individual fold support and false positives alongside the unweighted
mean F1. The outer held-out attack is absent from the corresponding inner folds;
their scores do not directly measure that attack. Outcomes depend on a small
number of recordings and are exploratory because the outer tests were seen.

For the limited parameter follow-up, set `--depth 3 --class-weight 1` (or 3),
`--thresholds 0.3 0.5 0.7`, and an explicit ignored `--output` path. Each model
is fitted once per fold and all thresholds use the same validation scores.
These hand-picked values are a small exploratory comparison, not an exhaustive
search; class weights are training-only. Thresholds and model choice must not
be selected using the previously inspected outer-test results.

Folds contain few recordings with very unequal attack counts, so the fold mean
can be unstable and the selection is not optimized for a specified false-alarm
budget. A held-out attack is absent from its inner validation; performance on it
cannot be inferred from the inner score. Outer test results were previously
inspected and are not a pristine final holdout. Recording separation does not
prove session independence. Report per-fold scores and confusion counts rather
than only averages. Do not redistribute feature files or generated results.
