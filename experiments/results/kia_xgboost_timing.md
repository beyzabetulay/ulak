# Kia XGBoost: timing and training/validation gap

Real-data exploratory comparison using the local HCRL Kia feature parquet and
the same recording-based outer and four-fold inner splits as the XGBoost
baseline. Both variants use CAN ID, DLC and payload bytes. The timing variant
adds `iat_id` and `iat_bus`, computed within each recording; it excludes
`bus_count_100ms`. No raw data, models or generated indices are committed.
See `experiments/kia_decision_tree/XGBOOST.md` for reproduction and parameters.

The same two candidates, depth 3 and depth 6, use 100 estimators and fixed
threshold 0.5. For each feature variant and outer fold, choose the depth with
the higher unweighted mean inner validation attack F1, fit on the entire outer
training partition and evaluate the previously inspected outer test. This
timing experiment was prompted by earlier outer test findings, so these test
results are exploratory and cannot serve as an untouched final estimate.

## Outer test results

| Held-out attack | Features | Selected depth | Attack TP / total | Recall | Precision | F1 | Normal false alarms / total | FPR |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| DoS | Standard | 6 | 0 / 16,072 | 0.000 | undefined | 0.000 | 0 / 103,928 | 0.0000 |
| DoS | + timing | 6 | 15,140 / 16,072 | 0.942 | 0.973 | 0.957 | 428 / 103,928 | 0.0041 |
| Injection | Standard | 3 | 51,945 / 141,164 | 0.368 | 0.965 | 0.533 | 1,907 / 462,836 | 0.0041 |
| Injection | + timing | 3 | 25,933 / 141,164 | 0.184 | 0.657 | 0.287 | 13,558 / 462,836 | 0.0293 |
| Spoofing | Standard | 3 | 38,096 / 71,980 | 0.529 | 1.000 | 0.692 | 10 / 708,908 | 0.000014 |
| Spoofing | + timing | 6 | 25,163 / 71,980 | 0.350 | 0.926 | 0.508 | 2,009 / 708,908 | 0.0028 |
| Replay | Standard | 6 | 0 / 155,640 | 0.000 | undefined | 0.000 | 0 / 410,698 | 0.0000 |
| Replay | + timing | 6 | 0 / 155,640 | 0.000 | undefined | 0.000 | 0 / 410,698 | 0.0000 |

These are frame-level metrics. Timing and depth change together for Spoofing,
so its difference cannot be attributed to timing alone. In the other rows the
selected depth is the same; the results remain observational on a small number
of recordings. High DoS recall here does not establish detection of arbitrary
flooding or operation on other vehicles and sessions.

## Inner training and validation

The following are unweighted means of four per-fold attack F1 scores. Training
scores are measured on the same rows used to fit each fold's model. Validation
uses separate recordings with different attack and class distributions, so a
gap is evidence of weak transfer to these recordings, not proof of a particular
overfitting mechanism. Inner validation never contains the outer held-out attack.

| Held out | Features | Depth | Mean training F1 | Mean validation F1 |
|---|---|---:|---:|---:|
| DoS | Standard | 3 / 6 | 0.786 / 0.844 | 0.418 / 0.495 |
| DoS | + timing | 3 / 6 | 0.901 / 0.954 | 0.566 / 0.572 |
| Injection | Standard | 3 / 6 | 0.706 / 0.780 | 0.005 / 0.001 |
| Injection | + timing | 3 / 6 | 0.900 / 0.946 | 0.346 / 0.339 |
| Spoofing | Standard | 3 / 6 | 0.744 / 0.811 | 0.472 / 0.467 |
| Spoofing | + timing | 3 / 6 | 0.885 / 0.947 | 0.574 / 0.647 |
| Replay | Standard | 3 / 6 | 0.997 / 1.000 | 0.373 / 0.529 |
| Replay | + timing | 3 / 6 | 0.998 / 1.000 | 0.371 / 0.588 |

Depth 6 improves the mean validation F1 in some cases and worsens it in others;
raising it blindly is not supported. On Replay holdout training, training F1
near one and much lower validation F1 indicate substantial distribution-specific
performance differences; they do not prove why Replay is missed. Only two
depths and one threshold were tried. False alarms vary by fold, validation
contains as few as 130 attack frames, recording independence is not verified at
session level, and timestamp ties/ordering need auditing for deployment claims.
Detailed fold counts and metrics are in the ignored local output JSON files.
