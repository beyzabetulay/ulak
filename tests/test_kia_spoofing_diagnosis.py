import unittest

import numpy as np
import pandas as pd

from experiments.kia_spoofing_diagnosis import FEATURES, signature_counts, summary


class SpoofingDiagnosisTests(unittest.TestCase):
    def test_exact_match_counts_preserve_duplicate_evaluation_rows(self):
        row = {feature: 0 for feature in FEATURES}
        row['can_id_dec'] = 42
        row['byte_7'] = np.nan
        normal = pd.DataFrame([row, row])
        attack = normal.iloc[:0]
        part = normal.assign(probability=[.1, .2])
        result = summary(part, signature_counts(normal), signature_counts(attack))
        self.assertEqual(result['rows'], 2)
        self.assertEqual(result['unique_signatures'], 1)
        self.assertEqual(result['exact_normal_training_matches'], 2)
        self.assertEqual(result['exact_attack_training_matches'], 0)


if __name__ == '__main__':
    unittest.main()
