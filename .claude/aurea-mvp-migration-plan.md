# Aurea MVP — Features y Plan de Migración desde bot_curriculum

> **Fuente de verdad:** `aurea-product-strategy-v2.md` define el roadmap y las decisiones estratégicas. Este documento las traduce a tareas concretas de implementación sobre el código existente en `pabloler21/bot_curriculum`.

---

## Parte 1 — Features del MVP

El MVP se compone de Fase 1a (pipeline funcional sin pagos) y Fase 1b (sistema de pagos y auth). Acá se describe cada feature, qué problema resuelve, y cómo se diferencia de lo que existe hoy.

---

### Feature 1: Pipeline anti-alucinación de 3 etapas

**Problema que resuelve:** Hoy, si alguien quiere adaptar su CV a un JD, pega ambos en ChatGPT y el modelo inventa experiencia que no tiene. Aurea garantiza que cada bullet del CV adaptado es trazable a algo que el usuario realmente puso en su CV original.

**Cómo funciona:**

*Etapa 1 — Extracción estructurada:* el CV crudo (texto extraído por LiteParse) se convierte en un `CVSchema` Pydantic estricto. Cada experiencia laboral, skill, educación y métrica se extrae como dato estructurado. El schema incluye un hash del texto original para auditoría. Lo que no está en el CV no existe en el schema — es la ground truth del pipeline.

*Etapa 2 — Adaptación con whitelist:* recibe el `CVSchema` + el JD. El modelo puede reformular, traducir, priorizar y re-frasear items que existen en el schema. Si el JD pide algo que no está en el schema (ej: Docker), va a la lista de `gaps`. No inventa, no completa, no extrapola. Output: `(adapted_cv_schema, gaps: list[Gap])`.

*Etapa 3 — Validación post-generación:* cada bullet del CV adaptado se compara por embedding similarity contra los bullets originales del schema. Si alguno tiene similitud < threshold (0.65 inicial, calibrable), se re-intenta la Etapa 2 con feedback. Máximo 2 retries. Si no pasa, se entrega con warning visual al usuario.

**Qué existe hoy en el repo:** `backend/evaluator.py` tiene un chain LangChain con `with_structured_output` que extrae `ResumeEvaluation` (score, keywords, recommendations). Es la Etapa 1 en versión simplificada. Hay que extender el schema de `ResumeEvaluation` (flat, orientado a diagnóstico) a `CVSchema` (anidado, orientado a extracción exhaustiva), y agregar las Etapas 2 y 3 que no existen.

**Qué NO existe:** la adaptación (Etapa 2), la validación por embeddings (Etapa 3), los prompts para cada etapa, el schema `CVSchema` con `WorkExperience`, `Education`, `Metric`, etc.

---

### Feature 2: Renderer PDF ATS-friendly

**Problema que resuelve:** los competidores que exportan a PDF usan templates genéricos. El usuario de Aurea necesita un PDF que un ATS pueda parsear sin problemas: single column, fuentes estándar, headers reconocibles, sin tables ni graphics.

**Cómo funciona:** el `adapted_cv_schema` se renderiza a PDF usando una plantilla diseñada para pasar ATS. Una sola plantilla, bien hecha. El usuario descarga el PDF directamente.

**Qué existe hoy:** nada. El evaluator actual devuelve JSON al frontend y el frontend lo muestra en pantalla. No hay generación de documentos.

**Qué se necesita:** un renderer Python que tome el `CVSchema` adaptado y produzca un PDF. Opciones: `weasyprint` (HTML→PDF) o `reportlab` (programático). WeasyPrint es más simple para una plantilla ATS que es básicamente HTML con fuentes estándar. Son ~100-150 líneas.

---

### Feature 3: Cover letter como texto copiable

**Problema que resuelve:** cuando aplicás a un job, necesitás CV + cover letter. Hacer ambos por separado es doble trabajo. Aurea los genera juntos desde el mismo schema + JD.

**Cómo funciona:** un prompt toma el `adapted_cv_schema` + JD y genera una cover letter de 3 párrafos que conecta la experiencia del candidato con los requirements del puesto. La cover letter solo referencia experiencia que está en el schema — no inventa. Se muestra como texto copiable en pantalla (botón "Copy to clipboard"). No se renderiza a PDF en el MVP — eso va en Fase 2.

