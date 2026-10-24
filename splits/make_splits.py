"""Write positional indices and feature contracts for leave-one-vehicle-out evaluation."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ['can_id_dec', 'dlc'] + [f'byte_{i}' for i in range(8)]
VEHICLES = ['Chevrolet_Spark', 'Hyundai_Sonata', 'Kia_Soul']


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'features_train.parquet')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'splits/generated')
    args = parser.parse_args()
    df = pd.read_parquet(args.input, columns=['vehicle', 'source_file', 'label_bin', 'split'])
    if not df['split'].eq('train').all() or not df.label_bin.isin([0, 1]).all():
        raise ValueError('Expected training partition with binary labels')
    if df[['vehicle', 'source_file']].isna().any().any():
        raise ValueError('Missing grouping metadata')
    if set(df.vehicle.unique()) - set(VEHICLES + ['unknown']):
        raise ValueError('Unexpected vehicle values')
    if not set(VEHICLES).issubset(set(df.vehicle.unique())):
        raise ValueError('All three vehicles must be present')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {'input': str(args.input.resolve()), 'sha256': sha256(args.input),
                'rows': len(df), 'index_semantics': 'zero-based row positions in the unchanged input parquet',
                'excluded_unknown_rows': int(df.vehicle.eq('unknown').sum()), 'target': 'label_bin',
                'variants': {'standard': FEATURES, 'id_masked': FEATURES[1:]},
                'forbidden_features': ['vehicle', 'attack_type', 'source_file', 'source_folder', 'split', 'label', 'label_bin'],
                'folds': []}
    known = df.vehicle.isin(VEHICLES)
    for vehicle in VEHICLES:
        train = np.flatnonzero((known & df.vehicle.ne(vehicle)).to_numpy())
        test = np.flatnonzero(df.vehicle.eq(vehicle).to_numpy())
        if set(df.iloc[train].source_file) & set(df.iloc[test].source_file):
            raise ValueError('Source file overlap across vehicles')
        fold = {'held_out_vehicle': vehicle}
        for name, indices in [('train', train), ('test', test)]:
            filename = f'{vehicle}_{name}.npy'
            np.save(args.output_dir / filename, indices, allow_pickle=False)
            fold[name] = {'indices': filename, 'rows': len(indices),
                          'class_counts': {str(k): int(v) for k, v in df.iloc[indices].label_bin.value_counts().items()}}
        manifest['folds'].append(fold)
        print(f'{vehicle}: train={len(train):,}, test={len(test):,}')
    (args.output_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
