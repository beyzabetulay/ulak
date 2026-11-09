"""Describe missed Spoofing frames and depth-6 false alarms without tuning."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

if __package__:
    from .kia_known_attack import known_recording_folds
    from .kia_xgboost_baseline import COMMON, FEATURES, digest, scores
else:
    from kia_known_attack import known_recording_folds
    from kia_xgboost_baseline import COMMON, FEATURES, digest, scores

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ['car_track_final_1st_train/Malfunction_1st_dataset_KIA_Soul_train.csv',
           'car_track_preliminary_train/Malfunction_KIA_Soul_train.csv']


def signature_counts(frame):
    return frame[FEATURES].fillna(-1).groupby(FEATURES, dropna=False).size().rename('count').reset_index()


def summary(part, normal_signatures, attack_signatures):
    signatures = part[FEATURES].fillna(-1)
    normal_match = signatures.merge(normal_signatures, on=FEATURES, how='left')['count'].notna()
    attack_match = signatures.merge(attack_signatures, on=FEATURES, how='left')['count'].notna()
    return {'rows': len(part), 'unique_signatures': len(signatures.drop_duplicates()),
            'exact_normal_training_matches': int(normal_match.sum()),
            'exact_attack_training_matches': int(attack_match.sum()),
            'id_counts': {str(k): int(v) for k, v in part.can_id_dec.value_counts().items()},
            'probability_quantiles': {str(k): float(v) for k, v in part.probability.quantile([0, .1, .5, .9, 1]).items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'experiments/kia_decision_tree/local_outputs/spoofing_diagnosis.json')
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'splits/generated/kia_soul/manifest.json').read_text())
    path = ROOT / 'kia_soul_features_all.parquet'
    if digest(path) != manifest['sha256'] or manifest['variants']['standard'] != FEATURES:
        raise ValueError('Parquet hash mismatch')
    previous = json.loads((ROOT / 'experiments/kia_decision_tree/local_outputs/known_attack.json').read_text())
    if previous['input_sha256'] != manifest['sha256']:
        raise ValueError('Earlier experiment input mismatch')
    df = pd.read_parquet(path, columns=FEATURES + ['label_bin', 'recording_id', 'split', 'attack_type'])
    X = df[FEATURES].fillna(-1).to_numpy(dtype=np.float32)
    result = {'input_sha256': manifest['sha256'], 'purpose': 'descriptive diagnosis; no tuning', 'recordings': []}
    for _, recording, train, test in known_recording_folds(df):
        if recording not in TARGETS:
            continue
        reference = next(f for f in previous['folds'] if f['test_recording'] == recording)
        training = df.iloc[train]
        normal_signatures = signature_counts(training[training.label_bin == 0])
        attack_signatures = signature_counts(training[training.label_bin == 1])
        entry = {'recording': recording, 'models': []}
        for depth in [3, 6]:
            model = XGBClassifier(**COMMON, max_depth=depth, n_estimators=100)
            model.fit(X[train], df.label_bin.to_numpy()[train])
            part = df.iloc[test].copy()
            part['probability'] = model.predict_proba(X[test])[:, 1]
            prediction = (part.probability >= .5).astype(np.int8)
            metrics = scores(part.label_bin, prediction)
            old = next(m for m in reference['models'] if m['model'] == f'xgboost_depth{depth}')
            if metrics != old['evaluation']:
                raise ValueError('Reproduced metrics differ from previous run')
            groups = {'attacks': part[part.label_bin == 1],
                      'false_alarms': part[(part.label_bin == 0) & (part.probability >= .5)],
                      'correct_normal': part[(part.label_bin == 0) & (part.probability < .5)]}
            item = {'depth': depth, 'metrics': metrics,
                    'groups': {name: summary(p, normal_signatures, attack_signatures)
                               for name, p in groups.items() if len(p)}}
            # Identify exact input signatures that carry both labels within the
            # evaluation recording. This is ambiguity for content-only models.
            label_counts = part[FEATURES + ['label_bin']].fillna(-1).groupby(FEATURES).label_bin.nunique()
            mixed = label_counts[label_counts > 1].reset_index()[FEATURES]
            item['attack_rows_sharing_content_with_test_normal'] = len(
                part[part.label_bin == 1][FEATURES].fillna(-1).merge(mixed, on=FEATURES))
            entry['models'].append(item)
            print(recording, json.dumps(item), flush=True)
        alarm_ids = set()
        for item in entry['models']:
            alarm_ids.update(item['groups'].get('false_alarms', {}).get('id_counts', {}))
        entry['alarm_id_training_context'] = {}
        for identifier in sorted(alarm_ids, key=int):
            identifier = int(identifier)
            same_id = training[training.can_id_dec == identifier]
            normal = same_id[same_id.label_bin == 0]
            evaluated_normal = df.iloc[test].loc[lambda x: (x.can_id_dec == identifier) & (x.label_bin == 0)]
            byte_columns = [f'byte_{i}' for i in range(8)]
            entry['alarm_id_training_context'][str(identifier)] = {
                'training_normal_rows': len(normal), 'training_attack_rows': int((same_id.label_bin == 1).sum()),
                'training_normal_byte_min': normal[byte_columns].min().to_dict(),
                'training_normal_byte_max': normal[byte_columns].max().to_dict(),
                'evaluation_normal_byte_min': evaluated_normal[byte_columns].min().to_dict(),
                'evaluation_normal_byte_max': evaluated_normal[byte_columns].max().to_dict()}
        result['recordings'].append(entry)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
