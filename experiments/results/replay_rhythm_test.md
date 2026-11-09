# Replay detection with rhythm features (Kia → Hyundai Sonata)

Real-data result on the raw HCRL 2019 CSV files. Settings were selected on the
Kia Soul Replay recording only, then the model was evaluated **once** on the
Hyundai Sonata Replay recording, which no earlier model had used. The Kia
release Replay file (final_2nd `File_4`) is reported as a second look: it was
already evaluated once in [the release test](kia_release_test.md).

The Sonata test is **semi-held-out**: before the features were designed, the
labelled Sonata Replay file was inspected (injection pattern, identical
payloads, and the `phase2` rule AUPRC of 0.716). Kia `File_4` is the direct
continuation of the Kia training Replay recording (it starts 0.25 ms after it
ends), so it measures the same session later, not a new recording.

## Why

In the release test, Replay stayed at F1 0.445 (variant C) while the other
attack types reached 0.99-1.00. The raw recordings show why. In both vehicles
the attack runs in 10 s episodes separated by 10 s without attack, and every
ID is attacked (Kia 45 of 45, Sonata 27 of 27). During an episode the
attacker inserts an old copy into each ID's stream about every 1.33 periods
(about every 13 ms for a 10 ms ID):

- The genuine frame right after a copy also has a short gap to its previous
  frame (Kia: 154,486 such normal frames for 155,640 copies). The gap to the
  previous frame (`iat_id`) therefore cannot tell them apart: frames with a
  short gap are about half copies and half genuine.
- Genuine frames keep the ID's rhythm; a copy falls between two beats. The gap
  to the frame **two** back is a whole number of periods for a genuine frame
  and a fraction (for example 1.3) for a copy.
- Kia ID 0153 carries a counter (`byte_6` steps by 0x10); a copy carries an
  old value. In Sonata the copied payload is often identical to the genuine
  one (ID 02C0: `14 00 00 ...`), so only timing separates them.

## Setup

All features are past-only, per CAN ID, and divided by the ID's median period
measured on an attack-free recording of the same vehicle. No CAN ID, raw
payload or bus-load feature enters the model, so a model trained on Kia can
score Sonata frames.

| Feature | Meaning |
|---|---|
| `gap1`, `gap2`, `gap3` | time to the 1st/2nd/3rd previous frame of the same ID, in periods |
| `phase2`, `phase3` | distance of `gap2`/`gap3` to the nearest whole number |
| `count100` | same-ID frames in the past 100 ms divided by the expected count |
| `bits1`, `bits2` | payload bits changed against the 1st/2nd previous same-ID frame |
| `dlc` | data length |

Variants: R0 = `gap1`, `count100` (rate only); R1 = R0 + `gap2`, `phase2`,
`gap3`, `phase3` (rhythm); R2 = R1 + `bits1`, `bits2`, `dlc` (rhythm and
content). Rule baseline: `phase2` alone as a score, without a model.

| Role | Kia Soul | Hyundai Sonata |
|---|---|---|
| Period calibration | final_1st `Attack_free_KIA_Soul_train.csv` | final_1st `Attack_free_HY_Sonata_train.csv` |
| Training / selection | final_2nd `Replay_dataset_KIA_Soul_train.csv`, preliminary `Attack_free_KIA_Soul_train.csv` | – |
| Test (once) | final_2nd release `File_4.csv` (second look) | final_2nd `Replay_dataset_HY_Sonata_train.csv`, preliminary `Attack_free_HYUNDAI_Sonata_train.csv` |

Calibration files are never used as training or test rows. Selection splits
each training file into the first and second half of its time span; each half
is the validation block once (block 0: 383,143 rows, 81,324 copies; block 1:
375,711 rows, 74,316 copies). Features are computed on the full stream before
splitting. XGBoost settings are shared with the earlier Kia experiments (100
trees, learning rate 0.1, hist, seed 42). Depth 3 or 6 was chosen by mean
fold AUPRC (depth 6 for every variant), and the out-of-fold F1 threshold was
frozen. Selection file sha256:
`df40f3d75a24d52331e536fb5fe7aa4af8729baa4eaff256d83a4909a0f5b8f9`.

## Validation (Kia, two time blocks)

| Variant | Fold AUPRC | OOF precision | OOF recall | OOF F1 | OOF FPR |
|---|---|---:|---:|---:|---:|
| `phase2` rule | 0.672 / 0.708 | – | – | – | – |
| R0 | 0.579 / 0.619 | 0.506 | 0.909 | 0.651 | 22.9 % |
| R1 | 0.940 / 0.965 | 0.885 | 0.885 | 0.885 | 3.0 % |
| R2 | 0.955 / 0.979 | 0.909 | 0.907 | 0.908 | 2.3 % |

## Test (evaluated once)

