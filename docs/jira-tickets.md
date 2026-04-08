# Jira Tickets — develop vs main
# Instrucciones para la próxima sesión:
# Leer este archivo y crear cada ticket en Jira usando el MCP.
# Crear primero los Epics, luego las Stories/Tasks linkadas a su Epic.

---

## EPICS

| Key | Nombre |
|-----|--------|
| EPIC-1 | Job Board — Backend (Fase 1) |
| EPIC-2 | Job Board — Frontend (Fase 1) |
| EPIC-3 | Session Management (Fase 2) |
| EPIC-4 | Embedding-Based Ranking (Fase 2.5) |
| EPIC-5 | LLM Scoring (Fase 3) |
| EPIC-6 | Job Detail Page (Fase 4) |
| EPIC-7 | Rate Limiting (Fase 5) |
| EPIC-8 | Zvec — Vector DB Persistente (Fase 6) |
| EPIC-9 | Glassmorphism + UX Redesign (Fase 6) |
| EPIC-10 | Testing |
| EPIC-11 | Documentación |

---

## EPIC-1: Job Board — Backend (Fase 1)

### JOB-001
- **Tipo:** Story
- **Título:** Modelo `Job` y función `strip_html()`
- **Componente:** `backend/jobs.py`
- **Descripción:** Crear el modelo Pydantic `Job` con campos: `id: str`, `title: str`, `company: str`, `location: str`, `employment_type: str`, `salary_range: Optional[str]`, `description: str`, `tags: list[str]`, `url: str`, `posted_at: date`. Crear clase interna `_HTMLStripper` que hereda de `HTMLParser` y exponer `strip_html(html: str) -> str` para limpiar HTML de las descripciones de Remotive.
- **AC:**
  - `strip_html("<b>Hello</b>")` → `"Hello"`
  - `strip_html("")` → `""`
  - `Job` se puede instanciar con `salary_range=None` sin error
  - `posted_at` es `date` (no `datetime`)

### JOB-002
- **Tipo:** Story
- **Título:** `fetch_jobs()` async con caché de 15 minutos
- **Componente:** `backend/jobs.py`
- **Descripción:** Implementar `fetch_jobs() -> list[Job]` usando `httpx.AsyncClient`. Consulta `https://remotive.com/api/remote-jobs` con `category=software-dev&limit=100`. Caché en memoria con `_cache: dict` a nivel de módulo (TTL 900s). Al fetchear nuevos jobs, hace upsert automático en Zvec (lazy import de `backend.ranker`). El mapper `_map_job(raw: dict) -> Job` convierte el raw de Remotive al modelo.
- **AC:**
  - Segunda llamada dentro de 15 min no hace HTTP request
  - Pasados 15 min hace fetch fresco
  - `_parse_date` usa `date.today()` como fallback ante fechas malformadas
  - Upsert en Zvec es best-effort: fallo silencioso con `logger.warning`
  - Límite de jobs: 100

### JOB-003
- **Tipo:** Story
- **Título:** `GET /jobs` endpoint con fallback 502
- **Componente:** `src/routes/jobs.py`, `src/router.py`
- **Descripción:** Crear `GET /jobs` que llama `fetch_jobs()` y devuelve lista de jobs como JSON. Manejar errores de upstream con `JSONResponse(502)` y errores internos con `JSONResponse(500)`, usando shape `{"detail": "...", "code": "..."}`. Registrar el router en `src/router.py`.
- **AC:**
  - `GET /jobs` → 200 con lista cuando Remotive responde OK
  - → 502 `{"detail": "Could not fetch job listings", "code": "upstream_error"}` si Remotive falla
  - → 500 `{"detail": "Internal server error", "code": "internal_error"}` en excepción inesperada

---

## EPIC-2: Job Board — Frontend (Fase 1)

### JOB-004
- **Tipo:** Story
- **Título:** `jobs.html` — página de job board con grid y CV bar placeholder
- **Componente:** `src/static/jobs.html`
- **Descripción:** Crear la página HTML del job board con: header con nav, sticky CV bar (placeholder para Fase 2), toolbar de sorting, grid de cards, estado vacío `.empty-state`. Estructura semántica con roles aria.
- **AC:**
  - Página carga sin errores
  - CV bar visible pero sin funcionalidad
  - Links de navegación al ATS evaluator

