# Kia Soul classification on the HCRL release test

Real-data result on the local HCRL 2019 Kia Soul parquet. The question is the
dataset's own classification question: train on all nine training recordings
and detect the same attack types in the seven release recordings, which no
earlier model had used. Feature variants measure shortcut reliance (CAN ID,
timing, bus load). The release test was evaluated **once**, with settings
frozen beforehand on inner validation only.

**Each release file continues a training recording of the same capture
session** (see [Release files continue training sessions](#release-files-continue-training-sessions)).
The release test is therefore a forward-in-time holdout of the same sessions,
not a test on new recordings. Scores across recordings of different sessions
come only from the inner folds and are much lower (F1 0.375-0.859).

This differs from the earlier leave-one-attack-out (`unseen_*`) experiments,
where the tested attack type was absent from training. Scores of the two
protocols answer different questions and must not be read as an improvement
of one model over another.

## Why the protocol changed

Diagnostics run before this experiment (exploratory, on training recordings;
scripts were not committed):

- Raw CSV and parquet agree row by row (Replay recording: 566,338 rows in both;
  timestamp, ID, DLC, bytes and label identical in sampled attack rows).
- Time split inside each attack recording (first 60 % train, last 40 % test,
  XGBoost depth 6, ID+DLC+bytes): attack F1 1.000 for DoS, both Injection and
  two Spoofing recordings; 0.667 for Spoofing final-1st (58 test attacks);
  0.676 for Replay (0.746 with `iat_id`). The pipeline and model learn attacks
  they have seen.
- Random 50/50 row split of all training rows (deliberately leaky): F1 0.835
  (0.878 with `iat_id`). Frame-level labels have a ceiling.
- Replay: in the Replay recording, frames with `iat_id` below 8 ms are about
  half normal and half attack in every 1-2 ms bin. A replayed frame shortens
  its own gap and the gap of the next genuine frame, so timing marks the
  moment, not the frame. 80 % of Replay attack frames are content-identical to
  a normal training frame.
- The two Injection recordings are different attacks: final uses the
  vehicle's 45 IDs with 4-19 ms gaps; preliminary uses 2,048 random IDs with
  600-750 ms gaps.

Conclusion: the `unseen_*` zeros reflect asking a supervised classifier to
recognise an attack mechanism it never saw, not a pipeline error.

## Protocol

- **Data**: `official` split of `splits/generated/kia_soul/manifest.json`;
  train 2,736,954 rows (14.1 % attack), release test 1,605,516 rows (17.7 %).
  Input sha256 `4f6c6fd2…69c`, outer manifest `29a46934…04d`.
- **Inner validation**: `python splits/make_kia_validation.py --seen-types --fold official`
  (validation manifest `92ec2492…c41`). Every attack type in a validation
  fold also remains in its inner training; DoS and Replay (one recording each)
  always stay in training and are therefore absent from selection.
  - Fold 1: Injection final, Spoofing preliminary, one attack-free recording
    (124,321 attacks).
  - Fold 2: Injection preliminary, Spoofing final-1st and final-2nd, the other
    attack-free recording (88,823 attacks).
- **Variants**: A `standard` (ID, DLC, bytes); B `id_masked`; C = A + `iat_id`;
  D = B + `iat_id`; F `full` (A + `iat_id`, `iat_bus`, `bus_count_100ms`).
  Missing bytes -1, missing timing values left as NaN.
- **Model**: XGBoost, 100 trees, learning rate 0.1, hist, seed 42, depth 3 or 6.
- **Selection** (per variant, no winner across variants): highest unweighted
  mean fold AUPRC, shallower depth on ties; decision threshold maximises
  pooled out-of-fold F1. Selection file sha256 `7081a949…ef5e`.
- **Sampling**: stratified 1:5 sampling of normal rows was tried first and
  dropped. In fold 1 (variant A, depth 3) it raised false alarms from 47,845
  to 94,172 of 921,891 normal frames; variant C fold 1 F1 fell from 0.687 to
  0.662. Final models use all rows; they are deterministic, so one seed.
- **Release**: refit on the full training partition, predict the release test
  once (`release_test_attempt.json` guard). Python 3.12.3, NumPy 2.5.4,
  pandas 3.1.0, scikit-learn 1.9.1, XGBoost 3.4.1.

## Validation (inner folds)

Mean fold AUPRC for depth 3 / 6; all variants selected depth 6.

| Variant | Depth 3 | Depth 6 | Threshold | Fold 1 F1 / FPR | Fold 2 F1 / FPR |
|---|---:|---:|---:|---|---|
| A | 0.755 | 0.800 | 0.823 | 0.722 / 9.38 % | 0.763 / 0.00 % |
| B | 0.788 | 0.801 | 0.967 | 0.859 / 1.92 % | 0.375 / 0.00 % |
| C | 0.854 | 0.904 | 0.815 | 0.745 / 4.59 % | 0.756 / 0.01 % |
| D | 0.855 | 0.905 | 0.840 | 0.777 / 2.66 % | 0.757 / 0.00 % |
| F | 0.754 | 0.904 | 0.383 | 0.814 / 3.82 % | 0.748 / 0.26 % |

Most fold-1 false alarms fall in the attack-free recording (variant A,
full data: 35,537 of 47,845); their cause was not diagnosed. This did not
recur on the release test.

## Release files continue training sessions

Found after the run. Sorting all 16 Kia recordings by timestamp, every release
file starts 0.19-0.6 ms after a training recording ends (or ends just before
it starts), with the same IDs; each pair is one capture cut in two.

| Training recording | Release file | Gap |
|---|---|---:|
| preliminary Fuzzy (Injection) | preliminary `File_8` | 0.6 ms |
| preliminary Malfunction (Spoofing) | preliminary `File_9` | 0.3 ms |
| preliminary Flooding (DoS) | preliminary `File_7` | 0.19 ms |
| final_2nd Replay | final_2nd `File_4` | 0.25 ms |
| final_2nd Malfunction (Spoofing) | final_2nd `File_2` | 0.24 ms |
| final_1st Malfunction (Spoofing) | final_1st `File_4` (precedes it) | 0.24 ms |
| final_1st Fuzzy (Injection) | final_1st `File_2` | 0.24 ms |

This confirms the inferred attack type of every release file. It also means
the release scores below answer "same session, later minutes", like the 60/40
time split above (F1 1.000), not "new recording".

## Release test

Attack type per release file is **inferred** from its attack-frame ID pattern
(HCRL does not publish it), so these IDs were inspected before the run.
Values at the frozen threshold: attack recall / F1, and false alarms per second.

| Release file (inferred type, attacks) | A | B | C | D | F |
|---|---|---|---|---|---|
| prelim File_7 (DoS, 17,069) | 1.000 / 1.000, 0.0 | **0.000** / 0.000, 0.0 | 1.000 / 1.000, 0.0 | 0.977 / 0.988, 0.1 | 1.000 / 0.980, 32.0 |
| final_1st File_2 (Injection, 106,849) | 0.987 / 0.993, 0.8 | 0.953 / 0.976, 0.5 | 0.982 / 0.990, 1.5 | 0.980 / 0.988, 2.9 | 0.998 / 0.981, 29.3 |
| prelim File_8 (Injection, 18,199) | 0.984 / 0.992, 0.0 | 0.952 / 0.976, 0.0 | 0.995 / 0.997, 0.0 | 0.997 / 0.998, 0.0 | 0.999 / 0.999, 0.4 |
| final_2nd File_2 (Spoofing, 59,040) | 1.000 / 1.000, 0.0 | 1.000 / 1.000, 0.0 | 1.000 / 1.000, 0.0 | 1.000 / 1.000, 0.0 | 1.000 / 1.000, 0.1 |
| prelim File_9 (Spoofing, 2,631) | 0.989 / 0.995, 0.0 | 0.959 / 0.979, 0.0 | 0.992 / 0.996, 0.0 | 0.993 / 0.997, 0.0 | 0.999 / 1.000, 0.0 |
| final_1st File_4 (Spoofing, 170) | 0.000 / 0.000, 0.0 | 0.000 / 0.000, 0.0 | 0.000 / 0.000, 0.0 | 0.000 / 0.000, 0.0 | 0.594 / 0.689, 0.1 |
| final_2nd File_4 (Replay, 80,140) | **0.003** / 0.006, 0.0 | 0.000 / 0.000, 0.0 | 0.286 / 0.445, 0.5 | 0.246 / 0.394, 1.3 | 0.916 / 0.912, **73.1** |

Pooled over all files (dominated by the Replay file; read per file):

| Variant | Precision | Recall | F1 | FPR | AUPRC | F1 at 0.5 (post hoc) |
|---|---:|---:|---:|---:|---:|---:|
| A | 0.9995 | 0.712 | 0.832 | 0.01 % | 0.913 | 0.847 |
| B | 0.9996 | 0.636 | 0.777 | 0.01 % | 0.888 | 0.787 |
| C | 0.9988 | 0.791 | 0.883 | 0.02 % | 0.975 | 0.903 |
| D | 0.9976 | 0.778 | 0.874 | 0.04 % | 0.974 | 0.902 |
| F | 0.9576 | 0.975 | 0.966 | 0.93 % | 0.995 | 0.968 |

Of 566,215 normal release frames whose content equals a training Replay
attack frame, variant A flags 9 (C: 120); Replay content in training did not
cause noticeable false alarms.

## Findings

- **Known attack types are detected later in the same session.** With ID and
  payload, DoS, both Injection files and the two larger Spoofing files reach
  F1 0.99-1.00 at below 3 false alarms per second. Across sessions (inner
  folds, for example Injection final validated with only Injection
  preliminary in training) F1 is 0.375-0.859 with up to 9.4 % FPR.
- **DoS detection is an ID shortcut.** Removing the ID drops DoS recall from
  1.000 (A) to 0.000 (B); adding `iat_id` without the ID restores 0.977 (D).
- **`bus_count_100ms` is a recording-level shortcut.** F reaches Replay recall
  0.916 only by also flagging normal frames during attacks: 73 false alarms
  per second in the Replay file and 32 in the DoS file.
- **Replay is not separable frame by frame.** Content alone catches 0.3 %;
  `iat_id` reaches 25-29 %, consistent with the 50/50 gap ambiguity above.
- **The 170-attack Spoofing file** is missed by A-D; too small to interpret.

## Limitations

- One to three recordings per attack type; one vehicle. Release files are
  verified **not** independent of training (same sessions). Preliminary
  training recordings also overlap in time (Fuzzy 0-58 s, Malfunction
  45-97 s, attack-free 88-180 s) and sit in different inner folds; no
  identical frames were found between them. Results do not show
  generalisation to new attack mechanisms (see the `unseen_*` reports).
- The frozen OOF threshold was worse than 0.5 on the release test for every
  variant (pooled table): inner validation did not predict the release test.
- The file-to-type mapping is inferred and the release ID patterns were
  inspected before the run (partial contamination).
- `id_masked` does not hide the ID: in normal training frames, the
  (DLC, bytes) content identifies the CAN ID with 97.1 % in-sample accuracy.
  Read B and D as "ID not given explicitly".
- No release ID is absent from training, so new-ID generalisation is untested.
- DoS and Replay were absent from selection; one deterministic seed; no
  event-level metric or confidence interval.
- The one-shot guard is file based; `local_outputs/` is not versioned.

## Reproduction

```sh
python splits/make_kia_validation.py --seen-types --fold official
python experiments/kia_release_test.py select
python experiments/kia_release_test.py release --selection-sha256 <printed sha256>
```

Outputs in the ignored `experiments/kia_decision_tree/local_outputs/`:
`release_selection.json`, `release_test.json`, per-variant release
probabilities and the attempt file. The rejected sampled selection is kept as
`release_selection_sampled.json` (`select --sample-normals`).
