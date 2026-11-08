import unittest

import pandas as pd

from experiments.kia_spoofing_sequence import BYTES, past_features


class SpoofingSequenceTests(unittest.TestCase):
    def test_previous_same_id_and_recording_only(self):
        df = pd.DataFrame({'recording_id': ['a', 'a', 'a', 'b'],
                           'can_id_dec': [1, 2, 1, 1], 'timestamp': [1., 2., 3., 4.], 'dlc': [8] * 4,
                           **{name: [0, 0, 0, 0] for name in BYTES}})
        df.loc[2, 'byte_0'] = 3
        result = past_features(df)
        self.assertEqual(result.loc[2, 'gap_id'], 2.)
        self.assertEqual(result.loc[2, 'gap_bus'], 1.)
        self.assertEqual(result.loc[2, 'changed_bits'], 2.)
        self.assertTrue(pd.isna(result.loc[3, 'gap_id']))
        self.assertTrue(pd.isna(result.loc[3, 'changed_bits']))
        pd.testing.assert_frame_equal(past_features(df.iloc[:2]), result.iloc[:2])

    def test_repetition_and_length_change(self):
        df = pd.DataFrame({'recording_id': ['a'] * 3, 'can_id_dec': [1] * 3,
                           'timestamp': [1., 2., 3.], 'dlc': [8, 8, 7],
                           **{name: [0, 0, 0] for name in BYTES}})
        result = past_features(df)
        self.assertEqual(result.loc[1, 'repeat_previous'], 1.)
        self.assertTrue(pd.isna(result.loc[2, 'changed_bits']))


if __name__ == '__main__':
    unittest.main()
