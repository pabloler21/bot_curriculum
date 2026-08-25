# CLAUDE.md — Aurea

## Proyecto

**Aurea** — SaaS de adaptación de CVs con IA. El usuario sube su CV + pega una descripción de trabajo → la app adapta el CV al rol, detecta skill gaps y genera una cover letter personalizada. Modelo freemium: 2 adaptaciones gratis, luego Pro (coming soon).

El proyecto también incluye un **job board** (herramienta secundaria, pre-existente) con scoring de CV contra ofertas de Remotive, búsqueda client-side e integración directa con el adapter.

## Stack

### Backend
- **Python 3.13**, `uv` como package manager
- **FastAPI** + uvicorn, rate limiting con slowapi (3/min por IP en `/adapt`)
- **AI**: `claude-haiku-4-5` vía LangChain con structured output (Pydantic)
- **Auth**: Supabase magic link → JWT validado en cada request con `supabase.auth.get_user(token)`
- **DB**: Supabase (PostgreSQL) — tablas `credits` y `waitlist`
- **Extracción de texto**: pdfplumber (PDFs, filtra texto oculto) + liteparse (DOCX y OCR de escaneos)
- **HTTP async**: httpx

### Frontend
- HTML/JS/CSS vanilla, sin frameworks, sin build steps
- Fuente Inter (Google Fonts)
- Supabase JS CDN en `adapt.html` y `pricing.html` para auth client-side

### Testing y calidad
- pytest + pytest-asyncio, mocks con `unittest.mock`
- ruff (linter)
- GitHub Actions corre `pytest` en cada PR

### Deploy
- Render.com (`render.yaml`) — pendiente de configurar para Aurea
- Variables de entorno requeridas (ver abajo)

## Variables de entorno

```
ANTHROPIC_API_KEY          # requerida — Claude AI
SUPABASE_URL               # requerida — URL del proyecto Supabase
SUPABASE_ANON_KEY          # requerida — clave pública de Supabase
SUPABASE_SERVICE_ROLE_KEY  # opcional — usada en waitlist si está disponible
FRONTEND_BASE_URL          # para CORS (default: http://localhost:3000)
```

## Estructura de archivos

```
backend/
  auth.py           # get_current_user(), get_required_user(), OptionalUser, RequiredUser
  credits.py        # get_balance(), ensure_user(), decrement(), restore(), add_credits()
                    # InsufficientCredits exception
  schemas.py        # AdaptationResult, CVSchema, WorkExperience, PipelineStatus, etc.
  adapter/
    pipeline.py     # run_pipeline() — orquesta las 3 etapas + cover letter
    extractor.py    # Etapa 1: extrae CVSchema estructurado del texto del CV
    adapter.py      # Etapa 2: adapta el CVSchema al job description
    validator.py    # Etapa 3: valida que no haya alucinaciones (anti-hallucination)
    cover_letter.py # Etapa 4: genera la cover letter
    renderer.py     # Genera PDF del CV adaptado
    logger.py       # Logging compartido del pipeline
  evaluator.py      # ATS evaluator (producto secundario)
  extractor.py      # extract_text() — descarta texto invisible (color/tamaño/posición
                    # + caracteres zero-width); usado en /adapt, /evaluate y /session
  jobs.py           # Job model, fetch_jobs(), caché 15 min (job board)
  sessions.py       # CVSession model, store/get/delete/cleanup con TTL 60 min
  ranker.py         # Embeddings + Zvec vector DB para ranking de jobs
  scorer.py         # LLM scoring CV vs job (job board)
  prompts/
    adapt_cv.md         # Prompt etapa 2 (adapter)
    extract_schema.md   # Prompt etapa 1 (extractor)
    cover_letter.md     # Prompt cover letter
    ats_skill.md        # Prompt ATS evaluator

src/
  main.py           # FastAPI app: CORS, static files, rate limiter global
  router.py         # Registra todos los routers
  routes/
    adapt.py        # POST /adapt — pipeline principal; GET /adapt/{run_id}/pdf
    auth.py         # (no existe como ruta — auth es dependency injection)
    config.py       # GET /config — devuelve SUPABASE_URL y SUPABASE_ANON_KEY al frontend
    credits.py      # GET /credits — devuelve balance del usuario autenticado
    evaluate.py     # POST /evaluate — ATS evaluator (producto secundario)
    health.py       # GET /health
    jobs.py         # GET /jobs, GET /jobs/ranked, POST /jobs/score (job board)
    session.py      # POST/GET/DELETE /session — CV sessions del job board
    waitlist.py     # POST /waitlist — registra interés en plan Pro
  static/
    adapt.html      # ★ PRINCIPAL — CV Adapter UI con auth modal + credit chip
    adapt.js        # Lógica: auth Supabase, upload CV, pipeline, results rendering,
                    # localStorage: SESSION_KEY (cv session), RESULT_KEY (último resultado),
                    # PENDING_JD_KEY (JD pre-cargado desde job board)
    pricing.html    # Pricing page: Free ($0) y Pro (coming soon)
    pricing.js      # Waitlist logic: detecta auth, botón "Notify me"
    index.html      # ATS Evaluator (producto secundario)
    app.js          # Lógica del ATS evaluator
    style.css       # Estilos globales: design system, componentes compartidos,
                    # pricing cards, auth modal, credit chip, waitlist confirm
    jobs.html       # Job Board (producto secundario)
    jobs.css        # Estilos del job board
    jobs.js         # Lógica del job board: búsqueda client-side (filteredJobs, filterByTag),
                    # CV upload, ranking, scoring background
    job-detail.html # Detalle de oferta laboral
    job-detail.js   # Lógica del detalle: carga job, CTA "Adapt my CV to this role"
                    # guarda JD en localStorage (aurea_pending_jd) y redirige a adapt.html

supabase/
  migrations/
    20260502000000_credits.sql          # Tabla credits + RLS + funciones SQL atómicas
    20260502000001_credits_default_2.sql # DEFAULT balance = 2
    20260502000002_waitlist.sql         # Tabla waitlist + RLS

tests/
  conftest.py              # fixture client (TestClient de FastAPI)
  test_adapt_route.py      # POST /adapt y GET /adapt/{run_id}/pdf
  test_adapter_adapter.py  # backend/adapter/adapter.py
  test_adapter_extractor.py
  test_adapter_pipeline.py
  test_adapter_schemas.py
  test_adapter_validator.py
  test_auth.py             # get_current_user() dependency + /adapt auth gate
  test_credits.py          # backend/credits.py — todas las funciones
  test_credits_route.py    # GET /credits
  test_evaluate.py         # POST /evaluate con session token
  test_jobs.py             # Job board backend
  test_ranker.py
  test_scorer.py
  test_sessions.py
  test_waitlist.py         # POST /waitlist
```

