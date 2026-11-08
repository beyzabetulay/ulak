"""Describe past-only timing/payload transitions for the 130 missed Spoofing frames."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

if __package__:
    from .kia_xgboost_baseline import FEATURES, digest
else:
    from kia_xgboost_baseline import FEATURES, digest

ROOT = Path(__file__).resolve().parents[1]
RECORDING = 'car_track_final_1st_train/Malfunction_1st_dataset_KIA_Soul_train.csv'
BYTES = [f'byte_{i}' for i in range(8)]


def past_features(frame):
    ordered = frame.sort_values(['recording_id', 'timestamp'], kind='stable').copy()
    groups = ordered.groupby(['recording_id', 'can_id_dec'], sort=False)
    previous = groups[BYTES + ['dlc']].shift()
    comparable = previous.dlc.notna() & previous.dlc.eq(ordered.dlc)
    a = ordered[BYTES].fillna(0).to_numpy(dtype=np.uint8)
    b = previous[BYTES].fillna(0).to_numpy(dtype=np.uint8)
    bits = np.unpackbits(np.bitwise_xor(a, b), axis=1).sum(axis=1).astype(float)
    bits[~comparable.to_numpy()] = np.nan
    ordered['changed_bits'] = bits
    ordered['repeat_previous'] = np.where(comparable, bits == 0, np.nan)
    ordered['gap_id'] = groups.timestamp.diff()
    ordered['gap_bus'] = ordered.groupby('recording_id', sort=False).timestamp.diff()
    return ordered


def describe(frame):
    result = {'rows': len(frame)}
    for name in ['gap_id', 'gap_bus', 'changed_bits', 'repeat_previous']:
        values = frame[name]
        result[name] = {'missing': int(values.isna().sum()),
                        'mean': float(values.mean()),
                        'quantiles': {str(k): float(v) for k, v in values.quantile([0, .1, .5, .9, 1]).items()}}
    return result


def main():
    path = ROOT / 'kia_soul_features_all.parquet'
    manifest = json.loads((ROOT / 'splits/generated/kia_soul/manifest.json').read_text())
    if digest(path) != manifest['sha256']:
        raise ValueError('Input hash mismatch')
    df = pd.read_parquet(path, columns=FEATURES + ['recording_id', 'timestamp', 'label_bin'])
    part = past_features(df[df.recording_id == RECORDING])
    attacks = part[part.label_bin == 1]
    ids = set(attacks.can_id_dec)
    normal = part[(part.label_bin == 0) & part.can_id_dec.isin(ids)]
    signatures = attacks[FEATURES].fillna(-1).drop_duplicates()
    # Labels are used only to select diagnostic groups, never in past_features.
    normal_controls = normal[FEATURES].fillna(-1).merge(signatures.assign(match=True), on=FEATURES, how='left')['match'].notna().to_numpy()
    normals_matching = normal.loc[normal_controls]
    normal_signatures = normal[FEATURES].fillna(-1).drop_duplicates()
    matched_attacks = attacks[FEATURES].fillna(-1).merge(normal_signatures.assign(match=True), on=FEATURES, how='left')['match'].notna().to_numpy()
    overlap_attacks = attacks.loc[matched_attacks]
    a = overlap_attacks[FEATURES + ['gap_id', 'changed_bits']].fillna({name: -1 for name in FEATURES})
    n = normals_matching[FEATURES + ['gap_id', 'changed_bits']].fillna({name: -1 for name in FEATURES})
    paired = a.groupby(FEATURES)[['gap_id', 'changed_bits']].median().join(
        n.groupby(FEATURES)[['gap_id', 'changed_bits']].median(), lsuffix='_attack', rsuffix='_normal')
    output = {'input_sha256': manifest['sha256'], 'recording': RECORDING,
              'purpose': 'descriptive only, no model or threshold selection',
              'timestamp_ties': int(part.timestamp.duplicated().sum()),
              'matched_signature_comparison': {'signatures': len(paired),
                  'attack_median_gap_lower': int((paired.gap_id_attack < paired.gap_id_normal).sum()),
                  'attack_median_changed_bits_higher': int((paired.changed_bits_attack > paired.changed_bits_normal).sum())},
              'groups': {'all_attacks': describe(attacks), 'same_id_normal': describe(normal),
                         'overlap_attacks': describe(overlap_attacks),
                         'identical_content_normal': describe(normals_matching)},
              'by_id': {str(identifier): {'attack': describe(attacks[attacks.can_id_dec == identifier]),
                                         'normal': describe(normal[normal.can_id_dec == identifier])} for identifier in sorted(ids)}}
    target = ROOT / 'experiments/kia_decision_tree/local_outputs/spoofing_sequence.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
