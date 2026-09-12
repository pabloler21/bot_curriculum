# Project Context — bot_curriculum (CV Evaluator + Job Board)

> Para agentes con tarea de refactor/giro de features. Leer esto en lugar de explorar archivo por archivo.

---

## Qué hace la app

**Aurea** — evaluador ATS de CVs + job board con scoring inteligente.

**Flujo core:**
1. Usuario sube CV (PDF/DOCX) → se extrae texto y se crea una sesión en memoria
2. El CV se embeds con `all-MiniLM-L6-v2` → vector guardado en `CVSession`
3. Jobs se fetchean de Remotive API (caché 15 min) y se indexan en Zvec (vector DB on-disk)
4. `GET /jobs/ranked?token=` → top-20 jobs por similitud coseno CV vs job descriptions
5. `POST /jobs/score` → Claude Haiku evalúa CV contra cada job → `JobMatch` (score 0-100, matched/missing skills)
6. `POST /evaluate` → Claude Haiku evalúa el CV con criterios ATS → `ResumeEvaluation`

---

## Stack

- **Runtime**: Python 3.13, `uv`
- **Backend**: FastAPI + uvicorn, `slowapi` (rate limit 3/min por IP)
- **AI**: LangChain + `claude-haiku-4-5` (structured output via `.with_structured_output()`)
- **Embeddings**: `fastembed` con `sentence-transformers/all-MiniLM-L6-v2` (384 dims)
- **Vector DB**: `zvec` (on-disk, path `./zvec_jobs`)
- **Extracción texto**: `liteparse` (PDF/DOCX via archivo temporal)
- **HTTP**: `httpx` async
- **Frontend**: vanilla JS/HTML/CSS, sin build step, servido por FastAPI StaticFiles
- **Tests**: `pytest` + `pytest-asyncio` + `respx`
- **Deploy**: Render.com (`render.yaml`)

---

## Rutas API

### `POST /evaluate` — `src/routes/evaluate.py`
- Acepta `file` (UploadFile, opcional) + `job_id` (Form, opcional)
- Header `X-CV-Session-Token`: si no hay `file`, usa el CV de la sesión existente
- Extrae texto → llama `evaluate_cv(cv_text, job_context?)` → retorna `ResumeEvaluation` como JSON
- `job_context`: si `job_id` presente, busca en `_cache` de jobs y concatena title+company+description al prompt
- Rate limit: 3/min por IP

### `GET /jobs` — `src/routes/jobs.py`
- Llama `fetch_jobs()` → retorna `list[Job]` (20 jobs de Remotive, caché 15 min)
- 502 si Remotive falla, 500 si error interno

### `GET /jobs/ranked?token=` — `src/routes/jobs.py`
- Si hay token válido y la sesión tiene `cv_embedding`: consulta Zvec `topk=20` por similitud
- Retorna jobs con campo `similarity_score` (float 0-1, o null si no rankeado)
- Fallback graceful: si no hay sesión/embedding, retorna todos sin score

### `POST /jobs/score` — `src/routes/jobs.py`
- Body: `{token: str, limit: int = 8}` (clampea 1-30)
- Requiere sesión con `cv_embedding`
- Selecciona top-N via Zvec → score paralelo con `asyncio.gather()` → cachea en `session.scored_jobs`
- Retorna list de `{job_id, score, match_level, matched_skills, missing_skills, one_line_summary}`
- Rate limit: 3/min por IP

### `POST /session` — `src/routes/session.py`
- Acepta `file` (UploadFile), máx 5 MB
- Extrae texto → `store_session()` → retorna `{token, filename, char_count}`
- `store_session()` también calcula y guarda `cv_embedding` (puede fallar silenciosamente)
- Rate limit: 3/min por IP

### `GET /session/{token}` — `src/routes/session.py`
- Retorna `{exists, filename, uploaded_at}` o 404
- TTL: 60 min. Validación UUID en la ruta.

### `DELETE /session/{token}` — `src/routes/session.py`
- Elimina la sesión. 204 si ok, 404 si no existe.

### `GET /health` — `src/routes/health.py`
- Simple healthcheck para el wakeup polling del frontend.

---

## Módulos backend