Values at the frozen OOF threshold. "After copy" is the share of genuine
frames directly after a copy that are flagged.

| File | Variant | Precision | Recall | F1 | AUPRC | FPR | False alarms/s | After copy |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Sonata Replay (145,902 copies) | `phase2` rule | – | – | – | 0.716 | – | – | – |
| | R0 | 0.465 | 0.932 | 0.620 | 0.465 | 40.7 % | 794.8 | 88.7 % |
| | R1 | 0.853 | 0.873 | 0.863 | 0.940 | 5.7 % | 111.6 | 12.5 % |
| | R2 | 0.855 | 0.900 | **0.877** | 0.947 | 5.8 % | 113.3 | 13.2 % |
| Sonata attack-free | R0 | – | – | – | – | 2.95 % | 57.7 | – |
| | R1 | – | – | – | – | 0.04 % | 0.8 | – |
| | R2 | – | – | – | – | 0.02 % | 0.3 | – |
| Kia release `File_4` (80,140 copies, second look) | `phase2` rule | – | – | – | 0.694 | – | – | – |
| | R0 | 0.520 | 0.945 | 0.671 | 0.637 | 32.4 % | 677.3 | 78.6 % |
| | R1 | 0.879 | 0.881 | 0.880 | 0.954 | 4.5 % | 94.7 | 9.2 % |
| | R2 | 0.901 | 0.904 | **0.903** | 0.966 | 3.7 % | 77.5 | 8.3 % |

At threshold 0.5, R1 and R2 stay within 0.01 F1 of these values (R2: Sonata
0.877, Kia `File_4` 0.902); R0 drops to 0.280 (Sonata) and 0.565 (Kia `File_4`).

## Findings

- **Rhythm resolves most of the Replay ambiguity.** Adding the gaps to the
  2nd and 3rd previous frame raises F1 from 0.62 to 0.86 on Sonata and from
  0.67 to 0.88 on the Kia release file. Flagged genuine frames directly after
  a copy fall from 89 % to 13 % (Sonata).
- **The features transfer across vehicles.** A model selected on Kia only
  reaches F1 0.877 on the Sonata recording, close to its Kia validation
  (0.908), and raises 0.3 false alarms per second on a clean Sonata drive.
  The Sonata file had been inspected before the design (see above).
- **Content adds little.** R2 over R1 gains 0.014 F1 on Sonata and 0.023 on
  the Kia release file, consistent with Sonata copies often being identical to
  the genuine payload.
- **Compared with the release test**, the Kia release Replay file improves
  from F1 0.445 (variant C) to 0.903 (R2). The models differ in training data
  (Replay recording plus attack-free versus all nine recordings) and features,
  the file was seen before, and it continues the training session; read this
  as a second look, not a clean test.
- **False alarms remain inside attacks.** The false alarms per second in the
  table average over the whole file. Split by attack episode (R2, frozen
  threshold), the Sonata Replay recording has 221.5 per second during
  episodes and 1.7 between them; Kia `File_4` has 158.4 and 1.2. The clean
  Sonata drive has 0.3. The remaining errors are genuine frames whose rhythm
  is disturbed by the attack.

## Limitations

- One Kia Replay recording; selection used two halves of the same recording,
  not independent recordings.
- Both vehicles' Replay recordings were made in the same challenge round with
  the same injection pattern (10 s episodes, a copy about every 1.33
  periods); the Sonata test measures transfer to another vehicle, not to
  another attacker or injection rate.
- The Sonata Replay file was inspected with labels before the features were
  designed; no independent, untouched Replay recording exists in the dataset.
- The OOF threshold comes from models trained on half of the Kia data and is
  applied to a model refit on all of it; at 0.5, R1 and R2 change by at most
  0.01 F1, but R0 is sensitive to it.
- The method needs an attack-free recording of the vehicle to measure ID
  periods; IDs absent from that recording get no timing features.
- The model is trained against Replay only; it was not checked on DoS,
  Injection or Spoofing recordings.
- Frame-level labels and metrics; no event-level metric or confidence
  interval; one deterministic seed. The one-shot guard is file based.

## Reproduction

```sh
python experiments/replay_rhythm_test.py select
python experiments/replay_rhythm_test.py test --selection-sha256 <printed sha256>
```

Prerequisites: raw `car_track_*` folders in the repository root (see the README
Dataset section) and `pip install -r experiments/requirements.txt`; no parquet
or split files are needed. Outputs in the ignored
`experiments/kia_decision_tree/local_outputs/`: `replay_selection.json`,
`replay_rhythm_test.json`, the attempt file and per-variant test
probabilities.

Pass the sha256 that your own `select` prints; it can differ from the hash
above if library versions differ. `test` writes `replay_rhythm_test_attempt.json`
before fitting, so a crash also uses up the attempt. Delete the attempt file
only for a deliberate rerun and record that rerun in this report.
