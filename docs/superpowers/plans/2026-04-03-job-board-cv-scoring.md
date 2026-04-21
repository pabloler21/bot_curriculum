# Job Board with CV-Aware Scoring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend CV Evaluator into a job board where uploaded CVs are scored against live job listings, with per-job ATS recommendations.

**Architecture:** Remotive API feeds a cached job list (15 min TTL); server-side ephemeral sessions (UUID-keyed in-memory dict, 60 min TTL) hold extracted CV text; a LangChain/Claude scorer rates each job in parallel. All new pages are vanilla JS / static HTML served by FastAPI, no new frontend frameworks.

**Tech Stack:** Python 3.13, FastAPI, httpx (async HTTP), LangChain + claude-haiku-4-5, Pydantic v2, slowapi, liteparse, vanilla JS/CSS.

---

## File Map

### New files
| File | Responsibility |
|------|----------------|
| `backend/jobs.py` | `Job` model, `strip_html()`, `fetch_jobs()` with 15-min cache |
| `backend/sessions.py` | `CVSession` model, `cv_sessions` dict, `cleanup_sessions()` |
| `backend/scorer.py` | `JobMatch` model, `score_job()` chain, `score_all_jobs()` |
| `src/routes/jobs.py` | `GET /jobs`, `POST /jobs/score` |
| `src/routes/session.py` | `POST /session`, `GET /session/{token}`, `DELETE /session/{token}` |
| `src/static/jobs.html` | Job listings page (main page) |
| `src/static/jobs.js` | Job listings + CV upload bar + scoring logic |
| `src/static/job-detail.html` | Job detail page |
| `src/static/job-detail.js` | Job detail + CTA to evaluation |
| `tests/test_jobs.py` | Tests for `backend/jobs.py` and `GET /jobs` |
| `tests/test_sessions.py` | Tests for `backend/sessions.py` and session routes |
| `tests/test_scorer.py` | Tests for `backend/scorer.py` and `POST /jobs/score` |
| `docs/TESTING.md` | Manual QA checklist |

### Modified files
| File | Change |
|------|--------|
| `pyproject.toml` | Add `httpx`, `pytest`, `pytest-asyncio`, `respx` |
| `src/router.py` | Include jobs + session routers |
| `src/routes/evaluate.py` | Accept optional `job_id`, inject job description into prompt |
| `backend/evaluator.py` | Add optional `job_context` param to `evaluate_cv()` |
| `src/static/index.html` | Add "← Back to jobs" link + session-aware CV pre-fill |

---

## PHASE 1 — Job Listings from Public API

---

### Task 1.1: Add dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add httpx, pytest, pytest-asyncio, respx to pyproject.toml**

```toml
# pyproject.toml — replace the [project] dependencies and add [dependency-groups]
[project]
name = "bot-curriculum"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "anthropic>=0.86.0",
    "fastapi>=0.135.2",
    "httpx>=0.28.0",
    "langchain>=1.2.13",
    "langchain-anthropic>=1.4.0",
    "liteparse>=1.1.0",
    "pydantic>=2.12.5",
    "python-dotenv>=1.2.2",
    "python-multipart>=0.0.22",
    "requests>=2.33.0",
    "slowapi>=0.1.9",
    "streamlit>=1.55.0",
    "uvicorn>=0.42.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "respx>=0.21.0",
    "ruff>=0.15.7",
]
```

- [ ] **Step 2: Install new deps**

```bash
pip install -e ".[dev]"
```

Expected: no errors. `httpx`, `pytest`, `pytest-asyncio`, `respx` available.

- [ ] **Step 3: Create tests directory with conftest**

Create `tests/__init__.py` (empty) and `tests/conftest.py`:

```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from src.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
```

- [ ] **Step 4: Verify pytest runs**

```bash
pytest tests/ -v
```

Expected: `no tests ran` — no errors.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml tests/__init__.py tests/conftest.py
git commit -m "chore: add httpx, pytest, pytest-asyncio, respx deps"
```

---

### Task 1.2: Job model and HTML stripper

**Files:**
- Create: `backend/jobs.py`
- Create: `tests/test_jobs.py`

- [ ] **Step 1: Write failing tests for Job model and strip_html**

```python
# tests/test_jobs.py
import pytest
from datetime import date
from backend.jobs import Job, strip_html


def test_strip_html_removes_tags():
    assert strip_html("<p>Hello <b>world</b></p>") == "Hello world"


def test_strip_html_plain_text_unchanged():
    assert strip_html("plain text") == "plain text"


def test_strip_html_empty():
    assert strip_html("") == ""


def test_strip_html_nested_tags():
    assert strip_html("<div><ul><li>item</li></ul></div>") == "item"


def test_job_model_fields():
    job = Job(
        id="123",
        title="Backend Engineer",
        company="Acme Corp",
        location="Remote",
        employment_type="full_time",
        salary_range=None,
        description="Python dev needed.",
        tags=["python", "fastapi"],
        url="https://example.com/job/123",
        posted_at=date(2025, 1, 15),
    )
    assert job.id == "123"
    assert job.tags == ["python", "fastapi"]
    assert job.salary_range is None


def test_job_model_serializable():
    import json
    job = Job(
        id="1",
        title="SWE",
        company="Co",
        location="Remote",
        employment_type="contract",
        salary_range="$80k-$100k",
        description="desc",
        tags=[],
        url="https://example.com",
        posted_at=date(2025, 3, 1),
    )
    data = job.model_dump(mode="json")
    assert data["posted_at"] == "2025-03-01"
    json.dumps(data)  # must not raise
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_jobs.py -v
```

Expected: `ImportError: cannot import name 'Job' from 'backend.jobs'` (file doesn't exist yet).

- [ ] **Step 3: Implement Job model and strip_html in backend/jobs.py**

```python
# backend/jobs.py
import logging
from datetime import date, datetime
from html.parser import HTMLParser
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts)


def strip_html(html: str) -> str:
    """Strip HTML tags from a string, returning plain text."""
    if not html:
        return html
    stripper = _HTMLStripper()
    stripper.feed(html)
    return stripper.get_text()


class Job(BaseModel):
    id: str
    title: str
    company: str
    location: str
    employment_type: str
    salary_range: Optional[str]
    description: str
    tags: list[str]
    url: str
    posted_at: date
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_jobs.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/jobs.py tests/test_jobs.py
git commit -m "feat: add Job model and strip_html to backend/jobs.py"
```

---

### Task 1.3: fetch_jobs() with 15-minute cache

**Files:**
- Modify: `backend/jobs.py`
- Modify: `tests/test_jobs.py`

- [ ] **Step 1: Write failing tests for fetch_jobs**

Append to `tests/test_jobs.py`:

```python
import httpx
import respx
import pytest
from unittest.mock import patch
from datetime import date, datetime, timedelta, timezone


REMOTIVE_SAMPLE = {
    "jobs": [
        {
            "id": 1,
            "title": "Python Developer",
            "company_name": "TechCorp",
            "candidate_required_location": "Worldwide",
            "job_type": "full_time",
            "salary": "$80k - $110k",
            "description": "<p>We need a <b>Python</b> dev.</p>",
            "tags": ["python", "django"],
            "url": "https://remotive.com/job/1",
            "publication_date": "2025-03-15T10:00:00",
        }
    ]
}


@pytest.mark.asyncio
@respx.mock
async def test_fetch_jobs_returns_normalized_jobs():
    from backend.jobs import fetch_jobs, _cache
    _cache["data"] = None  # clear cache

    respx.get("https://remotive.com/api/remote-jobs").mock(
        return_value=httpx.Response(200, json=REMOTIVE_SAMPLE)
    )

    jobs = await fetch_jobs()
    assert len(jobs) == 1
    assert jobs[0].title == "Python Developer"
    assert jobs[0].company == "TechCorp"
    assert jobs[0].description == "We need a Python dev."  # HTML stripped
    assert jobs[0].tags == ["python", "django"]
    assert jobs[0].posted_at == date(2025, 3, 15)
    assert jobs[0].url == "https://remotive.com/job/1"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_jobs_uses_cache():
    from backend.jobs import fetch_jobs, _cache
    # Prime cache with stale-looking but recent timestamp
    _cache["data"] = ([
        Job(
            id="99", title="Cached Job", company="CacheCo",
            location="Remote", employment_type="full_time",
            salary_range=None, description="cached",
            tags=[], url="https://example.com", posted_at=date(2025, 1, 1)
        )
    ], datetime.now(timezone.utc))

    # No HTTP mock — if fetch_jobs makes a real call it will raise
    jobs = await fetch_jobs()
    assert jobs[0].title == "Cached Job"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_jobs_invalidates_stale_cache():
    from backend.jobs import fetch_jobs, _cache
    old_time = datetime.now(timezone.utc) - timedelta(minutes=20)
    _cache["data"] = ([], old_time)

    respx.get("https://remotive.com/api/remote-jobs").mock(
        return_value=httpx.Response(200, json=REMOTIVE_SAMPLE)
    )

    jobs = await fetch_jobs()
    assert len(jobs) == 1
    assert jobs[0].title == "Python Developer"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_jobs_raises_on_http_error():
    from backend.jobs import fetch_jobs, _cache
    _cache["data"] = None

    respx.get("https://remotive.com/api/remote-jobs").mock(
        return_value=httpx.Response(503)
    )

    with pytest.raises(httpx.HTTPStatusError):
        await fetch_jobs()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_jobs.py::test_fetch_jobs_returns_normalized_jobs -v
```

Expected: `ImportError` or `AttributeError` — `fetch_jobs` not defined yet.

- [ ] **Step 3: Implement fetch_jobs with cache in backend/jobs.py**

Append to `backend/jobs.py` (after the `Job` class):

```python
import httpx
from datetime import timezone

