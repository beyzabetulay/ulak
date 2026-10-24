# Shortcut baseline

Input: `features_train.parquet`; 5,509,252 rows, 21 source files. No subsampling.
Environment: numpy 2.5.4, pandas 3.0.6, scikit-learn 1.9.1.
5-fold GroupKFold by source_file; pooled out-of-fold predictions. DecisionTreeClassifier(max_depth=6, min_samples_leaf=20, random_state=42); no class weighting.
Missing payload bytes use a fixed -1 sentinel (outside 0–255); no learned preprocessing. Only can_id_dec, dlc and byte_0..7 are eligible features. Timing features are outside this ablation.

Attack type identifies the source trace, not the frame label. Each trace subset includes normal and attack frames; precision includes false positives on normal frames in those traces. Normal-only traces have no attack support. Undefined metrics are reported as zero. These observational ablations do not establish causal shortcut reliance.

| Configuration | Trace attack type | Class | Support | Precision | Recall | F1 |
|---|---|---|---:|---:|---:|---:|
| id_only | ALL | normal | 4,766,085 | 0.8742 | 0.9970 | 0.9316 |
| id_only | ALL | attack | 743,167 | 0.8047 | 0.0799 | 0.1453 |
| id_only | DoS | normal | 252,836 | 1.0000 | 0.9998 | 0.9999 |
| id_only | DoS | attack | 48,164 | 0.9987 | 1.0000 | 0.9994 |
| id_only | Injection | normal | 898,353 | 0.7979 | 0.9994 | 0.8874 |
| id_only | Injection | attack | 237,946 | 0.9545 | 0.0445 | 0.0851 |
| id_only | Normal | normal | 1,350,970 | 1.0000 | 0.9957 | 0.9979 |
| id_only | Normal | attack | 0 | 0.0000 | 0.0000 | 0.0000 |
| id_only | Replay | normal | 795,414 | 0.7251 | 0.9980 | 0.8400 |
| id_only | Replay | attack | 301,542 | 0.2759 | 0.0020 | 0.0040 |
| id_only | Spoofing | normal | 1,468,512 | 0.9039 | 0.9956 | 0.9475 |
| id_only | Spoofing | attack | 155,515 | 0.0000 | 0.0000 | 0.0000 |
| all_features | ALL | normal | 4,766,085 | 0.9019 | 0.9868 | 0.9425 |
| all_features | ALL | attack | 743,167 | 0.7866 | 0.3117 | 0.4465 |
| all_features | DoS | normal | 252,836 | 1.0000 | 0.9858 | 0.9928 |
| all_features | DoS | attack | 48,164 | 0.9305 | 1.0000 | 0.9640 |
| all_features | Injection | normal | 898,353 | 0.8388 | 0.9918 | 0.9089 |
| all_features | Injection | attack | 237,946 | 0.9007 | 0.2803 | 0.4276 |
| all_features | Normal | normal | 1,350,970 | 1.0000 | 0.9697 | 0.9846 |
| all_features | Normal | attack | 0 | 0.0000 | 0.0000 | 0.0000 |
| all_features | Replay | normal | 795,414 | 0.7253 | 1.0000 | 0.8408 |
| all_features | Replay | attack | 301,542 | 0.9375 | 0.0012 | 0.0024 |
| all_features | Spoofing | normal | 1,468,512 | 0.9739 | 0.9925 | 0.9831 |
| all_features | Spoofing | attack | 155,515 | 0.9138 | 0.7487 | 0.8230 |
| without_id | ALL | normal | 4,766,085 | 0.9126 | 0.9894 | 0.9495 |
| without_id | ALL | attack | 743,167 | 0.8527 | 0.3923 | 0.5374 |
| without_id | DoS | normal | 252,836 | 0.8382 | 0.9866 | 0.9063 |
| without_id | DoS | attack | 48,164 | 0.0000 | 0.0000 | 0.0000 |
| without_id | Injection | normal | 898,353 | 0.8988 | 0.9923 | 0.9432 |
| without_id | Injection | attack | 237,946 | 0.9519 | 0.5783 | 0.7195 |
| without_id | Normal | normal | 1,350,970 | 1.0000 | 0.9836 | 0.9918 |
| without_id | Normal | attack | 0 | 0.0000 | 0.0000 | 0.0000 |
| without_id | Replay | normal | 795,414 | 0.7251 | 1.0000 | 0.8407 |
| without_id | Replay | attack | 301,542 | 0.5000 | 0.0000 | 0.0000 |
| without_id | Spoofing | normal | 1,468,512 | 0.9989 | 0.9878 | 0.9933 |
| without_id | Spoofing | attack | 155,515 | 0.8958 | 0.9900 | 0.9405 |

