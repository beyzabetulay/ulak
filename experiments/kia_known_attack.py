"""Evaluate known attack types on held-out Kia training recordings."""
import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
import xgboost
from sklearn.tree import DecisionTreeClassifier
from xgboost import XGBClassifier

if __package__:
    from .kia_xgboost_baseline import COMMON, FEATURES, digest, scores
else:
    from kia_xgboost_baseline import COMMON, FEATURES, digest, scores

ROOT = Path(__file__).resolve().parents[1]


def known_recording_folds(df):
    """Return absolute row positions; each evaluated attack has another training recording."""
    eligible = df[df['split'].eq('train')]
    if eligible[['recording_id', 'attack_type', 'label_bin']].isna().any().any():
        raise ValueError('Missing training metadata')
    if not eligible.label_bin.isin([0, 1]).all():
        raise ValueError('Expected binary labels')
    if (eligible.groupby('recording_id').attack_type.nunique() != 1).any():
        raise ValueError('Inconsistent recording attack types')
    recordings = eligible.groupby(['attack_type', 'recording_id']).label_bin.sum()
    attack_recordings = recordings[recordings > 0]
    folds = []
    for attack in sorted(attack_recordings.index.get_level_values(0).unique()):
        ids = sorted(attack_recordings.loc[attack].index)
        if len(ids) < 2:
            continue
        for recording in ids:
            test = np.flatnonzero((df['split'].eq('train') & df.recording_id.eq(recording)).to_numpy())
            train = np.flatnonzero((df['split'].eq('train') & ~df.recording_id.eq(recording)).to_numpy())
            if set(df.iloc[train].recording_id) & set(df.iloc[test].recording_id):
                raise ValueError('Recording overlap')
            folds.append((attack, recording, train, test))
    return folds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'kia_soul_features_all.parquet')
    parser.add_argument('--manifest', type=Path, default=ROOT / 'splits/generated/kia_soul/manifest.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'experiments/kia_decision_tree/local_outputs/known_attack.json')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    if digest(args.input) != manifest['sha256'] or manifest['variants']['standard'] != FEATURES:
        raise ValueError('Unexpected input or feature contract')
    df = pd.read_parquet(args.input, columns=FEATURES + ['split', 'recording_id', 'attack_type', 'label_bin'])
    if len(df) != manifest['rows']:
        raise ValueError('Unexpected row count')
    folds = known_recording_folds(df)
    X = df[FEATURES].fillna(-1).to_numpy(dtype=np.float32)
    y = df.label_bin.to_numpy(dtype=np.int8)
    result = {'input_sha256': manifest['sha256'], 'manifest_sha256': digest(args.manifest),
              'protocol': 'leave one training recording out; attack must occur in another training recording',
              'features': FEATURES, 'missing_value': -1, 'threshold': 0.5,
              'model_selection': 'none; all three predefined models reported',
              'versions': {'python': platform.python_version(), 'numpy': np.__version__, 'pandas': pd.__version__,
                           'sklearn': sklearn.__version__, 'xgboost': xgboost.__version__}, 'folds': []}
    for attack, recording, train, test in folds:
        entry = {'attack_type': attack, 'test_recording': recording,
                 'train_recordings': sorted(df.iloc[train].recording_id.unique().tolist()),
                 'train_positions_sha256': hashlib.sha256(train.astype('<i8').tobytes()).hexdigest(),
                 'test_positions_sha256': hashlib.sha256(test.astype('<i8').tobytes()).hexdigest(), 'models': []}
        for name, model in [('tree_depth6', DecisionTreeClassifier(max_depth=6, random_state=42)),
                            ('xgboost_depth3', XGBClassifier(**COMMON, max_depth=3, n_estimators=100)),
                            ('xgboost_depth6', XGBClassifier(**COMMON, max_depth=6, n_estimators=100))]:
            started = time.monotonic()
            model.fit(X[train], y[train])
            pred = (model.predict_proba(X[test])[:, 1] >= 0.5).astype(np.int8)
            train_pred = (model.predict_proba(X[train])[:, 1] >= 0.5).astype(np.int8)
            metric = scores(y[test], pred)
            entry['models'].append({'model': name, 'parameters': model.get_params(),
                                    'training': scores(y[train], train_pred), 'evaluation': metric,
                                    'seconds': round(time.monotonic() - started, 2)})
            print(f'{recording} {name}: {metric}', flush=True)
        result['folds'].append(entry)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
