# Rediseño de navegación y producto — Aurea

- **Fecha:** 2026-09-25
- **Rama:** `feature/task-4-1-rediseno-navegacion` (desde `develop`)
- **Fuente del diseño:** `C:\Users\pablo\Desktop\aurea_feedback.excalidraw`. Se implementa **tal cual** el esquema, completo, en esta rama.

## 1. Objetivo

Reorganizar Aurea en dos superficies con objetivos distintos:

| Superficie | Objetivo |
|---|---|
| **Landing** | Convertir visitas → usuarios |
| **App** | Convertir gratuitos → premium, y retener a los premium |

Hoy son 5 páginas sueltas con el mismo header de 4 tabs copiado en cada una (Evaluator, Adapter, Job Board, Pricing) y la auth repartida entre `adapt.js` y `pricing.js`. El rediseño agrega:

- Landing de marketing.
- Funnel de onboarding **sin login** que usa el Evaluator como gancho.
- Shell de App con sidebar.
- Tailor y Cover como acciones separadas, con costo propio.
- Historial persistido (My Jobs), CV base por usuario y Settings.

### Éxito

- Una visita puede subir su CV y ver su evaluación sin registrarse. El signup aparece recién al pedir una acción paga, y esa acción se ejecuta sola después del login.
- Con sesión, toda la App se navega desde un sidebar fijo con el chip de créditos siempre visible.
- Todo lo que genera un usuario (CVs, cartas, JDs) queda en My Jobs y se puede volver a descargar.
- La UI se puede usar en inglés (default) y en español.

## 2. Decisiones tomadas

| Tema | Decisión |
|---|---|
| Arquitectura del front | Multi-página + `shell.js` compartido (sin SPA, sin build step) |
| Landing con sesión | Login/Sign up se reemplazan por **"Go to app"**; no hay redirect automático |
| Home / About | Una sola landing con anclas |
| Features ▾ | Cada ítem hace scroll a un bloque de la landing con su CTA "Try it" |
| Sidebar | Solo con sesión. Sin sesión, la App es el onboarding a pantalla completa |
| Ítem "CV" | Subir o reemplazar el CV base del usuario |
| Add credits / Billing | UI real, pago "coming soon" → waitlist existente. Lemon Squeezy (3.5) sigue bloqueado |
| Idioma | UI en inglés por default, toggle EN/ES. El output (CV/carta) mantiene el comportamiento actual |
| Job link | El backend descarga la URL y extrae el texto, con protección anti-SSRF |
| Precios | Resultados: **Tailor 2🪙 = CV adaptado + cover letter**; **Cover 1🪙**. Pantalla Tailor: **1🪙 (solo CV)**. Pantalla Cover: **1🪙**. **Apply to my CV: 1🪙** |
| Apply to my CV | Un botón que aplica **todas** las recomendaciones; el CV mejorado reemplaza al CV base |
| Login | Google OAuth + magic link |
| Bono de signup | 5 créditos **solo para usuarios nuevos** (los existentes no cambian) |

## 3. Páginas y navegación

Todas en `src/static/`.

| URL | Contenido | Sidebar |
|---|---|---|
| `/` (`index.html`) | Landing | — |
| `evaluator.html` | Onboarding 1-3 (upload → analizando → resultados). Home de la App | solo con sesión |
| `tailor.html` | Form Tailor + resultado | ✅ |
| `cover.html` | Form Cover + carta | ✅ |
| `jobs.html` | My Jobs + Recommended jobs | ✅ |
| `job-detail.html` | Detalle de la oferta → "Adapt my CV to this role" → `tailor.html` con la JD cargada | ✅ |
| `cv.html` | CV base | ✅ |
| `settings.html` | Language · Usage · Add credits · Billing · Delete account | ✅ |

