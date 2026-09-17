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
- GitHub Actions (`ci.yml`) corre ruff + pytest en cada PR. Es el único gate real.
- `main` además tiene `claude-code-review.yml` y `claude.yml` (Claude Actions), que **hoy fallan**:
  el secret `CLAUDE_CODE_OAUTH_TOKEN` está vencido. Hay que renovarlo o borrar esos workflows.

### Deploy
Producción: **VPS Vultr `64.176.23.59`** (`aurea.pablolerner.dev`, respaldo `aurea-cv.duckdns.org`).

- `botcv.service` → `uv run --frozen uvicorn src.main:app` en `127.0.0.1:8000`, usuario `deploy`,
  working dir `/home/deploy/bot_curriculum`, env en el `.env` de ese directorio.
- Caddy hace TLS y ruteo (`/etc/caddy/Caddyfile`). El snippet `lazy` duerme el servicio cuando
  no hay tráfico y lo despierta con la primera navegación — que `botcv` figure `inactive`
  es normal, no es que esté caído.
- La rama desplegada es `main`.

### Deploy automático

Cada push a `main` dispara el job `deploy` de `ci.yml`, que corre después de los tests.
Entra por SSH al VPS y ejecuta `/home/deploy/deploy.sh`, después verifica `/health` desde
el runner con reintentos. Si no responde, el workflow falla — no hay rollback automático.

- `deploy/deploy.sh` en el repo es la copia de referencia. La que se ejecuta vive en
  `/home/deploy/deploy.sh`, **fuera del árbol de git**: si estuviera adentro, el checkout
  la reescribiría mientras corre. Si cambia acá, hay que reinstalarla allá.
- La clave SSH de CI está restringida con `command="/home/deploy/deploy.sh"` en el
  `authorized_keys` del usuario `deploy`. Esto importa: ese usuario tiene `NOPASSWD:ALL`
  en `/etc/sudoers.d/deploy`, así que sin el forced command la clave sería root.
- Secrets del repo: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`.
- El script nunca hace `git clean`: el `.env` vive en ese directorio y no está trackeado.

```bash
# Deploy manual (si hace falta saltear CI)
ssh linuxuser@64.176.23.59
sudo -iu deploy
/home/deploy/deploy.sh
```

Render.com (`render.yaml`) quedó sin usar.

## Variables de entorno

```
ANTHROPIC_API_KEY          # requerida — Claude AI
SUPABASE_URL               # requerida — URL del proyecto Supabase
SUPABASE_ANON_KEY          # requerida — clave pública de Supabase
SUPABASE_SERVICE_ROLE_KEY  # opcional — usada en waitlist si está disponible
SUPABASE_KEY               # opcional — SI se setea, sessions.py persiste los CVs en la tabla
                           #   cv_sessions en vez de usar memoria. Hoy NO se setea en prod
                           #   a propósito: esa tabla tiene RLS deshabilitada.
FRONTEND_BASE_URL          # para CORS (default: http://localhost:3000)

AUREA_EXTRACT_MODEL        # opcional — modelo etapa 1 (default: claude-haiku-4-5)
AUREA_ADAPT_MODEL          # opcional — modelo etapa 2 (default: claude-haiku-4-5)
AUREA_COVER_MODEL          # opcional — modelo cover letter (default: claude-haiku-4-5)
AUREA_INTERVIEW_MODEL      # opcional — modelo interview prep (default: claude-haiku-4-5)
```

El mapeo stage → modelo vive en `backend/models.py` (`model_for(stage)`).

## Estructura de archivos

```
backend/
  models.py         # model_for(stage) — modelo por etapa, configurable por env var
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
    interview.py    # Interview prep: preguntas + respuestas borrador
                    # (on-demand desde POST /interview, fuera de run_pipeline)
    renderer.py     # Genera PDF del CV adaptado
    logger.py       # Logging compartido del pipeline
  evaluator.py      # ATS evaluator (producto secundario)
  extractor.py      # extract_text() — descarta texto invisible (color/tamaño/posición
                    # + caracteres zero-width); usado en /adapt, /evaluate y /session
  jobs.py           # Job model, fetch_jobs(), caché 15 min (job board)
  sessions.py       # CVSession model, store/get/delete/cleanup con TTL 60 min
                    # Backend dual: Postgres si hay SUPABASE_KEY, si no dict en memoria
  ranker.py         # Embeddings + Zvec vector DB para ranking de jobs
  scorer.py         # LLM scoring CV vs job (job board)
  prompts/
    adapt_cv.md         # Prompt etapa 2 (adapter)
    extract_schema.md   # Prompt etapa 1 (extractor)
    cover_letter.md     # Prompt cover letter
    interview_prep.md   # Prompt interview prep
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
    interview.py    # POST /interview — preguntas de entrevista para una adaptación ya hecha
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
  conftest.py              # fixture client (TestClient de FastAPI) + fixture autouse que
                           # fuerza sesiones en memoria — sin eso la suite pega contra la
                           # Supabase real cuando hay SUPABASE_URL + SUPABASE_KEY en el env
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
  test_interview.py        # backend/adapter/interview.py
  test_interview_route.py  # POST /interview
  test_extractor.py        # backend/extractor.py — filtrado de texto oculto e invisible
  test_jobs.py             # Job board backend
  test_models.py           # backend/models.py — model_for(stage) y defaults
  test_ranker.py
  test_scorer.py
  test_sessions.py
  test_waitlist.py         # POST /waitlist
