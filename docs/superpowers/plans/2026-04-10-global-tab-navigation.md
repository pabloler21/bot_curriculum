# Global Tab Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agregar una banda de tabs sticky ("ATS Evaluator" / "Job Board") dentro del header en las tres páginas HTML, reemplazando los links de navegación sueltos que hay hoy.

**Architecture:** Cambio puro de HTML + CSS. Sin JS, sin backend. El header existente pasa a `position: sticky` y se le agrega un `.tab-strip` debajo del `.header-inner`. Cada página marca su tab activa con la clase `active`. Los estilos de nav que ya no se usan (`.cv-back-btn`, `.header-nav`, `.nav-link`) se eliminan de `style.css` y `jobs.css`.

**Tech Stack:** HTML5, CSS3 vanilla. Sin build step. FastAPI sirve los estáticos desde `src/static/`.

---

## File Map

| Archivo | Qué cambia |
|---------|-----------|
| `src/static/style.css` | `.header` → sticky; agrega `.tab-strip` + `.tab-strip-item`; elimina `.cv-back-btn`, `.header-nav` |
| `src/static/jobs.css` | Elimina `.header-nav`, `.nav-link` (ya no se usan) |
| `src/static/index.html` | Reemplaza `<nav class="header-nav">` con `.tab-strip` (ATS Evaluator activa) |
| `src/static/jobs.html` | Reemplaza `<nav class="header-nav">` con `.tab-strip` (Job Board activa) |
| `src/static/job-detail.html` | Reemplaza `<nav class="header-nav">` con `.tab-strip` (Job Board activa) |

---

## Task 1: Feature branch

- [ ] **Step 1: Crear rama desde develop**

```bash
git checkout develop
git pull origin develop
git checkout -b feature/phase-8-global-tab-nav
```

---

## Task 2: CSS — header sticky + tab strip

**Files:**
- Modify: `src/static/style.css`

- [ ] **Step 1: Hacer el header sticky**

En `style.css`, reemplazar el bloque `.header` (líneas 38–43):

```css
/* ANTES */
.header {
  background: linear-gradient(180deg, var(--bg-deep) 0%, #192538 100%);
  border-bottom: 1px solid rgba(76, 107, 138, 0.55);
  padding: 22px 40px;
  position: relative;
}
```

```css
/* DESPUÉS */
.header {
  background: linear-gradient(180deg, var(--bg-deep) 0%, #192538 100%);
  border-bottom: 1px solid rgba(76, 107, 138, 0.55);
  padding: 22px 40px 0;
  position: sticky;
  top: 0;
  z-index: 100;
}
```

- [ ] **Step 2: Eliminar `.header-nav` de style.css**

Eliminar estas líneas de `style.css` (cerca de la línea 575):

```css
.header-nav {
  display: flex;
  gap: 16px;
}
```

- [ ] **Step 3: Eliminar `.cv-back-btn` de style.css**

Eliminar el bloque completo (líneas 580–600):

```css
/* ── CV Evaluator back button ─────────────── */
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

- [ ] **Step 4: Agregar estilos `.tab-strip` a style.css**

Agregar después del bloque `/* ── Header inner ── */` (después de la línea que cierra `.header-inner`):

```css
/* ── Tab strip ───────────────────────────── */
.tab-strip {
  display: flex;
  margin-top: 12px;
}

.tab-strip-item {
  padding: 8px 20px 7px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  font-family: 'Inter', Arial, sans-serif;
  text-decoration: none;
  color: var(--text-secondary);
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: color 0.15s, border-color 0.15s;
}

.tab-strip-item.active {
  color: var(--accent-blue);
  border-bottom-color: var(--accent-blue);
}

.tab-strip-item:hover:not(.active) {
  color: var(--text-primary);
}
```

- [ ] **Step 5: Commit**

```bash
git add src/static/style.css
git commit -m "feat: make header sticky and add tab-strip styles"
```

---

## Task 3: CSS cleanup en jobs.css

**Files:**
- Modify: `src/static/jobs.css`

- [ ] **Step 1: Eliminar `.header-nav` y `.nav-link` de jobs.css**

Eliminar estas líneas de `jobs.css` (líneas 8–31):

```css
.header-nav {
  display: flex;
  gap: 16px;
}

.nav-link {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  text-decoration: none;
  padding: 5px 10px;
  border: 1px solid rgba(76, 107, 138, 0.45);
  border-radius: 20px;
  transition: color 0.15s, border-color 0.15s;
}

.nav-link:hover,
.nav-link:focus-visible {
  color: var(--accent-blue);
  border-color: rgba(102, 192, 244, 0.38);
  outline: none;
}
```

- [ ] **Step 2: Commit**

```bash
git add src/static/jobs.css
git commit -m "chore: remove unused nav-link and header-nav styles from jobs.css"
```

---

## Task 4: index.html — tab strip con ATS Evaluator activa

**Files:**
- Modify: `src/static/index.html`

- [ ] **Step 1: Reemplazar el header**

Reemplazar el bloque `<header>` completo (líneas 14–24):

```html
<!-- ANTES -->
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

