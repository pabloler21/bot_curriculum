# Jira Ticket Completion Plan — Fases 1 a 6

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Revisar la implementación real de cada feature (Fases 1–6), entenderla en profundidad, verificar que los tests pasan, y transicionar los tickets de Jira de "Ready for development" a "Done".

**Architecture:** Todo el código ya está implementado y mergeado en `develop`. Este plan NO escribe código nuevo: navega los archivos existentes para entender cada pieza, corre los tests como verificación, y cierra cada ticket en Jira via API.

**Tech Stack:** Python 3.13, FastAPI, LangChain + `claude-haiku-4-5`, Pydantic v2, Zvec (vector DB local), SentenceTransformer, slowapi, vanilla JS.

---

## Cómo cerrar un ticket en Jira

Para cada ticket, el comando de cierre es:

```python
import urllib.request, base64, json

TOKEN = "ATATT3xFfGF0yndBdQTjJYb57a4WkcKR7hpGg7mROZsLvfFaI5UoxfFvJBzB0yPL3nMmtDZRoPtGb033VYh5peL026CXG_PuYrsy7JMTOyfNvqbN9R2-z9E2swS-tBpo207HvzDFDHo3cojZoAbiuULZf68WTCfGw5Qs2BkT31dMQ2exjo-4oAA=04A2CFAB"
creds = base64.b64encode(f"lerner.pb@gmail.com:{TOKEN}".encode()).decode()

def get_transitions(issue_key):
    url = f"https://lernerpb.atlassian.net/rest/api/3/issue/{issue_key}/transitions"
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {creds}", "Accept": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())

def transition_to_done(issue_key, transition_id):
    url = f"https://lernerpb.atlassian.net/rest/api/3/issue/{issue_key}/transitions"
    body = json.dumps({"transition": {"id": transition_id}}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": f"Basic {creds}",
        "Content-Type": "application/json"
    }, method="POST")
    urllib.request.urlopen(req)
    print(f"{issue_key} → Done")
```

Primero explorar `get_transitions("KAN-15")` para encontrar el ID de la transición "Done", luego usarlo en todos los tickets.

---

## Tarea 0: Preparación — encontrar transition ID y crear tickets faltantes

**Files:**
- Ninguno — solo llamadas a Jira API

- [ ] **Step 1: Obtener el ID de la transición "Done"**

```python
import urllib.request, base64, json

TOKEN = "ATATT3xFfGF0yndBdQTjJYb57a4WkcKR7hpGg7mROZsLvfFaI5UoxfFvJBzB0yPL3nMmtDZRoPtGb033VYh5peL026CXG_PuYrsy7JMTOyfNvqbN9R2-z9E2swS-tBpo207HvzDFDHo3cojZoAbiuULZf68WTCfGw5Qs2BkT31dMQ2exjo-4oAA=04A2CFAB"
creds = base64.b64encode(f"lerner.pb@gmail.com:{TOKEN}".encode()).decode()

url = "https://lernerpb.atlassian.net/rest/api/3/issue/KAN-15/transitions"
req = urllib.request.Request(url, headers={"Authorization": f"Basic {creds}", "Accept": "application/json"})
data = json.loads(urllib.request.urlopen(req).read())
for t in data["transitions"]:
    print(t["id"], t["name"])
```

Anota el ID que corresponda a "Done" (probablemente "31" o similar).

- [ ] **Step 2: Crear ticket faltante — `src/routes/view/public/` (Fase 4)**

Hay una ruta estática en Fase 4 que sirve `job-detail.html` en `GET /jobs/{id}` que no tiene ticket. Crear en KAN como subtarea de KAN-7:

```python
url = "https://lernerpb.atlassian.net/rest/api/3/issue"
body = json.dumps({
    "fields": {
        "project": {"key": "KAN"},
        "summary": "Ruta estatica GET /jobs/{id} — sirve job-detail.html",
        "issuetype": {"name": "Tarea"},
        "parent": {"key": "KAN-7"},
        "description": {
            "type": "doc", "version": 1,
            "content": [{"type": "paragraph", "content": [
                {"type": "text", "text": "src/main.py monta StaticFiles desde src/static/ con html=True. job-detail.html se sirve automaticamente en /jobs/{id} por la convencion HTML mode de Starlette. No hay ruta FastAPI explicita para esto."}
            ]}]
        }
    }
}).encode()
req = urllib.request.Request(url, data=body, headers={
    "Authorization": f"Basic {creds}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}, method="POST")
resp = json.loads(urllib.request.urlopen(req).read())
print("Created:", resp["key"])
```

