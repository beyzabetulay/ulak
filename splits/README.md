# Generalization splits

Run from the repository root (dependencies: `pip install -r experiments/requirements.txt`):

```sh
python splits/make_splits.py
python experiments/shortcut_baseline.py
```

The generator uses only `features_train.parquet`. Three leave-one-vehicle-out folds train on two vehicles and evaluate on the third: Chevrolet Spark, Hyundai Sonata, and Kia Soul. Rows with vehicle `unknown` are excluded. Source files cannot overlap between training and evaluation. The official challenge test partition is not used. Tune models only within the training vehicles, grouping inner validation by `source_file`.

`splits/generated/` contains six NumPy index arrays and a manifest with counts, a SHA-256 of the input, and feature contracts. Arrays contain zero-based **row positions** in the unchanged input parquet, not DataFrame index labels. Regenerate after rebuilding or reordering that file. Generated artifacts are ignored by version control and must not be committed. `--input` and `--output-dir` override paths.

Both variants share exactly the same rows. `standard` includes `can_id_dec`, `dlc`, and `byte_0..7`. `id_masked` includes only `dlc` and `byte_0..7`: neither `can_id` nor `can_id_dec` is loaded. All metadata and labels are excluded from X through explicit allowlists. The target is `label_bin`; metadata remains available separately for grouping. These contracts intentionally exclude future timing features to keep the comparison reproducible. ID masking does not eliminate other possible shortcuts in payload or length.

```python
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

folder = Path('splits/generated')
m = json.loads((folder / 'manifest.json').read_text())
path = Path(m['input'])  # update location if the identical file was moved
with path.open('rb') as stream:
    assert hashlib.file_digest(stream, 'sha256').hexdigest() == m['sha256']
features = m['variants']['id_masked']  # or 'standard'
df = pd.read_parquet(path, columns=features + [m['target']])
fold = m['folds'][0]
train = np.load(folder / fold['train']['indices'], allow_pickle=False)
test = np.load(folder / fold['test']['indices'], allow_pickle=False)
X_train, y_train = df.iloc[train][features], df.iloc[train][m['target']]
X_test, y_test = df.iloc[test][features], df.iloc[test][m['target']]
```

Fit missing-value preprocessing on training data only. Report precision, recall and F1 for both classes. Attack-type analysis is valid only on this training partition; attack types identify traces containing both normal and attack frames.

The baseline runs a depth-6 decision tree with five source-file GroupKFold folds on all training rows, compares ID-only, full-feature, and ID-masked configurations, and writes `experiments/results/shortcut_baseline.md`. Its feature importances are averaged over the five fitted trees. Use `--help` for configuration options. Results are pooled out-of-fold metrics, not scores on the same rows used to fit a tree.

## Kia Soul (single vehicle)

```sh
python prepare_kia_soul.py
python build_features.py --input kia_soul_dataset.csv --prefix kia_soul_features
python splits/make_kia_splits.py
```

The generator uses `kia_soul_features_all.parquet` and writes to `splits/generated/kia_soul/`, in the same format as above (index arrays and `manifest.json`, loaded the same way). Each fold's manifest entry lists its train and test recordings. Train and test never share a `recording_id`.

| Fold | Train | Test |
|---|---|---|
| `unseen_dos`, `unseen_injection`, `unseen_spoofing`, `unseen_replay` | training partition without the held-out attack's recordings (attack-free recordings always included) | all recordings of the held-out attack |
| `official` | training partition (HCRL `*_train` folders) | HCRL `*_release` files (attack type withheld) |

Feature variants: `standard` (`can_id_dec`, `dlc`, `byte_0..7`), `id_masked` (no ID), `id_masked_timing` (no ID, plus `iat_id`, `iat_bus`) and `full` (everything, including `bus_count_100ms`). `bus_count_100ms` is only in `full` because it is also high for normal frames inside attack recordings, so it partly describes the recording rather than the frame (see `FINDINGS.md`).

Share of test attack frames whose CAN ID never occurs in the fold's training rows: 15% for `unseen_injection`, 0% for every other fold. Kia Soul fuzzing mostly reuses the vehicle's own IDs, and ID `0000` (all DoS frames) occurs 14 times in the training rows of `unseen_dos`, inside Injection recordings.

### Inner validation for Kia

After generating the Kia outer splits, run `python splits/make_kia_validation.py`.
This creates five recording-grouped GroupKFold train/validation pairs inside
each outer training partition, including `official`; its outer test remains
untouched. The original manifest and indices are not modified. The generated
`splits/generated/kia_soul/validation/manifest.json` records the input and outer
manifest hashes, absolute parquet row-position index files, recording names,
class counts and row counts by recording attack type for each part. Check both hashes
before reusing these indices; regenerate if either input or outer splits change.
Use `--folds`, `--input`, `--splits-dir` and `--output-dir` to override defaults.

The Kia outer training sets contain few recordings. GroupKFold balances row
counts, not attack types or classes: some validation folds can have no attack
frames or lack particular attack types. Report fold support and per-fold metrics;
do not interpret a missing class as a measured recall. Inner validation cannot
measure the held-out outer attack type. Select features and hyperparameters using
inner folds only, refit on the outer training partition, then evaluate on its
outer test. Previously inspected test results are not a pristine final holdout.
