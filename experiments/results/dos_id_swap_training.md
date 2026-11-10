# DoS without the ID 0 cue: ID-swapped training copy

Real-data follow-up to the [cross-vehicle shortcut test](shortcut_transfer_test.md).
In that test every model detected DoS through ID 0 only: after the flood
frames of the Spark and Sonata DoS recordings were given a normal ID, recall
fell to 0.000 (A), 0.035 (C) and 0.138 (T). No Kia training recording contains
a flood on a normal ID.

## Change

One addition to the training data, nothing else: a copy of the Kia DoS
recording (`Flooding_KIA_Soul_train.csv`) in which the ID 0 attack frames get
Kia's most frequent clean-drive ID (`153`); features are recomputed for the
copy. The four variants (A ID+bytes, B no ID, C A+`iat_id`, T ID-free rhythm)
are refit with the depth and threshold frozen in the cross-vehicle selection;
no new selection or tuning.

The test sets are the same Spark and Sonata recordings, so this is a **second
look** at them, not a clean test. The ID swap is the same synthetic change in
training and test; this measures that change, not a real attack on a normal ID.

## Results (frozen threshold; before → after)

| Variant | Spark DoS, ID swapped: recall | Sonata DoS, ID swapped: recall | Spark DoS, original: F1 | Spark clean-drive FPR | Sonata clean-drive FPR |
|---|---|---|---|---|---|
| A | 0.000 → 0.000 | 0.000 → 0.000 | 0.660 → 0.627 | 20.2 % → 25.2 % | 14.5 % → 18.1 % |
| B | 0.000 → 0.000 | 0.000 → 0.000 | 0 → 0 | 15.1 % → 15.2 % | 8.6 % → 8.5 % |
| C | 0.035 → 0.111 | 0.020 → 0.020 | 0.726 → 0.743 | 9.7 % → 8.4 % | 9.2 % → 9.5 % |
| T | **0.138 → 1.000** | **0.126 → 1.000** | 0.989 → 0.990 | 0.34 % → 0.31 % | 1.36 % → 1.31 % |

T on the swapped DoS recordings: F1 0.225 → 0.961 (Spark), 0.200 → 0.937
(Sonata). Other T results stay level; Spark Malfunction rises from 0.824 to
0.942 (recall 0.787 → 1.000).

## Findings

- **For the rhythm model, one swapped training copy removes the ID 0
  shortcut.** It now detects the flood by its timing on both vehicles, without
  more false alarms on clean drives.
- **The content models do not benefit.** A, B and C see the flood frame as an
  all-zero payload on a normal ID; nothing in their inputs describes the flood
  rate, so they cannot learn it. A's clean-drive false alarms rise (Spark
  20.2 % → 25.2 %).

## Limits

Second look at already used test recordings; synthetic swap in both training
and test; one Kia DoS recording; one swap ID per vehicle.

## Reproduction

After the cross-vehicle selection exists (`shortcut_transfer_test.py select`):

```sh
python experiments/dos_id_swap_training.py
```

Output: ignored `experiments/kia_decision_tree/local_outputs/dos_id_swap_training.json`.
