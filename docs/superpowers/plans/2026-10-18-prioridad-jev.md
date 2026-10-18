# 4.21 — Prioridad con Jev: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que `/evaluate` devuelva keywords faltantes y recomendaciones ordenadas por prioridad (decidida por Jev) y que el evaluator muestre el nivel de cada una con barras de señal en gris.

**Architecture:** Haiku agrega `target_role` a la evaluación. Un módulo nuevo, `backend/prioritizer.py`, hace una sola llamada a Jev con una pregunta `Score` por ítem, ordena las dos listas y agrega dos listas paralelas de niveles. `/evaluate` lo llama entre `evaluate_cv` y `save_evaluation`. El frontend dibuja las barras si las listas de niveles existen y coinciden en largo; si no, muestra las listas neutras.

**Tech Stack:** Python 3.13 + FastAPI, `typesafe-sdk` (Jev), LangChain + Haiku 5.5, JS/CSS vanilla.

**Spec:** `docs/superpowers/specs/2026-10-18-prioridad-jev-design.md`

## Global Constraints

- TDD estricto en backend: test que falla → commit `test(...)` → implementación → commit `feat/fix(...)`. Un cambio lógico por commit. Todo commit termina con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Rama `feature/task-4-21-prioridad-jev` (ya creada, sale de la 4.20).
- Dependencia nueva solo con `uv add typesafe-sdk`, para que entre en `pyproject.toml` y `uv.lock` (el VPS corre `uv run --frozen`).
- Clave: `TYPESAFE_API_KEY`. Modelo: el default del SDK (`jev-latest`). Timeout de Jev: `5.0` s.
- El CV **nunca** va al state de Jev. Keys del state: exactamente `target_role`, `job_description`, `missing_keywords`, `recommendations`.
- Niveles: `"essential"` si score `>= 1.5`, `"important"` si `>= 0.5`, si no `"optional"`. Orden por score descendente, estable.
- Campos nuevos de la respuesta: `keywords_missing_priority` y `recommendations_priority` (`list[str]`, mismo largo que su lista). `keywords_missing` y `recommendations` siguen siendo `list[str]`.
- Si Jev falla o no hay key: la evaluación sale sin los campos de prioridad, nunca un 500.
- Visual: sin color (el coral es solo de los botones pagos). Etiquetas: fondo `rgba(255,255,255,0.05)`, borde `rgba(255,255,255,0.14)`, texto `var(--text-secondary)`; imprescindibles con `var(--text-primary)`. Barras: 3 px de ancho, 3/6/9 px de alto, gap 2 px, encendida `rgba(255,255,255,0.80)`, apagada `rgba(255,255,255,0.16)`.
- El panel "What to fix" mide **571 px** y la columna izquierda **653 px** en 1920×945 con la evaluación de ejemplo, igual que hoy. Se ven las 14 keywords y 5 recomendaciones + "Show all".
- Nombres de nivel: EN "Essential / Important / Nice to have"; ES "Imprescindible / Importante / Opcional".
- Todo dato de la API pasa por `esc()` antes de tocar el DOM. Parchear en el lugar de importación (`src.routes.evaluate.prioritize`).

## Review Focus

- Jev responde sin alguna de las preguntas (falta una key en el resultado): la evaluación tiene que salir sin prioridades, no con un `KeyError` → test en Task 2.
- Haiku repite una keyword: el orden se calcula por índice, así que las dos copias conservan cada una su nivel → test en Task 2.
- Un usuario con sesión abre el evaluator con una evaluación guardada antes de este cambio (sin `target_role` ni prioridades): ve las listas neutras, sin barras ni leyenda, y nada en rojo → verificación en navegador en Task 4.
- Una lista de prioridad con un largo distinto al de su lista (dato corrupto o mezcla de versiones): esa lista se muestra sin barras → verificación en navegador en Task 4.
- Jev tarda más de 5 s: la evaluación sale igual, sin prioridades → test en Task 2 (`TypeSafeAPITimeoutError`).

---

### Task 1: Haiku devuelve el puesto objetivo

**Files:**
- Modify: `backend/evaluator.py` (`ResumeEvaluation` y el texto de RESPONSE FORMAT del prompt)
- Test: `tests/test_evaluate.py`

**Interfaces:**
- Produces: la evaluación (`dict`) trae `target_role: str`.

- [ ] **Step 1: Test que falla**

```python
def test_resume_evaluation_has_target_role():
    assert "target_role" in ResumeEvaluation.model_fields
```

