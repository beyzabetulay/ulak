# Shortcut test across vehicles (Kia → Spark, Sonata)

Real-data result on the raw HCRL 2019 CSV files. Four XGBoost variants were
trained on the nine Kia Soul training recordings, with settings chosen on Kia
inner folds only. They were evaluated **once** on Chevrolet Spark (main test)
and Hyundai Sonata (second test). The hypotheses below were written into the
selection file before any test file was read.

## Why

Earlier experiments showed partial shortcut evidence: DoS is detected through
CAN ID 0, `bus_count_100ms` describes the recording, the ID can be recovered
from the payload, and release-test scores come from the same capture sessions.
A shortcut only shows when it stops working. On clean drives Spark shares 3 of
its 83 normal CAN IDs with Kia (45 IDs), Sonata 22 of its 27. Memorised Kia IDs
and payloads cannot carry over to Spark, and only partly to Sonata.

## Setup

| Variant | Features |
|---|---|
| A | CAN ID, DLC, `byte_0..7` (-1 after the DLC) |
| B | A without the ID |
| C | A + `iat_id` (seconds since the same ID's previous frame) |
| T | ID-free rhythm features of the [Replay rhythm test](replay_rhythm_test.md): `gap1..3`, `phase2..3`, `count100` (scaled by the ID's period on a clean drive of the same vehicle), `bits1..2`, DLC. IDs absent from that clean drive get no timing values. |

- **Training:** the 9 Kia training recordings. Kia periods for T come from the
  two Kia attack-free recordings; in selection, each fold uses only the
  attack-free recording of its inner training.
- **Selection:** the two seen-type inner folds
  (`splits/generated/kia_soul/validation_seen/`). Depth 3 or 6 by mean fold
  AUPRC (depth 6 for every variant); frozen out-of-fold F1 threshold
  (A 0.823, B 0.967, C 0.815, T 0.028). Selection file sha256
  `c1bdb693a5508777a3ce633bebf0e6f186930a0fd815cdc7915516a3561d610d`. A, B and
  C reproduce the release-test selection exactly (same AUPRC and thresholds),
  so the raw-CSV pipeline matches the parquet pipeline.
- **Spark:** preliminary `Flooding` (DoS), `Fuzzy` (Injection), `Malfunction`
  (Spoofing). The attack-free recording is split in time: the first half sets
  T's periods, the second half measures clean-drive false alarms.
- **Sonata:** preliminary `Flooding`, `Fuzzy`, `Malfunction`; final_1st
  `Fuzzy_dataset`, `Malfunction_1st_dataset`; final_2nd `Malfunction_2nd`.
  Periods from final_1st `Attack_free`; clean-drive false alarms on
  preliminary `Attack_free`.
- **DoS ID swap (synthetic change of real data):** in each `Flooding`
  recording, ID 0 attack frames get the vehicle's most frequent clean-drive ID
  (Spark `1E5`, Sonata `316`); features are recomputed.

Release files were not used (they continue training sessions). The Spark and
Sonata attack recordings were not inspected with labels before the run; the
Spark recordings were part of the team's earlier pooled decision-tree baseline
(`shortcut_baseline.md`), so they are new to this design but not to the
project.

## Kia validation (cross-recording, F1 at the frozen threshold)

| Variant | Injection | Spoofing |
|---|---:|---:|
| A | 0.888 | 0.691 |
| B | 0.922 | 0.106 |
| C | 0.850 | 0.683 |
| T | 0.827 | 0.880 |

## Test results (evaluated once, frozen threshold)

Clean drives (no attacks): share of normal frames flagged and false alarms per
second.

| Variant | Spark clean FPR | Spark false alarms/s | Sonata clean FPR | Sonata false alarms/s |
|---|---:|---:|---:|---:|
| A | 20.2 % | 464.3 | 14.5 % | 282.4 |
| B | 15.1 % | 347.2 | 8.6 % | 167.7 |
| C | 9.7 % | 222.4 | 9.2 % | 180.2 |
| T | **0.34 %** | **7.7** | **1.4 %** | **26.6** |

Attack recordings, F1 (recall in brackets):

| Recording (attacks) | A | B | C | T |
|---|---|---|---|---|
| Spark Flooding (14,999) | 0.660 (1.000) | 0.000 (0.000) | 0.726 (1.000) | **0.989** (1.000) |
| Spark Flooding, ID swapped (synthetic) | 0.000 (0.000) | 0.000 (0.000) | 0.039 (0.035) | 0.225 (0.138) |
| Spark Fuzzy (3,043) | 0.417 (0.980) | 0.468 (0.951) | 0.498 (0.987) | **0.980** (1.000) |
| Spark Malfunction (3,995) | 0.585 (1.000) | 0.670 (1.000) | 0.629 (1.000) | **0.824** (0.787) |
| Sonata Flooding (17,093) | 0.751 (1.000) | 0.000 (0.000) | 0.811 (1.000) | **0.962** (1.000) |
| Sonata Flooding, ID swapped (synthetic) | 0.000 (0.000) | 0.000 (0.000) | 0.026 (0.020) | 0.200 (0.126) |
| Sonata Fuzzy prelim (9,095) | 0.545 (0.980) | 0.691 (0.948) | 0.677 (0.990) | **0.933** (0.999) |
| Sonata Fuzzy final_1st (84,644) | 0.708 (0.985) | **0.806** (0.955) | 0.778 (0.979) | 0.766 (1.000) |
| Sonata Malfunction prelim (8,202) | 0.535 (1.000) | 0.702 (1.000) | 0.651 (1.000) | **0.845** (1.000) |
| Sonata Malfunction_1st (144) | 0.002 (0.472) | 0.002 (0.236) | 0.004 (0.444) | 0.085 (0.833) |
| Sonata Malfunction_2nd (71,194) | 0.644 (1.000) | 0.812 (1.000) | 0.757 (1.000) | **0.886** (1.000) |

On Spark Fuzzy, precision is 0.265 (A), 0.310 (B), 0.333 (C) and 0.960 (T).

## Hypotheses (as pre-registered)

| | Statement | Outcome |
|---|---|---|
| H1 | A and C fall below half of their Kia validation F1 on Spark Fuzzy and Malfunction | **Not met.** A Fuzzy 0.417 vs 0.888 (-53 %), but A Malfunction 0.585 vs 0.691 (-15 %), C -41 % / -8 % |
| H2 | B drops less than A on both Spark files | **Met** (Fuzzy -49 % vs -53 %, a small margin; Malfunction B rises from 0.106) |
| H3 | T scores higher F1 than A on both Spark files | **Met** (0.980 vs 0.417; 0.824 vs 0.585) |
| H4 | A and C catch Flooding (recall >= 0.9) and fail after the ID swap (< 0.5); T keeps half of its recall | **Not met.** A and C behave as predicted (recall 1.0 → 0.0-0.035), but T also falls from 1.0 to 0.13-0.14 |

## Findings

- **The ID/payload shortcut shows as false alarms, not as missed attacks.**
  On another vehicle, A, B and C flag 9-20 % of a clean drive (222-464 false
  alarms per second): content they never saw in Kia's normal traffic is called
  an attack. Their recall stays high, which is why H1, defined on F1 drop,
  missed the effect. T, which sees no ID or payload, flags 0.34 % of the clean
  Spark drive.
- **DoS detection is an ID 0 rule in every content model.** Changing the ID
  of the flood frames drops A and C from recall 1.0 to 0.0-0.035 on both
  vehicles. B (no ID) never detects DoS.
- **The ID-free model most likely also relied on an ID cue for DoS.** ID 0
  is absent from every clean drive, so flood frames get no timing values, the
  same "unknown ID" pattern as every Kia DoS frame in training. The swap
  result fits this explanation; it was not tested directly. Once the flood uses a known ID, T catches only 13-14 %
  despite the very short gaps. No training recording teaches a flood on a
  known ID.
- **Rhythm transfers across vehicles for Injection and Spoofing.** T reaches
  F1 0.98 (Fuzzy) and 0.82 (Malfunction) on Spark and 0.77-0.93 / 0.85-0.89
  on Sonata. On Sonata final_1st Fuzzy, T has 320.9 false alarms per second
  and B scores higher (0.806 vs 0.766).
- **Sonata Malfunction_1st** has 144 attack frames among 285,450; every
  variant scores F1 below 0.1 there. Too small to interpret, like Kia's
  130-attack Spoofing recording.

## Limitations

- Spark has one recording per attack type (preliminary round only); the Spark
  clean-drive periods and false alarms come from two halves of one drive.
- The HCRL attacks share tools and injection patterns across vehicles; this
  measures transfer to another vehicle, not to another attacker.
- The ID swap is a synthetic change of real recordings; the genuine frames of
  the chosen ID now share their ID with the flood, which also raises T's false
  alarms (Spark 43.8/s after the swap vs 11.0/s before).
- T's frozen threshold is very low (0.028); its probabilities are poorly
  calibrated even though the ranking transfers.
- Frame-level labels; one deterministic seed; no confidence intervals.

## Reproduction

Prerequisites: raw `car_track_*` folders in the repository root (README
Dataset section), `pip install -r experiments/requirements.txt`, and the Kia
pipeline up to the seen-type folds (`prepare_kia_soul.py`, `build_features.py
--input kia_soul_dataset.csv --prefix kia_soul_features`,
`splits/make_kia_splits.py`, `splits/make_kia_validation.py --seen-types --fold official`).

```sh
python experiments/shortcut_transfer_test.py select
python experiments/shortcut_transfer_test.py test --selection-sha256 <printed sha256>
```

Pass the sha256 your own `select` prints. Outputs in the ignored
`experiments/kia_decision_tree/local_outputs/`: `shortcut_selection.json`,
`shortcut_transfer_test.json` and its attempt file. For a deliberate rerun,
delete `shortcut_transfer_test_attempt.json` and `shortcut_transfer_test.json`
and record the rerun in this report.
