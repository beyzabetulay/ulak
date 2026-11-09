"""Compare Kia feature variants using only existing inner validation partitions."""
import argparse
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
    from .kia_xgboost_baseline import CANDIDATES, COMMON, FEATURES, TIMING_FEATURES, digest, load_indices, scores
    from .kia_spoofing_sequence import past_features
else:
    from kia_xgboost_baseline import CANDIDATES, COMMON, FEATURES, TIMING_FEATURES, digest, load_indices, scores
    from kia_spoofing_sequence import past_features

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = {'standard': FEATURES, 'iat_id': FEATURES + ['iat_id'],
            'iat_bus': FEATURES + ['iat_bus'], 'both': TIMING_FEATURES,
            'sequence': FEATURES + ['iat_id', 'changed_bits', 'repeat_previous']}


def add_sequence_columns(frame):
    """Keep absolute parquet positions while deriving recording-local past features."""
    if not frame.index.is_unique:
        raise ValueError('Expected unique row positions')
    transitions = past_features(frame).reindex(frame.index)
    return frame.assign(changed_bits=transitions.changed_bits,
                        repeat_previous=transitions.repeat_previous)


def validate_inner(outer_train, train, valid, groups, labels):
    if not np.array_equal(np.sort(np.concatenate((train, valid))), np.sort(outer_train)) or set(groups[train]) & set(groups[valid]):
        raise ValueError('Invalid inner partition')
    if set(labels[train]) != {0, 1} or set(labels[valid]) != {0, 1}:
        raise ValueError('Inner partition missing a class')


