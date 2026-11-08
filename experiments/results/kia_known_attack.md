# Kia known-attack transfer across recordings

Real-data exploratory experiment on the local HCRL Kia feature parquet. Unlike
leave-one-attack-out, each evaluation recording has another recording of the
same attack type available in training. All remaining HCRL training recordings
are used to fit; the selected recording is entirely excluded. Release files
are never used. This yields two Injection and three Spoofing evaluations.
DoS and Replay each have only one attack recording and cannot support this
protocol. Recording separation does not establish independent acquisition
sessions; these recordings have been inspected in earlier experiments.

Reproduce: `python experiments/kia_known_attack.py` after installing the existing
experiment requirements and generating the Kia feature parquet/manifest.
The runner checks its input hash and feature contract. Ignored local output
`experiments/kia_decision_tree/local_outputs/known_attack.json` records model
parameters, versions, per-recording training/evaluation metrics, recording
membership, and hashes of absolute train/test row-position arrays.

All three models are predefined and reported without selecting a winner on the
evaluation data: decision tree depth 6 and XGBoost depths 3/6, both 100 trees,
learning rate 0.1, histogram training, four threads. Seed 42 and threshold 0.5
are fixed. No timing, class weighting or tuning is used. Inputs are CAN ID,
DLC and eight payload bytes, with missing bytes replaced by -1. Environment:
Python 3.14.5, NumPy 2.4.6, pandas 2.3.3, scikit-learn 1.9.0, XGBoost 3.4.1.

Recording abbreviations below refer to the training-folder raw file identities:
Injection final = final-first Fuzzy_dataset; Injection preliminary = preliminary
Fuzzy; Spoofing final-first = Malfunction_1st_dataset; final-second =
Malfunction_2nd; preliminary = preliminary Malfunction. All are Kia Soul.

| Evaluation recording | Attack frames | Model | Attack precision | Recall | F1 | Normal FPR |
|---|---:|---|---:|---:|---:|---:|
| Injection final | 119,551 | Tree 6 | 0.995 | 0.570 | 0.724 | 0.00110 |
| Injection final | 119,551 | XGBoost 3 | 0.957 | 0.862 | 0.907 | 0.01359 |
| Injection final | 119,551 | XGBoost 6 | 0.948 | 0.988 | 0.968 | 0.01889 |
| Injection preliminary | 21,613 | Tree 6 | 0.669 | 0.818 | 0.736 | 0.07154 |
| Injection preliminary | 21,613 | XGBoost 3 | 0.998 | 0.952 | 0.974 | 0.00038 |
| Injection preliminary | 21,613 | XGBoost 6 | 0.999 | 0.994 | 0.997 | 0.00011 |
| Spoofing final-first | 130 | Tree 6 | undefined | 0.000 | 0.000 | 0.00000 |
| Spoofing final-first | 130 | XGBoost 3 | undefined | 0.000 | 0.000 | 0.00000 |
| Spoofing final-first | 130 | XGBoost 6 | undefined | 0.000 | 0.000 | 0.00000 |
| Spoofing final-second | 67,080 | Tree 6 | 0.000 | 0.000 | 0.000 | 0.000009 |
| Spoofing final-second | 67,080 | XGBoost 3 | 0.999 | 0.500 | 0.666 | 0.000108 |
| Spoofing final-second | 67,080 | XGBoost 6 | 0.999 | 0.500 | 0.666 | 0.000123 |
| Spoofing preliminary | 4,770 | Tree 6 | 0.418 | 0.785 | 0.546 | 0.04814 |
| Spoofing preliminary | 4,770 | XGBoost 3 | 1.000 | 0.957 | 0.978 | 0.00000 |
| Spoofing preliminary | 4,770 | XGBoost 6 | 0.472 | 0.996 | 0.640 | 0.04919 |

XGBoost learns useful content-based relationships for Injection across these
two recordings; a blanket claim that boosting fails on this dataset is not
supported. On final Injection, higher recall comes with more false alarms than
the tree. Spoofing results vary strongly: neither model detects the 130 attacks
in one recording, and raising XGBoost depth from 3 to 6 greatly increases false
alarms on preliminary Spoofing. The broad attack name does not guarantee that
behavior transfers across recordings. The cause requires further diagnosis.

The earlier unseen-attack protocol differs in training population and size;
these results are not a controlled causal estimate of attack exposure alone.
They do distinguish useful known-type transfer from failure to detect wholly
held-out types. No single model or depth should be declared universally best
from five correlated, previously inspected recordings. Keep separate reports
for known-type transfer and unseen-type generalization.