- [ ] **Step 3: Crear ticket faltante — `src/router.py` (registro de todos los routers)**

```python
body = json.dumps({
    "fields": {
        "project": {"key": "KAN"},
        "summary": "src/router.py — registro de routers evaluate, health, jobs, session",
        "issuetype": {"name": "Tarea"},
        "parent": {"key": "KAN-11"},
        "description": {
            "type": "doc", "version": 1,
            "content": [{"type": "paragraph", "content": [
                {"type": "text", "text": "APIRouter raiz que incluye los 4 sub-routers: evaluate, health, jobs, session. Incluido en src/main.py via app.include_router(router)."}
            ]}]
        }
    }
}).encode()
req = urllib.request.Request(url, data=body, headers={
    "Authorization": f"Basic {creds}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}, method="POST")
resp = json.loads(urllib.request.urlopen(req).read())
print("Created:", resp["key"])
```

---

## Tarea 1: Fase 1 Backend — Job listings desde Remotive

**Tickets a cerrar:** KAN-11 (epic), KAN-15, KAN-16, KAN-17, y el nuevo ticket de `src/router.py`

**Files a leer:**
- `backend/jobs.py` — modelo Job, strip_html, fetch_jobs, caché
- `src/routes/jobs.py` — endpoints GET /jobs y GET /jobs/ranked
- `src/router.py` — registro de routers
- `tests/test_jobs.py` — 13 tests de todo lo anterior

### Qué entender

- [ ] **Step 1: Leer `backend/jobs.py`**

Lee el archivo completo. Conceptos clave:
- `_HTMLStripper(HTMLParser)`: parser de stdlib que acumula texto en `_parts`. `strip_html()` lo usa para limpiar el HTML que viene de Remotive.
- `Job(BaseModel)`: Pydantic v2. `posted_at` es `date` (no `datetime`). `salary_range` es `Optional[str]` porque Remotive a veces no lo incluye.
- `_cache: dict = {"data": None}`: caché a nivel de módulo. El valor es una tupla `(list[Job], datetime)`. Se invalida si tiene más de 900 segundos (15 min).
- `fetch_jobs()`: async porque usa `httpx.AsyncClient`. Llama a `upsert_job()` de `backend/ranker.py` para indexar en Zvec (lazy import para evitar circular imports).

- [ ] **Step 2: Leer `src/routes/jobs.py` — solo `GET /jobs` (líneas 95–119)**

- El endpoint llama `fetch_jobs()` y serializa con `model_dump(mode="json")` (necesario para que `date` se serialice como string ISO).
- Usa `JSONResponse` (no `HTTPException`) para poder incluir `{"detail": "...", "code": "..."}` en los errores — `HTTPException` no permite el campo `code`.

- [ ] **Step 3: Leer `src/router.py`**

Router raíz que agrega los 4 sub-routers. `src/main.py` hace `app.include_router(router)` antes de montar los archivos estáticos.

- [ ] **Step 4: Correr los tests de Fase 1**

```bash
pytest tests/test_jobs.py -v
```

Expected: 13 tests, todos PASS. Si alguno falla, leer el mensaje de error — probablemente sea un problema con el mock de `upsert_job`.

- [ ] **Step 5: Cerrar tickets KAN-15, KAN-16, KAN-17**

```python
DONE_TRANSITION_ID = "31"  # reemplazar con el ID real del Step 0
for key in ["KAN-15", "KAN-16", "KAN-17"]:
    url = f"https://lernerpb.atlassian.net/rest/api/3/issue/{key}/transitions"
    body = json.dumps({"transition": {"id": DONE_TRANSITION_ID}}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": f"Basic {creds}", "Content-Type": "application/json"
    }, method="POST")
    urllib.request.urlopen(req)
    print(f"{key} → Done")
```

- [ ] **Step 6: Cerrar el ticket nuevo de `src/router.py` (el key que devolvió Step 3 de Tarea 0)**

Mismo comando con el key nuevo.

---

## Tarea 2: Fase 1 Frontend — jobs.html, jobs.css, jobs.js

**Tickets a cerrar:** KAN-12 (epic), KAN-18, KAN-19, KAN-20, KAN-21

