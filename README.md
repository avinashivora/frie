# FRIE

FRIE (Financial Reliability Intelligence Engine) is an India-centric financial intelligence prototype. It combines credit, affordability, cash-flow, resilience, commitment, and spending evidence into a transparent assessment that can complement human financial decision-making.

The application uses a deterministic six-dimension score. It is a prototype decision-support tool, not a validated default predictor or an automated lending or insurance decision system.

## GitHub About

**Description (216 characters):**

> India-centric financial reliability prototype with deterministic six-dimension scoring, separate loan and insurance profiles, transparent data coverage, and a React and FastAPI application for human decision support.

**Suggested topics:** `financial-reliability`, `fintech`, `credit-assessment`, `financial-inclusion`, `deterministic-scoring`, `decision-support`, `fastapi`, `react`, `typescript`, `india`

## What it does

- Accepts profile information and reviewed financial documents or bank transaction data.
- Builds normalized financial features while preserving missing information.
- Calculates six dimension scores from 0 to 100 and adds available dimension scores into the FRIE Base Score, up to 600.
- Calculates separate Neutral, Loan, and Insurance profile scores out of 100.
- Reports data coverage, dimension status, and qualitative confidence.
- Saves assessments and serves the latest assessment and history through an authenticated API.

## Run locally

Prerequisites: Python 3.12, Node.js 20 or later, and npm. OCR for scanned documents uses PaddleOCR and may download its models the first time it runs.

### 1. Start the backend

In PowerShell, from the repository root:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -c "from app.db.session import init_db; init_db()"
python -m scripts.migrate_frie6d
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The API runs at `http://127.0.0.1:8000`. Interactive API documentation is at `http://127.0.0.1:8000/docs`.

### 2. Start the frontend

Open a second terminal at the repository root:

```powershell
npm ci
Copy-Item .env.example .env.local
npm run dev -- --host localhost --port 5173
```

Open `http://localhost:5173`. The local frontend configuration points to the backend at `http://127.0.0.1:8000`.

### Run checks and the scoring demo

From `backend/` with its virtual environment active:

```powershell
python -m compileall app scripts tests
python -m pytest
python scripts/demo_frie6d.py
```

The reproducible demo reads `data/frie_synthetic_1000_v22.csv` from the repository root. The dataset is synthetic and supports execution and methodology checks, not predictive-accuracy claims.

## Project documentation

- [Technical guide](docs/FRIE_TECHNICAL_GUIDE.md) — architecture, scoring, API, data handling, persistence, and validation.
- [FRIE proposal](docs/FRIE.docx) — project purpose, intended scope, and research motivation.
- [Project delivery plan](docs/FRIE_Project_Delivery_Plan.docx) — milestone schedule.

## Scoring scope

The six-dimension deterministic engine is authoritative. Legacy eight-indicator calculations remain for compatibility and recommendations; experimental or legacy ML artifacts are not part of the authoritative scoring flow. FRIE does not claim predictive accuracy from synthetic scores.
