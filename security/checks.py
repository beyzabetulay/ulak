"""Fail-fast partition checks and diagnostic duplicate/causality audits."""
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .data import BYTES, PAYLOAD, TIMING, feature_contract, require_columns, sha256


def checked_positions(values, rows, name):
    values = np.asarray(values)
    if values.ndim != 1 or not np.issubdtype(values.dtype, np.integer) or not len(values):
        raise ValueError(f"{name}: indices must be a nonempty integer vector")
    if values.min() < 0 or values.max() >= rows or len(np.unique(values)) != len(values):
        raise ValueError(f"{name}: duplicate or out-of-range row positions")
    return values


def check_partitions(df, partitions):
    if "train" not in partitions or "test" not in partitions:
        raise ValueError("Both train and test partitions are required")
    checked = {k: checked_positions(v, len(df), k) for k, v in partitions.items()}
    for left, right in itertools.combinations(checked, 2):
        a, b = df.iloc[checked[left]], df.iloc[checked[right]]
        if np.intersect1d(checked[left], checked[right]).size:
            raise ValueError(f"{left}/{right}: row overlap")
        for group in ["recording_id", "session_id"]:
            if group in df:
                if a[group].isna().any() or b[group].isna().any():
                    raise ValueError(f"Missing {group} for split audit")
                overlap = set(a[group]) & set(b[group])
                if overlap:
                    raise ValueError(f"{left}/{right}: {group} overlap: {sorted(overlap)[:5]}")
    return checked


def load_manifest(path, input_path, df):
    path = Path(path)
    manifest = json.loads(path.read_text())
    if manifest.get("sha256") != sha256(input_path) or manifest.get("rows") != len(df):
        raise ValueError("Manifest input hash/row count mismatch; regenerate splits for this exact file")
    if manifest.get("target") != "label_bin":
        raise ValueError("Manifest target must be label_bin")
    variants = manifest.get("variants", {})
    if not variants:
        raise ValueError("Manifest lacks feature contracts")
    for columns in variants.values():
        feature_contract(columns)
        require_columns(df, columns)
    folds = []
    names = set()
    for number, fold in enumerate(manifest.get("folds", [])):
        name = str(fold.get("name", fold.get("held_out_vehicle", f"fold_{number}")))
        if name in names:
            raise ValueError(f"Duplicate fold name: {name}")
        names.add(name)
        partitions = {}
        for part in ["train", "validation", "test"]:
            if part not in fold:
                continue
            index_path = (path.parent / fold[part]["indices"]).resolve()
            if not index_path.is_relative_to(path.parent.resolve()):
                raise ValueError("Index artifacts must be inside the manifest directory")
            partitions[part] = np.load(index_path, allow_pickle=False)
            if fold[part].get("rows") != len(partitions[part]):
                raise ValueError(f"{name}/{part}: manifest row count disagrees with indices")
        folds.append((name, check_partitions(df, partitions)))
    if not folds:
        raise ValueError("Manifest has no folds")
    return manifest, folds


def check_fit_rows(partitions, fitted_positions):
    """Check an optional preprocessing receipt; cannot infer fitting history from X."""
    fitted = np.asarray(fitted_positions)
    if fitted.ndim != 1 or not len(fitted) or not np.issubdtype(fitted.dtype, np.integer):
        raise ValueError("Preprocessing fit receipt requires nonempty integer row positions")
    if len(np.unique(fitted)) != len(fitted) or not set(fitted) <= set(partitions["train"]):
        raise ValueError("Preprocessing was fitted on rows outside the training partition or has duplicate rows")


def check_temporal_features(df):
    """Recompute past-only features in capture row order, including timestamp ties."""
    require_columns(df, TIMING)
    for recording, group in df.groupby("recording_id", sort=False):
        time = group.timestamp.to_numpy(dtype=float)
        if (np.diff(time) < 0).any():
            raise ValueError(f"{recording}: timestamps decrease in capture order; causality needs review")
        expected = {
            "iat_bus": group.timestamp.diff().to_numpy(),
            "iat_id": group.groupby("can_id_dec", sort=False).timestamp.diff().to_numpy(),
            "bus_count_100ms": np.arange(len(time)) - np.searchsorted(time, time - 0.1, side="right") + 1,
        }
        for column, values in expected.items():
            if not np.allclose(group[column].to_numpy(dtype=float), values, rtol=0, atol=1e-9, equal_nan=True):
                raise ValueError(f"{recording}: {column} violates past-only per-recording feature definition")
    return {"status": "passed", "order": "input capture order; (t-0.1,t] through current row only"}


def duplicate_diagnostics(df, partitions, byte_bin=4):
    """Hash CAN tuples, excluding labels/metadata. Repetition is evidence to review."""
    if not isinstance(byte_bin, int) or not 1 <= byte_bin <= 256:
        raise ValueError("byte_bin must be an integer in 1..256")
    exact = pd.util.hash_pandas_object(df[["timestamp", *PAYLOAD]], index=False).to_numpy()
    content = df[PAYLOAD].copy()
    payload_hash = pd.util.hash_pandas_object(content, index=False).to_numpy()
    content[BYTES] = np.floor(content[BYTES] / byte_bin)
    near = pd.util.hash_pandas_object(content, index=False).to_numpy()
    result = {"method": f"64-bit hashes: exact capture tuple; exact CAN content; same ID/DLC and byte bins of width {byte_bin}. "
                        "Binned matches are a limited near-duplicate proxy, not a distance search. Hash collisions are possible.",
              "pairs": {}}
    for left, right in itertools.combinations(partitions, 2):
        a, b = partitions[left], partitions[right]
        result["pairs"][f"{left}/{right}"] = {
            name: {f"{right}_matching_rows": int(np.isin(h[b], h[a]).sum()),
                   f"{left}_matching_rows": int(np.isin(h[a], h[b]).sum())}
            for name, h in [("exact_capture", exact), ("exact_content", payload_hash), ("binned_content", near)]}
    return result


def audit_fold(df, partitions, byte_bin=4, fail_on_duplicates=False):
    partitions = check_partitions(df, partitions)
    duplicates = duplicate_diagnostics(df, partitions, byte_bin)
    if fail_on_duplicates and any(
            any(count for count in match.values())
            for pair in duplicates["pairs"].values() for match in pair.values()):
        raise ValueError("Cross-partition duplicate signatures found; inspect with non-strict audit")
    groups = {part: {"rows": len(rows), "recordings": int(df.iloc[rows].recording_id.nunique()),
                     "vehicles": sorted(df.iloc[rows].vehicle.unique()),
                     "class_counts": {str(k): int(v) for k, v in df.iloc[rows].label_bin.value_counts().items()}}
              for part, rows in partitions.items()}
    return {"partitions": groups, "duplicates": duplicates,
            "session_check": "checked" if "session_id" in df else "unavailable: independent acquisition session_id not provided",
            "preprocessing_fit": "unverified unless a fit receipt is supplied; current baseline uses no learned normalization"}
