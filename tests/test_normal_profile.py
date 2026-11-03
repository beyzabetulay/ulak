"""F00 tests: synthetic edge cases, selected-input reuse, reproducibility."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from security.data import BYTES, sha256
from security.normal_profile import (RECORDINGS, canonical_inputs, compare_recordings,
                                     payload_profile, profile_frames, run, timing_profile)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "experiments/security/F00_normal_traffic/configs/f00.json"


def config():
    return json.loads(CONFIG.read_text())


def frames(records=None):
    records = records or [(0., 0x153, (1, 2)), (.01, 0x260, (3,)),
                          (.02, 0x153, (1, 3)), (.03, 0x260, (3,))]
    rows = []
    for number, recording in enumerate(RECORDINGS):
        folder, name = recording.split("/")
        for time, cid, data in records:
            rows.append({"recording_id": recording, "timestamp": time + 100 + number * 1000,
                         "can_id_dec": cid, "dlc": len(data),
                         **{b: data[i] if i < len(data) else np.nan for i, b in enumerate(BYTES)},
                         "label_bin": 0, "label": "R", "attack_type": "Normal", "vehicle": "Kia_Soul",
                         "source_folder": folder, "source_file": name, "split": "train"})
    return pd.DataFrame(rows)


class TimingProfileTests(unittest.TestCase):
    def test_recording_and_id_grouping_no_cross_boundary(self):
        output = profile_frames(frames(), config())["ids"]
        self.assertEqual(len(output), 4)
        self.assertTrue(output.interval_count.eq(1).all())
        np.testing.assert_allclose(output.interval_median_ms, 20)
        self.assertTrue(output.recordings_containing_id.eq(2).all())

    def test_zero_and_negative_intervals_flagged_not_imputed_or_sorted(self):
        result = timing_profile([10., 10.01, 10.01, 9.99, 10.02], config())
        self.assertEqual(result["interval_count"], 4)
        self.assertEqual(result["zero_interval_count"], 1)
        self.assertEqual(result["negative_interval_count"], 1)
        self.assertEqual(result["positive_interval_count"], 2)
        self.assertAlmostEqual(result["interval_mean_ms"], 20)
        self.assertAlmostEqual(result["interval_std_ms"], np.sqrt(200))

    def test_nonfinite_times_rejected(self):
        for value in [np.nan, np.inf, -np.inf]:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "Nonfinite"):
                timing_profile([0., value], config())

    def test_single_frame_and_zero_only_have_no_invented_period(self):
        for values in [[10.], [10., 10.]]:
            result = timing_profile(values, config())
            self.assertIsNone(result["interval_median_ms"])
            self.assertIsNone(result["interval_cv"])
            self.assertEqual(result["timing_group"], "unclassified")

    def test_periodic_category_requires_distribution_support(self):
        periodic = timing_profile(np.arange(100) * .01, config())
        self.assertEqual(periodic["timing_group"], "near_100Hz")
        irregular = timing_profile(np.cumsum([0., .001, .01, .1, .01, .2]), config())
        self.assertEqual(irregular["timing_group"], "unclassified")

    def test_possible_cycle_gaps_are_hypotheses(self):
        result = timing_profile([0., .01, .02, .04, .05], config())
        self.assertEqual(result["possible_missing_cycle_intervals"], 1)
        self.assertEqual(result["possible_missing_cycles"], 1)

    def test_histogram_modes_can_expose_two_supported_peaks(self):
        result = timing_profile(np.cumsum([0., *([.09, .11] * 100)]), config())
        self.assertGreaterEqual(len(json.loads(result["candidate_modes_ms"])), 2)

    def test_nonpositive_epoch_and_backwards_order_are_documented(self):
        table = frames([(0., 0x153, (1,)), (.01, 0x153, (1,)), (-.02, 0x153, (1,))])
        table.loc[table.recording_id.eq(RECORDINGS[0]), "timestamp"] -= 100
        result = profile_frames(table, config())
        first = next(r for r in result["recordings"] if r["recording_id"] == RECORDINGS[0])
        self.assertEqual(first["nonpositive_timestamp_count"], 2)
        self.assertEqual(first["backward_bus_timestamp_count"], 1)


class PayloadProfileTests(unittest.TestCase):
    def profile(self, records):
        group = frames(records).iloc[:len(records)]
        return payload_profile(group, RECORDINGS[0], "0x153", config())

    def test_variable_dlc_absent_bytes_never_zero_observations(self):
        result, byte, hist = self.profile([(0., 0x153, (0,)), (.01, 0x153, (1, 0xAA)), (.02, 0x153, (1,))])
        self.assertEqual(result["dlc_change_count"], 2)
        self.assertEqual(result["hamming_mean_bits"], .5)
        self.assertEqual(byte[1]["present_frames"], 1)
        self.assertEqual(byte[1]["comparable_pairs"], 0)
        self.assertIsNone(byte[1]["change_fraction"])
        self.assertEqual([r["value_dec"] for r in hist if r["byte_position"] == 1], [0xAA])
        self.assertEqual(byte[2]["variability"], "absent")

    def test_zero_dlc_has_no_comparable_bits(self):
        result, byte, _ = self.profile([(0., 0x153, ()), (.01, 0x153, ())])
        self.assertEqual(result["unique_payloads"], 1)
        self.assertIsNone(result["hamming_mean_bits"])
        self.assertTrue(all(r["present_frames"] == 0 for r in byte))

    def test_global_repetition_and_consecutive_repetition_differ(self):
        result, _, _ = self.profile([(0., 0x153, (1,)), (.01, 0x153, (2,)), (.02, 0x153, (1,))])
        self.assertAlmostEqual(result["repeated_payload_percent"], 100 / 3)
        self.assertEqual(result["consecutive_repeat_count"], 0)
        self.assertEqual(result["consecutive_repeat_percent"], 0)

    def test_bit_counts_and_hamming(self):
        result, byte, _ = self.profile([(0., 0x153, (0,)), (.01, 0x153, (0x81,))])
        self.assertEqual(result["hamming_mean_bits"], 2)
        self.assertEqual(byte[0]["bit_0_change_count"], 1)
        self.assertEqual(byte[0]["bit_7_change_count"], 1)
        self.assertEqual(byte[0]["bit_1_change_count"], 0)

    def test_counter_and_conservation_are_only_hypotheses(self):
        data = [(i / 100, 0x153, (i % 256, (-i) % 256)) for i in range(80)]
        result, _, _ = self.profile(data)
        hypotheses = json.loads(result["pattern_hypotheses"])
        self.assertTrue(any(r["kind"] == "counter_like" for r in hypotheses))
        self.assertTrue(any(r["kind"] == "checksum_like_conservation" for r in hypotheses))

    def test_missing_required_byte_rejected(self):
        table = frames()
        table.loc[0, "byte_0"] = np.nan
        with self.assertRaisesRegex(ValueError, "DLC"):
            profile_frames(table, config())

    def test_fifteen_state_cycle_can_be_a_counter_hypothesis(self):
        records = [(i / 100, 0x153, ((i % 15) << 4,)) for i in range(100)]
        result, _, _ = self.profile(records)
        hypotheses = json.loads(result["pattern_hypotheses"])
        self.assertTrue(any(r.get("field") == "high_nibble_observed_range" and r["modulus"] == 15
                            and r["support_fraction"] == 1 for r in hypotheses))

    def test_attack_or_other_vehicle_rejected(self):
        for column, value in [("vehicle", "unknown"), ("attack_type", "Replay")]:
            table = frames(); table[column] = value
            with self.subTest(column=column), self.assertRaisesRegex(ValueError, "attack-free"):
                profile_frames(table, config())


class ComparisonAndReproductionTests(unittest.TestCase):
    def test_same_content_does_not_prove_session_independence(self):
        table = frames(); settings = config(); settings["sequence_window_frames"] = 2
        output = profile_frames(table, settings)
        comparison, evidence = compare_recordings(table, output, settings)
        self.assertEqual(len(comparison), 2)
        self.assertEqual(evidence["exact_capture_tuple_intersection"], 0)
        self.assertGreater(evidence["shared_unique_content_sequence_hashes"], 0)
        self.assertIn("Unconfirmed", evidence["session_independence"])

    def test_absent_id_compared_without_fabricated_measurements(self):
        table = frames()
        table = table[~(table.recording_id.eq(RECORDINGS[1]) & table.can_id_dec.eq(0x260))]
        comp, _ = compare_recordings(table, profile_frames(table, config()), config())
        self.assertFalse(comp.set_index("can_id_dec").loc[0x260, "final_1st_present"])

    def test_source_selection_rejects_attack_or_traversal_paths(self):
        settings = config(); settings["recordings"][0] = "../Fuzzy_KIA_Soul_train.csv"
        with tempfile.TemporaryDirectory() as temp, self.assertRaisesRegex(ValueError, "exactly"):
            canonical_inputs(temp, settings, temp)

    def test_unmodified_data_scripts_source_integrity_and_reproducible_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for number, relative in enumerate(RECORDINGS):
                path = root / relative; path.parent.mkdir()
                rows = [f"{1000 + number * 100 + i * .01:.6f},153,2,{i % 256:02X} 00" + (",R" if number else "") for i in range(40)]
                path.write_text("\n".join(rows) + "\n")
            before = {name: sha256(root / name) for name in RECORDINGS}
            with contextlib.redirect_stdout(io.StringIO()):
                run(CONFIG, root, root / "run1")
                run(CONFIG, root, root / "run2")
            self.assertEqual(before, {name: sha256(root / name) for name in RECORDINGS})
            for first in sorted((root / "run1/results").iterdir()):
                self.assertEqual(first.read_bytes(), (root / "run2/results" / first.name).read_bytes(), first.name)
            for first in sorted((root / "run1/plots").glob("*.png")):
                self.assertEqual(first.read_bytes(), (root / "run2/plots" / first.name).read_bytes(), first.name)
            with self.assertRaisesRegex(ValueError, "already exists"):
                run(CONFIG, root, root / "run1")


if __name__ == "__main__":
    unittest.main()
