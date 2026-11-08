# Kia Spoofing: missed attacks and depth-6 false alarms

Real-data descriptive follow-up to `kia_known_attack.md`; no parameters,
thresholds or features were tuned. XGBoost depths 3/6 are retrained on the same
recording partitions and all reproduced confusion counts must match the earlier
run. Inputs remain ID, DLC and eight payload bytes, missing values -1. These
previously inspected recordings are not independent final holdouts. No raw
payload rows are committed. Input hashes and descriptive group statistics are
in the ignored `local_outputs/spoofing_diagnosis.json`.

Reproduce from the repository root with
`python experiments/kia_spoofing_diagnosis.py`, after running the known-attack
experiment. Dependencies and environment are the same as that experiment.

## Final-first recording: all 130 attack frames missed

The attack frames use two IDs, decimal 790 and 1087, with 65 frames each.
They comprise 55 distinct ID/DLC/byte signatures. Of the 130 attack rows:

- 63 exactly match at least one normal training signature.
- None exactly matches an attack training signature.
- 61 share the exact input signature of a normal frame in the evaluation
  recording itself. This count may overlap the 63 above and must not be added.

A deterministic classifier given only these inputs must give the same output
to identical signatures. It therefore cannot classify all normal and attack
frames in the latter overlapping subset correctly. This is input ambiguity,
not proof that the dataset labels are wrong. Temporal or sequential context
could help but was not examined here. It does not explain all 130 misses.

Attack score ranges are 0.0212–0.0436 at depth 3 and 0.00119–0.00853 at depth
6 (median 0.00183 at depth 6). Thus these are not just marginal scores below
the fixed 0.5 threshold. These model scores are not calibrated probabilities
of real-world attacks. Lowering the threshold has not been evaluated as a fix.

## Preliminary recording: depth-6 false alarms

Depth 3 flags no normal frames and catches 4,566/4,770 attacks. Depth 6 catches
4,751/4,770 but flags 5,324/108,230 normal frames. Its false alarms comprise
only 64 distinct ID/DLC/byte signatures:

| Normal-frame CAN ID (decimal) | Depth-6 false alarms |
|---|---:|
| 1087 | 5,210 |
| 24 | 114 |

All 5,210 normal frames of ID 1087 in this recording are flagged at depth 6,
whereas depth 3 classifies them correctly. None of the false-alarm signatures
matches a normal or attack training signature. Their depth-6 scores range from
0.614 to 0.882, so they are not all close to the threshold.

For ID 1087, `byte_4` is 120 in every evaluated normal frame; the same ID's
normal training values range from 70 to 116. Training also contains attacks
under this ID. This supports investigation of recording-specific payload shift
and overly specific learned rules, but does not demonstrate which feature
caused each prediction. No physical meaning is assigned to byte 4 without a
verified DBC. Individual byte ranges do not describe all joint input relations.

## Implication

The missed-attack and false-alarm problems differ: some attack inputs are
identical to normal content, while repeated unseen normal content is flagged
in another recording. Blindly increasing depth or chasing the reused test
threshold is not supported. Next candidates are sequence-aware features for
ambiguous inputs and regularization/recording-robust validation for false alarms.
Any claimed improvement needs evaluation chosen without these inspected rows.
