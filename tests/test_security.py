import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

from security.__main__ import main
from security.analyzer import analyze
from security.baseline import id_rules, run_baseline
from security.checks import (audit_fold, check_fit_rows, check_partitions,
                             check_temporal_features, load_manifest)
from security.data import BYTES, feature_contract, load_features, sha256, validate_frames, write_json
from security.evaluation import align_predictions, binary_metrics, evaluate

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    rows = []
    for number in range(4):
        folder = "car_track_preliminary_train" if number < 2 else "car_track_final_2nd_release"
        filename = f"File_{number % 2}.csv"  # repeated names, different recording IDs
        for position, (time, can_id, label) in enumerate([(0., 0x100, 0), (.05, 0x100, 1), (.05, 0, 1), (.2, 0x200, 0)]):
            rows.append({"timestamp": time + (number % 2), "can_id_dec": can_id,
                         "dlc": 2, **{c: (position if i < 2 else np.nan) for i, c in enumerate(BYTES)},
                         "label_bin": label, "label": "T" if label else "R",
                         "vehicle": "Kia_Soul" if number % 2 == 0 else "Hyundai_Sonata",
                         "attack_type": "DoS" if number < 2 else "mixed/unknown",
                         "source_folder": folder, "source_file": filename,
                         "recording_id": f"{folder}/{filename}", "split": "train" if number < 2 else "test",
                         "round": "preliminary" if number < 2 else "final_2nd"})
    df = pd.DataFrame(rows)
    for _, group in df.groupby("recording_id"):
        t = group.timestamp.to_numpy()
        df.loc[group.index, "iat_bus"] = group.timestamp.diff()
        df.loc[group.index, "iat_id"] = group.groupby("can_id_dec").timestamp.diff()
        df.loc[group.index, "bus_count_100ms"] = np.arange(len(t)) - np.searchsorted(t, t - .1, side="right") + 1
    return df


