"""Kia classification on the HCRL release test.

`select` chooses the depth and decision threshold per feature variant on the seen-type
inner folds of the `official` split; it never loads the release test indices.
`release` refits on the full official training partition and evaluates the release
test once, guarded by the selection hash and a one-shot attempt file.
"""
import argparse
import json
import platform
import time
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
import xgboost
from sklearn.metrics import average_precision_score, precision_recall_curve
from xgboost import XGBClassifier

if __package__:
    from .kia_validation_ablation import validate_inner
    from .kia_xgboost_baseline import CANDIDATES, COMMON, digest, load_indices, scores
else:
    from kia_validation_ablation import validate_inner
    from kia_xgboost_baseline import CANDIDATES, COMMON, digest, load_indices, scores

ROOT = Path(__file__).resolve().parents[1]
SPLITS = ROOT / 'splits/generated/kia_soul'
OUTPUTS = ROOT / 'experiments/kia_decision_tree/local_outputs'
TIMING = {'iat_id', 'iat_bus', 'bus_count_100ms'}
BYTES = [f'byte_{i}' for i in range(8)]
SAMPLING = {'normal_ratio': 0.2, 'min_per_group': 1000, 'group': ['recording_id', 'can_id_dec'],
            'kept_whole': 'all attack rows and every normal row of Replay recordings'}
SELECTION_SEED = 42
RELEASE_SEEDS = [42, 43, 44, 45, 46]


def build_variants(outer_manifest):
    standard = outer_manifest['variants']['standard']
    masked = outer_manifest['variants']['id_masked']
    return {'A_standard': standard, 'B_id_masked': masked,
            'C_standard_iat_id': standard + ['iat_id'], 'D_id_masked_iat_id': masked + ['iat_id'],
            'F_full': outer_manifest['variants']['full']}


def feature_matrix(df, columns):
    """Fill missing payload bytes with -1; keep missing timing values as NaN for XGBoost."""
    frame = df[columns].copy()
    payload = [c for c in columns if c not in TIMING]
    frame[payload] = frame[payload].fillna(-1)
    return frame.to_numpy(dtype=np.float32)


def subsample_normals(positions, labels, recordings, can_ids, keep_recordings, seed,
                      ratio=SAMPLING['normal_ratio'], minimum=SAMPLING['min_per_group']):
    """Keep every attack row and every row of keep_recordings; sample other normal rows per
    (recording, CAN ID) group, at least `minimum` rows (or the whole group if smaller)."""
    positions = np.asarray(positions)
    frame = pd.DataFrame({'pos': positions, 'rec': recordings[positions], 'id': can_ids[positions],
                          'y': labels[positions]})
    fixed = (frame.y == 1) | frame.rec.isin(keep_recordings)
    pool = frame[~fixed].copy()
    pool['r'] = np.random.default_rng(seed).random(len(pool))
    pool['rank'] = pool.groupby(['rec', 'id']).r.rank(method='first')
    size = pool.groupby(['rec', 'id']).r.transform('size')
    quota = np.where(size <= minimum, size, np.maximum(minimum, np.round(ratio * size)))
    kept = np.concatenate((frame.pos[fixed].to_numpy(), pool.pos[pool['rank'] <= quota].to_numpy()))
    return np.sort(kept)


def metrics(y, proba, threshold):
    result = scores(y, (proba >= threshold).astype(np.int8))
    has_both = 0 < y.sum() < len(y)
    result['auprc'] = float(average_precision_score(y, proba)) if has_both else None
    if y.sum() == 0:
        result.update(attack_precision=None, attack_recall=None, attack_f1=None)
    return result


def per_file(y, proba, recordings, timestamps, thresholds):
    out = {}
    for rec in sorted(set(recordings)):
        mask = recordings == rec
        duration = float(timestamps[mask].max() - timestamps[mask].min())
        out[rec] = {'duration_s': duration, 'rows': int(mask.sum()), 'attacks': int(y[mask].sum()),
                    'thresholds': {}}
        for name, threshold in thresholds.items():
            m = metrics(y[mask], proba[mask], threshold)
            m['false_alarms_per_s'] = m['fp'] / duration if duration > 0 else None
            out[rec]['thresholds'][name] = m
    return out


