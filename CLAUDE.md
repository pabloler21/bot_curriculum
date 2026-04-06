# CLAUDE.md — bot-curriculum

## Proyecto
CV Evaluator: app web que analiza CVs y evalúa su compatibilidad ATS usando Claude AI.
**En expansión**: se está convirtiendo en un job board con scoring de CV contra ofertas laborales reales.

## Stack
- **Runtime**: Python 3.13, `uv` como package manager
- **Backend**: FastAPI + uvicorn, rate limiting con slowapi (3/min por IP)
- **AI**: LangChain + `claude-haiku-4-5` con structured output (`ResumeEvaluation` pydantic model)
- **Extracción de texto**: liteparse (PDF/DOCX)
- **HTTP async**: httpx (para llamadas a APIs externas)
- **Frontend**: HTML/JS/CSS estático servido por FastAPI desde `src/static/`
- **Linter**: ruff
- **Tests**: pytest + pytest-asyncio + respx
- **Deploy**: Render.com (`render.yaml`)

## Estructura actual (post Fase 6)
```
src/
  main.py             # FastAPI app, CORS, static files, rate limiter
  router.py           # agrega routers (evaluate + health + jobs + session)
  routes/
    evaluate.py       # POST /evaluate — recibe archivo, extrae texto, llama evaluate_cv()
    health.py         # GET /health
    jobs.py           # GET /jobs, GET /jobs/ranked, POST /jobs/score
    session.py        # POST /session, GET /session/{token}, DELETE /session/{token}
    view/public/      # sirve job-detail.html como página estática
  static/
    index.html        # página ATS original
    app.js / style.css
    jobs.html         # job board con CV bar, similarity bars, score badges
    jobs.css          # estilos del job board
    jobs.js           # fetch /jobs/ranked, score badges, CV upload bar, keyboard nav
    job-detail.html   # ★ NUEVA — página de detalle de oferta laboral
    job-detail.js     # lógica: carga job_id, muestra scoring vs CV de sesión
backend/
  evaluator.py        # chain LangChain → Claude (structured output ResumeEvaluation)
  extractor.py        # extract_text() via liteparse
  jobs.py             # Job model, strip_html(), fetch_jobs(), caché 15 min
  sessions.py         # ★ NUEVO — CVSession model, cv_sessions dict, store/get/delete/cleanup
  ranker.py           # embed_text(), cosine_similarity(), get_jobs_collection(), upsert_job() — Zvec index at ./zvec_jobs
  scorer.py           # ★ NUEVO — JobMatch model, score_job() con claude-haiku-4-5
  prompts/
    ats_skill.md      # prompt de evaluación ATS
tests/
  conftest.py         # fixture client (TestClient de FastAPI)
  test_jobs.py        # 13 tests: strip_html, Job model, fetch_jobs, GET /jobs
  test_sessions.py    # ★ NUEVO — tests de CVSession store/get/delete/cleanup/TTL
  test_ranker.py      # ★ NUEVO — tests de embed_text, cosine_similarity, rank_jobs
  test_scorer.py      # ★ NUEVO — tests de score_job (mocked LLM)
  test_evaluate.py    # ★ NUEVO — tests de POST /evaluate con session CV header
```

## Variables de entorno
- `ANTHROPIC_API_KEY` — requerida
- `FRONTEND_BASE_URL` — para CORS (default: `http://localhost:3000`)

## Estrategia de ramas (Git workflow)

- **`main`**: producción. Solo recibe merges cuando una feature está probada y lista para deploy.
- **`develop`**: rama de integración. Todo el trabajo del meta-prompt de job board se integra aquí.
- **Feature branches**: se crean desde `develop` y se mergean de vuelta a `develop`.
  - Nombrado: `feature/phase-N-descripcion` (ej: `feature/phase-2-sessions`)
  - Nunca trabajar directo en `develop` ni en `main`.

**No usamos worktrees.** Se trabaja directamente en el repo clonado, cambiando de rama con `git checkout`.

```bash
# Flujo típico para una nueva fase
git checkout develop
git pull origin develop
git checkout -b feature/phase-N-descripcion
# ... implementar ...
git push origin feature/phase-N-descripcion
# mergear a develop cuando esté lista
```

## Comandos
```bash
# Instalar dependencias
pip install -e .

# Correr localmente
uvicorn src.main:app --reload

# Tests
pytest tests/ -v

# Lint (solo archivos del proyecto, no pre-existing issues en main.py/evaluator.py)
ruff check backend/jobs.py src/routes/jobs.py src/router.py tests/
```

## Convenciones
- Imports absolutos desde `src.*` y `backend.*`
- Logging con `logging.getLogger(__name__)` en cada módulo
- Errores HTTP: `HTTPException` para errores internos; `JSONResponse` cuando se necesita shape `{"detail": "...", "code": "..."}` (e.g. upstream errors)
- El modelo pydantic `ResumeEvaluation` define el contrato de respuesta de `/evaluate`
- Tests: TDD estricto — tests primero, luego implementación
- Frontend: vanilla JS, sin frameworks, sin build steps
- Accesibilidad: cards con `tabindex="0"`, `aria-label`, navegación con Enter/Space
- Seguridad JS: todo dato de API pasa por `escHtml()`, URLs por `safeUrl()`

---

## Meta-prompt activo: Job Board con CV-Aware Scoring

Plan completo en: `docs/superpowers/plans/2026-04-03-job-board-cv-scoring.md`

### Estado de las fases

