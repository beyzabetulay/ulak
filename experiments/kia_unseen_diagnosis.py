"""Diagnose why a tree misses held-out DoS and Replay attacks on Kia Soul."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SPLITS = ROOT / 'splits' / 'generated' / 'kia_soul'
PARQUET = ROOT / 'kia_soul_features_all.parquet'
BYTES = [f'byte_{i}' for i in range(8)]


def load_fold(df, manifest, name):
    fold = next(f for f in manifest['folds'] if f['name'] == name)
    train = df.iloc[np.load(SPLITS / fold['train']['indices'])]
    test = df.iloc[np.load(SPLITS / fold['test']['indices'])]
    return train, test


def dos(df, manifest):
    train, test = load_fold(df, manifest, 'unseen_dos')
    print('DoS (fold unseen_dos)')
    zero_id = train[train['can_id_dec'] == 0]
    print('training rows with can_id_dec == 0:', len(zero_id))
    print(zero_id.groupby(['recording_id', 'label_bin']).size().to_string())
    all_zero = (train[BYTES].fillna(-1) == 0).all(axis=1)
    print('training rows with all eight bytes 0, by label:')
    print(train[all_zero].groupby('label_bin').size().to_string())
    print('distinct IDs among them:', train[all_zero]['can_id_dec'].nunique())
    attacks = test[test['label_bin'] == 1]
    normals = test[test['label_bin'] == 0]
    print('test attack rows:', len(attacks), '| distinct IDs:',
          sorted(attacks['can_id_dec'].unique().tolist()))
    print('test normal rows with can_id_dec == 0:',
          int((normals['can_id_dec'] == 0).sum()))


def replay(df, manifest):
    train, test = load_fold(df, manifest, 'unseen_replay')
    cols = ['can_id_dec', 'dlc'] + BYTES
    known = train[train['label_bin'] == 0][cols].fillna(-1).drop_duplicates()

    def match_share(rows):
        merged = rows[cols].fillna(-1).merge(
            known, on=cols, how='left', indicator=True)
        return (merged['_merge'] == 'both').mean()

    print('Replay (fold unseen_replay)')
    print('share of test rows identical (ID, DLC, bytes) to a training normal row:')
    print('  attack rows:', round(match_share(test[test['label_bin'] == 1]), 3))
    print('  normal rows:', round(match_share(test[test['label_bin'] == 0]), 3))


def main():
    manifest = json.loads((SPLITS / 'manifest.json').read_text())
    with PARQUET.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == manifest['sha256'], \
            'Parquet changed since the splits were generated'
    df = pd.read_parquet(PARQUET)
    dos(df, manifest)
    print()
    replay(df, manifest)


if __name__ == '__main__':
    main()
