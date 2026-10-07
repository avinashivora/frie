# FRIE -- Framework & Technology Justification

## S3 Lab Work -- Framework Selection, Architecture Integration & Justification

## 1. Introduction

FRIE (Financial Reliability Intelligence Engine) is an M.Sc. Data Science
prototype that consolidates behavioural, credit, and financial signals into a
single prototype reliability score. The current implementation is a
dataset-backed Individual demonstration: a React frontend selects a complete
test record, a FastAPI backend validates the 98 model features, and a saved
XGBoost pipeline returns a prototype FRIE Score with a reliability level.

The purpose of this document is to justify, for S3 evaluation, the frameworks
and technologies actually used in the current implementation. Framework
selection matters for FRIE because the system spans four distinct
responsibilities -- interactive frontend, REST API with strict validation, ML
prediction pipeline with explainability, and automated testing -- and each
layer benefits from a tool designed for that responsibility. Every claim below
was verified by repository inspection (package manifests, source imports,
installed packages, and analysis artifacts). Technologies that are installed
but unused, test-only, or future are labelled as such and are not presented
as active capabilities.

## 2. FRIE Technology Stack Overview

| Technology | Layer | Current Usage | Purpose |
|---|---|---|---|
| React 18.3.1 | Frontend | Actively used (`src/app/App.tsx`, `src/main.tsx`) | Component-based user interface |
| TypeScript | Frontend | Actively used (all `src` files are `.ts`/`.tsx`) | Type-safe frontend code |
| Vite 6.3.5 | Frontend | Actively used (`npm run dev`, `npm run build`) | Development server and production build |
| Recharts 2.15.2 | Frontend | Actively used (Financial Analysis chart) | Score and financial visualisation |
| Lucide React 0.487.0 | Frontend | Actively used (icons throughout the UI) | Interface icons |
| Tailwind CSS 4.1.12 | Frontend | Actively used (utility classes, theme, fonts) | Styling |
| FastAPI 0.115.6 | Backend | Actively used (`backend/app/`) | REST API layer |
| Pydantic 2.10.4 | Backend | Actively used (request schemas) | Strict input validation |
| Uvicorn 0.34.0 | Backend | Actively used (serves the API) | ASGI server |
| Python 3.12 | Data/ML/Runtime | Actively used (project virtual environment) | Implementation language |
| Pandas 2.2.3 | Data/ML | Actively used (feature DataFrame, tests) | Dataset manipulation |
| NumPy 1.26.4 | Data/ML | Actively used (prediction handling, metrics) | Numerical processing |
| Scikit-learn 1.6.1 | Data/ML | Actively used (pipeline transformers, metrics) | Preprocessing and evaluation |
| XGBoost 2.1.4 | Data/ML | Actively used (V2 regression pipeline) | Prototype score prediction |
| SHAP | Explainability | Analysis-layer only (offline CSVs, not in serving path) | Model transparency |
| Joblib 1.4.2 | Persistence | Actively used (pipeline load at startup) | Model serialization |
| Pytest 8.3.4 | Testing | Actively used (`backend/tests/`, 15 tests) | Automated backend tests |
| Remaining `package.json` UI-kit packages (MUI, Radix set, React Router, Motion, DnD set, cmdk/embla/sonner family) | Frontend | Installed but unused by the active render path | Figma-generated footprint only |

## 3. Frontend Frameworks & Technologies

### 3.1 React

React is a declarative, component-based JavaScript UI library. FRIE uses
React 18 for the entire user interface: the login page, the dataset customer
selector, the Individual dashboard, the FRIE Score page, and the Financial
Analysis page are React components in `src/app/App.tsx`, mounted from
`src/main.tsx` via `react-dom/client`. State-driven rendering fits FRIE
because each screen is a direct function of a small explicit state
(authenticated user, selected record, prediction status), which keeps the
loading, ready, and error states of the scoring flow consistent. An
alternative considered is Angular or Vue; React was selected because the
delivered Figma-generated implementation is already component-based React,
so it required no rewrite and matches the team's working codebase.

### 3.2 TypeScript

