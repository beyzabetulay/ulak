# Security engineering review and verification

Review date: 2026-11-02. The repository calls this project ULAK; this review uses
the requested De-CAN security scope. This document separates inspected code,
committed historical results, executed synthetic verification, and unavailable
real-data evidence.

## 1. Existing project status

The initial checkout contained preparation scripts, numeric feature generation,
two split generators, a decision-tree shortcut experiment and its committed
Markdown results, dataset findings and a Kia summary, plus a FastAPI health/root
skeleton. There was no test suite, CI workflow, packaged training application,
local recording, combined CSV, generated Parquet or split array. The working
tree was clean. The initial interpreter had NumPy but lacked pandas, PyArrow,
scikit-learn and pytest.

| Initial review question | Finding |
|---|---|
| What exists? | Ingestion, frame labels, provenance, numeric/timing features, grouped tree ablation, vehicle and Kia attack/official split protocols. |
| What works? | Both preparation paths, features, both split generators and original tree run on synthetic fixtures; explicit ML allowlists and fixed sentinel preprocessing are present. |
| What is incomplete? | Independent-session provenance, reusable prediction exports, raw-data version manifest, parser robustness tests, aligned end-to-end security reports. |
| What may be incorrect? | Overbroad claims that Flooding requires zero ID and that only timing can detect Replay; filename grouping is coarser than recording identity; label-assisted release selection needs disclosure. |
| What blocks evaluation? | Missing actual data/features/predictions, unknown session independence, and unverified release annotation/vehicle provenance. |
| Who owns the next work? | Data owns schemas/provenance/features/splits; AI owns models/training/prediction export; Security owns threat analysis, audits, rule experiments and security interpretation. |

Only GitHub-style security and cross-team issue templates were present locally.
`glab` is installed, but the actual origin host `git.fiw.fhws.de` is not
authenticated. Remote issue content, state, duplication and ownership were not
available. No remote state was changed.

## 2. Data Engineer review

- `prepare_data.py` ingests sorted `car_track_*/*.csv` files. Six-column inputs
  include an ignored raw index; five have labels; four are assigned R. Vehicle,
  attack context and partition come from names. Generic release vehicles remain
  `unknown`; attack context remains `mixed/unknown`.
- `prepare_kia_soul.py` provides the existing `read_raw` helper but executes the
  full preparation workflow at import time. Importing it as a library would
  trigger writes. Security therefore consumes feature Parquet rather than
  adding a competing parser or refactoring Data-owned scripts.
- R/T remain frame targets; the numeric target is `label_bin`. Attack context
  includes R frames. Kia release selection uses R-frame ID fingerprints, so it
  is label-assisted curation rather than independent vehicle ground truth.
- `build_features.py` normalizes ID width/case, converts IDs, DLC and bytes,
  preserves missing bytes as NaN, and creates `recording_id` from folder/file.
  It preserves metadata separately and optionally retains round. It does not
  decode physical signals or learn normalization parameters.
- Timing features are grouped by recording in stable timestamp order. IAT uses
  preceding rows; the 100 ms count includes the current frame and preceding
  ties. No obvious future-window inclusion was found in this definition. Raw
  capture monotonicity still needs actual-data validation.
- Official train/release partitioning is folder-based. Kia manifests already
  enforce recording separation for leave-one-attack-out and official folds.
  Vehicle holdouts check filenames, which conservatively merges repeated names.
  Both generators use positional arrays, input hashes and feature allowlists.
- Independent acquisition session IDs, raw hashes and raw row offsets are not
  exported. Four-column regular-label assumptions, unsupported-width fallback,
  assertions and payload/DLC validation need Data-owned improvements.

The committed Kia report states 4,342,470 rows and 16 source files; FINDINGS
reports 37 recordings and historical normal/attack counts. These are historical
repository claims, not measurements reproduced on actual recordings here.

## 3. AI Engineer review

