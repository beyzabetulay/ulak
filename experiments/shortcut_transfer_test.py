"""Shortcut test across vehicles: train on Kia Soul, test once on Chevrolet Spark and Hyundai Sonata.

Spark shares 3 of its 83 normal CAN IDs with Kia, Sonata 22 of 27, so ID and payload
memorisation cannot transfer to Spark. `select` chooses depth and threshold per variant on the
seen-type Kia inner folds and writes the hypotheses before any test file is read. `test` refits
on all nine Kia training recordings and evaluates the Spark and Sonata recordings once, plus a
synthetic copy of each DoS (Flooding) recording whose ID 0 attack frames get a normal ID.
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

if __package__:
    from .kia_release_test import check_release_guard, choose_depth, fit_predict, metrics, oof_threshold, versions
    from .kia_xgboost_baseline import CANDIDATES, COMMON, digest
    from .replay_rhythm_test import read_raw, rhythm_features
else:
    from kia_release_test import check_release_guard, choose_depth, fit_predict, metrics, oof_threshold, versions
    from kia_xgboost_baseline import CANDIDATES, COMMON, digest
    from replay_rhythm_test import read_raw, rhythm_features

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / 'experiments/kia_decision_tree/local_outputs'
VALIDATION = ROOT / 'splits/generated/kia_soul/validation_seen/manifest.json'
OUTER = ROOT / 'splits/generated/kia_soul/manifest.json'
PRE, F1ST, F2ND = 'car_track_preliminary_train/', 'car_track_final_1st_train/', 'car_track_final_2nd_train/'
VEHICLES = {
    'spark': {'calibration': PRE + 'Attack_free_CHEVROLET_Spark_train.csv', 'calibration_half': 'first',
              'clean': PRE + 'Attack_free_CHEVROLET_Spark_train.csv', 'clean_half': 'second',
              'attacks': [PRE + 'Flooding_CHEVROLET_Spark_train.csv', PRE + 'Fuzzy_CHEVROLET_Spark_train.csv',
                          PRE + 'Malfunction_CHEVROLET_Spark_train.csv']},
    'sonata': {'calibration': F1ST + 'Attack_free_HY_Sonata_train.csv', 'calibration_half': None,
               'clean': PRE + 'Attack_free_HYUNDAI_Sonata_train.csv', 'clean_half': None,
               'attacks': [PRE + 'Flooding_HYUNDAI_Sonata_train.csv', PRE + 'Fuzzy_HYUNDAI_Sonata_train.csv',
                           F1ST + 'Fuzzy_dataset_HY_Sonata_train.csv', PRE + 'Malfunction_HYUNDAI_Sonata_train.csv',
                           F1ST + 'Malfunction_1st_dataset_HY_Sonata_train.csv',
                           F2ND + 'Malfunction_2nd_HY_Sonata_train.csv']},
}
BYTES = [f'byte_{i}' for i in range(8)]
RHYTHM = ['gap1', 'gap2', 'phase2', 'gap3', 'phase3', 'count100', 'bits1', 'bits2', 'dlc']
VARIANTS = {'A_standard': ['can_id_dec', 'dlc'] + BYTES, 'B_no_id': ['dlc'] + BYTES,
            'C_standard_iat_id': ['can_id_dec', 'dlc'] + BYTES + ['iat_id'], 'T_rhythm_no_id': RHYTHM}
HYPOTHESES = {
    'H1': 'A and C lose most F1 on Spark Fuzzy and Malfunction: F1 below half of their Kia validation '
          'F1 for the same attack type (Injection, Spoofing), at the frozen threshold.',
    'H2': 'B drops less than A: relative F1 drop of B smaller than that of A on both Spark files.',
    'H3': 'T scores a higher F1 than A on both Spark Fuzzy and Malfunction.',
    'H4': 'On both Flooding files A and C reach recall >= 0.9; after the ID swap A and C fall below '
          'recall 0.5 while T keeps at least half of its unswapped recall.',
}


def attack_type(path):
    name = Path(path).name.lower()
    for key, kind in (('flooding', 'DoS'), ('fuzzy', 'Injection'), ('malfunction', 'Spoofing'),
                      ('replay', 'Replay'), ('attack_free', 'Normal')):
        if key in name:
            return kind
    raise ValueError(f'Unknown attack type for {path}')


def half(frame, which):
    """Rows of the first or second half of the recording's time span."""
    if which is None:
        return frame
    middle = (frame.t.min() + frame.t.max()) / 2
    return frame[frame.t < middle] if which == 'first' else frame[frame.t >= middle]


def periods_of(frames):
    """Median same-ID gap over several recordings, without gaps across recording borders."""
    gaps = pd.concat([pd.DataFrame({'id': f.id, 'gap': f.groupby('id').t.diff()}) for f in frames])
    return gaps.groupby('id').gap.median().dropna()