## Supabase — tablas y patrones

### Tablas
| Tabla | PK | Campos clave |
|---|---|---|
| `credits` | `user_id TEXT` | `balance INT DEFAULT 2` |
| `waitlist` | `email TEXT` | `user_id TEXT`, `created_at` |

### Funciones SQL atómicas
- `decrement_credits(p_user_id, p_amount)` — UPDATE atómico, lanza excepción si `balance < amount`
- `increment_credits(p_user_id, p_amount)` — UPDATE atómico para restore/add

### Patrones de auth en backend
```python
# backend/auth.py
OptionalUser = Annotated[str | None, Depends(get_current_user)]  # None si no autenticado
RequiredUser = Annotated[str, Depends(get_required_user)]        # 401 si no autenticado

# Uso en routes:
async def adapt_resume(user_id: RequiredUser, ...):   # requiere JWT
def get_credits(user_id: RequiredUser):               # requiere JWT
def join_waitlist(user_id: OptionalUser, ...):        # opcional
```

### Patrones de créditos
```python
ensure_user(user_id)   # upsert idempotente — crea fila con balance=2 si no existe
decrement(user_id)     # lanza InsufficientCredits si balance = 0
restore(user_id)       # llamar en except si el pipeline falla post-decrement
get_balance(user_id)   # retorna int (0 si no hay fila o Supabase no disponible)
```
Todas las funciones son **no-op seguros** cuando `_supabase is None` (dev sin credenciales).

## Flujo del usuario (happy path)

```
adapt.html → Sign in (magic link) → Ver "✦ 2" créditos en header
→ Subir CV + pegar JD → POST /adapt → Pipeline 3 etapas + cover letter
→ Ver CV adaptado + gaps + cover letter + PDF download
→ Resultado guardado en localStorage (RESULT_KEY)
→ Crédito baja a 1 → Segunda adaptación → Crédito a 0
→ Banner "You've used all your free adaptations" → adapt btn deshabilitado
→ pricing.html → "Notify me when Pro launches" → Confirmación

Flujo alternativo (desde job board):
jobs.html → buscar oferta → job-detail.html → "Adapt my CV to this role"
→ JD guardado en localStorage (PENDING_JD_KEY) → redirige a adapt.html
→ textarea pre-cargado con el JD → usuario sube CV → POST /adapt
```