**Qué existe hoy:** nada.

**Qué se necesita:** un prompt nuevo + un LLM call de texto libre (no structured output). Estimado ~50 líneas de código backend + UI mínima en frontend.

---

### Feature 4: Selector de idioma de output

**Problema que resuelve:** un dev argentino tiene su CV en español pero aplica a un rol en US. Necesita que el output (CV adaptado + cover letter) salga en inglés, independientemente del idioma del input. O al revés: CV en inglés pero quiere aplicar a un rol local en español.

**Cómo funciona:** el usuario elige ES o EN antes de adaptar. El prompt de Etapa 2 recibe una instrucción de idioma target. La Etapa 1 (extracción) es language-agnostic — extrae datos, no traduce.

**Qué existe hoy:** nada explícito. El evaluator actual responde en inglés siempre.

**Qué se necesita:** un parámetro `output_language: Literal["es", "en"]` en el endpoint `/adapt` y una línea en los prompts de Etapa 2 y cover letter.

---

### Feature 5: Observabilidad del pipeline

**Problema que resuelve:** cuando el pipeline falle en producción (y va a fallar), sin logging estructurado no podés debuggear. No sabés si falló la extracción, la adaptación, o la validación. No sabés cuántos tokens consumió ni cuánto costó.

**Cómo funciona:** cada invocación del pipeline se loggea en una tabla `pipeline_runs` en Supabase con: status (created → extracting → adapting → validating → completed/failed/partial), tokens consumidos, costo en USD, duración, error message si falló. Cada run tiene un ID trazable.

**Qué existe hoy:** `logging.getLogger(__name__)` en cada módulo con logs de texto. No hay tabla, no hay métricas, no hay trazabilidad.

**Qué se necesita:** tabla `pipeline_runs` en Supabase + un wrapper/decorator que loggee cada etapa automáticamente. Estimado ~80 líneas.

---

### Feature 6: Sesiones persistentes en Postgres

**Problema que resuelve:** hoy las sesiones (`cv_sessions`) viven en un dict en memoria con TTL de 60 min. Si el server se reinicia, se pierden. Si hay 2 instancias, no comparten estado. Para un producto con usuarios pagos, esto es inaceptable.

**Cómo funciona:** el `CVSession` se guarda en Supabase (Postgres) en vez de en memoria. El token sigue siendo UUID v4. El TTL se maneja con un campo `created_at` y un query que filtra expirados.

**Qué existe hoy:** `backend/sessions.py` con `cv_sessions: dict[str, CVSession]`, `store_session()`, `get_session()`, `delete_session()`, `cleanup_sessions()`. Las rutas en `src/routes/session.py` ya usan estas funciones.

**Qué se necesita:** reemplazar el dict por queries a Supabase. La interfaz (`store_session`, `get_session`, etc.) se mantiene igual — los routes no cambian. Son ~60 líneas de cambio en `sessions.py` + setup de tabla en Supabase.

---

### Feature 7: Auth con magic link (Fase 1b)

**Problema que resuelve:** necesitás saber quién es el usuario para darle créditos, historial, y free tier limitado. Magic link es el auth más simple: el usuario pone su email, recibe un link, clickea, está autenticado. Sin password, sin OAuth.

**Cómo funciona:** Supabase Auth con Resend como email provider. El frontend muestra un input de email → el backend llama a Supabase Auth → Supabase envía el magic link via Resend → el usuario clickea → JWT en localStorage → las requests incluyen el JWT.

**Qué existe hoy:** nada. No hay auth.

**Qué se necesita:** Supabase Auth config + Resend API key + middleware FastAPI que valide JWT + UI de login en el frontend. Estimado: 1-2 días de trabajo.

---

### Feature 8: Sistema de créditos y pagos (Fase 1b)

**Problema que resuelve:** monetización. El usuario paga por adapters. Necesitás un sistema de créditos que decremente al usar y se recargue al comprar.

