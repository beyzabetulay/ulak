"""
combined_dataset.csv -> numeric features, split into train/test parquet files.

Input: combined_dataset.csv (output of prepare_data.py)
Output (row order matches combined_dataset.csv):
  - features_all.parquet   : full dataset with numeric features
  - features_train.parquet : split == "train" (HCRL *_train folders)
  - features_test.parquet  : split == "test"  (HCRL *_release folders, attack_type unknown)

Kia Soul subset (output of prepare_kia_soul.py):
  python build_features.py --input kia_soul_dataset.csv --prefix kia_soul_features
  -> kia_soul_features_all.parquet, kia_soul_features_train.parquet, kia_soul_features_test.parquet
"""
import argparse
import pandas as pd
import numpy as np
import os

base = os.path.dirname(os.path.abspath(__file__))
parser = argparse.ArgumentParser(description="CAN frames CSV -> numeric feature parquet files")
parser.add_argument("--input", default="combined_dataset.csv", help="CSV from prepare_data.py or prepare_kia_soul.py")
parser.add_argument("--prefix", default="features", help="output files are <prefix>_all/_train/_test.parquet")
args = parser.parse_args()

df = pd.read_csv(os.path.join(base, args.input), dtype=str)

# --- sanity checks (verify the input is in the expected format) ---
assert df["label"].isin(["R", "T"]).all(), "label column contains values other than R/T"
assert df["can_id"].str.match(r"^[0-9A-Fa-f]+$").all(), "can_id contains non-hex values"

# --- can_id: hex string -> decimal int ---
df["can_id_dec"] = df["can_id"].apply(lambda x: int(x, 16))
# raw files mix 3- and 4-digit IDs ("080" vs "0080"); normalize so string counts match can_id_dec
df["can_id"] = df["can_id_dec"].apply(lambda x: f"{x:04X}")

# --- dlc: string -> int ---
df["dlc"] = df["dlc"].astype(int)

# --- data: "D0 1C 10 09 00 00 00 00" -> byte_0..byte_7 (0-255), missing bytes are NaN ---
byte_lists = df["data"].str.split()
for i in range(8):
    df[f"byte_{i}"] = byte_lists.apply(lambda b, i=i: int(b[i], 16) if i < len(b) else np.nan)

# --- timestamp: string -> float ---
df["timestamp"] = df["timestamp"].astype(float)

# --- label: R/T -> 0/1 (model target variable) ---
df["label_bin"] = (df["label"] == "T").astype(int)

# --- recording_id: one value per raw CSV ---
# File names repeat across folders (File_1.csv in three release folders,
# Attack_free_KIA_Soul_train.csv in two train folders), so source_file alone
# merges separate recordings. Group by recording_id instead.
df["recording_id"] = df["source_folder"] + "/" + df["source_file"]

# --- timing features ---
# Computed per recording in timestamp order, using only past frames (causal).
# Row order of the output stays unchanged: splits/ stores row positions into these files.
BUS_WINDOW_S = 0.1
ts_sorted = df[["recording_id", "can_id_dec", "timestamp"]].sort_values(
    ["recording_id", "timestamp"], kind="stable")

# time since the previous frame on the bus (any ID); NaN for a recording's first frame
iat_bus = ts_sorted.groupby("recording_id")["timestamp"].diff()
# time since the previous frame with the same ID; NaN for an ID's first frame in a recording
iat_id = ts_sorted.groupby(["recording_id", "can_id_dec"])["timestamp"].diff()


def frames_in_window(ts):
    # frames in (t - BUS_WINDOW_S, t], including the current one
    t = ts.to_numpy()
    return pd.Series(np.arange(len(t)) - np.searchsorted(t, t - BUS_WINDOW_S, side="right") + 1,
                     index=ts.index)


bus_count = ts_sorted.groupby("recording_id", group_keys=False)["timestamp"].apply(frames_in_window)

df["iat_bus"] = iat_bus
df["iat_id"] = iat_id
df["bus_count_100ms"] = bus_count

cols = ["timestamp", "can_id", "can_id_dec", "dlc"] + [f"byte_{i}" for i in range(8)] + \
       ["iat_bus", "iat_id", "bus_count_100ms"] + \
       ["label", "label_bin", "vehicle", "attack_type", "source_file", "source_folder", "recording_id", "split"]
# prepare_kia_soul.py also records the HCRL round (preliminary / final_1st / final_2nd)
if "round" in df.columns:
    cols.append("round")
df = df[cols]

df.to_parquet(os.path.join(base, f"{args.prefix}_all.parquet"), index=False)

train = df[df["split"] == "train"]
test = df[df["split"] == "test"]
train.to_parquet(os.path.join(base, f"{args.prefix}_train.parquet"), index=False)
test.to_parquet(os.path.join(base, f"{args.prefix}_test.parquet"), index=False)

print("all  :", df.shape)
print("train:", train.shape, "-> label_bin distribution:\n", train["label_bin"].value_counts())
print("test :", test.shape, " -> label_bin distribution:\n", test["label_bin"].value_counts())
print("\nNaN byte ratio (comes from rows with dlc < 8):")
print(df[[f"byte_{i}" for i in range(8)]].isna().mean())