The only model implementation found is `experiments/shortcut_baseline.py`:
`DecisionTreeClassifier(max_depth=6, min_samples_leaf=20, random_state=42)`,
5-fold GroupKFold by `source_file`, pooled out-of-fold scoring, no subsampling,
no weighting. Variants are CAN-ID-only, ID/DLC/bytes and ID-masked DLC/bytes.
The model loads an explicit feature allowlist, excludes metadata and timestamps,
and fills absent payload bytes with a fixed -1 sentinel. There is no fitted
normalizer, random frame split, tuning pipeline, neural network or timing-model
experiment in the inspected implementation.

The committed report gives overall attack F1 of 0.1453 (ID-only), 0.4465
(ID/DLC/bytes) and 0.5374 (ID-masked); its DoS-context ID-only attack F1 is
0.9994. These are **existing results**, not new/revalidated HCRL measurements.
ID removal improved some attack-context scores in this limited tree, so a
universal degradation claim is unsupported. Near-zero Replay F1 does not prove
that no payload/sequence model could detect Replay.

The existing report gives precision/recall/F1 and support, but no aligned
prediction export, input checksum, reusable confusion matrices, FPR/FNR or
per-vehicle results. Its grouping is conservative but not identical to the Kia
recording-based manifests. The new rules must not be numerically compared with
it until datasets, partition rows, label semantics and metrics match.

## 4. Security Engineer work completed

- Added canonical feature validation without replacing raw parsing or feature
  generation. Added metadata/model-feature allowlists and byte/DLC/label checks.
- Added per-recording and vehicle/round/attack-context summaries for labels,
  IDs, overlap, DLC, payload and timing, with descriptive shortcut checks.
- Added manifest/hash/index checks, all-pairs train/validation/test recording
  and optional session isolation, duplicate signatures, causal timing audits,
  and optional preprocessing fit-row receipts.
- Added three train-safe CAN-ID rules: fixed zero ID, unseen regular training
  ID, and per-ID training-label majority. Existing split manifests are reused.
- Added reusable prediction alignment and binary evaluation, including attack
  precision/recall/F1, FPR/FNR, confusion matrices and metadata strata. Undefined
  denominators are null; no frame-to-episode conversion is fabricated.
- Documented attacker assumptions, challenge taxonomy and round limitations,
  stationary coverage, absent verified DBC, shortcut risks, usage and integration.

## 5. Files created or changed

| Path | Purpose |
|---|---|
| `security/__init__.py`, `security/__main__.py` | Package and offline CLI. |
| `security/data.py` | Canonical interface, feature allowlist, hashes, exclusive JSON output. |
| `security/analyzer.py` | Dataset security summaries and descriptive shortcut hypotheses. |
| `security/checks.py` | Split, duplicate, temporal and preprocessing checks. |
| `security/baseline.py` | Lightweight ID-rule experiment and fold results. |
| `security/evaluation.py` | Binary metrics, group metrics and aligned predictions. |
| `security/.gitignore` | Keep local generated security artifacts out of Git. |
| `tests/__init__.py`, `tests/test_security.py` | Synthetic focused checks and existing-pipeline integration. |
| `docs/security/README.md` | Commands, artifact contracts, metrics and limitations. |
| `docs/security/THREAT_MODEL.md` | Security assumptions, taxonomy and evaluation method. |
| `docs/security/INTEGRATION.md` | Prioritized local requirements by team owner. |
| `docs/security/REVIEW.md` | This review and evidence record. |
| `README.md` | Entry point to security documentation. |

No Data/AI source, committed experiment result, raw dataset or remote issue was
rewritten. Generated verification data was created only in temporary directories.

## 6. Tests executed and outcomes

Before implementation, `python -m unittest discover -v` discovered zero tests
and exited 5 (`NO TESTS RAN` under Python 3.14). This was not a passing test suite.
The existing requirements were installed into an isolated `/tmp` environment;
no project dependency file was changed.

The first security suite ran 33 tests successfully. After additional validation
for attack-free context and optional sessions, the final verification command is:

```sh
/tmp/decan-security-venv/bin/python -m unittest discover -v
```

Final outcome: **35 tests passed in 8.217 seconds**. CLI help, `git diff --check`,
and a whitespace/newline/local-Markdown-link check across the 15 changed or
created text files also passed. No additional dependency was introduced.

