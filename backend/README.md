# FRIE Prototype Backend

This FastAPI service exposes the supplied FRIE preprocessing-plus-XGBoost pipeline as a prototype API. It does not retrain, alter, or reimplement the model. The existing React/Vite frontend is intentionally not connected in this phase.

## Architecture

```text
FastAPI routes → PredictionService → saved joblib Pipeline → FRIE score response
```

`PredictionService` loads the model once during application startup. `FeatureContract` is the single authoritative contract: it reads the exact 98 names and their numeric/categorical groups from `models/frie_model_config.json`. `FeatureService` accepts only a complete source-normalized customer mapping and constructs the one-row dataframe in the saved pipeline's own feature order.

## Setup

From `backend/` in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The pinned versions include scikit-learn `1.6.1`, matching the serialized pipeline metadata. No model artifacts are modified during setup.

## Run

```powershell
uvicorn app.main:app --reload
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for the automatically generated API documentation.

## Endpoints

- `GET /health` reports API/model readiness without exposing filesystem details.
- `POST /predict` accepts `{ "features": { ... } }`, where `features` contains all 86 numeric and 12 categorical fields defined in `models/frie_model_config.json`. Unknown and omitted fields are rejected; no arbitrary defaults, zero filling, or undocumented financial derivations are used.

Responses contain the display-rounded `frie_score` and a prototype `reliability_level`:

| Score | Prototype level |
|---:|---|
| 0–39.99 | Poor |
| 40–54.99 | Average |
| 55–69.99 | Good |
| 70–100 | Excellent |

Scores are prototype/research outputs only. They are not regulatory decisions, universal thresholds, or externally validated measures of real-world financial reliability.

## Model artifacts

The service reads, but never changes:

- `backend/models/frie_xgboost_final_pipeline.joblib`
- `backend/models/frie_model_config.json`

## Tests

```powershell
pytest
```

Tests verify the feature contract, validation behavior, startup/model loading, and `/health`. The real prediction integration test reads one complete 98-feature row from `D:\frie\Model Train\frie_ml_test.csv` when available; it never sends that file's `frie_score` column to the API. The test is skipped when the externally stored dataset is unavailable.