### JOB-005
- **Tipo:** Story
- **Título:** `jobs.css` — estilos grid responsive + job cards
- **Componente:** `src/static/jobs.css`
- **Descripción:** Crear estilos del job board. Grid responsive: 1 col en mobile, 2 en ≥768px, 3 en ≥1200px. Job cards con hover glow. `.score-badge` oculto por defecto (preparado para Fase 3). Estilos para `.empty-state` y loading spinner.
- **AC:**
  - Layout responsive en los 3 breakpoints
  - Cards con transición suave en hover
  - `.score-badge` existe pero hidden

### JOB-006
- **Tipo:** Story
- **Título:** `jobs.js` — `loadJobs()`, `renderJobCard()`, keyboard nav
- **Componente:** `src/static/jobs.js`
- **Descripción:** Implementar lógica del job board: `loadJobs()` hace `fetch('/jobs')`, `renderJobCard()` con escaping XSS via `escHtml()` y `safeUrl()`. Sort por fecha (default) y score (stub). Navegación teclado en cards (`tabindex="0"`, Enter/Space).
- **AC:**
  - Todos los datos de API pasan por `escHtml()` antes del DOM
  - URLs de Apply pasan por `safeUrl()`
  - Sort por fecha funciona correctamente
  - Cards navegables con teclado

### JOB-007
- **Tipo:** Bug
- **Título:** Fix: `safeUrl` en hrefs, animation delay cap, keyboard nav
- **Componente:** `src/static/jobs.js`
- **Descripción:** Tres fixes: (1) `safeUrl()` no se aplicaba a hrefs de Apply buttons; (2) `animation-delay` sin cap causaba delays excesivos en listas largas; (3) keyboard nav con Enter/Space no propagaba correctamente en todos los elementos.

---

## EPIC-3: Session Management (Fase 2)

### SES-001
- **Tipo:** Story
- **Título:** `CVSession` model + store/get/delete/cleanup con TTL 60 min
- **Componente:** `backend/sessions.py`
- **Descripción:** Crear `CVSession` Pydantic con campos: `token`, `cv_text`, `cv_embedding: list[float] = []`, `filename`, `uploaded_at`, `scored_jobs: dict = {}`. Store en memoria `cv_sessions: dict[str, CVSession]`. Funciones: `store_session()` (genera UUID, calcula embedding best-effort), `get_session()` (valida TTL lazy), `delete_session() -> bool`, `cleanup_sessions()` (barre sesiones >60 min, llamada en store).
- **AC:**
  - Sesión con >60 min → `get_session` retorna None y elimina la entrada
  - `cleanup_sessions` elimina solo las expiradas
  - Embedding falla → sesión igual se crea con `cv_embedding = []`
  - `delete_session` retorna False si el token no existe

### SES-002
- **Tipo:** Story
- **Título:** `POST /session` — upload CV, extracción de texto, token UUID
- **Componente:** `src/routes/session.py`
- **Descripción:** Endpoint `POST /session` que acepta archivo multipart. Valida: no vacío, máximo 5 MB. Extrae texto con liteparse. Guarda sesión. Devuelve `{token, filename, char_count}`. Rate limit: 3/min por IP.
- **AC:**
  - 200 → `{"token": "<uuid>", "filename": "cv.pdf", "char_count": 4200}`
  - 400 si archivo vacío
  - 413 si >5 MB
  - 422 si no se puede extraer texto

### SES-003
- **Tipo:** Story
- **Título:** `GET /session/{token}` y `DELETE /session/{token}` con validación UUID
- **Componente:** `src/routes/session.py`
- **Descripción:** `GET /session/{token}`: valida UUID, devuelve `{exists, filename, uploaded_at}` o 404. `DELETE /session/{token}`: valida UUID, elimina sesión, devuelve 204 o 404. Tokens no-UUID → 400 con `code: "invalid_token"`.
- **AC:**
  - Token no-UUID → 400 `{"code": "invalid_token"}`
  - Token no encontrado/expirado → 404 en GET
  - DELETE exitoso → 204 sin body
  - DELETE de token inexistente → 404 `{"code": "session_not_found"}`

