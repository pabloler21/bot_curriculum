# CV Evaluator + Job Board — Estudio Completo del Proyecto

## 1. Visión General

**Qué es:** Una aplicación web que empezó como un evaluador de CVs (ATS Checker) y creció hasta convertirse en un job board inteligente con scoring personalizado por CV.

**Qué hace hoy:**
- Analiza tu CV con IA (Claude) y te da un score ATS con feedback
- Muestra ofertas de trabajo remotas en tech traídas de la API de Remotive
- Si subís tu CV, rankea los trabajos por similitud semántica al CV
- Scorea cada oferta contra tu CV con LLM: da un número 0–100, skills que matcheás, skills que faltan, y un resumen de una línea
- Página de detalle por oferta con análisis completo

---

## 2. Stack Tecnológico

### Backend
| Tecnología | Rol |
|---|---|
| **Python 3.13** | Runtime principal |
| **FastAPI** | Framework web, routing, serialización automática |
| **uvicorn** | ASGI server (desarrollo y producción) |
| **uv** | Package manager (reemplaza pip, más rápido) |
| **LangChain** | Abstracción sobre la API de Anthropic |
| **Claude Haiku 4.5** (`claude-haiku-4-5`) | Modelo LLM para scoring y evaluación ATS |
| **Pydantic** | Modelos de datos + structured output del LLM |
| **liteparse** | Extracción de texto de PDF y DOCX |
| **httpx** | HTTP cliente async para llamadas a Remotive API |
| **slowapi** | Rate limiting (3 req/min por IP) |
| **sentence-transformers** | Embeddings semánticos del CV y los jobs (`all-MiniLM-L6-v2`, 384 dimensiones) |
| **Zvec 0.3.0** | Vector database embebida (in-process) para búsqueda por similitud |

### Frontend
| Tecnología | Rol |
|---|---|
| **HTML/JS/CSS vanilla** | Sin frameworks, sin build steps |
| **Space Grotesk** | Tipografía del header (Google Fonts) |
| **Inter** | Tipografía del cuerpo (Google Fonts) |
| **Glassmorphism** | Estética visual (Steam colors + glass cards) |

### Testing y calidad
| Tecnología | Rol |
|---|---|
| **pytest** | Test runner |
| **pytest-asyncio** | Tests de código async |
| **respx** | Mock de llamadas HTTP (httpx) en tests |
| **ruff** | Linter Python |

### Deploy
- **Render.com** (configurado en `render.yaml`)
- Variable de entorno requerida: `ANTHROPIC_API_KEY`

---

## 3. Arquitectura del Sistema

```
Browser
  │
  ├── GET /              → index.html (ATS Evaluator)
  ├── GET /jobs.html     → jobs.html  (Job Board)
  ├── GET /jobs/{id}     → job-detail.html
  │
  └── API calls
        │
        ├── POST /evaluate          → Analiza CV (ATS score)
        ├── POST /session           → Crea sesión con CV
        ├── GET  /session/{token}   → Restaura sesión
        ├── DELETE /session/{token} → Elimina sesión
        ├── GET  /jobs              → Lista de jobs (sin ranking)
        ├── GET  /jobs/ranked       → Jobs rankeados por CV embedding
        └── POST /jobs/score        → Scorea jobs con LLM
```

### Flujo de datos al subir un CV

```
Usuario sube CV (PDF/DOCX)
        │
        ▼
POST /session
  1. liteparse extrae texto del archivo
  2. SentenceTransformer genera embedding del CV (384 dim)
  3. Se crea CVSession con {token, cv_text, cv_embedding, filename}
  4. Se guarda en dict en memoria con TTL 60 min
  5. Responde con {token, filename, char_count}
        │
        ▼ (frontend guarda token en localStorage)
        │
GET /jobs/ranked?token=...
  1. fetch_jobs() → Remotive API (caché 15 min)
  2. Para cada job nuevo: SentenceTransformer genera embedding + Zvec.insert()
  3. Zvec.query(cv_embedding, topk=20) → top 20 jobs más similares
  4. Responde jobs con similarity_score (0–1)
        │
        ▼ (frontend muestra cards con similarity bars)
        │
POST /jobs/score {token, limit: N}
  1. Zvec.query(cv_embedding, topk=N) → top N jobs
  2. asyncio.gather → N llamadas paralelas a Claude Haiku
  3. Claude devuelve JobMatch (score, matched_skills, missing_skills, one_line_summary)
  4. Se cachea en session.scored_jobs
  5. Responde lista de {job_id, score, matched_skills, ...}
```

