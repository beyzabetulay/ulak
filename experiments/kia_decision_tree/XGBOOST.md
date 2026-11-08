# Kia XGBoost baseline

This experiment compares two fixed XGBoost configurations against the same
Kia standard feature contract used by the decision-tree notebook. It does not
change the notebook, use timing features, or inspect the official release test.

Install `experiments/requirements.txt`, prepare the Kia parquet and outer
manifest as described in `splits/README.md`, and generate the balanced inner
folds with `python splits/make_kia_validation.py`. Then run:

```sh
python experiments/kia_xgboost_baseline.py
```

The output is `experiments/kia_decision_tree/local_outputs/xgboost.json`, which
is ignored by Git. Use `--input`, `--splits-dir`, and `--output` to override
paths. The input and outer manifest hashes are verified against the validation
manifest, and input row positions, recording separation and validation coverage
are checked before fitting. The JSON includes hashes, versions, configurations,
fold confusion counts, attack precision/recall/F1, normal false-positive rate,
and elapsed fitting plus prediction times. Index arrays are validated but not
cryptographically bound to their own hashes.

For each unseen attack outer split, use only its training rows for inner
validation. Compare max depth 3 and 6, both with 100 estimators, learning rate
0.1, histogram trees, four CPU threads, seed 42 and a fixed 0.5 decision
threshold. Choose the highest unweighted mean of the four validation attack F1
scores (the first configuration wins ties), refit on all outer training rows,
and evaluate once on that outer test. This is a small predefined comparison,
not a comprehensive hyperparameter search. There is no class weighting or
early stopping. Both models use CAN ID, DLC and eight payload bytes, with -1
for missing bytes, as in the decision-tree notebook.

Folds contain few recordings with very unequal attack counts, so the fold mean
can be unstable and the selection is not optimized for a specified false-alarm
budget. A held-out attack is absent from its inner validation; performance on it
cannot be inferred from the inner score. Outer test results were previously
inspected and are not a pristine final holdout. Recording separation does not
prove session independence. Report per-fold scores and confusion counts rather
than only averages. Do not redistribute feature files or generated results.