### `backend/evaluator.py`
- Crea `ResumeEvaluation` (Pydantic) con 8 campos: `candidate_name`, `overall_score`, `approved`, `formatting_issues`, `keywords_found`, `keywords_missing`, `recommendations`, `summary`
- Chain: `ChatPromptTemplate | ChatAnthropic("claude-haiku-4-5").with_structured_output(ResumeEvaluation)`
- Prompt del sistema en `backend/prompts/ats_skill.md`
- `evaluate_cv(cv_text, job_context=None) -> dict`

### `backend/scorer.py`
- Crea `JobMatch` (Pydantic): `score`, `match_level` (Literal strong/good/partial/weak), `matched_skills`, `missing_skills`, `one_line_summary`
- Chain async: `_prompt | ChatAnthropic("claude-haiku-4-5").with_structured_output(JobMatch)`
- `score_job(cv_text, job) -> JobMatch` (async)

### `backend/sessions.py`
- `CVSession` (Pydantic): `token`, `cv_text`, `cv_embedding: list[float]`, `filename`, `uploaded_at`, `scored_jobs: dict[str, Any]`
- Store en memoria: `cv_sessions: dict[str, CVSession]`
- TTL 60 min, cleanup lazy en cada `store_session()`
- `store_session()`, `get_session()`, `delete_session()`, `cleanup_sessions()`

### `backend/jobs.py`
- `Job` (Pydantic): `id`, `title`, `company`, `location`, `employment_type`, `salary_range`, `description`, `tags`, `url`, `posted_at`
- Fuente: `https://remotive.com/api/remote-jobs?category=software-dev&limit=20`
- `strip_html()` para limpiar descriptions de Remotive
- Caché módulo-nivel: `_cache = {"data": None}` → `(list[Job], datetime)` con TTL 15 min
- Al fetchear, llama `upsert_job()` en cada job para indexar en Zvec

### `backend/ranker.py`
- `TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")` — lazy init, singleton
- `embed_text(text) -> list[float]` — retorna embedding 384-dim
- `cosine_similarity(a, b) -> float` — con numpy
- `get_jobs_collection() -> zvec.Collection` — abre/crea colección Zvec en `./zvec_jobs`, singleton
- `upsert_job(job)` — idempotente (set `_inserted_ids` en memoria + falla silenciosa si ya existe en Zvec)

### `backend/extractor.py`
- `extract_text(file_bytes, file_name) -> str`
- Escribe a archivo temporal → `LiteParse().parse()` → retorna `result.text`
- Soporta PDF y DOCX. Lanza `RuntimeError` si falla el parse.

---

## Frontend — Páginas

### `index.html` + `app.js` + `style.css` — CV Evaluator
**Flujo UI:**
1. Si `?job_id=` en URL → `loadJobContext()` fetchea `/jobs`, muestra panel "Evaluating against [job]"
2. Si hay token en `localStorage["cv_session_token"]` → `checkExistingSession()` llama `GET /session/{token}` → muestra session chip (nombre del archivo) y habilita "Analyze my CV" sin re-upload
3. Usuario sube CV (drag/drop o browse) o usa sesión preloaded
4. Click "Analyze" → `waitForServer()` (polling `/health` si Render está dormido) → `POST /evaluate`
5. Si hay nuevo archivo Y token existente: también llama `POST /session` en background para refrescar el token
6. Resultados: SVG ring animado, score, candidate name, verdict badge, keywords, formatting issues, recommendations, CTA "Browse matching jobs →"
7. Reset: vuelve a estado inicial. Session chip: "Change file" llama `DELETE /session/{token}` y limpia localStorage.

**Elementos DOM clave:** `#hero-section`, `.evaluator-layout` (grid 2-col), `#upload-section`, `#drop-zone`, `#session-chip`, `#job-context-badge`, `#loading-section`, `#results-section`, `#score-ring-progress` (SVG), `#candidate-name`, `#verdict-badge`