**Páginas que se eliminan:**
- `adapt.html` queda como redirect (`<meta http-equiv="refresh">`) a `tailor.html`, para no romper magic links ya enviados ni bookmarks.
- `pricing.html` queda como redirect a `/#pricing`.
- `index.html` (Evaluator) se reemplaza por la landing y su contenido se muda a `evaluator.html`.
- `adapt.js`, `app.js` y `pricing.js` se reparten entre `shell.js` y los JS de cada página nueva.
- El buscador actual de `jobs.html` (búsqueda client-side + filtros por tag) se reemplaza por My Jobs + Recommended.

Las páginas con sidebar, si no hay sesión, redirigen a `evaluator.html`.

### 3.1 Landing (`index.html`)

- **Nav**: Aurea · Home · About · Features ▾ (Evaluator / Adapter / Job board) · Pricing · EN/ES · Login · Sign up. Con sesión, Login y Sign up pasan a **"Go to app"** → `evaluator.html`.
- **Secciones** (anclas):
  - `#home`: hero con CTA **"Improve my CV"** → `evaluator.html`.
  - `#about`.
  - `#features-evaluator`, `#features-adapter`, `#features-jobs`: un bloque por feature, cada uno con "Try it" → `evaluator.html`.
  - `#pricing`: cards Free / Pro con "Notify me", que absorbe lo que hoy hace `pricing.html` / `pricing.js`.
- Login y Sign up abren el modal de auth de `shell.js`.

## 4. Shell compartido

### 4.1 `shell.js`

Se carga en todas las páginas, incluida la landing, que solo usa auth + modal + i18n. Junto con la CDN de `supabase-js` que ya se usa.

Responsabilidades (la lógica sale de `adapt.js` líneas ~728-897 y de `pricing.js`):

1. Traer `GET /config` e inicializar el cliente de Supabase **una sola vez**.
2. Mostrar los errores del magic link que vienen en el fragmento de la URL (hoy `showAuthErrorFromUrl`).
3. Con sesión:
   - Dibujar el **sidebar**: Evaluator · Tailor · Cover · Jobs · CV · Settings · Log out, con el ítem activo según la página.
   - Dibujar el **chip de créditos** `N 🪙` arriba a la derecha.
4. Sin sesión:
   - Header mínimo "Aurea" + toggle EN/ES + Sign up.
   - Barra de oferta **"Sign up now and get 5 credits"** en `evaluator.html`.
5. **Modal de auth**:
   - Título de signup con la oferta de 5 créditos.
   - Botón **"Continue with Google"** (`signInWithOAuth({ provider: 'google', options: { redirectTo } })`).
   - Separador y el email con magic link (el flujo actual).
6. En el **primer login** con un token de sesión anónimo en `localStorage`, llama `PUT /cv` con ese token para reclamar el CV como CV base.
7. API pública en `window.aurea`:
   - `session`: la sesión actual o `null`.
   - `authFetch(url, opts)`: `fetch` con `Authorization: Bearer`.
   - `refreshCredits()`: vuelve a leer `GET /credits` y actualiza el chip; devuelve el balance.
   - `requireAuth(actionName, payload)`: si hay sesión, resuelve de inmediato. Si no, guarda `{actionName, payload}` en `localStorage` (`aurea_pending_action`), abre el modal y la promesa no resuelve. Al volver del login, la página lee `aurea.takePendingAction()` y la ejecuta.
   - `onReady(cb)`: se llama cuando la auth ya se inicializó.
   - `t(key)`: ver 4.2.

### 4.2 `i18n.js`

- El HTML se escribe en inglés con atributos `data-i18n="key"` (texto) y `data-i18n-placeholder="key"`.
- `i18n.js` define `const I18N_ES = { key: 'texto', … }`. El inglés es el texto del HTML, así que no hay parpadeo en el idioma default.
- Idioma guardado en `localStorage` (`aurea_lang`, `'en'` por default). Al cargar, si es `es`, se reemplazan los textos marcados.
- `aurea.t(key, fallbackEn)` para los textos que arma el JS.
- El toggle EN/ES aparece en el nav de la landing, en el header sin sesión y en Settings.

