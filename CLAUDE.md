# CLAUDE.md — bot-curriculum

## Proyecto
CV Evaluator: app web que analiza CVs y evalúa su compatibilidad ATS usando Claude AI.

## Stack
- **Runtime**: Python 3.13, `uv` como package manager
- **Backend**: FastAPI + uvicorn, rate limiting con slowapi (3/min por IP)
- **AI**: LangChain + `claude-haiku-4-5` con structured output (`ResumeEvaluation` pydantic model)
- **Extracción de texto**: liteparse (PDF/DOCX)
- **Frontend**: HTML/JS/CSS estático servido por FastAPI desde `src/static/`
- **Linter**: ruff (`ruff.toml`)
- **Deploy**: Render.com (`render.yaml`)

## Estructura
```
src/
  main.py          # FastAPI app, CORS, static files, rate limiter
  router.py        # agrega routers
  routes/
    evaluate.py    # POST /evaluate — recibe archivo, extrae texto, llama evaluate_cv()
    health.py      # GET /health
  static/          # index.html, app.js, style.css
backend/
  evaluator.py     # chain LangChain → Claude (structured output ResumeEvaluation)
  extractor.py     # extract_text() via liteparse (escribe tmp file, parsea, borra)
  prompts/
    ats_skill.md   # prompt de evaluación ATS inyectado al system message
```

## Variables de entorno
- `ANTHROPIC_API_KEY` — requerida
- `FRONTEND_BASE_URL` — para CORS (default: `http://localhost:3000`)

## Comandos
```bash
# Instalar dependencias
pip install -e .

# Correr localmente
uvicorn src.main:app --reload

# Lint
ruff check src/ backend/
```

## Convenciones
- Imports absolutos desde `src.*` y `backend.*`
- Logging con `logging.getLogger(__name__)` en cada módulo
- Errores HTTP se levantan como `HTTPException` en las routes
- El modelo pydantic `ResumeEvaluation` define el contrato de respuesta de la API
