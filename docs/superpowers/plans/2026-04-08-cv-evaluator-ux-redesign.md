# CV Evaluator UX Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the CV Evaluator page with a two-column layout, prominent back button, visible job context panel, session preloading (no re-upload if CV already in job board session), and a results CTA back to the job board.

**Architecture:** Pure frontend changes across three files. `index.html` gets a structural overhaul (new header, two-column layout, session chip, CTA). `style.css` gets new utility classes. `app.js` gets session detection on load and updated visibility management for the new layout.

**Tech Stack:** Vanilla HTML/CSS/JS. No build step. Served by FastAPI `StaticFiles(html=True)`. Backend API endpoints used: `GET /session/{token}` (session preloading), `POST /evaluate` (existing, unchanged).

---

## File Map

| File | What changes |
|------|-------------|
| `src/static/index.html` | Header restructure, two-column layout, session chip, job context panel, results CTA |
| `src/static/style.css` | New classes: `.header-inner`, `.cv-back-btn`, `.evaluator-layout`, `.evaluator-left-*`, `.job-context-panel`, `.session-chip`, `.results-cta`, `.btn-browse-jobs`, mobile breakpoint |
| `src/static/app.js` | Move `escHtml` to top, add session preload logic, update visibility management, update `loadJobContext()` |

---

## Task 1: Header + back button

**Files:**
- Modify: `src/static/index.html` (lines 14–19)
- Modify: `src/static/style.css` (append to end)

- [ ] **Step 1: Replace header in `index.html`**

Replace the entire `<header>` block (current lines 14–20):

```html
  <header class="header">
    <div class="header-inner">
      <div>
        <h1>CV Evaluator</h1>
        <p>ATS Resume Analysis</p>
      </div>
      <nav class="header-nav" aria-label="App navigation">
        <a href="jobs.html" class="cv-back-btn">← Job Board</a>
      </nav>
    </div>
  </header>
```

Also update the Google Fonts link in `<head>` to include Space Grotesk (needed for `h1`):

```html
  <link href="https://fonts.googleapis.com/css2?family=Anta&family=Inter:wght@400;500;600&family=Space+Grotesk:wght@700&display=swap" rel="stylesheet">
```

- [ ] **Step 2: Add `.header-inner` and `.cv-back-btn` to `style.css`**

Append to the end of `src/static/style.css`:

```css
/* ── Header inner (shared with jobs.html) ──── */
.header-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-nav {
  display: flex;
  gap: 16px;
}

/* ── CV Evaluator back button ────────────────── */
.cv-back-btn {
  display: inline-block;
  padding: 8px 18px;
  border-radius: 20px;
  background: linear-gradient(to bottom, #7ec2e2 0%, #3f8bae 100%);
  color: #0d1521;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  text-decoration: none;
  white-space: nowrap;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.4);
  transition: filter 0.15s, box-shadow 0.15s;
}

.cv-back-btn:hover {
  filter: brightness(1.1);
  box-shadow: 0 0 16px rgba(102, 192, 244, 0.28), 0 1px 4px rgba(0, 0, 0, 0.4);
}
```

- [ ] **Step 3: Verify visually**

```bash
uvicorn src.main:app --reload
```

Abrir `http://localhost:8000/`. Verificar:
- Header muestra "CV Evaluator" a la izquierda y botón pill azul "← Job Board" a la derecha
- El botón tiene hover con glow

- [ ] **Step 4: Commit**

```bash
git add src/static/index.html src/static/style.css
git commit -m "feat: redesign CV evaluator header with prominent back button"
```

---

## Task 2: Two-column layout + "What you get" panel

**Files:**
- Modify: `src/static/index.html`
- Modify: `src/static/style.css`
- Modify: `src/static/app.js`

- [ ] **Step 1: Restructure `<main>` in `index.html`**

Replace the entire `<main class="container">` block (everything from `<main>` to just before `<script>`):