**Files a leer:**
- `src/static/jobs.html` — estructura HTML del job board
- `src/static/jobs.css` — estilos glassmorphism (post Fase 6)
- `src/static/jobs.js` — lógica fetch, render, sort, keyboard nav

### Qué entender

- [ ] **Step 1: Leer `src/static/jobs.html`**

Estructura principal:
- `<header>` con nav links al job board y al evaluador
- `#cv-banner`: barra de upload de CV (Fase 2+), posicionada debajo del header, scrollea con la página (no sticky)
- `#jobs-toolbar`: sort buttons (Date / Match score)
- `#jobs-grid`: grid donde se renderizan las cards
- `#loading` / `#error-state` / `#empty-state`: estados de carga

- [ ] **Step 2: Leer `src/static/jobs.js` — funciones `loadJobs()` y `renderJobCard()`**

Busca estas funciones. Conceptos clave:
- `escHtml(str)`: sanitización XSS — todo dato de la API pasa por esta función antes de insertarse en el DOM. Nunca `innerHTML = data.title` directo.
- `safeUrl(str)`: valida que la URL empiece con `http://` o `https://` antes de usarla en `href`.
- `renderJobCard(job, cvActive)`: `cvActive` controla si aparece el botón "See full analysis" (solo cuando hay CV subido).
- `applyScoresToCards()`: re-aplica badges/skills/summary a las cards ya renderizadas. Se llama después de cada `renderJobs()` para que los scores persistan al cambiar de sort.

- [ ] **Step 3: Entender keyboard navigation**

Las cards tienen `tabindex="0"` y listeners de `keydown` para `Enter`/`Space`. Esto permite navegar con Tab y abrir jobs con teclado.

- [ ] **Step 4: Verificar manualmente en el browser**

```bash
uvicorn src.main:app --reload
```

Abrir `http://localhost:8000/jobs.html`. Verificar que:
- Las cards cargan con datos reales de Remotive
- El sort por fecha funciona
- La keyboard nav funciona (Tab entre cards, Enter abre el job)

- [ ] **Step 5: Cerrar tickets**

```python
for key in ["KAN-18", "KAN-19", "KAN-20", "KAN-21", "KAN-12"]:
    # mismo comando de transición que en Tarea 1
```

---

## Tarea 3: Fase 2 — Session Management

**Tickets a cerrar:** KAN-4 (epic), KAN-22, KAN-23, KAN-24, KAN-25

**Files a leer:**
- `backend/sessions.py` — CVSession model, cv_sessions dict, CRUD + cleanup
- `src/routes/session.py` — POST /session, GET/DELETE /session/{token}
- `tests/test_sessions.py` — 13 tests

### Qué entender

- [ ] **Step 1: Leer `backend/sessions.py`**

- `CVSession(BaseModel)`: tiene `token`, `cv_text`, `cv_embedding: list[float] = []`, `filename`, `uploaded_at`, `scored_jobs: dict`.
- `cv_sessions: dict[str, CVSession]`: store en memoria a nivel de módulo. En producción con >100 usuarios habría que migrar a Redis, pero para este proyecto alcanza.
- `store_session()`: genera UUID, crea la sesión, llama `cleanup_sessions()` (lazy cleanup al crear), luego intenta computar el embedding. Si el embedding falla, loguea warning y continúa — la sesión existe aunque sin embedding.
- `get_session()`: verifica TTL de 60 min. Si expiró, borra la sesión y devuelve `None`.

- [ ] **Step 2: Leer `src/routes/session.py`**

- `POST /session`: valida que el archivo no esté vacío (`file_bytes` falsy) y no supere 5 MB. Extrae texto con `liteparse` via `extract_text()`. Rate limit: 3/min por IP con `slowapi`.
- `GET /session/{token}`: primero valida formato UUID con `uuid.UUID(token)`. Si no es UUID válido → 400 con `code: invalid_token`. Si no existe o expiró → 404.
- `DELETE /session/{token}`: misma validación UUID. Si no existe → 404 con `code: session_not_found`. Si existe → 204 No Content.

- [ ] **Step 3: Correr los tests**

```bash
pytest tests/test_sessions.py -v
```

Expected: todos PASS. Los tests usan `patch("src.routes.session.extract_text", ...)` para no necesitar un PDF real.

- [ ] **Step 4: Entender el frontend — CV bar en `jobs.js`**