def oof_threshold(y, proba):
    """Threshold maximising attack F1 on pooled out-of-fold predictions (lowest on ties)."""
    precision, recall, thresholds = precision_recall_curve(y, proba)
    f1 = np.divide(2 * precision * recall, precision + recall,
                   out=np.zeros_like(precision), where=(precision + recall) > 0)[:-1]
    return float(thresholds[int(np.argmax(f1))])


def choose_depth(configurations):
    """Highest unweighted mean fold AUPRC; the shallower depth wins ties."""
    return min(configurations, key=lambda c: (-c['mean_auprc'], c['parameters']['max_depth']))


def fit_predict(X, y, train, test, depth):
    model = XGBClassifier(**COMMON, max_depth=depth, n_estimators=100)
    model.fit(X[train], y[train])
    return model.predict_proba(X[test])[:, 1]


def check_release_guard(selection, expected_sha256, output, attempt):
    if not selection.exists():
        raise ValueError(f'Selection file not found: {selection}')
    if digest(selection) != expected_sha256:
        raise ValueError('Selection file hash differs from --selection-sha256')
    for path in (output, attempt):
        if path.exists():
            raise ValueError(f'{path} exists: the release test was already attempted')


def load_contract(args):
    outer_path = args.splits_dir / 'manifest.json'
    inner_path = args.splits_dir / 'validation_seen/manifest.json'
    outer = json.loads(outer_path.read_text())
    inner = json.loads(inner_path.read_text())
    input_sha = digest(args.input)
    if input_sha != outer['sha256'] or inner['input_sha256'] != outer['sha256'] \
            or inner['outer_manifest_sha256'] != digest(outer_path):
        raise ValueError('Input or outer manifest hash does not match the validation manifest')
    hashes = {'input_sha256': input_sha, 'outer_manifest_sha256': digest(outer_path),
              'validation_manifest_sha256': digest(inner_path)}
    return outer, inner, hashes


def versions():
    return {'python': platform.python_version(), 'numpy': np.__version__, 'pandas': pd.__version__,
            'sklearn': sklearn.__version__, 'xgboost': xgboost.__version__}


def read_frame(path, variants, extra):
    columns = sorted({c for cols in variants.values() for c in cols} | set(extra))
    return pd.read_parquet(path, columns=columns)


def replay_recordings(df, positions):
    rows = df.iloc[positions]
    return set(rows.loc[rows.attack_type == 'Replay', 'recording_id'])


