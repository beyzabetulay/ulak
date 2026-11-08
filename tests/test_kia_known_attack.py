import unittest

import pandas as pd

from experiments.kia_known_attack import DEFAULT_MODELS, make_model, known_recording_folds


class KnownAttackTests(unittest.TestCase):
    def test_only_repeated_attack_recordings_are_evaluated(self):
        df = pd.DataFrame({
            'recording_id': ['a', 'a', 'b', 'b', 'c', 'd', 'e'],
            'attack_type': ['Injection'] * 4 + ['Replay', 'Replay', 'Normal'],
            'label_bin': [0, 1, 0, 1, 1, 1, 0],
            'split': ['train'] * 5 + ['test', 'train'],
        })
        folds = known_recording_folds(df)
        self.assertEqual([f[1] for f in folds], ['a', 'b'])
        for attack, recording, train, test in folds:
            self.assertEqual(set(df.iloc[test].recording_id), {recording})
            self.assertFalse(set(df.iloc[train].recording_id) & set(df.iloc[test].recording_id))
            self.assertTrue(df.iloc[train]['split'].eq('train').all())
            self.assertTrue(df.iloc[train].attack_type.eq(attack).any())
            self.assertNotIn(5, train)
            self.assertNotIn(5, test)

    def test_catboost_matches_validation_settings(self):
        params = make_model('catboost_depth3').get_params()
        self.assertEqual((params['depth'], params['iterations'], params['boosting_type']), (3, 100, 'Plain'))
        self.assertNotIn('catboost_depth3', DEFAULT_MODELS)


if __name__ == '__main__':
    unittest.main()
