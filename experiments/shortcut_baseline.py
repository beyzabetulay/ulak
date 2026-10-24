"""Grouped out-of-file shortcut ablation on the challenge training partition."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import precision_recall_fscore_support
from sklearn.model_selection import GroupKFold
from sklearn.tree import DecisionTreeClassifier

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ['can_id_dec', 'dlc'] + [f'byte_{i}' for i in range(8)]
CONFIGS = {'id_only': ['can_id_dec'], 'all_features': FEATURES,
           'without_id': FEATURES[1:]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'features_train.parquet')
    parser.add_argument('--output', type=Path, default=ROOT / 'experiments/results/shortcut_baseline.md')
    parser.add_argument('--folds', type=int, default=5)
    parser.add_argument('--max-depth', type=int, default=6)
    args = parser.parse_args()
    df = pd.read_parquet(args.input, columns=FEATURES + ['label_bin', 'attack_type', 'source_file', 'split'])
    if not df['split'].eq('train').all() or not df.label_bin.isin([0, 1]).all():
        raise ValueError('Expected training partition with binary labels')
    if df.source_file.isna().any() or df.attack_type.isna().any():
        raise ValueError('Missing grouping metadata')
    y = df.label_bin.to_numpy(dtype=np.uint8)
    groups = df.source_file.to_numpy()
    folds = list(GroupKFold(n_splits=args.folds).split(df, y, groups))
    lines = ['# Shortcut baseline', '',
             f'Input: `{args.input.name}`; {len(df):,} rows, {df.source_file.nunique()} source files. No subsampling.',
             f'Environment: numpy {np.__version__}, pandas {pd.__version__}, scikit-learn {sklearn.__version__}.',
             f'{args.folds}-fold GroupKFold by source_file; pooled out-of-fold predictions. '
             f'DecisionTreeClassifier(max_depth={args.max_depth}, min_samples_leaf=20, random_state=42); no class weighting.',
             'Missing payload bytes use a fixed -1 sentinel (outside 0–255); no learned preprocessing. '
             'Only can_id_dec, dlc and byte_0..7 are eligible features. Timing features are outside this ablation.', '',
             'Attack type identifies the source trace, not the frame label. Each trace subset includes normal and attack frames; '
             'precision includes false positives on normal frames in those traces. Normal-only traces have no attack support. '
             'Undefined metrics are reported as zero. These observational ablations do not establish causal shortcut reliance.', '',
             '| Configuration | Trace attack type | Class | Support | Precision | Recall | F1 |',
             '|---|---|---|---:|---:|---:|---:|']
    scores = {}
    importances = []
    for config, columns in CONFIGS.items():
        x = df[columns].fillna(-1).to_numpy(dtype=np.float32)
        pred = np.empty(len(df), dtype=np.uint8)
        importance = []
        for fold, (train, valid) in enumerate(folds):
            assert not set(groups[train]) & set(groups[valid])
            model = DecisionTreeClassifier(max_depth=args.max_depth, min_samples_leaf=20, random_state=42)
            model.fit(x[train], y[train])
            pred[valid] = model.predict(x[valid])
            importance.append(model.feature_importances_)
            print(f'{config}: fold {fold + 1}/{args.folds} complete', flush=True)
        for kind in ['ALL'] + sorted(df.attack_type.unique()):
            mask = np.ones(len(df), dtype=bool) if kind == 'ALL' else df.attack_type.eq(kind).to_numpy()
            p, r, f, n = precision_recall_fscore_support(y[mask], pred[mask], labels=[0, 1], zero_division=0)
            scores[config, kind] = f[1]
            for label, name in enumerate(['normal', 'attack']):
                lines.append(f'| {config} | {kind} | {name} | {n[label]:,} | {p[label]:.4f} | {r[label]:.4f} | {f[label]:.4f} |')
        if config == 'all_features':
            importances = np.asarray(importance)
        del x
    lines += ['', '## Feature importances', '', 'Impurity importances for all_features, mean ± standard deviation across held-out-file folds. '
              'These are descriptive and can favor high-cardinality features.', '', '| Feature | Mean | Std |', '|---|---:|---:|']
    for name, mean, std in zip(FEATURES, importances.mean(axis=0), importances.std(axis=0)):
        lines.append(f'| {name} | {mean:.4f} | {std:.4f} |')
    lines += ['', '## Attack F1 change after removing ID', '', '| Trace attack type | All features F1 | Without ID F1 | Drop (all − without) |', '|---|---:|---:|---:|']
    for kind in sorted(df.attack_type.unique()):
        a, b = scores['all_features', kind], scores['without_id', kind]
        lines.append(f'| {kind} | {a:.4f} | {b:.4f} | {a-b:+.4f} |')
    dos = df.attack_type.eq('DoS') & df.label_bin.eq(1)
    normal = df.label_bin.eq(0)
    lines += ['', '## Direct checks on the full train partition', '',
              f'- DoS attack frames with ID zero: {df.loc[dos, "can_id_dec"].eq(0).sum():,}/{dos.sum():,}.',
              f'- Normal frames with ID zero: {df.loc[normal, "can_id_dec"].eq(0).sum():,}/{normal.sum():,}.',
              f'- Unique IDs in normal frames: {df.loc[normal, "can_id_dec"].nunique():,}.',
              f'- Unique IDs in Injection attack frames: {df.loc[df.attack_type.eq("Injection") & df.label_bin.eq(1), "can_id_dec"].nunique():,}.', '',
              '## Interpretation', '',
              'ID removal can improve Injection and Spoofing in this depth-limited model; a universal performance drop is not supported. '
              'Replay remains poorly detected. These scores depend on the chosen tree and source-file folds.',
              'The documented 155 normal IDs is not reproduced in the training partition; use the direct count above. '
              'ID zero covers every DoS attack frame and no normal training frames, but the fitted tree can also flag other IDs and produce false positives.', '',
              '## Fold membership', '']
    for i, (_, valid) in enumerate(folds, 1):
        lines.append(f'- Fold {i}: ' + ', '.join(sorted(set(groups[valid]))))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
