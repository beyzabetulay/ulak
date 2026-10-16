"""
combined_dataset.csv -> numeric features, split into train/test parquet files.

Input: combined_dataset.csv (output of prepare_data.py)
Output:
  - features_all.parquet   : full dataset with numeric features
  - features_train.parquet : split == "train" (HCRL *_train folders)
  - features_test.parquet  : split == "test"  (HCRL *_release folders, attack_type unknown)
"""
import pandas as pd
import numpy as np
import os

base = os.path.dirname(os.path.abspath(__file__))
df = pd.read_csv(os.path.join(base, "combined_dataset.csv"), dtype=str)

# --- sanity checks (verify prepare_data.py's output is in the expected format) ---
assert df["label"].isin(["R", "T"]).all(), "label column contains values other than R/T"
assert df["can_id"].str.match(r"^[0-9A-Fa-f]+$").all(), "can_id contains non-hex values"

# --- can_id: hex string -> decimal int ---
df["can_id_dec"] = df["can_id"].apply(lambda x: int(x, 16))

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

cols = ["timestamp", "can_id", "can_id_dec", "dlc"] + [f"byte_{i}" for i in range(8)] + \
       ["label", "label_bin", "vehicle", "attack_type", "source_file", "source_folder", "split"]
df = df[cols]

df.to_parquet(os.path.join(base, "features_all.parquet"), index=False)

train = df[df["split"] == "train"]
test = df[df["split"] == "test"]
train.to_parquet(os.path.join(base, "features_train.parquet"), index=False)
test.to_parquet(os.path.join(base, "features_test.parquet"), index=False)

print("all  :", df.shape)
print("train:", train.shape, "-> label_bin distribution:\n", train["label_bin"].value_counts())
print("test :", test.shape, " -> label_bin distribution:\n", test["label_bin"].value_counts())
print("\nNaN byte ratio (comes from rows with dlc < 8):")
print(df[[f"byte_{i}" for i in range(8)]].isna().mean())