### SES-004
- **Tipo:** Story
- **Título:** Frontend: CV upload bar activa con persistencia en localStorage
- **Componente:** `src/static/jobs.js`, `src/static/jobs.html`
- **Descripción:** Activar la CV bar. Botón "Upload your CV" abre file input → `POST /session` → guarda token en `localStorage["cv_session_token"]` → muestra chip con nombre de archivo y botón X. Al X: llama `DELETE /session/{token}` y limpia localStorage. Al cargar página: verifica token existente con `GET /session/{token}` y restaura estado.
- **AC:**
  - Token persiste entre recargas
  - CV bar muestra nombre del archivo de la sesión
  - Quitar CV limpia localStorage y llama al backend

---

## EPIC-4: Embedding-Based Ranking (Fase 2.5)

### RNK-001
- **Tipo:** Story
- **Título:** `embed_text()` y `cosine_similarity()` con SentenceTransformer
- **Componente:** `backend/ranker.py`
- **Descripción:** Crear `backend/ranker.py`. `embed_text(text: str) -> list[float]` usa `SentenceTransformer("all-MiniLM-L6-v2")` con lazy loading (singleton `_model`). `cosine_similarity(a, b) -> float` usa numpy, maneja vectores zero-norm devolviendo 0.0.
- **AC:**
  - Modelo no se carga al importar, solo al primer `embed_text()`
  - `cosine_similarity([0,0,0], [...])` → 0.0 sin ZeroDivisionError
  - `embed_text()` devuelve lista de 384 floats

### RNK-002
- **Tipo:** Story
- **Título:** `cv_embedding` en `CVSession` — calcular en `store_session()`
- **Componente:** `backend/sessions.py`
- **Descripción:** Extender `CVSession` con `cv_embedding: list[float] = []`. En `store_session()`, calcular embedding con `embed_text(cv_text)` tras crear la sesión. Best-effort: si falla, loguear warning y dejar `cv_embedding = []`. Guard en endpoints que consumen el embedding para el caso de lista vacía.
- **AC:**
  - Upload exitoso aunque el embedding falle
  - `cv_embedding` tiene 384 dimensiones cuando se calcula bien

### RNK-003
- **Tipo:** Story
- **Título:** `GET /jobs/ranked` — ranking por similitud con Zvec
- **Componente:** `src/routes/jobs.py`
- **Descripción:** Endpoint `GET /jobs/ranked?token=<uuid>`. Con sesión y embedding: `collection.query(VectorQuery("embedding", vector=cv_embedding), topk=20)`. Cada job incluye `similarity_score: float | null`. Jobs no indexados en Zvec van al final con `similarity_score: null`. Sin token/embedding: todos los jobs con `similarity_score: null`.
- **AC:**
  - Sin token → todos los jobs, `similarity_score: null`
  - Con token válido → ordenados por similitud con score entre 0-1
  - Token UUID inválido → 400 `{"code": "invalid_token"}`
  - Guard si `cv_embedding` está vacío

### RNK-004
- **Tipo:** Story
- **Título:** Frontend: similarity bars, banner de ranking activo, collapse baja relevancia
- **Componente:** `src/static/jobs.js`, `src/static/jobs.css`
- **Descripción:** Con CV activo, usar `GET /jobs/ranked?token=`. Por cada card mostrar barra visual de similitud proporcional al `similarity_score`. Banner informativo que los resultados están ordenados por compatibilidad. Jobs con similitud muy baja quedan de-enfatizados.

---

## EPIC-5: LLM Scoring (Fase 3)