## Estrategia de ramas (Git workflow)

- **`main`**: producción. Solo recibe merges cuando el usuario decide hacer un release explícito.
- **`develop`**: rama de integración. Todo el trabajo se integra aquí vía PR.
- **Feature branches**: se crean desde `develop`, se mergean a `develop` vía PR, y se eliminan después del merge.
  - Nombrado: `feature/task-N-N-descripcion` (ej: `feature/task-3-1-supabase-auth`)

**Claude nunca mergea ni pushea a `main`.** El merge siempre lo hace el usuario en GitHub.

### Flujo por tarea

```bash
# 1. Iniciar tarea
git checkout develop
git pull origin develop
git checkout -b feature/task-N-N-descripcion

# 2. Implementar (commits atómicos)
# 3. Abrir PR
git push origin feature/task-N-N-descripcion
gh pr create --base develop --title "..." --body "..."

# 4. CI corre los tests automáticamente en GitHub Actions
# 5. Si pasan → el usuario mergea en GitHub y elimina la rama
# 6. Al iniciar la siguiente tarea → volver al paso 1
```

**Nunca trabajar directo en `develop` ni en `main`.**
**No usamos worktrees.** Se trabaja directamente en el repo clonado.

## Comandos

```bash
# Instalar dependencias
uv sync   # o: pip install -e .

# Correr localmente
uvicorn src.main:app --reload
# → http://localhost:8000/adapt.html

# Tests
pytest tests/ -v
pytest tests/ -q   # resumen

# Lint
ruff check backend/ src/routes/ tests/
```

## Convenciones

- Imports absolutos: `from backend.X import ...`, `from src.routes.X import ...`
- Logging: `logging.getLogger(__name__)` en cada módulo
- Errores HTTP: `HTTPException` para errores del servidor; `JSONResponse` cuando se necesita `{"detail": "...", "code": "..."}` (ej: `no_credits`)
- Tests: **TDD estricto** — tests primero, luego implementación
- Frontend: vanilla JS, sin frameworks, sin build steps
- Seguridad JS: todo dato de API pasa por `escHtml()` antes de tocar el DOM
- **Patch location en tests**: siempre parchear en el lugar de importación, no en la definición:
  - ✅ `patch("src.routes.adapt.ensure_user")`
  - ❌ `patch("backend.credits.ensure_user")`
- **Patch de `OptionalUser`**: como `Depends(get_current_user)` guarda la referencia directa, parchear `backend.auth._supabase`, no `backend.auth.get_current_user`

## Estado actual de tareas

| Task | Descripción | Estado |
|------|-------------|--------|
| 3.1 | Supabase Auth — `get_current_user`, magic link modal | ✅ mergeada |
| 3.2 | `RequiredUser` en `/adapt` — 401 sin JWT | ✅ mergeada |
| 3.3 | Login modal en `adapt.html` + `adapt.js` | ✅ mergeada |
| 3.4 | Tabla `credits` + funciones SQL atómicas | ✅ mergeada |
| 3.5 | Lemon Squeezy payments | ⏸ requiere dinero |
| 3.6 | `pricing.html` — página de pricing Free/Pro | ✅ mergeada |
| 3.7 | Free tier: `ensure_user` + `decrement` + `restore` en `/adapt` | ✅ mergeada |
| 3.8 | Railway deploy | ⏸ requiere dinero |
| 3.9 | `GET /credits` + credit chip `✦ N` en header | ✅ mergeada |
| 3.10 | Proactive credit gate — deshabilita botón si balance = 0 | ✅ mergeada |
| 3.11 | Waitlist — `POST /waitlist` + botón "Notify me" en pricing | ✅ mergeada |
| 3.12 | UX polish: 429 feedback, sign-out limpia sesión, Pricing tab nav | ✅ mergeada |
| 3.13 | Actualizar CLAUDE.md | ✅ mergeada |
| 3.14 | Persist resultado en localStorage + banner "View result" | ✅ mergeada |
| 3.15 | Job board → adapter handoff ("Adapt my CV to this role") | ✅ mergeada |
| 3.16 | Job board: búsqueda client-side + filtro por tags | ✅ mergeada |
| 3.17 | Actualizar CLAUDE.md | ✅ mergeada |
| 3.18 | Job cards clickeables con el mouse | ✅ mergeada |
| 3.19 | Mobile responsive layout (`adapt.html`, header, hero) | ✅ mergeada |
