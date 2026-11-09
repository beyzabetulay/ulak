import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'splits'))
from make_kia_validation import make_folds, make_seen_type_folds


class KiaValidationTests(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame({'recording_id': np.repeat(list('abcdef'), 3),
                                'label_bin': [0, 0, 1] * 5 + [0, 0, 0]})
        self.train = np.arange(15)
        self.test = np.arange(15, 18)

    def test_folds_partition_outer_training_by_recording(self):
        folds = make_folds(self.df, self.train, self.test, 5)
        self.assertEqual(len(folds), 5)
        self.assertEqual(sorted(np.concatenate([v for _, v in folds]).tolist()), self.train.tolist())
        for train, valid in folds:
            self.assertEqual(set(train) | set(valid), set(self.train))
            self.assertFalse(set(train) & set(valid))
            self.assertFalse(set(self.df.iloc[train].recording_id) & set(self.df.iloc[valid].recording_id))
            self.assertFalse(set(valid) & set(self.test))
            self.assertEqual(set(self.df.iloc[valid].label_bin), {0, 1})
        again = make_folds(self.df, self.train, self.test, 5)
        for (_, valid), (_, repeated) in zip(folds, again):
            np.testing.assert_array_equal(valid, repeated)

    def test_rejects_overlap_and_too_few_groups(self):
        with self.assertRaises(ValueError):
            make_folds(self.df, self.train, np.array([14]), 5)
        with self.assertRaises(ValueError):
            make_folds(self.df, self.train, self.test, 6)
        with self.assertRaises(ValueError):
            make_folds(self.df, np.arange(14), np.array([14, 15]), 5)
        self.df.loc[self.df.recording_id == 'e', 'label_bin'] = 0
        with self.assertRaisesRegex(ValueError, 'recordings containing both classes'):
            make_folds(self.df, self.train, self.test, 5)


class SeenTypeFoldTests(unittest.TestCase):
    def setUp(self):
        recordings = {'dos': 'DoS', 'rep': 'Replay', 'inj1': 'Injection', 'inj2': 'Injection',
                      'sp1': 'Spoofing', 'sp2': 'Spoofing', 'sp3': 'Spoofing', 'free1': 'Normal',
                      'free2': 'Normal', 'test': 'mixed'}
        rows = []
        for rec, kind in recordings.items():
            labels = [0, 0, 0, 0] if kind == 'Normal' else [0, 0, 1, 1]
            rows += [(rec, kind, label) for label in labels]
        self.df = pd.DataFrame(rows, columns=['recording_id', 'attack_type', 'label_bin'])
        self.test = np.flatnonzero(self.df.recording_id == 'test')
        self.train = np.flatnonzero(self.df.recording_id != 'test')

    def test_validated_types_stay_in_inner_training(self):
        folds = make_seen_type_folds(self.df, self.train, self.test, 2)
        self.assertEqual(sorted(np.concatenate([v for _, v in folds]).tolist()),
                         sorted(np.flatnonzero(self.df.recording_id.isin(
                             ['inj1', 'inj2', 'sp1', 'sp2', 'sp3', 'free1', 'free2'])).tolist()))
        for train, valid in folds:
            self.assertEqual(sorted(np.concatenate((train, valid)).tolist()), self.train.tolist())
            self.assertFalse(set(self.df.iloc[train].recording_id) & set(self.df.iloc[valid].recording_id))
            self.assertEqual(set(self.df.iloc[valid].label_bin), {0, 1})
            attacks = lambda part: set(self.df.iloc[part].query('label_bin == 1').attack_type)
            self.assertLessEqual(attacks(valid), attacks(train))
            self.assertFalse({'dos', 'rep'} & set(self.df.iloc[valid].recording_id))

    def test_rejects_when_no_type_can_be_validated(self):
        single = self.df[~self.df.recording_id.isin(['inj2', 'sp2', 'sp3'])].reset_index(drop=True)
        train = np.flatnonzero(single.recording_id != 'test')
        test = np.flatnonzero(single.recording_id == 'test')
        with self.assertRaisesRegex(ValueError, 'no attack recording'):
            make_seen_type_folds(single, train, test, 2)


if __name__ == '__main__':
    unittest.main()