Busca en `jobs.js` la función relacionada al upload de CV. Cosas clave:
- El token se guarda en `localStorage["cv_session_token"]`
- Al cargar la página, si ya hay token guardado, se verifica con `GET /session/{token}` que siga activo
- El chip con el nombre del archivo + botón X permite remover la sesión (`DELETE /session/{token}` + limpiar localStorage)

- [ ] **Step 5: Cerrar tickets**

```python
for key in ["KAN-22", "KAN-23", "KAN-24", "KAN-25", "KAN-4"]:
    # transición a Done
```

---

## Tarea 4: Fase 2.5 — Embedding-Based Job Ranking

**Tickets a cerrar:** KAN-5 (epic), KAN-26, KAN-27, KAN-28, KAN-29

**Files a leer:**
- `backend/ranker.py` — embed_text, cosine_similarity, get_jobs_collection, upsert_job
- `src/routes/jobs.py` líneas 24–92 — GET /jobs/ranked con Zvec
- `tests/test_ranker.py` — tests de embeddings y Zvec

### Qué entender

- [ ] **Step 1: Leer `backend/ranker.py`**

Conceptos clave:
- `_model: SentenceTransformer | None = None`: singleton lazy — el modelo (~90 MB) se carga solo cuando se llama por primera vez. Esto evita cargar el modelo en import time.
- `embed_text(text)`: llama `model.encode()` y convierte a `list[float]`. El modelo `all-MiniLM-L6-v2` produce vectores de 384 dimensiones.
- `cosine_similarity(a, b)`: producto punto dividido por el producto de las normas. Devuelve 1.0 si los vectores son idénticos, 0.0 si son ortogonales.
- `get_jobs_collection()`: singleton lazy para la colección Zvec en `./zvec_jobs`. Si el directorio existe, abre la colección existente (persistencia entre reinicios). Si no, la crea con schema `VectorSchema("embedding", VECTOR_FP32, 384)`.
- `upsert_job(job)`: embed `job.description` y hace `col.insert()`. Idempotente: si ya está en `_inserted_ids` (in-memory set), lo skipea. Si Zvec rechaza el insert (ya existe on-disk), loguea debug y continúa.

- [ ] **Step 2: Leer `src/routes/jobs.py` líneas 24–92 — GET /jobs/ranked**

El endpoint:
1. Valida que `token` sea UUID válido
2. Llama `fetch_jobs()` (trae jobs y los upsterta en Zvec si son nuevos)
3. Si hay sesión con `cv_embedding`: usa `col.query(VectorQuery("embedding", vector=...), topk=20)` para rankear
4. Agrega `similarity_score` a cada job (redondeado a 2 decimales)
5. Jobs no rankeados por Zvec se agregan al final con `similarity_score: null`
6. Fallback graceful si no hay sesión o embedding

- [ ] **Step 3: Correr los tests**

```bash
pytest tests/test_ranker.py -v
```

- [ ] **Step 4: Entender similarity bars en el frontend**

En `jobs.js`, busca donde se usa `similarity_score`. Las barras visuales se calculan como porcentaje de 0 a 1 (el score de Zvec). Jobs sin score muestran la barra vacía o el fallback badge.

- [ ] **Step 5: Cerrar tickets**

```python
for key in ["KAN-26", "KAN-27", "KAN-28", "KAN-29", "KAN-5"]:
    # transición a Done
```

---

## Tarea 5: Fase 3 — LLM Scoring CV vs Jobs

**Tickets a cerrar:** KAN-6 (epic), KAN-30, KAN-31, KAN-32

**Files a leer:**
- `backend/scorer.py` — JobMatch model, score_job() chain
- `src/routes/jobs.py` líneas 122–209 — POST /jobs/score
- `tests/test_scorer.py` — tests con LLM mockeado

### Qué entender

- [ ] **Step 1: Leer `backend/scorer.py`**

- `JobMatch(BaseModel)`: contrato de respuesta — `score` (0–100), `match_level` (Literal["strong","good","partial","weak"]), `matched_skills`, `missing_skills`, `one_line_summary`.
- `_model = ChatAnthropic(model="claude-haiku-4-5")`: instancia del modelo.
- `_structured_model = _model.with_structured_output(JobMatch)`: LangChain structured output — le dice a Claude que devuelva JSON que matchee el schema de `JobMatch`. Internamente usa tool calling.
- `chain = _prompt | _structured_model`: pipe de LangChain. `chain.ainvoke(...)` es async.
- `score_job(cv_text, job)`: llama `chain.ainvoke()` con el CV y la descripción del job. Devuelve `JobMatch`.

