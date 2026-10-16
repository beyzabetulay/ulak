# De-CAN

Intrusion detection for in-vehicle CAN bus networks, with a focus on whether
ML models learn genuine attack behavior or latch onto superficial shortcuts
(e.g. CAN ID distribution, message frequency) instead.

## Overview

De-CAN builds a data pipeline and detection models for CAN bus attacks
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

## Getting Started

### Prerequisites

- Python 3.12+
- Docker & Docker Compose

### Data pipeline

```bash
python -m venv venv && source venv/bin/activate
pip install pandas pyarrow

python prepare_data.py    # -> combined_dataset.csv
python build_features.py  # -> features_all.parquet, features_train.parquet, features_test.parquet
```

### Backend

```bash
docker compose up --build
```

- API: http://localhost:8001
- Interactive docs: http://localhost:8001/docs
