"""Create recording-grouped inner validation folds for the existing Kia splits."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from make_splits import sha256

ROOT = Path(__file__).resolve().parents[1]


def make_folds(df, outer_train, outer_test, n_splits=4):
    """Assign whole recordings, ensuring each validation fold has both labels."""
    outer_train = np.asarray(outer_train)
    outer_test = np.asarray(outer_test)
    for name, positions in [('train', outer_train), ('test', outer_test)]:
        if positions.ndim != 1 or not np.issubdtype(positions.dtype, np.integer):
            raise ValueError(f'{name} indices must be a one-dimensional integer array')
        if (positions < 0).any() or (positions >= len(df)).any() or len(np.unique(positions)) != len(positions):
            raise ValueError(f'{name} indices are invalid or duplicated')
    if np.intersect1d(outer_train, outer_test).size:
        raise ValueError('Outer train and test overlap')
    groups = df.iloc[outer_train].recording_id
    test_groups = set(df.iloc[outer_test].recording_id)
    if groups.isna().any() or df.iloc[outer_test].recording_id.isna().any():
        raise ValueError('Missing recording_id')
    if set(groups) & test_groups:
        raise ValueError('Outer train and test recordings overlap')
    rows = df.iloc[outer_train]
    counts = rows.groupby('recording_id', sort=True).label_bin.agg(['size', 'sum'])
    mixed = counts[(counts['sum'] > 0) & (counts['sum'] < counts['size'])]
    if len(mixed) < n_splits:
        raise ValueError(f'Need at least {n_splits} recordings containing both classes, got {len(mixed)}')
    # Place the largest mixed recordings first, one per fold. Assign the rest to
    # the smallest fold; stable identifiers break ties deterministically.
    ordered_mixed = sorted(mixed.index, key=lambda key: (-counts.loc[key, 'size'], key))
    remaining = sorted(counts.index.difference(mixed.index), key=lambda key: (-counts.loc[key, 'size'], key))
    assignment = [[] for _ in range(n_splits)]
    sizes = [0] * n_splits
    for key in ordered_mixed + remaining:
        fold = min(range(n_splits), key=lambda i: (sizes[i], i))
        assignment[fold].append(key)
        sizes[fold] += int(counts.loc[key, 'size'])
    result = []
    for recording_ids in assignment:
        mask = groups.isin(recording_ids).to_numpy()
        result.append((outer_train[~mask], outer_train[mask]))
    return result


def describe(df, indices, filename):
    rows = df.iloc[indices]
    return {'indices': filename, 'rows': len(indices),
            'recordings': sorted(rows.recording_id.unique().tolist()),
            'class_counts': {str(k): int(v) for k, v in rows.label_bin.value_counts().sort_index().items()},
            'attack_type_counts': {str(k): int(v) for k, v in rows.attack_type.value_counts().sort_index().items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'kia_soul_features_all.parquet')
    parser.add_argument('--splits-dir', type=Path, default=ROOT / 'splits/generated/kia_soul')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'splits/generated/kia_soul/validation_balanced')
    parser.add_argument('--folds', type=int, default=4)
    args = parser.parse_args()
    if args.folds < 2:
        parser.error('--folds must be at least 2')
    outer = json.loads((args.splits_dir / 'manifest.json').read_text())
    if sha256(args.input) != outer['sha256']:
        raise ValueError('Input parquet does not match outer split manifest')
    df = pd.read_parquet(args.input, columns=['recording_id', 'attack_type', 'label_bin'])
    if len(df) != outer['rows'] or df.isna().any().any() or not df.label_bin.isin([0, 1]).all():
        raise ValueError('Invalid input rows, labels or grouping metadata')
    result = {'input_sha256': outer['sha256'], 'outer_manifest_sha256': sha256(args.splits_dir / 'manifest.json'),
              'index_semantics': 'zero-based row positions in the unchanged input parquet',
              'group': 'recording_id', 'method': 'deterministic mixed-recording-first greedy row balance',
              'n_splits': args.folds, 'outer_folds': []}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for outer_fold in outer['folds']:
        name = outer_fold['name']
        train = np.load(args.splits_dir / outer_fold['train']['indices'], allow_pickle=False)
        test = np.load(args.splits_dir / outer_fold['test']['indices'], allow_pickle=False)
        folds = make_folds(df, train, test, args.folds)
        entry = {'name': name, 'folds': []}
        for number, (inner_train, valid) in enumerate(folds, 1):
            parts = {}
            for part, indices in [('train', inner_train), ('validation', valid)]:
                filename = f'{name}_fold{number}_{part}.npy'
                np.save(args.output_dir / filename, indices, allow_pickle=False)
                parts[part] = describe(df, indices, filename)
            entry['folds'].append({'fold': number, **parts})
            print(f'{name} fold {number}: train={len(inner_train):,}, validation={len(valid):,}, '
                  f'validation classes={parts["validation"]["class_counts"]}')
        result['outer_folds'].append(entry)
    (args.output_dir / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
