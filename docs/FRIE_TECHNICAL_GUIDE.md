# FRIE Technical Guide

This guide describes the application as implemented in this repository. FRIE is a prototype financial-intelligence and decision-support application: its deterministic six-dimension assessment summarizes the supplied financial evidence and is intended to complement human review. It is not a validated probability of default, a lending or insurance decision, or a replacement for a credit bureau. The project proposal in [FRIE.docx](FRIE.docx) describes the broader motivation and intended scope; this guide describes the current software.

## 1. System overview

FRIE has a React and TypeScript frontend, a FastAPI backend, and a SQLAlchemy persistence layer backed by SQLite by default. The backend assembles financial information from a user profile, reviewed document extractions, and bank transactions. It normalizes that information into the feature contract, calculates each of the six dimensions once, and derives the canonical score and purpose-specific profile scores from those results.

```text
Profile and financial sources
  ├─ Profile declarations
  ├─ Uploaded documents and reviewed extractions
  └─ Bank transaction imports
          ↓
Feature assembly and readiness
          ↓
Six deterministic scoring dimensions (each /100)
  ├─ FRIE Base Score: direct sum, maximum /600
  └─ Neutral, Loan, and Insurance profile scores (each /100)
          ↓
Explanation, persistence, authenticated API, React dashboard
```

### Main code areas

| Area | Location | Responsibility |
|---|---|---|
| React application | `src/app/` | Login, profile, document, dashboard, analysis, and recommendation views |
| Frontend API client | `src/services/api.ts` | HTTP requests, session handling, and TypeScript response types |
| FastAPI routes | `backend/app/api/routes/` | Authentication, profile, document, feature, prediction, and assessment endpoints |
| Request and response schemas | `backend/app/schemas/` | Pydantic validation and API shapes |
| Feature contract and settings | `backend/app/core/` | Feature validation, environment configuration, and runtime settings |
| Financial data services | `backend/app/services/` | Document storage/extraction, transaction import, feature assembly, persistence, and compatibility indicators |
| Deterministic scoring | `backend/app/services/scoring/` | Six dimension algorithms, score aggregation, and profile weights |
| Database | `backend/app/db/` | SQLAlchemy models, SQLite session setup, and schema migration |
| Backend tests | `backend/tests/` | Scoring, API, feature assembly, authentication, documents, and profile tests |

## 2. Authoritative scoring methodology

The algorithm version is `FRIE-6D-v1.0`. Each dimension is scored from 0 to 100. The canonical FRIE Base Score is the direct sum of available dimension scores, with a maximum of 600 when all six scores are available. It is not converted to a weighted /100 score. If some dimensions cannot be established, their scores are not silently replaced with zero; the score, available-dimension count, coverage, status, and confidence make the evidence limitations visible.

| Canonical dimension | Main evidence areas |
|---|---|
| Credit Behaviour | Credit history, repayment reliability, delinquency severity, credit utilisation, and contextual application behaviour |
| Affordability | Debt-to-income burden (30%), EMI-to-income burden (30%), expense-to-income burden (20%), and available surplus (20%) |
| Cash-Flow Stability | Cash-flow consistency/volatility (35%), negative cash-flow exposure (25%), minimum cash-flow strength (20%), and income stability (20%) |
| Financial Resilience | Liquidity buffer (35%), savings capacity (25%), long-term asset buffer (20%), and surplus resilience (20%) |
| Commitment Adherence | Payment reliability (40%), delinquency management (25%), recurring commitments (20%), and insurance adherence (15%) |
| Spending Behaviour | Overall spending burden (40%), discretionary spending discipline (30%), essential/discretionary balance (20%), and spending-pattern coverage (10%) |

The credit dimension keeps its intended component weights: credit history (15%), repayment reliability (30%), delinquency severity (30%), utilisation (15%), and application behaviour (10%). Application activity is contextual and capped; a count alone is not an automatic negative judgment. Negative `payment_difference` represents overpayment and is not rewarded symmetrically. Requested principal (`goods_price`) is not treated as existing debt. Spending uses total expense relative to income where available, with the synthetic spending ratio as a fallback; digital payment and UPI activity are contextual rather than inherently good or bad.

