# FRIE Phase 2 -- Database + Authentication Foundation

## 1. Objective

Establish the persistence and authentication foundation for the future
Working Demo: a SQLite database, secure registration and login, opaque
session handling, per-user profile persistence, document metadata
persistence, and table structures for future financial features,
predictions, and explanations. Foundation only: no OCR, extraction,
transaction parsing, feature engineering, SHAP, or prediction-logic
changes.

## 2. Existing Architecture Reviewed

Before implementing, the existing backend was inspected: FastAPI routes
(`app/api/routes/`), Pydantic schemas (`app/schemas/`), feature contract
(`app/core/feature_contract.py`), configuration (`app/core/config.py`),
feature service, prediction service (V2 pipeline loaded once at startup),
prediction routes, and lifespan in `app/main.py`; plus the Phase 1.5
provenance, architecture, and requirements documents. Phase 2 reuses these
modules unchanged and adds a parallel `app/db`, `app/services/*`,
`app/schemas/*`, and `app/api/*` persistence layer. No second backend
architecture was created.

## 3. Database Technology

SQLite via SQLAlchemy ORM 2.1.2 (pinned in `backend/requirements.txt`),
with Pydantic v2 schemas and the existing FastAPI app. SQLite was chosen
because the prototype needs a zero-operational-cost local store with no
server process; SQLAlchemy keeps all queries in typed ORM code rather
than raw SQL strings. Configuration is environment-driven:
`DATABASE_URL` (default `sqlite:///./frie.db`, created automatically on
first startup, so a fresh clone initializes cleanly). No production
credentials or secrets exist anywhere in the configuration.

## 4. Database Schema

All tables in `app/db/models.py` (`Base.metadata.create_all` on startup;
Alembic-style migrations are future scope):

- `users`: id, email (unique, indexed), password_hash, created_at,
  updated_at. Email uniqueness is enforced by the database, not just
  application code.
- `sessions`: id, user_id (FK, indexed), token_hash (unique, indexed),
  expires_at, created_at. Stores only the SHA-256 of the opaque token.
- `customer_profiles`: id, user_id (FK, unique), 16 raw profile inputs
  (gender, date_of_birth, children_count, family_size, family_status,
  education_level, housing_type, owns_car, owns_property, income_type,
  occupation, organization_type, contract_type, city, monthly_income,
  employment_start), created_at, updated_at.
- `documents`: id, user_id (FK, indexed), document_type, original_filename,
  storage_reference (nullable), uploaded_at, processing_status,
  extraction_status, source_type, review_status, created_at, updated_at.
- `financial_features`: id, user_id (FK, indexed), feature_name
  (indexed), feature_type, value_num (nullable), value_text (nullable),
  provenance, status (default DRAFT), timestamps; unique(user_id,
  feature_name).
- `predictions`: id, user_id (FK, indexed), profile_id (nullable FK),
  predicted_frie_score, reliability_level, model_version, timestamps.
- `explanations`: id, prediction_id (FK, indexed), feature_name,
  feature_value, contribution (nullable), explanation_type, timestamps.

## 5. Entity Relationships

User 1--1 CustomerProfile, User 1--N Sessions/Documents/FinancialFeatures/
Predictions, Prediction 1--N Explanations. All child rows carry the owning
`user_id` (directly or via the prediction), use `ON DELETE CASCADE`
(where applicable), and every query in the service layer filters by the
authenticated user, so isolation is structural rather than conventional.

## 6. Authentication Flow

Register: validate email/password -> normalize email -> reject duplicates
(409) -> PBKDF2-hash -> insert -> issue session -> return 201 with token
and safe user object. Login: look up normalized email -> constant-time
hash check -> identical 401 message for unknown email and wrong password
(no user enumeration) -> issue session -> return 200. Logout is client
side (token discarded); `/auth/me` validates a stored token on app start
to restore the session, else the login screen is shown.

## 7. Password Hashing Approach

PBKDF2-HMAC-SHA256 from the Python standard library (no extra
dependency): 600,000 iterations, 16-byte per-user random salt, stored as
`pbkdf2_sha256$600000$<salt-b64>$<hash-b64>`, verified with
`hmac.compare_digest`. Plaintext passwords never reach the database
(asserted by tests that inspect stored rows directly); salts guarantee
identical passwords hash differently (also tested).

## 8. API Endpoints

- `POST /auth/register` (201): `{email, password}` -> token + safe user;
  409 duplicate, 422 invalid email/short password.
- `POST /auth/login` (200): same input -> token + safe user; 401 on any
  credential failure.
- `GET /auth/me` (200): bearer session check; 401 without/expired token.
- `GET /profile` (200 | 404 when never saved).
- `PUT /profile` (200): partial upsert of raw inputs; validated types and
  ranges; 401 without token.