---

## 4. Estructura de Archivos

```
bot-curriculum/
│
├── src/
│   ├── main.py              # FastAPI app: CORS, static files mount, rate limiter
│   ├── router.py            # Registra todos los routers
│   └── routes/
│       ├── evaluate.py      # POST /evaluate — ATS analysis
│       ├── health.py        # GET /health
│       ├── jobs.py          # GET /jobs, GET /jobs/ranked, POST /jobs/score
│       ├── session.py       # POST/GET/DELETE /session
│       └── view/public/     # Sirve job-detail.html como ruta estática
│
├── backend/
│   ├── evaluator.py         # LangChain chain → Claude, retorna ResumeEvaluation
│   ├── extractor.py         # extract_text(file) → str via liteparse
│   ├── jobs.py              # Job (Pydantic), strip_html(), fetch_jobs(), caché
│   ├── sessions.py          # CVSession, cv_sessions dict, CRUD + TTL cleanup
│   ├── ranker.py            # embed_text(), get_jobs_collection(), upsert_job()
│   ├── scorer.py            # JobMatch, score_job(cv_text, job) → LLM call
│   └── prompts/
│       └── ats_skill.md     # Prompt del ATS evaluator
│
├── src/static/
│   ├── index.html           # Página ATS Evaluator
│   ├── app.js               # Lógica del ATS evaluator
│   ├── style.css            # Estilos globales (CSS vars, header, layout)
│   ├── jobs.html            # Job Board
│   ├── jobs.css             # Estilos del job board (glassmorphism)
│   ├── jobs.js              # Lógica del job board
│   ├── job-detail.html      # Página de detalle de oferta
│   └── job-detail.js        # Lógica del detalle
│
├── tests/
│   ├── conftest.py          # TestClient fixture
│   ├── test_jobs.py         # 13 tests: strip_html, Job, fetch_jobs, GET /jobs
│   ├── test_sessions.py     # 10 tests: CVSession CRUD, TTL
│   ├── test_ranker.py       # Tests: embed_text, cosine_sim, Zvec operations
│   ├── test_scorer.py       # Tests: score_job (LLM mockeado con respx)
│   └── test_evaluate.py     # Tests: POST /evaluate con session token
│
├── docs/superpowers/
│   ├── specs/               # Design docs de cada fase
│   └── plans/               # Implementation plans
│
├── zvec_jobs/               # Índice vectorial persistente (en disco, ignorado por git)
├── render.yaml              # Config de deploy en Render.com
├── CLAUDE.md                # Instrucciones para el agente IA
└── pyproject.toml           # Dependencias Python
```

---

## 5. Modelos de Datos Clave

### Job (Pydantic)
```python
class Job(BaseModel):
    id: str
    title: str
    company: str
    location: str
    url: str
    description: str        # texto limpio (sin HTML)
    tags: list[str]
    salary_range: str | None
    employment_type: str
    posted_at: str          # "YYYY-MM-DD"
```

### CVSession (Pydantic)
```python
class CVSession(BaseModel):
    token: str              # UUID v4
    cv_text: str            # texto extraído del PDF/DOCX
    cv_embedding: list[float]  # 384 dimensiones (all-MiniLM-L6-v2)
    filename: str
    created_at: datetime
    scored_jobs: dict       # {job_id: JobMatch dict} — caché de scores
```

### JobMatch (Pydantic — structured output del LLM)
```python
class JobMatch(BaseModel):
    score: int              # 0–100
    match_level: str        # "strong" | "good" | "partial" | "weak"
    matched_skills: list[str]
    missing_skills: list[str]
    one_line_summary: str
```

### ResumeEvaluation (Pydantic — ATS evaluator)
```python
class ResumeEvaluation(BaseModel):
    candidate_name: str
    ats_score: int          # 0–100
    verdict: str
    summary: str
    keywords_found: list[str]
    keywords_missing: list[str]
    formatting_issues: list[str]
    recommendations: list[str]
```

---

## 6. Fases del Proyecto — Cronología

### Fase 0 — ATS Evaluator original
**Qué había:** Una página que acepta PDF/DOCX, lo analiza con Claude y da feedback ATS.

