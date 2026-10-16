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
folders and place them in the project root before running the pipeline.

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
