"""Compare two fixed XGBoost configurations with recording-grouped Kia validation."""
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
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ['can_id_dec', 'dlc'] + [f'byte_{i}' for i in range(8)]
CANDIDATES = [
    {'max_depth': 3, 'n_estimators': 100},
    {'max_depth': 6, 'n_estimators': 100},
]
COMMON = {'learning_rate': 0.1, 'tree_method': 'hist', 'random_state': 42,
          'objective': 'binary:logistic', 'n_jobs': 4}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def scores(y, prediction):
    tn, fp, fn, tp = confusion_matrix(y, prediction, labels=[0, 1]).ravel()
    precision, recall, f1, _ = precision_recall_fscore_support(
        y, prediction, labels=[1], zero_division=0)
    return {'tn': int(tn), 'fp': int(fp), 'fn': int(fn), 'tp': int(tp),
            'attack_precision': float(precision[0]), 'attack_recall': float(recall[0]),
            'attack_f1': float(f1[0]), 'false_positive_rate': float(fp / (fp + tn)) if fp + tn else None}


def run_model(X, y, train, valid, params):
    model = XGBClassifier(**COMMON, **params)
    started = time.monotonic()
    model.fit(X[train], y[train])
    predicted = (model.predict_proba(X[valid])[:, 1] >= 0.5).astype(np.int8)
    return scores(y[valid], predicted), round(time.monotonic() - started, 2)


def load_indices(path, n):
    a = np.load(path, allow_pickle=False)
    if a.ndim != 1 or not np.issubdtype(a.dtype, np.integer) or (a < 0).any() or (a >= n).any() or len(np.unique(a)) != len(a):
        raise ValueError(f'Invalid indices: {path}')
    return a


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'kia_soul_features_all.parquet')
    parser.add_argument('--splits-dir', type=Path, default=ROOT / 'splits/generated/kia_soul')
    parser.add_argument('--output', type=Path, default=ROOT / 'experiments/kia_decision_tree/local_outputs/xgboost.json')
    args = parser.parse_args()
    outer_path = args.splits_dir / 'manifest.json'
    inner_dir = args.splits_dir / 'validation_balanced'
    outer = json.loads(outer_path.read_text())
    inner = json.loads((inner_dir / 'manifest.json').read_text())
    if digest(args.input) != outer['sha256'] or inner['input_sha256'] != outer['sha256'] or inner['outer_manifest_sha256'] != digest(outer_path):
        raise ValueError('Input or outer manifest hash does not match validation manifest')
    if outer['variants']['standard'] != FEATURES:
        raise ValueError('Unexpected standard feature contract')
    df = pd.read_parquet(args.input, columns=FEATURES + ['label_bin', 'recording_id'])
    if len(df) != outer['rows'] or not df.label_bin.isin([0, 1]).all() or df.recording_id.isna().any():
        raise ValueError('Invalid input labels, row count or recording IDs')
    X = df[FEATURES].fillna(-1).to_numpy(dtype=np.float32)
    y = df.label_bin.to_numpy(dtype=np.int8)
    groups = df.recording_id.to_numpy()
    results = {'input_sha256': outer['sha256'], 'outer_manifest_sha256': digest(outer_path),
               'validation_manifest_sha256': digest(inner_dir / 'manifest.json'),
               'features': FEATURES, 'missing_value': -1, 'threshold': 0.5,
               'selection': 'highest unweighted mean validation attack F1; first candidate wins ties',
               'candidates': CANDIDATES, 'common_parameters': COMMON,
               'versions': {'python': platform.python_version(), 'numpy': np.__version__, 'pandas': pd.__version__,
                            'sklearn': sklearn.__version__, 'xgboost': xgboost.__version__}, 'folds': []}
    outer_by_name = {f['name']: f for f in outer['folds']}
    for fold in inner['outer_folds']:
        name = fold['name']
        if name == 'official':
            continue
        outer_fold = outer_by_name[name]
        train = load_indices(args.splits_dir / outer_fold['train']['indices'], len(df))
        test = load_indices(args.splits_dir / outer_fold['test']['indices'], len(df))
        if np.intersect1d(train, test).size or set(groups[train]) & set(groups[test]):
            raise ValueError(f'{name}: outer split overlaps')
        prepared = []
        for part in fold['folds']:
            a = load_indices(inner_dir / part['train']['indices'], len(df))
            b = load_indices(inner_dir / part['validation']['indices'], len(df))
            if not np.array_equal(np.sort(np.concatenate((a, b))), np.sort(train)) or set(groups[a]) & set(groups[b]):
                raise ValueError(f'{name}: invalid inner partition')
            if set(y[b]) != {0, 1} or set(y[a]) != {0, 1}:
                raise ValueError(f'{name}: inner partition missing a class')
            prepared.append((a, b))
        if not np.array_equal(np.sort(np.concatenate([b for _, b in prepared])), np.sort(train)):
            raise ValueError(f'{name}: validation folds do not partition training rows')
        configs = []
        for params in CANDIDATES:
            validations = []
            for number, (a, b) in enumerate(prepared, 1):
                metric, seconds = run_model(X, y, a, b, params)
                validations.append({'fold': number, 'metrics': metric, 'seconds': seconds})
                print(f'{name} depth={params["max_depth"]} validation={number}: {metric} ({seconds}s)', flush=True)
            configs.append({'parameters': params, 'validation': validations,
                            'mean_attack_f1': float(np.mean([v['metrics']['attack_f1'] for v in validations]))})
        best = max(configs, key=lambda c: c['mean_attack_f1'])
        metric, seconds = run_model(X, y, train, test, best['parameters'])
        results['folds'].append({'name': name, 'configurations': configs, 'selected': best['parameters'],
                                 'test': metric, 'test_seconds': seconds})
        print(f'{name} selected={best["parameters"]} test={metric} ({seconds}s)', flush=True)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, indent=2) + '\n')


if __name__ == '__main__':
    main()
