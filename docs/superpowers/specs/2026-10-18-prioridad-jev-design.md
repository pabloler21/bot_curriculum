# 4.21 — Prioridad de keywords y recomendaciones con Jev

Fecha: 2026-10-18 · Rama: `feature/task-4-21-prioridad-jev` (sale de la 4.20, PR #71)

## Para qué

En los resultados del evaluator, "What to fix" muestra las keywords faltantes y las
recomendaciones en el orden en que las devuelve Haiku, y todas las keywords en rojo
(`.tag.missing`). El usuario no puede saber por dónde empezar, y el rojo compite con lo
que queremos que toque: los botones pagos de la columna derecha ("Generate Cover Letter",
"Tailor your CV").

Queremos que las dos listas vengan **ordenadas de imprescindible a opcional** y que el nivel
de cada ítem se lea de un vistazo, **sin color**.

## Objetivos

- Keywords y recomendaciones ordenadas por prioridad, en una sola escala de tres niveles:
  imprescindible → importante → opcional.
- El nivel se ve con un ícono de tres barras en gris (opción K del companion, elegida por el
  usuario): 3 barras encendidas = imprescindible, 2 = importante, 1 = opcional.
- La prioridad la decide **Jev** (TypeSafe), no Haiku. Decisión del usuario.

## No-objetivos

- No se cambia la columna derecha (adapter, jobs) ni los pliegues de fortalezas/debilidades.
- No se prioriza nada del job board ni del adapter: solo `/evaluate`.
- No se usa la confianza de Jev para decidir nada (ver "Decisiones").

## Anti-objetivos (aunque funcione, sería un fracaso)

- **Color en las prioridades.** El coral queda solo para los botones pagos. El usuario rechazó
  las versiones con coral/ámbar/aqua y con coral en intensidades porque se mezclan con
  "Generate Cover Letter".
- **Cambiar el tamaño de los paneles.** El panel "What to fix" tiene que medir lo mismo que hoy:
  571 px en 1920×945 con la evaluación de ejemplo, y la columna izquierda 653 px. El usuario
  rechazó plegar ítems (más corto) y agruparlos en filas o columnas con título (más alto).
- **Ocultar ítems.** Se siguen viendo las 14 keywords y 5 recomendaciones + "Show all".
- Que una caída de Jev rompa la evaluación, o que el cambio rompa `/improve` o las
  evaluaciones ya guardadas.

## Cómo queda (decidido con el usuario)

Referencia visual: `src/static/_mock-prio.html?v=k` (maqueta temporal, sin commitear; se borra
al terminar la tarea). Sobre la página real del evaluator:

- **Keywords:** una sola nube, en orden de prioridad. Todas las etiquetas iguales, en vidrio
  neutro: fondo `rgba(255,255,255,0.05)`, borde `rgba(255,255,255,0.14)`, texto
  `--text-secondary`; las imprescindibles con texto `--text-primary`. Cada una lleva adentro, a
  la izquierda del texto, el ícono de barras.
- **Ícono:** tres barras de 3 px de ancho y 3/6/9 px de alto, separadas 2 px, alineadas abajo.
  Encendida `rgba(255,255,255,0.80)`, apagada `rgba(255,255,255,0.16)`. Lleva `aria-label`
  con el nombre del nivel (traducido).
- **Leyenda:** al lado de "Missing keywords · 14", en la misma línea: ícono + "Essential",
  ícono + "Important", ícono + "Nice to have" (texto `none`, sin mayúsculas).
- **Recomendaciones:** mismo orden de prioridad; conservan el número de orden y llevan el
  ícono a la derecha de cada una, alineado con la primera línea. Las 5 primeras + "Show all",
  como hoy: al venir ordenadas, las 5 visibles son las más prioritarias.
- **Sin prioridades** (Jev falló, no hay key o la evaluación es anterior a este cambio): las
  listas en el orden de Haiku, etiquetas neutras, sin íconos ni leyenda. Nunca rojo.

## Cómo funciona (backend)

1. **Haiku** (`backend/evaluator.py`) agrega un campo a `ResumeEvaluation`:
   `target_role: str` — el puesto al que apunta el CV, inferido del CV (p. ej. "Data Analyst").
2. **Jev** se llama una vez por evaluación, desde un módulo nuevo `backend/prioritizer.py`,
   después de `evaluate_cv` y antes de `save_evaluation` en `src/routes/evaluate.py`.
   - SDK `typesafe-sdk` (cliente `AsyncTypeSafeClient`), clave en `TYPESAFE_API_KEY`.
     Modelo: el default del SDK (`jev-latest`).
   - **State** (JSON): `target_role`, `job_description` (el `job_context` de `/evaluate` cuando
     viene un `job_id`, si no `null`), `missing_keywords` y `recommendations`. **El CV no va**:
     la doc de Jev avisa que el contenido de más distrae y que texto malicioso en el state
     puede mover las respuestas, y el CV es input no confiable (task 3.23).
   - **Preguntas:** una `Score` por cada keyword y una por cada recomendación, todas en el
     mismo request (corren en paralelo). Las instrucciones son fijas y apuntan al ítem con un
     path entre backticks (`missing_keywords[3]`), sin meter el texto del ítem en la pregunta.
     Criterios de 3 niveles, **de menor a mayor** (así los pide `Score`). Borrador:

     Keywords — instrucción: "How essential is the keyword `missing_keywords[i]` for someone
     applying to `target_role` jobs? If `job_description` is not null, judge against it."
     0. "Optional: rarely asked for in these jobs; missing it barely changes the candidate's chances"
     1. "Important: often listed in these job posts; missing it lowers the match but does not rule the candidate out"
     2. "Essential: a core requirement; ATS filters and recruiters screen out candidates who lack it"

     Recomendaciones — instrucción: "How much does applying the recommendation
     `recommendations[i]` improve the chances of someone applying to `target_role` jobs?
     If `job_description` is not null, judge against it."
     0. "Optional: polish; a small wording or formatting tweak that barely changes how ATS or recruiters rank the CV"
     1. "Important: noticeably improves the keyword match or the clarity of the CV, but its absence does not rule the candidate out"
     2. "Essential: fixes something that makes ATS misread the CV or screen the candidate out, or adds a core requirement of the role"

3. **Orden y nivel** en código: cada ítem toma el `score` de su pregunta (0 a 2). Nivel:
   `>= 1.5` essential, `>= 0.5` important, si no optional. Las listas se ordenan por `score`
   de mayor a menor, con orden estable (en un empate queda el orden de Haiku).
4. **Formato de la respuesta:** `keywords_missing` y `recommendations` siguen siendo listas de
   strings (ya ordenadas), y se agregan dos listas paralelas, del mismo largo:
   `keywords_missing_priority` y `recommendations_priority`, con `"essential" | "important" |
   "optional"`. Así `/improve` (que recibe `list[str]`) y las evaluaciones guardadas siguen
   andando, y "Apply to my CV" manda primero las imprescindibles.
5. **Si Jev no está o falla** (sin `TYPESAFE_API_KEY`, timeout, 4xx/5xx, conexión): se loguea un
   warning y la evaluación sale sin las listas de prioridad. Nunca un 500 por Jev. Si las dos
   listas vienen vacías, no se llama a Jev.

## Decisiones que tomé yo (Claude), para revisar

- **Score, no Choice.** El usuario habló de "choices"; la doc de TypeSafe dice que Choice no
  modela orden entre opciones y que para una escala ordenada va Score.
- **Umbrales 1,5 / 0,5.** La doc permite usar el score para comparar con un umbral, no como
  medida exacta. Se ajustan corriendo 2 o 3 CVs reales al implementar.
- **Sin filtro por confianza:** es solo un orden en pantalla; la doc dice que una confianza baja
  no invalida una decisión inofensiva.
- **Timeout de 5 s** para Jev (el SDK trae 10 s por defecto): si tarda más, sale sin
  prioridades en vez de demorar la evaluación.
- **Nombres:** en inglés "Essential / Important / Nice to have" (los de la maqueta que vio el
  usuario); en español "Imprescindible / Importante / Opcional", las palabras del usuario.
- **También pasan a gris**, como en la maqueta elegida, los números de las recomendaciones (hoy
  con degradé coral/aqua) y el link "Show all recommendations" (hoy coral).
- **Se borra `.tag.missing`** de `style.css`: solo la usaba el evaluator.
- **Leyenda sin keywords:** si no hay keywords faltantes (el bloque se oculta) pero sí
  recomendaciones con prioridad, la leyenda va al lado de "Recommendations".
- **Prioridades inconsistentes:** si una lista de prioridad no tiene el mismo largo que su lista,
  el frontend la ignora y muestra esa lista sin íconos (como una evaluación vieja).

## Lo que queda para quien implementa

- El texto final de instrucciones y criterios (el borrador de arriba es el punto de partida) y
  los umbrales, ajustados con CVs reales.
- Cómo se arma el `AsyncTypeSafeClient` (por request o reutilizado) y el manejo fino de errores.
- Los tests: `tests/test_prioritizer.py` con el cliente mockeado (orden, niveles, umbrales,
  no-op sin key, fallo de Jev → sin prioridades), el cambio en `tests/test_evaluate.py`, un test
  estático del render (sin `tag missing`, íconos y leyenda cuando hay prioridades) y las
  traducciones en `i18n.js` (las exige `tests/test_i18n.py`).

## Restricciones y verificación

- TDD estricto en backend; commits chicos (test → implementación por cada cambio).
- Verificar en el navegador a 1920×945: el panel "What to fix" mide 571 px y la columna
  izquierda 653 px con la evaluación de ejemplo de la maqueta, igual que hoy.
- Corrida real con un CV de prueba (Haiku + Jev) antes de abrir el PR: los tests mockean ambos.
- Deploy: `typesafe-sdk` entra en `pyproject.toml` y `uv.lock` (el servicio corre con
  `uv run --frozen`); `TYPESAFE_API_KEY` en el `.env` local y en el del VPS.
- Actualizar README (variable de entorno nueva) y CLAUDE.md en la misma rama.

## Datos verificados (2026-10-17/18)

- Jev: `jev-latest` = Jev 1.13 estable; Jev 1.14 preview desde el 2026-10-14. $0,042 por millón
  de tokens de entrada, salida gratis. Límite 64k tokens por request. Fuente: docs.typesafe.ai/models.
- `Score`: criterios ordenados de menor a mayor; respuesta con `score`, `probabilities` y
  `confidence`. Fuente: docs.typesafe.ai/primitives/score.
- SDK Python `typesafe-sdk` 0.7.5 (PyPI, 2026-10-14); `TYPESAFE_API_KEY`, timeout por defecto
  10 s; excepción base `TypeSafeError`. Fuente: docs.typesafe.ai/sdk/python.
- Jev rinde mejor en inglés; Haiku devuelve keywords y recomendaciones en inglés.