```html
<!-- DESPUÉS -->
  <header class="header">
    <div class="header-inner">
      <div>
        <h1>CV Evaluator</h1>
        <p>ATS Resume Analysis</p>
      </div>
    </div>
    <div class="tab-strip" role="tablist" aria-label="App sections">
      <a href="index.html" class="tab-strip-item active" role="tab" aria-selected="true">ATS Evaluator</a>
      <a href="jobs.html" class="tab-strip-item" role="tab" aria-selected="false">Job Board</a>
    </div>
  </header>
```

- [ ] **Step 2: Verificar visualmente**

```bash
uvicorn src.main:app --reload
```

Abrir `http://localhost:8000/`. Verificar:
- Header muestra los dos tabs, "ATS Evaluator" en azul con línea inferior
- El header queda fijo al hacer scroll
- No hay botón pill ni links sueltos

- [ ] **Step 3: Commit**

```bash
git add src/static/index.html
git commit -m "feat: replace nav pill with sticky tab strip on index.html"
```

---

## Task 5: jobs.html — tab strip con Job Board activa

**Files:**
- Modify: `src/static/jobs.html`

- [ ] **Step 1: Reemplazar el header**

Reemplazar el bloque `<header>` completo (líneas 15–25):

```html
<!-- ANTES -->
  <header class="header">
    <div class="header-inner">
      <div>
        <h1>CV Evaluator</h1>
        <p>Remote Tech Job Board</p>
      </div>
      <nav class="header-nav" aria-label="App navigation">
        <a href="index.html" class="nav-link">ATS Evaluator</a>
      </nav>
    </div>
  </header>
```

```html
<!-- DESPUÉS -->
  <header class="header">
    <div class="header-inner">
      <div>
        <h1>CV Evaluator</h1>
        <p>Remote Tech Job Board</p>
      </div>
    </div>
    <div class="tab-strip" role="tablist" aria-label="App sections">
      <a href="index.html" class="tab-strip-item" role="tab" aria-selected="false">ATS Evaluator</a>
      <a href="jobs.html" class="tab-strip-item active" role="tab" aria-selected="true">Job Board</a>
    </div>
  </header>
```

- [ ] **Step 2: Verificar visualmente**

Abrir `http://localhost:8000/jobs.html`. Verificar:
- "Job Board" tab activa en azul, "ATS Evaluator" en gris
- El cv-banner sigue apareciendo debajo del header sticky y scrollea con el contenido
- La grilla de jobs carga correctamente

- [ ] **Step 3: Commit**

```bash
git add src/static/jobs.html
git commit -m "feat: replace nav link with sticky tab strip on jobs.html"
```

---

## Task 6: job-detail.html — tab strip con Job Board activa

**Files:**
- Modify: `src/static/job-detail.html`

- [ ] **Step 1: Reemplazar el header**

Reemplazar el bloque `<header>` completo (líneas 15–26):

```html
<!-- ANTES -->
  <header class="header">
    <div class="header-inner">
      <div>
        <h1>CV Evaluator</h1>
        <p>Remote Tech Job Board</p>
      </div>
      <nav class="header-nav" aria-label="App navigation">
        <a href="jobs.html" class="nav-link">← Back to jobs</a>
        <a href="index.html" class="nav-link">ATS Evaluator</a>
      </nav>
    </div>
  </header>
```

```html
<!-- DESPUÉS -->
  <header class="header">
    <div class="header-inner">
      <div>
        <h1>CV Evaluator</h1>
        <p>Remote Tech Job Board</p>
      </div>
    </div>
    <div class="tab-strip" role="tablist" aria-label="App sections">
      <a href="index.html" class="tab-strip-item" role="tab" aria-selected="false">ATS Evaluator</a>
      <a href="jobs.html" class="tab-strip-item active" role="tab" aria-selected="true">Job Board</a>
    </div>
  </header>
```

- [ ] **Step 2: Verificar visualmente**

Abrir `http://localhost:8000/jobs.html`, hacer click en cualquier oferta. Verificar:
- Tab "Job Board" activa en la página de detalle (indica contexto: sub-página del board)
- Los tabs navegan correctamente a sus páginas respectivas
- El header sticky funciona al scrollear el detalle largo de una oferta

- [ ] **Step 3: Commit**

```bash
git add src/static/job-detail.html
git commit -m "feat: replace nav links with sticky tab strip on job-detail.html"
```

---

## Task 7: Verificación final cross-page

- [ ] **Step 1: Navegación completa**

Con el servidor corriendo (`uvicorn src.main:app --reload`):

1. `http://localhost:8000/` → tab "ATS Evaluator" azul ✓
2. Click en "Job Board" → navega a jobs.html, tab "Job Board" azul ✓
3. Click en cualquier oferta → job-detail.html, tab "Job Board" azul ✓
4. Click en "ATS Evaluator" desde job-detail → vuelve a index.html, tab "ATS Evaluator" azul ✓

- [ ] **Step 2: Verificar sticky en scroll**

En jobs.html: hacer scroll hasta el fondo de la grilla → el header con los tabs permanece visible arriba.

- [ ] **Step 3: Correr tests para confirmar que nada del backend se rompió**

```bash
pytest tests/ -v
```

Resultado esperado: 55 passed.

- [ ] **Step 4: Push y PR a develop**

```bash
git push -u origin feature/phase-8-global-tab-nav
```

Crear PR de `feature/phase-8-global-tab-nav` → `develop`.
