# CV Evaluator Frontend — Design Spec
**Date:** 2026-03-26

## Context

The CV Evaluator backend is a FastAPI + LangChain app that evaluates resumes for ATS compatibility via `POST /evaluate`. Currently it has no frontend. The goal is to add a static HTML/CSS/JS page served directly by FastAPI so users can upload a PDF or DOCX file and see the evaluation results without needing a separate frontend server.

## Visual Design

**Aesthetic:** Steam-inspired dark UI.

| Token | Value |
|---|---|
| Main background | `#1b2838` |
| Panel background | `#16202d` |
| Secondary panel | `#2a475e` |
| Border | `#4c6b8a` |
| Text primary | `#c6d4df` |
| Text secondary | `#8f98a0` |
| Accent blue | `#66c0f4` |
| Success green | `#57cbde` |
| Danger red | `#e74c3c` |

Typography: system-safe sans-serif stack (`"Motiva Sans", Arial, sans-serif`), dense and technical feel.

## File Structure

```
src/
  static/
    index.html   # single page, references style.css and app.js
    style.css    # all styles
    app.js       # fetch logic, drag & drop, DOM rendering
```

`main.py` mounts `src/static/` as `StaticFiles` at `/`, serving `index.html` by default.

## Page Layout

### Header
Steam-style dark header bar with app title "CV Evaluator" and subtitle "Analizá tu CV con IA".

### Upload Zone
- Large drag & drop area with dashed border
- Accepts `.pdf` and `.docx` only (validated client-side by extension, server handles real validation)
- Fallback "Seleccionar archivo" button inside the zone
- Shows filename once a file is selected

### Loading State
- Upload zone and button disabled
- Spinner (CSS animation) centered on screen
- Text: "Analizando CV..."

### Results Dashboard (hidden until results arrive)
Six panels rendered after a successful API response:

1. **Score + Verdict** — two-column: circular/numeric score on the left (large, colored by value), candidate name + APROBADO/RECHAZADO badge on the right
2. **Resumen** — full-width text block with the `summary` field
3. **Keywords Encontradas** — tag cloud, accent blue tags
4. **Keywords Faltantes** — tag cloud, red/muted tags
5. **Problemas de Formato** — list with warning icon prefix per item
6. **Recomendaciones** — numbered list

All panels appear with a CSS fade-in animation.

A "Analizar otro CV" button resets the page back to the upload state.

## API Integration

- `POST /evaluate` with `FormData` containing the file
- On success (200): render results dashboard
- On error (400/422/429/500): show an inline error message in Steam-red below the upload zone, keep the form active
- Timeout: none set (Claude calls can take 10-15s, browser default is fine)

## FastAPI Changes

In `main.py`:
- Import `StaticFiles` from `starlette.staticfiles`
- Mount: `app.mount("/", StaticFiles(directory="src/static", html=True), name="static")`
- This must be added **after** `app.include_router(router)` so API routes take priority

## Out of Scope

- Authentication
- History of past evaluations
- Mobile responsiveness (desktop-first)
- Dark/light toggle