TypeScript adds static types to the FRIE frontend: every source file under
`src/` is `.ts` or `.tsx`, and the API layer defines typed contracts such as
`PredictionRequest`, `PredictionResponse`, `HealthResponse`, and the
`PrototypeFrieScoreState` union. This gives compile-time checking of the
frontend-backend data exchange (for example, the four reliability levels are
a closed union shared with the backend response). The benefit for
maintainability is that contract changes surface as type errors at the exact
consuming component rather than as runtime failures. Note: the repository
runs `vite build` for production output and does not configure a separate
standalone type-check step.

### 3.3 Vite

Vite (6.3.5, with `@vitejs/plugin-react` 4.7.0) is the frontend build and
development tool: `npm run dev` serves the application with hot reloading and
hosts the development-only dataset middleware (`/__frie_dev/*`), while
`npm run build` produces the static production bundle in `dist/`. It fits the
React application because it is the toolchain the generated project ships
with, gives fast feedback during UI integration work, and cleanly separates
development-only dataset access (serve mode only, eliminated from production
bundles) from the shipped app.

### 3.4 Recharts

Recharts (2.15.2) is a React charting library. FRIE uses it in the Financial
Analysis page for the Monthly Financial Breakdown bar chart, which visualises
dataset-derived income, expenses, savings, and EMI values. It fits the
application because it renders declarative React chart components in the same
component tree and visual language as the rest of the dashboard, without a
separate charting service.

### 3.5 Lucide React

Lucide React (0.487.0) provides the interface icons used across the FRIE UI
(navigation, score components, statistics cards, and status indicators). It
fits the interface because the icons are lightweight React components that
inherit the surrounding typography and colour scheme, keeping the
Figma-derived visual language consistent.

## 4. Backend Frameworks & Technologies

### 4.1 FastAPI

FastAPI (0.115.6) provides the REST API layer in `backend/app/`. It exposes
`GET /health` (API and model-readiness reporting, including a 503 degraded
state) and `POST /predict` (prototype scoring), parses requests into typed
Pydantic models, delegates inference to the prediction service, and returns
`frie_score` with the backend-authoritative `reliability_level`. Startup
model loading happens once via the application lifespan, and a custom
validation-error handler guarantees controlled 422 responses. FastAPI fits
FRIE because it combines lightweight API development with typed request
handling and automatically generated OpenAPI documentation (`/docs`), which
suits a small, contract-strict prototype service.

### 4.2 Pydantic

Pydantic (2.10.4) enforces the strict 98-feature input contract. The request
schema is built dynamically from the model configuration: 86 numeric fields
accept finite JSON numbers only (strings, booleans, nulls, NaN, and
infinities rejected), 12 categorical fields accept non-empty strings only,
and the model forbids extra fields -- so missing fields, unexpected fields,
and the `frie_score` target itself are all rejected with controlled 422
validation errors. This enforcement is what prevents silent fabrication or
zero-filling of model inputs.

### 4.3 Uvicorn

Uvicorn (0.34.0) is the ASGI server that runs the FastAPI backend
(`uvicorn app.main:app`), used in the project virtual environment for both
verification runs and the demo. It fits because it is the standard,
lightweight server for FastAPI/Starlette applications.

## 5. Data Science & Machine Learning Technologies

### 5.1 Python

Python (CPython 3.12 in the project virtual environment) is the language of
the data and ML layers: the Home Credit foundation build, the synthetic
Indian behavioural layer, dataset validation scripts, the scoring data
preparation, the ML training/evaluation workflow, and the FastAPI backend
itself. A single language across data preparation, modelling, and serving
keeps the feature definitions and preprocessing consistent end to end.

### 5.2 Pandas

Pandas (2.2.3) is used for dataset manipulation: building the model input as
a named one-row DataFrame in `FeatureService`, reading the ML test CSV in
tests and verification scripts, and preparing train/test frames during the
ML workflow. Named-column DataFrames are load-bearing for correctness here:
the saved pipeline selects features by name, so pandas guarantees each value
reaches the preprocessing stage under its contracted feature name.

### 5.3 NumPy

NumPy (1.26.4) supports numerical processing where verified: converting the
pipeline output to a scalar prediction in `PredictionService` and computing
evaluation statistics (MAE, RMSE, R2, error distributions) in the ML
workflow and verification scripts.

### 5.4 Scikit-learn

