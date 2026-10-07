"""Run one synthetic CSV row through deterministic FRIE-6D scoring."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPOSITORY = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings  # noqa: E402
from app.core.feature_contract import get_feature_contract  # noqa: E402
from app.services.prediction_service import PredictionService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "dataset",
        nargs="?",
        type=Path,
        default=REPOSITORY / "data" / "frie_synthetic_1000_v22.csv",
    )
    parser.add_argument("--row", type=int, default=0, help="zero-based CSV row index")
    args = parser.parse_args()
    if not args.dataset.is_file():
        print(f"Dataset not found: {args.dataset}", file=sys.stderr)
        return 2
    with args.dataset.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader):
            if index == args.row:
                break
        else:
            print(f"Dataset has no row at index {args.row}.", file=sys.stderr)
            return 2

    contract = get_feature_contract()
    features = {}
    for name in contract.feature_names:
        raw = row.get(name)
        if raw is None or raw.strip() == "":
            continue
        if name in contract.numeric_features:
            features[name] = float(raw)
        else:
            features[name] = raw

    service = PredictionService(get_settings())
    result = service.predict_with_partial_data(features, profile="neutral")
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
