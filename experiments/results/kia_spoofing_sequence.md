# Kia missed Spoofing frames: timing and payload transitions

Real-data descriptive analysis of the final-first Kia Malfunction recording,
following `kia_spoofing_diagnosis.md`. All 130 attack frames were missed by the
earlier content-only models. This analysis fits no classifier, selects no
threshold, and does not report detection performance. The recording has already
been inspected; findings are exploratory.

Reproduce with `python experiments/kia_spoofing_sequence.py`. The parquet hash
is verified against the Kia manifest. Output is the ignored
`experiments/kia_decision_tree/local_outputs/spoofing_sequence.json`. No raw
payload examples or recording rows are committed.

Messages are sorted stably by recording/timestamp. For each current message,
the previous message on the bus and previous message of the same CAN ID supply
the time gaps. Payload changes are the Hamming distance (changed bits) from the
previous same-ID payload, provided lengths agree. First messages and length
changes have missing transition features. Labels are used only to define
diagnostic groups; no label enters the feature calculation. There are no tied
timestamps in this recording. Temporal deployment validity still requires
capture/provenance checks; sorting is not a proof of live arrival order.

## Observations

| Group | Rows | Median same-ID gap | Median changed bits | Previous payload repeats |
|---|---:|---:|---:|---:|
| All attack frames | 130 | 4.88 ms | 7 | 0% |
| Normal frames of the same two IDs | 25,568 | 10.00 ms | 1 | 35.0% |
| Attacks also seen as normal content | 61 | 4.54 ms | 8 | 0% |
| Normal frames matching attack content | 736 | 10.00 ms | 2 | 36.8% |

Repeat percentages exclude missing transitions. The all-normal group has two
missing same-ID/transition values (one first frame for each ID). The overlap
groups have none. The 736 controls match the set of attack signatures, not
one-to-one pairings with the 61 attack frames. Frame counts are correlated and
are not independent trials.

To reduce confounding by content, medians were also compared within each exact
ID/DLC/byte signature appearing with both labels. There are 38 such signatures:
all 38 have a shorter median same-ID gap among attacks than among normal frames;
37/38 have a higher median changed-bit count among attacks. Some signatures have
few observations; these counts are not a significance test or classifier score.

The overall difference also holds descriptively within both IDs:

| CAN ID (decimal) | Attack frames | Normal frames | Attack median gap | Normal median gap | Attack / normal median changed bits |
|---|---:|---:|---:|---:|---:|
| 790 | 65 | 12,784 | 4.39 ms | 10.01 ms | 7 / 2 |
| 1087 | 65 | 12,784 | 5.15 ms | 10.00 ms | 7 / 1 |

For identical-content groups, median bus-wide gaps are 0.370 ms for attacks and
0.236 ms for normals: the descriptive same-ID result does not translate into a
universal shorter bus-wide gap. Timing and transition distributions overlap;
none of these observations establishes a perfect separating rule.

## Next experiment

The existing content-only inputs cannot distinguish identical signatures with
different labels. This recording contains additional timing/sequence signals,
supporting an experiment with past-only changed-bit/repetition features alongside
same-ID timing. Compute features independently per recording without labels;
compare fixed models on the existing recording-based validation protocol and
report per-recording F1, recall, precision, FPR and support. Fit any learned
per-ID timing normalization only on training rows. Do not choose thresholds on
these inspected 130 frames or claim they are an untouched final holdout.
