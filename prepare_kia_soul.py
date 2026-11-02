"""
Single-vehicle subset: every Kia Soul frame from all six HCRL folders -> kia_soul_dataset.csv

Input:  car_track_*/*.csv (raw HCRL challenge files)
Output:
  - kia_soul_dataset.csv          : merged Kia Soul frames (not committed, regenerate with this script)
  - reports/kia_soul_summary.md   : row counts and label / attack type / round breakdowns

How files are assigned to Kia Soul:
  - *_train folders: the vehicle name is in the filename (KIA / Soul).
  - *_release folders: files are only named File_N.csv, so the vehicle is identified by
    its CAN ID fingerprint. Each vehicle broadcasts its own fixed set of IDs; a release
    file belongs to Kia Soul when the IDs in its normal (R) frames match the IDs in the
    Kia Soul Attack_free files (Jaccard similarity >= FINGERPRINT_THRESHOLD). Attack (T)
    frames are left out of the fingerprint because fuzzing injects random IDs.
"""
import pandas as pd
import glob, os

base = os.path.dirname(os.path.abspath(__file__))
VEHICLE = "Kia_Soul"
FINGERPRINT_THRESHOLD = 0.9
OUT_COLS = ["timestamp", "can_id", "dlc", "data", "label", "vehicle", "attack_type",
            "round", "split", "source_folder", "source_file"]


def read_raw(path):
    """Read one HCRL CSV into timestamp, can_id, dlc, data, label (4/5/6 column layouts)."""
    with open(path) as fh:
        ncols = len(fh.readline().strip().split(","))
    cols = ["idx", "timestamp", "can_id", "dlc", "data", "label"] if ncols == 6 else \
           (["timestamp", "can_id", "dlc", "data", "label"] if ncols == 5 else
            ["timestamp", "can_id", "dlc", "data"])
    df = pd.read_csv(path, header=None, names=cols, dtype=str)

    # attack_free files have no label column because every row is normal
    if "label" not in df.columns:
        df["label"] = "R"

    # Attack_free files write IDs as 3 hex digits ("316"), all other files as 4 ("0316").
    # Left as-is, the same ID would look like two different values depending on the source file.
    df["can_id"] = df["can_id"].str.upper().str.zfill(4)
    return df[["timestamp", "can_id", "dlc", "data", "label"]]


def is_kia_filename(fname):
    return "KIA" in fname or "Soul" in fname


def attack_type_from_filename(fname):
    low = fname.lower()
    if "flooding" in low: return "DoS"
    if "fuzzy" in low: return "Injection"
    if "malfunction" in low: return "Spoofing"
    if "replay" in low: return "Replay"
    if "attack_free" in low: return "Normal"
    # release files mix normal and attack frames; HCRL withholds the attack type
    return "mixed/unknown"


def jaccard(a, b):
    return len(a & b) / len(a | b)


files = sorted(glob.glob(os.path.join(base, "car_track_*", "*.csv")))
train_files = [f for f in files if os.path.basename(os.path.dirname(f)).endswith("_train")]
release_files = [f for f in files if os.path.basename(os.path.dirname(f)).endswith("_release")]

# --- Kia Soul reference fingerprint: all IDs seen in its attack-free recordings ---
reference_ids = set()
for f in train_files:
    fname = os.path.basename(f)
    if is_kia_filename(fname) and attack_type_from_filename(fname) == "Normal":
        reference_ids |= set(read_raw(f)["can_id"])
print(f"Kia Soul reference fingerprint: {len(reference_ids)} CAN IDs")

# --- select files and merge ---
parts, assignment_log = [], []
for f in files:
    fname = os.path.basename(f)
    folder = os.path.basename(os.path.dirname(f))

    if f in train_files:
        if not is_kia_filename(fname):
            continue
        df = read_raw(f)
        how = "filename"
    else:
        df = read_raw(f)
        score = jaccard(set(df.loc[df["label"] == "R", "can_id"]), reference_ids)
        assignment_log.append((folder, fname, score))
        if score < FINGERPRINT_THRESHOLD:
            continue
        how = f"fingerprint (Jaccard {score:.2f})"

    df["vehicle"] = VEHICLE
    df["attack_type"] = attack_type_from_filename(fname)
    df["round"] = folder.removeprefix("car_track_").rsplit("_", 1)[0]  # preliminary / final_1st / final_2nd
    df["split"] = "train" if folder.endswith("_train") else "test"
    df["source_folder"] = folder
    df["source_file"] = fname
    parts.append(df[OUT_COLS])
    print(f"  + {folder}/{fname}: {len(df):,} rows via {how}")

kia = pd.concat(parts, ignore_index=True)

# --- sanity checks ---
assert kia["label"].isin(["R", "T"]).all(), "label column contains values other than R/T"
assert kia["can_id"].str.fullmatch(r"[0-9A-F]{4}").all(), "can_id is not a 4-digit hex string"
assert kia[["timestamp", "can_id", "dlc"]].notna().all().all(), "missing timestamp/can_id/dlc"
assert set(kia["attack_type"]) >= {"DoS", "Injection", "Spoofing", "Replay"}, "an attack type is missing"

kia.to_csv(os.path.join(base, "kia_soul_dataset.csv"), index=False)
print(f"\nkia_soul_dataset.csv: {kia.shape[0]:,} rows x {kia.shape[1]} columns")


# --- summary report ---
def count_table(df, rows, header):
    t = pd.crosstab(df[rows], df["label"], margins=True, margins_name="total")
    t = t.reindex(columns=["R", "T", "total"], fill_value=0)
    lines = [f"| {header} | R (normal) | T (attack) | total |", "|---|---:|---:|---:|"]
    lines += [f"| {idx} | {r['R']:,} | {r['T']:,} | {r['total']:,} |" for idx, r in t.iterrows()]
    return "\n".join(lines)


labels = kia["label"].value_counts()
report = f"""# Kia Soul subset summary

Generated by `prepare_kia_soul.py`. Output file: `kia_soul_dataset.csv`
({kia.shape[0]:,} rows, {len(parts)} source files).

## Label distribution

| label | rows | share |
|---|---:|---:|
| R (normal) | {labels.get('R', 0):,} | {labels.get('R', 0) / len(kia):.2%} |
| T (attack) | {labels.get('T', 0):,} | {labels.get('T', 0) / len(kia):.2%} |

## By attack type

`attack_type` comes from the filename. Release (test) files mix normal and attack
frames and HCRL does not publish which attack they contain, so they are `mixed/unknown`.

{count_table(kia, 'attack_type', 'attack_type')}

## By round (preliminary vs final)

{count_table(kia, 'round', 'round')}

## By round and split

{count_table(kia.assign(round_split=kia['round'] + ' / ' + kia['split']), 'round_split', 'round / split')}

## Release file assignment (CAN ID fingerprint)

Jaccard similarity between each release file's normal-frame CAN IDs and the
{len(reference_ids)} IDs of the Kia Soul attack-free recordings. Files at or above
{FINGERPRINT_THRESHOLD} are included.

| folder | file | Jaccard | included |
|---|---|---:|---|
""" + "\n".join(f"| {fo} | {fn} | {s:.3f} | {'yes' if s >= FINGERPRINT_THRESHOLD else 'no'} |"
                for fo, fn, s in assignment_log) + "\n"

os.makedirs(os.path.join(base, "reports"), exist_ok=True)
with open(os.path.join(base, "reports", "kia_soul_summary.md"), "w") as fh:
    fh.write(report)

print(labels)
print(kia["attack_type"].value_counts())
print(kia["round"].value_counts())
