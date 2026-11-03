# F00 methodology and measurement definitions

## Scope, provenance, and reuse

Only the preliminary and final-first-round Kia Soul attack-free recordings
listed in [the configuration](../configs/f00.json) are accepted. Resolution uses
both directory and filename. A path must resolve inside the provided dataset
root. No recursive discovery or attack-recording selection is performed.

The existing `prepare_data.py` and `build_features.py` are copied unchanged to a
temporary directory with symlinks to just those two files. Their normal parsing
and canonical feature extraction execute there. `security.data.load_features`
and `validate_frames` validate the resulting interface, including label, ID,
DLC/byte consistency, and recording identity. There is no second raw parser.
No Data/AI source file is changed. The F00 code adds descriptive measurements in
`security/normal_profile.py`; plotting is in `security/normal_plots.py`.

Rows retain canonical input order. Within each file that is capture order;
the parser's order of concatenating files is irrelevant to all calculations.
The Data script's pre-existing sorted timing features are **not** used as a
substitute for F00 capture-order differences. Each ID is grouped by
`(recording_id, can_id_dec)` before differencing. Filename alone would combine
the two recordings incorrectly.

Raw SHA-256 digests are checked before conversion, after conversion, and after
profiling. Results record code revision, relevant source/configuration hashes,
unchanged Data-script hashes, and dependency versions. Generated outputs use
new directories. Temporary canonical files are removed. The selected raw files
are opened for reading only.

## Inventory and rates

For each recording/ID, `frame_count` is N and `traffic_percent` is
`100 * N / recording_frame_count`. `can_id_hex` and `can_id_dec` describe the
same arbitration identifier, not an ECU identity. `dlc_counts` maps each observed
payload length to its count. `recordings_containing_id` counts distinct complete
recording identities containing the ID.

`first_timestamp` and `last_timestamp` are the first/last same-ID observations
in capture order. `id_observation_duration_s` is that ID's maximum minus minimum
timestamp. `recording_duration_s` uses the whole recording's range. These ranges
agree with first-to-last spans in the actual monotonic recordings.

Two rates are intentionally named differently:

- `rate_recording_fps = N / recording_duration_s` measures the ID's observed
  contribution over the whole recording. It is useful for comparing traffic.
- `rate_id_span_fps = (N-1) / id_observation_duration_s` uses completed same-ID
  intervals. It equals reciprocal mean interval when timestamps increase.

An ID seen once has no interval rate. A zero-length observation span yields
null rather than infinity. Boundary placement especially affects slow IDs:
92 or 93 one-second messages in a roughly 92-second capture does not imply a
large underlying rate difference. No interval spans different files.

## Timing statistics and timestamp policy

`delta_t_ms = 1000 * (current_timestamp - previous_same_ID_timestamp)`.
The total interval count is N-1. Finite strictly positive intervals supply the
mean, median, minimum, maximum, and linearly interpolated P5/P25/P75/P95
percentiles. P5 means 5% of these intervals are at or below that value; the
median is P50. Standard deviation uses the sample denominator m-1, where m is
the number of positive intervals. It is null for fewer than two such intervals.
The coefficient of variation is `sample_std / mean`, a dimensionless relative
spread. A smaller value means more tightly grouped intervals.

Nonfinite/non-numeric timestamps fail canonical conversion/validation; the run
does not impute, drop, or silently repair them. Nonpositive absolute timestamps,
backward bus timestamps, and equal adjacent bus timestamps are counted in the
summary. Same-ID zero and negative intervals are counted separately, kept out
of positive-interval statistics, and never repaired by sorting. A flagged file
would need review before periodicity conclusions. Epoch timestamps are parsed
by the existing float64 interface; near this epoch the representational spacing
is about 0.00024 ms. Extremely fine differences should not be overinterpreted.

A broad timing group is assigned only if the median is within 5% of one of
10/20/100/200/1000 ms **and** at least 95% of positive intervals are within 20%
of that nominal period. Otherwise the group is `unclassified`. These are
descriptive configured bands, not an official CAN requirement or a learned
detector. The group names use reciprocal nominal periods (100/50/10/5/1 Hz),
not an assumption that every message arrives exactly on schedule.

Short gaps are below 0.5 times the same-ID median; long gaps exceed 1.5 times
that median. Both are exploratory review flags, not attacks. A gap near integer
k times the median (k >= 2, within 0.20 cycle) is counted as a possible missing
cycle interval, with k-1 possible missed cycles. Without recorder/transmitter
evidence this cannot distinguish capture loss, suppressed transmission, a
schedule change, or an incorrect period hypothesis. Zero flags do not prove
complete capture.

Possible modes are local peaks of a histogram spanning 0.5–1.5 times the median,
with bin width 1% of the median and a three-bin [1/4, 1/2, 1/4] smoothing kernel.
A candidate is above its left neighbor and at least its right neighbor, has at
least 5% of all positive intervals in its three-bin neighborhood, and is at least
5% of the median from stronger selected peaks. Tails remain in other statistics.
Centers depend on bin alignment; they are exploratory histogram features, not
separate proven transmission periods. Fine timing bumps can reflect scheduling,
arbitration, or recording effects. Histograms support visual review.