Scikit-learn (1.6.1, matching the serialized pipeline metadata) is used in
preprocessing, the train/test workflow, regression baselines, and evaluation
metrics. Concretely, the saved pipeline's preprocessing stage is a
`ColumnTransformer` combining median imputation with standard scaling for the
86 numeric features and most-frequent imputation with one-hot encoding for
the 12 categorical features; comparisons against Linear Regression and
Random Forest baselines, and MAE/RMSE/R2 evaluation, were produced with the
scikit-learn workflow during the ML experiments.

### 5.5 XGBoost

XGBoost (2.1.4) provides FRIE's current prototype regression model: an
`XGBRegressor` (500 estimators, depth 4, learning rate 0.03) fitted to
approximate the methodology-generated prototype FRIE Score from the 98
features. It was selected after model comparison because it gave the best
measured prototype score approximation among the tested models (XGBoost MAE
1.730576 against 2.246 for Linear Regression and 2.769 for Random Forest on
the corrected comparison). Current measured metrics on the held-out test set
are MAE = 1.730576, RMSE = 2.144333, R2 = 0.972064. The target is the
prototype FRIE Score generated by the project scoring methodology from
synthetic prototype data. These figures describe score approximation
validated within the current synthetic prototype dataset only; they are not
evidence of real-world financial reliability prediction, and FRIE makes no
claim to predict loan default or to replace CIBIL or credit bureaus.

## 6. Explainability

### 6.1 SHAP

SHAP (SHapley Additive exPlanations) attributes a trained model's prediction
to its input features, supporting both global importance rankings and
individual prediction explanations. In FRIE, SHAP was used in the offline ML
analysis environment: the repository carries the resulting
`frie_corrected_shap_feature_importance.csv` (185 transformed features),
headed by savings rate (mean absolute SHAP 5.65), insurance premium (2.05),
and savings balance (1.95), consistent with the XGBoost gain ranking led by
savings rate. SHAP is not installed in the backend environment, no SHAP code
exists in the serving path, and no SHAP values are computed during
prediction; it is an analysis-layer transparency aid, not real-time
inference. SHAP explains the behaviour of the trained model. It does not
establish causal relationships or external validity.

## 7. Model Persistence

### 7.1 Joblib

Joblib (1.4.2) serializes the trained pipeline so training never needs to
repeat at serving time. The backend loads
`frie_xgboost_final_pipeline_v2.joblib` once at startup into the
application-lifetime prediction service; every `/predict` call then reuses
the in-memory object. Bundling preprocessing and the regressor in one
pipeline object is useful because inference automatically applies the exact
fitted imputers, scaler, and encoder from training, which prevents
train/serve skew. The versioned artifact is verified in the repository:
`backend/models/` holds the preserved mismatched V1 artifact alongside the
verified V2 artifact and its metadata config (`frie_model_config_v2.json`,
recording parameters, metrics, and SHA256).

## 8. Testing Framework

### 8.1 Pytest

Pytest (8.3.4, with httpx 0.28.1 as the TestClient transport) runs the
automated backend suite in `backend/tests/test_prediction.py`: unit tests for
the feature contract and feature service, API tests for the health and
prediction endpoints, validation tests (missing/unexpected fields, invalid
numeric and categorical values, non-finite numbers, target-as-input),
response-schema and reliability-level tests, error-handling tests (including
model-unavailable 503s), and a repeated-prediction consistency test. Current
verified result: 15 tests passed. No additional coverage beyond these 15
tests is claimed.

## 9. Framework Selection Justification