def manifest_fixture(folder, df):
    path = folder / "features.parquet"
    df.to_parquet(path, index=False)
    np.save(folder / "train.npy", np.arange(8))
    np.save(folder / "test.npy", np.arange(8, 16))
    manifest = {"sha256": sha256(path), "rows": len(df), "target": "label_bin",
                "variants": {"standard": ["can_id_dec"]},
                "folds": [{"name": "official", "train": {"indices": "train.npy", "rows": 8},
                           "test": {"indices": "test.npy", "rows": 8}}]}
    manifest_path = folder / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    return path, manifest_path, manifest


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.df = fixture()
        self.partitions = {"train": np.arange(8), "test": np.arange(8, 16)}

    def test_canonical_contract_and_past_only_features(self):
        validate_frames(self.df)
        self.assertEqual(check_temporal_features(self.df)["status"], "passed")

    def test_inconsistent_frame_labels_rejected(self):
        self.df.loc[0, "label"] = "T"
        with self.assertRaisesRegex(ValueError, "disagree"):
            validate_frames(self.df)

    def test_invalid_frame_values_rejected(self):
        for column, value in [("label_bin", 2), ("can_id_dec", 2048), ("dlc", 9), ("byte_0", 256),
                              ("timestamp", np.inf), ("vehicle", ""), ("recording_id", "wrong")]:
            with self.subTest(column=column):
                df = self.df.copy()
                df.loc[0, column] = value
                with self.assertRaises(ValueError):
                    validate_frames(df)

    def test_dlc_missing_byte_consistency(self):
        self.df.loc[0, "byte_3"] = 0
        with self.assertRaisesRegex(ValueError, "DLC"):
            validate_frames(self.df)

    def test_mixed_recording_context_rejected(self):
        self.df.loc[0, "attack_type"] = "Replay"
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            validate_frames(self.df)

    def test_attack_free_context_cannot_contain_injected_frames(self):
        self.df["attack_type"] = "Normal"
        with self.assertRaisesRegex(ValueError, "Attack-free"):
            validate_frames(self.df)

    def test_optional_session_metadata_cannot_be_blank(self):
        self.df["session_id"] = ""
        with self.assertRaisesRegex(ValueError, "Missing session_id"):
            validate_frames(self.df)

    def test_feature_allowlist_blocks_metadata_and_indices(self):
        feature_contract(["can_id_dec", "iat_id"])
        for column in ["timestamp", "vehicle", "attack_type", "row_position", "index", "label_bin", "filename"]:
            with self.subTest(column=column), self.assertRaises(ValueError):
                feature_contract([column])

    def test_repeated_filename_does_not_imply_same_recording(self):
        self.assertTrue(set(self.df.iloc[:8].source_file) & set(self.df.iloc[8:].source_file))
        check_partitions(self.df, self.partitions)

    def test_random_frame_split_fails_recording_overlap(self):
        with self.assertRaisesRegex(ValueError, "recording_id overlap"):
            check_partitions(self.df, {"train": np.arange(0, 16, 2), "test": np.arange(1, 16, 2)})

    def test_validation_overlap_also_checked(self):
        with self.assertRaisesRegex(ValueError, "row overlap"):
            check_partitions(self.df, {**self.partitions, "validation": np.array([0])})

    def test_session_overlap_fails_even_if_recordings_differ(self):
        self.df["session_id"] = "same_acquisition"
        with self.assertRaisesRegex(ValueError, "session_id overlap"):
            check_partitions(self.df, self.partitions)

    def test_invalid_indices_fail(self):
        for indices in [np.array([0, 0]), np.array([16]), np.array([-1]), np.array([1.5]), np.array([], dtype=int)]:
            with self.subTest(indices=indices), self.assertRaises(ValueError):
                check_partitions(self.df, {**self.partitions, "train": indices})

    def test_duplicate_diagnostics_and_strict_failure(self):
        result = audit_fold(self.df, self.partitions)
        pair = result["duplicates"]["pairs"]["train/test"]
        self.assertEqual(pair["exact_capture"]["test_matching_rows"], 8)
        self.assertIn("unavailable", result["session_check"])
        with self.assertRaisesRegex(ValueError, "duplicate signatures"):
            audit_fold(self.df, self.partitions, fail_on_duplicates=True)

    def test_binned_near_duplicate_is_distinct_from_exact(self):
        self.df.loc[8:, "timestamp"] += 10
        self.df.loc[8:, "byte_0"] += 1
        pair = audit_fold(self.df, self.partitions)["duplicates"]["pairs"]["train/test"]
        self.assertEqual(pair["exact_capture"]["test_matching_rows"], 0)
        self.assertEqual(pair["exact_content"]["test_matching_rows"], 0)
        self.assertGreater(pair["binned_content"]["test_matching_rows"], 0)

    def test_preprocessing_fit_on_holdout_rejected(self):
        check_fit_rows(self.partitions, np.arange(4))
        with self.assertRaisesRegex(ValueError, "outside"):
            check_fit_rows(self.partitions, np.array([0, 8]))

    def test_future_window_frame_rejected(self):
        # Equal timestamps must not let the earlier row count the later row.
        self.df.loc[1, "bus_count_100ms"] += 1
        with self.assertRaisesRegex(ValueError, "past-only"):
            check_temporal_features(self.df)

    def test_future_or_cross_recording_iat_rejected(self):
        for column in ["iat_bus", "iat_id"]:
            df = self.df.copy()
            df.loc[0, column] = 0
            with self.subTest(column=column), self.assertRaisesRegex(ValueError, "past-only"):
                check_temporal_features(df)

    def test_timestamp_reordering_requires_review(self):
        self.df.loc[1, "timestamp"] = -.5
        with self.assertRaisesRegex(ValueError, "capture order"):
            check_temporal_features(self.df)


class EvaluationTests(unittest.TestCase):
    def test_confusion_and_metrics(self):
        metrics = binary_metrics([0, 0, 0, 1, 1], [0, 0, 1, 0, 1])
        self.assertEqual(metrics["confusion_matrix"], [[2, 1], [1, 1]])
        self.assertEqual(metrics["attack_precision"], .5)
        self.assertEqual(metrics["attack_recall"], .5)
        self.assertEqual(metrics["attack_f1"], .5)
        self.assertEqual(metrics["false_positive_rate"], 1 / 3)
        self.assertEqual(metrics["false_negative_rate"], .5)

    def test_absent_class_metrics_are_explicit(self):
        metrics = binary_metrics([0, 0], [0, 0])
        self.assertIsNone(metrics["attack_recall"])
        self.assertIsNone(metrics["attack_precision"])
        self.assertIsNone(metrics["attack_f1"])
        self.assertEqual(metrics["false_positive_rate"], 0)

    def test_invalid_predictions_fail(self):
        for truth, predicted in [([], []), ([1], [0, 1]), ([0], [.5]), ([2], [0]), ([1], [np.nan])]:
            with self.subTest(truth=truth), self.assertRaises(ValueError):
                binary_metrics(truth, predicted)

    def test_attack_context_includes_regular_false_positives(self):
        df = fixture()
        result = evaluate(df, np.ones(len(df), dtype=int))
        self.assertEqual(result["groups"]["attack_type"]["DoS"]["false_positive_rate"], 1)
        self.assertIn("mixed/unknown", result["groups"]["attack_type"])

    def test_prediction_alignment_not_csv_row_order(self):
        df = fixture()
        rows = np.array([8, 9, 10, 11])
        exported = pd.DataFrame({"row_position": rows, "label_bin": df.iloc[rows].label_bin, "y_pred": [0, 1, 1, 0]})
        np.testing.assert_array_equal(align_predictions(df, rows, exported.iloc[::-1]), [0, 1, 1, 0])

    def test_mismatched_prediction_truth_rows_and_duplicates_fail(self):
        df = fixture()
        exported = pd.DataFrame({"row_position": [8, 9], "label_bin": [0, 1], "y_pred": [0, 1]})
        for column, values in [("label_bin", [1, 1]), ("row_position", [8, 8]), ("row_position", [8, 10])]:
            bad = exported.copy()
            bad[column] = values
            with self.subTest(column=column), self.assertRaises(ValueError):
                align_predictions(df, np.array([8, 9]), bad)


