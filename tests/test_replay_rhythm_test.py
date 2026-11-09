import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from experiments.replay_rhythm_test import VARIANTS, periods, read_raw, rhythm_features, time_blocks


def stream(times, ids=None, labels=None):
    n = len(times)
    frame = pd.DataFrame({'t': times, 'id': ids if ids is not None else [1] * n, 'dlc': 8,
                          'label': labels if labels is not None else [0] * n})
    for i in range(8):
        frame[f'b{i}'] = np.uint8(0)
    return frame.sort_values('t', kind='stable').reset_index(drop=True)


class RhythmFeatureTests(unittest.TestCase):
    def setUp(self):
        self.period = periods(stream(np.arange(0, 1, 0.01)))
        times = [0.0, 0.01, 0.02, 0.023, 0.03, 0.04]
        self.frame = stream(times, labels=[0, 0, 0, 1, 0, 0])
        self.features = rhythm_features(self.frame, self.period)

    def test_copy_breaks_the_rhythm_and_the_next_genuine_frame_keeps_it(self):
        copy, genuine = self.features.iloc[3], self.features.iloc[4]
        self.assertAlmostEqual(copy.phase2, 0.3, places=6)
        self.assertAlmostEqual(genuine.phase2, 0.0, places=6)
        self.assertLess(genuine.gap1, 1)  # one gap back cannot tell them apart
        self.assertTrue(genuine.after_attack)
        self.assertFalse(self.features.after_attack.iloc[[0, 1, 2, 3, 5]].any())

    def test_features_use_only_the_past(self):
        changed = self.frame.copy()
        changed.loc[5, ['t', 'b0']] = [0.041, 255]
        again = rhythm_features(changed, self.period)
        pd.testing.assert_frame_equal(self.features.iloc[:5], again.iloc[:5])

    def test_unknown_id_has_no_timing_features(self):
        features = rhythm_features(stream([0.0, 0.01, 0.02], ids=[7, 7, 7]), self.period)
        self.assertTrue(features[['gap1', 'gap2', 'count100']].isna().all().all())

    def test_variants_exclude_id_and_raw_payload(self):
        for columns in VARIANTS.values():
            self.assertFalse({'id', 'can_id', 't'} & set(columns))
            self.assertFalse([c for c in columns if c.startswith('b') and c[1:].isdigit()])


class InputTests(unittest.TestCase):
    def test_reads_attack_free_and_indexed_layouts(self):
        with tempfile.TemporaryDirectory() as directory:
            free, indexed = Path(directory) / 'free.csv', Path(directory) / 'indexed.csv'
            free.write_text('0.02,316,2,45 26\n0.01,18F,8,FE 50 00 00 00 49 00 00\n')
            indexed.write_text('1,0.01,0316,8,00 00 00 00 00 00 00 10,T\n')
            a, b = read_raw(free), read_raw(indexed)
        self.assertEqual(a.id.tolist(), [0x18F, 0x316])
        self.assertEqual(a.label.tolist(), [0, 0])
        self.assertEqual(a.loc[1, ['b0', 'b1', 'b2']].tolist(), [0x45, 0x26, 0])
        self.assertEqual((b.id.iloc[0], b.label.iloc[0], b.b7.iloc[0]), (0x316, 1, 0x10))

    def test_time_blocks_split_each_file_by_its_own_span(self):
        frame = pd.DataFrame({'file': ['a'] * 4 + ['b'] * 2, 't': [0, 1, 2, 3, 100, 200]})
        self.assertEqual(time_blocks(frame).tolist(), [0, 0, 1, 1, 0, 1])


if __name__ == '__main__':
    unittest.main()
