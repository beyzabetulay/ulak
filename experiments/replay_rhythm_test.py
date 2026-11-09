"""Replay detection with vehicle-independent rhythm features: select on Kia, test on Sonata.

Every feature is past-only, per CAN ID and scaled by the ID's median period measured on an
attack-free recording of the same vehicle, so no CAN ID or raw payload enters the model.
`select` uses only the Kia Replay recording and a Kia attack-free recording, split into two
time blocks. `test` refits on both and evaluates the Sonata Replay and attack-free recordings
once (plus the Kia release Replay file, which was already evaluated once before).
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score
from xgboost import XGBClassifier

if __package__:
    from .kia_release_test import check_release_guard, choose_depth, fit_predict, metrics, oof_threshold, versions
    from .kia_xgboost_baseline import CANDIDATES, COMMON, digest
else:
    from kia_release_test import check_release_guard, choose_depth, fit_predict, metrics, oof_threshold, versions
    from kia_xgboost_baseline import CANDIDATES, COMMON, digest

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / 'experiments/kia_decision_tree/local_outputs'
FILES = {
    'kia_calibration': 'car_track_final_1st_train/Attack_free_KIA_Soul_train.csv',
    'kia_replay': 'car_track_final_2nd_train/Replay_dataset_KIA_Soul_train.csv',
    'kia_free': 'car_track_preliminary_train/Attack_free_KIA_Soul_train.csv',
    'sonata_calibration': 'car_track_final_1st_train/Attack_free_HY_Sonata_train.csv',
    'sonata_replay': 'car_track_final_2nd_train/Replay_dataset_HY_Sonata_train.csv',
    'sonata_free': 'car_track_preliminary_train/Attack_free_HYUNDAI_Sonata_train.csv',
    'kia_release_replay': 'car_track_final_2nd_release/File_4.csv',
}
TRAIN = ['kia_replay', 'kia_free']
TESTS = {'sonata_replay': 'sonata_calibration', 'sonata_free': 'sonata_calibration',
         'kia_release_replay': 'kia_calibration'}
WINDOW_S = 0.1
RATE = ['gap1', 'count100']
RHYTHM = RATE + ['gap2', 'phase2', 'gap3', 'phase3']
VARIANTS = {'R0_rate': RATE, 'R1_rhythm': RHYTHM, 'R2_rhythm_content': RHYTHM + ['bits1', 'bits2', 'dlc']}
RULE = 'phase2'


def read_raw(path):
    """Read one HCRL CSV (4, 5 or 6 columns) into time, ID, DLC, payload bytes and label."""
    with open(path) as stream:
        ncols = len(stream.readline().strip().split(','))
    names = {6: ['idx', 't', 'id', 'dlc', 'data', 'label'], 5: ['t', 'id', 'dlc', 'data', 'label'],
             4: ['t', 'id', 'dlc', 'data']}[ncols]
    raw = pd.read_csv(path, header=None, names=names, dtype=str)
    data = raw.data.fillna('').str.split(expand=True).reindex(columns=range(8))
    payload = data.apply(lambda col: col.map(lambda x: int(x, 16), na_action='ignore')).fillna(0)
    frame = pd.DataFrame({'t': raw.t.astype(float), 'id': raw.id.map(lambda x: int(x, 16)),
                          'dlc': raw.dlc.astype(int),
                          'label': (raw.label == 'T').astype(np.int8) if 'label' in raw else np.int8(0)})
    frame[[f'b{i}' for i in range(8)]] = payload.to_numpy(dtype=np.uint8)
    return frame.sort_values('t', kind='stable').reset_index(drop=True)


def periods(calibration):
    """Median gap between consecutive frames of each ID in an attack-free recording."""
    gaps = calibration.groupby('id').t.diff()
    return gaps.groupby(calibration.id).median().dropna()


def rhythm_features(frame, period):
    """Past-only per-ID features; IDs missing from the calibration get NaN timing features."""
    out = frame[['t', 'id', 'dlc', 'label']].copy()
    scale = frame.id.map(period).to_numpy()
    groups = frame.groupby('id', sort=False)
    for k in (1, 2, 3):
        gap = (frame.t - groups.t.shift(k)).to_numpy() / scale
        out[f'gap{k}'] = gap
        if k > 1:
            out[f'phase{k}'] = np.abs(gap - np.round(gap))
    count = np.empty(len(frame))
    for _, index in groups.indices.items():
        t = frame.t.to_numpy()[index]
        count[index] = np.arange(len(t)) - np.searchsorted(t, t - WINDOW_S, side='right')
    out['count100'] = count / (WINDOW_S / scale)
    payload = frame[[f'b{i}' for i in range(8)]].to_numpy(dtype=np.uint8)
    for k in (1, 2):
        previous = groups[[f'b{i}' for i in range(8)] + ['dlc']].shift(k)
        comparable = previous.dlc.eq(frame.dlc).to_numpy()
        before = previous[[f'b{i}' for i in range(8)]].fillna(0).to_numpy(dtype=np.uint8)
        bits = np.unpackbits(np.bitwise_xor(payload, before), axis=1).sum(axis=1).astype(float)
        bits[~comparable] = np.nan
        out[f'bits{k}'] = bits
    out['after_attack'] = groups.label.shift(1).eq(1).to_numpy() & (frame.label == 0).to_numpy()
    return out


def load(name, calibration):
    frame = rhythm_features(read_raw(ROOT / FILES[name]), periods(read_raw(ROOT / FILES[calibration])))
    frame['file'] = name
    return frame


def time_blocks(frame):
    """Block 0 = first half of each file's time span, block 1 = second half."""
    blocks = np.zeros(len(frame), dtype=np.int8)
    for name in frame.file.unique():
        mask = (frame.file == name).to_numpy()
        t = frame.t.to_numpy()[mask]
        blocks[mask] = (t >= (t.min() + t.max()) / 2).astype(np.int8)
    return blocks