### Purpose-specific profiles

Purpose profiles are separate weighted summaries of the same six dimension results. They do not change the canonical /600 Base Score and do not recalculate dimensions.

| Dimension | Neutral | Loan | Insurance |
|---|---:|---:|---:|
| Credit Behaviour | 20% | 30% | 15% |
| Affordability | 20% | 25% | 15% |
| Cash-Flow Stability | 20% | 15% | 20% |
| Financial Resilience | 15% | 10% | 20% |
| Commitment Adherence | 15% | 15% | 25% |
| Spending Behaviour | 10% | 5% | 5% |

Each profile score is out of 100. Its configured weights are redistributed proportionally across usable dimensions when some are missing. The result exposes both configured and effective weights, profile coverage, confidence, and available dimensions. The assessment response contains all three profiles; `profile` remains the selected/default neutral profile for compatibility.

### Missing information and confidence

Missing, zero, unavailable, invalid, and not-established evidence are distinct states. A real zero is retained as a real value; missing evidence is not invented as zero. In particular, an absent credit history can produce `NOT_ESTABLISHED` rather than a zero credit score. Dimension statuses are:

- `AVAILABLE` — sufficient evidence was available for the dimension.
- `LIMITED` — some evidence was available, but coverage is incomplete.
- `NOT_ESTABLISHED` — the relationship or behaviour cannot be established from the available evidence.
- `UNAVAILABLE` — required evidence is unavailable.

Confidence is qualitative (`High`, `Moderate`, or `Low`), based on available dimensions and coverage. It is not a probability. Dimension coverage is between 0 and 1; overall Base Score coverage is the mean of the six dimension coverage values. Profile coverage reflects the configured profile weights and dimension coverage.

Affordability treats `current_dti` and `bureau_dti` as alternative sources for debt-to-income evidence rather than as separately weighted components. EMI burden uses `current_loan_annuity / monthly_income`, falling back to `synthetic_total_emi / monthly_income` where appropriate. Expense burden uses `synthetic_total_expense / monthly_income`; available surplus uses `available_surplus / monthly_income`, with the documented expense-plus-EMI fallback where appropriate. `available_surplus` already accounts for spending/responsibilities including EMI. Savings/assets are reserved for resilience to avoid unnecessary duplication.

The configured ratio scoring points are interpolated between anchors where the scoring module specifies continuous scoring. Debt-to-income and EMI burden use 0.10 → 100, 0.20 → 90, 0.30 → 75, 0.40 → 50, 0.50 → 25, and above 0.50 → 0. Expense burden uses 0.30 → 100, 0.40 → 90, 0.50 → 75, 0.60 → 55, 0.70 → 35, 0.80 → 15, and above 0.80 → 0. Surplus ratio uses below 0 → 0, 0.05 → 25, 0.10 → 50, and 0.20 → 75; it approaches 90 below 0.30 and scores 100 at or above 0.30.

Other data semantics preserved by the implementation include:

- Positive `payment_difference` means required EMI exceeded the amount paid (underpayment).
- `cash_flow_mean`, `cash_flow_std`, and `cash_flow_min` describe monthly cash-flow level and variation; `cash_flow_negative_months` is used without inventing an observation-period denominator.
- `health_insurance` and `life_insurance` are coverage flags. Missing insurance evidence does not zero Commitment Adherence.
- Expense categories include food, rent, education, healthcare, transport, utilities, and discretionary spending. Missing categories stay missing.
- Investment balances/contributions and savings evidence inform resilience; UPI and digital-payment behavior are not treated as inherently positive or negative.

## 3. Data collection and feature assembly

The feature assembler produces the backend's normalized feature vector from user profile declarations, confirmed financial-status declarations, reviewed extraction values, and parsed bank transactions. The project currently defines 98 normalized input features; dimensions consume the evidence relevant to their scoring logic. This input contract is not a second score and must not be confused with the canonical six-dimension FRIE methodology.