### `jobs.html` + `jobs.js` + `jobs.css` — Job Board
**Flujo UI:**
1. Init: si `localStorage["cv_session_token"]` existe → activa CV banner, carga `/jobs/ranked?token=`, hace scoring automático
2. Sin CV: carga `/jobs` (sin ranking), cards sin score badge
3. CV upload en el banner → `POST /session` → guarda token → carga ranked jobs → `startBackgroundScoring()`
4. `startBackgroundScoring()`: llama `POST /jobs/score` → aplica score badges en las cards → auto-switch a sort "Match score"
5. Sort: "Date posted" (default) | "Match score" (habilitado inmediatamente al subir CV)
6. Cards: título, empresa, location, tipo, tags, similarity bar (si rankeado), score badge (si scoreado), "Apply" y "See full analysis" (si CV activo)

**Estado global JS:** `allJobs[]`, `scoresByJobId{}`, `cvSessionToken`, `currentSort`

**Skeleton loading:** 9 cards skeleton mientras carga (CSS animations)

### `job-detail.html` + `job-detail.js` — Detalle de oferta
**Flujo UI:**
1. Lee `?id=` de la URL → filtra `/jobs` por id
2. Muestra descripción completa del job
3. Si hay sesión → muestra scoring o lo solicita
4. "Analyze against this job" → navega a `index.html?job_id={id}`

---

## Convenciones críticas

- **Imports**: absolutos desde `src.*` y `backend.*`
- **Errores HTTP**: `HTTPException` para errores simples; `JSONResponse({"detail":..., "code":...})` cuando se necesita `code` field (ej: upstream errors)
- **XSS**: todo dato de API pasa por `escHtml()`. URLs por `safeUrl()`.
- **Tests**: TDD. Tests en `tests/` con fixture `client` (TestClient), LLMs mockeados con `respx`/`mocker`
- **Sessions**: in-memory, no Redis, no persistencia. Límite real en prod: ~100 usuarios concurrentes antes de necesitar migrar.
- **Zvec**: on-disk en `./zvec_jobs`. En dev se crea solo. En Render persiste entre deploys si el disco es persistente.
- **BACKEND_URL en JS**: `''` en dev (mismo origen), `'https://bot-curriculum.onrender.com'` en prod (hostname check hardcodeado)
- **Rate limiting**: `slowapi` con `get_remote_address`. 3/min por IP en `/evaluate`, `/session`, `/jobs/score`

---

## Estructura de archivos (solo los relevantes)

```
src/
  main.py              # FastAPI app, CORS, slowapi, StaticFiles mount
  router.py            # agrega todos los routers
  routes/
    evaluate.py        # POST /evaluate
    health.py          # GET /health
    jobs.py            # GET /jobs, GET /jobs/ranked, POST /jobs/score
    session.py         # POST /session, GET+DELETE /session/{token}
  static/
    index.html         # Evaluator page (Aurea)
    app.js             # Evaluator logic (~373 lines)
    style.css          # Estilos evaluator + shared
    jobs.html          # Job board
    jobs.js            # Job board logic (~560 lines)
    jobs.css           # Job board styles
    job-detail.html    # Job detail page
    job-detail.js      # Job detail logic (~162 lines)
    favicon.svg
backend/
  evaluator.py         # LangChain chain → ResumeEvaluation
  scorer.py            # LangChain chain async → JobMatch
  sessions.py          # CVSession in-memory store
  jobs.py              # Job model, fetch_jobs(), cache, strip_html()
  ranker.py            # fastembed, Zvec collection, upsert_job()
  extractor.py         # liteparse wrapper
  prompts/
    ats_skill.md       # System prompt para el evaluador ATS
tests/
  conftest.py          # fixture: client = TestClient(app)
  test_evaluate.py     # POST /evaluate (file + session token flows)
  test_jobs.py         # strip_html, Job model, fetch_jobs, GET /jobs
  test_sessions.py     # store/get/delete/cleanup/TTL
  test_ranker.py       # embed_text, cosine_similarity, upsert_job
  test_scorer.py       # score_job (LLM mockeado)
```

---

## Variables de entorno

| Variable | Uso | Default |
|---|---|---|
| `ANTHROPIC_API_KEY` | LangChain/Anthropic | (requerida) |
| `FRONTEND_BASE_URL` | CORS allow_origins | `http://localhost:3000` |

---

## Comandos útiles

```bash
pip install -e .          # instalar deps
uvicorn src.main:app --reload  # dev server
pytest tests/ -v          # tests
ruff check backend/ src/routes/ tests/  # lint
```
