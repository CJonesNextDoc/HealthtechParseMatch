# HealthtechParseMatch

This project was bootstrapped from: `C:\repo\scaffold\fastapi_demo`.

# healthtech_parse_match

Generated FastAPI scaffold.
## Development Setup

```bash
# Create virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Unix/Mac:
source .venv/bin/activate

# Install dependencies
pip install -e .[dev]
```

## CI/CD Pipeline

This project uses GitHub Actions for continuous integration and deployment.

### Automated Checks
- **Code Quality**: Black formatting, Ruff linting, mypy type checking
- **Security**: Bandit security scanning, Safety dependency checks
- **Testing**: pytest with coverage reporting (PostgreSQL test database)
- **Build**: Package building and validation

### Local Validation
Run the same checks locally before committing:

```bash
# Run all validation checks
python scripts/validate.py

# Auto-fix formatting and linting issues
python scripts/validate.py --fix
```

### Pre-commit Hooks
Install pre-commit hooks for automatic validation:

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

### Workflows
- **CI**: Runs on every push/PR to `main` and `dev` branches
- **Release**: Automated PyPI publishing and production deployment
- **Dependabot**: Weekly dependency updates

## Run Application

```bash
uvicorn app.main:app --reload
```

## Observability Stack (Docker + Prometheus + Grafana)

The application includes a complete observability stack for monitoring API performance, request rates, and error tracking.

### Quick Start with Observability

```bash
# 1. Start the observability stack (Prometheus + Grafana)
docker-compose up -d

# 2. In another terminal, start the FastAPI application
uvicorn app.main:app --reload

# 3. Access the services:
# - FastAPI API: http://localhost:8000
# - FastAPI Docs: http://localhost:8000/docs
# - Prometheus: http://localhost:9090
# - Grafana: http://localhost:3000 (admin/admin)
```

### Grafana Dashboard

A pre-configured dashboard is available at `docs/grafana_dashboard.json` with 8 monitoring panels:

- **Request Rate (per second)** - Real-time API call frequency
- **Success Rate (%)** - API reliability metrics
- **Request Latency Percentiles** - P50, P95, P99 response times
- **Total Requests by Method** - Usage statistics table
- **Error Rate Over Time** - Failure trend monitoring
- **Current Success Rate** - Live reliability indicator
- **Average Latency (P95)** - Performance threshold monitoring
- **Total Requests (24h)** - Volume tracking

### Generating Metrics

To populate the dashboard with data:

```bash
# Make several patient match requests to generate metrics
for i in {1..5}; do
  curl -X POST http://localhost:8000/patient/match \
    -H "Content-Type: application/json" \
    -d '{"dob":"1990-01-01","zip":"12345"}'
done
```

### Docker Services

- **Prometheus** (port 9090): Scrapes metrics from FastAPI `/health/metrics` endpoint
- **Grafana** (port 3000): Visualizes metrics with pre-configured dashboard
- **FastAPI** (port 8000): Main application with Prometheus metrics instrumentation

### Configuration Files

- `docker-compose.yml` - Container orchestration
- `prometheus.yml` - Prometheus scraping configuration
- `docs/grafana_dashboard.json` - Grafana dashboard definition
- `docs/grafana_setup.md` - Detailed setup instructions

## Test

```bash
pytest
```

# Healthtech Parse+Match Scaffold (DOB/ZIP + tie‑breakers) — v1

A starter repo plan + reference code to revive our scaffold and add robust DOB/ZIP parsing from STT, multi‑signal patient disambiguation, and evals. Aligned with your stack (FastAPI, SQLAlchemy 3.x async, Postgres/pgvector optional, Keycloak‑ready).

---

## 0) Goals
- **Parse** DOB & ZIP (from noisy STT) deterministically and fast, with ML/LLM fallback only when needed.
- **Match** against an EHR (FHIR first) using **DOB + ZIP** and tie‑breakers: **phone last4**, **last‑name prefix** (and optionally first‑name initial).
- **Disambiguate** multiple candidates via a transparent scoring policy.
- **Evaluate** with your existing real‑world DOB dataset (drop‑in JSONL) + CI friendly metrics.
- **Audit/PHI**: log only redacted inputs; never store raw transcripts.

---