Documents are stored locally by default under `backend/storage/documents`. PDFs with embedded text are read with PyMuPDF; scanned pages/images can be processed with PaddleOCR. Extraction parsers only return fields found in document text. Users can review and edit extracted values before they contribute to feature assembly. Bank transactions can be imported and edited. Readiness reporting distinguishes missing, unreviewed, confirmed absent, and available sources; uncertain or unreviewed financial data is not silently treated as a confirmed zero.

Supported source areas include profile and income information, bank statements/transactions, credit and loan records, insurance, and investments. Feature derivations and source provenance are implemented in `backend/app/services/feature_engineering.py`, `bank_import.py`, `credit_records.py`, and `transaction_classifier.py`. The 98-feature contract is declared in `backend/app/core/feature_contract.py` and its configured feature definition.

## 4. Backend API

The API is served at `http://127.0.0.1:8000`; OpenAPI documentation is available at `/docs`.

| Endpoint | Authentication | Purpose |
|---|---|---|
| `GET /health` | No | Report service readiness and deterministic scoring version |
| `POST /predict` | No | Score a complete normalized feature vector |
| `POST /predict/partial` | No | Score available normalized evidence directly, without model imputation |
| `POST /auth/register`, `POST /auth/login`, `GET /auth/me` | Login/register as applicable | Create and inspect an authenticated session |
| `GET /profile`, `PUT /profile` | Yes | Read/update profile details |
| `GET /profile/financial-status`, `PUT /profile/financial-status` | Yes | Read/update declared financial-product status |
| `GET /documents`, `POST /documents/upload`, `POST /documents/import/bank` | Yes | List/upload documents and import transactions; additional routes handle extraction, review, edits, downloads, and deletion |
| `POST /features/build`, `GET /features`, `GET /features/readiness`, `GET /features/completeness` | Yes | Assemble and inspect normalized features and source readiness |
| `GET /analysis/status`, `POST /analysis/assess` | Yes | Check readiness and create/persist an assessment from the same deterministic engine |
| `GET /analysis/latest`, `GET /analysis/history`, `GET /analysis/explanation` | Yes | Retrieve canonical saved scores/history or a deterministic explanation |

`/predict` and `/predict/partial` receive a JSON object with a `features` member. The partial route omits null values and scores the evidence it receives; it does not claim V2 model imputation. Assessment state (`complete` or `estimated`) is a data-readiness/UI state and does not select a different scoring methodology.

### Score response shape

Responses carry the version, canonical Base Score, six dimensions, and profile scores. A shortened example:

```json
{
  "algorithm_version": "FRIE-6D-v1.0",
  "frie_score": {
    "value": 483.0,
    "maximum": 600.0,
    "available_dimensions": 6,
    "dimension_count": 6,
    "coverage": 1.0,
    "confidence": "High"
  },
  "dimensions": {
    "credit_behaviour": {
      "score": 82.0,
      "max_score": 100.0,
      "coverage": 1.0,
      "status": "AVAILABLE",
      "confidence": "High",
      "indicators": {},
      "effective_weights": {},
      "validation": {}
    }
  },
  "profile": { "profile": "neutral", "score": 80.5 },
  "profiles": {
    "neutral": { "profile": "neutral", "score": 80.5 },
    "loan": { "profile": "loan", "score": 81.0 },
    "insurance": { "profile": "insurance", "score": 79.8 }
  }
}
```

The sample values are illustrative only. Each profile object also includes its maximum, coverage, confidence, configured/effective weights, and available-dimension count. Each dimension includes its full score, status, qualitative confidence, coverage, indicator metadata, effective weights, and validation/explanation metadata. In the full response, the dimension map contains all six canonical dimensions.

The assessment endpoint also persists source snapshots, feature snapshots, readiness metadata, recommendations, and legacy indicator context. Deterministic dimension explanations are the explanation for the authoritative FRIE score. Any SHAP or ML artifact is not used as that score's explanation.

## 5. Persistence and migrations