**Archivos originales:**
- `index.html` + `app.js` + `style.css` — Frontend
- `backend/evaluator.py` — Chain LangChain con structured output
- `backend/extractor.py` — Extracción de texto
- `POST /evaluate` — Endpoint principal

**Concepto clave:** LangChain structured output — le pasás un Pydantic model al LLM y devuelve JSON con la forma exacta que definiste, con validación automática.

---

### Fase 1 — Job Listings desde API pública
**Problema:** Mostrar ofertas de trabajo reales junto al evaluador de CVs.

**Decisiones técnicas:**
- API elegida: **Remotive** (gratuita, enfocada en remote tech jobs)
- Caché en memoria de 15 min para evitar llamar a Remotive en cada request
- `strip_html()` para limpiar las descripciones de HTML
- Parámetros: `category=software-dev, limit=100`

**Código clave:**
```python
# backend/jobs.py
_cache: dict = {"jobs": [], "fetched_at": None}

async def fetch_jobs() -> list[Job]:
    if _cache["fetched_at"] and time.time() - _cache["fetched_at"] < 900:
        return _cache["jobs"]
    # ... fetch from Remotive, parse, cache, return
```

**Frontend:** Grid de cards 1/2/3 columnas responsive. Keyboard navigation (Enter/Space abre el job). XSS prevention con `escHtml()` y `safeUrl()`.

---

### Fase 2 — Session Management + CV Upload
**Problema:** El CV del usuario necesita persistir en el servidor para compararlo contra cada oferta.

**Decisiones técnicas:**
- Token = UUID v4 generado en servidor
- CV text en memoria del servidor (no en localStorage, no en cloud)
- TTL 60 min con lazy cleanup (se limpian sesiones expiradas cuando se crea una nueva)
- Límite de 5 MB por archivo

**Código clave:**
```python
# backend/sessions.py
cv_sessions: dict[str, CVSession] = {}

def store_session(cv_text: str, cv_embedding: list[float], filename: str) -> CVSession:
    cleanup_sessions()  # lazy TTL cleanup
    token = str(uuid.uuid4())
    session = CVSession(token=token, cv_text=cv_text, ...)
    cv_sessions[token] = session
    return session
```

**Endpoints:**
- `POST /session` → valida archivo, extrae texto, genera embedding, crea sesión
- `GET /session/{token}` → devuelve metadata (sin el texto del CV)
- `DELETE /session/{token}` → elimina sesión

**Frontend:** CV chip (nombre + botón X) reemplaza el botón de upload. Token guardado en `localStorage` para sobrevivir refreshes.

---

### Fase 2.5 — Embedding-based Job Ranking
**Problema:** Mostrar primero los jobs más relevantes para el CV del usuario.

**Tecnología:** `sentence-transformers` con modelo `all-MiniLM-L6-v2`
- Modelo liviano (22M params), 384 dimensiones
- Corre en CPU sin GPU
- Cosine similarity para comparar vectores

**Flujo:**
1. Al subir CV → `embed_text(cv_text)` genera el vector del CV
2. Al pedir jobs rankeados → `embed_text(job.title + job.description)` por cada job
3. `cosine_similarity(cv_vec, job_vec)` para cada par
4. Sort descendente por similarity score

**Cosine similarity:**
```python
def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x**2 for x in a) ** 0.5
    norm_b = sum(x**2 for x in b) ** 0.5
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
```

**Frontend:** Similarity bars visuales por card, banner "Showing N jobs ranked by relevance to your CV", collapse de jobs con baja relevancia (<0.25).

---

### Fase 3 — LLM Scoring CV vs Jobs
**Problema:** El embedding ranking dice "qué tan parecidos son semánticamente" pero no "¿sos apto para este trabajo?" El LLM puede razonar sobre skills específicos.

**Diseño:**
- `score_job(cv_text, job)` → llama a Claude Haiku con el texto del CV y la descripción del job
- Devuelve `JobMatch` con structured output
- Múltiples jobs se scorean en paralelo con `asyncio.gather()`
- Resultados cacheados en `session.scored_jobs` (no volver a llamar si ya fue scoread)

**Prompt estrategia:** Claude recibe CV + job description y debe devolver:
- Score 0–100 (fit del candidato para el rol)
- Skills que matchean
- Skills que faltan
- Un resumen de una línea explicando el score

**Frontend:** Badges de score en los cards, matched skills highlighted, one-line summary debajo del título.

---

### Fase 4 — Job Detail Page + Integración con Evaluate
**Problema:** Querer ver el análisis completo de una oferta específica sin abandonar el contexto del CV.