class AnalysisAndBaselineTests(unittest.TestCase):
    def test_analyzer_rounds_id_overlap_and_payload_counts(self):
        result = analyze(fixture())
        self.assertEqual(len(result["recordings"]), 4)
        self.assertEqual(result["coverage"]["round"], {"final_2nd": 8, "preliminary": 8})
        recording = result["recordings"][0]
        self.assertEqual(recording["ids_in_both_classes"], ["0100"])
        self.assertEqual(recording["injected_frames_reusing_regular_id"], 1)
        self.assertEqual(recording["by_label"]["0"]["dlc"], {"2": 2})
        self.assertEqual(recording["by_label"]["0"]["bytes"]["byte_7"]["distribution"]["missing"], 2)
        self.assertIn("bytes", result["aggregates"]["vehicle"][0]["by_label"]["0"])
        json.dumps(result, allow_nan=False)

    def test_id_rules_train_only_and_no_metadata_inputs(self):
        train = pd.DataFrame({"can_id_dec": [0x100, 0x100, 0], "label_bin": [0, 0, 1]})
        test = pd.DataFrame({"can_id_dec": [0x100, 0, 0x321]})
        result = id_rules(train, test)
        np.testing.assert_array_equal(result["zero_id"], [0, 1, 0])
        np.testing.assert_array_equal(result["unseen_regular_id"], [0, 1, 1])
        np.testing.assert_array_equal(result["id_majority"], [0, 1, 0])

    def test_baseline_refuses_leaky_folds(self):
        with self.assertRaisesRegex(ValueError, "recording_id overlap"):
            run_baseline(fixture(), [("bad", {"train": np.array([0]), "test": np.array([1])})])

    def test_analyzer_all_missing_timing_is_json_safe(self):
        df = fixture().iloc[[0]].copy()
        df["iat_id"] = np.nan
        json.dumps(analyze(df), allow_nan=False)


