# De-CAN threat model and security evaluation

## Assets, boundary and attacker assumptions

The protected assets are CAN communication availability and message integrity;
the offline IDS aims to distinguish regular frames from injected frames. An
adversary is assumed to have a compromised ECU or another means of transmitting
on the observed CAN segment. ECU compromise and physical access are entry-point
assumptions, not capabilities demonstrated by these recordings. A CAN ID is an
arbitration identifier and not authenticated sender identity.

The assumed attacker can inject chosen identifiers and payloads, vary rate, or
retransmit captured traffic. The dataset does not establish an ability to suppress
all legitimate traffic, alter the recorder, defeat a gateway, compromise the IDS,
or access another vehicle segment. Adaptive use of legitimate IDs, lower-rate
attacks, novel payloads and shifted timing are generalization hypotheses requiring
separate authorized offline evidence. This implementation performs no injection,
replay, flooding or fuzzing on physical CAN interfaces.

Trusted inputs are local artifacts with verified provenance, the R/T annotation
contract, and the documented capture/feature ordering. The annotation process is
an assumption to validate, not proof that all regular traffic is benign under
every automotive security definition. `T` means an injected/attack message in
this dataset; it does not directly measure physical harm. Predictions and model
training history are outside this package's trust boundary; hash/alignment checks
prevent accidental mismatches but cannot prove how a model was trained.

## Taxonomy and coverage

The [HCRL challenge description](https://ocslab.hksecurity.net/Datasets/datachallenge2019/car)
identifies three vehicles and four attack families, with R/T message labels.
Preliminary traffic contains Flooding, Fuzzy and Malfunction. Final session 1
contains Fuzzy and Malfunction; final session 2 contains Malfunction and Replay.
HCRL states that all data was collected with stationary vehicles.

| HCRL family | Existing pipeline context | Observable hypothesis | Security limitation |
|---|---|---|---|
| Flooding | `DoS` | Abnormal rate and arbitration pressure; project reports zero-ID injection. | Flooding need not use zero; ID alone does not establish communication loss. |
| Fuzzy | `Injection` | Diverse IDs and payload bytes, including both legitimate and unused IDs. | An attacker can reuse legitimate IDs; unseen-ID coverage is vehicle/recording dependent. |
| Malfunction | `Spoofing` | Manipulated payloads at selected IDs, accompanied by injection. | The pipeline alias is not a verified mapping to every kind of spoofing or a decoded physical effect. |
| Replay | `Replay` | Retransmitted legitimate content and sequence/rate changes. | Payload repetition is also normal; a weak payload-only tree does not prove timing is the only possible detector. |

These descriptions characterize the challenge, not a complete automotive attack
taxonomy. The dataset does not demonstrate coverage of all adversaries, moving
vehicles, environmental changes, stealth rates, cross-segment attacks or new ECU
configurations. Vehicle and attack-family coverage differs by challenge round;
pooling rounds can confound recognition of collection conditions with recognition
of attack behavior. The repository reports Spark has no Replay coverage; this has
not been revalidated here without data.

## Labels and provenance

Keep frame labels separate from trace context. Attack-containing files include
both R and T frames. Filename-derived `attack_type` describes the recording;
it is not an authoritative per-T subtype in mixed release files. A file with
attacks does not make every row an attack. Whole-trace classification requires a
separate aggregation policy, episode labels and alert accounting.

The general parser leaves release vehicles unknown. The Kia subset uses regular
frame labels from release traffic to select vehicle fingerprints. That is
label-assisted offline curation and can influence selection of the evaluation
population. Report it explicitly; validate vehicle assignments independently
before claiming label-independent deployment or cross-vehicle generalization.
Do not manufacture per-attack release results from filenames or fingerprints.

`recording_id = source_folder/source_file` preserves file identity. A file is not
necessarily an independent acquisition session. Challenge round is not a verified
session identity. Cross-file copied data and related sessions must be reviewed
with provenance and duplicate diagnostics. Preserve row order, original source
offsets and raw file hashes upstream where possible.

**A verified DBC mapping for this particular dataset is not currently available.**
Arbitrary payload bytes must not be interpreted as RPM, speed, steering, braking,
or other physical signals without independent evidence. Raw byte statistics and
CAN identifier analysis do not constitute a physical semantic model.

## Evaluation methodology

1. Validate labels, payload/DLC, provenance, feature definitions and immutable
   artifact hashes. Review the dataset security report by vehicle, round and
   recording before interpreting pooled counts.
2. Use independent recording/session partitions for training, validation and
   testing. The existing Kia official and leave-one-attack-out manifests and
   three-vehicle holdouts provide distinct protocols, not interchangeable scores.
   Tune only within training data using independent recording/session groups.
3. Audit model feature lists, preprocessing fit rows, duplicate content and causal
   feature behavior. A normalized CAN ID is still a strong shortcut candidate.
   Vehicle identity can be reconstructed from ID/payload vocabulary even when its
   explicit metadata column is excluded. A bus-rate feature may identify an
   attack-containing trace while falsely flagging its regular frames.
4. Run fixed zero-ID, train-fitted unseen-regular-ID and per-ID-majority rules.
   Compare with ML only on identical input hashes, fold rows, label semantics,
   metric definitions and aggregation. Ablation differences alone are not causal
   proof of which behavior a model learned.
5. Export aligned held-out predictions, then report attack precision, recall, F1,
   FPR, FNR, supports and confusion matrices. Show per-vehicle, trace attack
   context, round and recording results. Retain unknown strata. Do not tune
   thresholds or select models on the final test results.
6. Report finite-recording variation, class imbalance and absent attack classes.
   Millions of correlated frames do not imply millions of independent trials.
   Future confidence intervals should resample independent recordings/sessions,
   not individual frames. This package does not fabricate confidence bounds.

Frame FPR is not alerts/hour; frame recall is not episode detection or latency.
No trace-level or physical safety guarantee follows from these metrics. More
coverage, independently validated provenance, and a separate episode/alert
specification are needed for those claims.