It covers schema/provenance/labels, feature allowlists, invalid indices, manifest
hashes, recording/session overlap, validation-partition overlap, exact and binned
duplicates, fit-row leakage, future/tied-time features, undefined metrics,
prediction alignment and all CLI commands. Integration runs unmodified copies
of both existing preparation scripts and feature generation on **120 synthetic
raw frames across ten files**, then runs both actual split generators and the
actual tree baseline with tiny test-only parameters. It verifies 4/5/6-column
layouts and reused filenames without treating synthetic metrics as HCRL results.

The CLI help executes. A real-data analysis attempt with `features_all.parquet`
exits 2 with a clear missing-feature-file message. No HCRL security analysis,
real-data rule score, actual duplicate finding, model comparison or full-data
runtime/memory measurement is claimed.

## 7. Confirmed security issues and interpretation gaps

1. Release vehicle selection in the Kia script reads ground-truth R labels.
   This is confirmed label-assisted dataset selection, not confirmed model-input
   leakage. Label-independent vehicle assignment and population selection are
   unverified.
2. Grouping by `source_file` differs from recording identity and merges repeated
   names across rounds. This is conservative grouping, **not confirmed cross-fold
   leakage** in the current baseline. It changes the experiment unit.
3. The ingestion code does not explicitly reject unsupported widths or limit
   unlabeled four-column inputs to verified attack-free recordings; feature
   generation lacks payload/DLC agreement checks. These are confirmed validation
   gaps, not evidence that the current raw data is malformed.
4. Existing text overstates Flooding's dependence on ID zero and Replay's need
   for timing. The new threat model qualifies these claims; historical teammate
   notes were preserved.
5. No independent-session provenance or machine-readable model predictions are
   available here, preventing a complete independent security evaluation.

No random frame split, timestamp-as-feature input, filename/label-as-feature input,
learned normalization before splitting, or future-window leakage was found in
the inspected tree implementation. Absence of such code does not validate unseen
pipelines or unavailable data.

## 8. Potential risks requiring actual-data investigation

- ID zero, unused IDs, DLC/bytes, file formatting and rate as collection shortcuts.
- Vehicle identity inferred from ID vocabulary, even without a vehicle input.
- Whole-trace rate shifts incorrectly flagging regular frames in attack traces.
- Duplicate captures, replay content or related acquisition sessions across files.
- Timestamp resets/reordering affecting the operational meaning of causal timing.
- Attack/round confounding, stationary collection and sparse vehicle coverage.
- Unknown release annotation provenance and unverified attack subtypes.
- Accuracy hiding class imbalance, pooled frame metrics hiding bad recordings,
  and correlation invalidating frame-independent uncertainty estimates.

These remain hypotheses or known coverage limits, not newly measured failures.
No verified DBC for this dataset is available; raw payload bytes cannot be
interpreted as physical signals without independent evidence.

## 9. Team dependencies and blockers

Priority-0 blockers are authorized local canonical data, release label/vehicle
provenance, and AI prediction exports on shared hashed split artifacts. Session
independence remains unverified without acquisition metadata. Authenticated
GitLab access is needed only to inspect/reconcile issues; local offline tools
can run without it. Detailed owners and acceptance criteria are in
[INTEGRATION.md](INTEGRATION.md).

## 10. Recommended next tasks and readiness

1. **P0 / Data:** provide local feature artifacts plus provenance; clarify release
   annotations and label-assisted cohort selection.
2. **P0 / AI:** export held-out predictions with exact input and split identities.
3. **P1 / Security:** run full analyzer/audits and ID rules on those artifacts;
   review each recording and round before comparing compatible ML predictions.
4. **P1 / Data + AI:** align grouping with recording/session identities, improve
   parser validation, and establish independent inner validation before tuning.
5. **P2 / Security + AI:** assess later-round and vehicle transfer, then design
   documented offline robustness tests and independent-dataset evaluation.

**Readiness:** the repository has executable, synthetic-tested security tooling
and compatible data interfaces. It is **not ready for a completed, evidence-backed
security evaluation of HCRL or the ML models** in this checkout: actual data,
prediction exports and provenance verification are still required.