### SCO-001
- **Tipo:** Story
- **Título:** `JobMatch` model + `score_job()` con `claude-haiku-4-5`
- **Componente:** `backend/scorer.py`
- **Descripción:** Crear `backend/scorer.py`. Modelo `JobMatch`: `score: int` (0-100), `match_level: Literal["strong","good","partial","weak"]`, `matched_skills: list[str]`, `missing_skills: list[str]`, `one_line_summary: str` (máx 15 palabras). `score_job(cv_text, job) -> JobMatch` async usa LangChain + `claude-haiku-4-5` con `.with_structured_output(JobMatch)`. Prompt de sistema: recruiter técnico evaluando fit.
- **AC:**
  - Siempre devuelve `JobMatch` válido (structured output)
  - `score` entre 0 y 100
  - `one_line_summary` ≤15 palabras

### SCO-002
- **Tipo:** Story
- **Título:** `POST /jobs/score` — scoring en paralelo con caché en sesión
- **Componente:** `src/routes/jobs.py`
- **Descripción:** Body: `{token: str, limit: int = 8}`. Flujo: validar UUID y sesión, verificar `cv_embedding`, seleccionar top-N via Zvec `collection.query(topk=limit)`, scorear en paralelo con `asyncio.gather()`, cachear en `session.scored_jobs[job_id]`. Fallos individuales: no cachear, devolver campos null, permitir retry. Límite clampeo: [1, 30]. Rate limit: 3/min por IP.
- **AC:**
  - Jobs ya cacheados no se re-scorean
  - Fallo individual no rompe el batch
  - Respuesta: lista de `{job_id, score, match_level, matched_skills, missing_skills, one_line_summary}`

### SCO-003
- **Tipo:** Story
- **Título:** Frontend: score badges animados, matched skills, botón "Score more"
- **Componente:** `src/static/jobs.js`, `src/static/jobs.css`
- **Descripción:** Badge de score por card con color según `match_level`: strong (verde), good (azul), partial (amarillo), weak (rojo). Animación de entrada. Lista de `matched_skills` visible. Botón "Score more" para solicitar más scoring. Sort por score habilitado tras primer scoring. (Nota: botón eliminado en Fase 6.)

---

## EPIC-6: Job Detail Page (Fase 4)

### DET-001
- **Tipo:** Story
- **Título:** `job-detail.html` — página de detalle de oferta laboral
- **Componente:** `src/static/job-detail.html`
- **Descripción:** Página HTML de detalle de oferta. Header con nav (Back to jobs, ATS Evaluator), loading spinner, mensaje de error, contenedor `#job-detail` que popula el JS. Usa `style.css` y `jobs.css`.

### DET-002
- **Tipo:** Story
- **Título:** `job-detail.js` — carga job por ID, CTA contextual según sesión
- **Componente:** `src/static/job-detail.js`
- **Descripción:** Lee `?id=` de URL → `GET /jobs` → filtra por id → renderiza título, empresa, ubicación, tags, descripción completa, botón Apply. CTA: si hay `cv_session_token` en localStorage → "See how to improve your match →" (link a `index.html?job_id={id}`); si no → "Upload your CV to see your match score" (link a `index.html`). Todo dato por `escHtml()`. URLs externas por `safeUrl()`.
- **AC:**
  - Sin `?id=` → error "No job ID specified"
  - Job no encontrado → error "Job not found"
  - Sin conexión → "Could not connect to the server"
  - XSS imposible

### DET-003
- **Tipo:** Story
- **Título:** `POST /evaluate` extendido: `job_id` form field + job context injection
- **Componente:** `src/routes/evaluate.py`
- **Descripción:** Aceptar `job_id: Optional[str]` como campo de form. Si presente, buscar job en `jobs_cache["data"]` y construir `job_context = "Title: ...\nCompany: ...\n\n{description}"`. Pasar a `evaluate_cv(cv_text, job_context=job_context)`. Si `job_id` no está en caché, continuar sin contexto (no error).
- **AC:**
  - Con `job_id` válido en caché → evaluación contextualizada
  - Con `job_id` no encontrado → evaluación normal sin contexto
  - Sin `job_id` → comportamiento original