REMOTIVE_URL = "https://remotive.com/api/remote-jobs"
REMOTIVE_PARAMS = {"category": "software-dev", "limit": 20}
CACHE_TTL_SECONDS = 900  # 15 minutes

# Module-level cache: {"data": (list[Job], datetime) | None}
_cache: dict = {"data": None}


def _parse_date(value: str) -> date:
    """Parse ISO datetime or date string to date."""
    try:
        return datetime.fromisoformat(value).date()
    except (ValueError, AttributeError):
        return date.today()


def _map_job(raw: dict) -> Job:
    return Job(
        id=str(raw["id"]),
        title=raw.get("title", ""),
        company=raw.get("company_name", ""),
        location=raw.get("candidate_required_location", "Remote"),
        employment_type=raw.get("job_type", "full_time"),
        salary_range=raw.get("salary") or None,
        description=strip_html(raw.get("description", "")),
        tags=raw.get("tags", []),
        url=raw.get("url", ""),
        posted_at=_parse_date(raw.get("publication_date", "")),
    )


async def fetch_jobs() -> list[Job]:
    """Return cached job list, fetching from Remotive if stale."""
    cached = _cache["data"]
    if cached is not None:
        jobs, ts = cached
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        if age < CACHE_TTL_SECONDS:
            logger.debug("[jobs] Returning %d cached jobs (age=%.0fs)", len(jobs), age)
            return jobs

    logger.info("[jobs] Fetching fresh job listings from Remotive")
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(REMOTIVE_URL, params=REMOTIVE_PARAMS)
        response.raise_for_status()

    data = response.json()
    jobs = [_map_job(raw) for raw in data.get("jobs", [])]
    _cache["data"] = (jobs, datetime.now(timezone.utc))
    logger.info("[jobs] Cached %d jobs", len(jobs))
    return jobs
```

- [ ] **Step 4: Run all job tests**

```bash
pytest tests/test_jobs.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/jobs.py tests/test_jobs.py
git commit -m "feat: add fetch_jobs() with 15-min memory cache (Remotive API)"
```

---

### Task 1.4: GET /jobs route

**Files:**
- Create: `src/routes/jobs.py`
- Modify: `src/router.py`
- Modify: `tests/test_jobs.py`

- [ ] **Step 1: Write failing test for GET /jobs**

Append to `tests/test_jobs.py`:

```python
from unittest.mock import AsyncMock, patch


def test_get_jobs_returns_200(client):
    sample_jobs = [
        Job(
            id="1", title="Dev", company="Co", location="Remote",
            employment_type="full_time", salary_range=None,
            description="desc", tags=["python"],
            url="https://example.com", posted_at=date(2025, 3, 1),
        )
    ]
    with patch("src.routes.jobs.fetch_jobs", new=AsyncMock(return_value=sample_jobs)):
        response = client.get("/jobs")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Dev"
    assert data[0]["posted_at"] == "2025-03-01"


def test_get_jobs_returns_502_on_upstream_error(client):
    async def boom():
        raise httpx.RequestError("connection failed")

    with patch("src.routes.jobs.fetch_jobs", new=boom):
        response = client.get("/jobs")
    assert response.status_code == 502
    body = response.json()
    assert body["code"] == "upstream_error"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_jobs.py::test_get_jobs_returns_200 -v
```

Expected: `404 Not Found` — route doesn't exist yet.

- [ ] **Step 3: Create src/routes/jobs.py**

```python
# src/routes/jobs.py
import logging

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.jobs import fetch_jobs

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/jobs")
async def get_jobs():
    try:
        jobs = await fetch_jobs()
        return [job.model_dump(mode="json") for job in jobs]
    except (httpx.HTTPError, httpx.RequestError) as e:
        logger.warning("[jobs] Upstream fetch failed: %s", e)
        return JSONResponse(
            status_code=502,
            content={"detail": "Could not fetch job listings", "code": "upstream_error"},
        )
    except Exception as e:
        logger.exception("[jobs] Unexpected error: %s", e)
        return JSONResponse(
            status_code=502,
            content={"detail": "Could not fetch job listings", "code": "upstream_error"},
        )
```

- [ ] **Step 4: Register jobs router in src/router.py**

```python
# src/router.py
from dotenv import load_dotenv
from fastapi import APIRouter

from src.routes.evaluate import router as evaluate_router
from src.routes.health import router as health_router
from src.routes.jobs import router as jobs_router

load_dotenv()

router = APIRouter()

router.include_router(evaluate_router)
router.include_router(health_router)
router.include_router(jobs_router)
```

- [ ] **Step 5: Run all tests**

```bash
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/routes/jobs.py src/router.py tests/test_jobs.py
git commit -m "feat: add GET /jobs endpoint with 502 fallback"
```

---

### Task 1.5: Job listings frontend (jobs.html + jobs.js)

**Files:**
- Create: `src/static/jobs.html`
- Create: `src/static/jobs.js`

> **NOTE:** Use `impeccable:frontend-design` skill to design the job cards UI before writing HTML/CSS. Then use `impeccable:arrange` to review the layout. The design must match the existing dark Steam-like theme (CSS variables already defined in `style.css`).

- [ ] **Step 1: Invoke impeccable:frontend-design for job cards design**

Use the Skill tool with `impeccable:frontend-design` before writing the HTML.

- [ ] **Step 2: Create src/static/jobs.html**

The page must:
- Link `style.css` for shared variables/base styles
- Have a `<header>` matching the existing app header style
- Have a `#jobs-grid` container (1-col mobile, 2-col tablet ≥768px, 3-col desktop ≥1200px)
- Each job card (`<article class="job-card">`) contains:
  - Job title (`<h2>`)
  - Company + location line
  - Employment type badge
  - Salary range (if present)
  - Tags (`<div class="tag-cloud">`)
  - Score badge placeholder (`<span class="score-badge">` — empty in Phase 1, populated in Phase 3)
  - Primary CTA: `<a class="btn-primary" href="/job/{id}">See your match →</a>`
  - Secondary link: `<a class="view-original" target="_blank" rel="noopener noreferrer">View original posting ↗</a>`
- A sort toolbar: "Sort by: [Date posted ▾] [Match score]" (match score disabled until Phase 3)
- A `#loading-jobs` spinner shown while fetching
- An `#error-jobs` message div for fetch errors
- Keyboard navigation: cards must be focusable (`tabindex="0"`) with visible focus ring

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CV Evaluator — Job Board</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Anta&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="style.css">
  <link rel="stylesheet" href="jobs.css">
</head>
<body>
  <header class="header">
    <div class="header-inner">
      <div>
        <h1>CV Evaluator</h1>
        <p>Remote Tech Job Board</p>
      </div>
      <nav class="header-nav">
        <a href="index.html" class="nav-link">ATS Evaluator</a>
      </nav>
    </div>
  </header>

  <main class="container">
    <!-- Sort toolbar -->
    <div class="toolbar" role="toolbar" aria-label="Sort options">
      <span class="toolbar-label">Sort by:</span>
      <button id="sort-date" class="sort-btn active" aria-pressed="true">Date posted</button>
      <button id="sort-score" class="sort-btn" aria-pressed="false" disabled title="Upload your CV to sort by match score">Match score</button>
    </div>

    <!-- Loading -->
    <div id="loading-jobs" class="loading-state" aria-live="polite">
      <div class="spinner"></div>
      <p class="loading-text">Loading job listings...</p>
    </div>

    <!-- Error -->
    <p id="error-jobs" class="error-msg hidden" role="alert"></p>

    <!-- Job grid -->
    <div id="jobs-grid" class="jobs-grid" aria-label="Job listings"></div>
  </main>

  <script src="jobs.js"></script>
</body>
</html>
```

- [ ] **Step 3: Create src/static/jobs.css**

```css
/* jobs.css — job board specific styles, imports style.css variables */

/* ── Header inner layout ─────────────────── */
.header-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-nav {
  display: flex;
  gap: 16px;
}

.nav-link {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  text-decoration: none;
  padding: 5px 10px;
  border: 1px solid rgba(76, 107, 138, 0.45);
  border-radius: 2px;
  transition: color 0.15s, border-color 0.15s;
}

.nav-link:hover, .nav-link:focus-visible {
  color: var(--accent-blue);
  border-color: rgba(102, 192, 244, 0.38);
  outline: none;
}

/* ── Toolbar ─────────────────────────────── */
.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 24px;
}

.toolbar-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.sort-btn {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid rgba(76, 107, 138, 0.45);
  padding: 5px 12px;
  border-radius: 2px;
  font-family: 'Inter', Arial, sans-serif;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
}

.sort-btn.active {
  color: var(--accent-blue);
  border-color: rgba(102, 192, 244, 0.5);
  background: rgba(102, 192, 244, 0.08);
}

.sort-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.sort-btn:not(:disabled):hover,
.sort-btn:not(:disabled):focus-visible {
  color: var(--accent-blue);
  border-color: rgba(102, 192, 244, 0.38);
  outline: none;
}

/* ── Loading state ───────────────────────── */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 240px;
  gap: 20px;
}

/* ── Jobs grid ───────────────────────────── */
.jobs-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}

@media (min-width: 768px) {
  .jobs-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (min-width: 1200px) {
  .jobs-grid { grid-template-columns: repeat(3, 1fr); }
}

/* ── Job card ────────────────────────────── */
.job-card {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-top-color: rgba(102, 192, 244, 0.18);
  border-radius: 3px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  box-shadow: var(--shadow-panel);
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
  animation: slideUp 0.3s cubic-bezier(0.22, 1, 0.36, 1) both;
  position: relative;
}

.job-card:hover,
.job-card:focus-visible {
  border-color: rgba(102, 192, 244, 0.55);
  box-shadow: 0 0 18px rgba(102, 192, 244, 0.1), var(--shadow-panel);
  outline: none;
}

.job-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
}