## Feature importances

Impurity importances for all_features, mean ± standard deviation across held-out-file folds. These are descriptive and can favor high-cardinality features.

| Feature | Mean | Std |
|---|---:|---:|
| can_id_dec | 0.1589 | 0.0588 |
| dlc | 0.0006 | 0.0012 |
| byte_0 | 0.0607 | 0.0794 |
| byte_1 | 0.0414 | 0.0694 |
| byte_2 | 0.0497 | 0.0346 |
| byte_3 | 0.1098 | 0.0549 |
| byte_4 | 0.1280 | 0.0658 |
| byte_5 | 0.1269 | 0.1148 |
| byte_6 | 0.1146 | 0.0595 |
| byte_7 | 0.2093 | 0.0807 |

## Attack F1 change after removing ID

| Trace attack type | All features F1 | Without ID F1 | Drop (all − without) |
|---|---:|---:|---:|
| DoS | 0.9640 | 0.0000 | +0.9640 |
| Injection | 0.4276 | 0.7195 | -0.2919 |
| Normal | 0.0000 | 0.0000 | +0.0000 |
| Replay | 0.0024 | 0.0000 | +0.0024 |
| Spoofing | 0.8230 | 0.9405 | -0.1175 |

## Direct checks on the full train partition

- DoS attack frames with ID zero: 48,164/48,164.
- Normal frames with ID zero: 0/4,766,085.
- Unique IDs in normal frames: 128.
- Unique IDs in Injection attack frames: 2,048.

## Interpretation

ID removal can improve Injection and Spoofing in this depth-limited model; a universal performance drop is not supported. Replay remains poorly detected. These scores depend on the chosen tree and source-file folds.
The documented 155 normal IDs is not reproduced in the training partition; use the direct count above. ID zero covers every DoS attack frame and no normal training frames, but the fitted tree can also flag other IDs and produce false positives.

## Fold membership

- Fold 1: Attack_free_KIA_Soul_train.csv, Flooding_CHEVROLET_Spark_train.csv, Malfunction_1st_dataset_KIA_Soul_train.csv, Malfunction_KIA_Soul_train.csv
- Fold 2: Attack_free_CHEVROLET_Spark_train.csv, Fuzzy_CHEVROLET_Spark_train.csv, Fuzzy_HYUNDAI_Sonata_train.csv, Malfunction_1st_dataset_HY_Sonata_train.csv, Replay_dataset_KIA_Soul_train.csv
- Fold 3: Attack_free_HYUNDAI_Sonata_train.csv, Malfunction_2nd_KIA_Soul_train.csv, Malfunction_CHEVROLET_Spark_train.csv, Replay_dataset_HY_Sonata_train.csv
- Fold 4: Flooding_HYUNDAI_Sonata_train.csv, Flooding_KIA_Soul_train.csv, Fuzzy_dataset_HY_Sonata_train.csv, Fuzzy_dataset_KIA_Soul_train.csv
- Fold 5: Attack_free_HY_Sonata_train.csv, Fuzzy_KIA_Soul_train.csv, Malfunction_2nd_HY_Sonata_train.csv, Malfunction_HYUNDAI_Sonata_train.csv