| Fase | Estado | Rama |
|------|--------|------|
| **Fase 1** — Job listings desde API pública | ✅ Completa | mergeada a `develop` |
| **Fase 2** — Session management + CV upload | ✅ Completa | mergeada a `develop` |
| **Fase 2.5** — Embedding-based job ranking | ✅ Completa | mergeada a `develop` |
| **Fase 3** — LLM scoring CV vs jobs (per-job) | ✅ Completa | mergeada a `develop` |
| **Fase 4** — Job detail + integración evaluate | ✅ Completa | mergeada a `develop` |
| **Fase 5** — Polish + rate limiting | ✅ Completa | `feature/phase-5-polish` |
| **Fase 6** — Zvec persistent vector DB, job limit 100 | ✅ Completa | `feature/phase-6-zvec` |

### Fase 1 — Qué se implementó

**Backend:**
- `backend/jobs.py`: modelo `Job` (Pydantic), `strip_html()` (limpia HTML de Remotive), `fetch_jobs()` async con caché de 15 min en memoria (`_cache` dict a nivel de módulo)
- `src/routes/jobs.py`: `GET /jobs` → llama `fetch_jobs()`, devuelve `list[Job]` como JSON. 502 si Remotive falla, 500 si error interno
- `src/router.py`: registra el nuevo router de jobs

**Frontend (`src/static/`):**
- `jobs.html`: página de job board con sticky CV bar (placeholder para Fase 2), header con nav, toolbar de sort, grid de cards
- `jobs.css`: estilos específicos — grid 1/2/3 col responsive (768px / 1200px), job cards con hover glow, score badge oculto (Fase 3), `.empty-state`
- `jobs.js`: `loadJobs()` → `fetch('/jobs')`, `renderJobCard()` con escaping XSS + `safeUrl()`, sort por fecha (default) y score (stub Fase 3), keyboard nav

**Tests (13 en total):**
- `strip_html` (4 tests), `Job model` (2), `fetch_jobs` con mocks respx (4), `GET /jobs` route (3)

### Fase 2 — Qué se implementó

**Backend:**
- `backend/sessions.py`: modelo `CVSession` (Pydantic), dict `cv_sessions`, `store_session()`, `get_session()`, `delete_session()`, `cleanup_sessions()` con TTL 60 min (lazy cleanup al crear sesión)
- `src/routes/session.py`: `POST /session` (recibe archivo, extrae texto, guarda sesión, devuelve `{token, filename, char_count}`), `GET /session/{token}`, `DELETE /session/{token}`. Validación UUID en GET/DELETE. Límite 5 MB por archivo.

**Frontend:**
- CV bar activada en `jobs.html`: botón "Upload your CV" → chip con nombre + X para remover. Token guardado en `localStorage["cv_session_token"]`. Reutiliza el token si ya existe.

**Decisiones de diseño:**
- Solo texto extraído en memoria del servidor (no localStorage base64, no cloud storage)
- Token = UUID generado en servidor
- Para prod >100 usuarios: migrar a Redis (no implementado)

### Fase 2.5 — Qué se implementó

**Backend:**
- `backend/ranker.py`: carga `SentenceTransformer("all-MiniLM-L6-v2")` (lazy), `embed_text()`, `cosine_similarity()`, `rank_jobs()` — ordena lista de `Job` por similitud coseno contra el embedding del CV
- `CVSession` extendida con campo `cv_embedding: list[float]` — se calcula al hacer `store_session()`
- `GET /jobs/ranked`: acepta `?token=` query param, devuelve jobs ordenados por `similarity_score` (0–1). Fallback graceful si no hay sesión o embedding.

**Frontend:**
- Similarity bars visuales por job card
- Banner mostrando que los resultados están ordenados por compatibilidad
- Collapse de trabajos con similitud muy baja

### Fase 3 — Qué se implementó

**Backend:**
- `backend/scorer.py`: modelo `JobMatch` (score 0–100, match_level, matched_skills, missing_skills, one_line_summary), `score_job(cv_text, job)` async usando `claude-haiku-4-5` con structured output
- `POST /jobs/score`: acepta `{token, job_ids?, limit?}`, toma el CV de la sesión, rankea jobs por embedding, hace scoring LLM en paralelo con `asyncio.gather()` sobre los top-N. Cachea resultados en `session.scored_jobs`. Rate limit: 3/min por IP.

**Frontend:**
- Score badges animados en cards (strong/good/partial/weak con colores)
- Lista de matched skills visible en cada card
- Botón "Score more" para pedir scoring de más jobs

**Tests:** `test_scorer.py` (LLM mockeado), `test_ranker.py`

### Fase 4 — Qué se implementó

**Backend:**
- `src/routes/view/public/`: sirve `job-detail.html` como ruta estática (`GET /jobs/{id}`)
- `POST /evaluate` extendido: acepta header `X-CV-Session-Token` para usar el CV de la sesión en lugar de subir archivo nuevamente

**Frontend:**
- `src/static/job-detail.html` + `job-detail.js`: página de detalle de oferta
  - Lee `job_id` de la URL (`?id=...`)
  - Carga datos del job desde `/jobs` (filtra por id)
  - Si hay sesión activa, muestra el scoring LLM (o lo solicita)
  - Renderiza descripción completa, matched/missing skills, summary

### Fase 5 — Qué se implementó

- Rate limiting aplicado a `POST /session` (3/min por IP) con `slowapi`
- Rate limiting aplicado a `POST /jobs/score` (3/min por IP)
- `TESTING.md`: guía de testing manual y escenarios de prueba documentados