### 4.3 Estilos

`style.css` suma:
- Layout `.app-shell`: sidebar fijo de ~150 px + contenido.
- Sidebar colapsable en mobile (menú hamburguesa, sin JS extra más allá de un toggle de clase).
- Estilos de la landing.

Se mantiene el design system actual (Inter, tokens y componentes existentes).

## 5. Funnel de onboarding (`evaluator.html`)

Una página con tres estados.

**Estado 1 — Upload**
- Zona drag & drop "Upload or drop your CV" + panel **"You will get"** con los cuatro ítems y los textos del esquema: ATS compatibility score, Keyword intelligence, Formatting flags, Actionable recommendations.
- Si el usuario tiene sesión y CV base con `last_evaluation`, arranca directo en el estado 3. "Upload a new CV" vuelve al estado 1.

**Estado 2 — Analizando**
- El panel "You will get" queda fijo; la zona de upload pasa a "Analyzing your CV…" con progreso.
- Llamadas:
  - `POST /session` con el archivo → token (se guarda en `localStorage`, como hoy `SESSION_KEY`).
  - `POST /evaluate` con `X-CV-Session-Token` (y `Authorization` si hay sesión).

**Estado 3 — Resultados**
- Cabecera: avatar con iniciales + `candidate_name` + `overall_score`.
- **Summary**, **Strengths**, **Weaknesses**. Weaknesses incluye `formatting_issues` y `keywords_missing`.
- **Recommendations** + botón **"Apply to my CV · 1🪙"** → `POST /improve`.
- **Caja Adapter**: input "Job link or description", **"Generate Cover Letter · 1🪙"** (`mode=cover`) y **"Tailor your CV · 2🪙"** (`mode=both`). El resultado se guarda en `localStorage` y se redirige a `cover.html` o `tailor.html`, que lo muestran.
- **Job recommendations**: cards desde `GET /jobs/ranked?token=…` → `job-detail.html`.
- El resultado de la evaluación se guarda en `localStorage` (`aurea_last_evaluation`) para sobrevivir al ida y vuelta del login.

**Gate de acciones pagas**: los tres botones llaman `aurea.requireAuth()` (ver 4.1).
- Con 402 `no_credits`: banner "You've used all your credits" con link a `settings.html#add-credits`.

**Errores**: archivo vacío o de más de 5 MB, extracción fallida (422), 429 y fallo del evaluator. Se reusan los mensajes de `app.js` y se puede reintentar sin recargar.

## 6. Pantallas con sidebar

- **`tailor.html`**
  - Línea "Using: `<filename>` · Change" → `cv.html`.
  - Input "Job link or description" + **"Tailor your CV · 1🪙"** (`mode=cv`).
  - El resultado reusa el render actual de `adapt.js`: CV adaptado, gaps, suspicious bullets, descarga del PDF y el panel "Prepare for the interview" (`POST /interview`, sin cambios).
  - Link "Generate a cover letter for this job · 1🪙" → `cover.html` con la JD cargada.
  - Toma la JD pendiente del job board (`aurea_pending_jd`, como hoy).
- **`cover.html`**: el mismo form + **"Generate Cover Letter · 1🪙"** (`mode=cover`) → la carta, con Copy y Download (`.txt`).
- **`jobs.html`**, dos columnas:
  - **My Jobs**: `GET /history`. Cada ítem muestra puesto, empresa, fecha y chips CV/Cover. Al abrirlo (`GET /history/{id}`) se ven la JD, el CV adaptado (+ `GET /history/{id}/pdf`) y la carta.
  - **Recommended jobs**: `GET /jobs/ranked` (con sesión, contra el CV base) → `job-detail.html`.