### DET-004
- **Tipo:** Story
- **Título:** `POST /evaluate` extendido: header `X-CV-Session-Token`
- **Componente:** `src/routes/evaluate.py`
- **Descripción:** Leer header `X-CV-Session-Token`. Lógica: si archivo tiene bytes → extraer texto del archivo (prioridad). Si archivo vacío + token válido → usar `cv_text` de la sesión. Si archivo vacío + sin token → 400. Prioridad: archivo > sesión.
- **AC:**
  - Archivo con contenido → extrae texto del archivo
  - Archivo vacío + token válido → usa CV de sesión
  - Archivo vacío + sin token → 400 "No CV provided"
  - Archivo vacío + token expirado → 400 "Session not found or expired"

### DET-005
- **Tipo:** Story
- **Título:** `app.js`: `loadJobContext()`, badge de job, enviar `job_id` y session token
- **Componente:** `src/static/app.js`
- **Descripción:** (1) `loadJobContext()`: lee `?job_id=` de URL → `GET /jobs` → muestra badge `#job-context-badge` "Evaluating for: {title} at {company}". (2) Al hacer submit, si hay `job_id` en URL → `formData.append('job_id', contextJobId)`. (3) Si hay `cv_session_token` en localStorage → agregar header `X-CV-Session-Token`.
- **AC:**
  - Badge solo visible si `?job_id=` existe y el job se encontró
  - `job_id` solo appendeado al FormData si está en la URL
  - Header de sesión no rompe si el backend no lo soporta

### DET-006
- **Tipo:** Task
- **Título:** `index.html`: nav link al Job Board + `#job-context-badge`
- **Componente:** `src/static/index.html`
- **Descripción:** (1) Agregar `<nav>` en header con link "← Job Board" a `jobs.html`. (2) Agregar `<div id="job-context-badge" class="hidden">` que `app.js` popula con el contexto del job.

---

## EPIC-7: Rate Limiting (Fase 5)

### RL-001
- **Tipo:** Story
- **Título:** Rate limiting en `POST /session` — 3/min por IP
- **Componente:** `src/routes/session.py`
- **Descripción:** Aplicar `@limiter.limit("3/minute")` a `POST /session` con `slowapi` usando `get_remote_address` como key function.
- **AC:**
  - 4ta request desde la misma IP en 1 minuto → 429

### RL-002
- **Tipo:** Story
- **Título:** Rate limiting en `POST /jobs/score` — 3/min por IP
- **Componente:** `src/routes/jobs.py`
- **Descripción:** Aplicar `@limiter.limit("3/minute")` a `POST /jobs/score`. Mismo patrón que RL-001.
- **AC:**
  - 4ta solicitud de scoring en 1 minuto → 429

### RL-003
- **Tipo:** Task
- **Título:** `docs/TESTING.md` — guía de testing manual
- **Componente:** `docs/`
- **Descripción:** Documentar escenarios de testing manual: upload CV, ranking, scoring, job detail, rate limits, sesión expirada, flujo evaluate con job_id.

---

## EPIC-8: Zvec — Vector DB Persistente (Fase 6)

### ZVC-001
- **Tipo:** Story
- **Título:** `get_jobs_collection()` — singleton lazy de colección Zvec
- **Componente:** `backend/ranker.py`
- **Descripción:** `get_jobs_collection() -> zvec.Collection`. Si `./zvec_jobs` existe → abre. Si no → crea con schema `CollectionSchema(name="jobs", vectors=VectorSchema("embedding", VECTOR_FP32, 384))`. Singleton con `_collection` a nivel de módulo.
- **AC:**
  - Segunda llamada devuelve la misma instancia
  - Si no existe el path, crea y abre correctamente
  - Si ya existe, abre sin recrear

### ZVC-002
- **Tipo:** Story
- **Título:** `upsert_job()` — embed + insert idempotente en Zvec
- **Componente:** `backend/ranker.py`
- **Descripción:** `upsert_job(job: Job) -> None`. Si `job.id` en `_inserted_ids` (set en memoria) → return. Sino: calcular embedding, `col.insert(Doc(id=job.id, vectors={"embedding": embedding}))`. Si `status.ok()` → log debug. Si no ok (ya en disco) → log debug "skipping". Siempre agregar a `_inserted_ids`.
- **AC:**
  - Segunda llamada mismo job no hace embed ni insert
  - Insert rechazado por Zvec no levanta excepción
  - Persiste en disco entre reinicios