- [ ] **Step 2: Leer `src/routes/jobs.py` líneas 122–209 — POST /jobs/score**

El endpoint:
1. Valida UUID del token
2. Clampa `limit` entre 1 y 30 (`min(max(body.limit, 1), 30)`)
3. Verifica que la sesión exista y tenga `cv_embedding` (sino 400)
4. Usa Zvec `col.query(topk=limit)` para seleccionar los top-N jobs
5. `score_one(job)`: primero verifica cache en `session.scored_jobs[job.id]`. Si ya está cacheado, lo devuelve sin llamar al LLM. Si falla el scoring, retorna `None` (no cachea fallos para permitir retry).
6. `asyncio.gather(*[score_one(j) for j in top_jobs])`: ejecuta el scoring en paralelo para todos los jobs.

- [ ] **Step 3: Correr los tests**

```bash
pytest tests/test_scorer.py -v
```

Los tests mockean el LLM con `patch`. Busca en el archivo cómo se mockea `chain.ainvoke` para devolver un `JobMatch` sin llamar a la API real.

- [ ] **Step 4: Entender los score badges en el frontend**

En `jobs.js`, busca `match_level`. Los badges mapean así:
- `strong` → verde oscuro
- `good` → azul
- `partial` → naranja
- `weak` → rojo

El mejor score del lote se muestra en verde, todos los demás en rojo (Fase 6 fix).

- [ ] **Step 5: Cerrar tickets**

```python
for key in ["KAN-30", "KAN-31", "KAN-32", "KAN-6"]:
    # transición a Done
```

---

## Tarea 6: Fase 4 — Job Detail Page + Integración con /evaluate

**Tickets a cerrar:** KAN-7 (epic), KAN-33, KAN-34, KAN-35, KAN-36, KAN-37, KAN-38, y el nuevo ticket de ruta estática

**Files a leer:**
- `src/static/job-detail.html` — estructura de la página de detalle
- `src/static/job-detail.js` — carga job por ID, scoring CTA, rendering
- `src/routes/evaluate.py` — POST /evaluate extendido
- `backend/evaluator.py` — evaluate_cv() con job_context opcional
- `src/static/app.js` — loadJobContext(), badge de job
- `tests/test_evaluate.py` — tests del endpoint extendido

### Qué entender

- [ ] **Step 1: Leer `src/static/job-detail.html`**

La URL tiene el formato `/job-detail.html?id=<job_id>`. Starlette sirve este archivo en modo HTML (cuando pide `/jobs/<id>`, el browser no lo encuentra y sirve el fallback HTML). El JS lee `?id=` de `location.search`.

- [ ] **Step 2: Leer `src/static/job-detail.js`**

Flujo:
1. Lee `job_id` de `URLSearchParams`
2. Llama `GET /jobs` (endpoint que ya existe), filtra el job por `id`
3. Renderiza título, empresa, descripción completa, tags
4. Si hay token en localStorage: muestra el scoring LLM del job (llama `POST /jobs/score` con `{token, job_ids: [job_id], limit: 1}`) o CTA para subir CV

- [ ] **Step 3: Leer `src/routes/evaluate.py`**

Extensiones de Fase 4:
- Acepta header `X-CV-Session-Token`: si el `file` está vacío y hay token, usa el CV de la sesión en lugar de un archivo subido.
- Acepta campo de formulario `job_id`: busca el job en `_cache["data"]` (el caché de `backend/jobs.py`) y construye `job_context` como string `"Title: ...\nCompany: ...\n\n{description}"`.
- Llama `evaluate_cv(cv_text, job_context=job_context)` — el `job_context` se inyecta en el prompt ATS.

- [ ] **Step 4: Correr los tests**

```bash
pytest tests/test_evaluate.py -v
```

- [ ] **Step 5: Cerrar tickets**

```python
for key in ["KAN-33", "KAN-34", "KAN-35", "KAN-36", "KAN-37", "KAN-38", "KAN-7"]:
    # transición a Done
# También cerrar el ticket nuevo de ruta estática
```

---

## Tarea 7: Fase 5 — Rate Limiting

**Tickets a cerrar:** KAN-8 (epic), KAN-39, KAN-40, KAN-41

**Files a leer:**
- `src/routes/session.py` líneas 14, 22–23 — rate limit en POST /session
- `src/routes/jobs.py` líneas 20, 128–129 — rate limit en POST /jobs/score
- `src/main.py` líneas 21–27 — configuración global de slowapi
- `docs/TESTING.md` — guía de testing manual

