import pandas as pd
import glob, os

base = os.path.dirname(os.path.abspath(__file__))
rows = []

# Restricted to car_track_*/*.csv: folders like venv/ don't match this pattern,
# which keeps a recursive glob from picking up unrelated numpy test CSVs.
for f in sorted(glob.glob(os.path.join(base, "car_track_*", "*.csv"))):
    fname = os.path.basename(f)
    folder = os.path.basename(os.path.dirname(f))
    with open(f) as fh:
        ncols = len(fh.readline().strip().split(","))
    cols = ["idx", "timestamp", "can_id", "dlc", "data", "label"] if ncols == 6 else \
           (["timestamp", "can_id", "dlc", "data", "label"] if ncols == 5 else
            ["timestamp", "can_id", "dlc", "data"])
    df = pd.read_csv(f, header=None, names=cols, dtype=str)

    # attack_free files have no label column because every row is normal
    if "label" not in df.columns:
        df["label"] = "R"

    # derive vehicle name from filename
    if "KIA" in fname or "Soul" in fname:
        vehicle = "Kia_Soul"
    elif "HY" in fname or "Sonata" in fname or "HYUNDAI" in fname:
        vehicle = "Hyundai_Sonata"
    elif "CHEVROLET" in fname or "Spark" in fname:
        vehicle = "Chevrolet_Spark"
    else:
        vehicle = "unknown"

    # derive attack type from filename
    low = fname.lower()
    if "flooding" in low: attack = "DoS"
    elif "fuzzy" in low: attack = "Injection"
    elif "malfunction" in low: attack = "Spoofing"
    elif "replay" in low: attack = "Replay"
    elif "attack_free" in low: attack = "Normal"
    else: attack = "mixed/unknown"

    # train/release folders are HCRL's own split: train = training, release = holdout/test
    split = "train" if folder.endswith("_train") else "test"

    df["vehicle"] = vehicle
    df["attack_type"] = attack
    df["source_file"] = fname
    df["source_folder"] = folder
    df["split"] = split
    rows.append(df[["timestamp", "can_id", "dlc", "data", "label", "vehicle", "attack_type",
                     "source_file", "source_folder", "split"]])

full = pd.concat(rows, ignore_index=True)
full.to_csv(os.path.join(base, "combined_dataset.csv"), index=False)
print(full.shape)
print(full["vehicle"].value_counts())
print(full["attack_type"].value_counts())
print(full["label"].value_counts())