## 1) Repo layout
```
healthtech-parse-match/
├─ app/
│  ├─ main.py
│  ├─ core/
│  │  ├─ config.py
│  │  └─ redaction.py
│  ├─ services/
│  │  ├─ dob_zip_parser.py
│  │  ├─ matcher.py
│  │  └─ scoring.py
│  ├─ clients/
│  │  └─ fhir_client.py
│  ├─ routers/
│  │  ├─ dob_router.py        # custom endpoint
│  │  └─ patient_router.py      # custom endpoint
│  └─ models/                   # if we persist anything (audit only)
│     ├─ __init__.py
│     └─ audit.py
├─ tests/
│  ├─ data/
│  │  └─ dob_cases.jsonl        # your real STT set (see schema below)
│  ├─ test_dob_parser.py
│  ├─ test_matcher.py
│  └─ conftest.py
├─ scripts/
│  └─ run_eval.py
├─ pyproject.toml
├─ .env.example
└─ README.md
```

---

## 2) Endpoints (OpenAPI summary)
**POST /parse/dob-zip** → parse DOB + ZIP from free‑text (STT).
Request: `{ "text": "…", "date_floor": 1905, "date_ceiling": 2025 }`
Response: `{ "dob_candidates": [{"iso":"1984-06-05","score":0.92}], "zip_candidates": [{"zip":"85719","score":0.9}] }`

**POST /patient/match** → query EHR and resolve a unique patient.
```json
{
  "dob": "1984-06-05",
  "zip": "85719",
  "last4_phone": "1234",         // optional, boosts tie-break
  "last_name_prefix": "smi",      // optional, boosts tie-break
  "first_initial": "j"            // optional
}
```
Response (examples):
- Unique: `{ "status":"unique", "patient_id":"abc123", "confidence":0.96, "reasons":["dob","zip","last4"] }`
- Ambiguous: `{ "status":"ambiguous", "candidates":[{"patient_id":"a1","confidence":0.78},{"patient_id":"b2","confidence":0.74}], "next_best_signal":"last4_phone" }`
- None: `{ "status":"none" }`

**POST /eval/run** → run parser & matcher evals over tests/data, return metrics.

> Security: wire to Keycloak later (bearer auth, roles). For now, keep behind a private network.

---

## 3) Config & Env
`.env.example`
```
APP_ENV=local
FHIR_BASE_URL=https://ehr.example.com/fhir
FHIR_AUTH_TYPE=bearer
FHIR_BEARER_TOKEN=REDACT_ME
LOG_LEVEL=INFO
```

---

## 4) Core code

### app/core/redaction.py
```python
import re

def redact_text(s: str) -> str:
    # Remove emails, phones, SSN-like, keep dates/zip masked in logs
    s = re.sub(r"[\w\.-]+@[\w\.-]+", "[EMAIL]", s)
    s = re.sub(r"\b\d{3}[-.\s]?\d{2,3}[-.\s]?\d{4}\b", "[PHONE]", s)
    s = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[SSN]", s)
    return s
```

### app/services/dob_zip_parser.py
(Deterministic, fast. Accepts a single transcript.)
```python
from datetime import date
from typing import List, Tuple
from .parser_primitives import normalize_spaces, words_to_digits_seq, pick_year_from_two_digits, MONTHS, ORDINAL_WORD
import re

def parse_dob_candidates(text: str, *, today: date | None = None,
                          min_age: int = 0, max_age: int = 120) -> List[Tuple[str, float]]:
    """Return [(iso, score)] sorted desc."""
    # (Paste in the robust version we iterated earlier; trimmed here for brevity.)
    ...

def extract_zip_candidates(text: str) -> List[Tuple[str, float]]:
    # numeric + spelled digits + dash handling
    ...
```
> **Note**: We’ll import your existing DOB test corpus to harden edge cases.

### app/services/scoring.py
```python
from dataclasses import dataclass

@dataclass
class MatchSignals:
    dob: bool
    zip_exact: bool
    zip_prefix: bool
    last4_match: bool
    last_name_prefix: bool
    first_initial: bool

# Transparent weights (tune in evals)
WEIGHTS = {
    "dob": 1.00,
    "zip_exact": 0.60,
    "zip_prefix": 0.20,
    "last4_match": 0.30,
    "last_name_prefix": 0.25,
    "first_initial": 0.10,
}

def score(signals: MatchSignals) -> float:
    s = 0.0
    for k, v in signals.__dict__.items():
        if v:
            s += WEIGHTS[k]
    return round(min(s, 1.0), 2)
```