**Cómo funciona:** tabla `credits` en Supabase con `user_id, balance, last_purchase_at`. Lemon Squeezy como Merchant of Record (maneja VAT, impuestos, payouts). Webhook handler para `order.created` que acredita créditos. Lógica de decremento provisional al iniciar pipeline, restauración si falla (ver política de errores en plan v2).

**Pricing:**
- Free (con cuenta): 2 adapters gratis (con preview, sin descarga PDF).
- Pay-per-use: $4.99 = 5 créditos. 1 crédito = 1 adapter + 1 cover letter + descarga PDF.
- Pro: $9.99/mes ilimitado.
- Lifetime (primeros 3 meses): $49.

**Qué existe hoy:** nada.

**Qué se necesita:** webhook handler, tabla de créditos, middleware de verificación de créditos antes de ejecutar pipeline, UI de pricing/checkout. Estimado: 3-4 días.

---

### Feature 9: Frontend del adapter (nueva página)

**Problema que resuelve:** el frontend actual es un evaluator ATS. El adapter es un flujo distinto: el usuario pega un JD, elige idioma, clickea "Adapt", ve el resultado con gaps y cover letter, y descarga el PDF.

**Cómo funciona:** nueva página `adapt.html` (o extensión de `index.html`) con: textarea para pegar JD, selector de idioma (ES/EN), botón "Adapt my CV", sección de resultados con CV adaptado + gaps + cover letter + botón de descarga PDF + botón "Copy cover letter".

**Qué existe hoy:** `index.html` + `app.js` tienen el flujo del evaluator (upload CV → ver score + keywords + recommendations). La estructura de upload ya existe. El flujo de resultados es distinto.

**Qué se necesita:** decidir si es una página nueva o un modo del `index.html` existente. Dado que el evaluator ATS se mantiene como funnel free, lo más limpio es una página nueva `adapt.html` con su `adapt.js`. Reutiliza `style.css` y la lógica de upload/session chip de `app.js`.

---

## Parte 2 — Plan de Migración

El plan se divide en 3 fases de migración. Cada fase termina en un estado usable y deployable.

---

### Fase de Migración 1: Backend del pipeline (corresponde a Fase 1a del plan)

**Punto de partida:** el repo tal como está hoy.
**Punto de llegada:** endpoint `/adapt` funcionando, pipeline de 3 etapas completo, sesiones en Supabase, observabilidad básica. Sin auth, sin pagos, sin frontend del adapter.

#### Tarea 1.1 — Definir schemas Pydantic del pipeline

Crear `backend/schemas.py` con los modelos nuevos. Estos reemplazan a `ResumeEvaluation` como output del pipeline de adaptación (el evaluator ATS sigue usando `ResumeEvaluation` tal cual).

```python
# backend/schemas.py — modelos del pipeline de adaptación

from pydantic import BaseModel, Field
from typing import Literal

class Metric(BaseModel):
    value: str                          # "30%", "$2M", "50+"
    context: str                        # "increased revenue by"

class WorkExperience(BaseModel):
    company: str
    role: str
    start_date: str
    end_date: str | None
    bullets: list[str]                  # logros tal cual están en el CV
    technologies: list[str]             # stack mencionado explícitamente
    metrics: list[Metric]               # números/porcentajes mencionados

class Education(BaseModel):
    institution: str
    degree: str
    field: str | None
    year: str | None

class CVSchema(BaseModel):
    candidate_name: str
    summary: str | None
    experiences: list[WorkExperience]
    skills: list[str]                   # solo skills explícitamente mencionadas
    education: list[Education]
    languages: list[str]
    certifications: list[str]
    raw_text_hash: str                  # hash SHA-256 del texto original

class Gap(BaseModel):
    jd_requirement: str
    confidence: Literal["hard", "soft"]
    suggestion: str

class AdaptationResult(BaseModel):
    adapted_schema: CVSchema
    gaps: list[Gap]
    cover_letter: str | None            # se genera por separado pero se agrupa acá
```

**Archivos que se tocan:** nuevo `backend/schemas.py`. No se modifica `backend/evaluator.py` — coexisten.

#### Tarea 1.2 — Crear el extractor de schema (Etapa 1)