```

## Supabase — tablas y patrones

### Tablas
| Tabla | PK | Campos clave | RLS |
|---|---|---|---|
| `credits` | `user_id TEXT` | `balance INT DEFAULT 2` | ✅ |
| `waitlist` | `email TEXT` | `user_id TEXT`, `created_at` | ✅ |
| `cv_sessions` | `token` | CV persistido del job board | ❌ |
| `pipeline_runs` | — | runs del pipeline | ❌ |

⚠️ `cv_sessions` y `pipeline_runs` tienen **RLS deshabilitada**: con la anon key (que es pública,
la sirve `GET /config`) cualquiera lee y escribe todas sus filas. Por eso prod corre sin
`SUPABASE_KEY`. Antes de activar RLS hay que escribir las políticas, o se bloquea todo acceso.

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
→ (opcional) "Prepare for the interview" → POST /interview → preguntas + respuestas borrador
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

**Claude abre el PR; no mergea por iniciativa propia.** Mergea únicamente cuando el usuario
se lo pide de forma explícita en esa conversación — incluido `main`. La autorización no se
arrastra a la tarea siguiente: si no lo pidió, el merge lo hace el usuario en GitHub.

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
# 5. Si pasan → mergea el usuario (o Claude, si el usuario se lo pide) y se elimina la rama
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
- **`.mcp.json` no se versiona** (está en `.gitignore`): contiene el access token de Supabase.
  Tampoco versionar `*.traineddata` ni ningún otro binario grande.

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
| 3.8 | Deploy productivo | ✅ en VPS Vultr (Railway descartado: sin free tier) |
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
| 3.20 | UX fixes: sin highlight persistente en tab Adapter, botón Sign in glass | ✅ mergeada |
| 3.21 | — (no existe: la numeración salta de 3.20 a 3.22) | — |
| 3.22 | Model config por etapa — `backend/models.py` + env vars `AUREA_*_MODEL` | ✅ mergeada |
| 3.23 | Hardening anti prompt-injection: descarta texto oculto del CV, CV como dato no confiable | ✅ mergeada |
| 3.24 | Deploy de Aurea al VPS + doc de deploy | ✅ mergeada |
| 3.25 | Actualizar CLAUDE.md | ✅ mergeada |
| 3.26 | Header nav: mismo set de tabs, pill de dos filas en pantallas angostas | ✅ mergeada |
| 3.27 | Interview prep — `POST /interview` + panel en resultados | ✅ mergeada |
| 3.28 | Deploy automático al VPS en cada push a `main` | 🔀 PR abierto |

**Sprint 3 cerrado y releaseado**: `main` está al día con `develop` (PR #29). La única tarea
abierta es **3.5 (Lemon Squeezy)**, bloqueada porque necesita cuenta de merchant.

## Deuda abierta

1. **Rotar los access tokens de Supabase**: `.mcp.json` estuvo versionado con el token `sbp_…`
   en texto plano. Se untrackeó, pero dos tokens siguen en el historial público de GitHub.
2. **RLS deshabilitada** en `cv_sessions` y `pipeline_runs` (ver sección Supabase).
3. **Secret `CLAUDE_CODE_OAUTH_TOKEN` vencido** → los workflows de Claude Actions en `main` fallan.
4. **Confirmar el redirect del magic link**: falta verificar que Supabase acepte
   `https://aurea.pablolerner.dev` (Auth → URL Configuration). Solo se comprueba con un login real.
5. **Límite conocido del filtro de texto oculto** (marcado con comentario `ponytail:` en
   `backend/extractor.py`): pdfplumber no expone text render mode ni alpha, así que `3 Tr`,
   opacidad 0 y texto tapado por una imagen todavía pasan.
