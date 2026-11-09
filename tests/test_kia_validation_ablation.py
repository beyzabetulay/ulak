import unittest

import numpy as np
from sklearn.tree import DecisionTreeClassifier

from experiments.kia_validation_ablation import VARIANTS, add_sequence_columns, evaluate, validate_inner
import pandas as pd


class ValidationAblationTests(unittest.TestCase):
    def test_variants_add_only_the_named_timing_feature(self):
        base = VARIANTS['standard']
        self.assertEqual(VARIANTS['iat_id'], base + ['iat_id'])
        self.assertEqual(VARIANTS['iat_bus'], base + ['iat_bus'])
        self.assertEqual(VARIANTS['both'], base + ['iat_id', 'iat_bus'])
        self.assertEqual(VARIANTS['sequence'], VARIANTS['iat_id'] + ['changed_bits', 'repeat_previous'])

    def test_sequence_features_keep_positions_and_ignore_labels(self):
        df = pd.DataFrame({'recording_id': ['a', 'a', 'a'], 'can_id_dec': [1, 1, 1],
                           'timestamp': [3., 1., 2.], 'dlc': [8] * 3, 'label_bin': [1, 0, 1],
                           **{f'byte_{i}': [3, 0, 0] if i == 0 else [0, 0, 0] for i in range(8)}})
        result = add_sequence_columns(df)
        self.assertEqual(result.index.tolist(), df.index.tolist())
        self.assertEqual(result.loc[0, 'changed_bits'], 2.)
        self.assertTrue(pd.isna(result.loc[1, 'changed_bits']))
        self.assertEqual(result.loc[2, 'repeat_previous'], 1.)
        altered = add_sequence_columns(df.assign(label_bin=1-df.label_bin))
        pd.testing.assert_frame_equal(result[['changed_bits', 'repeat_previous']],
                                      altered[['changed_bits', 'repeat_previous']])

    def test_rejects_row_or_recording_overlap_and_missing_class(self):
        groups = np.array(['a', 'a', 'b', 'b', 'c', 'c'])
        labels = np.array([0, 1, 0, 1, 0, 1])
        outer = np.arange(6)
        validate_inner(outer, np.array([0, 1, 2, 3]), np.array([4, 5]), groups, labels)
        with self.assertRaises(ValueError):
            validate_inner(outer, np.array([0, 1, 2, 3]), np.array([3, 5]), groups, labels)
        with self.assertRaises(ValueError):
            validate_inner(outer, np.array([0, 2, 3, 4]), np.array([1, 5]), groups, labels)
        with self.assertRaises(ValueError):
            validate_inner(outer, np.array([0, 2, 4]), np.array([1, 3, 5]), np.arange(6), labels)

    def test_thresholds_share_a_single_fitted_model(self):
        X = np.array([[0], [0], [1], [1], [0], [1]], dtype=np.float32)
        y = np.array([0, 0, 1, 1, 0, 1])
        result, _ = evaluate(X, y, np.array([0, 1, 2, 3]), np.array([4, 5]),
                             DecisionTreeClassifier(max_depth=1, random_state=42), [0.3, 0.7])
        self.assertEqual(set(result), {'0.3', '0.7'})
        for metric in result.values():
            self.assertEqual(sum(metric[k] for k in ('tn', 'fp', 'fn', 'tp')), 2)


if __name__ == '__main__':
    unittest.main()