### app/services/matcher.py
```python
from .scoring import MatchSignals, score
from typing import Any, Dict, List

class Candidate(dict):
    # expected keys: patient_id, birthDate (YYYY-MM-DD), postalCode, telecom_last4?, family?, given?
    pass

class MatchResult(dict):
    pass

class PatientMatcher:
    def __init__(self, fhir_client):
        self.fhir = fhir_client

    async def match(self, dob: str, zip: str, last4_phone: str | None = None,
                    last_name_prefix: str | None = None, first_initial: str | None = None) -> MatchResult:
        # 1) Retrieve initial candidate set via FHIR search
        candidates = await self.fhir.search_patients(dob=dob, zip=zip)
        if not candidates:
            return {"status": "none"}

        # 2) Score candidates
        scored: List[tuple[float, Candidate]] = []
        for c in candidates:
            sig = MatchSignals(
                dob=(c.get("birthDate") == dob),
                zip_exact=(c.get("postalCode") == zip),
                zip_prefix=(c.get("postalCode", "").startswith(zip[:3])),
                last4_match=(last4_phone and c.get("telecom_last4") == last4_phone) or False,
                last_name_prefix=(last_name_prefix and c.get("family", "").lower().startswith(last_name_prefix.lower())) or False,
                first_initial=(first_initial and c.get("given", "").lower()[:1] == first_initial.lower()) or False,
            )
            scored.append((score(sig), c))

        scored.sort(key=lambda x: x[0], reverse=True)

        # 3) Decide unique / ambiguous
        if scored and (len(scored) == 1 or (scored[0][0] - scored[1][0] >= 0.15 and scored[0][0] >= 0.8)):
            best = scored[0]
            return {
                "status": "unique",
                "patient_id": best[1]["patient_id"],
                "confidence": best[0],
                "reasons": [k for k, v in MatchSignals(**{**{f:False for f in MatchSignals.__annotations__.keys()}, **{}}).__dict__.items() if v]
            }
        # else ambiguous
        return {
            "status": "ambiguous",
            "candidates": [{"patient_id": c[1]["patient_id"], "confidence": c[0]} for c in scored[:5]],
            "next_best_signal": "last4_phone" if any(not c[1].get("telecom_last4") for c in scored[:3]) else "last_name_prefix"
        }
```

### app/clients/fhir_client.py
```python
import httpx
from typing import List, Dict

class FHIRClient:
    def __init__(self, base_url: str, token: str | None = None):
        self.base_url = base_url.rstrip('/')
        self.token = token

    async def search_patients(self, *, dob: str, zip: str) -> List[Dict]:
        # Minimal FHIR Patient search: birthdate + postal-code; adapt per EHR
        # GET /Patient?birthdate=eqYYYY-MM-DD&address-postalcode=NNNNN
        params = {"birthdate": f"eq{dob}", "address-postalcode": zip}
        headers = {"Accept": "application/fhir+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{self.base_url}/Patient", params=params, headers=headers)
            r.raise_for_status()
            bundle = r.json()
        out = []
        for e in bundle.get("entry", []):
            p = e.get("resource", {})
            telecoms = ''.join(t.get("value", "") for t in p.get("telecom", []) if t.get("system") == "phone")
            last4 = telecoms[-4:] if telecoms and telecoms[-4:].isdigit() else None
            postal = None
            for addr in p.get("address", []) or []:
                if "postalCode" in addr:
                    postal = addr["postalCode"]
                    break
            out.append({
                "patient_id": p.get("id"),
                "birthDate": p.get("birthDate"),
                "postalCode": postal,
                "telecom_last4": last4,
                "family": (p.get("name", [{}])[0].get("family") if p.get("name") else None),
                "given": (p.get("name", [{}])[0].get("given", [None])[0] if p.get("name") else None),
            })
        return out
```