- [ ] **Step 2:** `uv run pytest tests/test_evaluate.py::test_resume_evaluation_has_target_role -q` → FAIL.
- [ ] **Step 3:** Commit `test(evaluator): la evaluación trae el puesto al que apunta el CV`.
- [ ] **Step 4:** En `ResumeEvaluation`, después de `candidate_name`: `target_role: str = Field(description="The job title this resume targets, inferred from the resume, e.g. 'Data Analyst'")`. En RESPONSE FORMAT, agregar "target role" a la lista de campos.
- [ ] **Step 5:** `uv run pytest tests/test_evaluate.py -q` → PASS.
- [ ] **Step 6:** Commit `feat(evaluator): Haiku devuelve target_role`.

### Task 2: `backend/prioritizer.py`

**Files:**
- Create: `backend/prioritizer.py`
- Create: `tests/test_prioritizer.py`
- Modify: `tests/conftest.py` (fixture autouse), `pyproject.toml` + `uv.lock` (vía `uv add`)

**Interfaces:**
- Consumes: la evaluación de Task 1 (`target_role`, `keywords_missing`, `recommendations`).
- Produces:
  - `KEYWORD_LEVELS: list[str]`, `RECOMMENDATION_LEVELS: list[str]` — los 3 criterios de cada tipo, de menor a mayor, copiados textuales del spec.
  - `level_for(score: float) -> str`
  - `rank(items: list[str], scores: list[float]) -> tuple[list[str], list[str]]` — ítems ordenados y sus niveles.
  - `build_questions(n_keywords: int, n_recommendations: int) -> dict[str, Score]` — ids `kw_{i}` y `rec_{i}`.
  - `async _ask_jev(state: dict, questions: dict[str, Score]) -> dict[str, float]` — única función que toca el SDK.
  - `async prioritize(evaluation: dict, job_context: str | None = None) -> dict` — devuelve una copia con las listas ordenadas y `keywords_missing_priority` / `recommendations_priority`; sin cambios si no hay key, si las dos listas están vacías o si Jev falla.

- [ ] **Step 1:** `uv add typesafe-sdk` (0.7.5 era la última el 2026-10-14). En `tests/conftest.py`, fixture autouse que haga `monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)`: sin eso, con la key en el `.env` la suite le pegaría a Jev de verdad. Commit `chore: typesafe-sdk como dependencia; los tests nunca llaman a Jev`.

- [ ] **Step 2: Tests de niveles y orden (fallan)**

```python
def test_level_thresholds():
    assert [level_for(s) for s in (2.0, 1.5, 1.49, 0.5, 0.49, 0.0)] == [
        "essential", "essential", "important", "important", "optional", "optional"]

def test_rank_orders_by_score_and_keeps_ties_stable():
    items, levels = rank(["a", "b", "c", "d"], [0.2, 1.8, 0.2, 1.0])
    assert items == ["b", "d", "a", "c"]
    assert levels == ["essential", "important", "optional", "optional"]

def test_rank_keeps_duplicates_paired_with_their_scores():
    items, levels = rank(["SQL", "Excel", "SQL"], [0.1, 1.0, 1.9])
    assert items == ["SQL", "Excel", "SQL"] and levels == ["essential", "important", "optional"]
```

- [ ] **Step 3:** `uv run pytest tests/test_prioritizer.py -q` → FAIL (no existe el módulo). Commit `test(prioritizer): niveles por umbral y orden estable por score`.
- [ ] **Step 4:** Implementar `level_for` y `rank` (ordenar índices por score descendente con `sorted`, que es estable). Tests → PASS. Commit `feat(prioritizer): niveles y orden por score`.

- [ ] **Step 5: Tests de las preguntas (fallan)**

```python
def test_build_questions_one_score_per_item():
    qs = build_questions(2, 3)
    assert sorted(qs) == ["kw_0", "kw_1", "rec_0", "rec_1", "rec_2"]
    assert "`missing_keywords[1]`" in qs["kw_1"].instructions
    assert "`recommendations[2]`" in qs["rec_2"].instructions
    assert list(qs["kw_0"].criteria) == KEYWORD_LEVELS and len(KEYWORD_LEVELS) == 3
    assert list(qs["rec_0"].criteria) == RECOMMENDATION_LEVELS
    assert KEYWORD_LEVELS[0].startswith("Optional") and KEYWORD_LEVELS[2].startswith("Essential")
```