class ArtifactTests(unittest.TestCase):
    def test_manifest_binding_and_mutation_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            df = fixture()
            path, manifest_path, manifest = manifest_fixture(folder, df)
            _, folds = load_manifest(manifest_path, path, df)
            self.assertEqual(folds[0][0], "official")
            manifest["sha256"] = "bad"
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "hash/row count"):
                load_manifest(manifest_path, path, df)

    def test_manifest_feature_and_path_checks(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            df = fixture()
            path, manifest_path, manifest = manifest_fixture(folder, df)
            manifest["variants"]["bad"] = ["timestamp"]
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "Unsafe"):
                load_manifest(manifest_path, path, df)
            del manifest["variants"]["bad"]
            manifest["folds"][0]["train"]["indices"] = "../outside.npy"
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "inside"):
                load_manifest(manifest_path, path, df)

    def test_round_derivation_and_conflict(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "frames.parquet"
            df = fixture().drop(columns="round")
            df.to_parquet(path)
            self.assertEqual(set(load_features(path)["round"]), {"preliminary", "final_2nd"})
            df["round"] = "preliminary"
            df.to_parquet(path)
            with self.assertRaisesRegex(ValueError, "round disagrees"):
                load_features(path)

    def test_outputs_never_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "result.json"
            write_json(path, {"original": True})
            with self.assertRaises(FileExistsError):
                write_json(path, {"original": False})
            self.assertEqual(json.loads(path.read_text()), {"original": True})

    def test_all_cli_commands_and_prediction_binding(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            path, manifest, _ = manifest_fixture(folder, fixture())
            common = ["--input", str(path), "--manifest", str(manifest)]
            self.assertEqual(main(["analyze", "--input", str(path), "--output", str(folder / "analysis.json")]), 0)
            self.assertEqual(main(["audit", *common, "--output", str(folder / "audit.json")]), 0)
            self.assertEqual(main(["baseline", *common, "--output-dir", str(folder / "baseline")]), 0)
            report = json.loads((folder / "baseline/report.json").read_text())
            self.assertEqual(set(report["provenance"]["partition_positions_sha256"]["official"]), {"train", "test"})
            export = folder / "baseline" / report["prediction_exports"][0]["file"]
            output = folder / "evaluation.json"
            self.assertEqual(main(["evaluate", *common, "--fold", "official", "--predictions", str(export), "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text())["overall"], report["folds"]["official"]["zero_id"]["overall"])
            predictions = pd.read_csv(export)
            predictions["input_sha256"] = "wrong"
            predictions.to_csv(folder / "wrong.csv", index=False)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                main(["evaluate", *common, "--fold", "official", "--predictions", str(folder / "wrong.csv"), "--output", str(folder / "bad.json")])
            self.assertEqual(caught.exception.code, 2)


class ExistingPipelineIntegrationTests(unittest.TestCase):
    def test_existing_parsers_features_split_generators_and_ai_baseline(self):
        """Run teammates' unmodified entry points against tiny synthetic raw files."""
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            for script in ["prepare_data.py", "prepare_kia_soul.py", "build_features.py"]:
                shutil.copy(ROOT / script, folder / script)
            recordings = [
                ("preliminary_train", "Attack_free_KIA_Soul_train.csv", 4),
                ("preliminary_train", "Flooding_KIA_Soul_train.csv", 5),
                ("preliminary_train", "Fuzzy_KIA_Soul_train.csv", 6),
                ("preliminary_train", "Malfunction_KIA_Soul_train.csv", 5),
                ("preliminary_train", "Attack_free_CHEVROLET_Spark_train.csv", 4),
                ("preliminary_train", "Attack_free_HYUNDAI_Sonata_train.csv", 4),
                ("final_1st_train", "Attack_free_KIA_Soul_train.csv", 4),
                ("final_1st_train", "Malfunction_1st_dataset_KIA_Soul_train.csv", 5),
                ("final_2nd_train", "Replay_dataset_KIA_Soul_train.csv", 5),
                ("preliminary_release", "File_1.csv", 6),
            ]
            for round_name, name, width in recordings:
                directory = folder / f"car_track_{round_name}"
                directory.mkdir(exist_ok=True)
                lines = []
                for i in range(12):
                    label = "R" if width == 4 or i % 3 else "T"
                    can_id = "0000" if "Flooding" in name and label == "T" else ("100" if i % 2 else "200")
                    row = [str(i * .01), can_id, "2", "01 02"]
                    if width > 4:
                        row += [label]
                    if width == 6:
                        row.insert(0, str(i))
                    lines.append(",".join(row))
                (directory / name).write_text("\n".join(lines) + "\n")

            def run(script, *args):
                result = subprocess.run([sys.executable, str(script), *map(str, args)], cwd=folder,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            run(folder / "prepare_data.py")
            run(folder / "build_features.py")
            full = load_features(folder / "features_all.parquet")
            self.assertEqual(len(full), 120)
            self.assertEqual(full.recording_id.nunique(), 10)
            check_temporal_features(full)
            run(folder / "prepare_kia_soul.py")
            run(folder / "build_features.py", "--input", "kia_soul_dataset.csv", "--prefix", "kia_soul_features")
            kia_path = folder / "kia_soul_features_all.parquet"
            kia = load_features(kia_path)
            run(ROOT / "splits/make_kia_splits.py", "--input", kia_path, "--output-dir", folder / "kia_splits")
            _, kia_folds = load_manifest(folder / "kia_splits/manifest.json", kia_path, kia)
            self.assertEqual(len(kia_folds), 5)
            run_baseline(kia, kia_folds)
            train_path = folder / "features_train.parquet"
            run(ROOT / "splits/make_splits.py", "--input", train_path, "--output-dir", folder / "vehicle_splits")
            _, vehicle_folds = load_manifest(folder / "vehicle_splits/manifest.json", train_path, load_features(train_path))
            self.assertEqual(len(vehicle_folds), 3)
            run(ROOT / "experiments/shortcut_baseline.py", "--input", train_path,
                "--output", folder / "ai_baseline.md", "--folds", "2", "--max-depth", "2")
            self.assertIn("pooled out-of-fold", (folder / "ai_baseline.md").read_text())


if __name__ == "__main__":
    unittest.main()
