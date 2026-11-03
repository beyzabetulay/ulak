# Team integration requirements

These are local review requirements, **not GitLab issues**. The CLI is installed,
but `glab auth status --hostname git.fiw.fhws.de` reports that the project's host
is unauthenticated. Remote issues could not be inspected for duplicates. No issue
was created, changed or closed. Once authorized access is available, reconcile
these requirements with existing issues before proposing any new remote work.

## Data Engineer

### DATA-1: Reproducible provenance and session independence — priority 0

Existing: feature files preserve `recording_id = source_folder/source_file` and
source provenance; Kia files also preserve round. That meets file-level grouping
needs and should be retained. Independent acquisition sessions, raw row offsets,
raw file hashes and a raw-data version manifest are not exported.

Required: provide authorized local raw data or regenerated canonical feature
artifacts with checksums and preparation version. Preserve `recording_id` in all
outputs. Supply `session_id` only when capture evidence establishes its meaning;
otherwise document that session isolation cannot yet be guaranteed. Preserve raw
row offsets and file hashes for tracing copied samples or reordered captures.

Acceptance: rebuilding produces traceable artifacts; security can run analysis
and verify independent recording/session partitions with no overlap. Do not
equate repeated filenames or challenge rounds with acquisition identities.

### DATA-2: Release annotation and vehicle assignment — priority 0

Existing: `prepare_data.py` leaves anonymous release vehicles unknown.
`prepare_kia_soul.py` uses release **R labels** and a >=0.9 Jaccard threshold
against Kia regular IDs to select the Kia subset. No attack subtype is assigned
to those mixed recordings. This is useful offline curation but label-assisted.

Required: document the origin/version of release R/T annotations, recording-level
vehicle assignment method, confidence, reference recordings, and whether labels
were used for selection. Obtain independent vehicle evidence where possible.
Keep unverified vehicles and mixed attack types explicitly unknown.

Acceptance: evaluation reports identify label-assisted cohort selection and do
not claim release attack-type coverage or independent vehicle assignment without
evidence. Security must not silently substitute fingerprint inference.

### DATA-3: Validation and temporal ordering — priority 1

Existing: both ingestion scripts recognize 4/5/6-column layouts from the first
line; any other width falls back to the four-column choice. Four-column inputs
are assigned R, with no restriction to attack-free filenames. Byte/DLC agreement
is not checked in feature generation. `build_features.py` sorts timestamps within
recordings for timing features, retaining original output row order.

Required: reject unsupported schemas, unexpected headers, ambiguous unlabeled
attack files, malformed rows, invalid DLC/payload lengths and invalid numeric
values with file/row diagnostics. Use explicit exceptions for production
invariants rather than only assertions, which `python -O` disables. Establish
whether capture order is monotonic; document timestamp resets, ties and any
reordering policy. Retain the current past-only behavior at tied timestamps.

Acceptance: add Data-owned parser validation tests, keep valid 4/5/6-column input
support, and pass the security canonical-table/temporal audits. No malformed
dataset example was found here because no real recordings are present; these
are confirmed code validation gaps with potential data effects.

### DATA-4: Consistent experiment grouping — priority 1

Existing: Kia split generation already checks `recording_id`, supports official
and leave-one-attack-out folds, and excludes metadata via feature allowlists.
The three-vehicle generator still checks `source_file`. Existing manifests bind
their input file by SHA-256 and save positional row arrays; this should be reused.

Required: migrate grouping references consistently to recording/session IDs,
including documentation and any inner validation. Preserve input hashes, target,
feature contracts and index semantics. Add validation partitions when tuning is
introduced. Provide a preliminary-only versus later-round experiment when
scientifically appropriate, with attack coverage confounds stated.

Acceptance: all partitions pass security checks; unknown metadata remains
explicit; round/session choices are reproducible. Source-file grouping currently
merges repeated names conservatively; it is **not evidence of random-frame
leakage**. Do not replace the working generators just to change ownership.

## AI Engineer

### AI-1: Export aligned held-out predictions — priority 0

Existing: `experiments/shortcut_baseline.py` writes Markdown aggregate metrics
and source-file fold membership, without prediction rows, input SHA-256 or a
shared manifest identity. There are no saved models/prediction artifacts here.

Required: export predictions using the [security contract](README.md#evaluate-existing-model-predictions):
canonical `row_position`, `label_bin`, binary `y_pred`, exact `input_sha256`, and
fold identity. Keep model/configuration/seed, feature list, split artifact hashes,
decision threshold and dependency versions with the experiment. Supply scores
as additional columns if useful; fix thresholds on training/validation only.

Acceptance: security `evaluate` consumes every held-out row exactly once, rejects
mismatched labels/files/folds, and regenerates aggregate/per-group metrics.
No source data or predictions need to leave the authorized local workspace.

### AI-2: Compatible comparisons and preprocessing — priority 1

Existing: a depth-6 tree compares ID-only, ID/DLC/bytes, and ID-masked variants
using source-file GroupKFold. It explicitly selects features and uses a fixed
-1 sentinel. There is no learned normalization and no raw timestamp input in
this implementation. Timing feature variants exist in Kia manifests but have
no committed model results.

Required: run models and security rules on identical canonical inputs and
partition rows when comparing them. Use recording/session groups for inner
validation. Fit any learned preprocessing on training rows only; export fit-row
receipts when added. Record explicit feature lists and causal temporal feature
definitions. Treat official release test results as final evaluation.

Acceptance: input and split hashes, target, thresholds and defined metrics agree;
an absent class is handled explicitly. The security package reports null for
undefined metrics; the original tree reports zero, so do not compare those
undefined values. Do not claim performance improvements from different protocols.

## Security Engineer

Own threat assumptions, attack taxonomy, label/shortcut interpretation, audits,
security rule experiments and evaluation methodology. Run the new tools on local
artifacts once provided; review duplicates and round/vehicle strata rather than
equating every repeated payload with contamination. Reconcile historical claims
against regenerated reports, then assess dataset and protocol compatibility
before any model comparison. Any later synthetic perturbations require explicit
offline provenance and must never overwrite original data.

Security does not own ingestion replacement, silent vehicle relabeling, model
architecture/training, service deployment or modifying teammates' remote issues.