- [ ] **Step 6:** FAIL → commit `test(prioritizer): una pregunta Score por keyword y por recomendación`.
- [ ] **Step 7:** Implementar `build_questions` con las instrucciones y criterios del spec (sección "Cómo funciona", punto 2), cambiando `i` por el índice. PASS → commit `feat(prioritizer): preguntas Score para Jev`.

- [ ] **Step 8: Tests de `prioritize` (fallan).** Imports: `AsyncMock`, `patch` de `unittest.mock`; `TypeSafeAPIConnectionError`, `TypeSafeAPITimeoutError`, `TypeSafeError` de `typesafe_sdk`.

```python
EV = {"target_role": "Data Analyst", "keywords_missing": ["Looker", "SQL"],
      "recommendations": ["Use a pipe separator", "Add SQL"], "summary": "CV text must not leak"}
SCORES = {"kw_0": 0.2, "kw_1": 1.9, "rec_0": 0.3, "rec_1": 1.6}
ASK = "backend.prioritizer._ask_jev"

async def test_prioritize_orders_both_lists_and_adds_levels(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test")
    with patch(ASK, new_callable=AsyncMock, return_value=SCORES):
        result = await prioritize(EV)
    assert result["keywords_missing"] == ["SQL", "Looker"]
    assert result["keywords_missing_priority"] == ["essential", "optional"]
    assert result["recommendations"] == ["Add SQL", "Use a pipe separator"]
    assert result["recommendations_priority"] == ["essential", "optional"]
    assert EV["keywords_missing"] == ["Looker", "SQL"]  # devuelve una copia

async def test_prioritize_sends_only_the_lists_and_the_role(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test")
    with patch(ASK, new_callable=AsyncMock, return_value=SCORES) as ask:
        await prioritize(EV, job_context="Senior Data Analyst at Acme")
    state = ask.await_args.args[0]
    assert set(state) == {"target_role", "job_description", "missing_keywords", "recommendations"}
    assert state["job_description"] == "Senior Data Analyst at Acme"
    assert "CV text must not leak" not in str(state)

async def test_prioritize_without_key_is_a_noop():
    with patch(ASK, new_callable=AsyncMock) as ask:
        assert await prioritize(EV) == EV
    ask.assert_not_awaited()

async def test_prioritize_skips_jev_when_both_lists_are_empty(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test")
    empty = {**EV, "keywords_missing": [], "recommendations": []}
    with patch(ASK, new_callable=AsyncMock) as ask:
        assert await prioritize(empty) == empty
    ask.assert_not_awaited()

@pytest.mark.parametrize("error", [TypeSafeAPITimeoutError(5.0), TypeSafeAPIConnectionError("down"), TypeSafeError("boom")])
async def test_prioritize_returns_the_evaluation_untouched_when_jev_fails(monkeypatch, error):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test")
    with patch(ASK, new_callable=AsyncMock, side_effect=error):
        assert await prioritize(EV) == EV

async def test_prioritize_treats_a_missing_answer_as_a_failure(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test")
    with patch(ASK, new_callable=AsyncMock, return_value={"kw_0": 1.0}):
        assert await prioritize(EV) == EV
```

- [ ] **Step 9:** FAIL → commit `test(prioritizer): prioritize ordena, no manda el CV y no rompe si Jev falla`.
- [ ] **Step 10:** Implementar `_ask_jev` (`async with AsyncTypeSafeClient(timeout=5.0) as client`, `response = await client.system_one(state, questions)`, devolver `{name: response.scores[name].score for name in questions}`) y `prioritize` (leer la key con `os.getenv` en cada llamada; capturar `TypeSafeError` y `KeyError` con `logger.warning`; `target_role` con `.get(..., "")`). PASS → commit `feat(prioritizer): prioridades con Jev, con fallback sin prioridades`.
- [ ] **Step 11:** `uv run pytest tests/ -q` y `uv run ruff check .` → todo verde.

### Task 3: `/evaluate` prioriza antes de guardar

**Files:**
- Modify: `src/routes/evaluate.py:83-92`
- Test: `tests/test_evaluate.py`

**Interfaces:**
- Consumes: `prioritize(evaluation, job_context)` de Task 2.
- Produces: la respuesta de `POST /evaluate` y `last_evaluation` traen los campos de prioridad cuando Jev respondió.

- [ ] **Step 1: Tests que fallan**

