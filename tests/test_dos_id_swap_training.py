import unittest

import numpy as np
import pandas as pd

from experiments.dos_id_swap_training import add_swapped_dos


def stream(ids, labels):
    frame = pd.DataFrame({'t': np.arange(len(ids)) * 0.01, 'id': ids, 'dlc': 8, 'label': labels})
    for i in range(8):
        frame[f'b{i}'] = np.uint8(0)
    return frame


class AugmentationTests(unittest.TestCase):
    def test_swapped_copy_has_no_id0_attacks_and_keeps_normals(self):
        raw = {'x/Attack_free_KIA.csv': stream([5, 5, 7], [0, 0, 0]),
               'x/Flooding_KIA.csv': stream([0, 9, 0, 9], [1, 0, 1, 0])}
        augmented, common_id = add_swapped_dos(raw)
        self.assertEqual(common_id, 5)
        copy = augmented['x/Flooding_KIA.csv:id_swapped_to_5']
        self.assertFalse(((copy.label == 1) & (copy.id == 0)).any())
        self.assertEqual(copy.id.tolist(), [5, 9, 5, 9])
        self.assertEqual(raw['x/Flooding_KIA.csv'].id.tolist(), [0, 9, 0, 9])
        self.assertEqual(len(augmented), 3)


if __name__ == '__main__':
    unittest.main()