| Technology | Requirement in FRIE | Selected Technology | Alternative | Reason for Selection |
|---|---|---|---|---|
| Interactive frontend | Component UI for login, selection, dashboard | React | Angular / Vue | Component-based UI and the existing delivered implementation, avoiding a rewrite |
| Type-safe frontend contracts | Shared API/score types | TypeScript | Plain JavaScript | Compile-time checking of the frontend-backend exchange |
| Build and dev serving | Bundle and serve the React app | Vite | Generic bundlers | Ships with the project, fast feedback, clean dev-only dataset separation |
| Charts | Financial/score visualisation | Recharts | Custom SVG / chart service | Declarative React charts in the existing visual language |
| Icons | Interface iconography | Lucide React | Custom icon assets | Lightweight components consistent with the UI |
| Prediction API | Typed REST scoring service | FastAPI | Flask | Typed validation, lifespan management, and auto-generated API docs for a small strict service |
| Input validation | 98-feature contract enforcement | Pydantic | Manual validation | Strong schema enforcement with controlled errors |
| ASGI serving | Run the FastAPI app | Uvicorn | Other ASGI servers | Standard lightweight server for this stack |
| ML regression | Prototype score approximation | XGBoost | Random Forest / Linear Regression | Best measured prototype approximation among tested models |
| Explainability | Local and global model insight | SHAP (offline analysis) | Gain importance only | Per-prediction attributions plus global rankings |
| Serialization | Persist fitted pipeline | Joblib | Rebuild per run | Single artifact bundling preprocessing with the model |
| Testing | Automated API/backend verification | Pytest | unittest | Clear fixtures and expressive API-level assertions |

Alternatives are not presented as inferior in general; each selection is
justified only by fit to FRIE's specific prototype requirements.

## 10. FRIE System Architecture & Technology Integration

Actual request flow in the current implementation:

User
-> React + TypeScript frontend (login, customer selector, dashboard)
-> FastAPI REST API (`POST /predict`, `GET /health`)
-> Pydantic validation (strict 98-feature schema)
-> Feature contract / feature service (named one-row DataFrame)
-> Preprocessing pipeline (ColumnTransformer from the saved artifact)
-> XGBoost model (V2 regressor)
-> FRIE Score prediction
-> Response (`frie_score`, backend `reliability_level`) to frontend
-> FRIE dashboard / scoring-engine indicators

Joblib persistence connects training to serving: the fitted
preprocessing-plus-model pipeline is loaded once at startup. SHAP sits
outside the request path as an analysis layer over recorded model
behaviour. Pytest verifies each boundary (contract, validation, endpoints,
errors, consistency). Pandas, NumPy, scikit-learn, and XGBoost jointly
implement the ML workflow from frames through metrics to the fitted
artifact. SHAP is currently used for model explainability and analysis; it
is not executed during prediction and no real-time SHAP inference is
claimed.

## 11. Current vs Future Technology Capabilities

| Capability | Current Status | Notes |
|---|---|---|
| REST prediction API | Implemented | FastAPI `/health`, `/predict` |
| Model persistence | Implemented | Versioned joblib artifacts |
| Strict input validation | Implemented | 98-feature Pydantic contract |
| Automated backend tests | Implemented | 15 pytest tests |
| SHAP analysis | Implemented for explainability | Offline CSV findings, not per-request |
| Dataset-backed Individual demo | Implemented | 24 complete test records, dev-only access |
| Real bank integrations | Future | Not implemented |
| Account Aggregator integration | Future | Not implemented |
| OCR / document processing | Future | Not implemented |
| Production authentication | Future | Demo credential only |
| Real-world financial outcome validation | Future | Prototype score approximation only |

## 12. Limitations

- FRIE is currently a prototype and research system, not a production
  credit product.
- The current score is methodology-generated and validated only within
  the synthetic prototype dataset; it is not externally validated
  against any real-world financial reliability outcome.
- Synthetic Indian financial variables form part of the research
  dataset alongside Home Credit foundation variables.
- Home Credit is a foundation and source for financial and credit
  variables, not the final FRIE target; its TARGET column is never used.
- No live banking or Account Aggregator integration is implemented.
- Authentication is demo and prototype-level (single demo credential).
- Model performance figures describe score approximation, not
  real-world predictive validity.

## 13. Conclusion

The FRIE technology stack is layered: React, TypeScript, Vite, Recharts,
and Lucide implement the interactive frontend; FastAPI, Pydantic, and
Uvicorn implement the validated prediction API; Python with Pandas, NumPy,
scikit-learn, and XGBoost implements the ML workflow; Joblib persists the
fitted pipeline; SHAP supports offline explainability; and Pytest verifies
the backend. Frontend, API, ML, and testing responsibilities are separated
across these layers, which supports maintainability and transparency. The
architecture provides a foundation for future FRIE development while the
current implementation remains appropriate to its prototype and research
stage, without claiming production readiness.