def rule_auprc(frame):
    y = frame.label.to_numpy()
    if not 0 < y.sum() < len(y):
        return None
    return float(average_precision_score(y, frame[RULE].fillna(0).to_numpy()))


def training_frame():
    return pd.concat([load(name, 'kia_calibration') for name in TRAIN], ignore_index=True)


def select(args):
    df = training_frame()
    y = df.label.to_numpy()
    blocks = time_blocks(df)
    folds = [(np.flatnonzero(blocks != b), np.flatnonzero(blocks == b)) for b in (0, 1)]
    for _, valid in folds:
        if not 0 < y[valid].sum() < len(valid):
            raise ValueError('A validation block lacks one of the classes')
    result = {'files': {n: {'path': FILES[n], 'sha256': digest(ROOT / FILES[n])}
                        for n in TRAIN + ['kia_calibration']},
              'versions': versions(), 'variants': VARIANTS, 'window_s': WINDOW_S,
              'rule': 'unweighted mean fold AUPRC, shallower depth on ties; OOF-F1 threshold',
              'folds': [{'block': b, 'validation_rows': len(v), 'validation_attacks': int(y[v].sum())}
                        for b, (_, v) in enumerate(folds)],
              'phase2_rule_auprc': [rule_auprc(df.iloc[v]) for _, v in folds], 'selected': {}}
    for variant, columns in VARIANTS.items():
        X = df[columns].to_numpy(dtype=np.float32)
        configurations = []
        for parameters in CANDIDATES:
            oof = np.empty(len(df))
            fold_scores = []
            for train, valid in folds:
                oof[valid] = fit_predict(X, y, train, valid, parameters['max_depth'])
                fold_scores.append(metrics(y[valid], oof[valid], 0.5))
            configurations.append({'parameters': parameters, 'folds': fold_scores, 'oof': oof,
                                   'mean_auprc': float(np.mean([s['auprc'] for s in fold_scores]))})
        best = choose_depth(configurations)
        threshold = oof_threshold(y, best['oof'])
        result['selected'][variant] = {
            'max_depth': best['parameters']['max_depth'], 'oof_f1_threshold': threshold,
            'oof_at_threshold': metrics(y, best['oof'], threshold),
            'configurations': [{k: v for k, v in c.items() if k != 'oof'} for c in configurations]}
        print(f"{variant}: depth {best['parameters']['max_depth']}, mean AUPRC {best['mean_auprc']:.3f}, "
              f'threshold {threshold:.3f}')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(f'{args.output}\nsha256 {digest(args.output)}')