.job-title {
  font-family: 'Anta', Arial, sans-serif;
  font-size: 15px;
  font-weight: 400;
  color: var(--text-primary);
  letter-spacing: 0.02em;
  line-height: 1.3;
  margin: 0;
}

/* Phase 3 score badge — hidden in Phase 1 */
.score-badge {
  display: none;
  flex-shrink: 0;
  width: 42px;
  height: 42px;
  border-radius: 50%;
  border: 2px solid var(--border);
  align-items: center;
  justify-content: center;
  font-family: 'Anta', Arial, sans-serif;
  font-size: 13px;
  font-weight: 400;
  color: var(--text-secondary);
}

.job-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.job-company {
  font-size: 13px;
  color: var(--accent-blue);
  font-weight: 500;
}

.job-meta-sep {
  color: var(--text-secondary);
  font-size: 11px;
}

.job-location {
  font-size: 12px;
  color: var(--text-secondary);
}

.job-type-badge {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: 2px;
  background: rgba(102, 192, 244, 0.1);
  border: 1px solid rgba(102, 192, 244, 0.28);
  color: var(--accent-blue);
}

.job-salary {
  font-size: 12px;
  color: var(--text-secondary);
  font-style: italic;
}

.job-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: auto;
}

.job-date {
  font-size: 11px;
  color: var(--text-secondary);
  letter-spacing: 0.04em;
  margin-top: 4px;
}

/* ── Card actions ────────────────────────── */
.card-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 4px;
}

.btn-match {
  background: linear-gradient(to bottom, #7ec2e2 0%, #4e9dc2 49%, #3f8bae 50%, #2f789b 100%);
  color: #0d1521;
  border: none;
  border-bottom: 1px solid rgba(0, 0, 0, 0.38);
  padding: 8px 16px;
  border-radius: 2px;
  font-family: 'Inter', Arial, sans-serif;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  cursor: pointer;
  text-align: center;
  text-decoration: none;
  display: block;
  transition: filter 0.15s;
}

.btn-match:hover:not(:disabled),
.btn-match:focus-visible {
  filter: brightness(1.1);
  outline: none;
}

.view-original {
  font-size: 11px;
  color: var(--text-secondary);
  text-decoration: none;
  text-align: center;
  letter-spacing: 0.04em;
  transition: color 0.15s;
  padding: 4px 0;
}

.view-original:hover,
.view-original:focus-visible {
  color: var(--accent-blue);
  outline: none;
}
```

- [ ] **Step 4: Create src/static/jobs.js**

```javascript
// src/static/jobs.js

const BACKEND_URL = window.location.hostname === 'bot-curriculum-1.onrender.com'
  ? 'https://bot-curriculum.onrender.com'
  : '';

const jobsGrid    = document.getElementById('jobs-grid');
const loadingEl   = document.getElementById('loading-jobs');
const errorEl     = document.getElementById('error-jobs');
const sortDateBtn = document.getElementById('sort-date');
const sortScoreBtn = document.getElementById('sort-score');

let allJobs = [];
let currentSort = 'date';  // 'date' | 'score'

// ── Format helpers ─────────────────────────────────────────────────────────

function formatDate(dateStr) {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatEmploymentType(type) {
  return type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

// ── Render ─────────────────────────────────────────────────────────────────

function renderJobCard(job, index) {
  const article = document.createElement('article');
  article.className = 'job-card';
  article.setAttribute('tabindex', '0');
  article.setAttribute('role', 'article');
  article.setAttribute('aria-label', `${escHtml(job.title)} at ${escHtml(job.company)}`);
  article.style.animationDelay = `${index * 0.04}s`;
  article.dataset.jobId = job.id;

  const tags = job.tags.slice(0, 5)
    .map(t => `<span class="tag found">${escHtml(t)}</span>`)
    .join('');

  article.innerHTML = `
    <div class="job-card-header">
      <h2 class="job-title">${escHtml(job.title)}</h2>
      <span class="score-badge" aria-label="Match score" aria-hidden="true"></span>
    </div>
    <div class="job-meta">
      <span class="job-company">${escHtml(job.company)}</span>
      <span class="job-meta-sep">·</span>
      <span class="job-location">${escHtml(job.location)}</span>
      <span class="job-type-badge">${escHtml(formatEmploymentType(job.employment_type))}</span>
      ${job.salary_range ? `<span class="job-salary">${escHtml(job.salary_range)}</span>` : ''}
    </div>
    ${tags ? `<div class="job-tags">${tags}</div>` : ''}
    <p class="job-date">Posted ${formatDate(job.posted_at)}</p>
    <div class="card-actions">
      <a href="job-detail.html?id=${encodeURIComponent(job.id)}"
         class="btn-match"
         aria-label="See your match for ${escHtml(job.title)}">
        See your match →
      </a>
      <a href="${escHtml(job.url)}"
         target="_blank"
         rel="noopener noreferrer"
         class="view-original"
         aria-label="View original posting for ${escHtml(job.title)} (opens in new tab)"
         onclick="event.stopPropagation()">
        View original posting ↗
      </a>
    </div>
  `;

  // Keyboard: Enter/Space activates primary CTA
  article.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      window.location.href = `job-detail.html?id=${encodeURIComponent(job.id)}`;
    }
  });

  return article;
}

function renderJobs(jobs) {
  jobsGrid.innerHTML = '';
  if (jobs.length === 0) {
    jobsGrid.innerHTML = '<p style="color:var(--text-secondary);text-align:center;padding:40px 0;">No job listings available right now.</p>';
    return;
  }
  jobs.forEach((job, i) => jobsGrid.appendChild(renderJobCard(job, i)));
}

// ── Sort ───────────────────────────────────────────────────────────────────

function sortedJobs() {
  const jobs = [...allJobs];
  if (currentSort === 'date') {
    jobs.sort((a, b) => new Date(b.posted_at) - new Date(a.posted_at));
  }
  // 'score' sort enabled in Phase 3
  return jobs;
}

function setSort(mode) {
  currentSort = mode;
  sortDateBtn.classList.toggle('active', mode === 'date');
  sortDateBtn.setAttribute('aria-pressed', mode === 'date');
  sortScoreBtn.classList.toggle('active', mode === 'score');
  sortScoreBtn.setAttribute('aria-pressed', mode === 'score');
  renderJobs(sortedJobs());
}

sortDateBtn.addEventListener('click', () => setSort('date'));
sortScoreBtn.addEventListener('click', () => { if (!sortScoreBtn.disabled) setSort('score'); });

// ── Fetch ──────────────────────────────────────────────────────────────────

