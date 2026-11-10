"""DoS without the ID 0 cue: add an ID-swapped copy of the Kia DoS recording to training.

Every model of the cross-vehicle test detected DoS through ID 0 only. This retrains the same
four variants with the same depth and threshold (from the cross-vehicle selection file), adding
a copy of the Kia Flooding recording whose ID 0 attack frames carry Kia's most frequent clean-drive
ID. The Spark and Sonata test sets are the same as before, so this is a second look at them.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from xgboost import XGBClassifier

if __package__:
    from .kia_release_test import versions
    from .kia_xgboost_baseline import COMMON, digest
    from .shortcut_transfer_test import (OUTPUTS, VARIANTS, attack_type, evaluate, kia_frames, kia_matrix,
                                         swap_dos_id, test_sets)
else:
    from kia_release_test import versions
    from kia_xgboost_baseline import COMMON, digest
    from shortcut_transfer_test import (OUTPUTS, VARIANTS, attack_type, evaluate, kia_frames, kia_matrix,
                                        swap_dos_id, test_sets)


def add_swapped_dos(raw):
    """Return the recordings plus an ID-swapped copy of each DoS recording and the ID used."""
    free = [f for name, f in raw.items() if attack_type(name) == 'Normal']
    common_id = int(np.bincount(np.concatenate([f.id.to_numpy() for f in free])).argmax())
    augmented = dict(raw)
    for name, frame in raw.items():
        if attack_type(name) == 'DoS':
            augmented[f'{name}:id_swapped_to_{common_id:X}'] = swap_dos_id(frame, common_id)
    return augmented, common_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection', type=Path, default=OUTPUTS / 'shortcut_selection.json')
    parser.add_argument('--output', type=Path, default=OUTPUTS / 'dos_id_swap_training.json')
    args = parser.parse_args()
    selection = json.loads(args.selection.read_text())
    raw, common_id = add_swapped_dos(kia_frames())
    train = kia_matrix(raw, [r for r in raw if attack_type(r) == 'Normal'])
    sets = test_sets()
    result = {'selection_sha256': digest(args.selection), 'versions': versions(),
              'kia_swap_id': f'{common_id:X}', 'variants': {}}
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
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(args.output)


if __name__ == '__main__':
    main()
