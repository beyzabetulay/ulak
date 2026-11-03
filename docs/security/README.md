# Offline security tooling

This package consumes the Data Engineer's existing `build_features.py` Parquet
interface. It does not parse raw recordings, assign release vehicles, generate
replacement splits, or train replacement ML models. Run from the repository root.
All new code and test fixtures are local. No CAN interface is opened.

## Setup and input

Use `experiments/requirements.txt`; no new dependency is required. Python 3.12+
is supported by the existing project. Verification in this checkout used Python
3.14.8, NumPy 2.5.4, pandas 3.1.0, PyArrow 26.0.0 and scikit-learn 1.9.1 in
`/tmp/decan-security-venv`.

```sh
python -m venv /tmp/decan-security-venv
/tmp/decan-security-venv/bin/python -m pip install -r experiments/requirements.txt
```

Commands below assume the environment is active. Obtain authorized data locally
and run the **existing** preparation and feature scripts documented in the root
README. Do not run them over existing outputs without arranging a new location:
those scripts overwrite their outputs. The security commands require fresh
output paths and refuse to overwrite artifacts.

```sh
mkdir -p security/generated
python -m security analyze --input kia_soul_features_all.parquet \
  --output security/generated/kia_analysis.json
python -m security audit --input kia_soul_features_all.parquet \
  --manifest splits/generated/kia_soul/manifest.json \
  --output security/generated/kia_audit.json
python -m security baseline --input kia_soul_features_all.parquet \
  --manifest splits/generated/kia_soul/manifest.json \
  --output-dir security/generated/kia_id_rules
```

For the three-vehicle training analysis, use `features_train.parquet` and
`splits/generated/manifest.json`. For the full recording analysis, use
`features_all.parquet`. A manifest must reference indices into the **exact input
file**, verified by SHA-256 and row count. Feature variants are checked against
an explicit allowlist: numeric ID, DLC, bytes, and the three existing causal
timing features. Timestamp, labels, provenance, vehicle, round and row indices
are rejected as predictive inputs. The audit validates all declared variants;
it cannot establish which columns a separate training program actually used.

Run the audit before interpreting baseline or model results. Baseline and
evaluation always check partition separation, but do not automatically run the
more expensive duplicate/temporal audit. Commands read the whole feature table
into memory; allow enough RAM for that table and working copies. Full-data
runtime and peak memory have not been measured without local recordings.

## Analyzer output

The JSON contains per-recording and joint vehicle/round/attack-context/partition
summaries, plus vehicle, round and attack marginals. It reports R/T counts,
injected fraction, ID histograms and overlap, DLC histograms, byte histograms,
frequent CAN/payload tuples, distinct payload tuple counts, timestamp ties,
duration, IAT distributions, per-ID timing, and bus-window counts. Payload bytes
remain opaque. Timing is checked against the current-frame-and-past definition
before reporting. Challenge round is derived from `source_folder` when absent;
unknown folder formats remain `unknown`.

Zero-ID metrics are descriptive. Within-recording regular/injected ID overlap
uses that recording's labels and must not be described as held-out unseen-ID
performance. Release `mixed/unknown` context is preserved. Generic feature files
keep unknown release vehicles; Kia files retain the existing label-assisted
vehicle assignment. The analyzer neither invents attack subtypes nor infers new
vehicles from CAN IDs. Regular-ID Jaccard overlap helps inspect vehicle identity
as a possible shortcut, not establish classifier reliance.

## Leakage audit

Hard failures include:

- Invalid/missing labels, provenance, bytes/DLC, or classic 11-bit CAN IDs.
- Stale manifests, unsafe feature contracts, duplicate/out-of-range indices.
- Row, recording or supplied `session_id` overlap across train/validation/test.
- Incorrect IAT or bus-window features, including future rows at timestamp ties.
- Decreasing timestamps in original row order; capture-order semantics then need
  Data Engineering review rather than silently sorting them for this audit.

The optional `session_id` must identify an independent acquisition session, not
just a challenge round. Without it, the report explicitly marks session isolation
unverified. This may be stricter than existing filename-based experiment groups.

Duplicate diagnostics compare each pair of partitions, reporting matching-row
counts on both sides for (a) exact timestamp/ID/DLC/bytes, (b) exact ID/DLC/bytes
without timestamps, and (c) same ID/DLC with each byte quantized into bins of
width 4 by default. No labels or filenames enter fingerprints. These are 64-bit
hash diagnostics, with a theoretical collision risk. Binning is a limited
similarity proxy: nearby bytes across bin boundaries are missed; this is not an
exhaustive distance search. Repeated normal CAN content is expected, while exact
capture copies or long duplicate sequences warrant provenance review. Duplicate
matches are warnings by default, not confirmed leakage. Use
`--fail-on-duplicates` for an experiment that requires all these signatures to be
disjoint, and `--byte-bin N` to change the documented proxy.