def features(frame, period, name):
    """Payload (-1 after the DLC), raw same-ID gap and rhythm features for one recording."""
    out = rhythm_features(frame, period)
    out['can_id_dec'] = frame.id.to_numpy()
    dlc = frame.dlc.to_numpy()
    for i in range(8):
        out[f'byte_{i}'] = np.where(i < dlc, frame[f'b{i}'].to_numpy(dtype=np.int16), -1)
    out['iat_id'] = frame.groupby('id', sort=False).t.diff().to_numpy()
    out['file'] = name
    return out


def swap_dos_id(frame, new_id):
    """Synthetic counterfactual: give every ID 0 attack frame the vehicle's most frequent normal ID."""
    swapped = frame.copy()
    swapped.loc[(swapped.label == 1) & (swapped.id == 0), 'id'] = new_id
    return swapped


def kia_frames():
    outer = json.loads(OUTER.read_text())
    recordings = next(f for f in outer['folds'] if f['name'] == 'official')['train']['recordings']
    return {r: read_raw(ROOT / r) for r in recordings}


def kia_matrix(raw, calibration):
    period = periods_of([raw[c] for c in calibration])
    return pd.concat([features(f, period, name) for name, f in raw.items()], ignore_index=True)


def per_type_f1(df, proba, threshold):
    out = {}
    for kind in ('Injection', 'Spoofing'):
        mask = df.file.map(attack_type).eq(kind).to_numpy()
        if mask.any():
            out[kind] = metrics(df.label.to_numpy()[mask], proba[mask], threshold)['attack_f1']
    return out