SQLAlchemy models are in `backend/app/db/models.py`; database sessions and safe base-table initialization are in `backend/app/db/session.py`. By default, SQLite stores data in `backend/frie.db` when commands run from the backend directory. The database stores users/sessions, profiles, financial declarations/features, documents/extractions, assessments, and explanation/source records.

Each assessment stores the numeric Base Score in the existing compatibility column `predicted_frie_score`; the deterministic fields include `algorithm_version`, `frie_maximum`, `scoring_profile`, `dimensions_json`, `overall_coverage`, and qualitative `overall_confidence`. The JSON snapshot stores all six dimensions, the selected/default profile, and all three purpose-specific profiles. `/analysis/latest` and `/analysis/history` deserialize this saved representation.

`backend/app/db/001_add_frie6d_assessment_fields.sql` documents the fields. The SQLite-aware script `backend/scripts/migrate_frie6d.py` inspects existing columns before altering the database. If it finds an old numeric `overall_confidence`, it preserves that value in `overall_confidence_legacy` and adds the qualitative string column. Back up an existing database before manual schema work; do not repeatedly apply raw `ALTER TABLE` statements.

## 6. Frontend behavior

The dashboard shows the six dimension scores and the canonical FRIE Base Score out of 600. It separately shows Neutral, Loan, and Insurance purpose scores out of 100. Coverage, confidence, dimension status, and available-dimension count explain how much information supported the assessment. The “Why this score?” view summarizes dimension scores in plain language; detailed raw features are not presented as the customer-facing explanation.

The assessment display category (`Poor`, `Average`, `Good`, or `Excellent`) is a temporary UI bucket based on the normalized /600 value. These buckets are not validated financial-risk thresholds and should not be used as such.

## 7. Legacy and experimental components

`backend/app/services/indicator_service.py` retains the older eight-indicator calculation to support existing recommendations and compatibility surfaces. Those indicators do not calculate or replace the six-dimension FRIE Base Score.

XGBoost and other ML dependencies/artifacts may remain in the repository for legacy or experimental compatibility. They are not loaded into or used by the authoritative deterministic scoring path. Synthetic score imitation, if retained for experimentation, is not evidence of real-world predictive accuracy. The current synthetic dataset cannot establish default, repayment, or insurance-outcome accuracy.

## 8. Validation and limitations

Backend tests live under `backend/tests/`. They cover scoring invariants, profile weighting, missing-data behavior, feature assembly/readiness, authentication, documents, and recommendation compatibility. `backend/scripts/demo_frie6d.py` loads a row from `data/frie_synthetic_1000_v22.csv`, maps it to features, and prints the deterministic results. The data can demonstrate execution, deterministic repeatability, score bounds, schema behavior, and missing-evidence handling; it is not validated outcome data.

The prototype has not established predictive accuracy, causal effects, regulated underwriting suitability, fairness across populations, or production security/compliance readiness. Scores and profile weights are methodology outputs for human review, not financial advice or automatic product eligibility decisions. Real-world use would require consent and data governance controls, representative observed outcomes, independent validation, fairness evaluation, monitoring, and applicable regulatory review.

## 9. Runtime configuration

| Setting | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./frie.db` | SQLAlchemy database URL |
| `FRIE_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Allowed browser origins |
| `FRIE_SESSION_DAYS` | `7` | Session lifetime |
| `FRIE_STORAGE_DIR` | `backend/storage/documents` | Uploaded file storage |
| `FRIE_MAX_UPLOAD_MB` | `10` | Maximum upload size |
| `FRIE_SEED_DEMO_USER` | `false` | Enable optional demo-user seeding |
| `FRIE_DEMO_EMAIL`, `FRIE_DEMO_PASSWORD` | Prototype defaults | Credentials used only when demo seeding is enabled; override for local use |
| `FRIE_TESSERACT_CMD` | Auto-detected if present | Optional Tesseract executable path |
| `VITE_API_BASE_URL` | No application fallback | Frontend API base URL; set to `http://127.0.0.1:8000` locally |

