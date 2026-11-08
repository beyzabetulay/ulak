import unittest

import numpy as np
from sklearn.tree import DecisionTreeClassifier

from experiments.kia_validation_ablation import VARIANTS, evaluate, validate_inner


class ValidationAblationTests(unittest.TestCase):
    def test_variants_add_only_the_named_timing_feature(self):
        base = VARIANTS['standard']
        self.assertEqual(VARIANTS['iat_id'], base + ['iat_id'])
        self.assertEqual(VARIANTS['iat_bus'], base + ['iat_bus'])
        self.assertEqual(VARIANTS['both'], base + ['iat_id', 'iat_bus'])

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
