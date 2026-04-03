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

## Estructura actual (post Fase 1)
```
src/
  main.py             # FastAPI app, CORS, static files, rate limiter
  router.py           # agrega routers (evaluate + health + jobs)
  routes/
    evaluate.py       # POST /evaluate — recibe archivo, extrae texto, llama evaluate_cv()
    health.py         # GET /health
    jobs.py           # GET /jobs — devuelve listado de trabajos (con caché 15 min)
  static/
    index.html        # página ATS original
    app.js / style.css
    jobs.html         # ★ NUEVA — job board con cards responsivas
    jobs.css          # estilos específicos del job board
    jobs.js           # lógica: fetch /jobs, render cards, sort, teclado/aria
backend/
  evaluator.py        # chain LangChain → Claude (structured output ResumeEvaluation)
  extractor.py        # extract_text() via liteparse
  jobs.py             # ★ NUEVO — Job model, strip_html(), fetch_jobs(), caché 15 min
  prompts/
    ats_skill.md      # prompt de evaluación ATS
tests/
  conftest.py         # fixture client (TestClient de FastAPI)
  test_jobs.py        # 13 tests: strip_html, Job model, fetch_jobs, GET /jobs
```

## Variables de entorno
- `ANTHROPIC_API_KEY` — requerida
- `FRONTEND_BASE_URL` — para CORS (default: `http://localhost:3000`)

## Comandos
```bash
# Instalar dependencias
pip install -e .

# Correr localmente (desde el worktree de la rama activa)
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
| **Fase 1** — Job listings desde API pública | ✅ Completa | `feature/phase-1-job-listings` |
| **Fase 2** — Session management + CV upload | ⏳ Pendiente | — |
| **Fase 3** — Scoring CV vs jobs (per-job) | ⏳ Pendiente | — |
| **Fase 4** — Job detail + integración evaluate | ⏳ Pendiente | — |
| **Fase 5** — Polish + producción | ⏳ Pendiente | — |

### Worktree activo
```
.worktrees/phase-1-job-listings   ← rama feature/phase-1-job-listings
                                    (pendiente de merge a main)
```

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

### Fase 2 — Qué viene (contexto para retomar)

Implementar sesiones de CV en memoria del servidor:
- `backend/sessions.py`: modelo `CVSession`, dict `cv_sessions`, `store_session()`, `get_session()`, `delete_session()`, `cleanup_sessions()` (TTL 60 min)
- `src/routes/session.py`: `POST /session` (sube CV, extrae texto, guarda sesión, devuelve token UUID), `GET /session/{token}`, `DELETE /session/{token}`
- Frontend: activar el CV bar que ya existe en `jobs.html` — botón "Upload your CV" → chip con nombre de archivo + X para remover. Token en `localStorage["cv_session_token"]`

**Decisiones de diseño ya tomadas:**
- NO usar localStorage base64 ni cloud storage — solo texto extraído en memoria del servidor
- Token = UUID generado en el servidor
- Cleanup lazy (al guardar nueva sesión) + TTL 60 min
- Reutilizar `backend/extractor.py` existente, no duplicar lógica
- Para prod a escala >100 usuarios: migrar a Redis (no implementar ahora)

### Cómo retomar en la próxima sesión

1. Leer `docs/superpowers/plans/2026-04-03-job-board-cv-scoring.md` — contiene el plan detallado de todas las fases con código exacto
2. Decir "empezar Fase 2" → usar `superpowers:executing-plans` o `superpowers:subagent-driven-development`
3. Primero mergear `feature/phase-1-job-listings` a `main` si aún no se hizo