### app/routers/dob_router.py
```python
from fastapi import APIRouter
from pydantic import BaseModel
from ..services.dob_zip_parser import parse_dob_candidates, extract_zip_candidates

router = APIRouter(prefix="/parse", tags=["parse"])

class ParseIn(BaseModel):
    text: str
    date_floor: int | None = None
    date_ceiling: int | None = None

@router.post("/dob-zip")
async def parse_dob_zip(payload: ParseIn):
    dob = parse_dob_candidates(payload.text)
    zc = extract_zip_candidates(payload.text)
    return {"dob_candidates": [{"iso": d[0], "score": d[1]} for d in dob],
            "zip_candidates": [{"zip": z, "score": 0.9} for z in zc]}
```

### app/routers/patient_router.py
```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from ..clients.fhir_client import FHIRClient
from ..services.matcher import PatientMatcher
import os

router = APIRouter(prefix="/patient", tags=["patient"])

class MatchIn(BaseModel):
    dob: str
    zip: str
    last4_phone: str | None = None
    last_name_prefix: str | None = None
    first_initial: str | None = None

@router.post("/match")
async def match_patient(payload: MatchIn):
    fc = FHIRClient(base_url=os.environ.get("FHIR_BASE_URL", ""), token=os.environ.get("FHIR_BEARER_TOKEN"))
    matcher = PatientMatcher(fc)
    return await matcher.match(**payload.model_dump())
```

### app/main.py
```python
from fastapi import FastAPI
from .routers.dob_router import router as dob_router
from .routers.patient_router import router as patient_router

app = FastAPI(title="Healthtech Parse+Match API")
app.include_router(dob_router)
app.include_router(patient_router)
```

---

## 5) Tests & Eval Harness

### tests/data/dob_cases.jsonl (schema)
Each line:
```json
{"text":"june fifth nineteen eighty four","dob_iso":"1984-06-05"}
```
- Put your **hundreds of real STT** lines here; add tricky ones (ordinals, "oh"=0, EU dates, etc.).

### tests/test_dob_parser.py
```python
import json, pathlib
from app.services.dob_zip_parser import parse_dob_candidates

DATA = pathlib.Path(__file__).parent / "data" / "dob_cases.jsonl"

def test_dob_parser_precision():
    total = 0
    correct = 0
    with DATA.open() as f:
        for line in f:
            total += 1
            rec = json.loads(line)
            cands = parse_dob_candidates(rec["text"])  # returns [(iso, score)]
            pred = cands[0][0] if cands else None
            if pred == rec["dob_iso"]:
                correct += 1
    assert correct / total >= 0.95
```

### tests/test_matcher.py
```python
import pytest
from app.services.matcher import PatientMatcher

class FakeFHIR:
    async def search_patients(self, *, dob, zip):
        return [
            {"patient_id":"a1","birthDate":dob,"postalCode":zip,"telecom_last4":None,"family":"Smith","given":"Jane"},
            {"patient_id":"b2","birthDate":dob,"postalCode":zip,"telecom_last4":"1234","family":"Smythe","given":"John"},
        ]

@pytest.mark.asyncio
async def test_disambiguation_uses_last4():
    m = PatientMatcher(FakeFHIR())
    res = await m.match(dob="1984-06-05", zip="85719", last4_phone="1234")
    assert res["status"] == "unique" and res["patient_id"] == "b2"
```

### scripts/run_eval.py
```python
# CLI to run parser eval and print precision/recall by pattern
# (stubbed; fill in metrics you care about)
```

---

## 6) README (quick start)

```
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env
uvicorn app.main:app --reload
```
Open: `http://127.0.0.1:8000/docs` → try `/parse/dob-zip` and `/patient/match`.

Run tests:
```
pytest -q
```

---

## 7) Notes & Next Steps
- **Bring your dataset**: drop the JSONL; we’ll iterate until ≥95% accuracy (or your target) on DOB parsing.
- **Expand signals**: allow middle initial, street prefix if available; add fuzzy family matching w/ metaphone for STT misspellings.
- **LLM fallback (optional)**: constrained JSON extraction for truly weird utterances; only used when deterministic parser yields 0 candidates.
- **Keycloak**: add bearer auth and roles (`viewer`, `agent`, `admin`).
- **Audit table**: persist `action`, `redacted_input`, `result`, `latency_ms` only; never raw PHI.
- **pgvector** (if we later do RAG): optional module for policy/runbook retrieval, not required for parse+match.
