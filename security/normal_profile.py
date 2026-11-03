"""F00 descriptive profiling of canonical, attack-free Kia Soul frames.

Run with python -m security.normal_profile --help. No models or CAN interfaces.
"""
import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd

from .data import BYTES, load_features, sha256, validate_frames, write_json

ROOT = Path(__file__).resolve().parents[1]
RECORDINGS = (
    "car_track_preliminary_train/Attack_free_KIA_Soul_train.csv",
    "car_track_final_1st_train/Attack_free_KIA_Soul_train.csv",
)


def compact(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def ratio(a, b, scale=1):
    return float(a / b * scale) if b else None


def candidate_modes(intervals, median, config):
    """Coarse smoothed histogram peaks, not fitted mixture components."""
    if len(intervals) < 32 or not median:
        return []
    width = median * config["mode_bin_fraction"]
    # Only characterize the central +/-50%; tails are reported separately.
    edges = np.arange(median * .5, median * 1.5 + width / 2, width)
    counts, edges = np.histogram(intervals, bins=edges)
    smooth = np.convolve(counts, [1 / 4, 1 / 2, 1 / 4], mode="same")
    candidates = [i for i in range(1, len(counts) - 1)
                  if smooth[i] > smooth[i - 1] and smooth[i] >= smooth[i + 1]
                  and counts[max(0, i - 1):i + 2].sum() >= len(intervals) * config["mode_min_fraction"]]
    selected = []
    for i in sorted(candidates, key=lambda i: (-smooth[i], i)):
        center = (edges[i] + edges[i + 1]) / 2
        if all(abs(center - other) >= median * config["mode_min_separation_fraction"] for other in selected):
            selected.append(float(center))
    return sorted(selected)


def timing_profile(timestamps, config):
    time = np.asarray(timestamps, dtype=float)
    if not np.isfinite(time).all():
        raise ValueError("Nonfinite timestamps: repair upstream; no intervals imputed")
    intervals = np.diff(time) * 1000
    positive = intervals[intervals > 0]
    result = {"interval_count": len(intervals), "positive_interval_count": len(positive),
              "zero_interval_count": int((intervals == 0).sum()),
              "negative_interval_count": int((intervals < 0).sum())}
    for name in ["mean", "median", "std", "min", "max", "p5", "p25", "p75", "p95"]:
        result[f"interval_{name}_ms"] = None
    result.update(interval_cv=None, nominal_period_ms=None, timing_group="unclassified",
                  short_interval_count=0, long_interval_count=0, possible_missing_cycle_intervals=0,
                  possible_missing_cycles=0, candidate_modes_ms="[]", nominal_band_fraction=None)
    if not len(positive):
        return result
    median, mean = float(np.median(positive)), float(positive.mean())
    std = float(positive.std(ddof=1)) if len(positive) > 1 else None
    result.update(interval_mean_ms=mean, interval_median_ms=median, interval_std_ms=std,
                  interval_min_ms=float(positive.min()), interval_max_ms=float(positive.max()),
                  interval_cv=ratio(std, mean) if std is not None else None)
    for p in [5, 25, 75, 95]:
        result[f"interval_p{p}_ms"] = float(np.percentile(positive, p))
    period = min(config["periods_ms"], key=lambda v: abs(v - median))
    band = float((np.abs(positive - period) <= period * config["period_interval_tolerance"]).mean())
    result["nominal_band_fraction"] = band
    if abs(median - period) <= period * config["period_median_tolerance"] and band >= config["period_required_fraction"]:
        result.update(nominal_period_ms=period, timing_group=f"near_{1000 / period:g}Hz")
    result["short_interval_count"] = int((positive < median * config["short_interval_ratio"]).sum())
    result["long_interval_count"] = int((positive > median * config["long_interval_ratio"]).sum())
    cycles = np.rint(positive / median).astype(int)
    plausible = (cycles >= 2) & (np.abs(positive / median - cycles) <= config["cycle_tolerance"])
    result["possible_missing_cycle_intervals"] = int(plausible.sum())
    result["possible_missing_cycles"] = int((cycles[plausible] - 1).sum())
    result["candidate_modes_ms"] = compact(candidate_modes(positive, median, config))
    return result


def payloads(group):
    values = group[BYTES].to_numpy()
    return [tuple(int(v) for v in row[:int(dlc)]) for row, dlc in zip(values, group.dlc)]


def payload_profile(group, recording, can_id, config):
    values = group[BYTES].to_numpy(dtype=float)
    present = np.isfinite(values)
    # Padding here is ONLY for vector arithmetic. Every result is masked by presence.
    numeric = np.nan_to_num(values, nan=0).astype(np.uint8)
    comparable = present[1:] & present[:-1]
    xor = np.bitwise_xor(numeric[1:], numeric[:-1])
    bits = np.unpackbits(xor[:, :, None], axis=2, bitorder="little")
    bit_flips = (bits * comparable[:, :, None]).sum(axis=(1, 2))
    compared_bits = comparable.sum(axis=1) * 8
    valid = compared_bits > 0
    content = payloads(group)
    frequencies = Counter(content)
    repeated = sum(a == b for a, b in zip(content, content[1:]))
    top = sorted(frequencies.items(), key=lambda pair: (-pair[1], pair[0]))[:5]
    result = {"unique_payloads": len(frequencies),
              "repeated_payload_percent": (len(group) - len(frequencies)) / len(group) * 100,
              "consecutive_repeat_count": repeated,
              "consecutive_repeat_percent": ratio(repeated, len(group) - 1, 100),
              "top_payloads": compact([{"payload": bytes(p).hex(" ").upper(), "count": n} for p, n in top]),
              "dlc_change_count": int((group.dlc.diff().dropna() != 0).sum()),
              "hamming_comparable_pairs": int(valid.sum()),
              "hamming_mean_bits": float(bit_flips[valid].mean()) if valid.any() else None,
              "hamming_max_bits": int(bit_flips[valid].max()) if valid.any() else None,
              "hamming_p95_bits": float(np.percentile(bit_flips[valid], 95)) if valid.any() else None,
              "hamming_mean_changed_bit_fraction": float((bit_flips[valid] / compared_bits[valid]).mean()) if valid.any() else None}
    byte_rows, hist_rows, hypotheses = [], [], []
    for i in range(8):
        observed = numeric[present[:, i], i]
        mask = comparable[:, i]
        previous, current = numeric[:-1, i][mask], numeric[1:, i][mask]
        counts = Counter(int(v) for v in observed)
        row = {"recording_id": recording, "can_id_hex": can_id, "byte_position": i,
               "present_frames": len(observed), "absent_frames": int((~present[:, i]).sum()),
               "unique_values": len(counts), "comparable_pairs": int(mask.sum()),
               "change_count": int((previous != current).sum()),
               "change_fraction": ratio(int((previous != current).sum()), int(mask.sum())),
               "variability": "absent" if not len(counts) else "stable" if len(counts) == 1 else "variable"}
        for bit in range(8):
            row[f"bit_{bit}_change_count"] = int(bits[mask, i, bit].sum())
            row[f"bit_{bit}_change_fraction"] = ratio(row[f"bit_{bit}_change_count"], int(mask.sum()))
        byte_rows.append(row)
        hist_rows.extend({"recording_id": recording, "can_id_hex": can_id, "byte_position": i,
                          "value_hex": f"{v:02X}", "value_dec": v, "frame_count": n,
                          "present_frame_fraction": n / len(observed)} for v, n in sorted(counts.items()))
        fields = [
                ("byte", previous.astype(int), current.astype(int), 256),
                ("low_nibble", previous.astype(int) & 15, current.astype(int) & 15, 16),
                ("high_nibble", previous.astype(int) >> 4, current.astype(int) >> 4, 16)]
        # A counter can omit the field's highest encodable values (e.g. 0..14).
        # Only test a smaller modulus if the observed states are exactly 0..k.
        for name, before, after, modulus in list(fields):
            states = set(np.concatenate([before, after]).tolist())
            if states and 3 <= max(states) < modulus - 1 and states == set(range(max(states) + 1)):
                fields.append((name + "_observed_range", before, after, max(states) + 1))
        for name, before, after, modulus in fields:
            if len(before) < config["pattern_min_pairs"] or len(np.unique(after)) < 4:
                continue
            step, support = Counter(((after - before) % modulus).tolist()).most_common(1)[0]
            if step and support / len(before) >= config["pattern_required_fraction"]:
                hypotheses.append({"kind": "counter_like", "byte": i, "field": name, "modulus": modulus,
                                   "step": step, "pairs": len(before), "support_fraction": support / len(before)})
    # Simple whole-byte checksum relationships only; no algorithm identification.
    if group.dlc.nunique() == 1 and group.dlc.iloc[0] >= 2 and len(frequencies) >= 16:
        width = int(group.dlc.iloc[0])
        for name, check in [("sum_all_bytes_mod_256", numeric[:, :width].sum(axis=1) % 256),
                            ("xor_all_bytes", np.bitwise_xor.reduce(numeric[:, :width], axis=1))]:
            constant, support = Counter(check.tolist()).most_common(1)[0]
            if support >= config["pattern_min_pairs"] and support / len(group) >= config["pattern_required_fraction"]:
                hypotheses.append({"kind": "checksum_like_conservation", "operation": name,
                                   "constant": int(constant), "support_fraction": support / len(group),
                                   "warning": "May reflect redundant fields or constrained payloads, not a checksum"})
    result["pattern_hypotheses"] = compact(hypotheses)
    return result, byte_rows, hist_rows


def profile_frames(df, config):
    validate_frames(df)
    if not df.vehicle.eq("Kia_Soul").all() or not df.attack_type.eq("Normal").all() or df.label_bin.any():
        raise ValueError("F00 accepts only Kia Soul attack-free frames")
    rows, byte_rows, hist_rows, recordings, examples = [], [], [], [], []
    containing = df.groupby("can_id_dec").recording_id.nunique()
    for recording, frames in df.groupby("recording_id", sort=True):
        times = frames.timestamp.to_numpy()
        duration = float(times.max() - times.min())
        recordings.append({"recording_id": recording, "frames": len(frames),
                           "unique_ids": int(frames.can_id_dec.nunique()), "first_timestamp": float(times[0]),
                           "last_timestamp": float(times[-1]), "duration_s": duration,
                           "nonpositive_timestamp_count": int((times <= 0).sum()),
                           "backward_bus_timestamp_count": int((np.diff(times) < 0).sum()),
                           "zero_bus_interval_count": int((np.diff(times) == 0).sum())})
        for can_id, group in frames.groupby("can_id_dec", sort=True):
            name = f"0x{can_id:03X}"
            span = float(group.timestamp.max() - group.timestamp.min())
            row = {"recording_id": recording, "can_id_hex": name, "can_id_dec": int(can_id),
                   "frame_count": len(group), "traffic_percent": len(group) / len(frames) * 100,
                   "dlc_counts": compact({str(k): int(v) for k, v in group.dlc.value_counts().sort_index().items()}),
                   "first_timestamp": float(group.timestamp.iloc[0]), "last_timestamp": float(group.timestamp.iloc[-1]),
                   "id_observation_duration_s": span, "recording_duration_s": duration,
                   "rate_recording_fps": ratio(len(group), duration),
                   "rate_id_span_fps": ratio(len(group) - 1, span) if len(group) > 1 else None,
                   "recordings_containing_id": int(containing[can_id]), **timing_profile(group.timestamp, config)}
            payload, bytes_, hist = payload_profile(group, recording, name, config)
            row.update(payload)
            rows.append(row); byte_rows.extend(bytes_); hist_rows.extend(hist)
            if can_id in config["important_ids"]:
                for order, (position, frame) in enumerate(group.head(config["example_messages"]).iterrows()):
                    data = tuple(int(frame[b]) for b in BYTES[:int(frame.dlc)])
                    examples.append({"recording_id": recording, "can_id_hex": name, "sequence_index": order,
                                     "canonical_row_position": int(position), "timestamp": float(frame.timestamp),
                                     "dlc": int(frame.dlc), "payload": bytes(data).hex(" ").upper()})
    return {"ids": pd.DataFrame(rows), "bytes": pd.DataFrame(byte_rows), "histograms": pd.DataFrame(hist_rows),
            "recordings": recordings, "examples": pd.DataFrame(examples)}


def compare_recordings(df, profile, config):
    groups = {name: group for name, group in df.groupby("recording_id", sort=True)}
    if len(groups) != 2:
        raise ValueError("F00 comparison needs exactly two recordings")
    preliminary = RECORDINGS[0]
    final = RECORDINGS[1]
    if set(groups) != {preliminary, final}:
        raise ValueError("Recording identities differ from the two configured Kia sources")
    a, b = groups[preliminary], groups[final]
    indexed = profile["ids"].set_index(["recording_id", "can_id_dec"])
    comparisons = []
    for cid in sorted(set(a.can_id_dec) | set(b.can_id_dec)):
        row = {"can_id_hex": f"0x{cid:03X}", "can_id_dec": int(cid)}
        parts = [group.loc[group.can_id_dec.eq(cid)] for group in (a, b)]
        contents = [set(payloads(part)) for part in parts]
        row.update(shared_unique_payloads=len(contents[0] & contents[1]),
                   payload_set_jaccard=ratio(len(contents[0] & contents[1]), len(contents[0] | contents[1])))
        for name, recording, part, other in zip(["preliminary", "final_1st"], [preliminary, final], parts, contents[::-1]):
            row[f"{name}_present"] = not part.empty
            if part.empty:
                continue
            p = indexed.loc[(recording, cid)]
            for key in ["frame_count", "dlc_counts", "rate_recording_fps", "interval_mean_ms", "interval_std_ms",
                        "interval_min_ms", "interval_p5_ms", "interval_p25_ms", "interval_median_ms",
                        "interval_p75_ms", "interval_p95_ms", "interval_max_ms", "interval_cv", "unique_payloads", "repeated_payload_percent",
                        "consecutive_repeat_percent", "hamming_mean_bits", "timing_group"]:
                row[f"{name}_{key}"] = p[key]
            row[f"{name}_shared_content_frame_percent"] = sum(p in other for p in payloads(part)) / len(part) * 100
        if all(not part.empty for part in parts):
            row["rate_change_percent"] = (row["final_1st_rate_recording_fps"] / row["preliminary_rate_recording_fps"] - 1) * 100
            row["median_interval_change_percent"] = ratio(
                row["final_1st_interval_median_ms"] - row["preliminary_interval_median_ms"], row["preliminary_interval_median_ms"], 100)
            row["dlc_values_match"] = set(parts[0].dlc) == set(parts[1].dlc)
            row["unique_payload_fraction_change_pp"] = (
                row["preliminary_repeated_payload_percent"] - row["final_1st_repeated_payload_percent"])
        comparisons.append(row)
    # Compare complete tuples, not just 64-bit hashes; missing bytes use a private sentinel.
    def tuples(group, include_time):
        prefix = group[["timestamp", "can_id_dec"]].to_numpy() if include_time else group[["can_id_dec"]].to_numpy()
        return [tuple(p) + (int(dlc),) + data for p, dlc, data in zip(prefix, group.dlc, payloads(group))]
    exact_a, exact_b = set(tuples(a, True)), set(tuples(b, True))
    def sequence_hashes(group):
        tokens = [int(cid).to_bytes(2, "big") + bytes([int(dlc)]) + bytes(data)
                  for cid, dlc, data in zip(group.can_id_dec, group.dlc, payloads(group))]
        width = config["sequence_window_frames"]
        for i in range(len(tokens) - width + 1):
            yield hashlib.sha256(b"".join(tokens[i:i + width])).digest()
    window_a = set(sequence_hashes(a))
    windows_b = list(sequence_hashes(b))
    evidence = {"exact_capture_tuple_intersection": len(exact_a & exact_b),
                "timestamp_range_overlap_s": max(0., float(min(a.timestamp.max(), b.timestamp.max()) - max(a.timestamp.min(), b.timestamp.min()))),
                "gap_between_ranges_s": float(b.timestamp.min() - a.timestamp.max()),
                "sequence_window_frames": config["sequence_window_frames"],
                "shared_unique_content_sequence_hashes": len(window_a & set(windows_b)),
                "final_windows_matching_preliminary": sum(value in window_a for value in windows_b),
                "sequence_test": "SHA-256 of ordered ID/DLC/payload windows; timestamps excluded; theoretical hash collision possible",
                "session_independence": "Unconfirmed: no independent acquisition-session metadata. Non-overlap does not prove independence."}
    return pd.DataFrame(comparisons), evidence


def canonical_inputs(data_root, config, scratch):
    """Reuse unmodified Data scripts on only two symlinked recordings."""
    if tuple(config["recordings"]) != RECORDINGS:
        raise ValueError("F00 config must select exactly the preliminary and final-first-round attack-free Kia files")
    root = Path(data_root).resolve()
    sources = [(relative, (root / relative).resolve()) for relative in RECORDINGS]
    if any(not path.is_relative_to(root) or not path.is_file() for _, path in sources):
        raise ValueError("Selected recordings must exist inside data-root")
    before = {relative: sha256(path) for relative, path in sources}
    script_hashes = {name: sha256(ROOT / name) for name in ["prepare_data.py", "build_features.py"]}
    with tempfile.TemporaryDirectory(prefix="canonical-", dir=scratch) as temp:
        work = Path(temp)
        for relative, source in sources:
            target = work / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(source)
        for name in script_hashes:
            shutil.copyfile(ROOT / name, work / name)
            result = subprocess.run([sys.executable, str(work / name)], cwd=work, capture_output=True, text=True)
            if result.returncode:
                raise ValueError(f"Existing {name} failed: {result.stdout}\n{result.stderr}")
        df = load_features(work / "features_all.parquet")
    if set(df.recording_id) != set(RECORDINGS):
        raise ValueError("Canonical data contains unexpected recording identities")
    after = {relative: sha256(path) for relative, path in sources}
    if before != after:
        raise ValueError("Raw source changed during canonical conversion")
    return df, {"raw_sha256": before, "data_script_sha256": script_hashes}


def run(config_path, data_root, output_dir):
    config = json.loads(Path(config_path).read_text())
    output = Path(output_dir)
    if output.exists():
        raise ValueError(f"Output already exists: {output}; choose a new directory")
    output.mkdir(parents=True)
    df, provenance = canonical_inputs(data_root, config, output)
    profile = profile_frames(df, config)
    comparison, overlap = compare_recordings(df, profile, config)
    for folder in ["results", "plots"]:
        (output / folder).mkdir()
    tables = {"kia_normal_id_profile.csv": profile["ids"], "kia_normal_recording_comparison.csv": comparison,
              "kia_normal_byte_profile.csv": profile["bytes"], "kia_normal_byte_values.csv": profile["histograms"],
              "kia_normal_message_examples.csv": profile["examples"]}
    for name, table in tables.items():
        table.to_csv(output / "results" / name, index=False, float_format="%.9f", lineterminator="\n")
    provenance.update(config_sha256=sha256(config_path),
                      git_revision=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                      source_sha256={name: sha256(Path(__file__).with_name(name)) for name in ["normal_profile.py", "normal_plots.py", "data.py"]},
                      dependencies={name: importlib.metadata.version(name) for name in ["numpy", "pandas", "pyarrow", "matplotlib"]},
                      python=sys.version.split()[0])
    # A second integrity check covers the entire profiling run, not just ingestion.
    if provenance["raw_sha256"] != {relative: sha256(Path(data_root) / relative) for relative in RECORDINGS}:
        raise ValueError("Raw source changed during profiling")
    write_json(output / "results" / "kia_normal_summary.json", {
        "provenance": provenance, "recordings": profile["recordings"], "recording_comparison": overlap,
        "source_integrity": "Both selected raw SHA-256 digests unchanged before/after ingestion and profiling"})
    from .normal_plots import make_plots
    make_plots(df, profile, comparison, output / "plots", config)
    print(f"Profiled {len(df):,} frames from {df.recording_id.nunique()} recordings; outputs: {output}")


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--config", type=Path, required=True)
    cli.add_argument("--data-root", type=Path, required=True)
    cli.add_argument("--output-dir", type=Path, required=True, help="New directory; refuses overwrite")
    args = cli.parse_args()
    try:
        run(args.config, args.data_root, args.output_dir)
    except (ValueError, OSError, KeyError) as error:
        cli.exit(2, f"F00: {error}\n")


if __name__ == "__main__":
    main()
