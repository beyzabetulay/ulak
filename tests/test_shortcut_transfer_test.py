import unittest

import numpy as np
import pandas as pd

from experiments.shortcut_transfer_test import (BYTES, VARIANTS, VEHICLES, attack_type, features, half,
                                                periods_of, swap_dos_id)


def stream(times, ids, labels=None, dlc=8):
    n = len(times)
    frame = pd.DataFrame({'t': times, 'id': ids, 'dlc': dlc, 'label': labels if labels is not None else [0] * n})
    for i in range(8):
        frame[f'b{i}'] = np.uint8(7)
    return frame


class FeatureTests(unittest.TestCase):
    def test_bytes_after_dlc_are_minus_one(self):
        frame = stream([0.0, 0.01], [5, 5], dlc=3)
        out = features(frame, periods_of([frame]), 'f')
        self.assertEqual(out.loc[0, BYTES].tolist(), [7, 7, 7, -1, -1, -1, -1, -1])

    def test_periods_ignore_gaps_across_recordings(self):
        a, b = stream([0.0, 0.01, 0.02], [5] * 3), stream([100.0, 100.01], [5] * 2)
        self.assertAlmostEqual(periods_of([a, b])[5], 0.01)

    def test_rhythm_variant_has_no_id_or_payload(self):
        self.assertFalse({'can_id_dec', 'id'} & set(VARIANTS['T_rhythm_no_id']))
        self.assertFalse(set(BYTES) & set(VARIANTS['T_rhythm_no_id']))
        self.assertNotIn('can_id_dec', VARIANTS['B_no_id'])


class SwapTests(unittest.TestCase):
    def test_swap_changes_only_id0_attack_frames_and_features_follow(self):
        frame = stream([0.0, 0.001, 0.002, 0.01, 0.02], [0, 0, 9, 9, 0], labels=[1, 1, 0, 0, 0])
        swapped = swap_dos_id(frame, 9)
        self.assertEqual(swapped.id.tolist(), [9, 9, 9, 9, 0])
        self.assertEqual(frame.id.tolist(), [0, 0, 9, 9, 0])
        period = pd.Series({9: 0.01})
        before, after = features(frame, period, 'f'), features(swapped, period, 'f')
        self.assertTrue(np.isnan(before.loc[1, 'gap1']))
        self.assertAlmostEqual(after.loc[1, 'gap1'], 0.1)


class SplitTests(unittest.TestCase):
    def test_spark_clean_drive_halves_do_not_overlap(self):
        frame = stream(np.arange(0, 10, 0.5), [1] * 20)
        first, second = half(frame, 'first'), half(frame, 'second')
        self.assertFalse(set(first.index) & set(second.index))
        self.assertEqual(len(first) + len(second), len(frame))
        self.assertLess(first.t.max(), second.t.min())
        spark = VEHICLES['spark']
        self.assertEqual(spark['calibration'], spark['clean'])
        self.assertEqual((spark['calibration_half'], spark['clean_half']), ('first', 'second'))

    def test_attack_type_from_file_name(self):
        self.assertEqual([attack_type(p) for p in VEHICLES['spark']['attacks']], ['DoS', 'Injection', 'Spoofing'])
        with self.assertRaises(ValueError):
            attack_type('File_1.csv')


if __name__ == '__main__':
    unittest.main()
