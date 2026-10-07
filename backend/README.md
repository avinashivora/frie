# FRIE deterministic scoring backend

This FastAPI service implements the authoritative FRIE six-dimension scoring methodology. It is a deterministic decision-support prototype, not a validated prediction of default or repayment outcomes. The proposal describes FRIE as a complementary financial intelligence profile that supports human decision-makers.

## Scoring

Credit Behaviour, Affordability, Cash-Flow Stability, Financial Resilience, Commitment Adherence, and Spending Behaviour each score from 0 to 100. The FRIE Base Score is their direct sum, out of 600. Unavailable and not-established dimensions are omitted rather than silently treated as zero; coverage, status, and qualitative confidence describe the evidence available.

Purpose profiles are separate weighted scores out of 100. Neutral, loan, and insurance weights are defined in `app/services/scoring/profiles.py`. Missing dimensions have their configured weights redistributed across usable dimensions. The neutral base score remains unweighted.

`POST /predict` accepts a complete feature record. `POST /predict/partial` scores available evidence directly without imputation and returns feature coverage and missing source groups. Both responses include `algorithm_version`, the nested `frie_score`, all six dimension results, and the profile result. Authenticated assessment endpoints persist the same result; `/analysis/latest` and `/analysis/history` deserialize it in the same structure.

Dimension responses include score, coverage, status (`AVAILABLE`, `LIMITED`, `NOT_ESTABLISHED`, or `UNAVAILABLE`), qualitative confidence (`High`, `Moderate`, or `Low`), indicator details, effective weights, and validation metadata. Missing evidence is not equivalent to a financial zero.

The old eight-indicator calculations remain only for recommendation and compatibility context. They do not calculate the FRIE Base Score. XGBoost artifacts and their score-imitation experiments are legacy/experimental and are not loaded into the authoritative scoring flow. No predictive accuracy is claimed from synthetic score labels.

## Setup and run

From `backend/` in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m scripts.migrate_frie6d
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The migration inspects the existing SQLite schema and adds only absent columns. If an old database has numeric `overall_confidence`, the migration preserves that field as `overall_confidence_legacy` and adds a qualitative `VARCHAR(16)` field rather than converting numeric values into misleading labels.

## Local validation

```powershell
python -m compileall app scripts tests
python -m pytest
python scripts/demo_frie6d.py
```

The demo reads row zero from `../data/frie_synthetic_1000_v22.csv` by default and accepts a CSV path and `--row` override. The dataset is not included in this checkout. The demo exits with a clear message when it is unavailable. Mathematical invariant tests cover score bounds, determinism, schema shape, weight redistribution, and missing-data semantics.

Display categories derived from the normalized /600 score are temporary UI buckets only; they are not validated financial-risk thresholds. Synthetic data supports execution and missing-data checks, not claims of predictive performance.