### Qué entender

- [ ] **Step 1: Entender cómo funciona slowapi**

slowapi es un wrapper de `limits` para FastAPI. Requiere:
1. `app.state.limiter = Limiter(key_func=get_remote_address)` en `main.py`
2. `app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)` para manejar el error
3. Cada router crea su propio `Limiter` local solo para el decorador `@limiter.limit()` — el rate limiting real usa el limiter global de `app.state`.
4. El decorador `@limiter.limit("3/minute")` en cada endpoint activa el límite.

- [ ] **Step 2: Leer `src/main.py` líneas 21–27**

Observar la configuración: `Limiter(key_func=get_remote_address)` usa la IP del cliente como clave. En producción detrás de un proxy, habría que configurar `X-Forwarded-For`.

- [ ] **Step 3: Leer `docs/TESTING.md`**

Contiene escenarios de prueba manual: qué hacer para verificar que el rate limiting funciona, qué respuesta esperar al exceder el límite (HTTP 429).

- [ ] **Step 4: Cerrar tickets**

```python
for key in ["KAN-39", "KAN-40", "KAN-41", "KAN-8"]:
    # transición a Done
```

---

## Tarea 8: Fase 6 — Zvec Vector DB Persistente

**Tickets a cerrar:** KAN-13 (epic), KAN-42, KAN-43, KAN-44, KAN-45, KAN-46, KAN-47, KAN-48

**Files a leer:**
- `backend/ranker.py` — ya leído en Tarea 4, re-focalizar en Zvec specifics
- `backend/jobs.py` líneas 93–107 — upsert automático en fetch_jobs()
- `src/routes/jobs.py` — ambos endpoints usando Zvec

### Qué entender

- [ ] **Step 1: Entender la arquitectura Zvec**

Zvec es una base de datos vectorial local (embedded, sin servidor). Guarda los datos en `./zvec_jobs/` (directorio en el filesystem). El schema define:
- `name="jobs"`: nombre de la colección
- `vectors=VectorSchema("embedding", DataType.VECTOR_FP32, 384)`: vectores de 384 dimensiones en float32

Cada `Doc` tiene `id` (string) y `vectors={"embedding": [...384 floats...]}`.

- [ ] **Step 2: Entender idempotencia en `upsert_job()`**

El problema: entre reinicios del servidor, `_inserted_ids` (set en memoria) se resetea, pero los datos siguen en Zvec on-disk. Entonces si se llama `col.insert()` con un id que ya existe, Zvec devuelve un status no-ok.

La solución: siempre agregar a `_inserted_ids` (para evitar el intento en la misma sesión), y cuando el insert falla, loguear debug y continuar sin crashear.

- [ ] **Step 3: Entender `GET /jobs/ranked` con Zvec (líneas 60–84 de `src/routes/jobs.py`)**

`col.query(VectorQuery("embedding", vector=cv_embedding), topk=20)` devuelve los 20 jobs más similares al CV. Los resultados tienen `.id` y `.score` (similitud coseno).

Luego se hace un join manual: `jobs_by_id = {job.id: job for job in jobs}` para enriquecer cada resultado Zvec con los datos completos del job.

- [ ] **Step 4: Eliminar `Job.embedding` — entender por qué**

En Fases 2.5 el campo `cv_embedding` vivía en `CVSession`. Los embeddings de los jobs vivían en `Job.embedding`. En Fase 6 se mueve el embedding de los jobs a Zvec, y se elimina `Job.embedding` del modelo Pydantic. Ahora `Job` no tiene embeddings — solo Zvec los tiene. Esto permite escalar a 100 jobs sin cargar todos los vectores en memoria.

- [ ] **Step 5: Correr todos los tests de ranker**

```bash
pytest tests/test_ranker.py -v
```

- [ ] **Step 6: Cerrar tickets**

```python
for key in ["KAN-42", "KAN-43", "KAN-44", "KAN-45", "KAN-46", "KAN-47", "KAN-48", "KAN-13"]:
    # transición a Done
```

---

## Tarea 9: Fase 6 — Glassmorphism + UX Redesign

**Tickets a cerrar:** KAN-9 (epic), KAN-49 a KAN-61

**Files a leer:**
- `src/static/jobs.css` — estilos glassmorphism completos
- `src/static/jobs.js` — fixes de UX (applyScoresToCards, cvActive, auto-sort, etc.)
- `src/static/style.css` — `.tag` border-radius