- `POST /documents/metadata` (201): type/filename (+optional storage
  reference/source); statuses default to UPLOADED/PENDING/PENDING; 422 on
  unknown type; 401 without token.
- `GET /documents` (200): own documents only, newest first.
- `GET /documents/{id}` (200 | 404, including other users' ids).
- Unchanged: `GET /health`, `POST /predict` (same contract, same V2).

## 9. User Isolation

Every persistence query is scoped to `current_user.id`; cross-user reads
return 404 (never 403-with-existence-leak, never чужі data). Covered by
tests: separate profiles per account, document list/detail isolation, and
`/auth/me` identity checks.

## 10. Profile Persistence

`GET /profile` returns the caller's profile or 404; `PUT /profile`
creates-or-updates only the caller's row with validated raw inputs. No
98-feature computation occurs here. Verified live: save Pune/95000,
restart server, values persist from the SQLite file.

## 11. Document Metadata Persistence

`POST /documents/metadata` records type, filename, optional storage
reference, and honest initial statuses (UPLOADED/PENDING/PENDING);
`GET /documents` and `GET /documents/{id}` are ownership-scoped. No file
bytes, OCR, or extraction run in Phase 2; statuses never claim work that
has not happened.

## 12. Financial Feature Persistence Design

Normalized `financial_features` rows were chosen over a JSON snapshot
because per-feature provenance (USER/DOCUMENT/DERIVED) and review status
(DRAFT/REVIEWED/READY) stay queryable per feature, which is exactly what
the readiness model needs. Absent values have no row (never NULL-filled
or zero-filled). Tables and constraints exist now; write paths arrive
with Phase 6 feature engineering, and READY status will require a
complete validated vector.

## 13. Prediction Persistence

The `predictions` table stores results only (score, level, model version
such as `FRIE XGBoost V2`, profile link, timestamp); results can never
become inputs because no code path feeds them to `/predict`. The live
`/predict` contract is byte-for-byte unchanged, and Phase 2 adds no
prediction routes; recording flows belong to later phases.

## 14. Explanation Persistence

The `explanations` table (prediction link, feature name/value,
contribution, explanation type) is created for future SHAP storage. No
SHAP values are generated in Phase 2.

## 15. Security Considerations

Salted slow hashing, unique-email constraint, generic 401 messages,
bearer tokens stored as hashes with expiry, ownership-scoped queries,
validated schemas, no password material in responses or logs, env-driven
config, `*.db*` git-ignored. Explicitly NOT claimed: production-grade,
bank-grade, or certified security; real authentication strength review;
encryption at rest; rate limiting. This is an academic prototype.

## 16. Tests Added

`tests/conftest.py` (isolated file DB per test + client fixture +
register/login helpers), `tests/test_auth.py` (12: init, register,
duplicate, invalid email/password, hash/salt properties, login,
wrong-password, unknown-email, token rejection, isolation, idempotent
seed), `tests/test_profile.py` (7: auth gating, 404-before-save,
roundtrip, merge, validation, isolation, file persistence),
`tests/test_documents.py` (5: auth gating, defaults, type rejection,
list/detail isolation). Existing 15 tests untouched.

## 17. Test Results

`pytest -q`: **39 passed** (15 pre-existing + 24 new), 1 pre-existing
third-party warning.

## 18. Frontend Changes

`src/services/api.ts` only: `registerUser`, `loginUser`, session
storage helpers, bearer `authorizedFetch`, `fetchAccount`,
`fetchProfile`, `saveProfile` (all errors typed as `FrieApiError`).
`App.tsx`: real backend login with sign-in/register modes and busy/error
states; session restore on reload with fallback to login; demo hint kept
for the seeded account; new Profile view (account card + 16-field form
with loading/saving/success/error states, dropdowns using the encoder's
exact training levels); Profile added to sidebar; client-side demo
account gate removed. Dashboard, selector, score, and analysis flows are
unchanged and still backend-driven.

## 19. Existing Prediction Regression Result

`/health` 200 with model loaded; `POST /predict` with the verified test
row returns the V2 result; empty features still 422. All 15 pre-existing
prediction tests pass unmodified.

## 20. Limitations

SQLite file store (no migrations yet -- `create_all` only); opaque
bearer tokens without refresh/rotation; demo seed enabled by default
(documented); profile holds raw inputs with basic validation only;
documents are metadata-only; features/predictions/explanations tables
await Phase 6/7 writers; no rate limiting, audit logging, or
production hardening.

## 21. What Phase 3 Will Implement

Richer profile input UX (grouped sections, derived-value previews such
as age/employment years computed for display, exact-level guardrails),
profile-completeness tracking toward the 18-field USER block, and any
additional profile validation needed before document phases -- building
on the GET/PUT API and table created here.