def select(args):
    outer, inner, hashes = load_contract(args)
    variants = build_variants(outer)
    df = read_frame(args.input, variants, ['label_bin', 'recording_id', 'attack_type'])
    if len(df) != outer['rows']:
        raise ValueError('Unexpected row count')
    y = df.label_bin.to_numpy(dtype=np.int8)
    groups = df.recording_id.to_numpy()
    can_ids = df.can_id_dec.to_numpy()
    official = next(f for f in outer['folds'] if f['name'] == 'official')
    outer_train = load_indices(args.splits_dir / official['train']['indices'], len(df))
    entry = next(f for f in inner['outer_folds'] if f['name'] == 'official')
    folds, index_hashes = [], {}
    for part in entry['folds']:
        paths = [args.splits_dir / 'validation_seen' / part[p]['indices'] for p in ('train', 'validation')]
        a, b = (load_indices(p, len(df)) for p in paths)
        validate_inner(outer_train, a, b, groups, y)
        index_hashes.update({p.name: digest(p) for p in paths})
        folds.append((part['fold'], a, b))
    keep = replay_recordings(df, outer_train)
    sampled = {number: subsample_normals(a, y, groups, can_ids, keep, SELECTION_SEED) if args.sample_normals else a
               for number, a, _ in folds}
    result = {'phase': 'select', **hashes, 'inner_index_sha256': index_hashes, 'release_test_loaded': False,
              'versions': versions(), 'common_parameters': COMMON, 'candidates': CANDIDATES,
              'rule': 'per variant: highest unweighted mean fold AUPRC, shallower depth on ties; '
                      'decision threshold maximises pooled out-of-fold F1; no winner across variants',
              'sampling': {'enabled': args.sample_normals, **(SAMPLING if args.sample_normals else {}),
                           'seed': SELECTION_SEED if args.sample_normals else None,
                           'training_rows': {str(n): len(s) for n, s in sampled.items()}},
              'variants': {}}
    for name, columns in variants.items():
        X = feature_matrix(df, columns)
        configs, probabilities = [], {}
        for params in CANDIDATES:
            depth = params['max_depth']
            fold_results = []
            for number, _, b in folds:
                started = time.monotonic()
                proba = fit_predict(X, y, sampled[number], b, depth)
                probabilities[(depth, number)] = proba
                fold_results.append({'fold': number, 'seconds': round(time.monotonic() - started, 1),
                                     **metrics(y[b], proba, 0.5)})
                print(f'{name} depth={depth} fold={number} AUPRC={fold_results[-1]["auprc"]:.4f} '
                      f'F1@0.5={fold_results[-1]["attack_f1"]:.4f}', flush=True)
            configs.append({'parameters': params, 'folds': fold_results,
                            'mean_auprc': float(np.mean([f['auprc'] for f in fold_results])),
                            'mean_f1_at_0_5': float(np.mean([f['attack_f1'] for f in fold_results]))})
        chosen = choose_depth(configs)
        depth = chosen['parameters']['max_depth']
        oof_y = np.concatenate([y[b] for _, _, b in folds])
        oof_p = np.concatenate([probabilities[(depth, n)] for n, _, _ in folds])
        threshold = oof_threshold(oof_y, oof_p)
        at_threshold = [{'fold': n, **metrics(y[b], probabilities[(depth, n)], threshold)} for n, _, b in folds]
        result['variants'][name] = {'features': columns, 'configurations': configs,
                                    'chosen': {'max_depth': depth, 'threshold': threshold},
                                    'folds_at_chosen_threshold': at_threshold}
        if args.sample_normals and name == 'C_standard_iat_id':
            check = []
            for number, a, b in folds:
                full = metrics(y[b], fit_predict(X, y, a, b, depth), 0.5)['attack_f1']
                sampled_f1 = next(f for f in chosen['folds'] if f['fold'] == number)['attack_f1']
                check.append({'fold': number, 'full_f1_at_0_5': full, 'sampled_f1_at_0_5': sampled_f1,
                              'difference_above_0_01': abs(full - sampled_f1) > 0.01})
            result['sampling']['full_data_check'] = {'variant': name, 'max_depth': depth, 'folds': check}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(f'selection written to {args.output}\nsha256 {digest(args.output)}')


def summarize(runs, key_path):
    values = []
    for run in runs:
        node = run
        for key in key_path:
            node = node[key]
        values.append(node)
    values = [v for v in values if v is not None]
    if not values:
        return None
    return {'mean': float(np.mean(values)), 'std': float(np.std(values)), 'min': float(min(values)),
            'max': float(max(values))}