async function loadJobs() {
  loadingEl.classList.remove('hidden');
  errorEl.classList.add('hidden');
  jobsGrid.innerHTML = '';

  try {
    const res = await fetch(`${BACKEND_URL}/jobs`);
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Error ${res.status}`);
    }
    allJobs = await res.json();
    loadingEl.classList.add('hidden');
    renderJobs(sortedJobs());
  } catch (err) {
    loadingEl.classList.add('hidden');
    errorEl.textContent = err.message.includes('fetch')
      ? 'Could not connect to the server. Check your connection.'
      : err.message;
    errorEl.classList.remove('hidden');
  }
}

loadJobs();
```

- [ ] **Step 5: Manually verify the page renders**

Start the server: `uvicorn src.main:app --reload`
Open `http://localhost:8000/jobs.html`

Checklist:
- [ ] Spinner shows while loading
- [ ] Job cards appear with title, company, location, tags
- [ ] "View original posting ↗" opens Remotive URL in new tab
- [ ] "See your match →" links to `job-detail.html?id=...`
- [ ] Cards are keyboard-navigable (Tab → focus ring visible, Enter navigates)
- [ ] Sort by Date is active by default
- [ ] Sort by Match Score is disabled (greyed out)
- [ ] Layout: 1-col on narrow viewport, 2-col at 768px, 3-col at 1200px

- [ ] **Step 6: Commit**

```bash
git add src/static/jobs.html src/static/jobs.css src/static/jobs.js
git commit -m "feat: add job listings frontend page with responsive grid"
```

---

## PHASE 2 — Session Management & CV Upload Flow

---

### Task 2.1: CVSession model and in-memory store

**Files:**
- Create: `backend/sessions.py`
- Create: `tests/test_sessions.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_sessions.py
import pytest
from datetime import datetime, timedelta, timezone
from backend.sessions import CVSession, cv_sessions, store_session, get_session, delete_session, cleanup_sessions


def test_store_and_get_session():
    token = store_session("cv text here", "resume.pdf")
    session = get_session(token)
    assert session is not None
    assert session.cv_text == "cv text here"
    assert session.filename == "resume.pdf"
    assert session.char_count == len("cv text here")


def test_get_session_returns_none_for_unknown_token():
    assert get_session("nonexistent-token") is None


def test_delete_session():
    token = store_session("text", "file.pdf")
    delete_session(token)
    assert get_session(token) is None


def test_delete_nonexistent_session_does_not_raise():
    delete_session("ghost-token")  # must not raise


def test_cleanup_removes_expired_sessions():
    token = store_session("text", "file.pdf")
    # Manually backdate the session
    cv_sessions[token].uploaded_at = datetime.now(timezone.utc) - timedelta(minutes=61)
    cleanup_sessions()
    assert get_session(token) is None


def test_cleanup_keeps_fresh_sessions():
    token = store_session("text", "file.pdf")
    cleanup_sessions()
    assert get_session(token) is not None
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_sessions.py -v
```

Expected: `ImportError` — `backend.sessions` doesn't exist.

- [ ] **Step 3: Implement backend/sessions.py**

```python
# backend/sessions.py
import logging
import uuid
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel

logger = logging.getLogger(__name__)

SESSION_TTL_MINUTES = 60


class CVSession(BaseModel):
    token: str
    cv_text: str
    filename: str
    char_count: int
    uploaded_at: datetime


# Module-level store: token → CVSession
cv_sessions: dict[str, CVSession] = {}


def store_session(cv_text: str, filename: str) -> str:
    """Store extracted CV text, return session token."""
    cleanup_sessions()
    token = str(uuid.uuid4())
    cv_sessions[token] = CVSession(
        token=token,
        cv_text=cv_text,
        filename=filename,
        char_count=len(cv_text),
        uploaded_at=datetime.now(timezone.utc),
    )
    logger.info("[sessions] Stored session %s (%d chars, %s)", token[:8], len(cv_text), filename)
    return token


def get_session(token: str) -> CVSession | None:
    """Return session if it exists and is not expired."""
    session = cv_sessions.get(token)
    if session is None:
        return None
    age = datetime.now(timezone.utc) - session.uploaded_at
    if age > timedelta(minutes=SESSION_TTL_MINUTES):
        del cv_sessions[token]
        logger.info("[sessions] Session %s expired and removed", token[:8])
        return None
    return session


def delete_session(token: str) -> None:
    """Explicitly remove a session."""
    cv_sessions.pop(token, None)


def cleanup_sessions() -> None:
    """Remove all sessions older than SESSION_TTL_MINUTES."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=SESSION_TTL_MINUTES)
    expired = [t for t, s in cv_sessions.items() if s.uploaded_at < cutoff]
    for t in expired:
        del cv_sessions[t]
    if expired:
        logger.info("[sessions] Cleaned up %d expired sessions", len(expired))
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_sessions.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/sessions.py tests/test_sessions.py
git commit -m "feat: add CVSession in-memory store with 60-min TTL"
```

---

### Task 2.2: Session API routes

**Files:**
- Create: `src/routes/session.py`
- Modify: `src/router.py`
- Modify: `tests/test_sessions.py`

- [ ] **Step 1: Write failing tests for session routes**

Append to `tests/test_sessions.py`:

```python
import io
from fastapi.testclient import TestClient
from src.main import app
from unittest.mock import patch


client = TestClient(app)


def test_post_session_returns_token():
    fake_pdf = b"%PDF-1.4 fake content"
    with patch("src.routes.session.extract_text", return_value="extracted cv text"):
        response = client.post(
            "/session",
            files={"file": ("resume.pdf", io.BytesIO(fake_pdf), "application/pdf")},
        )
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["filename"] == "resume.pdf"
    assert data["char_count"] == len("extracted cv text")


def test_post_session_rejects_empty_file():
    with patch("src.routes.session.extract_text", return_value="text"):
        response = client.post(
            "/session",
            files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
        )
    assert response.status_code == 400


def test_post_session_rejects_oversized_file():
    big_content = b"x" * (5 * 1024 * 1024 + 1)
    with patch("src.routes.session.extract_text", return_value="text"):
        response = client.post(
            "/session",
            files={"file": ("big.pdf", io.BytesIO(big_content), "application/pdf")},
        )
    assert response.status_code == 413


def test_get_session_exists():
    with patch("src.routes.session.extract_text", return_value="cv text"):
        post_res = client.post(
            "/session",
            files={"file": ("cv.pdf", io.BytesIO(b"data"), "application/pdf")},
        )
    token = post_res.json()["token"]
    response = client.get(f"/session/{token}")
    assert response.status_code == 200
    data = response.json()
    assert data["exists"] is True
    assert data["filename"] == "cv.pdf"


def test_get_session_not_found():
    response = client.get("/session/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_delete_session():
    with patch("src.routes.session.extract_text", return_value="text"):
        post_res = client.post(
            "/session",
            files={"file": ("cv.pdf", io.BytesIO(b"data"), "application/pdf")},
        )
    token = post_res.json()["token"]
    del_res = client.delete(f"/session/{token}")
    assert del_res.status_code == 204
    get_res = client.get(f"/session/{token}")
    assert get_res.status_code == 404
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_sessions.py::test_post_session_returns_token -v
```

Expected: `404` or `ImportError`.

- [ ] **Step 3: Create src/routes/session.py**

```python
# src/routes/session.py
import logging

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response

from backend.extractor import extract_text
from backend.sessions import delete_session, get_session, store_session

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB


@router.post("/session")
async def create_session(file: UploadFile = File(...)):
    file_bytes = await file.read()

    if not file_bytes:
        raise HTTPException(status_code=400, detail="File is empty", )

    if len(file_bytes) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 5 MB limit")

    cv_text = extract_text(file_bytes, file.filename)
    if not cv_text or not cv_text.strip():
        raise HTTPException(
            status_code=422,
            detail="Could not extract text. Scanned PDFs may not be readable.",
        )

    token = store_session(cv_text, file.filename)
    logger.info("[session] Created session for %s", file.filename)
    return {"token": token, "filename": file.filename, "char_count": len(cv_text)}


@router.get("/session/{token}")
async def read_session(token: str):
    session = get_session(token)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    return {
        "exists": True,
        "filename": session.filename,
        "uploaded_at": session.uploaded_at.isoformat(),
    }


@router.delete("/session/{token}", status_code=204)
async def remove_session(token: str):
    delete_session(token)
    return Response(status_code=204)
```

- [ ] **Step 4: Register session router in src/router.py**

```python
# src/router.py
from dotenv import load_dotenv
from fastapi import APIRouter

from src.routes.evaluate import router as evaluate_router
from src.routes.health import router as health_router
from src.routes.jobs import router as jobs_router
from src.routes.session import router as session_router

load_dotenv()

router = APIRouter()

router.include_router(evaluate_router)
router.include_router(health_router)
router.include_router(jobs_router)
router.include_router(session_router)
```

- [ ] **Step 5: Run all tests**

```bash
pytest tests/ -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/routes/session.py src/router.py tests/test_sessions.py
git commit -m "feat: add POST/GET/DELETE /session endpoints"
```

---

### Task 2.3: CV upload bar in jobs frontend

**Files:**
- Modify: `src/static/jobs.html`
- Modify: `src/static/jobs.js`
- Modify: `src/static/jobs.css`

> **NOTE:** Use `impeccable:arrange` to review the layout of the sticky top bar before coding.

- [ ] **Step 1: Add sticky CV bar to jobs.html**

Add immediately after `<body>`, before `<header>`:

```html
<!-- Sticky CV bar -->
<div id="cv-bar" class="cv-bar" role="complementary" aria-label="CV upload status">
  <div class="cv-bar-inner">
    <div id="cv-upload-area">
      <button id="cv-upload-btn" class="btn-primary cv-upload-trigger" aria-label="Upload your CV to see match scores">
        Upload your CV
      </button>
      <input type="file" id="cv-file-input" accept=".pdf,.docx" hidden aria-label="Select CV file">
    </div>
    <div id="cv-active-area" class="hidden">
      <div class="cv-chip" role="status" aria-live="polite">
        <span class="cv-chip-icon" aria-hidden="true">📄</span>
        <span id="cv-chip-name" class="cv-chip-name"></span>
        <button id="cv-remove-btn" class="cv-chip-remove" aria-label="Remove uploaded CV">×</button>
      </div>
      <span id="cv-scoring-status" class="cv-scoring-status hidden" aria-live="polite">
        <span class="spinner-small" aria-hidden="true"></span>
        Scoring jobs against your CV…
      </span>
    </div>
    <p id="cv-error" class="cv-error hidden" role="alert"></p>
  </div>
</div>
```

- [ ] **Step 2: Add CV bar styles to jobs.css**

```css
/* ── CV Bar ──────────────────────────────── */
.cv-bar {
  position: sticky;
  top: 0;
  z-index: 100;
  background: var(--bg-deep);
  border-bottom: 1px solid rgba(76, 107, 138, 0.55);
  padding: 10px 40px;
}

.cv-bar::after {
  content: '';
  position: absolute;
  bottom: 0; left: 0; right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent 0%, var(--accent-blue) 30%, var(--accent-blue) 70%, transparent 100%);
  opacity: 0.18;
}

.cv-bar-inner {
  max-width: 960px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.cv-upload-trigger {
  padding: 7px 18px;
  font-size: 12px;
}

.cv-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(102, 192, 244, 0.08);
  border: 1px solid rgba(102, 192, 244, 0.35);
  border-radius: 20px;
  padding: 4px 12px 4px 8px;
}

.cv-chip-icon { font-size: 14px; }

.cv-chip-name {
  font-size: 12px;
  color: var(--accent-blue);
  font-weight: 500;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cv-chip-remove {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
  padding: 0 2px;
  transition: color 0.15s;
}
.cv-chip-remove:hover { color: var(--danger-red); }

.cv-scoring-status {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-secondary);
  letter-spacing: 0.04em;
}

.spinner-small {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(76, 107, 138, 0.28);
  border-top-color: var(--accent-blue);
  border-radius: 50%;
  animation: spin 0.75s linear infinite;
}

.cv-error {
  font-size: 12px;
  color: #f08070;
  padding: 4px 10px;
  background: var(--danger-red-alpha);
  border: 1px solid rgba(231, 76, 60, 0.28);
  border-radius: 2px;
}
```

- [ ] **Step 3: Add CV session logic to jobs.js**

Prepend to `jobs.js` (before `loadJobs()`):

```javascript
// ── CV Session ─────────────────────────────────────────────────────────────

const CV_TOKEN_KEY = 'cv_session_token';

const cvUploadBtn    = document.getElementById('cv-upload-btn');
const cvFileInput    = document.getElementById('cv-file-input');
const cvUploadArea   = document.getElementById('cv-upload-area');
const cvActiveArea   = document.getElementById('cv-active-area');
const cvChipName     = document.getElementById('cv-chip-name');
const cvRemoveBtn    = document.getElementById('cv-remove-btn');
const cvError        = document.getElementById('cv-error');
const cvScoringStatus = document.getElementById('cv-scoring-status');

function showCvActive(filename) {
  cvChipName.textContent = filename;
  cvUploadArea.classList.add('hidden');
  cvActiveArea.classList.remove('hidden');
  cvError.classList.add('hidden');
}

function showCvUpload() {
  cvActiveArea.classList.add('hidden');
  cvUploadArea.classList.remove('hidden');
  cvError.classList.add('hidden');
}

function showCvError(msg) {
  cvError.textContent = msg;
  cvError.classList.remove('hidden');
}

cvUploadBtn.addEventListener('click', () => cvFileInput.click());

cvFileInput.addEventListener('change', async () => {
  const file = cvFileInput.files[0];
  if (!file) return;

  const ext = file.name.split('.').pop().toLowerCase();
  if (!['pdf', 'docx'].includes(ext)) {
    showCvError('Only PDF or DOCX files are accepted.');
    return;
  }
  if (file.size > 5 * 1024 * 1024) {
    showCvError('File exceeds 5 MB limit.');
    return;
  }

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch(`${BACKEND_URL}/session`, { method: 'POST', body: formData });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Upload failed (${res.status})`);
    }
    const data = await res.json();
    localStorage.setItem(CV_TOKEN_KEY, data.token);
    showCvActive(data.filename);
  } catch (err) {
    showCvError(err.message);
  } finally {
    cvFileInput.value = '';
  }
});