- **`cv.html`**:
  - El CV base activo (`GET /cv`): nombre del archivo, origen (upload / improved) y fecha.
  - "Replace CV" (drag & drop → `PUT /cv`).
  - "Re-evaluate" → `evaluator.html` en el estado 2.
- **`settings.html`**:
  - **Language**: toggle EN/ES.
  - **Usage**: créditos disponibles (`GET /credits`) + cantidad de generaciones (`GET /history`).
  - **Add credits** (`#add-credits`): tres paquetes con precio y "Notify me" → `POST /waitlist` (sin cambios de backend).
  - **Billing**: plan Free, historial de pagos vacío.
  - **Delete account**: el usuario escribe "DELETE" para confirmar → `DELETE /account` → sign out → `/`.
- Sin CV base, Tailor y Cover muestran el aviso "Upload your CV first" con link a `cv.html`.

## 7. Backend

### 7.1 Acceso a la base

- **`backend/db.py`** (nuevo): un único cliente de Supabase creado con `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`. Si falta alguna de las dos, el cliente es `None` y los módulos que lo usan son no-op, como hoy.
- `backend/credits.py` pasa a usar `db`. **Motivo**: hoy lee `SUPABASE_KEY`, que prod no setea a propósito (ver CLAUDE.md). Si es así, los créditos están desactivados en prod. Hay que verificarlo en el `.env` del VPS.
- `backend/sessions.py` y `backend/auth.py` no cambian.
- `ensure_user()` hace el upsert con `balance: 5` (hoy tiene `2` hardcodeado).

### 7.2 Migraciones (`supabase/migrations/`)

1. `…_credits_default_5.sql`: `ALTER TABLE credits ALTER COLUMN balance SET DEFAULT 5;`
2. `…_user_cvs.sql`:
   - `user_cvs(user_id UUID PK, cv_text TEXT NOT NULL, filename TEXT, source TEXT CHECK (source IN ('upload','improved')), last_evaluation JSONB, updated_at TIMESTAMPTZ DEFAULT now())`
   - **RLS activada, sin políticas.**
3. `…_generations.sql`:
   - `generations(id UUID PK DEFAULT gen_random_uuid(), user_id UUID NOT NULL, created_at TIMESTAMPTZ DEFAULT now(), kind TEXT CHECK (kind IN ('cv','cover','both','improve')), job_title TEXT, company TEXT, job_description TEXT, job_url TEXT, result JSONB NOT NULL)`
   - Índice en `(user_id, created_at DESC)`.
   - **RLS activada, sin políticas.**

Sin políticas, la anon key no puede leer ni escribir esas tablas; solo el backend, con la service role. Las migraciones las aplica el usuario en Supabase (o Claude con el MCP, si se lo pide).

### 7.3 Módulos nuevos

- **`backend/user_cv.py`**: `get_cv(user_id)`, `save_cv(user_id, cv_text, filename, source)`, `save_evaluation(user_id, evaluation)`, `delete_cv(user_id)`.
- **`backend/history.py`**: `add(user_id, kind, job_description, job_url, result)`, `list_for(user_id)` (sin `result`, para que sea liviano), `get(user_id, id)` (filtra por `user_id`: nadie lee filas ajenas), `delete_all(user_id)`.
  - `job_title` y `company` salen del CV adaptado o, si no hay, de las primeras líneas de la JD. No hace falta una llamada extra al LLM.
- **`backend/job_fetch.py`**: `async fetch_job_text(url) -> str`
  - Solo `http` y `https`.
  - Resuelve el host y **rechaza** IPs privadas, loopback, link-local, reservadas y multicast (`ipaddress`).
  - Redirects: `follow_redirects=False` y se siguen a mano, máximo 3, validando cada salto.
  - Timeout de 10 s; lectura en streaming con tope de 2 MB.
  - Extrae el texto visible con `html.parser` de la stdlib (descarta `script`, `style`, `noscript`).
  - Si falla o quedan menos de 200 caracteres, lanza `JobFetchError`. La ruta la convierte en 422: *"We couldn't read that link — paste the job description instead."*
  - `ponytail:` la IP se valida al resolver, pero httpx vuelve a resolver al conectar (queda una ventana de DNS rebinding). Si pasa a importar, conectar a la IP ya validada.
