# Aurea

**Tailor your CV to every job with AI.** Upload your CV and paste a job description or its link. Aurea rewrites the CV for that role, lists the skills you're missing and writes the cover letter.

[![CI](https://github.com/pabloler21/bot_curriculum/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/pabloler21/bot_curriculum/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Claude](https://img.shields.io/badge/Claude-Haiku_5.5-D97757?logo=anthropic&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-3FCF8E?logo=supabase&logoColor=white)

**Live:** https://aurea.pablolerner.dev

> The server sleeps when nobody is using it. Your first visit wakes it up, which takes a few seconds.

---

## What it does

| Feature | Account | Cost |
|---|---|---|
| **ATS Evaluator**: score, missing keywords and the top fixes for your CV | No | Free |
| **Tailor**: your CV rewritten for one job, with skill gaps and a PDF | Yes | 1 credit |
| **Cover letter** for the same job | Yes | 1 credit, or 2 together with the tailored CV |
| **Improve my CV**: applies the evaluator's fixes to your saved CV | Yes | 1 credit |
| **Interview prep**: likely questions and draft answers for a tailored application | Yes | Free |
| **Job board**: remote software jobs from [Remotive](https://remotive.com), ranked against your CV | No | Free |

New accounts get 5 credits. Paid credit packs are not live yet.

With an account, Aurea also keeps your base CV, so you don't upload it every time, and a history of your results with their PDFs. The interface is in English and Spanish.

---

## How tailoring works

```
CV (PDF/DOCX) ──► text, with hidden text removed
                        │
                        ▼
              1. Extract ──► structured CV (Pydantic schema)
                        │
job description ────────┤   (or a link: the page is fetched first)
                        ▼
              2. Adapt ────► tailored CV + skill gaps
                        │                       ▲
                        ▼                       │ bullets that drifted,
              3. Validate ──────────────────────┘ up to 2 retries
                        │
                        ▼
              4. Cover letter (optional) + PDF
```

- Extract, Adapt and the cover letter are Claude calls through LangChain, with the output parsed into Pydantic models. Each one reads its model from an environment variable, so it can switch models without code changes.
- **Validate** is the anti-hallucination step. Each rewritten bullet is compared with the original bullets by embedding similarity. Bullets below the threshold go back to the model as feedback. If any still fail after the retries, the result is delivered with those bullets flagged, not hidden.
- Credits are charged only after the inputs are checked and the job link is fetched. If the pipeline fails, they are refunded. If only the cover letter fails, only its credit is refunded.

### Security

- **The CV is untrusted input.** Text a reader can't see (white, tiny or off-page text, zero-width characters) is dropped before it reaches the model, so a CV can't carry hidden instructions.
- **Job links are fetched with SSRF protection.** Only `http`/`https` is allowed. Every host, including each redirect, must resolve to public IPs. Each fetch has a 10 s deadline and a 2 MB cap.
- **Credits move only through atomic SQL functions**, and only the backend can call them.
- **Tables with personal data** (saved CVs, history) have row-level security with no policies, so only the backend's service role can read them.
- **The AI endpoints are rate-limited** to 3 requests per minute per IP.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.13, FastAPI, uvicorn, [uv](https://docs.astral.sh/uv/) |
| AI | Claude Haiku 5.5 via LangChain (`langchain-anthropic`), structured outputs validated with Pydantic |
| Auth and database | Supabase: email magic link and Postgres. Google sign-in is built in but not enabled yet |
| CV parsing | pdfplumber for PDFs, LiteParse for DOCX and for scanned PDFs (OCR) |
| Embeddings | fastembed (`all-MiniLM-L6-v2`, runs locally on CPU) + Zvec vector store |
| PDF output | ReportLab |
| Frontend | Vanilla HTML, CSS and JavaScript: no framework, no build step |
| Quality | pytest, Ruff, GitHub Actions |
| Hosting | Vultr VPS, systemd, Caddy |

---

## Project layout

```
backend/              business logic, no HTTP
  adapter/            tailoring pipeline: extract → adapt → validate → cover letter → PDF
  prompts/            system prompts, one Markdown file per stage
src/
  main.py             FastAPI app: CORS, rate limiter, static files
  routes/             one module per endpoint group
  static/             frontend: landing pages and app pages
supabase/migrations/  database schema
tests/
deploy/deploy.sh      reference copy of the production deploy script
```

---

## API

With the server running, FastAPI serves the full interactive reference at `/docs`.

| Endpoint | Sign-in | What it does |
|---|---|---|
| `POST /evaluate` | Optional | ATS report for a CV |
| `POST /adapt` | Required | Tailored CV, cover letter or both (`mode`: `cv`, `cover`, `both`) |
| `GET /adapt/{run_id}/pdf` | — | Tailored CV as PDF |
| `POST /improve` | Required | Rewrites the saved CV with the evaluator's fixes |
| `POST /interview` | Required | Interview questions for a tailored application |
| `GET`, `PUT /cv` | Required | Reads or replaces the saved CV |
| `GET /history`, `/history/{id}`, `/history/{id}/pdf` | Required | Past results |
| `GET /credits` | Required | Credit balance |
| `DELETE /account` | Required | Deletes the account and all its data |
| `POST /session`, `GET`/`DELETE /session/{token}` | — | Anonymous CV session for the job board |
| `GET /jobs`, `GET /jobs/ranked`, `POST /jobs/score` | Optional | Job listings, ranked and scored against the CV |
| `POST /waitlist` | Optional | Joins the Pro plan waitlist |
| `GET /config`, `GET /health` | — | Public Supabase settings for the frontend; health check |

Signed-in requests send the Supabase access token as `Authorization: Bearer <token>`. `/adapt`, `/evaluate`, `/improve`, `/interview`, `/session` and `/jobs/score` are limited to 3 requests per minute per IP.

---

## Running locally

**You need:** Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/pabloler21/bot_curriculum.git
cd bot_curriculum
uv sync
```

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=sk-ant-...

# Optional: needed for sign-in, credits, saved CV and history
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
```

```bash
uv run uvicorn src.main:app --reload   # http://localhost:8000
uv run pytest                          # tests
uv run ruff check .                    # lint
```

Without Supabase, the evaluator and the job board work. Everything that needs an account returns `401`, because nobody can sign in.

To set up Supabase, run the files in `supabase/migrations/` in order, either in the SQL editor or with the Supabase CLI. Then add `http://localhost:8000/**` under Authentication → URL Configuration → Redirect URLs, so the magic link brings you back to your local server.

### Environment variables

| Variable | Required | What it's for |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Claude API |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | For sign-in | Supabase project. The anon key is public: the frontend gets it from `/config` |
| `SUPABASE_SERVICE_ROLE_KEY` | For accounts | Credits, saved CV, history and account deletion. Without it those features do nothing, and `DELETE /account` returns `503` |
| `SUPABASE_KEY` | No | Stores job-board CV sessions in Postgres instead of memory. Production leaves it unset |
| `FRONTEND_BASE_URL` | No | Allowed CORS origin (default `http://localhost:3000`) |
| `AUREA_EXTRACT_MODEL`, `AUREA_ADAPT_MODEL`, `AUREA_COVER_MODEL`, `AUREA_INTERVIEW_MODEL`, `AUREA_IMPROVE_MODEL`, `AUREA_EVALUATE_MODEL`, `AUREA_SCORE_MODEL` | No | Claude model for each stage (default `claude-haiku-5-5`) |

---

## Deployment

Production runs on a Vultr VPS:

- **systemd** runs uvicorn on `127.0.0.1:8000`.
- **Caddy** sits in front. It handles HTTPS and stops the service when there is no traffic. The next visit starts it again.
- **Every push to `main`** runs CI: Ruff, then pytest. If both pass, a deploy job connects over SSH and runs [`deploy/deploy.sh`](deploy/deploy.sh), which checks out `main`, syncs dependencies and restarts the service. The job then polls `/health` until it answers.
- **The CI SSH key can only run that script.** `authorized_keys` pins it to a forced command, and the server user can restart the service but has no other sudo rights.

---

## Branches

```
main          production, deploys on every push
  └── develop                         integration
        └── feature/task-N-N-name     one branch per task, merged into develop through a PR
```