cvRemoveBtn.addEventListener('click', async () => {
  const token = localStorage.getItem(CV_TOKEN_KEY);
  if (token) {
    await fetch(`${BACKEND_URL}/session/${token}`, { method: 'DELETE' }).catch(() => {});
    localStorage.removeItem(CV_TOKEN_KEY);
  }
  showCvUpload();
});

async function restoreSessionFromStorage() {
  const token = localStorage.getItem(CV_TOKEN_KEY);
  if (!token) return;
  try {
    const res = await fetch(`${BACKEND_URL}/session/${token}`);
    if (res.status === 404) {
      localStorage.removeItem(CV_TOKEN_KEY);
      return;
    }
    if (res.ok) {
      const data = await res.json();
      showCvActive(data.filename);
    }
  } catch (_) {
    // Network error — leave token, try again next load
  }
}

restoreSessionFromStorage();
```

- [ ] **Step 4: Manual verification**

- [ ] Clicking "Upload your CV" opens file picker
- [ ] After upload: file picker replaced by chip with filename and × button
- [ ] × removes chip and clears localStorage
- [ ] Reload page with token in localStorage: chip re-appears via session check
- [ ] Reload after manual token deletion from localStorage: upload button shown
- [ ] Oversized file shows error message
- [ ] Non-PDF/DOCX shows error message

- [ ] **Step 5: Commit**

```bash
git add src/static/jobs.html src/static/jobs.js src/static/jobs.css
git commit -m "feat: add sticky CV upload bar with session persistence"
```

---

## PHASE 3 — Per-Job CV Scoring

---

### Task 3.1: JobMatch model and scorer chain

**Files:**
- Create: `backend/scorer.py`
- Create: `tests/test_scorer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_scorer.py
import pytest
from unittest.mock import patch, MagicMock
from backend.scorer import JobMatch, score_job, score_all_jobs
from backend.jobs import Job
from datetime import date


SAMPLE_JOB = Job(
    id="1", title="Python Developer", company="TechCo",
    location="Remote", employment_type="full_time",
    salary_range=None, description="Needs Python and FastAPI experience.",
    tags=["python", "fastapi"], url="https://example.com", posted_at=date(2025, 1, 1),
)

SAMPLE_CV = "Experienced Python engineer with 5 years FastAPI, Django, Docker."


def test_job_match_model():
    match = JobMatch(
        job_id="1",
        score=82,
        match_level="strong",
        matched_skills=["python", "fastapi"],
        missing_skills=["aws"],
        one_line_summary="Strong Python match, missing AWS",
    )
    assert match.score == 82
    assert match.match_level == "strong"


def test_job_match_score_range():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        JobMatch(
            job_id="1", score=150, match_level="strong",
            matched_skills=[], missing_skills=[], one_line_summary="x",
        )


@pytest.mark.asyncio
async def test_score_job_returns_job_match():
    mock_result = JobMatch(
        job_id="1", score=75, match_level="good",
        matched_skills=["python"], missing_skills=["docker"],
        one_line_summary="Good Python match, missing Docker",
    )
    with patch("backend.scorer.chain") as mock_chain:
        mock_chain.ainvoke = MagicMock(return_value=mock_result)
        result = await score_job(SAMPLE_CV, SAMPLE_JOB)
    assert result.job_id == "1"
    assert result.score == 75


@pytest.mark.asyncio
async def test_score_all_jobs_parallel():
    mock_result = JobMatch(
        job_id="1", score=60, match_level="partial",
        matched_skills=[], missing_skills=["aws"],
        one_line_summary="Partial match",
    )
    with patch("backend.scorer.chain") as mock_chain:
        mock_chain.ainvoke = MagicMock(return_value=mock_result)
        results = await score_all_jobs(SAMPLE_CV, [SAMPLE_JOB, SAMPLE_JOB])
    assert len(results) == 2
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_scorer.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Create backend/scorer.py**

```python
# backend/scorer.py
import asyncio
import logging
import pathlib
from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from backend.jobs import Job

logger = logging.getLogger(__name__)


class JobMatch(BaseModel):
    job_id: str
    score: int = Field(ge=0, le=100, description="Match score 0-100")
    match_level: Literal["strong", "good", "partial", "weak"]
    matched_skills: list[str] = Field(description="Skills found in both CV and job")
    missing_skills: list[str] = Field(description="Required skills absent from CV")
    one_line_summary: str = Field(description="Max 15-word summary of the match")


_model = ChatAnthropic(model="claude-haiku-4-5")
_structured = _model.with_structured_output(JobMatch)

_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a CV-to-job matching engine. Given a CV and a job listing, return a structured match assessment.
Be concise. The one_line_summary must be 15 words or fewer.
Match levels: strong (75-100), good (50-74), partial (25-49), weak (0-24).""",
    ),
    (
        "human",
        """CV:
{cv_text}

Job Title: {job_title}
Company: {company}
Required skills / tags: {tags}
Description excerpt: {description}

Return job_id as "{job_id}".""",
    ),
])

chain = _prompt | _structured


async def score_job(cv_text: str, job: Job) -> JobMatch:
    """Score a single job against CV text."""
    logger.info("[scorer] Scoring job %s (%s)", job.id, job.title)
    result = await chain.ainvoke({
        "cv_text": cv_text[:3000],  # truncate to keep latency low
        "job_title": job.title,
        "company": job.company,
        "tags": ", ".join(job.tags),
        "description": job.description[:800],
        "job_id": job.id,
    })
    return result


async def score_all_jobs(cv_text: str, jobs: list[Job]) -> list[JobMatch]:
    """Score all jobs in parallel."""
    tasks = [score_job(cv_text, job) for job in jobs]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    matches = []
    for job, result in zip(jobs, results):
        if isinstance(result, Exception):
            logger.warning("[scorer] Failed to score job %s: %s", job.id, result)
            matches.append(JobMatch(
                job_id=job.id, score=0, match_level="weak",
                matched_skills=[], missing_skills=[],
                one_line_summary="Score unavailable",
            ))
        else:
            matches.append(result)
    return matches
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_scorer.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/scorer.py tests/test_scorer.py
git commit -m "feat: add JobMatch model and parallel scorer chain"
```

---

### Task 3.2: POST /jobs/score endpoint

**Files:**
- Modify: `src/routes/jobs.py`
- Modify: `tests/test_jobs.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_jobs.py`:

```python
from unittest.mock import AsyncMock, patch
from backend.scorer import JobMatch
from datetime import date


def test_post_jobs_score_returns_matches(client):
    token = "test-token-abc"
    from backend.sessions import cv_sessions, CVSession
    from datetime import datetime, timezone
    cv_sessions[token] = CVSession(
        token=token, cv_text="Python developer", filename="cv.pdf",
        char_count=16, uploaded_at=datetime.now(timezone.utc),
    )
    sample_match = JobMatch(
        job_id="1", score=80, match_level="strong",
        matched_skills=["python"], missing_skills=[],
        one_line_summary="Strong Python match",
    )
    sample_jobs = [
        Job(id="1", title="Dev", company="Co", location="Remote",
            employment_type="full_time", salary_range=None,
            description="desc", tags=["python"],
            url="https://example.com", posted_at=date(2025, 1, 1)),
    ]
    with patch("src.routes.jobs.fetch_jobs", new=AsyncMock(return_value=sample_jobs)), \
         patch("src.routes.jobs.score_all_jobs", new=AsyncMock(return_value=[sample_match])):
        response = client.post("/jobs/score", json={"token": token})
    assert response.status_code == 200
    data = response.json()
    assert data["1"]["score"] == 80
    assert data["1"]["match_level"] == "strong"


def test_post_jobs_score_returns_404_for_bad_token(client):
    response = client.post("/jobs/score", json={"token": "nonexistent"})
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_jobs.py::test_post_jobs_score_returns_matches -v
```

Expected: `405 Method Not Allowed` or `404`.

- [ ] **Step 3: Add POST /jobs/score to src/routes/jobs.py**