Crear `backend/adapter/extractor.py` (no confundir con `backend/extractor.py` que es LiteParse → texto plano). Este módulo toma texto plano y produce `CVSchema`.

Se reutiliza el patrón de `evaluator.py`: LangChain + `with_structured_output` + Pydantic. El prompt va en `backend/prompts/extract_schema.md`.

**Archivos nuevos:**
- `backend/adapter/__init__.py`
- `backend/adapter/extractor.py` — función `extract_schema(cv_text: str) -> CVSchema`
- `backend/prompts/extract_schema.md` — prompt de extracción

**Archivos que NO se tocan:** `backend/evaluator.py`, `backend/extractor.py`. Siguen funcionando para el evaluator ATS.

#### Tarea 1.3 — Crear el adapter (Etapa 2)

Crear `backend/adapter/adapter.py`. Recibe `(CVSchema, job_description, output_language)` y produce `(adapted_cv_schema, gaps)`.

**Archivos nuevos:**
- `backend/adapter/adapter.py` — función `adapt_cv(schema: CVSchema, jd: str, lang: str) -> tuple[CVSchema, list[Gap]]`
- `backend/prompts/adapt_cv.md` — prompt de adaptación con la regla de whitelist

#### Tarea 1.4 — Crear el validador (Etapa 3)

Crear `backend/adapter/validator.py`. Compara cada bullet del schema adaptado contra los bullets originales usando embeddings (`all-MiniLM-L6-v2`, ya disponible via `backend/ranker.py` que tiene `embed_text()`).

**Archivos nuevos:**
- `backend/adapter/validator.py` — función `validate_adaptation(original: CVSchema, adapted: CVSchema) -> list[str]` (retorna lista de bullets sospechosos)

**Archivos que se reutilizan:** `backend/ranker.py` → `embed_text()` ya usa `all-MiniLM-L6-v2`.

#### Tarea 1.5 — Crear el orquestador del pipeline

Crear `backend/adapter/pipeline.py`. Orquesta las 3 etapas + cover letter + logging. Maneja retries y estados.

```python
# backend/adapter/pipeline.py — interfaz pública del pipeline

async def run_pipeline(
    cv_text: str,
    job_description: str,
    output_language: Literal["es", "en"] = "en",
    user_id: str | None = None,
) -> AdaptationResult:
    """
    Ejecuta el pipeline completo:
    1. Extracción → CVSchema
    2. Adaptación → adapted CVSchema + gaps
    3. Validación → bullets sospechosos
    4. Cover letter → texto libre
    5. Logging → pipeline_runs table
    
    Retries: máx 2 en Etapa 2 si validación falla.
    """
```

**Archivos nuevos:** `backend/adapter/pipeline.py`

#### Tarea 1.6 — Migrar sesiones a Supabase

Modificar `backend/sessions.py` para usar Supabase en vez del dict en memoria. La interfaz pública (`store_session`, `get_session`, `delete_session`) se mantiene idéntica para no romper las rutas.

**Archivos que se modifican:** `backend/sessions.py`
**Archivos que NO se tocan:** `src/routes/session.py` (usa las funciones de `sessions.py`, la interfaz no cambia)

**Dependencia nueva:** `supabase` (Python SDK)

**Setup requerido:** crear proyecto en Supabase, tabla `cv_sessions` con campos `token, cv_text, cv_embedding, filename, created_at`. Env vars: `SUPABASE_URL`, `SUPABASE_KEY`.

#### Tarea 1.7 — Crear tabla pipeline_runs en Supabase

SQL de creación + wrapper Python para loggear cada invocación.

**Archivos nuevos:** `backend/adapter/logger.py` — funciones `log_pipeline_start()`, `log_pipeline_stage()`, `log_pipeline_end()`

#### Tarea 1.8 — Endpoint `/adapt`

Crear `src/routes/adapt.py` con el endpoint `POST /adapt`. Recibe CV (file o session token) + JD (texto) + idioma. Ejecuta el pipeline. Retorna el `AdaptationResult`.

**Archivos nuevos:** `src/routes/adapt.py`
**Archivos que se modifican:** `src/router.py` (agregar el nuevo router)