```python
def test_evaluate_returns_and_saves_the_prioritized_evaluation(client, as_user):
    prioritized = {**_EVAL, "recommendations_priority": ["essential"]}
    token = _session_token()
    with _patch("src.routes.evaluate.evaluate_cv", return_value=_EVAL), \
         _patch("src.routes.evaluate.prioritize", new_callable=AsyncMock, return_value=prioritized) as prio, \
         _patch("src.routes.evaluate.save_evaluation") as save:
        res = client.post("/evaluate", headers={"X-CV-Session-Token": token}, data={})
    assert res.json()["recommendations_priority"] == ["essential"]
    save.assert_called_once_with(as_user, prioritized)
    assert prio.await_args.args[0] == _EVAL

def test_evaluate_passes_the_job_context_to_prioritize():
    jobs_cache["data"] = ([make_job("42")], datetime.now(timezone.utc))
    with patch("src.routes.evaluate.evaluate_cv", return_value=MOCK_EVAL), \
         patch("src.routes.evaluate.extract_text", return_value="My Python CV"), \
         patch("src.routes.evaluate.prioritize", new_callable=AsyncMock, return_value=MOCK_EVAL) as prio:
        eval_client.post("/evaluate", data={"job_id": "42"},
                         files={"file": ("cv.pdf", io.BytesIO(b"data"), "application/pdf")})
    assert "Python FastAPI developer" in prio.await_args.args[1]
```

(`AsyncMock` se agrega a los imports de `unittest.mock` del archivo.)

- [ ] **Step 2:** FAIL → commit `test(evaluate): la evaluación se prioriza antes de responder y guardar`.
- [ ] **Step 3:** En `evaluate_resume`, `result = await prioritize(result, job_context)` justo después de `evaluate_cv`. Import `from backend.prioritizer import prioritize`.
- [ ] **Step 4:** `uv run pytest tests/test_evaluate.py -q` → PASS (los tests viejos siguen pasando: sin key, `prioritize` no hace nada). Commit `feat(evaluate): prioriza keywords y recomendaciones con Jev`.

### Task 4: Barras de prioridad en el evaluator

**Files:**
- Modify: `src/static/evaluator.js` (`renderResults`, líneas 115-135), `src/static/evaluator.html` (labels de keywords y recomendaciones), `src/static/app.css` (bloque `.ev-*`, líneas 270-290), `src/static/style.css:715` (borrar `.tag.missing`), `src/static/i18n.js` (keys `ev.prio_*`)
- Test: `tests/test_static_pages.py`

**Interfaces:**
- Consumes: `ev.keywords_missing_priority`, `ev.recommendations_priority` (opcionales).

- [ ] **Step 1: Tests que fallan**

```python
def test_evaluator_keywords_are_not_red():
    assert "tag missing" not in (STATIC / "evaluator.js").read_text(encoding="utf-8")
    assert ".tag.missing" not in (STATIC / "style.css").read_text(encoding="utf-8")

def test_evaluator_draws_priority_bars_with_a_legend():
    js = (STATIC / "evaluator.js").read_text(encoding="utf-8")
    assert "keywords_missing_priority" in js and "recommendations_priority" in js
    html = _evaluator_html()
    for key in ("ev.prio_essential", "ev.prio_important", "ev.prio_optional"):
        assert f'data-i18n="{key}"' in html
```

- [ ] **Step 2:** FAIL → commit `test(evaluator): keywords sin rojo y barras de prioridad con leyenda`.
- [ ] **Step 3: HTML + i18n.** En `evaluator.html`, una leyenda oculta (`class="ev-legend hidden"`) dentro del label de keywords y otra dentro del label de recomendaciones; cada una con tres ítems: el ícono de barras y un `<span data-i18n="ev.prio_essential">Essential</span>` (ídem `important` / "Important", `optional` / "Nice to have"). En `i18n.js`: `'ev.prio_essential': 'Imprescindible'`, `'ev.prio_important': 'Importante'`, `'ev.prio_optional': 'Opcional'`.
- [ ] **Step 4: JS.** En `evaluator.js`:
  - `levelsFor(items, levels)` → `levels` si es array del mismo largo que `items`, si no `null`.
  - `barsHtml(level)` → `<span class="bars l3|l2|l1" aria-label="…"><b></b><b></b><b></b></span>` (`essential`=3, `important`=2, `optional`=1; `aria-label` con `t('ev.prio_<level>', …)`).
  - Keywords: `<span class="tag ev-kw is-<level>">` + barras + `esc(k)`; sin niveles, `<span class="tag ev-kw">` + `esc(k)`.
  - Recomendaciones: `<li><span class="rec-text">esc(r)</span>` + barras `</li>` (sin niveles, sin barras). `showAllRecs` no cambia.
  - Leyenda: visible la del label de keywords si hay niveles y keywords; si no hay keywords y sí niveles de recomendaciones, la del label de recomendaciones; si no, las dos ocultas.