def select(args):
    raw = kia_frames()
    free = [r for r in raw if attack_type(r) == 'Normal']
    folds = json.loads(VALIDATION.read_text())['outer_folds'][0]['folds']
    fold_data = []
    for fold in folds:
        valid_recordings = set(fold['validation']['recordings'])
        calibration = [r for r in free if r not in valid_recordings]  # inner-training attack-free only
        df = kia_matrix(raw, calibration)
        fold_data.append((df, df.file.isin(valid_recordings).to_numpy(), calibration))
    result = {'hypotheses': HYPOTHESES, 'versions': versions(), 'variants': VARIANTS,
              'validation_manifest_sha256': digest(VALIDATION),
              'kia_files': {r: digest(ROOT / r) for r in raw},
              'fold_calibration': [c for _, _, c in fold_data],
              'rule': 'unweighted mean fold AUPRC, shallower depth on ties; OOF-F1 threshold', 'selected': {}}
    for variant, columns in VARIANTS.items():
        configurations = []
        for parameters in CANDIDATES:
            fold_scores, oof_y, oof_p, oof_rows = [], [], [], []
            for df, valid, _ in fold_data:
                X, y = df[columns].to_numpy(dtype=np.float32), df.label.to_numpy()
                proba = fit_predict(X, y, np.flatnonzero(~valid), np.flatnonzero(valid), parameters['max_depth'])
                fold_scores.append(metrics(y[valid], proba, 0.5))
                oof_y.append(y[valid]); oof_p.append(proba); oof_rows.append(df[valid])
            configurations.append({'parameters': parameters, 'folds': fold_scores,
                                   'mean_auprc': float(np.mean([s['auprc'] for s in fold_scores])),
                                   'oof': (np.concatenate(oof_y), np.concatenate(oof_p), pd.concat(oof_rows))})
        best = choose_depth(configurations)
        y, proba, rows = best['oof']
        threshold = oof_threshold(y, proba)
        result['selected'][variant] = {
            'max_depth': best['parameters']['max_depth'], 'oof_f1_threshold': threshold,
            'oof_at_threshold': metrics(y, proba, threshold),
            'kia_validation_f1_by_type': per_type_f1(rows, proba, threshold),
            'configurations': [{k: v for k, v in c.items() if k != 'oof'} for c in configurations]}
        print(f"{variant}: depth {best['parameters']['max_depth']}, mean AUPRC {best['mean_auprc']:.3f}, "
              f"threshold {threshold:.3f}, Kia F1 by type {result['selected'][variant]['kia_validation_f1_by_type']}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(f'{args.output}\nsha256 {digest(args.output)}')


def evaluate(frame, proba, thresholds):
    y = frame.label.to_numpy()
    duration = float(frame.t.max() - frame.t.min())
    out = {'rows': len(frame), 'attacks': int(y.sum()), 'duration_s': duration, 'thresholds': {}}
    for name, threshold in thresholds.items():
        m = metrics(y, proba, threshold)
        m['false_alarms_per_s'] = m['fp'] / duration if duration > 0 else None
        out['thresholds'][name] = m
    return out


def test_sets():
    """Test frames per vehicle: attack recordings, the swapped DoS copy and the clean drive."""
    sets = {}
    for vehicle, spec in VEHICLES.items():
        calibration = half(read_raw(ROOT / spec['calibration']), spec['calibration_half'])
        period = periods_of([calibration])
        common_id = int(calibration.id.value_counts().idxmax())
        for path in spec['attacks']:
            frame = read_raw(ROOT / path)
            sets[f'{vehicle}:{path}'] = features(frame, period, path)
            if attack_type(path) == 'DoS':
                sets[f'{vehicle}:{path}:id_swapped_to_{common_id:X}'] = features(swap_dos_id(frame, common_id), period, path)
        clean = read_raw(ROOT / spec['clean'])
        clean_rows = features(clean, period, spec['clean']).loc[half(clean, spec['clean_half']).index]
        sets[f"{vehicle}:{spec['clean']}:{spec['clean_half'] or 'full'}"] = clean_rows
    return sets


def check_hypotheses(results, selection):
    def f1(v, key):
        return results[v][key]['thresholds']['oof_f1']['attack_f1']

    def recall(v, key):
        return results[v][key]['thresholds']['oof_f1']['attack_recall']

    spark = {'Injection': 'spark:' + PRE + 'Fuzzy_CHEVROLET_Spark_train.csv',
             'Spoofing': 'spark:' + PRE + 'Malfunction_CHEVROLET_Spark_train.csv'}
    kia = {v: selection['selected'][v]['kia_validation_f1_by_type'] for v in VARIANTS}
    drop = {v: {k: 1 - f1(v, key) / kia[v][k] if kia[v][k] else float('nan') for k, key in spark.items()}
            for v in VARIANTS}
    h1 = all(f1(v, key) < 0.5 * kia[v][k] for v in ('A_standard', 'C_standard_iat_id') for k, key in spark.items())
    h2 = all(drop['B_no_id'][k] < drop['A_standard'][k] for k in spark)
    h3 = all(f1('T_rhythm_no_id', key) > f1('A_standard', key) for key in spark.values())
    floods = [k for k in results['A_standard'] if 'Flooding' in k and 'id_swapped' not in k]
    swapped = {k: next(s for s in results['A_standard'] if s.startswith(k + ':id_swapped')) for k in floods}
    h4 = all(recall(v, k) >= 0.9 and recall(v, swapped[k]) < 0.5 for v in ('A_standard', 'C_standard_iat_id')
             for k in floods) and all(recall('T_rhythm_no_id', swapped[k]) >= 0.5 * recall('T_rhythm_no_id', k)
                                      for k in floods)
    return {'H1': h1, 'H2': h2, 'H3': h3, 'H4': h4, 'relative_f1_drop_on_spark': drop}


def test(args):
    output = args.output
    attempt = output.with_name(output.stem + '_attempt.json')
    check_release_guard(args.selection, args.selection_sha256, output, attempt)
    selection = json.loads(args.selection.read_text())
    if digest(VALIDATION) != selection['validation_manifest_sha256'] or any(
            digest(ROOT / r) != h for r, h in selection['kia_files'].items()):
        raise ValueError('Kia inputs changed since selection')
    with attempt.open('x') as stream:
        json.dump({'selection_sha256': args.selection_sha256, 'started_unix': time.time()}, stream)
    raw = kia_frames()
    train = kia_matrix(raw, [r for r in raw if attack_type(r) == 'Normal'])
    sets = test_sets()
    result = {'selection_sha256': args.selection_sha256, 'versions': versions(), 'hypotheses': HYPOTHESES,
              'test_files': sorted({p for spec in VEHICLES.values() for p in spec['attacks'] + [spec['clean'], spec['calibration']]}),
              'test_file_sha256': {p: digest(ROOT / p) for spec in VEHICLES.values()
                                   for p in spec['attacks'] + [spec['clean'], spec['calibration']]},
              'variants': {}}
    for variant, columns in VARIANTS.items():
        chosen = selection['selected'][variant]
        thresholds = {'0.5': 0.5, 'oof_f1': chosen['oof_f1_threshold']}
        model = XGBClassifier(**COMMON, max_depth=chosen['max_depth'], n_estimators=100)
        model.fit(train[columns].to_numpy(dtype=np.float32), train.label.to_numpy())
        result['variants'][variant] = {}
        for key, frame in sets.items():
            proba = model.predict_proba(frame[columns].to_numpy(dtype=np.float32))[:, 1]
            result['variants'][variant][key] = evaluate(frame, proba, thresholds)
            m = result['variants'][variant][key]['thresholds']['oof_f1']
            print(f"{variant} {key}: F1 {m['attack_f1']} recall {m['attack_recall']} FA/s {m['false_alarms_per_s']:.2f}")
    result['hypothesis_results'] = check_hypotheses(result['variants'], selection)
    print(result['hypothesis_results'])
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    s = sub.add_parser('select')
    s.add_argument('--output', type=Path, default=OUTPUTS / 'shortcut_selection.json')
    t = sub.add_parser('test')
    t.add_argument('--selection', type=Path, default=OUTPUTS / 'shortcut_selection.json')
    t.add_argument('--selection-sha256', required=True)
    t.add_argument('--output', type=Path, default=OUTPUTS / 'shortcut_transfer_test.json')
    args = parser.parse_args()
    select(args) if args.command == 'select' else test(args)


if __name__ == '__main__':
    main()