## Payload, byte, and bit measurements

A payload is the ordered tuple of its actually present bytes. Its length is
part of its identity. An absent byte is missing, never a measured zero. The
existing canonical validation rejects missing bytes within DLC or bytes beyond
DLC. Byte arithmetic uses masked scratch padding internally; padded positions
never enter distributions, transition counts, or Hamming distance.

- Unique payloads U count distinct complete tuples. The five most frequent
  payloads are ordered by descending count, breaking ties by byte tuple.
- `repeated_payload_percent = 100 * (N-U)/N` counts observations beyond each
  payload's first occurrence, anywhere in that ID's recording.
- Consecutive repeat count compares each payload with the preceding same-ID
  payload, requiring the same length and bytes. Its percentage divides by N-1.
  It is null when there is no pair. A cyclic sequence can have high global
  repetition and zero consecutive repetition.
- Each byte's histogram divides counts by frames in which that position exists.
  `stable` means one observed value, `variable` means more than one, and
  `absent` means no observations. Stable means only stable in this recording.
- Byte change frequency divides changed values by adjacent same-ID pairs where
  that byte exists in **both** frames. Missing intermediate positions are not
  bridged. Each bit's change count/fraction uses the same pair denominator;
  bit 0 is the least significant bit.
- Hamming distance counts differing bits using XOR. For changing DLC, only
  byte positions shared by both frames are compared; DLC changes are separately
  counted. Mean, P95, maximum, and comparable-pair count are reported. The mean
  changed-bit fraction divides each pair by its actually compared bit count
  before averaging. Empty common payloads do not create a zero-distance
  observation. For equal DLC 8, distances compare 64 bits.

Counter-like tests examine full bytes and high/low nibbles (four-bit halves).
They require at least 32 comparable pairs, at least four observed successor
states, and at least 95% agreement with one nonzero modular increment. Moduli
are 256/16, plus a smaller range only if observed states are exactly 0 through
k. The inferred range is a hypothesis; unseen states may exist elsewhere.
This recognizes the measured 15-state cycle at `0x153` without forcing a
16-state counter. A regular changing field can have another purpose.

Checksum-like checks only test whether the sum of all bytes modulo 256 or the
XOR of all bytes is conserved in at least 95% of frames. They require fixed DLC,
at least 16 distinct payloads, and at least 32 supporting frames. A conservation
relationship can arise from repeated/redundant fields; it does not identify a
checksum field, algorithm, validation rule, or ECU function. Other checksum
families and nibble relationships are not searched exhaustively.

## Recording comparison and possible duplication

The comparison table uses the union of IDs, preserving an absent-ID flag rather
than inventing measurements. It compares DLC sets, whole-recording rates,
timing statistics, payload cardinality, global/consecutive repetition, and
Hamming distance. Changes are final minus preliminary; relative timing/rate
changes divide by the preliminary value. An undefined denominator stays null.

For payload sets, Jaccard similarity is intersection size divided by union size.
Each recording also reports the proportion of its frames whose complete payload
is in the other recording's same-ID set. These are content similarities, not
evidence of a copied capture by themselves. Raw unique counts and global repeat
percentages depend on recording length; the final capture is longer. Consecutive
changes, byte distributions, and comparable timing statistics provide context.
No equal-duration subsampling or statistical significance test is implied.

Three additional checks address duplication: raw file hash identity, absolute
timestamp-range overlap, and exact timestamp/ID/DLC/payload tuple intersection
(compared as full tuples). SHA-256 fingerprints of every ordered 16-frame
ID/DLC/payload window test for copied local bus sequences even after a timestamp
shift; timestamps are excluded from this sequence test. Hash collisions are
theoretically possible. Shorter copies, interleaved/edited copies, and shared
acquisition conditions can escape it. No session identity is inferred from a
round label, similar rate, or the absence of duplicate windows.

## Visualization and reproducibility

Bars compare per-recording percentages, not unmatched raw counts. Timing-group
plots show both ID counts and frame shares. Interval histograms use shared bins
per representative ID and probability density, allowing different-duration
recordings to be compared. Each ID has its own x-axis range. The heatmap shows
byte change fractions, with gray for absent/uncomparable positions. The all-ID
comparison uses a log scale for median intervals so 10–1000 ms remain readable.
The detailed plot shows raw byte values, not decoded signals.

No random sampling or fitted model is used. Tables and JSON use fixed ordering;
PNG metadata has no creation timestamp. Reproducibility tests compare complete
outputs from two synthetic runs in the same environment. Cross-version fonts,
plotting, or numeric formatting can differ; use recorded versions and hashes.
The profiled real data verifies execution on these two recordings, not security
detection performance or general validity on other vehicles/conditions.
