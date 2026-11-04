# Kia Soul: why held-out DoS and Replay are missed

Input: `kia_soul_features_all.parquet` with the Kia Soul leave-one-attack-out splits (`unseen_dos`, `unseen_replay`); the Parquet SHA-256 is checked against the split manifest.
Environment: numpy 2.5.4, pandas 3.1.0, scikit-learn 1.9.1.
Reproduce with `python experiments/kia_unseen_diagnosis.py` (read-only, prints to the console).

## Observation to explain

The decision-tree notebook (`experiments/kia_decision_tree/01_first_decision_tree.ipynb`) trains `DecisionTreeClassifier(max_depth=6, random_state=42)` on `can_id_dec`, `dlc` and `byte_0..7`, with missing bytes set to -1. On the held-out attack it detects none of the DoS attacks (0 of 16,072) and none of the Replay attacks (0 of 155,640). The baseline in `shortcut_baseline.py` additionally sets `min_samples_leaf=20`; the notebook keeps the default.

## DoS (`unseen_dos`, test recording: Flooding)

| Measurement | Value |
|---|---:|
| Training rows with `can_id_dec` = 0 | 14 (all labelled attack, all from one Fuzzy recording) |
| Training rows with all eight bytes 0, normal | 121,452 |
| Training rows with all eight bytes 0, attack | 9,013 |
| Distinct IDs among the all-zero training rows | 9 |
| Test attack rows / distinct IDs | 16,072 / only ID 0 |
| Test normal rows with `can_id_dec` = 0 | 0 |

An all-zero payload is common in normal traffic, so the payload alone does not mark a DoS frame. The ID does: in the test recording, ID 0 separates attack from normal without exception, and in training every ID 0 row is an attack. Training contains only 14 such rows out of 2,616,954.

## Replay (`unseen_replay`, test recording: Replay)

Share of test rows whose ID, DLC and eight bytes are identical to at least one normal training row:

| Test rows | Share |
|---|---:|
| Attack | 0.801 |
| Normal | 0.816 |

Replay frames are indistinguishable from normal frames by content: both shares are almost equal.

## Reading and limits

- The DoS result is consistent with the miss (a rule that holds in training but rests on 14 rows). The tree structure was not inspected, so this is not shown to be the cause.
- The Replay result is consistent with `FINDINGS.md` section 3: content and ID do not separate the attack, so timing features are the candidate signal. They are not evaluated here.
- Exact matching compares against normal training rows only and uses one fold per attack type.
