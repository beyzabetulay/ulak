"""Validate the Data Engineer's feature interface; never parse raw CAN CSVs."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

BYTES = [f"byte_{i}" for i in range(8)]
PAYLOAD = ["can_id_dec", "dlc", *BYTES]
TIMING = ["iat_bus", "iat_id", "bus_count_100ms"]
ALLOWED_FEATURES = set(PAYLOAD + TIMING)
METADATA = ["vehicle", "attack_type", "source_folder", "source_file", "recording_id", "split"]


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require_columns(df, columns):
    missing = set(columns) - set(df.columns)
    if missing:
        raise ValueError(f"Missing canonical columns: {sorted(missing)}; run build_features.py")


def validate_frames(df):
    require_columns(df, ["timestamp", "label_bin", *PAYLOAD, *METADATA])
    if df.empty:
        raise ValueError("Feature table is empty")
    for column in METADATA:
        if df[column].isna().any() or not df[column].map(lambda v: isinstance(v, str) and bool(v.strip())).all():
            raise ValueError(f"Missing or invalid grouping metadata: {column}")
    if "session_id" in df and (df.session_id.isna().any() or df.session_id.astype(str).str.strip().eq("").any()):
        raise ValueError("Missing session_id; omit the column if independent sessions are unavailable")
    expected = df.source_folder + "/" + df.source_file
    if not df.recording_id.eq(expected).all():
        raise ValueError("recording_id must equal source_folder/source_file")
    if not df.label_bin.isin([0, 1]).all():
        raise ValueError("label_bin must contain only 0 (R) or 1 (T)")
    if "label" in df:
        if not df.label.isin(["R", "T"]).all() or not df.label.eq(df.label_bin.map({0: "R", 1: "T"})).all():
            raise ValueError("R/T labels disagree with label_bin")
    if (df.attack_type.eq("Normal") & df.label_bin.eq(1)).any():
        raise ValueError("Attack-free Normal context contains injected frames; review labels/provenance")
    if not df.split.isin(["train", "test", "validation"]).all():
        raise ValueError("Unexpected partition in split")
    if not pd.api.types.is_numeric_dtype(df.timestamp) or not np.isfinite(df.timestamp).all():
        raise ValueError("timestamp must be finite numeric seconds")
    for column, maximum in [("can_id_dec", 0x7FF), ("dlc", 8), *[(c, 255) for c in BYTES]]:
        values = df[column]
        if not pd.api.types.is_numeric_dtype(values):
            raise ValueError(f"{column} must be numeric")
        present = values.dropna()
        if not (np.isfinite(present) & present.between(0, maximum) & present.eq(np.floor(present))).all():
            raise ValueError(f"{column} outside the HCRL classic CAN integer range")
        if column in ["dlc", "can_id_dec"] and values.isna().any():
            raise ValueError(f"Missing {column}")
    for i, column in enumerate(BYTES):
        if not df[column].notna().eq(df.dlc.gt(i)).all():
            raise ValueError(f"{column} presence disagrees with DLC")
    for column in ["vehicle", "attack_type", "source_folder", "source_file", "split", "round", "session_id"]:
        if column in df and df.groupby("recording_id")[column].nunique(dropna=False).gt(1).any():
            raise ValueError(f"A recording has inconsistent {column}")


def load_features(path):
    """Use build_features.py output, retaining its unchanged positional indices."""
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"Feature file unavailable: {path}; run the existing data pipeline first")
    df = pd.read_parquet(path).reset_index(drop=True)
    validate_frames(df)
    derived_round = df.source_folder.str.extract(r"^car_track_(preliminary|final_1st|final_2nd)_(?:train|release)$", expand=False)
    if "round" in df and derived_round.notna().any():
        if not df.loc[derived_round.notna(), "round"].eq(derived_round.dropna()).all():
            raise ValueError("round disagrees with source_folder")
    if "round" not in df:
        df["round"] = derived_round.fillna("unknown")
    return df


def feature_contract(columns):
    if not columns or len(columns) != len(set(columns)):
        raise ValueError("Feature list must be nonempty and unique")
    forbidden = set(columns) - ALLOWED_FEATURES
    if forbidden:
        raise ValueError(f"Unsafe/unreviewed predictive features: {sorted(forbidden)}")


def write_json(path, result):
    """Exclusive creation protects existing experiment artifacts."""
    encoded = json.dumps(result, indent=2, allow_nan=False) + "\n"
    with Path(path).open("x") as stream:
        stream.write(encoded)
