# FRIE S3 NFR Evidence

Measured on 2026-09-18 against the V2 pipeline
(`backend/models/frie_xgboost_final_pipeline_v2.joblib`,
MAE 1.730576 / RMSE 2.144333 / R2 0.972064, 98 features).
Only measured results are recorded below; anything else is marked future scope.

## Reliability

- Valid prediction request returns HTTP 200. Live: `POST /predict`
  with the first complete test row returned
  `{"frie_score": 64.19, "reliability_level": "Good"}`.
- Repeated identical predictions return the same result.
  Test `test_repeated_predictions_are_identical`: 3 repetitions,
  all equal. `pytest -q`: 15 passed.
- The model loads once at startup (`lifespan` in `backend/app/main.py`;
  startup log: "FRIE XGBoost pipeline loaded successfully with 98 features").
- `GET /health` reports readiness. Live:
  `{"status": "ok", "model_loaded": true, "model": "FRIE XGBoost"}`.
- Missing features are never fabricated: strict validation rejects
  incomplete payloads (see Input Validation).
- The frontend never falls back to a fake score: API/hook layers throw
  `FrieApiError` (`src/services/api.ts`, `src/hooks/usePrototypeFrieScore.ts`)
  and every score surface has an explicit error state
  (`PrototypeScorePanel`, `CustomerSelector`, score-page badge).
- Customer switching never shows a stale score: the hook resets to
  `loading` on every `sampleId` change and features become `null`
  (dashboard shows "--") until the new prediction arrives.

## Input Validation

Strict 98-feature contract: 86 numeric (finite JSON numbers only,
booleans rejected) + 12 categorical (non-empty strings only),
`extra="forbid"`, target column rejected as input.

| Case | Expected | Actual |
|---|---|---|
| Valid 98-feature request | 200 | 200 (live + test) |
| Missing all features | 422 | 422 |
| Missing one feature | 422 | 422 |
| Unexpected feature | 422 | 422 |
| `frie_score` supplied as input | 422 | 422 |
| Numeric value as string | 422 | 422 |
| Boolean as numeric | 422 | 422 |
| NaN / Infinity / -Infinity | 422 | 422 (fixed; previously 500) |
| Empty/blank categorical | 422 | 422 |
| Number as categorical | 422 | 422 |
| Malformed JSON body | 422 (`json_invalid`) | 422 |

No invalid input is silently converted to zero.

## Error Handling

- Malformed request: 422 with `json_invalid` detail (verified live).
- Missing feature: 422. Extra feature: 422 with field name in detail.
- Invalid dev sample id: 404 `sample_not_found` (verified live);
  the loader throws and the UI shows the error state.
- Backend unavailable: `fetch` throws, mapped to `FrieApiError`
  ("Unable to reach the FRIE scoring service"), shown in the
  score panel / selector error states; no previous score is retained.
- Model not loaded: 503 on both `/health` and `/predict`
  (test `test_unavailable_model_reports_503`).

## Performance

Setup: `POST /predict` through the full in-process ASGI stack
(`backend/scripts/measure_predict_latency.py`, dev/test-only),
first complete test row, 1 warm-up request excluded as it carries
one-time warm-up effects, 40 measured requests.

- Requests: 40 (+1 warm-up excluded)
- Successful: 40
- Failed: 0
- Min: 9.05 ms
- Max: 18.14 ms
- Mean: 11.39 ms
- Median: 10.68 ms
- Standard deviation: 2.28 ms

Frontend production build (`npm run build`): JS 563.34 kB,
CSS 97.59 kB.

## Security

Implemented controls (with evidence):

- Strict Pydantic validation rejects unexpected fields, wrong types,
  non-finite numbers, blank strings, and the `frie_score` target
  (tests listed above).
- `reliability_level` is produced only by the backend; the frontend
  passes the backend value through unchanged (test asserts equality
  with the backend `reliability_level()` function).
- No secrets in backend source (`app/core/config.py` defines none).
- API base URL comes from `VITE_API_BASE_URL` environment configuration
  (no hard-coded production URL in `src/services/api.ts`).
- CORS is restricted to configured origins (default
  `http://localhost:5173,http://127.0.0.1:5173`), credentials off,
  methods GET/POST only, `Content-Type` header only.
- The development-only sample endpoints (`/__frie_dev/*`) run only on
  the Vite dev server, are guarded by `import.meta.env.DEV`, and are
  absent from the production bundle (verified: bundle contains none of
  `__frie_dev`, `sample-records`, `frie_ml_test`).
- Only synthetic prototype/test data is used; no real customer data.

Limitations (not claimed): demo-only `FRIE123` credential with no real
authentication; no encryption, audit, or certification claims are made.

## Maintainability

- Frontend: React components -> centralized API service
  (`src/services/api.ts`) -> hook (`src/hooks/usePrototypeFrieScore.ts`)
  -> dashboard components. No `fetch()` calls in UI components.
- Backend: route (`app/api/routes/prediction.py`) -> schemas
  (`app/schemas/prediction.py`) -> feature service
  (`app/services/feature_service.py`) -> prediction service
  (`app/services/prediction_service.py`) -> versioned model.
- Model loads once at startup, never per prediction.
- Feature contract is separated (`app/core/feature_contract.py`,
  driven by the model config file); configuration is separated
  (`app/core/config.py`, environment-aware).
- Model artifacts are versioned: mismatched V1 preserved untouched,
  verified V2 (`frie_xgboost_final_pipeline_v2.joblib`) plus metadata
  config (`frie_model_config_v2.json`, SHA256 recorded).
- Tests exist: `backend/tests/test_prediction.py` (15 tests).

## Usability

Active Individual flow: login -> customer selector -> loading state ->
score + reliability level -> financial snapshot -> indicator breakdown.

- Selector shows loading ("Loading prototype customers..."), error, and
  empty states, listing only complete records with real metadata.
- Score surfaces show loading ("Calculating FRIE Score..."), ready, and
  error ("Unable to calculate FRIE Score" / "Score unavailable") states.
- Switching customers resets to loading; error states retain no score.
- Labels present: "Dataset-backed prototype", "Prediction generated by
  FRIE XGBoost", per-record line ("Record N - Age - Occupation"), and
  the breakdown caption distinguishing scoring-engine indicators from
  the V2 XGBoost prediction.
