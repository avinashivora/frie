# FRIE -- Code Quality & Maintainability

## S3 Lab Work -- Codebase Quality, Maintainability & Engineering Practices

Audit-only report. No application, model, scoring, dataset, contract, or
behaviour changes were made for this audit. Every finding below is supported
by inspection of the repository at `D:/frie/Frontend/Frie` (the Git
repository root). Findings are classified PASS, MINOR ISSUE, MODERATE ISSUE,
or MAJOR ISSUE as defined at the end of this document.

## 1. Introduction

This document audits the FRIE codebase against S3 code-quality and
maintainability expectations: organization, modularity, separation of
concerns, naming, duplication, error handling, configuration, dependencies,
documentation, testing, type safety, and ML integration quality. The audited
system is the dataset-backed Individual prototype (React + TypeScript + Vite
frontend, FastAPI backend, saved XGBoost V2 pipeline, 15 pytest tests). The
goal is an evidence-based record of what is already good, what is honestly
limited, and which improvements are actually justified -- without redesigning
the application.

## 2. Codebase Structure

Repository root: `D:/frie/Frontend/Frie` (105 tracked files; the external
`D:/frie/Model Train` dataset and `D:/frie/*.py` data scripts are outside
version control and outside this audit's scope).

| Area | Path | Status |
|---|---|---|
| Frontend application | `src/app/App.tsx`, `src/main.tsx` | Present |
| Frontend API layer | `src/services/api.ts`, `src/services/devSampleFeatures.ts` | Present |
| Frontend state hook | `src/hooks/usePrototypeFrieScore.ts` | Present |
| Generated UI kit (unused) | `src/app/components/ui/` | Present, unrendered |
| Backend routes | `backend/app/api/routes/` | Present |
| Backend core | `backend/app/core/` | Present |
| Backend schemas | `backend/app/schemas/` | Present |
| Backend services | `backend/app/services/` | Present |
| Backend tests | `backend/tests/` | Present |
| Backend dev scripts | `backend/scripts/` | Present |
| Model artifacts | `backend/models/` | Present |
| Documentation | `docs/` | Present |

Status: PASS. Responsibilities are logically separated into
frontend/backend, and within the backend into routes, schemas, services,
core, tests, models, and scripts.

## 3. Modularity & Separation of Concerns

Backend modules are small and single-purpose (lines of code, docstrings
excluded from the count basis): `health.py` 13, `config.py` 25,
`prediction.py` (route) 36, `feature_contract.py` 39, `prediction.py`
(schema) 40, `feature_service.py` 47, `prediction_service.py` 59,
`main.py` 58, `test_prediction.py` 154. Evidence of separation:

- `backend/app/api/routes/prediction.py` handles HTTP only and delegates to
  the prediction service; it contains no model mathematics.
- `backend/app/schemas/prediction.py` owns validation via a dynamically
  built Pydantic model; it contains no routing or inference.
- `backend/app/services/feature_service.py` builds the named one-row
  DataFrame; it contains no HTTP or model code.
- `backend/app/services/prediction_service.py` owns the loaded pipeline and
  inference; it contains no HTTP code.
- `backend/app/core/feature_contract.py` is the single source of the
  98-feature contract, read from the model config file.
- Frontend: all four `fetch()` call sites live in `src/services/`
  (`api.ts` lines 55/70, `devSampleFeatures.ts` lines 70/99); no UI
  component calls `fetch` directly. `usePrototypeFrieScore` owns the
  idle/loading/ready/error state machine.

Status: PASS for both layers. The one structural exception is the size of
`src/app/App.tsx` (1831 lines, ~30 component definitions), assessed
separately below; it does not indicate tangled responsibilities, since data
flow still passes through the service and hook layers.

## 4. Naming & Readability

Inspected: variables, functions, classes, files, constants, and API names
across `backend/app`, `backend/tests`, `src/services`, `src/hooks`,
`src/app/App.tsx`, and `vite/`.

- Names are descriptive and consistent: `usePrototypeFrieScore`,
  `loadDevSampleRecord`, `buildCompleteFeatureRow`, `FeatureContractError`,
  `FrieApiError`, `frieDevSamplePlugin`, `measure_predict_latency.py`.
- Backend modules carry docstrings (33 docstring delimiters across
  `backend/app`); frontend sections carry banner comments; no TODO, FIXME,
  XXX, HACK, `debugger`, `alert()`, `innerHTML`, or `eval()` markers were
  found in active code (the only `print()` calls are in the dev-only
  latency probe, which is appropriate).
- No unclear abbreviations or misleading names were found in active code.

Status: PASS, with one cosmetic MINOR ISSUE: the Figma-generated asset
`src/imports/RightSplit/svg-qcu94pqgtn.ts` keeps an opaque hash filename
(harmless; it is imported correctly).

## 5. Code Duplication

Searched for duplicated API calls, validation logic, feature construction,
formatting, constants, and UI logic:

- API calls: centralized; the four `fetch()` sites each serve a distinct
  endpoint and share the `FrieApiError` type.
- Validation: single contract (`feature_contract.py` + Pydantic schema);
  no parallel validation copies.
- Feature construction: one function (`build_model_input`); one row loader
  per record kind.
- Formatting: shared helpers (`fmt`, `fmtFeature`, `pctFeature`,
  `yearsFeature`, `decimalFeature`); shared `Stat`, `CompBar`,
  `PrototypeScorePanel` presentation components.
- No repeated calculations of scores or levels; the frontend never
  recomputes `reliability_level` for live predictions.

Status: PASS, with one MINOR ISSUE: legacy threshold helpers
(`scoreColor`, `scoreLabel`, `scoreBadgeCls` with the old 85/70/55 bands)
remain in the file but are reachable only from dead components; they
duplicate threshold knowledge that could confuse a future reader.

## 6. Error Handling

Frontend (`src/services/api.ts`, `src/hooks/usePrototypeFrieScore.ts`,
`CustomerSelector`, `PrototypeScorePanel`, score-page badge): network
failure, unhealthy model, missing sample data, and prediction failure each
produce a typed error state; no path renders a previous or hardcoded score
after an error (verified by render-graph inspection and live failure test).

Backend (`backend/app/main.py`, routes, services): missing/unexpected
fields, wrong types, blank categoricals, non-finite numbers, malformed
JSON, unknown sample ids, unloaded model, and degraded health map to 422,
404, or 503 as appropriate; the NaN-serialization 500 found in Phase 8 was
fixed at the error-serialization layer with 15-test coverage.

Status: PASS. Errors are controlled, understandable, and never silent.

## 7. Configuration Management

Configuration is centralized and environment-aware:

- Frontend API URL: `VITE_API_BASE_URL` (`.env.development`,
  `.env.example`); no hard-coded production URL in `src/services/api.ts`.
- Backend: `backend/app/core/config.py` resolves model paths relative to
  the module and reads CORS origins from `FRIE_CORS_ORIGINS`
  (default `http://localhost:5173,http://127.0.0.1:5173`).
- Model contract: `backend/models/frie_model_config*.json` (feature names,
  groups, target, counts); V2 metadata config records parameters, metrics,
  and SHA256.
- Secrets: none in backend source; the only credential in the repo is the
  documented demo login `FRIE123` (prototype only, no real authentication
  is claimed).
- Ignore rules: root `.gitignore` (dependencies, build output, local env,
  logs) and `backend/.gitignore` (venv, bytecode, pytest cache).

Status: PASS, with one MINOR ISSUE: `.env.development` is committed. It
contains only a localhost URL (no secret), so this is a convention note
rather than a risk.

## 8. Dependency Management

Backend `backend/requirements.txt` (10 pinned packages): all actively used
-- FastAPI, Uvicorn, Pydantic, Joblib, NumPy, Pandas, scikit-learn, XGBoost
in the serving path; Pytest and httpx for testing; Starlette/pydantic-core
arrive transitively. Status: PASS.

Frontend `package.json`: actively used by the running app are React,
React-DOM, Recharts (Financial Analysis chart), Lucide React, Tailwind CSS
(plus Vite tooling). Roughly thirty Figma-generated packages (MUI, Radix
set, React Router, Motion, drag-and-drop, cmdk/embla/sonner family and
related utilities) are installed but have zero imports outside the
unrendered `src/app/components/ui/` library. Production-bundle inspection
confirms zero runtime effect (no legacy/mock/dev strings in `dist`
output). Status: MINOR ISSUE -- install-time footprint and potential
reader confusion only; removal must not be automatic and would need
regression testing, so it is recorded but not prescribed here.

## 9. Documentation

Present: `docs/S3_NFR_Evidence.md` (measured NFR results),
`docs/S3_Framework_Justification.md` (+ validated `.docx`), backend
docstrings, frontend section banners, `backend/scripts` usage text, and
setup instructions in `backend/README.md`.

Gaps found:

- Root `README.md` is untouched Figma boilerplate ("Define app
  requirements"); it does not say what FRIE is or how to run, test, or
  predict. For team handover this is a MODERATE ISSUE.
- `backend/README.md` has two stale lines (states the frontend is
  "intentionally not connected" and references only V1 artifacts).
  MINOR ISSUE.
- `guidelines/Guidelines.md` is an empty generator template; the
  `src/imports/pasted_text/frie-app-spec.md` spec text and
  `src/imports/RightSplit/index.tsx` component are never imported.
  Collectively a MINOR ISSUE of generated leftovers.

## 10. Testing & Testability

`backend/tests/test_prediction.py` (154 lines): module-scoped fixture
loading the first complete dataset row read-only (skips cleanly when the
external file is absent); contract tests; service-level rejection tests;
endpoint tests for valid/invalid/non-finite/categorical/boolean/target-
as-input payloads; schema and reliability-equality assertions; repeat-
consistency test; model-unavailable 503 test. Verification for this audit:
`pytest -q` -> 15 passed. No frontend unit-test framework is configured
(`package.json` scripts are `build`/`dev` only); verification of the UI
rests on production builds, dev-server module checks, and live API tests.
Status: PASS for backend testability, with the frontend-test gap folded
into the script-tooling note below.

## 11. Type Safety

Active TypeScript (`src/app/App.tsx`, `src/services`, `src/hooks`,
`vite/`) contains zero `: any` annotations and zero `as any`/`as unknown`
casts, including the generated UI library and import shims. API shapes,
hook states, record metadata, and indicator maps are explicitly typed, and
the four reliability levels form a closed union shared with the backend
response. Status: PASS, with one MINOR process note: the repo defines no
standalone `tsc`, lint, or frontend-test npm scripts, so type and style
checking are limited to the Vite build's transpile step.

## 12. Backend Code Quality

The route -> schema -> service -> versioned-model layering described in
Section 3 holds under inspection: each file has one job, configuration is
centralized, the model loads once at startup, errors map to explicit HTTP
semantics, and the V1-to-V2 migration required changing only two filename
resolutions in `config.py` -- concrete evidence that adding another model
version is cheap. Status: PASS.

## 13. Frontend Code Quality

Active code (login, selector, dashboard, score page, analysis, layout,
gauge, stats, services, hook, dev plugin) is organized, typed, and free of
`any`/hacks; API logic is fully separated from presentation; demo-only
dataset access is isolated and eliminated from production bundles
(verified). Two honest qualifications:

- `src/app/App.tsx` (1831 lines) mixes roughly ten reachable components
  with roughly twelve unreachable legacy/role components in one file.
  Reachable logic is coherent, but file scale plus dead-code intermix
  raises the cost of navigation and the risk of accidental edits.
  MODERATE ISSUE. (Per audit scope, no split was performed.)
- Reachable-vs-unreachable accounting above is exact per render-graph
  grep; dead code is never rendered and is absent from the production
  bundle, so this is a maintainability observation, not a behavioural one.

## 14. ML Code Quality

- Pipeline: preprocessing plus regressor in one versioned joblib object;
  feature selection by contract names; column order handled explicitly.
  PASS.
- Versioning: mismatched V1 preserved untouched; verified V2 artifact
  plus metadata config with parameters, metrics, and SHA256. PASS.
- Leakage prevention: `frie_score` rejected as model input by schema and
  by test; evaluation uses held-out rows. PASS.
- Evaluation artifacts present (comparisons, predictions, importance
  files) with measured V2 metrics MAE 1.730576 / RMSE 2.144333 /
  R2 0.972064. PASS.
- Reproducibility gap: no training script exists in the repository, and
  the exact V2 reproduction procedure currently lives outside version
  control, so the model cannot be regenerated from repo contents alone.
  MODERATE ISSUE (recommendation only; no retraining performed).

## 15. Security-Related Code Quality

Evaluated implementation practices only; no production-security claims are
made. Strict validation with field rejection (tested), environment-driven
API URL and CORS with credentials off and minimal methods/headers,
no backend secrets, dev-only endpoints excluded from production bundles
(verified by bundle inspection), no unsafe file handling (fixed dataset
paths, no user-supplied paths), and the demo credential documented as
prototype-only. Status: PASS.

## 16. Code Quality Assessment Table

| Category | Status | Evidence | Recommendation |
|---|---|---|---|
| Project structure | PASS | `src/` vs `backend/`; api/core/schemas/services/tests/models/scripts; `docs/` | None |
| Backend modularity | PASS | Modules of 13-154 lines, one job each | None |
| Separation of concerns | PASS | Route/schema/service/contract split; all `fetch()` in `src/services/` | None |
| Naming and readability | PASS | Descriptive names; docstrings; zero TODO/hack markers | None |
| Duplication | PASS | Centralized calls, contract, formatting, components | Remove legacy threshold helpers when convenient (minor) |
| Error handling | PASS | 422/404/503 coverage; explicit UI error states; 15 tests | None |
| Configuration | PASS | Env-based URL/CORS; central `config.py`; model JSON contracts | Consider ignoring `.env.*` by convention (minor) |
| Backend dependencies | PASS | All 10 pinned packages used | None |
| Frontend dependencies | MINOR ISSUE | ~30 installed packages with zero active imports; zero bundle effect verified | Prune carefully with regression testing (future) |
| Documentation | MODERATE ISSUE | Root README is boilerplate; backend README has 2 stale lines | Write onboarding README; refresh backend README |
| Testing | PASS | 15/15 pytest; deterministic fixtures | None |
| Type safety | PASS | Zero `any`/unsafe casts; typed contracts | Consider `tsc`/lint scripts (minor) |
| Backend maintainability | PASS | V1-to-V2 needed a 2-line config change | None |
| Frontend maintainability | MODERATE ISSUE | 1831-line `App.tsx` mixing active and dead components | Split active views from legacy code (future) |
| ML quality | MODERATE ISSUE | Versioning/leakage/evaluation pass; no training script in repo | Commit the reproduction procedure (future) |
| Security practices | PASS | Validation, CORS, no secrets, dev separation verified | None |

## 17. Identified Issues

MINOR ISSUES (7):

1. Legacy threshold helpers (`scoreColor`, `scoreLabel`, `scoreBadgeCls`)
   retained for dead components only (`src/app/App.tsx` lines ~108-125).
2. Opaque Figma asset filename
   (`src/imports/RightSplit/svg-qcu94pqgtn.ts`).
3. `.env.development` committed (localhost URL only; no secret).
4. Two stale lines in `backend/README.md` (frontend "not connected",
   V1-only artifact list).
5. No `tsc`, lint, or frontend-test npm scripts.
6. Generated leftovers: empty `guidelines/Guidelines.md` template,
   unimported `src/imports/pasted_text/frie-app-spec.md` and
   `src/imports/RightSplit/index.tsx`.
7. Unused frontend dependency footprint (~30 packages; verified
   zero runtime effect).

MODERATE ISSUES (3):

1. `src/app/App.tsx` (1831 lines) mixes reachable and unreachable
   components, raising navigation and edit risk.
2. Root `README.md` is Figma boilerplate with no onboarding content
   (what FRIE is, how to run/test/predict).
3. No training/reproduction procedure in version control, so V2 cannot
   be regenerated from repo contents alone.

MAJOR ISSUES: none identified. No finding affects correctness,
reliability, or security of the running prototype.

## 18. Improvement Priorities

### Priority 1 -- Should Fix

1. Write a proper root `README.md` (project purpose, run instructions
   for frontend/backend, test commands, artifact locations).
2. Commit the exact V2 reproduction procedure (script plus pinned
   environment note) so the model is regenerable from the repo.
3. Resolve the committed editor lock file (`docs/~$_Framework_Justification.md`,
   currently showing as an unstaged deletion) so the tree is clean.

### Priority 2 -- Good to Improve

1. Split `src/app/App.tsx`: move reachable views first, then remove or
   isolate legacy role components behind a clear marker.
2. Refresh the two stale `backend/README.md` lines.
3. Add `typecheck`/`lint` npm scripts (and run them in future verification).
4. Carefully prune demonstrably unused frontend dependencies with a
   rebuild plus smoke test per removal batch.

### Priority 3 -- Optional / Future

1. Rename the hashed Figma asset; remove the empty guidelines template.
2. Adopt `.env.*` ignore conventions for local files.
3. Production-bundle size budgets and frontend unit tests if the
   prototype grows toward production.

No improvement was implemented during this audit.

## 19. Verification Results

- Backend tests: `pytest -q` -> 15 passed, 1 warning (same as the
  project-verified result).
- Frontend build: `npm run build` -> success (~5.9 s).
- Git diff check: `git diff --check` -> exit 0.
- If any had failed, the failure would be reported here with its
  pre-existing status; all three passed, so no such note is needed.

## 20. Conclusion

The FRIE implementation demonstrates the qualities expected of an
academic S3 prototype: a logically structured and genuinely modular
backend, centralized validation and configuration, disciplined error
handling with test coverage, type-safe frontend service layers, clean
separation of dev-only dataset access from production output, and
versioned ML artifacts with leakage controls. The honest limitations are
the single-file frontend mixing live and legacy components, onboarding
documentation gaps, an unused dependency footprint, and a missing
in-repo training procedure -- all recorded above as moderate or minor
issues with proportionate recommendations. No major issue was found.

## Code Quality Assessment

The current implementation demonstrates the qualities expected for an
academic S3 prototype. Thirteen assessed areas pass on evidence, seven
minor issues and three moderate issues are documented with file-level
references, and no major issue was identified. The codebase is
maintainable in its present research scope provided the Priority 1 items
(onboarding documentation, reproducible training procedure, and a clean
tree) are addressed as follow-up work. No official rubric score is
claimed here, as the rubric definition was not part of the inspected
materials.
