"""Development/test-only latency probe for POST /predict.

Not part of the production application path and not collected by pytest.
Uses the first complete row of the existing legitimate FRIE ML test dataset.
One warm-up request is excluded from the measured sample because it includes
one-time model/pipeline warm-up effects rather than steady-state latency.
"""

from __future__ import annotations

import statistics
import time
from pathlib import Path
from typing import Any

import pandas as pd
from app.core.feature_contract import get_feature_contract
from app.main import app
from fastapi.testclient import TestClient

REAL_TEST_DATASET = Path(r"D:\frie\Model Train\frie_ml_test.csv")
REQUEST_COUNT = 40


def load_complete_row() -> dict[str, Any]:
    contract = get_feature_contract()
    frame = pd.read_csv(REAL_TEST_DATASET, usecols=list(contract.feature_names))
    row = frame.dropna(subset=list(contract.feature_names)).iloc[0].to_dict()
    return {
        name: value.item() if hasattr(value, "item") else value
        for name, value in row.items()
    }


def main() -> None:
    features = load_complete_row()
    latencies: list[float] = []
    failed = 0
    with TestClient(app) as client:
        warmup = client.post("/predict", json={"features": features})
        assert warmup.status_code == 200, warmup.text
        for _ in range(REQUEST_COUNT):
            started = time.perf_counter()
            response = client.post("/predict", json={"features": features})
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            if response.status_code == 200:
                latencies.append(elapsed_ms)
            else:
                failed += 1

    print(f"requests: {REQUEST_COUNT} (+1 warm-up excluded)")
    print(f"successful: {len(latencies)}")
    print(f"failed: {failed}")
    print(f"min_ms: {min(latencies):.2f}")
    print(f"max_ms: {max(latencies):.2f}")
    print(f"mean_ms: {statistics.mean(latencies):.2f}")
    print(f"median_ms: {statistics.median(latencies):.2f}")
    print(f"stdev_ms: {statistics.stdev(latencies):.2f}")


if __name__ == "__main__":
    main()
