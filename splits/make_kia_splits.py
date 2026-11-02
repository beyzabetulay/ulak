"""Write positional indices and feature contracts for the Kia Soul single-vehicle experiments."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from make_splits import sha256

ROOT = Path(__file__).resolve().parents[1]
ATTACKS = ['DoS', 'Injection', 'Spoofing', 'Replay']
BYTES = [f'byte_{i}' for i in range(8)]
VARIANTS = {
    'standard': ['can_id_dec', 'dlc'] + BYTES,
    'id_masked': ['dlc'] + BYTES,
    'id_masked_timing': ['dlc'] + BYTES + ['iat_id', 'iat_bus'],
    'full': ['can_id_dec', 'dlc'] + BYTES + ['iat_id', 'iat_bus', 'bus_count_100ms'],
}
FORBIDDEN = ['timestamp', 'can_id', 'vehicle', 'attack_type', 'source_file', 'source_folder',
             'recording_id', 'round', 'split', 'label', 'label_bin']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'kia_soul_features_all.parquet')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'splits/generated/kia_soul')
    args = parser.parse_args()
    df = pd.read_parquet(args.input, columns=['vehicle', 'attack_type', 'recording_id', 'label_bin', 'split'])
    if not df.vehicle.eq('Kia_Soul').all() or not df.label_bin.isin([0, 1]).all():
        raise ValueError('Expected Kia Soul rows with binary labels')
    if df[['attack_type', 'recording_id', 'split']].isna().any().any():
        raise ValueError('Missing grouping metadata')
    train_part = df.split.eq('train')
    if not set(ATTACKS) <= set(df[train_part].attack_type):
        raise ValueError('All four attack types must be present in the training partition')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {'input': str(args.input.resolve()), 'sha256': sha256(args.input),
                'rows': len(df), 'index_semantics': 'zero-based row positions in the unchanged input parquet',
                'target': 'label_bin', 'group': 'recording_id',
                'variants': VARIANTS, 'forbidden_features': FORBIDDEN, 'folds': []}

    # leave-one-attack-out: the held-out attack's recordings are unseen during training;
    # attack-free recordings always stay in training
    folds = [(f'unseen_{a.lower()}', {'held_out_attack': a},
              train_part & df.attack_type.ne(a), train_part & df.attack_type.eq(a)) for a in ATTACKS]
    # HCRL's own partition: *_train folders vs. *_release folders (attack type withheld)
    folds.append(('official', {'held_out_attack': None}, train_part, df.split.eq('test')))

    for name, info, train_mask, test_mask in folds:
        train = np.flatnonzero(train_mask.to_numpy())
        test = np.flatnonzero(test_mask.to_numpy())
        if set(df.recording_id.iloc[train]) & set(df.recording_id.iloc[test]):
            raise ValueError(f'{name}: recording overlap between train and test')
        fold = {'name': name, **info}
        for part, indices in [('train', train), ('test', test)]:
            filename = f'{name}_{part}.npy'
            np.save(args.output_dir / filename, indices, allow_pickle=False)
            fold[part] = {'indices': filename, 'rows': len(indices),
                          'recordings': sorted(df.recording_id.iloc[indices].unique()),
                          'class_counts': {str(k): int(v) for k, v in df.iloc[indices].label_bin.value_counts().items()}}
        manifest['folds'].append(fold)
        print(f'{name}: train={len(train):,} ({fold["train"]["class_counts"].get("1", 0):,} attack), '
              f'test={len(test):,} ({fold["test"]["class_counts"].get("1", 0):,} attack)')
    (args.output_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