### ZVC-003
- **Tipo:** Task
- **Título:** `fetch_jobs()` — upsert automático en Zvec al fetchear
- **Componente:** `backend/jobs.py`
- **Descripción:** En `fetch_jobs()`, tras mapear los jobs, iterar y llamar `upsert_job(job)` por cada uno. Import lazy (`from backend.ranker import upsert_job as _upsert_job`) para evitar circularidad. Upsert es best-effort: error individual loguea warning, no interrumpe el fetch.
- **AC:**
  - Si Zvec no disponible, `fetch_jobs` igual retorna los jobs
  - Límite elevado de 20 → 100 jobs

### ZVC-004
- **Tipo:** Story
- **Título:** `GET /jobs/ranked` refactorizado — usa `Zvec collection.query()`
- **Componente:** `src/routes/jobs.py`
- **Descripción:** Reemplazar ranking coseno en memoria por `collection.query(VectorQuery("embedding", vector=session.cv_embedding), topk=20)`. Jobs no indexados en Zvec se appendean al final con `similarity_score: null`. Guard si `cv_embedding` está vacío.
- **AC:**
  - Respuesta idéntica en forma a la versión anterior
  - Guard contra `cv_embedding` vacío

### ZVC-005
- **Tipo:** Task
- **Título:** `POST /jobs/score` refactorizado — usa Zvec para top-N
- **Componente:** `src/routes/jobs.py`
- **Descripción:** Reemplazar selección top-N en memoria por `collection.query(VectorQuery, topk=limit)`. Guard: si `session.cv_embedding` vacío → 400.

### ZVC-006
- **Tipo:** Task
- **Título:** Eliminar `Job.embedding`, subir límite a 100 jobs
- **Componente:** `backend/jobs.py`
- **Descripción:** El campo `Job.embedding` ya no es necesario (embedding vive en Zvec). Eliminarlo del modelo. Subir límite de Remotive de 20 a 100 en `REMOTIVE_PARAMS`.
- **AC:**
  - Sin referencias a `job.embedding` en el codebase
  - Remotive consultado con `limit=100`

### ZVC-007
- **Tipo:** Bug
- **Título:** Guard anti-crash: `cv_embedding` vacío en sesiones
- **Componente:** `src/routes/jobs.py`, `backend/sessions.py`
- **Descripción:** Si `store_session()` falla al calcular el embedding, `cv_embedding = []`. Las rutas que pasaban este vector a Zvec crasheaban. Agregar guard: si `cv_embedding` está vacío, usar fallback no-ranking.

---

## EPIC-9: Glassmorphism + UX Redesign (Fase 6)

### UX-001
- **Tipo:** Story
- **Título:** Reemplazar sticky `#cv-bar` con `#cv-banner` debajo del header
- **Componente:** `src/static/jobs.html`, `src/static/jobs.css`
- **Descripción:** Remover sticky `#cv-bar`. Reemplazar por `#cv-banner` en flujo normal del documento, debajo del `<header>` (scrollea con la página). Estilos glassmorphism: `background: rgba(255,255,255,0.03)`, `border-bottom`, `backdrop-filter: blur(8px)`.

### UX-002
- **Tipo:** Story
- **Título:** Rediseño glassmorphism completo de `jobs.css`
- **Componente:** `src/static/jobs.css`
- **Descripción:** Refactor completo al estilo glassmorphism: cards con `background: rgba(255,255,255,0.04)`, `border-radius: 12px`, `backdrop-filter: blur(...)`; botones pill `border-radius: 20px`; `.score-badge` pill con colores por match_level; `.btn-match` glass sin gradiente; `.cv-banner-btn` pill glass accent blue; similarity bars más gruesas y redondeadas; nav links pill con borde tenue.

### UX-003
- **Tipo:** Task
- **Título:** `style.css`: `.tag` border-radius 2px → 20px
- **Componente:** `src/static/style.css`
- **Descripción:** Actualizar `.tag` de `border-radius: 2px` a `border-radius: 20px` para consistencia con el sistema de diseño pill.