def evaluate(frame, proba, thresholds):
    y = frame.label.to_numpy()
    duration = float(frame.t.max() - frame.t.min())
    out = {'rows': len(frame), 'attacks': int(y.sum()), 'duration_s': duration, 'thresholds': {}}
    after = frame.after_attack.to_numpy()
    for name, threshold in thresholds.items():
        m = metrics(y, proba, threshold)
        m['false_alarms_per_s'] = m['fp'] / duration if duration > 0 else None
        m['alarm_rate_on_normal_after_attack'] = float((proba[after] >= threshold).mean()) if after.any() else None
        out['thresholds'][name] = m
    return out


def test(args):
    output = args.output
    attempt = output.with_name(output.stem + '_attempt.json')
    check_release_guard(args.selection, args.selection_sha256, output, attempt)
    selection = json.loads(args.selection.read_text())
    for name, entry in selection['files'].items():
        if digest(ROOT / entry['path']) != entry['sha256']:
            raise ValueError(f'{name} changed since selection')
    with attempt.open('x') as stream:
        json.dump({'selection_sha256': args.selection_sha256, 'started_unix': time.time()}, stream)
    train = training_frame()
    tests = {name: load(name, calibration) for name, calibration in TESTS.items()}
    result = {'selection_sha256': args.selection_sha256, 'versions': versions(),
              'test_files': {n: {'path': FILES[n], 'sha256': digest(ROOT / FILES[n]),
                                 'calibration': FILES[c]} for n, c in TESTS.items()},
              'phase2_rule_auprc': {n: rule_auprc(f) for n, f in tests.items()}, 'variants': {}}
    for variant, columns in VARIANTS.items():
        chosen = selection['selected'][variant]
        thresholds = {'0.5': 0.5, 'oof_f1': chosen['oof_f1_threshold']}
        result['variants'][variant] = {'max_depth': chosen['max_depth'], 'files': {}}
        model = XGBClassifier(**COMMON, max_depth=chosen['max_depth'], n_estimators=100)
        model.fit(train[columns].to_numpy(dtype=np.float32), train.label.to_numpy())
        for name, frame in tests.items():
            proba = model.predict_proba(frame[columns].to_numpy(dtype=np.float32))[:, 1]
            np.save(OUTPUTS / f'replay_rhythm_proba_{variant}_{name}.npy', proba)
            result['variants'][variant]['files'][name] = evaluate(frame, proba, thresholds)
            f1 = result['variants'][variant]['files'][name]['thresholds']['oof_f1']['attack_f1']
            print(f'{variant} {name}: F1 at OOF threshold {f1}')
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    s = sub.add_parser('select')
    s.add_argument('--output', type=Path, default=OUTPUTS / 'replay_selection.json')
    t = sub.add_parser('test')
    t.add_argument('--selection', type=Path, default=OUTPUTS / 'replay_selection.json')
    t.add_argument('--selection-sha256', required=True)
    t.add_argument('--output', type=Path, default=OUTPUTS / 'replay_rhythm_test.json')
    args = parser.parse_args()
    select(args) if args.command == 'select' else test(args)


if __name__ == '__main__':
    main()