- **`backend/adapter/improver.py`** + **`backend/prompts/improve_cv.md`**: toma el `CVSchema` y la lista de recomendaciones y devuelve un `CVSchema` mejorado. El CV y las recomendaciones van como **dato no confiable**, con el mismo encuadre anti prompt-injection del resto de los prompts. Se pasa por el validator existente y se renderiza con `render_pdf`.

### 7.4 Endpoints

| Endpoint | Auth | Comportamiento |
|---|---|---|
| `POST /evaluate` | opcional | `ResumeEvaluation` suma `strengths: list[str]` y `weaknesses: list[str]` (prompt `ats_skill.md` actualizado). Con sesión, `save_evaluation()`. |
| `GET /cv` | requerida | `{filename, source, updated_at, last_evaluation}` o 404. |
| `PUT /cv` | requerida | Archivo **o** `X-CV-Session-Token`. Extrae el texto (`extract_text`) o lo toma de la sesión y `save_cv(source='upload')`. Mismos límites que `/adapt` (5 MB, mínimo 100 caracteres). |
| `POST /adapt` | requerida | Campos: `job_input` (texto o URL), `mode` (`cv`/`cover`/`both`, default `both`), `output_language`, `file` opcional. Costo `{cv:1, cover:1, both:2}`. CV: archivo > token de sesión > CV base. Si `job_input` es URL, se descarga con `fetch_job_text`. `decrement(user_id, cost)`; si el pipeline falla, `restore(user_id, cost)`. Al terminar, `history.add(...)`. |
| `POST /improve` | requerida | Body `{recommendations: list[str]}` (máx. 20 ítems, 500 caracteres cada uno). CV base obligatorio (si falta, 400). Costo 1. `extract` → `improve` → `validate` → `render_pdf`. `save_cv(source='improved')` con el texto del CV mejorado, `history.add(kind='improve')`. Devuelve el mismo formato que `AdaptationResult` (con `run_id` para el PDF). |
| `GET /history` | requerida | Lista del usuario, más reciente primero. |
| `GET /history/{id}` | requerida | Detalle; 404 si no existe o no es del usuario. |
| `GET /history/{id}/pdf` | requerida | Regenera el PDF desde `result.adapted_schema` con `render_pdf`. 404 si es de tipo `cover`. |
| `GET /jobs/ranked` | opcional | Si no hay `token` y hay sesión con CV base, calcula `embed_text(cv_text)` y rankea contra eso. |
| `DELETE /account` | requerida | Borra las filas del usuario en `user_cvs`, `generations`, `credits` y `waitlist`, y después `auth.admin.delete_user(user_id)`. 204. |

**Cambios en el pipeline** (`run_pipeline`): parámetro nuevo `mode`.
- `cv`: igual que hoy pero sin la etapa 4.
- `both`: igual que hoy.
- `cover`: etapa 1 (extract) + `generate_cover_letter(cv_schema_original, jd, lang)`. Sin adapt, validator ni PDF.

**Sin cambios**: el rate limit (3/min por IP en `/adapt`, `/evaluate`, `/improve`), el validator, el renderer, `/interview`, `/credits` y `/waitlist`.

### 7.5 Configuración del usuario (fuera del código)

1. **Google OAuth**:
   - En Google Cloud Console, crear un OAuth client (Web).
   - Authorized redirect URI: `https://<project-ref>.supabase.co/auth/v1/callback`.
   - En Supabase → Authentication → Providers → Google, pegar el client ID y el secret.
   - En Authentication → URL Configuration, agregar `https://aurea.pablolerner.dev/**` y `http://localhost:8000/**` como redirect URLs (con wildcard: el login manda `redirectTo` = URL de la página actual).
