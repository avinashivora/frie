# FRIE Phase 3 -- Customer Profile + 18 User-Input Acquisition

## 1. Objective

Let an authenticated user enter, save, edit, and track the 18 direct
USER inputs from Phase 1.5, with deterministic completeness and honest
readiness states. No scoring, OCR, extraction, parsing, SHAP, document
features, or derived-feature engineering was built in this phase.

## 2. Phase 1.5 Requirements Used

`docs/FRIE_WORKING_DEMO_DATA_REQUIREMENTS.md` Section 2 (18-field form
spec), Section 7 (exact derivation formulas, reused unchanged),
Section 8 (matrix), Section 9 (readiness statuses). The 18/64/16 split
and all formulas are preserved verbatim.

## 3. 18 USER-Input Layer

Implemented exactly as specified: gender, age_years (via date_of_birth),
children_count, family_size, family_status, education_level,
housing_type, owns_car, owns_property, income_type, occupation,
organization_type, contract_type, city_tier (via city), occupation_band
(via occupation), indian_household_size (via family_size),
monthly_income, employment_years (via employment_start). No 98-field
form exists; no feature was added or renamed.

## 4. Profile Database Structure

Existing `customer_profiles` table reused unchanged (one row per user
via unique `user_id`; timestamps preserved). It stores 16 raw inputs;
the remaining mapping (DOB->age, city->tier, occupation->band,
family_size->household, start->years) is documented in code and computed
only by the completeness check, never persisted as features. No score,
prediction, or document financials are stored in the profile.

## 5. Raw vs Derived Values

Raw (stored): the 16 form inputs. Derived (never stored, shown for
feedback only): age preview and employment-duration preview on the
profile form; completeness mapping in `profile_service.py`. Feature
engineering remains a later phase; this phase performs no model-feature
computation.

## 6. Validation Rules

Backend-authoritative (`app/schemas/profile.py`): email-style presence
is not needed here, but every field is constrained -- 10 categoricals
must exactly match the fitted V2 encoder levels (verified by a test
that loads the pipeline; unknown levels get 422, never silent mapping);
dates must be real calendar dates with DOB/employment-start never in the
future and age capped at 120 years (dynamic today); monthly_income must
be finite and positive; counts non-negative (family size >= 1).
Frontend mirrors these checks for UX only.

## 7. Completeness Methodology

Single source of truth: `COMPLETENESS_REQUIREMENTS` in
`app/services/profile_service.py` (18 feature-to-field mappings).
A feature counts when its source raw input is present and valid per
Section 6. Result: `{completed, required: 18, percentage, missing[]}`
with per-feature labels. Frontend displays backend numbers only; no
duplicated logic exists.

## 8. PROFILE_READY Definition

`profile_status == "READY"` and `profile_ready == true` exactly when
completed == 18 (NOT_READY at 0, PARTIALLY_READY otherwise).

## 9. FRIE_SCORING_READY Definition

Constant `false` in Phase 3. A complete profile can never imply scoring
readiness because the 64 document and 16 derived features are absent by
design; no code path in this phase can trigger prediction from profile
data (verified: predictions table stays empty through all profile tests).

## 10. API Behavior

`GET /profile` now returns `{profile, completeness, readiness}` (200
always when authenticated; `profile` is null when never saved -- the old
404 was replaced deliberately and the corresponding test updated).
`PUT /profile` partial-upserts and returns the same envelope with fresh
numbers. Auth, isolation, and validation semantics are otherwise
unchanged from Phase 2.

## 11. Frontend UX

Login/register unchanged; Profile view has account card, completeness
bar (dynamic X/18 with missing-field names), readiness card (profile
block live, documents/history/vector/score honestly marked
not-ready/locked), four labeled sections with required markers,
exact-level dropdowns, date/number controls, client-side checks,
loading/saving/success/error states, unsaved-changes hint, and age /
employment previews. Dashboard shows a profile-state banner linking to
Profile; scoring flow untouched.

## 12. Provenance Handling

Only USER provenance is populated (profile rows). No DOCUMENT or DERIVED
feature records are created anywhere in Phase 3; the financial-features
table remains empty by design.

## 13. Tests

`tests/test_profile_completeness.py` (12 new): empty/partial/complete
completeness values, readiness transitions, scoring-ready-always-false
with zero prediction rows, encoder-level parity test, malformed/future/
unreasonable DOB, future employment start, non-positive income,
negative counts, unknown categoricals, envelope shape. Phase 2 profile
tests updated for the envelope (missing-profile and isolation cases now
assert 200-envelope semantics). Full suite: **51 passed**.

## 14. Build Result

`npm run build` succeeds. Live verification: register -> 0/18
NOT_READY -> invalid occupation 422 -> partial 6/18 PARTIALLY_READY ->
full 18/18 READY with scoring false -> future DOB 422; `/health` 200;
empty `/predict` still 422.

## 15. Limitations

SQLite `create_all` (no migrations); readiness UI is honest but static
until document phases land; categorical dropdowns freeze current
encoder levels (encoder retraining would require resync, guarded by the
parity test); demo seed unchanged.

## 16. What Phase 4 Will Implement

Document upload with source metadata, file storage references, review
flags, and per-user document listing -- writing into the existing
`documents` table via the existing metadata endpoints; no extraction
or parsing yet.

IMPLEMENTED IN PHASE 3: everything in Sections 3-14.
PLANNED FOR PHASE 4+: documents/OCR/parsing/engineering/scoring/SHAP.
