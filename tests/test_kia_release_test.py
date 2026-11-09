import tempfile
import unittest
from pathlib import Path

import numpy as np

from experiments.kia_release_test import (build_variants, check_release_guard, choose_depth, metrics,
                                          oof_threshold, per_file, subsample_normals)
from experiments.kia_xgboost_baseline import digest


class ReleaseGuardTests(unittest.TestCase):
    def test_refuses_missing_selection_wrong_hash_and_repeated_attempts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            selection, output, attempt = root / 'selection.json', root / 'out.json', root / 'out_attempt.json'
            with self.assertRaisesRegex(ValueError, 'not found'):
                check_release_guard(selection, 'x', output, attempt)
            selection.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'hash'):
                check_release_guard(selection, '0' * 64, output, attempt)
            check_release_guard(selection, digest(selection), output, attempt)
            for path in (attempt, output):
                path.write_text('{}')
                with self.assertRaisesRegex(ValueError, 'already attempted'):
                    check_release_guard(selection, digest(selection), output, attempt)
                path.unlink()


class MetricTests(unittest.TestCase):
    def test_per_file_counts_sum_to_pooled_and_attack_free_file_has_no_attack_scores(self):
        y = np.array([0, 1, 1, 0, 0, 0])
        proba = np.array([.9, .8, .2, .1, .7, .3])
        recordings = np.array(['a', 'a', 'a', 'a', 'b', 'b'])
        timestamps = np.array([0., 1., 2., 4., 0., 2.])
        files = per_file(y, proba, recordings, timestamps, {'0.5': 0.5})
        pooled = metrics(y, proba, 0.5)
        for key in ('tp', 'fp', 'fn', 'tn'):
            self.assertEqual(sum(f['thresholds']['0.5'][key] for f in files.values()), pooled[key])
        self.assertIsNone(files['b']['thresholds']['0.5']['attack_f1'])
        self.assertIsNone(files['b']['thresholds']['0.5']['auprc'])
        self.assertEqual(files['b']['thresholds']['0.5']['false_alarms_per_s'], 0.5)
        self.assertEqual(files['a']['thresholds']['0.5']['false_alarms_per_s'], 0.25)

    def test_auprc_separates_rankings_with_equal_f1(self):
        y = np.array([0, 0, 1, 1])
        good, poor = np.array([.1, .2, .3, .9]), np.array([.3, .1, .2, .9])
        self.assertEqual(metrics(y, good, .5)['attack_f1'], metrics(y, poor, .5)['attack_f1'])
        self.assertEqual(metrics(y, good, .5)['auprc'], 1.0)
        self.assertLess(metrics(y, poor, .5)['auprc'], 1.0)

    def test_oof_threshold_maximises_f1(self):
        y = np.array([0, 0, 1, 1])
        self.assertEqual(oof_threshold(y, np.array([.1, .2, .3, .9])), .3)

    def test_shallower_depth_wins_ties(self):
        configs = [{'parameters': {'max_depth': 6}, 'mean_auprc': .5},
                   {'parameters': {'max_depth': 3}, 'mean_auprc': .5}]
        self.assertEqual(choose_depth(configs)['parameters']['max_depth'], 3)


class SamplingTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(0)
        n = 6000
        self.recordings = np.array(['big'] * 5000 + ['small'] * 500 + ['replay'] * 500)
        self.ids = rng.integers(0, 2, n)
        self.labels = np.zeros(n, dtype=np.int8)
        self.labels[[0, 1, 5000, 5500]] = 1
        self.positions = np.arange(n)

    def sample(self, seed):
        return subsample_normals(self.positions, self.labels, self.recordings, self.ids, {'replay'}, seed,
                                 ratio=.2, minimum=100)

    def test_keeps_attacks_replay_normals_and_every_group(self):
        kept = self.sample(1)
        self.assertTrue(set(np.flatnonzero(self.labels == 1)) <= set(kept))
        self.assertTrue(set(np.flatnonzero(self.recordings == 'replay')) <= set(kept))
        self.assertTrue(set(kept) <= set(self.positions))
        for rec in ('big', 'small'):
            for identifier in (0, 1):
                group = (self.recordings == rec) & (self.ids == identifier) & (self.labels == 0)
                kept_in_group = np.isin(np.flatnonzero(group), kept).sum()
                self.assertEqual(kept_in_group, max(100, round(.2 * group.sum())) if group.sum() > 100 else group.sum())

    def test_seed_controls_sample(self):
        np.testing.assert_array_equal(self.sample(1), self.sample(1))
        self.assertFalse(np.array_equal(self.sample(1), self.sample(2)))


class VariantTests(unittest.TestCase):
    def test_masked_variants_exclude_the_id(self):
        standard = ['can_id_dec', 'dlc'] + [f'byte_{i}' for i in range(8)]
        manifest = {'variants': {'standard': standard, 'id_masked': standard[1:],
                                 'full': standard + ['iat_id', 'iat_bus', 'bus_count_100ms']}}
        variants = build_variants(manifest)
        self.assertNotIn('can_id_dec', variants['B_id_masked'])
        self.assertNotIn('can_id_dec', variants['D_id_masked_iat_id'])
        self.assertEqual(variants['C_standard_iat_id'], standard + ['iat_id'])


if __name__ == '__main__':
    unittest.main()