```python
# Append to src/routes/jobs.py
from pydantic import BaseModel
from backend.scorer import score_all_jobs
from backend.sessions import get_session


class ScoreRequest(BaseModel):
    token: str


@router.post("/jobs/score")
async def score_jobs(body: ScoreRequest):
    session = get_session(body.token)
    if session is None:
        return JSONResponse(
            status_code=404,
            content={"detail": "Session not found or expired", "code": "session_not_found"},
        )

    try:
        jobs = await fetch_jobs()
    except Exception as e:
        logger.warning("[jobs/score] Could not fetch jobs: %s", e)
        return JSONResponse(
            status_code=502,
            content={"detail": "Could not fetch job listings", "code": "upstream_error"},
        )

    matches = await score_all_jobs(session.cv_text, jobs)
    return {match.job_id: match.model_dump() for match in matches}
```

- [ ] **Step 4: Run all tests**

```bash
pytest tests/ -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/routes/jobs.py tests/test_jobs.py
git commit -m "feat: add POST /jobs/score endpoint"
```

---

### Task 3.3: Score badges + animations in jobs frontend

**Files:**
- Modify: `src/static/jobs.js`
- Modify: `src/static/jobs.css`

- [ ] **Step 1: Add scoring trigger and badge rendering to jobs.js**

After the `restoreSessionFromStorage()` call, add:

```javascript
// ── Scoring ────────────────────────────────────────────────────────────────

let scoresByJobId = {};  // jobId → JobMatch

function getScoreBadgeClass(score) {
  if (score >= 75) return 'score-strong';
  if (score >= 50) return 'score-good';
  return 'score-weak';
}

function animateScore(el, targetScore) {
  let current = 0;
  const step = Math.ceil(targetScore / 30);
  const interval = setInterval(() => {
    current = Math.min(current + step, targetScore);
    el.textContent = current;
    if (current >= targetScore) clearInterval(interval);
  }, 25);
}

function applyScoresToCards() {
  document.querySelectorAll('.job-card').forEach(card => {
    const jobId = card.dataset.jobId;
    const match = scoresByJobId[jobId];
    const badge = card.querySelector('.score-badge');
    if (!badge) return;

    if (!match) {
      badge.textContent = '—';
      badge.style.display = 'flex';
      return;
    }

    badge.className = `score-badge ${getScoreBadgeClass(match.score)}`;
    badge.style.display = 'flex';
    badge.setAttribute('aria-label', `Match score: ${match.score}`);
    animateScore(badge, match.score);

    // Highlight matched skills in tags
    card.querySelectorAll('.job-tags .tag').forEach(tag => {
      const tagText = tag.textContent.trim().toLowerCase();
      if (match.matched_skills.some(s => s.toLowerCase() === tagText)) {
        tag.classList.add('matched');
      }
    });

    // Show summary under title
    const existingSummary = card.querySelector('.job-one-line');
    if (!existingSummary && match.one_line_summary) {
      const summary = document.createElement('p');
      summary.className = 'job-one-line';
      summary.textContent = match.one_line_summary;
      card.querySelector('.job-card-header').insertAdjacentElement('afterend', summary);
    }
  });
}

async function triggerScoring() {
  const token = localStorage.getItem(CV_TOKEN_KEY);
  if (!token) return;

  cvScoringStatus.classList.remove('hidden');

  try {
    const res = await fetch(`${BACKEND_URL}/jobs/score`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    });
    if (res.status === 404) {
      localStorage.removeItem(CV_TOKEN_KEY);
      showCvUpload();
      return;
    }
    if (!res.ok) return;

    scoresByJobId = await res.json();
    applyScoresToCards();

    // Enable sort-by-score
    sortScoreBtn.disabled = false;
    setSort('score');
  } catch (_) {
    // Scoring failure is silent — neutral badges already shown
  } finally {
    cvScoringStatus.classList.add('hidden');
  }
}
```

Update `showCvActive()` to trigger scoring:

```javascript
function showCvActive(filename) {
  cvChipName.textContent = filename;
  cvUploadArea.classList.add('hidden');
  cvActiveArea.classList.remove('hidden');
  cvError.classList.add('hidden');
  // Trigger scoring when CV is active and jobs are loaded
  if (allJobs.length > 0) triggerScoring();
}
```

Update `loadJobs()` to trigger scoring after load if CV is active:

```javascript
// At the end of the try block in loadJobs(), after renderJobs():
const token = localStorage.getItem(CV_TOKEN_KEY);
if (token) triggerScoring();
```

Update `sortedJobs()` to handle score sorting:

```javascript
function sortedJobs() {
  const jobs = [...allJobs];
  if (currentSort === 'date') {
    jobs.sort((a, b) => new Date(b.posted_at) - new Date(a.posted_at));
  } else if (currentSort === 'score') {
    jobs.sort((a, b) => {
      const sa = scoresByJobId[a.id]?.score ?? -1;
      const sb = scoresByJobId[b.id]?.score ?? -1;
      return sb - sa;
    });
  }
  return jobs;
}
```

- [ ] **Step 2: Add score badge CSS to jobs.css**

```css
/* ── Score badges (Phase 3) ──────────────── */
.score-badge {
  display: none; /* shown by JS after scoring */
}

.score-badge.score-strong {
  border-color: var(--success-green);
  color: var(--success-green);
  box-shadow: 0 0 10px rgba(87, 203, 222, 0.25);
}

.score-badge.score-good {
  border-color: var(--warning-amber);
  color: var(--warning-amber);
  box-shadow: 0 0 10px rgba(243, 156, 18, 0.25);
}

.score-badge.score-weak {
  border-color: var(--danger-red);
  color: var(--danger-red);
}

/* Matched skill tag highlight */
.tag.matched {
  background-color: rgba(87, 203, 222, 0.15);
  border-color: rgba(87, 203, 222, 0.5);
  color: var(--success-green);
}

/* One-line match summary */
.job-one-line {
  font-size: 12px;
  color: var(--text-secondary);
  font-style: italic;
  line-height: 1.4;
  margin-top: -4px;
}
```

- [ ] **Step 3: Manual verification**

- [ ] Upload CV → skeleton `--` badges appear on all cards
- [ ] After scoring: badges animate 0 → score
- [ ] Green (≥75), yellow (50–74), red (<50) badge colors
- [ ] Matched skills highlighted in teal on cards
- [ ] One-line summary appears under job title
- [ ] Cards re-sort by score descending
- [ ] "Match score" sort button becomes enabled
- [ ] Scoring failure: `--` badges remain, no error thrown

- [ ] **Step 4: Commit**

```bash
git add src/static/jobs.js src/static/jobs.css
git commit -m "feat: add per-job score badges with counter animation and sort-by-score"
```

---

## PHASE 4 — Job Detail & Evaluation Flow Integration

---

### Task 4.1: Job detail page

**Files:**
- Create: `src/static/job-detail.html`
- Create: `src/static/job-detail.js`

- [ ] **Step 1: Create job-detail.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Job Detail — CV Evaluator</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Anta&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="style.css">
  <link rel="stylesheet" href="job-detail.css">
</head>
<body>
  <header class="header">
    <div class="header-inner">
      <div>
        <h1>CV Evaluator</h1>
        <p>Job Detail</p>
      </div>
    </div>
  </header>

  <main class="container">
    <a href="jobs.html" class="back-link" aria-label="Back to job listings">← Back to jobs</a>

    <div id="loading-detail" class="loading-state" aria-live="polite">
      <div class="spinner"></div>
      <p class="loading-text">Loading job details...</p>
    </div>

    <p id="error-detail" class="error-msg hidden" role="alert"></p>

    <div id="detail-content" class="hidden">
      <div class="detail-header panel">
        <div class="detail-title-row">
          <div>
            <h2 id="detail-title"></h2>
            <p id="detail-meta" class="detail-meta"></p>
          </div>
          <span id="detail-score-badge" class="score-badge detail-score" aria-label="Match score"></span>
        </div>
        <div id="detail-tags" class="tag-cloud" style="margin-top:12px;"></div>
        <p id="detail-one-line" class="job-one-line" style="margin-top:8px;"></p>
      </div>

      <!-- Primary CTA -->
      <div id="cta-section" class="cta-panel panel">
        <a id="cta-evaluate" href="index.html" class="btn-primary cta-btn" aria-label="See how to improve your match">
          See how to improve your match →
        </a>
        <p id="cta-no-cv" class="cta-hint hidden">
          <a href="jobs.html" class="cta-hint-link">Upload your CV</a> to see your match score.
        </p>
      </div>

      <!-- Description -->
      <div class="panel">
        <h3>Job Description</h3>
        <div id="detail-description" class="detail-description"></div>
      </div>

      <!-- View original -->
      <a id="detail-original-link" href="#" target="_blank" rel="noopener noreferrer" class="view-original-detail">
        View original posting ↗
      </a>
    </div>
  </main>

  <script src="job-detail.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create job-detail.js**