Learned normalization cannot be audited from a feature matrix alone. The existing
baseline uses a fixed -1 sentinel, no fitted scaling. A future pipeline can
supply `--fit-receipt receipt.json`:

```json
{
  "input_sha256": "<SHA-256 of input parquet>",
  "folds": {"official": [0, 1, 2]}
}
```

Include **every** manifest fold, mapping it to rows used to fit preprocessing.
Any fit position outside that fold's training rows fails. This is a self-reported
receipt, not proof of training history; separate preprocessing objects or steps
should be audited separately. Never fit a scaler or imputer on the held-out set.

## CAN-ID shortcut experiment

The baseline consumes existing manifests, with training and evaluation separated
by recording and by session when supplied. It implements three lightweight rules:

| Rule | Behavior |
|---|---|
| `zero_id` | Predict attack iff numeric CAN ID is zero. Fixed from previously published project findings. |
| `unseen_regular_id` | Predict attack iff ID never occurs among regular **training** frames. |
| `id_majority` | Predict attack iff the training attack fraction for that ID is at least 0.5; unseen IDs predict regular. |

Rules do not read vehicle, attack context, timestamps, payload, or test labels.
Training labels establish regular IDs or per-ID fractions; test labels are used
only for scoring. The ID-zero rule is a hypothesis informed by prior inspection
of this dataset, not an independently discovered result on pristine test data.
These rules complement `experiments/shortcut_baseline.py` rather than replace its
depth-limited decision tree. No comparison with the committed AI result is made:
its source-file folds and input hashes do not establish compatible experiments.

Each manifest fold has its own results. The same row may be tested in multiple
protocols, so results are **not** pooled across leave-one-attack-out and official
folds. No validation-based tuning is performed. CSV exports identify fold, rule,
canonical row position, truth, binary prediction and input SHA-256. A report
indexes these files. Reports record dependency versions, input/manifest hashes
and security module hashes. Each loaded partition also has a SHA-256 over its row
positions encoded as little-endian signed 64-bit integers, in array order. This
binds the actual split arrays even when the original manifest only hashes input
data and refers to index files by name.

## Evaluate existing model predictions

Export one CSV per fold and model using this contract:

```text
row_position,label_bin,y_pred,input_sha256,fold
8,0,0,<SHA-256 of exact input parquet>,official
9,1,1,<SHA-256 of exact input parquet>,official
```

`row_position` is a zero-based position in the manifest's unchanged Parquet input,
not the CSV row number, original raw index, timestamp, or DataFrame index label.
Include every test row exactly once, no other rows. Truth must match the canonical
R/T target. `fold` is optional but checked if present. Threshold probability
scores using a decision fixed on training/validation data before export.

```sh
python -m security evaluate --input kia_soul_features_all.parquet \
  --manifest splits/generated/kia_soul/manifest.json --fold official \
  --predictions local_model_predictions.csv \
  --output security/generated/model_official.json
python -m unittest discover -v
```

For unnamed vehicle folds, the fold key is `held_out_vehicle`; otherwise the key
is manifest `name`, with `fold_N` as the fallback (zero-based). To evaluate
multiple protocols, run against each manifest fold's prediction export.

The reusable Python APIs are `binary_metrics(truth, predictions)`,
`evaluate(metadata_with_label_bin, aligned_predictions)`, and
`align_predictions(df, test_positions, export)`. File/hash/fold binding is added
by the CLI. The direct `evaluate` API assumes positional alignment already holds.

Metrics include attack precision/recall/F1, FPR, FNR, supports and confusion matrix
`[[TN, FP], [FN, TP]]`. A zero denominator is `null`, not a fabricated zero score.
This differs from the existing baseline's `zero_division=0`; compare only defined
metrics with matched data, folds and aggregation. Per-attack metrics include
regular rows from those attack-containing traces, so false positives are counted.
`mixed/unknown` is not a known attack subtype. Per-vehicle/round/recording/session
metrics are available where metadata exists. There is no claim about episode
detection, time to detection, operational alert rate or physical signal validity.

See [review and verification](REVIEW.md), [threat model](THREAT_MODEL.md), and
[team integration requirements](INTEGRATION.md).