def evaluate(X, y, train, valid, model, thresholds):
    started = time.monotonic()
    model.fit(X[train], y[train])
    probabilities = model.predict_proba(X[valid])[:, 1]
    metrics = {str(threshold): scores(y[valid], (probabilities >= threshold).astype(np.int8))
               for threshold in thresholds}
    return metrics, round(time.monotonic() - started, 2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', choices=['tree', 'xgboost', 'catboost'], required=True)
    parser.add_argument('--variant', choices=VARIANTS, required=True)
    parser.add_argument('--input', type=Path, default=ROOT / 'kia_soul_features_all.parquet')
    parser.add_argument('--splits-dir', type=Path, default=ROOT / 'splits/generated/kia_soul')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--depth', type=int, choices=[3, 6])
    parser.add_argument('--class-weight', type=float, default=1.0,
                        help='Boosting positive-class weight (training only)')
    parser.add_argument('--thresholds', type=float, nargs='+', default=[0.5])
    args = parser.parse_args()
    catboost_version = None
    if args.model == 'catboost':
        import catboost
        from catboost import CatBoostClassifier
        catboost_version = catboost.__version__
    if args.class_weight <= 0 or any(t < 0 or t > 1 for t in args.thresholds):
        parser.error('class weight must be positive and thresholds must be between 0 and 1')
    if args.model == 'tree' and (args.class_weight != 1 or args.depth is not None):
        parser.error('class weight and depth options are for boosting models')
    if args.output is None and (args.class_weight != 1 or args.depth is not None or args.thresholds != [0.5]):
        parser.error('provide --output for a parameter experiment')
    output = args.output or ROOT / f'experiments/kia_decision_tree/local_outputs/ablation_{args.model}_{args.variant}.json'
    outer_path = args.splits_dir / 'manifest.json'
    inner_dir = args.splits_dir / 'validation_balanced'
    outer = json.loads(outer_path.read_text())
    inner = json.loads((inner_dir / 'manifest.json').read_text())
    if digest(args.input) != outer['sha256'] or inner['input_sha256'] != outer['sha256'] or inner['outer_manifest_sha256'] != digest(outer_path):
        raise ValueError('Input or outer manifest hash does not match validation manifest')
    if outer['variants']['standard'] != FEATURES or outer['variants']['full'] != TIMING_FEATURES + ['bus_count_100ms']:
        raise ValueError('Unexpected feature contract')
    features = VARIANTS[args.variant]
    columns = [f for f in features if f not in ['changed_bits', 'repeat_previous']] + ['label_bin', 'recording_id']
    if args.variant == 'sequence':
        columns.append('timestamp')
    df = pd.read_parquet(args.input, columns=columns)
    if len(df) != outer['rows'] or not df.label_bin.isin([0, 1]).all() or df.recording_id.isna().any():
        raise ValueError('Invalid input labels, row count or recording IDs')
    if args.variant == 'sequence':
        df = add_sequence_columns(df)
    X = df[features].fillna(-1).to_numpy(dtype=np.float32)
    y = df.label_bin.to_numpy(dtype=np.int8)
    groups = df.recording_id.to_numpy()
    result = {'input_sha256': outer['sha256'], 'outer_manifest_sha256': digest(outer_path),
              'validation_manifest_sha256': digest(inner_dir / 'manifest.json'),
              'model': args.model, 'variant': args.variant, 'features': features,
              'missing_value': -1, 'thresholds': args.thresholds, 'class_weight': args.class_weight,
              'outer_test_evaluated': False,
              'sequence_source_sha256': digest(ROOT / 'experiments/kia_spoofing_sequence.py') if args.variant == 'sequence' else None,
              'versions': {'python': platform.python_version(), 'numpy': np.__version__, 'pandas': pd.__version__,
                           'sklearn': sklearn.__version__, 'xgboost': xgboost.__version__,
                           'catboost': catboost_version}, 'outer_folds': []}
    outer_by_name = {fold['name']: fold for fold in outer['folds']}
    for fold in inner['outer_folds']:
        name = fold['name']
        if name == 'official':
            continue
        outer_fold = outer_by_name[name]
        outer_train = load_indices(args.splits_dir / outer_fold['train']['indices'], len(df))
        if set(groups[outer_train]) & set(outer_fold['test']['recordings']):
            raise ValueError(f'{name}: training recording overlaps outer test')
        prepared = []
        for part in fold['folds']:
            train = load_indices(inner_dir / part['train']['indices'], len(df))
            valid = load_indices(inner_dir / part['validation']['indices'], len(df))
            validate_inner(outer_train, train, valid, groups, y)
            prepared.append((train, valid))
        if not np.array_equal(np.sort(np.concatenate([v for _, v in prepared])), np.sort(outer_train)):
            raise ValueError(f'{name}: validation folds do not partition training rows')
        params_list = ([p for p in CANDIDATES if args.depth is None or p['max_depth'] == args.depth]
                       if args.model in ['xgboost', 'catboost'] else [{'max_depth': 6, 'random_state': 42}])
        configs = []
        for params in params_list:
            validations = []
            for number, (train, valid) in enumerate(prepared, 1):
                if args.model == 'catboost':
                    model = CatBoostClassifier(iterations=params['n_estimators'], depth=params['max_depth'],
                                               learning_rate=0.1, loss_function='Logloss', random_seed=42,
                                               thread_count=4, verbose=False, allow_writing_files=False,
                                               boosting_type='Plain', scale_pos_weight=args.class_weight)
                elif args.model == 'xgboost':
                    model = XGBClassifier(**COMMON, **params, scale_pos_weight=args.class_weight)
                else:
                    model = DecisionTreeClassifier(**params)
                metrics, elapsed = evaluate(X, y, train, valid, model, args.thresholds)
                validations.append({'fold': number, 'threshold_metrics': metrics, 'seconds': elapsed})
                metric = metrics[str(args.thresholds[0])]
                print(f'{args.model} {args.variant} {name} depth={params["max_depth"]} '
                      f'fold={number} F1={metric["attack_f1"]:.4f} FPR={metric["false_positive_rate"]:.4f}', flush=True)
            configs.append({'parameters': params, 'estimator_parameters': model.get_params(), 'validation': validations,
                            'mean_attack_f1_by_threshold': {
                                str(t): float(np.mean([v['threshold_metrics'][str(t)]['attack_f1'] for v in validations]))
                                for t in args.thresholds}})
        result['outer_folds'].append({'name': name, 'configurations': configs})
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