### UX-004
- **Tipo:** Bug
- **Título:** Fix: scores persisten al cambiar de sort via `applyScoresToCards()`
- **Componente:** `src/static/jobs.js`
- **Descripción:** Al cambiar el sort, `renderJobs()` re-renderizaba las cards sin badges de score. Implementar `applyScoresToCards()` que re-aplica badges, skills y summary sobre cards ya renderizadas. Llamarlo en `setSort()` después de `renderJobs()`.
- **AC:**
  - Cambiar sort con CV activo → badges siguen visibles

### UX-005
- **Tipo:** Task
- **Título:** `cvActive` param en `renderJobCard()` — CTA condicional
- **Componente:** `src/static/jobs.js`
- **Descripción:** Botón "See full analysis" (link a `job-detail.html`) debe aparecer solo cuando hay CV activo. Agregar `cvActive: boolean` a `renderJobCard()`. Si false, no renderizar el CTA.

### UX-006
- **Tipo:** Bug
- **Título:** Fix: sort habilitado inmediatamente al subir CV
- **Componente:** `src/static/jobs.js`
- **Descripción:** El sort por "Match score" estaba deshabilitado hasta que el scoring LLM completaba. Debe habilitarse inmediatamente al subir el CV (con el ranking por similitud disponible).

### UX-007
- **Tipo:** Story
- **Título:** Auto-switch a "Match score" sort cuando el scoring LLM completa
- **Componente:** `src/static/jobs.js`
- **Descripción:** Cuando `POST /jobs/score` retorna resultados, hacer auto-switch al sort "Match score" si el usuario no cambió el sort manualmente. Prioriza automáticamente los mejores matches.

### UX-008
- **Tipo:** Story
- **Título:** Scoring automático al subir CV, eliminar botón "Score more"
- **Componente:** `src/static/jobs.js`, `src/static/jobs.html`
- **Descripción:** Eliminar botón "Score more". El scoring de todos los ranked jobs se dispara automáticamente al subir el CV. Enviar el count de ranked jobs como `limit` al `POST /jobs/score`.
- **AC:**
  - Al subir CV → scoring se inicia automáticamente
  - Sin botón "Score more" en el UI

### UX-009
- **Tipo:** Task
- **Título:** Elevar límite de scoring cap de 12 a 30
- **Componente:** `src/routes/jobs.py`, `src/static/jobs.js`
- **Descripción:** Backend clampea `limit` a [1, 30]. Frontend envía el count exacto de ranked jobs hasta 30.

### UX-010
- **Tipo:** Story
- **Título:** Fallback badge de similitud para jobs rankeados sin score LLM
- **Componente:** `src/static/jobs.js`
- **Descripción:** Mientras el scoring LLM no completa, los jobs rankeados por Zvec muestran un badge de similitud (porcentaje o barra) como indicador visual de relevancia.

### UX-011
- **Tipo:** Story
- **Título:** Badge del mejor score en verde, resto en rojo
- **Componente:** `src/static/jobs.js`, `src/static/jobs.css`
- **Descripción:** Tras el scoring LLM, el job con mayor `score` tiene badge verde. Todos los demás tienen badge rojo, independientemente del `match_level`. Crea diferenciador visual inmediato del mejor match.

### UX-012
- **Tipo:** Task
- **Título:** Space Grotesk font para el header del job board
- **Componente:** `src/static/jobs.html`, `src/static/jobs.css`
- **Descripción:** Cargar Space Grotesk desde Google Fonts y aplicar al header (h1, subtítulo). Agregar `<link>` preconnect en `<head>`.

### UX-013
- **Tipo:** Bug
- **Título:** Fix: mayor visibilidad de glass cards — bg, borders, backdrop-filter
- **Componente:** `src/static/jobs.css`
- **Descripción:** Las cards glassmorphism resultaban muy transparentes. Aumentar `background` a valor más opaco, reforzar `border` con mayor opacidad, asegurar `backdrop-filter` con prefijos necesarios.

---

## EPIC-10: Testing