#### Tarea 1.9 — Renderer PDF

Crear `backend/adapter/renderer.py`. Toma un `CVSchema` adaptado y genera un PDF ATS-friendly.

**Archivos nuevos:** `backend/adapter/renderer.py`
**Dependencia nueva:** `weasyprint` (o `reportlab`)

#### Tarea 1.10 — Tests del pipeline

Tests para cada etapa del pipeline + test de integración del orquestador. Mockear LLM calls con `respx` (patrón ya usado en `tests/test_scorer.py`).

**Archivos nuevos:** `tests/test_adapter_extractor.py`, `tests/test_adapter_adapter.py`, `tests/test_adapter_validator.py`, `tests/test_adapter_pipeline.py`, `tests/test_adapt_route.py`

**Estado al terminar Fase de Migración 1:**
```
bot-curriculum/
├── backend/
│   ├── adapter/                    # ← NUEVO: todo el pipeline de adaptación
│   │   ├── __init__.py
│   │   ├── extractor.py            # Etapa 1: texto → CVSchema
│   │   ├── adapter.py              # Etapa 2: CVSchema + JD → adapted + gaps
│   │   ├── validator.py            # Etapa 3: similarity check
│   │   ├── pipeline.py             # Orquestador de las 3 etapas
│   │   ├── cover_letter.py         # Generador de cover letter
│   │   ├── renderer.py             # CVSchema → PDF
│   │   └── logger.py               # Logging a pipeline_runs
│   ├── schemas.py                  # ← NUEVO: CVSchema, Gap, AdaptationResult
│   ├── evaluator.py                # sin cambios — sigue funcionando para ATS
│   ├── extractor.py                # sin cambios — LiteParse
│   ├── sessions.py                 # ← MODIFICADO: Supabase en vez de dict
│   ├── prompts/
│   │   ├── ats_skill.md            # sin cambios
│   │   ├── extract_schema.md       # ← NUEVO
│   │   └── adapt_cv.md             # ← NUEVO
│   └── ... (rest sin cambios)
├── src/routes/
│   ├── adapt.py                    # ← NUEVO: POST /adapt
│   └── ... (rest sin cambios)
└── tests/
    ├── test_adapter_*.py           # ← NUEVOS
    └── ... (rest sin cambios)
```

**Verificación:** `POST /adapt` con un CV y un JD devuelve un JSON con `adapted_schema`, `gaps`, y `cover_letter`. El PDF se puede descargar. La tabla `pipeline_runs` registra la invocación. Todo sin auth, sin pagos, sin frontend nuevo.

---

### Fase de Migración 2: Frontend del adapter (sigue en Fase 1a)

**Punto de partida:** el pipeline funciona via API.
**Punto de llegada:** un usuario puede subir su CV, pegar un JD, y descargar el CV adaptado + copiar la cover letter. Sin auth, sin pagos.

#### Tarea 2.1 — Página adapt.html

Crear `src/static/adapt.html` con:
- Header con nav (← Back to evaluator)
- Zona de upload de CV (reutiliza patrón de `index.html`: drop zone + session chip)
- Textarea para pegar JD
- Selector de idioma (ES/EN, dos botones toggle)
- Botón "Adapt my CV"
- Sección de resultados (oculta inicialmente):
  - CV adaptado renderizado (preview del PDF)
  - Lista de gaps con sus sugerencias
  - Cover letter con botón "Copy to clipboard"
  - Botón "Download PDF"

#### Tarea 2.2 — adapt.js

Lógica del adapter: detect session, submit to `/adapt`, render results, handle download, copy cover letter.

**Archivos nuevos:** `src/static/adapt.html`, `src/static/adapt.js`
**Archivos que se modifican:** `src/static/style.css` (agregar estilos del adapter, reutilizando CSS vars existentes)

**Verificación:** el flujo completo funciona end-to-end en browser. Subís CV → pegás JD → elegís idioma → clickeás "Adapt" → ves resultado con gaps + cover letter → descargás PDF. Se lo mandás a 5 testers.

---

### Fase de Migración 3: Auth, pagos y deploy (corresponde a Fase 1b)