### Qué entender

- [ ] **Step 1: Leer `src/static/jobs.css` — secciones clave**

Busca y entiende estos bloques:
- `.job-card`: `background: rgba(255,255,255,0.04)`, `backdrop-filter: blur(12px)`, `border-radius: 12px` — glassmorphism base
- `.score-badge`: pill shape (`border-radius: 20px`), colores por match_level
- `.score-badge.best`: verde (mejor score del lote)
- `.score-badge:not(.best)`: rojo
- `.cv-banner`: posicionado debajo del header, `position: relative` (no fixed), scrollea con la página

- [ ] **Step 2: Leer `src/static/jobs.js` — fixes de UX**

Busca y entiende estas funciones/fixes:
- `applyScoresToCards()`: itera `scoredJobs` (dict job_id → JobMatch) y actualiza el DOM de cada card ya renderizada. Se llama en `setSort()` después de `renderJobs()` para que los scores no desaparezcan al cambiar sort.
- `renderJobCard(job, cvActive)`: el `cvActive` booleano controla si el botón "See full analysis" aparece. Sin CV subido, no tiene sentido mostrar ese CTA.
- Auto-switch sort: cuando el scoring LLM completa, se llama `setSort("score")` automáticamente para que el usuario vea los resultados rankeados por match sin tener que hacer click.
- Scoring automático: al subir CV, se llama inmediatamente a `POST /jobs/score` con `limit: 30`. Se elimina el botón "Score more" que existía en Fase 3.
- Fallback badge: jobs rankeados por Zvec pero sin score LLM muestran un badge de similitud (azul), no el badge de match_level.

- [ ] **Step 3: Verificar Space Grotesk font**

En `jobs.html`, busca el `<link>` a Google Fonts para Space Grotesk. Solo se usa en el `<header>` del job board.

- [ ] **Step 4: Verificar en el browser**

```bash
uvicorn src.main:app --reload
```

Subir un CV en `/jobs.html`. Verificar:
- Las cards tienen el estilo glass (fondo semi-transparente, blur)
- Los badges son pills redondeados
- Al subir CV, el sort se habilita y el scoring empieza automáticamente
- Cuando el scoring termina, se auto-switcha a "Match score"
- El mejor score está en verde, los demás en rojo

- [ ] **Step 5: Cerrar tickets KAN-49 a KAN-61**

```python
for key in [f"KAN-{n}" for n in range(49, 62)] + ["KAN-9"]:
    # transición a Done
```

---

## Tarea 10: Testing — pyproject.toml + tests

**Tickets a cerrar:** KAN-10 (epic), KAN-62 a KAN-68

**Files a leer:**
- `pyproject.toml` — dependencias de prod y dev
- `tests/conftest.py` — fixture `client`
- `tests/test_jobs.py`, `test_sessions.py`, `test_ranker.py`, `test_scorer.py`, `test_evaluate.py`

### Qué entender

- [ ] **Step 1: Leer `pyproject.toml`**

Verifica que estén presentes:
- Prod: `httpx`, `slowapi`, `langchain`, `langchain-anthropic`, `liteparse`, `zvec`, `sentence-transformers`
- Dev: `pytest`, `pytest-asyncio`, `respx`

- [ ] **Step 2: Leer `tests/conftest.py`**

La fixture `client` crea un `TestClient(app)` de FastAPI/Starlette. Starlette TestClient usa `requests` internamente y maneja el ciclo de vida de FastAPI. Los tests que usan `client` tienen acceso a todos los endpoints.

- [ ] **Step 3: Correr todos los tests**

```bash
pytest tests/ -v
```

Expected: todos PASS. Si alguno falla, leer el traceback. Los tests que usan `respx` mockean las llamadas HTTP externas (Remotive API). Los tests que usan LLM mockean `chain.ainvoke`.

- [ ] **Step 4: Entender patrones de testing usados**

- `@respx.mock` + `respx.get(url).mock(return_value=httpx.Response(...))`: mock de llamadas HTTP externas
- `with patch("module.function", ...)`: mock de dependencias internas
- `AsyncMock(return_value=...)`: mock de funciones async
- `setup_function()`: reset de estado global antes de cada test (limpia `cv_sessions` y los limiters)

- [ ] **Step 5: Cerrar tickets**

```python
for key in [f"KAN-{n}" for n in range(62, 69)] + ["KAN-10"]:
    # transición a Done
```

