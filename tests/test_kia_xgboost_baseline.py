import tempfile
import unittest
from pathlib import Path

import numpy as np

from experiments.kia_xgboost_baseline import load_indices, run_model, scores


class XGBoostBaselineTests(unittest.TestCase):
    def test_metrics_distinguish_missed_attacks_and_false_alarms(self):
        result = scores(np.array([0, 0, 1, 1]), np.array([0, 1, 0, 1]))
        self.assertEqual((result['tn'], result['fp'], result['fn'], result['tp']), (1, 1, 1, 1))
        self.assertEqual(result['attack_f1'], 0.5)
        self.assertEqual(result['false_positive_rate'], 0.5)

    def test_rejects_duplicate_and_out_of_range_indices(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'indices.npy'
            for array in (np.array([0, 0]), np.array([0, 3])):
                np.save(path, array)
                with self.assertRaises(ValueError):
                    load_indices(path, 3)

    def test_training_on_synthetic_data(self):
        X = np.array([[0], [0], [1], [1], [0], [1]], dtype=np.float32)
        y = np.array([0, 0, 1, 1, 0, 1], dtype=np.int8)
        metric, training, seconds = run_model(X, y, np.array([0, 1, 2, 3]), np.array([4, 5]),
                                              {'max_depth': 3, 'n_estimators': 2}, training_metrics=True)
        self.assertEqual(sum(metric[k] for k in ('tn', 'fp', 'fn', 'tp')), 2)
        self.assertEqual(sum(training[k] for k in ('tn', 'fp', 'fn', 'tp')), 4)
        self.assertGreaterEqual(seconds, 0)


if __name__ == '__main__':
    unittest.main()