- [ ] **Step 5: CSS.** En `app.css`: `.ev-kw` neutra con `gap: 7px` (valores de Global Constraints), `.ev-kw.is-essential` con `--text-primary`; `.bars` y `.bars b` (medidas de Global Constraints; encendidas `.l3 b`, `.l2 b:nth-child(-n+2)`, `.l1 b:nth-child(1)`); `.ev-recs .rec-text { flex: 1; }`, `.ev-recs li .bars { margin-top: 7px; }`; `.ev-recs li::before` neutro (fondo `rgba(255,255,255,0.05)`, borde `rgba(255,255,255,0.10)`, número `--text-secondary`); `#ev-recs-more` en `--text-secondary` (hover `--text-primary`); `.ev-legend` en línea con el label (`margin-left: 10px`, `gap: 12px`, sin mayúsculas ni letter-spacing). Copiar del bloque K de `src/static/_mock-prio.html`. En `style.css`, borrar la línea `.tag.missing`.
- [ ] **Step 6:** `uv run pytest tests/ -q` → PASS. Commit `feat(evaluator): barras de prioridad en gris en keywords y recomendaciones`.
- [ ] **Step 7: Medir el alto.** Copiar `evaluator.html` a `src/static/_measure.html` (sin commitear). Arriba del `<body>`, un script que guarde en `localStorage['aurea_last_evaluation']` la evaluación de ejemplo de `_mock-prio.html` **con** `keywords_missing_priority: K.map(k => k[1])` y `recommendations_priority: R.map(r => r[1])`. Al final, un script que después de `document.fonts.ready` escriba en `body.dataset.h` el alto de `.ev-main .panel` y en `body.dataset.col` el de `.ev-main`. Correr Chrome headless (`--window-size=1920,945 --virtual-time-budget=8000 --dump-dom`, perfil en el scratchpad) contra `http://127.0.0.1:8001/_measure.html`. Esperado: `data-h="571" data-col="653"`. Si no da, ajustar `.bars` o `.ev-kw` hasta que dé.
- [ ] **Step 8: Casos sin prioridades (Review Focus).** En el mismo `_measure.html`: (a) sin los dos campos de prioridad → etiquetas neutras, sin barras ni leyenda, nada rojo; (b) con `keywords_missing_priority` de un largo menos → keywords sin barras, recomendaciones con barras. Revisar con capturas headless.
- [ ] **Step 9:** Borrar `src/static/_measure.html` y `src/static/_mock-prio.html`.

### Task 5: Corrida real, ajuste y docs

**Files:**
- Modify: `README.md` (tabla de variables de entorno), `CLAUDE.md` (estructura, tests, variables, flujo, fila 4.21)

- [ ] **Step 1:** Con `TYPESAFE_API_KEY` en el `.env`, correr el script del scratchpad (`verify_haiku55.py` o uno nuevo) llamando `evaluate_cv` + `prioritize` con 2 o 3 CVs de prueba (el inventado de la 4.20 y variantes). Revisar que el orden y los niveles tengan sentido y que no salga todo en un solo nivel. Si hace falta, ajustar los umbrales o el texto de los criterios (cada ajuste, con su test actualizado, en su propio commit).
- [ ] **Step 2:** Verificar en el navegador, con un CV de prueba subido de verdad en `http://127.0.0.1:8001/evaluator.html`: barras, leyenda, "Show all" y "Apply to my CV" (que manda primero las imprescindibles).
- [ ] **Step 3:** README: fila de `TYPESAFE_API_KEY` (opcional; sin ella no hay prioridades). Commit `docs(readme): TYPESAFE_API_KEY para la prioridad del evaluator`.
- [ ] **Step 4:** CLAUDE.md: `backend/prioritizer.py` y `tests/test_prioritizer.py` en la estructura, `TYPESAFE_API_KEY` en variables, Jev en el stack, el flujo del evaluator con prioridades, la fixture de conftest y la fila 4.21 (🔄 PR abierto; sale de la 4.20: mergear #68 → #69 → #71 primero; al deployar, `TYPESAFE_API_KEY` en el `.env` del VPS). Commit `docs: tarea 4.21 en CLAUDE.md`.
- [ ] **Step 5:** `uv run pytest tests/ -q` y `uv run ruff check .` → verde. Push y `gh pr create --base develop` con el orden de merge y el aviso de la key en el VPS.