### TST-001
- **Tipo:** Task
- **Título:** `pyproject.toml` — agregar dependencias nuevas de prod y dev
- **Componente:** `pyproject.toml`
- **Descripción:** `dependencies`: agregar `httpx>=0.28.0`, `sentence-transformers>=3.0.0`, `zvec>=0.1.0`. `[dependency-groups].dev`: agregar `pytest>=8.0.0`, `pytest-asyncio>=0.24.0`, `respx>=0.21.0`. Configurar `[tool.pytest.ini_options]` con `asyncio_mode = "auto"`.

### TST-002
- **Tipo:** Task
- **Título:** `tests/conftest.py` + `tests/__init__.py`
- **Componente:** `tests/`
- **Descripción:** `tests/__init__.py` vacío para que pytest reconozca el directorio como package. `tests/conftest.py` con fixture `client` que instancia `TestClient(app)` del `src.main`.

### TST-003
- **Tipo:** Story
- **Título:** `test_jobs.py` — 13 tests: strip_html, Job model, fetch_jobs, GET /jobs
- **Componente:** `tests/test_jobs.py`
- **Descripción:** `strip_html`: con tags, vacío, None, nested (4 tests). `Job` model: instanciación válida, salary_range opcional (2 tests). `fetch_jobs()` con mocks respx: respuesta OK, HTTP error, malformada, caché (4 tests). `GET /jobs`: 200, 502 upstream, 500 internal (3 tests).

### TST-004
- **Tipo:** Story
- **Título:** `test_sessions.py` — store/get/delete/cleanup/TTL
- **Componente:** `tests/test_sessions.py`
- **Descripción:** `store_session()` retorna CVSession con token UUID. `get_session()` retorna sesión existente, None si no existe. TTL: sesión con uploaded_at >60 min → None. `delete_session()` True/False. `cleanup_sessions()` solo elimina expiradas.

### TST-005
- **Tipo:** Story
- **Título:** `test_ranker.py` — embed_text, cosine_similarity, get_jobs_collection, upsert_job
- **Componente:** `tests/test_ranker.py`
- **Descripción:** `embed_text()` → 384 dimensiones. `cosine_similarity()` vectores idénticos → 1.0, ortogonales → 0.0, zero → 0.0. `get_jobs_collection()` singleton (misma instancia). `upsert_job()` inserción exitosa + idempotencia.

### TST-006
- **Tipo:** Story
- **Título:** `test_scorer.py` — score_job con LLM mockeado
- **Componente:** `tests/test_scorer.py`
- **Descripción:** Mockear la llamada LangChain (sin requests reales a Claude). Cubrir: respuesta exitosa con `JobMatch` válido, score en [0,100], match_levels válidos, matched/missing_skills son listas, one_line_summary es string.

### TST-007
- **Tipo:** Story
- **Título:** `test_evaluate.py` — POST /evaluate con session CV y job_id
- **Componente:** `tests/test_evaluate.py`
- **Descripción:** Upload normal → evaluación estándar. `X-CV-Session-Token` con sesión válida + archivo vacío → usa CV de sesión. Token expirado → 400. `job_id` en form → inyección de contexto. Sin archivo y sin token → 400.

---

## EPIC-11: Documentación

### DOC-001
- **Tipo:** Task
- **Título:** README reescrito con scope completo del proyecto
- **Componente:** `README.md`
- **Descripción:** Reescribir README reflejando el scope actual: job board con CV scoring, todas las fases implementadas, stack tecnológico completo, referencia de API endpoints, instrucciones de setup y deploy.

### DOC-002
- **Tipo:** Task
- **Título:** `docs/estudio-completo.md` — guía de estudio comprensiva
- **Componente:** `docs/estudio-completo.md`
- **Descripción:** Documento que cubre todas las fases del proyecto, arquitectura, patrones utilizados, decisiones de diseño y flujos de datos. Sirve como referencia para onboarding.

### DOC-003
- **Tipo:** Task
- **Título:** `CLAUDE.md` actualizado con fases 1-6
- **Componente:** `CLAUDE.md`
- **Descripción:** Actualizar `CLAUDE.md` con estado completado de todas las fases (1-6), estructura de archivos actualizada, y detalle de qué se implementó en cada fase.
