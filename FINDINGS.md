# Data Findings

Notes from exploring the HCRL dataset after `prepare_data.py` / `build_features.py`.
Read this before building models or attack scenarios on top of this data.

## Schema reference

| Column | Meaning |
|---|---|
| `timestamp` | Unix epoch (seconds.microseconds) when the frame was captured |
| `can_id` | Arbitration ID, hex string. Lower ID = higher bus priority. The mapping from ID to a physical signal (RPM, steering, etc.) is manufacturer-proprietary (DBC file) and **not available** for this dataset — IDs are opaque numbers here |
| `can_id_dec` | `can_id` converted to decimal, for numeric model input |
| `dlc` | Data length code: number of payload bytes (0-8) |
| `byte_0`..`byte_7` | Raw payload bytes (0-255). Missing when `dlc < 8` (`NaN`, not zero-filled) |
| `label` | **Ground truth per frame.** `R` = regular/normal, `T` = tampered/attack |
| `label_bin` | `label` as 0/1, the actual model target |
| `vehicle` | Hyundai_Sonata / Kia_Soul / Chevrolet_Spark / unknown — derived from filename, **not part of the original CAN data** |
| `attack_type` | DoS / Injection / Spoofing / Replay / Normal / mixed-unknown — derived from filename, **not part of the original CAN data** |
| `source_file`, `source_folder` | Traceability back to the original HCRL file |
| `split` | `train` (HCRL `*_train` folders) or `test` (HCRL `*_release` folders) |

## label vs. attack_type — do not confuse these

- `label` is the real ground truth for every row, always known (R/T).
- `attack_type` is a coarse label guessed from the **filename**, not from the row itself.
- In the test split (`*_release` folders), a single file mixes normal and attack
  frames together and the real attack type is deliberately withheld by the
  challenge organizers — so `attack_type = "mixed/unknown"` for the entire test
  split. `label`/`label_bin` is still correct and usable there.

## Critical: do not feed `vehicle` / `attack_type` to a model

Both are reconstructed from filenames, not from the CAN signal itself. Using
them as model input features would let a model "cheat" by reading metadata
instead of learning attack behavior — this is exactly the shortcut-learning
failure mode this project investigates. Use them only for grouping/analysis
(e.g. leave-one-vehicle-out generalization tests), never as features.

## Class imbalance

Train split: 4,766,085 normal (`label_bin=0`) vs 743,167 attack (`label_bin=1`)
— roughly 87% / 13%. Plain accuracy is misleading here; use precision/recall/F1
per class.

## Key shortcut-learning findings

### 1. DoS attacks are 100% identifiable by `can_id == "0000"` alone

Every single DoS-labeled attack row (48,164/48,164 in the train split) has
`can_id = "0000"`. This is not a data artifact — it follows from how CAN
arbitration works: the ID with the most dominant (zero) bits always wins the
bus, so `0x000` has the highest possible priority. A flooding/DoS attack uses
it to guarantee it saturates the bus. A model can hit 100% accuracy on DoS by
checking one feature equals zero, without learning anything about flooding
behavior (message rate, timing). Any attacker who floods with a non-zero ID
would likely break a model that learned this shortcut.

### 2. Fuzzy/Injection attacks explode CAN ID cardinality

Unique `can_id` values seen: **155** during normal traffic vs. **2,048**
during Injection (Fuzzy) attacks. Fuzzing injects random/unused IDs, so
"unseen ID" is a strong but superficial signal — a model relying on it would
likely fail against a fuzzer that stays within the legitimate ID range.

## Open caveats

- No DBC file: payload bytes cannot be decoded into real physical signals,
  only used as raw numeric features.
- No formal license published for the dataset (see README) — download it
  from the original source yourself, don't redistribute copies.
- Not yet explored: timestamp/inter-arrival-time features (relevant to
  flooding-rate shortcuts) and payload-level statistics beyond raw bytes.
  Revisit if the AI team's results suggest a timing-based shortcut.