2. Confirmar que `SUPABASE_SERVICE_ROLE_KEY` esté en `/home/deploy/bot_curriculum/.env`.
3. Aplicar las 3 migraciones.

## 8. Errores y seguridad

- Todo dato de la API pasa por `escHtml()` antes de tocar el DOM (convención existente).
- Las recomendaciones que envía el cliente a `/improve` son input no confiable: se validan los topes y se encuadran como dato en el prompt.
- El job link tiene protección anti-SSRF (7.3).
- `generations` y `user_cvs` solo son accesibles vía backend, y cada query filtra por el `user_id` del JWT.
- Los errores de LLM en `/adapt` y `/improve` restauran los créditos.
- Sin cambios en `/session`: los CVs anónimos siguen con un TTL de 60 minutos.

## 9. Testing

- **Backend, TDD estricto** (tests primero). Los patches se hacen en el lugar de importación y el cliente de DB se mockea en `backend.db`. Cobertura:
  - `ensure_user` con 5.
  - `credits` usa el cliente de `db`.
  - `/adapt`: cada modo con su costo, `restore` con el mismo costo si falla, orden de fuente del CV (archivo > token > base), `job_input` URL → `fetch_job_text` (mock) y 422 si falla, `history.add` llamado.
  - `/improve`: sin CV base → 400; sin créditos → 402; topes de las recomendaciones; guarda el CV como `improved`.
  - `/cv` GET/PUT (archivo y token).
  - `/history`: aislamiento por usuario y PDF de un `cover` → 404.
  - `/account` borra todo y llama a admin.
  - `/evaluate` con strengths/weaknesses y `save_evaluation` solo con sesión.
  - `/jobs/ranked` con CV base.
  - `job_fetch`: esquema no http, IP privada, redirect a IP privada, más de 3 redirects, tope de tamaño, texto corto, extracción de HTML.
  - Pipeline con `mode=cover` y `mode=cv`.
- **i18n**: `tests/test_i18n.py` recorre `src/static/*.html`, junta las keys `data-i18n*` y falla si falta alguna en `I18N_ES` (parseando `i18n.js` con una regex).
- **Front**: verificación manual con Playwright por página, sin y con sesión, en desktop (1280) y mobile (390). Flujo crítico: landing → Improve my CV → upload → resultados → Tailor 2🪙 → modal → login → la acción corre sola.
- `ruff check backend/ src/routes/ tests/` y `pytest tests/ -q` en verde antes de cada commit.

## 10. Orden de implementación

Commits atómicos en esta rama; un PR a `develop` al final.

1. **Base de backend**: `db.py`, `credits` → `db` + 5 créditos, migraciones.
2. **Endpoints**: `/evaluate` (strengths/weaknesses) → `user_cv` + `/cv` → `job_fetch` → pipeline `mode` + `/adapt` → `history` + `/history` → `improver` + `/improve` → `/account` → `/jobs/ranked`.
3. **Shell**: `i18n.js`, `shell.js`, layout del sidebar, modal con Google.
4. **Landing** (`index.html`).
5. **`evaluator.html`** (funnel).
6. **`tailor.html`** + **`cover.html`**.
7. **`jobs.html`**, **`cv.html`**, **`settings.html`** (+ `job-detail.html` dentro del shell).
8. **Limpieza**: redirects de `adapt.html` / `pricing.html`, borrar `adapt.js`, `app.js`, `pricing.js`, `jobs.css` si queda sin uso; actualizar CLAUDE.md.

## 11. Fuera de alcance

- Checkout real (Lemon Squeezy, tarea 3.5).
- Traducir el output del LLM según el idioma de la UI.
- Guardar los PDFs como binarios (se regeneran).
- Activar RLS en `cv_sessions` / `pipeline_runs` (deuda existente, sin cambios).