**Nuevo endpoint:** `POST /evaluate` acepta header `X-CV-Session-Token` → usa el CV de la sesión en vez de pedir que lo suban de vuelta.

**Nueva página:** `job-detail.html` con URL `?id=<job_id>`
- Carga datos del job desde `/jobs`
- Si hay sesión activa → muestra JobMatch scoring
- Descripción completa del job renderizada
- Skills matched/missing con visual feedback

---

### Fase 5 — Rate Limiting + Polish
**Problema:** Proteger los endpoints costosos de abuso.

**Implementación con slowapi:**
```python
limiter = Limiter(key_func=get_remote_address)

@router.post("/jobs/score")
@limiter.limit("3/minute")
async def score_jobs(request: Request, body: ScoreRequest):
    ...
```

Rate limit en:
- `POST /session` — 3/min por IP
- `POST /jobs/score` — 3/min por IP

---

### Fase 6 — Zvec Persistent Vector DB
**Problema original:** En cada request se recalculaban todos los embeddings de jobs. Con 100 jobs y modelo de 22M params, esto era lento.

**Solución:** **Zvec** — una vector database embebida (in-process, archivos en disco) inspirada en SQLite.

**Conceptos clave de Zvec:**
```python
import zvec

# Abrir/crear colección
col = zvec.create_and_open("./zvec_jobs", schema)

# Insertar
status = col.insert([zvec.Doc(job_id, {"embedding": vector})])

# Buscar por similitud
results = col.query(
    vectors=zvec.VectorQuery("embedding", vector=cv_embedding),
    topk=20
)
# results[i].id = job_id
# results[i].score = cosine similarity
```

**Patrón Singleton:**
```python
_collection: zvec.Collection | None = None

def get_jobs_collection() -> zvec.Collection:
    global _collection
    if _collection is None:
        _collection = zvec.open("./zvec_jobs") or zvec.create_and_open(...)
    return _collection
```

**Idempotencia:** `upsert_job()` trackea IDs insertados en `_inserted_ids: set[str]`. Si el job ya fue insertado (el proceso no se reinició), no vuelve a llamar a Zvec.

**Beneficio:** Los embeddings de jobs persisten entre reinicios del servidor. Solo se recalculan para jobs nuevos.

**Cambio en `/jobs/score`:** Ya no hace cosine similarity manual — delega a Zvec para obtener el top-N más similar al CV.

---

### Fase 7 — UX + Glassmorphism
**Problema:** UX subóptima y estética desactualizada.

**Cambios UX:**
1. **CV Banner** — reemplaza el sticky cv-bar por un banner no-sticky entre el header y el main
2. **"See full analysis" condicional** — solo aparece si hay CV activo (`cvActive` param)
3. **Bug fix: scores desaparecen al cambiar sort** — `setSort()` reconstruía el DOM desde cero, descartando los badges. Fix: `applyScoresToCards()` helper que se llama después de cada `renderJobs()`
4. **Auto-switch a "Match score"** — después de que el LLM termina de scorear, cambia automáticamente el sort
5. **Sort habilitado inmediatamente** — al subir CV, "Match score" sort se habilita de inmediato usando `similarity_score * 100` como fallback hasta que lleguen los scores LLM
6. **Todos los jobs rankeados se scorean** — `limit: allJobs.filter(j => j.similarity_score != null).length` en vez de hardcoded 8

**Estética glassmorphism:**
```css
/* Card */
background: rgba(255, 255, 255, 0.07);
border: 1px solid rgba(255, 255, 255, 0.12);
border-top: 1px solid rgba(102, 192, 244, 0.35);
border-radius: 12px;
backdrop-filter: blur(8px);
box-shadow: 0 4px 24px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.08);

/* Badges/buttons → pill shape */
border-radius: 20px;

/* Score badge */
padding: 3px 10px;  /* pill, no fixed width/height */
```

**Sistema de badges de score:**
- `score-best` (verde claro) → el card con el score más alto
- `score-default` (rojo) → todos los demás
- Fallback: si el LLM no pudo scorear pero el job tiene `similarity_score`, se muestra `Math.round(similarity_score * 100)` con el mismo estilo rojo

---

## 7. Bugs Resueltos y Sus Causas