---

## Tarea 11: Documentación

**Tickets a cerrar:** KAN-14 (epic), KAN-69, KAN-70, KAN-71

**Files a leer:**
- `README.md` — scope completo del proyecto
- `docs/estudio-completo.md` — guía de estudio comprensiva de todas las fases
- `CLAUDE.md` — instrucciones del proyecto para Claude Code

### Qué entender

- [ ] **Step 1: Leer `README.md`**

Debe cubrir: qué es el proyecto, cómo correrlo localmente, endpoints disponibles, variables de entorno necesarias.

- [ ] **Step 2: Leer `docs/estudio-completo.md`**

Guía de estudio que cubre todas las fases, arquitectura, patrones usados. Útil para onboarding de nuevos devs.

- [ ] **Step 3: Verificar que `CLAUDE.md` esté actualizado**

Debe tener la tabla de estado de fases con todas las fases marcadas como ✅ Completa y la estructura de archivos post-Fase 6.

- [ ] **Step 4: Cerrar tickets**

```python
for key in ["KAN-69", "KAN-70", "KAN-71", "KAN-14"]:
    # transición a Done
```

---

## Tarea 12: Cierre final — run completo de tests + epics restantes

**Tickets a cerrar:** Ningún epic restante abierto

- [ ] **Step 1: Correr todos los tests una vez más para confirmar estado final**

```bash
pytest tests/ -v --tb=short
```

Expected: todos PASS.

- [ ] **Step 2: Verificar que todos los tickets de historia/tarea/error estén Done**

```python
import urllib.request, base64, json, urllib.parse

TOKEN = "ATATT3xFfGF0yndBdQTjJYb57a4WkcKR7hpGg7mROZsLvfFaI5UoxfFvJBzB0yPL3nMmtDZRoPtGb033VYh5peL026CXG_PuYrsy7JMTOyfNvqbN9R2-z9E2swS-tBpo207HvzDFDHo3cojZoAbiuULZf68WTCfGw5Qs2BkT31dMQ2exjo-4oAA=04A2CFAB"
creds = base64.b64encode(f"lerner.pb@gmail.com:{TOKEN}".encode()).decode()

params = urllib.parse.urlencode({"jql": "project = KAN AND status != Done ORDER BY key ASC", "maxResults": 100, "fields": "summary,status"})
url = f"https://lernerpb.atlassian.net/rest/api/3/search/jql?{params}"
req = urllib.request.Request(url, headers={"Authorization": f"Basic {creds}", "Accept": "application/json"})
data = json.loads(urllib.request.urlopen(req).read())
remaining = data.get("issues", [])
if not remaining:
    print("✅ Todos los tickets están Done")
else:
    print(f"⚠️  {len(remaining)} tickets pendientes:")
    for i in remaining:
        print(f"  {i['key']}: {i['fields']['summary']}")
```

- [ ] **Step 3: Cierre del proyecto en git**

```bash
git log --oneline develop | head -10
```

Verificar que los últimos commits corresponden al trabajo de Fase 6.

---

## Orden de ejecución recomendado

| Prioridad | Tarea | Tickets |
|-----------|-------|---------|
| 1 | Tarea 0 — Preparación + crear tickets faltantes | — |
| 2 | Tarea 1 — Fase 1 Backend | KAN-11, 15, 16, 17 |
| 3 | Tarea 2 — Fase 1 Frontend | KAN-12, 18, 19, 20, 21 |
| 4 | Tarea 3 — Fase 2 Sessions | KAN-4, 22, 23, 24, 25 |
| 5 | Tarea 4 — Fase 2.5 Embeddings | KAN-5, 26, 27, 28, 29 |
| 6 | Tarea 5 — Fase 3 LLM Scoring | KAN-6, 30, 31, 32 |
| 7 | Tarea 6 — Fase 4 Job Detail | KAN-7, 33–38 |
| 8 | Tarea 7 — Fase 5 Rate Limiting | KAN-8, 39, 40, 41 |
| 9 | Tarea 8 — Fase 6 Zvec | KAN-13, 42–48 |
| 10 | Tarea 9 — Fase 6 Glassmorphism | KAN-9, 49–61 |
| 11 | Tarea 10 — Testing | KAN-10, 62–68 |
| 12 | Tarea 11 — Documentación | KAN-14, 69–71 |
| 13 | Tarea 12 — Verificación final | todos |