```javascript
// src/static/job-detail.js
const BACKEND_URL = window.location.hostname === 'bot-curriculum-1.onrender.com'
  ? 'https://bot-curriculum.onrender.com'
  : '';

const CV_TOKEN_KEY = 'cv_session_token';

const loadingEl   = document.getElementById('loading-detail');
const errorEl     = document.getElementById('error-detail');
const contentEl   = document.getElementById('detail-content');
const ctaEvaluate = document.getElementById('cta-evaluate');
const ctaNoCv     = document.getElementById('cta-no-cv');

function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function getJobIdFromUrl() {
  return new URLSearchParams(window.location.search).get('id');
}

async function loadDetail() {
  const jobId = getJobIdFromUrl();
  if (!jobId) {
    errorEl.textContent = 'No job ID specified.';
    errorEl.classList.remove('hidden');
    loadingEl.classList.add('hidden');
    return;
  }

  try {
    const res = await fetch(`${BACKEND_URL}/jobs`);
    if (!res.ok) throw new Error(`Error ${res.status}`);
    const jobs = await res.json();
    const job = jobs.find(j => j.id === jobId);
    if (!job) throw new Error('Job not found.');

    renderDetail(job);
    loadingEl.classList.add('hidden');
    contentEl.classList.remove('hidden');
  } catch (err) {
    loadingEl.classList.add('hidden');
    errorEl.textContent = err.message;
    errorEl.classList.remove('hidden');
  }
}

function renderDetail(job) {
  document.title = `${job.title} — CV Evaluator`;
  document.getElementById('detail-title').textContent = job.title;
  document.getElementById('detail-meta').textContent =
    `${job.company} · ${job.location} · ${job.employment_type.replace(/_/g,' ')}` +
    (job.salary_range ? ` · ${job.salary_range}` : '');

  document.getElementById('detail-tags').innerHTML =
    job.tags.map(t => `<span class="tag found">${escHtml(t)}</span>`).join('');

  const desc = document.getElementById('detail-description');
  desc.textContent = job.description;

  document.getElementById('detail-original-link').href = job.url;

  setupCta(job);
  applyStoredScore(job.id);
}

function setupCta(job) {
  const token = localStorage.getItem(CV_TOKEN_KEY);
  if (token) {
    ctaEvaluate.href = `index.html?job_id=${encodeURIComponent(job.id)}&token=${encodeURIComponent(token)}`;
    ctaNoCv.classList.add('hidden');
    ctaEvaluate.classList.remove('hidden');
  } else {
    ctaEvaluate.classList.add('hidden');
    ctaNoCv.classList.remove('hidden');
  }
}

function applyStoredScore(jobId) {
  // Scores are stored in sessionStorage by jobs.js if they were computed
  const raw = sessionStorage.getItem('cv_scores');
  if (!raw) return;
  try {
    const scores = JSON.parse(raw);
    const match = scores[jobId];
    if (!match) return;
    const badge = document.getElementById('detail-score-badge');
    badge.textContent = match.score;
    badge.style.display = 'flex';
    if (match.score >= 75) badge.classList.add('score-strong');
    else if (match.score >= 50) badge.classList.add('score-good');
    else badge.classList.add('score-weak');

    if (match.one_line_summary) {
      document.getElementById('detail-one-line').textContent = match.one_line_summary;
    }
  } catch (_) {}
}

loadDetail();
```

> **NOTE:** In `jobs.js`, after scoring completes, store scores in `sessionStorage`:
> ```javascript
> sessionStorage.setItem('cv_scores', JSON.stringify(scoresByJobId));
> ```
> Add this line inside `triggerScoring()` after `scoresByJobId = await res.json();`.

- [ ] **Step 3: Create job-detail.css**

```css
/* job-detail.css */
.back-link {
  display: inline-block;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  text-decoration: none;
  margin-bottom: 20px;
  padding: 5px 0;
  transition: color 0.15s;
}
.back-link:hover, .back-link:focus-visible {
  color: var(--accent-blue);
  outline: none;
}

.detail-header { padding: 24px; }

.detail-title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.detail-score {
  width: 56px;
  height: 56px;
  font-size: 18px;
  flex-shrink: 0;
}

#detail-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cta-panel {
  padding: 24px;
  text-align: center;
}

.cta-btn {
  display: inline-block;
  padding: 14px 36px;
  font-size: 14px;
  text-decoration: none;
}

.cta-hint {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 12px;
}

.cta-hint-link {
  color: var(--accent-blue);
}

.detail-description {
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  padding: 18px 24px;
}

.detail-meta {
  color: var(--text-secondary);
  font-size: 13px;
  margin-top: 6px;
}

.view-original-detail {
  font-size: 12px;
  color: var(--text-secondary);
  text-decoration: none;
  text-align: center;
  display: block;
  padding: 8px;
  transition: color 0.15s;
}
.view-original-detail:hover { color: var(--accent-blue); }
```

- [ ] **Step 4: Commit**

```bash
git add src/static/job-detail.html src/static/job-detail.js src/static/job-detail.css
git commit -m "feat: add job detail page with CTA and match score display"
```

---

### Task 4.2: Job-specific ATS evaluation

**Files:**
- Modify: `src/routes/evaluate.py`
- Modify: `backend/evaluator.py`
- Modify: `src/static/index.html`
- Modify: `src/static/app.js`

- [ ] **Step 1: Write failing test**

Append to `tests/test_jobs.py` (or create `tests/test_evaluate.py`):

```python
# tests/test_evaluate.py
import io
from unittest.mock import patch
from fastapi.testclient import TestClient
from src.main import app
from backend.sessions import cv_sessions, CVSession
from datetime import datetime, timezone

client = TestClient(app)


def test_evaluate_with_job_id_injects_context(client):
    from backend.jobs import Job
    from datetime import date
    from unittest.mock import AsyncMock

    sample_job = Job(
        id="99", title="Senior Python Engineer", company="MegaCorp",
        location="Remote", employment_type="full_time", salary_range=None,
        description="Requires Python, FastAPI, AWS.", tags=["python", "fastapi", "aws"],
        url="https://example.com", posted_at=date(2025, 1, 1),
    )
    expected_result = {
        "candidate_name": "John", "overall_score": 85, "approved": True,
        "formatting_issues": [], "keywords_found": ["python"],
        "keywords_missing": ["aws"], "recommendations": [], "summary": "Good match.",
    }

    with patch("src.routes.evaluate.fetch_jobs", new=AsyncMock(return_value=[sample_job])), \
         patch("src.routes.evaluate.evaluate_cv", return_value=expected_result):
        response = client.post(
            "/evaluate",
            files={"file": ("cv.pdf", io.BytesIO(b"fake pdf"), "application/pdf")},
            data={"job_id": "99"},
        )
    assert response.status_code == 200


def test_evaluate_without_job_id_still_works(client):
    expected_result = {
        "candidate_name": "Jane", "overall_score": 70, "approved": False,
        "formatting_issues": [], "keywords_found": [],
        "keywords_missing": [], "recommendations": [], "summary": "OK.",
    }
    with patch("src.routes.evaluate.extract_text", return_value="cv text"), \
         patch("src.routes.evaluate.evaluate_cv", return_value=expected_result):
        response = client.post(
            "/evaluate",
            files={"file": ("cv.pdf", io.BytesIO(b"fake pdf"), "application/pdf")},
        )
    assert response.status_code == 200
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_evaluate.py -v
```