```html
  <main class="container">

    <!-- Job context panel (shown when ?job_id= in URL) -->
    <div id="job-context-badge" class="job-context-panel hidden"></div>

    <!-- Two-column layout — upload state only -->
    <div class="evaluator-layout">

      <!-- Left: What you get -->
      <div class="evaluator-left">
        <div class="evaluator-left-header">What you get</div>
        <div class="evaluator-left-body">
          <ul class="evaluator-left-list">
            <li class="evaluator-left-item">
              <span class="evaluator-left-item-icon" aria-hidden="true">🎯</span>
              ATS compatibility score from 0 to 100
            </li>
            <li class="evaluator-left-item">
              <span class="evaluator-left-item-icon" aria-hidden="true">🔑</span>
              Keywords found and missing vs the role
            </li>
            <li class="evaluator-left-item">
              <span class="evaluator-left-item-icon" aria-hidden="true">⚠️</span>
              Formatting issues that hurt your ranking
            </li>
            <li class="evaluator-left-item">
              <span class="evaluator-left-item-icon" aria-hidden="true">✅</span>
              Actionable recommendations to improve
            </li>
          </ul>
          <div class="evaluator-left-footer">Powered by Claude AI · PDF and DOCX</div>
        </div>
      </div>

      <!-- Right: Upload form -->
      <div class="evaluator-right">
        <div id="upload-section">
          <!-- Session chip: shown when CV already uploaded in job board -->
          <div id="session-chip" class="session-chip hidden" aria-live="polite">
            <span class="session-chip-icon" aria-hidden="true">📄</span>
            <span id="session-chip-name" class="session-chip-name"></span>
            <button id="session-chip-change" class="session-chip-change">Change file</button>
          </div>

          <div id="drop-zone" class="drop-zone">
            <div class="drop-zone-content">
              <div class="drop-icon" aria-hidden="true">📄</div>
              <p>Drop your CV here</p>
              <p class="secondary-text">PDF or DOCX</p>
              <button id="select-btn" class="btn-primary">Select file</button>
              <p id="file-name" class="file-name hidden" aria-live="polite"></p>
            </div>
            <input type="file" id="file-input" accept=".pdf,.docx" hidden aria-label="Select CV file">
          </div>
          <p id="error-msg" class="error-msg hidden" aria-live="assertive"></p>
          <button id="analyze-btn" class="btn-primary btn-large hidden">Analyze CV</button>
        </div>
      </div>

    </div>

    <!-- Loading (full width, hidden during upload state) -->
    <div id="loading-section" class="hidden">
      <div class="spinner"></div>
      <p class="loading-text">Analyzing your resume, this may take a few seconds...</p>
    </div>

    <!-- Results dashboard (full width, hidden during upload state) -->
    <div id="results-section" class="hidden">

      <div class="results-header">
        <button id="reset-btn" class="btn-reset">← Analyze another CV</button>
      </div>

      <div class="panel panel-score">
        <div class="score-left">
          <div id="score-circle" class="score-circle">
            <span id="score-value"></span>
          </div>
        </div>
        <div class="score-right">
          <h2 id="candidate-name"></h2>
          <span id="verdict-badge" class="badge"></span>
        </div>
      </div>

      <div class="panel">
        <h3>Summary <button class="copy-btn" data-copy-target="summary-text" aria-label="Copy summary">copy</button></h3>
        <p id="summary-text"></p>
      </div>

      <div class="panel">
        <h3>Found Keywords <button class="copy-btn" data-copy-target="keywords-found" aria-label="Copy found keywords">copy</button></h3>
        <div id="keywords-found" class="tag-cloud"></div>
      </div>

      <div class="panel">
        <h3>Missing Keywords <button class="copy-btn" data-copy-target="keywords-missing" aria-label="Copy missing keywords">copy</button></h3>
        <div id="keywords-missing" class="tag-cloud"></div>
      </div>

      <div class="panel">
        <h3>Formatting Issues <button class="copy-btn" data-copy-target="formatting-issues" aria-label="Copy formatting issues">copy</button></h3>
        <ul id="formatting-issues" class="issue-list"></ul>
      </div>

      <div class="panel">
        <h3>Recommendations <button class="copy-btn" data-copy-target="recommendations" aria-label="Copy recommendations">copy</button></h3>
        <ol id="recommendations" class="recommendations-list"></ol>
      </div>

      <!-- CTA: back to job board -->
      <div class="results-cta">
        <p class="results-cta-text">Ready to apply? Browse roles that match your profile.</p>
        <a href="jobs.html" class="btn-browse-jobs">Browse matching jobs →</a>
      </div>

    </div>
  </main>
```

- [ ] **Step 2: Add layout styles to `style.css`**

Append to `src/static/style.css`:

```css
/* ── Two-column evaluator layout ─────────────── */
.evaluator-layout {
  display: grid;
  grid-template-columns: 2fr 3fr;
  gap: 24px;
  align-items: start;
}

.evaluator-left {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-top-color: rgba(102, 192, 244, 0.2);
  border-radius: 3px;
  overflow: hidden;
  box-shadow: var(--shadow-panel);
}

.evaluator-left-header {
  background: rgba(0, 0, 0, 0.22);
  border-bottom: 1px solid rgba(76, 107, 138, 0.38);
  padding: 9px 12px 9px 24px;
  font-family: 'Anta', Arial, sans-serif;
  font-size: 11px;
  font-weight: 400;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.13em;
  position: relative;
}

.evaluator-left-header::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--accent-blue);
  opacity: 0.5;
}

.evaluator-left-body {
  padding: 20px 24px;
}

.evaluator-left-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.evaluator-left-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.45;
}

.evaluator-left-item-icon {
  font-size: 14px;
  flex-shrink: 0;
  margin-top: 1px;
}

.evaluator-left-footer {
  margin-top: 20px;
  padding-top: 14px;
  border-top: 1px solid rgba(76, 107, 138, 0.3);
  font-size: 11px;
  color: var(--text-secondary);
  letter-spacing: 0.04em;
}

.evaluator-right {
  /* inherits full width of its grid column */
}
```

- [ ] **Step 3: Update visibility management in `app.js`**

Add a reference to `evaluatorLayout` near the top of `app.js`, after the existing element refs:

```js
const evaluatorLayout = document.querySelector('.evaluator-layout');
```

Replace the `setLoading` function:

```js
function setLoading(active) {
  if (active) {
    evaluatorLayout.classList.add('hidden');
    loadingSection.classList.remove('hidden');
    setLoadingMessage('Analyzing your resume, this may take a few seconds...');
  } else {
    loadingSection.classList.add('hidden');
    evaluatorLayout.classList.remove('hidden');
  }
}
```

Replace the `showResults` function:

```js
function showResults() {
  loadingSection.classList.add('hidden');
  evaluatorLayout.classList.add('hidden');
  resultsSection.classList.remove('hidden');
}
```

Replace the `resetBtn` click handler:

```js
resetBtn.addEventListener('click', () => {
  selectedFile      = null;
  fileInput.value   = '';
  fileNameEl.classList.add('hidden');
  analyzeBtn.classList.add('hidden');
  hideError();
  resultsSection.classList.add('hidden');
  evaluatorLayout.classList.remove('hidden');
});
```

- [ ] **Step 4: Verify visually**

```bash
uvicorn src.main:app --reload
```

Abrir `http://localhost:8000/`. Verificar:
- Dos columnas: izquierda con "What you get", derecha con el dropzone
- El loading spinner oculta el layout y se muestra centrado
- Los resultados también se muestran a full width
- El botón reset vuelve a mostrar el layout de dos columnas

- [ ] **Step 5: Commit**

```bash
git add src/static/index.html src/static/style.css src/static/app.js
git commit -m "feat: add two-column layout with What You Get panel to CV evaluator"
```

---

## Task 3: Job context panel

**Files:**
- Modify: `src/static/style.css`
- Modify: `src/static/app.js`

El `#job-context-badge` ya está en el HTML desde Task 2 con la clase `job-context-panel`. Solo falta el CSS y actualizar el JS para llenar ese panel con estructura HTML en vez de texto plano.

- [ ] **Step 1: Add `.job-context-panel` styles to `style.css`**

Append to `src/static/style.css`:

```css
/* ── Job context panel ───────────────────────── */
.job-context-panel {
  margin-bottom: 20px;
  padding: 12px 20px;
  background: rgba(102, 192, 244, 0.06);
  border: 1px solid rgba(102, 192, 244, 0.25);
  border-left: 3px solid var(--accent-blue);
  border-radius: 3px;
}

.job-context-label {
  display: block;
  font-size: 10px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-bottom: 4px;
}

.job-context-title {
  display: block;
  font-size: 15px;
  font-weight: 600;
  color: var(--accent-blue);
  line-height: 1.3;
}

.job-context-company {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}
```

- [ ] **Step 2: Move `escHtml` to top of `app.js` and update `loadJobContext`**

`escHtml` is currently defined at line ~189 (inside renderResults area), but `loadJobContext` runs at load time and needs it. Move the function to the very top of the file, before any other code:

```js
function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
```

Then remove the duplicate `escHtml` definition that was previously inside `renderResults`.

Update `loadJobContext` to fill the panel with structured HTML instead of plain text:

```js
async function loadJobContext() {
  if (!contextJobId) return;
  try {
    const res = await fetch(`${BACKEND_URL}/jobs`);
    if (!res.ok) return;
    const jobs = await res.json();
    const job = jobs.find(j => String(j.id) === String(contextJobId));
    if (!job) return;
    contextJobData = job;
    const panel = document.getElementById('job-context-badge');
    if (panel) {
      panel.innerHTML = `
        <span class="job-context-label">Evaluating against</span>
        <span class="job-context-title">${escHtml(job.title)}</span>
        <span class="job-context-company">${escHtml(job.company)}</span>
      `;
      panel.classList.remove('hidden');
    }
  } catch { /* silently ignore */ }
}
```

- [ ] **Step 3: Verify visually**

```bash
uvicorn src.main:app --reload
```

Necesitás un `job_id` real. Obtenerlo: abrir `http://localhost:8000/jobs` en el browser, copiar el `id` de cualquier job.

Abrir `http://localhost:8000/?job_id=<id_copiado>`. Verificar:
- Panel azul aparece arriba del layout con "EVALUATING AGAINST", el título del job en azul, y la empresa abajo
- Sin `?job_id`, no aparece nada (hidden)

- [ ] **Step 4: Commit**

```bash
git add src/static/style.css src/static/app.js
git commit -m "feat: replace job context badge with prominent panel in CV evaluator"
```

---

## Task 4: Session preloading

**Files:**
- Modify: `src/static/style.css`
- Modify: `src/static/app.js`

El `#session-chip` ya está en el HTML desde Task 2. Esta tarea agrega el CSS y la lógica JS.

- [ ] **Step 1: Add `.session-chip` styles to `style.css`**

Append to `src/static/style.css`:

```css
/* ── Session preload chip ────────────────────── */
.session-chip {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: var(--accent-blue-alpha);
  border: 1px solid rgba(102, 192, 244, 0.3);
  border-radius: 3px;
  margin-bottom: 12px;
}

.session-chip-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.session-chip-name {
  flex: 1;
  font-size: 13px;
  color: var(--accent-blue);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-chip-change {
  background: transparent;
  border: 1px solid rgba(76, 107, 138, 0.5);
  color: var(--text-secondary);
  font-family: 'Inter', Arial, sans-serif;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  padding: 4px 10px;
  border-radius: 2px;
  cursor: pointer;
  flex-shrink: 0;
  transition: color 0.15s, border-color 0.15s;
}

.session-chip-change:hover {
  color: var(--text-primary);
  border-color: rgba(76, 107, 138, 0.85);
}
```

- [ ] **Step 2: Add session preload variables and refs to `app.js`**

Add after the existing element refs block (after `const resetBtn = ...`):

```js
const sessionChip       = document.getElementById('session-chip');
const sessionChipName   = document.getElementById('session-chip-name');
const sessionChipChange = document.getElementById('session-chip-change');

let sessionPreloaded = false;
```

- [ ] **Step 3: Add `checkExistingSession` function to `app.js`**

Add after `loadJobContext()` definition, before `loadJobContext()` is called:

```js
async function checkExistingSession() {
  const token = localStorage.getItem('cv_session_token');
  if (!token) return;
  try {
    const res = await fetch(`${BACKEND_URL}/session/${encodeURIComponent(token)}`);
    if (!res.ok) {
      // Session expired or invalid — clean up localStorage
      localStorage.removeItem('cv_session_token');
      return;
    }
    const data = await res.json();
    // Show preloaded state
    sessionPreloaded = true;
    sessionChipName.textContent = data.filename;
    sessionChip.classList.remove('hidden');
    dropZone.classList.add('hidden');
    analyzeBtn.classList.remove('hidden');
  } catch {
    // Server unreachable — degrade gracefully, show normal dropzone
  }
}
```

- [ ] **Step 4: Call `checkExistingSession` at bottom of `app.js`**

At the very bottom of `app.js`, after `loadJobContext()` is called, add:

```js
checkExistingSession();
```

- [ ] **Step 5: Update `analyzeBtn` click handler to support preloaded session**

The current guard at the top of the handler is `if (!selectedFile) return;`. Replace that line:

```js
analyzeBtn.addEventListener('click', async () => {
  if (!selectedFile && !sessionPreloaded) return;
```

Later in the same handler, the FormData construction currently always appends the file. Replace:

```js
  const formData = new FormData();
  if (selectedFile) {
    formData.append('file', selectedFile);
  }
  if (contextJobId) formData.append('job_id', contextJobId);
```

- [ ] **Step 6: Add `sessionChipChange` click handler**

Add after the `resetBtn` click handler:

```js
sessionChipChange.addEventListener('click', () => {
  sessionPreloaded = false;
  sessionChip.classList.add('hidden');
  dropZone.classList.remove('hidden');
  analyzeBtn.classList.add('hidden');
  selectedFile = null;
  fileInput.value = '';
  fileNameEl.classList.add('hidden');
  hideError();
});
```

- [ ] **Step 7: Verify visually**

```bash
uvicorn src.main:app --reload
```

**Test A — sin sesión:**
Abrir `http://localhost:8000/` en ventana incógnita (sin token en localStorage). Verificar que el dropzone normal aparece.

**Test B — con sesión activa:**
1. Ir a `http://localhost:8000/jobs.html`
2. Subir un CV (aparece el chip con el nombre del archivo en el banner)
3. Abrir `http://localhost:8000/`
4. Verificar que el chip muestra el nombre del CV y el botón "Analyze CV" ya está visible sin necesidad de re-subir
5. Hacer clic en "Change file" → chip desaparece, dropzone vuelve a aparecer

**Test C — token expirado:**
1. Poner manualmente en localStorage `cv_session_token = "token-falso"` desde DevTools
2. Recargar `http://localhost:8000/`
3. Verificar que el token inválido se limpia y aparece el dropzone normal

- [ ] **Step 8: Commit**

```bash
git add src/static/style.css src/static/app.js
git commit -m "feat: detect active CV session on load — skip re-upload if already done"
```

---

## Task 5: Results CTA + mobile breakpoint

**Files:**
- Modify: `src/static/style.css`

El `.results-cta` ya está en el HTML desde Task 2. Solo falta el CSS y el breakpoint mobile.

- [ ] **Step 1: Add `.results-cta` and mobile styles to `style.css`**

Append to `src/static/style.css`:

```css
/* ── Results CTA ─────────────────────────────── */
.results-cta {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-top-color: rgba(102, 192, 244, 0.2);
  border-radius: 3px;
  padding: 24px;
  text-align: center;
  box-shadow: var(--shadow-panel);
  animation: slideUp 0.38s cubic-bezier(0.22, 1, 0.36, 1) both;
  animation-delay: 0.42s;
}

.results-cta-text {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 14px;
}

.btn-browse-jobs {
  display: inline-block;
  padding: 10px 28px;
  border-radius: 20px;
  background: linear-gradient(to bottom, #7ec2e2 0%, #3f8bae 100%);
  color: #0d1521;
  font-family: 'Inter', Arial, sans-serif;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  text-decoration: none;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.4);
  transition: filter 0.15s, box-shadow 0.15s;
}

.btn-browse-jobs:hover {
  filter: brightness(1.1);
  box-shadow: 0 0 16px rgba(102, 192, 244, 0.28), 0 1px 4px rgba(0, 0, 0, 0.4);
}

/* ── Mobile breakpoint ───────────────────────── */
@media (max-width: 640px) {
  .evaluator-layout {
    grid-template-columns: 1fr;
  }

  .evaluator-left-body {
    padding: 16px;
  }
}
```

- [ ] **Step 2: Verify visually**

```bash
uvicorn src.main:app --reload
```

**Test resultados:**
1. Subir un CV y hacer clic en "Analyze CV"
2. Verificar que al final de los resultados aparece el panel con "Ready to apply?" y el botón "Browse matching jobs →"
3. Hacer clic en el botón → debe navegar a `jobs.html`

**Test mobile:**
1. Abrir DevTools → activar mobile emulation (< 640px de ancho)
2. Verificar que el layout colapsa a una columna: "What you get" arriba, dropzone abajo

- [ ] **Step 3: Commit**

```bash
git add src/static/style.css
git commit -m "feat: add results CTA and mobile responsive layout to CV evaluator"
```

---

## Self-review

**Spec coverage:**
- ✅ Header + back button prominente → Task 1
- ✅ Two-column layout con "What you get" → Task 2
- ✅ Job context panel visible → Task 3
- ✅ Session preloading — no re-upload → Task 4
- ✅ Results CTA back to job board → Task 5
- ✅ Mobile breakpoint → Task 5
- ✅ Dark theme + paleta azules/cyan mantenida en todos los estilos

**No placeholders:** revisado — todos los pasos tienen código completo.

**Type consistency:** `evaluatorLayout`, `sessionChip`, `sessionChipName`, `sessionChipChange`, `sessionPreloaded` usados consistentemente en Tasks 2 y 4. `escHtml` movida al top en Task 3 antes de ser usada.

**Scope:** un solo subsistema (frontend CV Evaluator). No se toca el backend.
