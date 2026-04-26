# CV Evaluator + Job Board

**AI-powered ATS resume analyzer and intelligent remote tech job board — upload your CV and instantly see how well you match real job listings.**

![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.135-009688?logo=fastapi)
![LangChain](https://img.shields.io/badge/LangChain-1.2-000000?logo=chainlink)
![Anthropic](https://img.shields.io/badge/Claude-Haiku_4.5-orange?logo=anthropic)
![Render](https://img.shields.io/badge/Deployed_on-Render-46E3B7?logo=render)

**Live demo:** https://bot-curriculum-1.onrender.com

> The service runs on Render's free tier and may be inactive. The first request triggers a ~30s wakeup — the UI handles this automatically via polling.

---

## What It Does

**Navigation** — A persistent tab strip sits below the header on every page (ATS Evaluator, Job Board, and Job Detail). `position: sticky; top: 0` keeps it always visible while scrolling.

**ATS Evaluator** (`/`) — Upload a PDF or DOCX resume and get a structured compatibility report from Claude: ATS score, found/missing keywords, formatting issues, and actionable recommendations. The page is designed around a clear user flow:
- **Two-column layout** — "What you get" panel on the left, upload zone on the right
- **Session preloading** — if you already uploaded your CV on the Job Board, the evaluator detects the active session and lets you analyze without re-uploading
- **Job context** — when accessed from a job detail page, a prominent panel shows which role you're evaluating against
- **Results CTA** — after seeing your score, a "Browse matching jobs →" button closes the loop back to the Job Board

**Job Board** (`/jobs.html`) — Browse remote tech jobs pulled from [Remotive](https://remotive.com). Upload your CV to:
- **Rank jobs** by semantic similarity to your resume (embeddings via `all-MiniLM-L6-v2` + Zvec vector DB)
- **Score each job** with Claude: a 0–100 fit score, matched skills, missing skills, and a one-line summary
- **Sort by match score** — the best match gets a green badge, all others red
- **See full analysis** per job on a dedicated detail page

---

## Tech Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.13 |
| Web framework | FastAPI + Uvicorn |
| Package manager | uv |
| LLM | Claude Haiku 4.5 (`claude-haiku-4-5`) |
| AI orchestration | LangChain + `langchain-anthropic` |
| Structured output | Pydantic v2 + `.with_structured_output()` |
| Embeddings | `sentence-transformers` — `all-MiniLM-L6-v2` (384-dim, local/CPU) |
| Vector DB | Zvec 0.3.0 (in-process, persistent on disk) |
| Job listings | Remotive public API |
| File parsing | LiteParse (PDF/DOCX → plain text) |
| Rate limiting | SlowAPI (3 req/min per IP) |
| HTTP client | httpx (async) |
| Frontend | Vanilla HTML/CSS/JS — no framework, no build step |
| Fonts | Space Grotesk (header), Inter (body) — Google Fonts |
| Linter | Ruff |
| Tests | pytest + pytest-asyncio + respx |
| Deployment | Render.com |

---

## Architecture

```
bot_curriculum/
├── src/
│   ├── main.py                  # App factory: CORS, rate limiter, static mount
│   ├── router.py                # Aggregates all routers
│   └── routes/
│       ├── evaluate.py          # POST /evaluate — ATS analysis
│       ├── health.py            # GET /health — wakeup polling
│       ├── jobs.py              # GET /jobs, GET /jobs/ranked, POST /jobs/score
│       ├── session.py           # POST/GET/DELETE /session
│       └── view/public/         # Serves job-detail.html as static route
│
├── backend/                     # Business logic — no HTTP dependencies
│   ├── evaluator.py             # LangChain chain → Claude → ResumeEvaluation
│   ├── extractor.py             # LiteParse: bytes → plain text
│   ├── jobs.py                  # Job model, strip_html(), fetch_jobs() + 15-min cache
│   ├── sessions.py              # CVSession model, in-memory store, 60-min TTL
│   ├── ranker.py                # embed_text(), Zvec singleton, upsert_job()
│   ├── scorer.py                # JobMatch model, score_job() — LLM per-job scoring
│   └── prompts/
│       └── ats_skill.md         # ATS evaluator system prompt
│
├── src/static/
│   ├── index.html               # ATS Evaluator — two-column layout, session preload, job context panel
│   ├── app.js                   # Evaluator logic: session detection, visibility management, XSS escaping
│   ├── style.css                # Global styles + evaluator redesign classes
│   ├── jobs.html / jobs.js      # Job Board page
│   ├── jobs.css                 # Job board styles (glassmorphism)
│   ├── job-detail.html          # Job detail page
│   └── job-detail.js
│
├── tests/                       # 57 tests
│   ├── test_jobs.py
│   ├── test_sessions.py
│   ├── test_ranker.py
│   ├── test_scorer.py
│   └── test_evaluate.py
│
├── zvec_jobs/                   # Persistent vector index (gitignored)
├── render.yaml
└── pyproject.toml
```

---

## Data Flow

### CV Upload + Job Ranking

```
User uploads CV (PDF/DOCX)
        │
        ▼
POST /session
  ├── LiteParse → extract plain text
  ├── all-MiniLM-L6-v2 → 384-dim embedding vector
  └── Store CVSession {token, cv_text, cv_embedding} in memory (TTL 60 min)
        │
        ▼ token saved in localStorage
        │
GET /jobs/ranked?token=...
  ├── fetch_jobs() → Remotive API (cached 15 min, limit=100)
  ├── upsert_job() → embed each new job → insert into Zvec (persistent)
  ├── Zvec.query(cv_embedding, topk=20) → top 20 most similar jobs
  └── Return jobs with similarity_score (0–1)
        │
        ▼
POST /jobs/score {token, limit: N}
  ├── Zvec.query(cv_embedding, topk=N) → select top N jobs
  ├── asyncio.gather → N parallel Claude Haiku calls
  ├── Each call returns JobMatch {score, matched_skills, missing_skills, summary}
  └── Cache results in session.scored_jobs
```

### ATS Evaluation

```
User uploads CV
        │
        ▼
POST /evaluate
  ├── LiteParse → extract plain text
  ├── LangChain chain → Claude Haiku (structured output)
  └── Return ResumeEvaluation {ats_score, keywords_found, keywords_missing, ...}
```

---

## Key Data Models

```python
class CVSession(BaseModel):
    token: str                      # UUID v4
    cv_text: str                    # Extracted plain text
    cv_embedding: list[float]       # 384-dim vector
    filename: str
    created_at: datetime
    scored_jobs: dict               # {job_id: JobMatch} — LLM score cache

class JobMatch(BaseModel):          # LLM structured output
    score: int                      # 0–100 fit score
    match_level: str                # "strong" | "good" | "partial" | "weak"
    matched_skills: list[str]
    missing_skills: list[str]
    one_line_summary: str

class ResumeEvaluation(BaseModel):  # ATS evaluator structured output
    candidate_name: str
    ats_score: int
    verdict: str
    summary: str
    keywords_found: list[str]
    keywords_missing: list[str]
    formatting_issues: list[str]
    recommendations: list[str]
```

---

## API Reference

### `GET /health`
Returns `{ "status": "ok" }`. Used by the frontend to detect Render free-tier wakeup.

### `POST /evaluate`
Analyzes a CV and returns a structured ATS report. Rate limited: 3/min per IP.

**Request:** `multipart/form-data`. `file` (PDF or DOCX) is **optional** — if omitted, send an `X-CV-Session-Token` header to use an existing session's CV text instead of re-uploading. Sending neither returns `400 No CV provided`.

**Response `200`:**
```json
{
  "candidate_name": "Jane Smith",
  "ats_score": 74,
  "verdict": "Needs Improvement",
  "summary": "Solid technical background but missing several infrastructure keywords.",
  "keywords_found": ["Python", "FastAPI", "REST API"],
  "keywords_missing": ["Docker", "CI/CD", "Kubernetes"],
  "formatting_issues": ["Two-column layout detected"],
  "recommendations": ["Add a Skills section listing missing keywords explicitly"]
}
```

### `POST /session`
Creates a CV session. Rate limited: 3/min per IP.

**Request:** `multipart/form-data` with `file` (PDF or DOCX, max 5 MB).

**Response `200`:** `{ "token": "<uuid>", "filename": "cv.pdf", "char_count": 3842 }`

### `GET /session/{token}`
Returns session metadata (no CV text exposed).

### `DELETE /session/{token}`
Removes the session from memory.

### `GET /jobs`
Returns all job listings (unranked). Remotive data cached 15 min.

### `GET /jobs/ranked?token=<uuid>`
Returns jobs ranked by cosine similarity to the session's CV embedding (top 20 from Zvec). Remaining jobs appended with `similarity_score: null`.

### `POST /jobs/score`
Scores the top N jobs against the CV using Claude. Rate limited: 3/min per IP.

**Request:** `{ "token": "<uuid>", "limit": 20 }`

**Response:** Array of `{ job_id, score, match_level, matched_skills, missing_skills, one_line_summary }`.

---

## Running Locally

**Prerequisites:** Python 3.13+, [uv](https://docs.astral.sh/uv/)

```bash
# Clone
git clone <repo-url>
cd bot_curriculum

# Install dependencies
pip install -e .

# Environment
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# Start
uvicorn src.main:app --reload
```

Open **http://localhost:8000** (ATS Evaluator) or **http://localhost:8000/jobs.html** (Job Board).

> **Tip:** Upload a CV on the Job Board first. When you then open the ATS Evaluator, it auto-detects your active session and skips the re-upload step.

```bash
# Run tests
pytest tests/ -v

# Lint
ruff check backend/ src/routes/ tests/
```

---

## Environment Variables

| Variable | Required | Description | Default |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key | — |
| `FRONTEND_BASE_URL` | No | Allowed CORS origin | `http://localhost:3000` |

---

## Frontend Design

The app uses a **glassmorphism** aesthetic with the Steam color palette:

**Job Board:**
- Cards: `rgba(255,255,255,0.07)` background + `backdrop-filter: blur(8px)` + blue accent top border
- Score badges: pill-shaped (`border-radius: 20px`) — green for the top match, red for all others
- If a job couldn't be LLM-scored, `similarity_score × 100` is shown as a fallback badge
- All interactive elements are keyboard-navigable (`tabindex`, `aria-label`, Enter/Space handlers)

**ATS Evaluator:**
- Two-column layout: left panel explains the tool, right panel has the upload zone
- Glassmorphism: drop zone, panels, buttons, and chips all use `rgba` + `backdrop-filter: blur` + `border-radius: 12–20px` — matching the Job Board aesthetic
- Job context panel with left blue border when arriving from a job detail (`?job_id=`)
- Session chip: if a CV session is active from the Job Board, shows filename + "Change file" — no re-upload needed
- Results CTA at the bottom: "Browse matching jobs →" returns the user to the Job Board

**Shared:**
- Persistent tab strip in the sticky header on all pages (ATS Evaluator, Job Board, Job Detail) — always shows both navigation options regardless of where the user is
- All API data is XSS-sanitized via `escHtml()` and `safeUrl()` before being injected into the DOM

---

## Deployment (Render.com)

```yaml
# render.yaml
services:
  - type: web
    name: bot-curriculum
    runtime: python
    buildCommand: pip install -e .
    startCommand: uvicorn src.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: PYTHON_VERSION
        value: "3.13"
```

1. Fork this repo
2. Create a new **Web Service** on [render.com](https://render.com) pointing to your fork
3. Render auto-detects `render.yaml`
4. Add `ANTHROPIC_API_KEY` in the Environment tab

**Note on free tier:** Render spins down inactive services. The frontend polls `GET /health` on load and shows a wakeup message if the server is starting — no action required from the user.

---

## Git Workflow

```
main        ← production (merges from develop when ready to deploy)
  └── develop    ← integration branch
        └── feature/phase-N-description    ← all active work
```

Never commit directly to `main` or `develop`. All work goes through feature branches.