**Punto de partida:** el adapter funciona end-to-end, testeado con 5 personas.
**Punto de llegada:** un desconocido puede pagar y descargar un CV adaptado.

#### Tarea 3.1 — Setup Supabase Auth

Configurar Supabase Auth con magic link. Configurar Resend como email provider en Supabase.

**Archivos nuevos:** `backend/auth.py` — helper para validar JWT de Supabase en FastAPI

#### Tarea 3.2 — Middleware de auth en FastAPI

Dependency injection que extrae el user_id del JWT y lo inyecta en los endpoints que lo necesiten. Los endpoints existentes (`/evaluate`, `/jobs`) siguen sin auth. Solo `/adapt` requiere auth.

**Archivos que se modifican:** `src/routes/adapt.py` (agregar dependency de auth)

#### Tarea 3.3 — Frontend de login

Modal o página de login con input de email + "Send magic link" + estado de "check your email". Después de auth, el JWT se guarda en localStorage y se envía en headers.

**Archivos que se modifican:** `src/static/adapt.html` (agregar modal de login), `src/static/adapt.js` (lógica de auth)

#### Tarea 3.4 — Sistema de créditos

Tabla `credits` en Supabase. Lógica de decremento provisional al iniciar pipeline, restauración si falla (según política de errores del plan v2).

**Archivos nuevos:** `backend/credits.py` — `get_balance()`, `decrement()`, `restore()`, `add_credits()`

#### Tarea 3.5 — Integración Lemon Squeezy

Webhook handler para `order.created` y `subscription.updated`. Cuando Lemon Squeezy confirma un pago, se llama a `add_credits()`.

**Archivos nuevos:** `src/routes/webhooks.py` — `POST /webhooks/lemonsqueezy`
**Archivos que se modifican:** `src/router.py` (agregar webhook router)

#### Tarea 3.6 — UI de pricing y checkout

Página o sección con los tiers de pricing. Botones que redirigen a Lemon Squeezy checkout. Indicador de créditos disponibles en el header.

**Archivos nuevos:** `src/static/pricing.html` (o sección en `adapt.html`)

#### Tarea 3.7 — Free tier lógica

2 adapters gratis con cuenta creada. Sin descarga PDF en free — solo preview en pantalla. El backend chequea: si `credits.balance == 0` y `total_free_used < 2`, permite el adapter pero no genera PDF. Si `total_free_used >= 2` y no hay créditos, muestra pricing.

**Archivos que se modifican:** `src/routes/adapt.py`, `backend/credits.py`

#### Tarea 3.8 — Migrar deploy a Railway

Crear proyecto en Railway. Configurar env vars. Actualizar `render.yaml` → `railway.toml` (o usar auto-detect). DNS si hay dominio custom.

**Archivos que se modifican/nuevos:** `railway.toml` (o se borra `render.yaml` y Railway auto-detecta)

#### Tarea 3.9 — Desacoplar Job Board del flujo crítico

El Job Board (`/jobs`, `/jobs/ranked`, `/jobs/score`) sigue funcionando pero no se promociona. El nav del adapter no linkea al Job Board. Si alguna dependencia del Job Board falla (Remotive API down, Zvec corrupto), el adapter no se ve afectado.

**Archivos que se modifican:** verificar que `src/routes/adapt.py` no importa nada de `backend/jobs.py` ni `backend/scorer.py` ni `backend/ranker.py` (excepto `embed_text()` que se usa para validación).

**Verificación:** alguien sin cuenta llega → ve el adapter → pone email → recibe magic link → usa 2 adapters gratis (sin PDF) → ve pricing → paga $4.99 → tiene 5 créditos → adapta con descarga PDF.

---

## Parte 3 — Mapa de dependencias

Lo que se puede hacer en paralelo y lo que tiene que ser secuencial:

```
Fase de Migración 1 (secuencial, ~7-8 días):
  1.1 Schemas           ──→ 1.2 Extractor ──→ 1.3 Adapter ──→ 1.5 Pipeline
  (independiente)          1.4 Validator ──────────────────────↗
                           1.6 Sesiones Supabase (paralelo con 1.2-1.4)
                           1.7 Pipeline runs (paralelo con 1.2-1.4)
                           1.8 Endpoint /adapt (después de 1.5)
                           1.9 Renderer PDF (paralelo con 1.3-1.5)
                           1.10 Tests (continuo)

Fase de Migración 2 (~2-3 días):
  2.1 adapt.html ──→ 2.2 adapt.js
  (depende de que 1.8 esté funcionando)

Fase de Migración 3 (~7-10 días):
  3.1 Supabase Auth ──→ 3.2 Middleware ──→ 3.3 Frontend login
  3.4 Créditos ──→ 3.5 Lemon Squeezy ──→ 3.6 Pricing UI
  3.7 Free tier (después de 3.4)
  3.8 Railway (paralelo con todo)
  3.9 Desacoplar Job Board (paralelo con todo)
```

---

## Parte 4 — Lo que NO se toca

Estos archivos/módulos siguen funcionando exactamente como están. No se modifican, no se migran, no se refactorean:

- `backend/evaluator.py` — el evaluator ATS sigue siendo el funnel free.
- `backend/extractor.py` — LiteParse sigue extrayendo texto. El pipeline nuevo lo usa.
- `backend/jobs.py`, `backend/scorer.py`, `backend/ranker.py` — el Job Board sigue vivo pero no se promociona. Se reutiliza `embed_text()` de `ranker.py` para la validación.
- `src/routes/evaluate.py`, `src/routes/health.py`, `src/routes/jobs.py`, `src/routes/session.py` — todos los endpoints existentes siguen funcionando.
- `src/static/index.html`, `src/static/app.js` — el evaluator ATS no cambia.
- `src/static/jobs.html`, `src/static/jobs.js`, `src/static/jobs.css` — el Job Board no cambia.
- Todos los tests existentes (57 tests) — deben seguir pasando después de cada fase de migración.

---

## Parte 5 — Dependencias nuevas

| Paquete | Para qué | Estimado de líneas que ahorra |
|---------|----------|-------------------------------|
| `supabase` | SDK Python para auth + DB + storage | Reemplaza el dict en memoria + agrega auth + logging |
| `weasyprint` | Render HTML → PDF | Alternativa a escribir PDF con reportlab (~200 líneas ahorradas) |
| `resend` | Envío de emails (magic link via Supabase, notificaciones) | Solo config, Supabase lo llama directo |

**Dependencias que NO se agregan:** no se migra a React/Next.js/Astro. No se agrega Redis. No se agrega Celery/background workers. El pipeline corre síncrono en el request (el response time es ~5-10 seg, aceptable para un adapter que el usuario espera).

---

## Parte 6 — Checklist pre-deploy de cada fase

### Después de Fase de Migración 1:
- [ ] `POST /adapt` con CV de prueba + JD de prueba devuelve JSON válido
- [ ] El `adapted_schema` no contiene skills que no estén en el CV original
- [ ] El PDF se descarga y es parseable por un ATS (test: copiar texto del PDF y verificar que no está roto)
- [ ] La tabla `pipeline_runs` tiene un registro con status `completed`
- [ ] Los 57 tests existentes siguen pasando
- [ ] Los tests nuevos del pipeline pasan

### Después de Fase de Migración 2:
- [ ] El flujo end-to-end funciona en browser
- [ ] 5 testers reales lo probaron y al menos 3/5 usarían el CV adaptado
- [ ] La cover letter se puede copiar al clipboard
- [ ] El selector de idioma funciona (output en ES cuando se pide ES, EN cuando se pide EN)

### Después de Fase de Migración 3:
- [ ] Magic link llega al email y autentica correctamente
- [ ] Los 2 adapters gratis funcionan sin pago
- [ ] El adapter 3 muestra pricing
- [ ] Un pago de prueba en Lemon Squeezy (modo test) acredita créditos
- [ ] Un adapter post-pago consume 1 crédito y permite descarga PDF
- [ ] Si el pipeline falla, el crédito se restaura
- [ ] Railway sirve sin sleep (a diferencia de Render free)
- [ ] El evaluator ATS sigue funcionando independientemente del adapter
