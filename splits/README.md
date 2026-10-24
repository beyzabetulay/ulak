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