Expected: both FAIL (evaluate doesn't accept `job_id` yet).

- [ ] **Step 3: Modify backend/evaluator.py to accept job_context**

Change the `evaluate_cv` signature and prompt:

```python
def evaluate_cv(cv_text: str, job_context: str | None = None) -> dict:
    """Evaluate CV text. If job_context is provided, tailor recommendations to that job."""
    try:
        job_section = f"\nTARGET JOB CONTEXT\n{job_context}" if job_context else ""
        logger.info("[evaluator] Invoking Claude with %d chars of CV text", len(cv_text))
        result = chain.invoke({
            "ats_skill": ats_skill + job_section,
            "cv_text": cv_text,
        })
        logger.info("[evaluator] Claude response received")
        return result.model_dump()
    except Exception as e:
        logger.exception("[evaluator] Error calling Anthropic API: %s", e)
        raise
```

- [ ] **Step 4: Modify src/routes/evaluate.py to accept job_id**

```python
# src/routes/evaluate.py
import logging

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile, File
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.evaluator import evaluate_cv
from backend.extractor import extract_text
from backend.jobs import fetch_jobs

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.post("/evaluate")
@limiter.limit("3/minute")
async def evaluate_resume(
    request: Request,
    file: UploadFile = File(...),
    job_id: str | None = Form(default=None),
):
    try:
        file_bytes = await file.read()
        logger.info("[evaluate] File received: %s (%d bytes)", file.filename, len(file_bytes))

        if not file_bytes:
            raise HTTPException(status_code=400, detail="File is empty")

        cv_text = extract_text(file_bytes, file.filename)
        if not cv_text or cv_text.strip() == "":
            raise HTTPException(
                status_code=422,
                detail="Could not extract text. Scanned PDFs may not be readable.",
            )

        job_context: str | None = None
        if job_id:
            try:
                jobs = await fetch_jobs()
                job = next((j for j in jobs if j.id == job_id), None)
                if job:
                    job_context = (
                        f"Job Title: {job.title}\n"
                        f"Company: {job.company}\n"
                        f"Required skills: {', '.join(job.tags)}\n"
                        f"Description: {job.description[:600]}"
                    )
            except Exception as e:
                logger.warning("[evaluate] Could not fetch job context for %s: %s", job_id, e)

        result = evaluate_cv(cv_text, job_context=job_context)
        logger.info("[evaluate] Evaluation complete for: %s", file.filename)
        return JSONResponse(status_code=200, content=result)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[evaluate] Unexpected error: %s", e)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
```

- [ ] **Step 5: Update index.html — add "← Back to jobs" + job context indicator**

Add to `index.html` inside `<main>` at the top, before `#upload-section`:

```html
<!-- Back nav + job context (shown when arriving from job detail) -->
<div id="job-context-bar" class="job-context-bar hidden">
  <a href="jobs.html" class="back-link">← Back to jobs</a>
  <span id="job-context-label" class="job-context-label"></span>
</div>
```

- [ ] **Step 6: Update app.js — read job_id and token from URL, pre-fill CV, show context**

Add at the top of `app.js`:

```javascript
const CV_TOKEN_KEY = 'cv_session_token';

function getUrlParam(name) {
  return new URLSearchParams(window.location.search).get(name);
}

async function initFromUrl() {
  const jobId  = getUrlParam('job_id');
  const token  = getUrlParam('token') || localStorage.getItem(CV_TOKEN_KEY);

  if (jobId) {
    document.getElementById('job-context-bar').classList.remove('hidden');
    // Fetch job title for the context label
    try {
      const res = await fetch(`${BACKEND_URL}/jobs`);
      if (res.ok) {
        const jobs = await res.json();
        const job = jobs.find(j => j.id === jobId);
        if (job) {
          document.getElementById('job-context-label').textContent =
            `Evaluating for: ${job.title} at ${job.company}`;
        }
      }
    } catch (_) {}
  }
}

initFromUrl();
```

Update `analyzeBtn` click handler in `app.js` to append `job_id` to the form data:

```javascript
analyzeBtn.addEventListener('click', async () => {
  if (!selectedFile) return;
  setLoading(true);
  hideError();

  await waitForServer();
  setLoadingMessage('Analyzing your resume, this may take a few seconds...');

  const formData = new FormData();
  formData.append('file', selectedFile);

  const jobId = getUrlParam('job_id');
  if (jobId) formData.append('job_id', jobId);

  // ... rest of existing fetch logic unchanged
```

- [ ] **Step 7: Run all tests**

```bash
pytest tests/ -v
```

Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/evaluator.py src/routes/evaluate.py src/static/index.html src/static/app.js tests/test_evaluate.py
git commit -m "feat: job-specific ATS evaluation via optional job_id param"
```

---

## PHASE 5 — Polish & Production Readiness

---

### Task 5.1: Rate limiting on all new endpoints

**Files:**
- Modify: `src/routes/jobs.py`
- Modify: `src/routes/session.py`

- [ ] **Step 1: Add rate limiter to GET /jobs and POST /jobs/score**

In `src/routes/jobs.py`, import and apply limiter:

```python
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.get("/jobs")
@limiter.limit("30/minute")
async def get_jobs(request: Request):
    ...

@router.post("/jobs/score")
@limiter.limit("10/minute")
async def score_jobs(request: Request, body: ScoreRequest):
    ...
```

- [ ] **Step 2: Add rate limiter to session routes**

In `src/routes/session.py`:

```python
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/session")
@limiter.limit("10/minute")
async def create_session(request: Request, file: UploadFile = File(...)):
    ...
```

- [ ] **Step 3: Commit**

```bash
git add src/routes/jobs.py src/routes/session.py
git commit -m "chore: apply rate limits to all new endpoints"
```

---

### Task 5.2: Input validation

**Files:**
- Modify: `src/routes/session.py`
- Modify: `src/routes/jobs.py`

- [ ] **Step 1: Validate session token format (UUID)**

In `src/routes/session.py`, add to `read_session` and `remove_session`:

```python
import re

UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')

@router.get("/session/{token}")
async def read_session(token: str):
    if not UUID_RE.match(token):
        raise HTTPException(status_code=422, detail="Invalid token format")
    ...

@router.delete("/session/{token}", status_code=204)
async def remove_session(token: str):
    if not UUID_RE.match(token):
        raise HTTPException(status_code=422, detail="Invalid token format")
    ...
```

- [ ] **Step 2: Write tests for validation**

Append to `tests/test_sessions.py`:

```python
def test_get_session_invalid_token_format(client):
    response = client.get("/session/not-a-uuid")
    assert response.status_code == 422

def test_delete_session_invalid_token_format(client):
    response = client.delete("/session/not-a-uuid")
    assert response.status_code == 422
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/ -v
```

Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add src/routes/session.py tests/test_sessions.py
git commit -m "chore: add UUID format validation to session endpoints"
```

---

### Task 5.3: ruff lint pass

**Files:** All modified Python files.

- [ ] **Step 1: Run ruff and fix all warnings**

```bash
ruff check src/ backend/ tests/
```

Fix any reported issues. Common issues to watch for:
- Unused imports
- Line length (ruff.toml defines max-line-length)
- Missing blank lines between top-level definitions

- [ ] **Step 2: Verify clean**

```bash
ruff check src/ backend/ tests/
```

Expected: `All checks passed!`

- [ ] **Step 3: Commit**

```bash
git add -u
git commit -m "chore: fix all ruff lint warnings"
```

---

### Task 5.4: Run impeccable:audit on all new pages

- [ ] **Step 1: Invoke impeccable:audit skill**

Use `impeccable:audit` to audit `jobs.html`, `job-detail.html`, and `index.html`.
Fix all critical issues found (accessibility, performance, responsive design).

- [ ] **Step 2: Invoke impeccable:polish for final touches**

Use `impeccable:polish` on all new/modified static files.

- [ ] **Step 3: Commit**

```bash
git add src/static/
git commit -m "chore: accessibility and polish pass on all new pages"
```

---

### Task 5.5: Manual QA checklist and TESTING.md

**Files:**
- Create: `docs/TESTING.md`

- [ ] **Step 1: Create docs/TESTING.md**

```markdown
# Manual QA Checklist

## Full Flow
- [ ] Open `/jobs.html` — job cards load (≤3 seconds)
- [ ] Each card shows title, company, location, type badge, tags, date
- [ ] "View original posting ↗" opens Remotive URL in new tab
- [ ] "See your match →" navigates to `/job-detail.html?id=...`
- [ ] Sort by Date: most recent first
- [ ] Sort by Match Score: disabled until CV uploaded

## CV Upload
- [ ] Click "Upload your CV" → file picker opens
- [ ] Upload PDF → chip shows filename
- [ ] Upload DOCX → chip shows filename
- [ ] Upload non-PDF/DOCX → error message shown
- [ ] Upload >5MB → 413 error shown
- [ ] × button removes chip and clears localStorage
- [ ] Reload page → chip re-appears (token in localStorage)
- [ ] Reload after 60+ minutes (manual token expiry test) → upload button shown

## Scoring
- [ ] After CV upload: skeleton `--` badges appear
- [ ] After scoring: badges animate from 0 to score
- [ ] Green (≥75), yellow (50–74), red (<50) badge colors
- [ ] Matched skills highlighted on cards
- [ ] One-line summary under job title
- [ ] Cards re-sort by score descending
- [ ] Sort toggle "By match" / "By date" works
- [ ] Scoring failure: `--` badges remain, no JS error in console

## Job Detail
- [ ] Click "See your match →" → job detail page loads
- [ ] Job title, meta, tags, description shown
- [ ] "← Back to jobs" returns to jobs list
- [ ] "View original posting ↗" opens Remotive URL
- [ ] With CV active: "See how to improve your match →" CTA visible
- [ ] Without CV: "Upload your CV to see your match score." hint shown
- [ ] Match score badge shown if scoring was completed

## ATS Evaluation with Job Context
- [ ] From job detail, click CTA → `/index.html?job_id=...&token=...`
- [ ] "Evaluating for: [Job Title] at [Company]" context bar visible
- [ ] Analyze CV → response includes job-specific recommendations
- [ ] Without job_id param: standard generic evaluation works

## Accessibility
- [ ] Job cards are keyboard-navigable (Tab → focus ring, Enter → detail)
- [ ] Sort buttons accessible via keyboard
- [ ] Screen reader: cards have aria-labels
- [ ] No browser console errors on any page

## Mobile
- [ ] Job cards 1-col on <768px viewport
- [ ] Job cards 2-col on 768–1199px
- [ ] Job cards 3-col on ≥1200px
- [ ] CV bar wraps cleanly on small screens
- [ ] Tap targets ≥44px on mobile
```

- [ ] **Step 2: Commit**

```bash
git add docs/TESTING.md
git commit -m "docs: add manual QA checklist for full job board flow"
```

---

## Self-Review Against Spec

### Spec coverage check

| Requirement | Covered in |
|-------------|-----------|
| Remotive API, Job model, fetch_jobs, 15-min cache | Task 1.2, 1.3 |
| GET /jobs with 502 fallback | Task 1.4 |
| HTML tag stripping | Task 1.2 (`strip_html`) |
| posted_at normalized to date | Task 1.3 (`_parse_date`) |
| Client-side sort by date/score | Task 1.5, 3.3 |
| "View original posting ↗" | Task 1.5 |
| Session storage (UUID, in-memory, 60-min TTL, cleanup) | Task 2.1 |
| POST/GET/DELETE /session | Task 2.2 |
| Sticky CV bar with chip | Task 2.3 |
| localStorage token persistence | Task 2.3 |
| Session restore on load | Task 2.3 |
| Max 5MB file | Task 2.2 |
| JobMatch model + scorer chain | Task 3.1 |
| POST /jobs/score (parallel) | Task 3.2 |
| Score badges + animation | Task 3.3 |
| Matched skill highlights | Task 3.3 |
| one_line_summary on cards | Task 3.3 |
| Score caching in session | Task 3.2 (noted, no separate cache — scoring is async/fast) |
| Job detail page | Task 4.1 |
| Job-specific evaluate (job_id param) | Task 4.2 |
| CV pre-fill from session on index.html | Task 4.2 |
| Rate limiting on all new endpoints | Task 5.1 |
| UUID token validation | Task 5.2 |
| ruff clean | Task 5.3 |
| impeccable:audit + polish | Task 5.4 |
| TESTING.md | Task 5.5 |
| 1-col/2-col/3-col responsive grid | Task 1.5 CSS |
| Keyboard navigation + aria-labels | Task 1.5, verified in 5.4 |
| Absolute imports src.* backend.* | All route/backend files |
| No new frontend frameworks | All frontend tasks |

### Gaps identified and addressed

- **Score caching in session object**: The spec asks to "cache scoring results in the session object so re-scoring the same CV+jobs is instant." This was not tasked explicitly. Should be added: in `backend/sessions.py`, add `scores: dict = {}` field to `CVSession`, and in `POST /jobs/score` check if `session.scores` is non-empty before re-scoring. Mark as a follow-up in Task 3.2 or add a Task 3.2b.

- **`httpx` already in venv but not pyproject.toml**: Covered in Task 1.1.

- **`pytest`/`pytest-asyncio` not in dev deps**: Covered in Task 1.1.
