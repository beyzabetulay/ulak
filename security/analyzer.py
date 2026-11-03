"""Descriptive security statistics; label-assisted patterns are not evaluations."""
import itertools

import numpy as np
import pandas as pd

from .data import BYTES, PAYLOAD, TIMING, require_columns
from .evaluation import binary_metrics


def histogram(values):
    return {str(key): int(count) for key, count in values.value_counts(dropna=False).sort_index().items()}


def distribution(values):
    values = pd.Series(values)
    finite = values[np.isfinite(values)]
    return {"present": len(finite), "missing": int(values.isna().sum()),
            "min": float(finite.min()) if len(finite) else None,
            "median": float(finite.median()) if len(finite) else None,
            "p95": float(finite.quantile(0.95)) if len(finite) else None,
            "max": float(finite.max()) if len(finite) else None}


def id_name(value):
    return f"{int(value):04X}"


def summarize(group, detailed=False):
    regular = set(group.loc[group.label_bin.eq(0), "can_id_dec"])
    injected = set(group.loc[group.label_bin.eq(1), "can_id_dec"])
    shared = sorted(regular & injected)
    result = {"frames": len(group), "regular": int(group.label_bin.eq(0).sum()),
              "injected": int(group.label_bin.eq(1).sum()), "attack_fraction": float(group.label_bin.mean()),
              "recordings": int(group.recording_id.nunique()), "unique_ids": int(group.can_id_dec.nunique()),
              "unique_regular_ids": len(regular), "unique_injected_ids": len(injected),
              "ids_in_both_classes": [id_name(i) for i in shared],
              "injected_frames_reusing_regular_id": int((group.label_bin.eq(1) & group.can_id_dec.isin(regular)).sum()),
              "zero_id_rule_descriptive": binary_metrics(group.label_bin, group.can_id_dec.eq(0).astype(int)),
              "by_label": {}}
    for label, part in group.groupby("label_bin", sort=True):
        summary = {"frames": len(part),
                   "can_ids": {id_name(k): int(v) for k, v in part.can_id_dec.value_counts().sort_index().items()},
                   "dlc": histogram(part.dlc),
                   "timing": {column: distribution(part[column]) for column in TIMING}}
        summary["bytes"] = {column: {"distribution": distribution(part[column]),
                                     "histogram": histogram(part[column].dropna().astype(int))}
                            for column in BYTES}
        if detailed:
            content = part[PAYLOAD].fillna(-1).astype(int)
            counts = content.value_counts()
            summary["unique_can_payload_tuples"] = len(counts)
            summary["top_can_payload_tuples"] = [
                {"can_id": id_name(key[0]), "dlc": key[1],
                 "payload": [None if v == -1 else v for v in key[2:]], "frames": int(count)}
                for key, count in counts.head(10).items()]
        result["by_label"][str(int(label))] = summary
    if detailed:
        result["per_id_timing"] = {
            id_name(can_id): {str(int(label)): {"frames": len(part),
                                               "iat_id": distribution(part.iat_id),
                                               "iat_bus": distribution(part.iat_bus)}
                              for label, part in by_id.groupby("label_bin", sort=True)}
            for can_id, by_id in group.groupby("can_id_dec", sort=True)}
        times = group.timestamp.to_numpy()
        result["capture_order_timestamp_decreases"] = int((np.diff(times) < 0).sum())
        result["duration_seconds"] = float(group.timestamp.max() - group.timestamp.min())
        result["equal_adjacent_timestamps"] = int((np.diff(times) == 0).sum())
    return result


def analyze(df):
    require_columns(df, ["round", *TIMING])
    result = {"semantics": "Descriptive, label-assisted R/T analysis. ID overlap within a recording uses its labels; "
                           "this is not a held-out unseen-ID detector. attack_type is trace context. "
                           "Unknown release attack types/vehicles remain unknown; no payload is decoded as a physical signal.",
              "coverage": {column: histogram(df[column]) for column in ["vehicle", "attack_type", "round", "split"]},
              "recordings": [], "aggregates": {}}
    for recording, group in df.groupby("recording_id", sort=True):
        result["recordings"].append({"recording_id": recording,
                                     **{c: group[c].iloc[0] for c in ["vehicle", "attack_type", "round", "split"]},
                                     **summarize(group, detailed=True)})
    # Include joint groups: pooled marginals alone hide round/vehicle confounding.
    for columns in [["vehicle"], ["attack_type"], ["round"], ["vehicle", "round", "attack_type", "split"]]:
        name = "/".join(columns)
        entries = []
        for key, group in df.groupby(columns, sort=True):
            key = key if isinstance(key, tuple) else (key,)
            entries.append({**dict(zip(columns, key)), **summarize(group)})
        result["aggregates"][name] = entries
    fingerprints = {vehicle: set(group.loc[group.label_bin.eq(0), "can_id_dec"])
                    for vehicle, group in df.groupby("vehicle") if vehicle != "unknown"}
    result["regular_id_vehicle_overlap"] = {
        f"{a}/{b}": {"intersection": len(fingerprints[a] & fingerprints[b]),
                     "jaccard": len(fingerprints[a] & fingerprints[b]) / len(fingerprints[a] | fingerprints[b])
                     if fingerprints[a] | fingerprints[b] else None}
        for a, b in itertools.combinations(sorted(fingerprints), 2)}
    result["shortcut_review"] = [
        "Inspect zero-ID precision and recall, not just attack coverage, separately by round and vehicle.",
        "Compare injected IDs with regular IDs; within-trace overlap is descriptive and label-assisted.",
        "Evaluate unseen-regular-ID and train-fitted ID-majority rules with a recording-safe manifest using baseline.",
        "Compare regular and injected DLC, byte histograms, per-ID IAT, and bus rate within the same recording.",
        "CAN ID vocabulary may identify vehicle; vehicle-specific prevalence and round coverage can confound detection.",
        "Stationary recordings do not establish detection performance while driving.",
    ]
    return result
