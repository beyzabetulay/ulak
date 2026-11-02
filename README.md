# ULAK

Intrusion detection for in-vehicle CAN bus networks, with a focus on whether
ML models learn genuine attack behavior or latch onto superficial shortcuts
(e.g. CAN ID distribution, message frequency) instead.

## Overview

ULAK builds a data pipeline and detection models for CAN bus attacks
(spoofing, replay, fuzzing/injection, DoS) using the HCRL "In-Vehicle Network
Intrusion Detection Challenge" (2019) dataset, recorded across three vehicles
(Hyundai Sonata, Kia Soul, Chevrolet Spark). Alongside standard detection
performance, the project evaluates shortcut learning: whether a model's
accuracy survives when obvious shortcuts (CAN ID, timing) are masked or
tested on unseen vehicles/attack types.

## Tech Stack

- Python, pandas, PyArrow (data pipeline & features)
- FastAPI (backend API)
- Docker / Docker Compose

## Project Structure

```
.
├── prepare_data.py      # merges raw HCRL CSVs into combined_dataset.csv
├── prepare_kia_soul.py  # single-vehicle subset -> kia_soul_dataset.csv
├── reports/             # generated dataset summaries
├── build_features.py    # hex -> numeric features, train/test split -> parquet
├── backend/              # FastAPI service
│   ├── app/main.py
│   ├── Dockerfile
│   └── requirements.txt
└── docker-compose.yml
```

## Dataset

Uses the HCRL "In-Vehicle Network Intrusion Detection Challenge" (2019)
dataset. Not included in this repo due to size — download the `car_track_*`
folders directly from the source below and place them in the project root
before running the pipeline.

- Source: [HCRL - Information Security R&D Data Challenge 2019](https://ocslab.hksecurity.net/Datasets/datachallenge2019/car)
- Download: [Dropbox folder](https://www.dropbox.com/scl/fo/7d7zkq4h2xm9oti5u6soe/AFl055lkmYfWJQF-WhdPsgM?rlkey=gqw50ge0ybtb85wzi064cr475&st=l8redih9&dl=0)
- No formal license is published on the dataset page; HCRL states the data is
  released "for all security researchers for free." Download it from the
  source above yourself rather than redistributing a copy.
- Related publication (citation, not required but good practice):
  > Han, Mee Lan, Byung Il Kwak, and Huy Kang Kim. "Anomaly intrusion detection
  > method for vehicular networks based on survival analysis." *Vehicular
  > Communications* 14 (2018): 52-63.

### Single-vehicle subset (Kia Soul)

Experiments start on one vehicle before extending to all three. Kia Soul is
used because it appears in both the preliminary and final rounds and covers
all four attack types (DoS, Injection, Spoofing, Replay); Chevrolet Spark has
no Replay data. `prepare_kia_soul.py` collects every Kia Soul frame from the
six HCRL folders. Release files carry no vehicle name, so they are assigned by
CAN ID fingerprint (see the script docstring). Counts are in
[reports/kia_soul_summary.md](reports/kia_soul_summary.md). Features are built
with the same `build_features.py` as the full dataset (`--input` / `--prefix`),
so the columns match `features_*.parquet`, plus a `round` column.

## Related Work

- [2024tm05004-beep/HCRL](https://github.com/2024tm05004-beep/HCRL) uses the
  same HCRL dataset with a dual-layer detector (XGBoost with payload entropy on
  the CAN layer, Autoencoder / 3-sigma on the telemetry layer) and MITRE ATT&CK
  for Automotive style alerts, reporting 99.38% accuracy and 0% false
  positives. It does not analyse shortcut learning, which is this project's
  focus. Referenced for comparison only; no code from it is included here.

## Future Work

- Secondary datasets for cross-dataset generalization:
  CAN-MIRGU (only the sample part has been inspected so far) and the ROAD
  dataset.

## Getting Started

### Prerequisites

- Python 3.12+
- Docker & Docker Compose

### Data pipeline

```bash
python -m venv venv && source venv/bin/activate
pip install pandas pyarrow

python prepare_kia_soul.py  # -> kia_soul_dataset.csv, reports/kia_soul_summary.md
python build_features.py --input kia_soul_dataset.csv --prefix kia_soul_features
                          # -> kia_soul_features_all/_train/_test.parquet
python prepare_data.py    # -> combined_dataset.csv
python build_features.py  # -> features_all.parquet, features_train.parquet, features_test.parquet
```

### Backend

```bash
docker compose up --build
```

- API: http://localhost:8001
- Interactive docs: http://localhost:8001/docs