def release(args):
    output = args.output
    attempt = output.with_name(output.stem + '_attempt.json')
    check_release_guard(args.selection, args.selection_sha256, output, attempt)
    selection = json.loads(args.selection.read_text())
    outer, _, hashes = load_contract(args)
    for key, value in hashes.items():
        if selection[key] != value:
            raise ValueError(f'{key} changed since selection')
    variants = build_variants(outer)
    sampling = selection['sampling']['enabled']
    if args.seeds is None:
        args.seeds = RELEASE_SEEDS if sampling else [SELECTION_SEED]
    if not sampling and len(args.seeds) > 1:
        raise ValueError('Without sampling the model is deterministic; use a single seed')
    with attempt.open('x') as stream:
        json.dump({'selection_sha256': args.selection_sha256, 'started_unix': time.time()}, stream)
    df = read_frame(args.input, variants, ['label_bin', 'recording_id', 'attack_type', 'timestamp'] + BYTES + ['dlc'])
    y = df.label_bin.to_numpy(dtype=np.int8)
    groups = df.recording_id.to_numpy()
    official = next(f for f in outer['folds'] if f['name'] == 'official')
    train = load_indices(args.splits_dir / official['train']['indices'], len(df))
    test = load_indices(args.splits_dir / official['test']['indices'], len(df))
    if np.intersect1d(train, test).size or set(groups[train]) & set(groups[test]):
        raise ValueError('Official train and test overlap')
    keep = replay_recordings(df, train)
    # Release normal rows whose exact content equals a training Replay attack frame.
    content = ['can_id_dec', 'dlc'] + BYTES
    keys = pd.util.hash_pandas_object(df[content].fillna(-1), index=False).to_numpy()
    replay_attack = train[(y[train] == 1) & np.isin(groups[train], list(keep))]
    overlap = np.isin(keys[test], keys[replay_attack])
    y_test, rec_test, ts_test = y[test], groups[test], df.timestamp.to_numpy()[test]
    result = {'phase': 'release', 'selection_sha256': args.selection_sha256, **hashes, 'versions': versions(),
              'seeds': args.seeds, 'sampling': selection['sampling'], 'test_rows': len(test),
              'normal_rows_matching_training_replay_attack': int((overlap & (y_test == 0)).sum()),
              'variants': {}, 'complete': False}
    for name, columns in variants.items():
        chosen = selection['variants'][name]['chosen']
        thresholds = {'0.5': 0.5, 'oof_f1': chosen['threshold']}
        X = feature_matrix(df, columns)
        runs = []
        for seed in args.seeds:
            started = time.monotonic()
            fit_rows = subsample_normals(train, y, groups, df.can_id_dec.to_numpy(), keep, seed) if sampling else train
            proba = fit_predict(X, y, fit_rows, test, chosen['max_depth'])
            proba_path = output.with_name(f'release_proba_{name}_seed{seed}.npy')
            np.save(proba_path, proba.astype(np.float32), allow_pickle=False)
            run = {'seed': seed, 'training_rows': len(fit_rows), 'probabilities': proba_path.name,
                   'probabilities_sha256': digest(proba_path), 'pooled': {}, 'replay_overlap_false_alarms': {},
                   'per_file': per_file(y_test, proba, rec_test, ts_test, thresholds),
                   'seconds': round(time.monotonic() - started, 1)}
            for label, threshold in thresholds.items():
                run['pooled'][label] = metrics(y_test, proba, threshold)
                alarm = (proba >= threshold) & (y_test == 0)
                run['replay_overlap_false_alarms'][label] = {
                    'matching_normal_rows': int((overlap & (y_test == 0)).sum()),
                    'false_alarms_matching': int((alarm & overlap).sum()),
                    'other_normal_rows': int((~overlap & (y_test == 0)).sum()),
                    'false_alarms_other': int((alarm & ~overlap).sum())}
            runs.append(run)
            p = run['pooled']['oof_f1']
            print(f'{name} seed={seed} release F1={p["attack_f1"]:.4f} AUPRC={p["auprc"]:.4f} '
                  f'({run["seconds"]}s)', flush=True)
        summary = {'pooled': {}, 'per_file': {}}
        for label in thresholds:
            summary['pooled'][label] = {m: summarize(runs, ['pooled', label, m])
                                        for m in ('attack_precision', 'attack_recall', 'attack_f1',
                                                  'false_positive_rate', 'auprc')}
            for rec in runs[0]['per_file']:
                summary['per_file'].setdefault(rec, {})[label] = {
                    m: summarize(runs, ['per_file', rec, 'thresholds', label, m])
                    for m in ('attack_precision', 'attack_recall', 'attack_f1', 'false_positive_rate',
                              'auprc', 'false_alarms_per_s')}
        result['variants'][name] = {'features': columns, 'chosen': chosen, 'runs': runs, 'summary': summary}
        output.write_text(json.dumps(result, indent=2) + '\n')
    result['complete'] = True
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(f'release results written to {output}')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--input', type=Path, default=ROOT / 'kia_soul_features_all.parquet')
    parser.add_argument('--splits-dir', type=Path, default=SPLITS)
    sub = parser.add_subparsers(dest='command', required=True)
    s = sub.add_parser('select', help='choose settings on seen-type inner folds')
    s.add_argument('--output', type=Path, default=OUTPUTS / 'release_selection.json')
    s.add_argument('--sample-normals', action='store_true',
                   help='stratified 1:5 sampling of normal training rows (off by default: it doubled '
                        'validation false alarms)')
    r = sub.add_parser('release', help='evaluate the release test once')
    r.add_argument('--selection', type=Path, default=OUTPUTS / 'release_selection.json')
    r.add_argument('--selection-sha256', required=True)
    r.add_argument('--output', type=Path, default=OUTPUTS / 'release_test.json')
    r.add_argument('--seeds', type=int, nargs='+',
                   help='default: 42-46 with sampling, 42 without (deterministic)')
    args = parser.parse_args()
    if args.command == 'select':
        select(args)
    else:
        release(args)


if __name__ == '__main__':
    main()