| Bug | Causa raíz | Fix |
|---|---|---|
| Scores desaparecen al cambiar sort | `renderJobs()` reconstruye DOM desde cero | `applyScoresToCards()` helper llamado después de cada render |
| Solo se scorean 8 jobs | `limit: 8` hardcoded en frontend | `limit: rankedJobs.length` |
| Solo 12 como máximo | Backend cap hardcoded `min(..., 12)` | Subir cap a 30 |
| Jobs fallidos cacheados para siempre como null | `session.scored_jobs[job.id] = None` | No cachear fallos |
| Cards sin badge si LLM falla | No había fallback visual | `applyScoresToCards()` pase 2: `similarity_score * 100` como fallback |
| Zvec file lock en tests | Zvec usa lock exclusivo, no tiene `close()` | `gc.collect()` antes de resetear `_collection = None` en tests |

---

## 8. Patrones Técnicos Importantes

### Structured Output con LangChain
```python
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate

llm = ChatAnthropic(model="claude-haiku-4-5")
structured_llm = llm.with_structured_output(JobMatch)

chain = prompt | structured_llm
result: JobMatch = await chain.ainvoke({"cv_text": ..., "job_desc": ...})
```

### Parallelismo async
```python
# Scorear N jobs en paralelo
results_list = await asyncio.gather(*[score_one(j) for j in top_jobs])
```

### Seguridad XSS en frontend vanilla
```js
function escHtml(s) {
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function safeUrl(u) {
    try {
        const parsed = new URL(u);
        return (parsed.protocol === 'https:' || parsed.protocol === 'http:') ? u : '#';
    } catch { return '#'; }
}
```

### Caché en memoria (Python module-level)
```python
# El dict vive en el proceso Python, compartido entre requests
_cache: dict = {"jobs": [], "fetched_at": None}
```

### Lazy TTL cleanup de sesiones
```python
def cleanup_sessions():
    """Llamado al crear nueva sesión — evita acumular sesiones expiradas."""
    now = datetime.now()
    expired = [t for t, s in cv_sessions.items() if (now - s.created_at).seconds > 3600]
    for t in expired:
        del cv_sessions[t]
```

---

## 9. Decisiones de Diseño y Trade-offs

| Decisión | Alternativa | Por qué se eligió esta |
|---|---|---|
| Sesiones en memoria del servidor | Redis, DB | Simplicidad. Nota: en prod con >100 users → migrar a Redis |
| Zvec en disco (in-process) | Qdrant, Pinecone, pgvector | Zero infra overhead, persiste entre reinicios, API simple |
| Claude Haiku para scoring | GPT-4, Claude Sonnet | Costo bajo, suficiente para structured output de scoring |
| all-MiniLM-L6-v2 para embeddings | text-embedding-ada-002 | Gratis, local, 384 dim es suficiente para ranking de relevancia |
| Vanilla JS sin framework | React, Vue | Zero build step, menos dependencias, suficiente para esta app |
| Remotive como fuente de jobs | LinkedIn API, Indeed | Gratuita, enfocada en remote tech, API simple |
| `limit=ranked_jobs.length` para scoring | Batch manual | Un solo request paralelo es más eficiente que múltiples requests |

---

## 10. Comandos de Desarrollo

```bash
# Setup
pip install -e .

# Correr servidor local
uvicorn src.main:app --reload
# → http://localhost:8000/jobs.html

# Tests
pytest tests/ -v
pytest tests/ -q   # resumen

# Lint
ruff check backend/jobs.py src/routes/jobs.py src/router.py tests/

# Variable de entorno requerida
export ANTHROPIC_API_KEY=sk-ant-...
```

## 11. Git Workflow

```
main (producción)
  └── develop (integración)
        └── feature/phase-N-descripcion (trabajo activo)
```

```bash
# Nueva feature
git checkout develop
git checkout -b feature/phase-N-descripcion
# ... implementar, commit, commit ...
git checkout develop
git merge feature/phase-N-descripcion
git branch -d feature/phase-N-descripcion
```

**Regla:** Nunca commitear directo en `main`. Nunca commitear directo en `develop`. Siempre feature branch.

---

## 12. Estado Actual (post Fase 7)

- **55 tests pasando**
- Jobs board funcional con glassmorphism
- Ranking por embedding + LLM scoring de todos los jobs rankeados
- Sort automático a "Match score" después de scoring
- Badge verde para mejor match, rojo para el resto
- Fallback badge con similarity score para jobs no scoreados por LLM
- Tipografía Space Grotesk en el header
