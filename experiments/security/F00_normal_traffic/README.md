# F00 — Kia Soul normal CAN traffic profiling

F00 establishes an observed reference for later security experiments. It
describes IDs, timing, raw payload changes, and differences between two normal
recordings. It does not train a model, analyze attacks, decode physical signals,
or repeat the previous diagnostic-protocol investigation.

Read the [findings and examples](reports/F00_Normal_Traffic_Profile.md) and the
[measurement definitions](reports/F00_Methodology.md). The report includes a
short German presentation text.

## Input requirements

The local dataset root must contain these **two exact relative paths**:

```text
car_track_preliminary_train/Attack_free_KIA_Soul_train.csv
car_track_final_1st_train/Attack_free_KIA_Soul_train.csv
```

The files have identical names, so filename-only selection is unsafe. Configure
them in [configs/f00.json](configs/f00.json); the runner enforces this selection.
Do not download or commit recordings as part of this experiment. The configured
local root in the example below is `In-Vehicle Network Intrusion Detection`.
Use a different `--data-root` if your authorized local copy is elsewhere.

## Exact reproduction

From the repository root, with Python 3.12+:

```sh
python3 -m venv /tmp/decan-f00-venv
/tmp/decan-f00-venv/bin/python -m pip install -r experiments/security/requirements.txt
/tmp/decan-f00-venv/bin/python -m unittest discover -v
/tmp/decan-f00-venv/bin/python -m security.normal_profile \
  --config experiments/security/F00_normal_traffic/configs/f00.json \
  --data-root 'In-Vehicle Network Intrusion Detection' \
  --output-dir experiments/security/F00_normal_traffic/local_outputs/reproduction
```

The output directory must not already exist. Choose another name for another
run; existing experiment outputs are never overwritten by the runner. Canonical
CSV/Parquet conversion occurs in a temporary subdirectory that is removed after
loading. The temporary workspace contains symlinks to only the two selected
recordings and unmodified copies of `prepare_data.py` and `build_features.py`.
This reuses the Data Engineer's parser and extraction logic without executing
their full dataset workflow or changing their source files.

The submitted measured run used code commit `e57b1da` (profiler implementation
in `4a23587`), Python 3.14.8, NumPy 2.5.4, pandas 3.1.0, PyArrow 26.0.0, and
Matplotlib 3.11.2. Source, configuration, and selected raw-file hashes are in
[the provenance summary](results/kia_normal_summary.json). This code revision
precedes the documentation/results commit, avoiding a circular commit reference.

To compare reproduced tables with the submitted measurements:

```sh
diff -u experiments/security/F00_normal_traffic/results/kia_normal_id_profile.csv \
  experiments/security/F00_normal_traffic/local_outputs/reproduction/results/kia_normal_id_profile.csv
diff -u experiments/security/F00_normal_traffic/results/kia_normal_recording_comparison.csv \
  experiments/security/F00_normal_traffic/local_outputs/reproduction/results/kia_normal_recording_comparison.csv
```

Numeric tables are deterministic for unchanged inputs/configuration/software.
The provenance JSON's Git revision changes if reproduction runs from a later
commit; plot bytes can change with plotting-library/font versions. The tests
check byte-identical tables, provenance, and PNGs in the same environment.

## Outputs

| Location | Contents |
|---|---|
| `configs/f00.json` | Selected relative paths, timing bands, exploratory thresholds, important IDs. |
| [ID profile](results/kia_normal_id_profile.csv) | 90 recording/ID rows: counts, DLC, timestamps, rates, timing statistics, repetition, Hamming distance, hypotheses. |
| [Recording comparison](results/kia_normal_recording_comparison.csv) | 45 IDs compared across recordings, including shared payloads and rate/timing differences. |
| [Byte profile](results/kia_normal_byte_profile.csv) | 720 recording/ID/byte rows, including absent positions and individual bit change counts/fractions. |
| [Byte values](results/kia_normal_byte_values.csv) | Observed per-byte value histograms, with present-byte denominators. |
| [Message examples](results/kia_normal_message_examples.csv) | Six consecutive same-ID messages for each of four important IDs in each recording; 48 rows. |
| [Summary](results/kia_normal_summary.json) | Recording counts, timestamp quality, overlap checks, source integrity, and provenance. |
| `plots/` | Six PNG figures: traffic shares, timing groups, interval histograms, byte changes, all-ID comparison, important-ID details. |
| `reports/` | Beginner-friendly findings and precise methodology. |
| `local_outputs/` | Ignored generated runs and Matplotlib caches; no raw data belongs in Git. |

These are descriptive measurements, not model features chosen for training.
Counts and output sizes are measured from the selected inputs rather than
hardcoded success criteria. Only small tables, six figures, and reports are
submitted. No canonical CSV/Parquet or full payload listing is committed.

## Key findings and boundaries

The run verifies 192,516 preliminary and 473,212 final-first-round frames, with
the same 45 IDs and matching per-ID DLC values. Timing is concentrated near
100, 50, 10, 5, and 1 Hz, but not equally precise for every ID. Normal payload
values and repetition rates can change substantially even when timing is stable.
No source hashes changed during processing.

No exact capture tuples or 16-frame content windows were shared. The timestamp
ranges do not overlap, but independent acquisition sessions cannot be confirmed.
No ECU ownership, physical signal meanings, verified checksum algorithms,
diagnostic services, attack detection performance, or driving-condition
generalization follows from these recordings.
