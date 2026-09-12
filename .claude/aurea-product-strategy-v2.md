# Aurea — Plan estratégico v2 (con auditoría integrada)

> **Contexto:** Este documento es la evolución del brief original (`aurea-product-strategy-audit.md`). Incorpora la auditoría técnica realizada, cierra gaps identificados, define criterios de éxito por fase, incluye política de errores del pipeline, y desglosa costos reales. Las secciones 1-4 del documento original se mantienen sin cambios y no se repiten acá.

---

## 1. Cambios respecto al plan original

### Lo que cambió

- **Fase 1 se divide en 1a (validación) y 1b (cobrable).** El MVP original intentaba desplegar auth + pagos + pipeline + renderer todo junto. Ahora se valida primero que el pipeline produce output usable, y después se construye el sistema de pagos encima.
- **Cover letter se mueve de Fase 2 a Fase 1b** como texto copiable (sin renderer PDF/DOCX). Un crédito = 1 job application completa (CV adaptado + cover letter).
- **Pricing simplificado.** 1 crédito = 1 adapter + 1 cover letter. Se elimina el "0.5 créditos por cover letter" que agregaba complejidad de billing sin valor.
- **Free tier requiere email desde el primer uso** (magic link). Se elimina el "2 análisis gratis sin cuenta" que introducía complejidad de rate limiting por IP/fingerprint sin dar retargeting.
- **Observabilidad entra en Fase 1a**, no como afterthought.
- **Cada fase tiene criterio de éxito, kill signal, y tiempo máximo.**
- **Política de errores del pipeline definida** con estados y política de créditos.

### Lo que NO cambió

Todo lo que está en secciones 1-4 del documento original se mantiene: estado actual del producto, pivote estratégico, target & posicionamiento, pipeline anti-alucinación (3 etapas). El stack propuesto en sección 5 también se mantiene.

---

## 2. Estimación de costos por adapter

### Modelo de tokens por etapa (Haiku 4.5)

Basado en un CV típico de 1-2 páginas (dev tech LATAM) y un JD de ~500 palabras.

| Etapa | Input tokens (est.) | Output tokens (est.) | Notas |
|-------|--------------------:|---------------------:|-------|
| Etapa 1 — Extracción | ~2.500 | ~1.500 | CV crudo + system prompt → CVSchema JSON |
| Etapa 2 — Adaptación | ~4.000 | ~2.000 | CVSchema + JD + system prompt → adapted schema + gaps |
| Etapa 3 — Validación | ~500 | ~0 | Embedding comparison, sin LLM call |
| Retry (25% de los casos) | ~4.000 | ~2.000 | Re-run etapa 2 con feedback de validación |
| Cover letter | ~3.000 | ~800 | Adapted schema + JD → texto libre 3 párrafos |
| **Total sin retry** | **~10.000** | **~4.300** | |
| **Total con retry** | **~14.000** | **~6.300** | |

### Costo en USD por adapter (Haiku 4.5: $1/1M input, $5/1M output)

| Escenario | Costo input | Costo output | **Total** |
|-----------|------------:|-------------:|----------:|
| Sin retry | $0.010 | $0.022 | **$0.032** |
| Con retry (1x) | $0.014 | $0.032 | **$0.046** |
| Peor caso (2 retries) | $0.018 | $0.042 | **$0.060** |

### Margen por crédito

| Precio por crédito | Costo promedio | Fee Lemon Squeezy (5% + $0.50 sobre pack $4.99) | Margen neto por crédito |
|-------------------:|---------------:|-------------------------------------------------:|------------------------:|
| $1.00 (pack $4.99 = 5) | $0.04 | ~$0.15 | **$0.81** |
| $1.00 (Pro $9.99/mes, ~15 usos) | $0.04 | ~$0.10 | **$0.86** |

**Conclusión:** el margen es cómodo con Haiku 4.5. Incluso en peor caso ($0.06/adapter), el costo de LLM es ~6% del precio. El factor limitante de margen es Lemon Squeezy, no los tokens.

### ¿Sonnet en vez de Haiku para alguna etapa?

Sonnet 4.6: $3/1M input, $15/1M output. Costo por adapter subiría a ~$0.10-0.18. Todavía viable, pero hay que **medirlo**: correr 20 CVs reales por ambos modelos y comparar calidad de extracción y adaptación antes de decidir. No asumir que Sonnet es mejor — medir.

---

## 3. Roadmap revisado por fases

### Fase 0 — Cortar (3-4 días)

**Qué:** Sacar Job Board del scope monetizable. Eliminar dependencias de `/jobs/score` del flujo crítico. Documentar lo cortado.

**Criterio de éxito:** el repo tiene un README actualizado, el deploy no depende de nada del Job Board para funcionar, y el evaluator ATS funciona independiente.

**Kill signal:** N/A — es housekeeping, no hay riesgo de validación.

**Costo de infra en esta fase:** $0 (sigue en Render free).

---

### Fase 1a — Adapter funciona, sin pagos (1 semana)

**Goal:** el pipeline de 3 etapas produce un CV adaptado + cover letter que 3/5 testers reales usarían tal cual.

**Qué se construye:**

- Migrar `cv_sessions` dict → Postgres (Supabase free tier).
- Pipeline completo: Etapa 1 (extracción) → Etapa 2 (adaptación) → Etapa 3 (validación por embeddings).
- Renderer PDF con UNA plantilla ATS-friendly.
- Cover letter como texto (sin renderer).
- Observabilidad básica: tabla `pipeline_runs` en Supabase con campos `id, user_id, status, stage, input_hash, output_hash, tokens_input, tokens_output, cost_usd, duration_ms, error_message, created_at`. Cada invocación loggea su trace completo.
- Endpoint `/adapt` funcional sin auth ni pagos.
- Bilingüe: usuario elige idioma de output (ES/EN).

**Criterio de éxito:** mandarlo a 5 personas reales buscando laburo (de tu red). Al menos 3/5 usarían el CV adaptado tal como salió o con edits menores. Si 3/5 dicen "tuve que rehacer la mitad", el pipeline no está listo.

**Kill signal:** si después de 2 iteraciones del pipeline los testers siguen rechazando el output, el problema es el prompting o el modelo, no features faltantes. Hay que calibrar antes de avanzar.

**Tiempo máximo:** 10 días. Si se extiende, es señal de que el scope está mal cortado.

**Costo de infra:**

| Item | Costo/mes |
|------|----------:|
| Supabase free tier | $0 |
| Render free tier (sigue acá) | $0 |
| Anthropic API (testing, ~50 runs) | ~$2 |
| Resend (no se usa aún) | $0 |
| **Total** | **~$2** |

---

### Fase 1b — MVP cobrable (2 semanas)

**Goal:** un desconocido paga por un adapter.

**Qué se construye:**

- Auth con Supabase Auth, magic link via Resend. Email obligatorio desde el primer uso.
- Free tier: 2 adapters gratis (con cuenta creada, limitado por email). Sin descarga PDF en free — solo preview.
- Lemon Squeezy: webhook handler para `order.created` y `subscription.updated`.
- Sistema de créditos en DB: tabla `credits` con `user_id, balance, last_purchase_at`.
- Lógica de decremento provisional (ver sección 4: Política de errores).
- Migrar deploy a Railway (Hobby $5/mes).

**Pricing:**

| Tier | Precio | Incluye |
|------|--------|---------|
| Free (con cuenta) | $0 | 2 adapters completos (CV + cover letter), sin descarga PDF |
| Pay-per-use | USD $4.99 = 5 créditos | 1 crédito = 1 adapter + 1 cover letter + descarga PDF |
| Pro | USD $9.99/mes | Ilimitado, todas las plantillas (cuando haya más), historial |
| Lifetime (primeros 3 meses) | USD $49 | Pro de por vida — early traction + testimonials |

**Criterio de éxito:** dentro de las primeras 2 semanas post-deploy, al menos 1 persona que NO conocés completa un pago. No 10 — 1. Si ni un desconocido paga, el problema es distribución o confianza, y hay que investigar cuál antes de seguir.

**Kill signal:** 0 pagos en 3 semanas → pausar features, investigar si el problema es awareness (nadie llega), conversión (llegan pero no pagan), o valor percibido (prueban free y no ven suficiente valor).

**Tiempo máximo:** 2 semanas de build + 3 semanas de observación.

**Costo de infra:**

| Item | Costo/mes |
|------|----------:|
| Railway Hobby | $5 |
| Supabase free tier | $0 |
| Resend free tier (100 emails/día) | $0 |
| Lemon Squeezy | 5% + $0.50 por tx (solo si hay ventas) |
| Anthropic API (estimado 100 runs/mes iniciales) | ~$4 |
| Dominio (si se compra) | ~$12/año = $1/mes |
| **Total fijo** | **~$10/mes** |

---

### Fase 2 — Producto que retiene (2 semanas)

**Goal:** un usuario vuelve a usar Aurea para un segundo job.

**Qué se construye:**

- Historial de adaptaciones (cada una con su CV original y JD, regenerable).
- 2 plantillas más (total: 3).
- Cover letter con export DOCX (ahora sí con renderer).
- Score ATS antes/después con visualización de delta.

**Criterio de éxito:** al menos 1 usuario vuelve a usar el producto para un segundo job distinto dentro de los 30 días. Si nadie vuelve, más plantillas y features no van a arreglar eso.

**Kill signal:** 0 usuarios recurrentes en 30 días → el problema es retención, no features. Investigar si el output del adapter es suficientemente bueno, si el pricing free es demasiado generoso, o si el flujo tiene demasiada fricción.

**Costo de infra adicional:**

| Item | Delta vs Fase 1b |
|------|------------------:|
| Supabase Storage (historial de CVs) | $0 (free tier cubre ~1GB) |
| Mayor uso de API (usuarios recurrentes) | +$5-10/mes |
| **Total estimado** | **~$15-20/mes** |

---

### Fase 3 — El moat (3-4 semanas)

**Goal:** un usuario menciona Gap Interview o Match Radar como razón para elegir Aurea.

**Qué se construye:**

- **Gap Interview** completo (chat conversacional con detección de gaps).
- **Match Radar**: visualización semántica de qué keywords del JD cubrís, cuáles no, y qué tenés de más.
- Versionado por empresa/rol con metadata.

**Criterio de éxito:** feedback cualitativo de al menos 3 usuarios mencionando estas features como diferenciador. Esto se mide con un survey post-uso o con feedback directo.

**Kill signal:** si los usuarios ignoran Gap Interview y Match Radar (no los usan aunque estén disponibles), el valor percibido está mal calibrado. Pivotear a features que los usuarios sí pidan.

**Nota sobre frontend:** el Gap Interview requiere un flujo de chat que vanilla JS no maneja bien. Evaluar en este punto si migrar a un framework liviano (Astro, htmx). Costo estimado de migración: 1 semana adicional. Decisión se toma al inicio de Fase 3 con datos de cuánto vanilla JS está costando mantener.

**Costo de infra adicional:**

| Item | Delta vs Fase 2 |
|------|------------------:|
| Más tokens por Gap Interview (~3k tokens/sesión) | +$5-10/mes |
| Posible Supabase Pro si DB > 500MB | +$25/mes |
| **Total estimado** | **~$40-55/mes** |

---

### Fase 4 — Distribución (1 mes)

- Reactivar Job Board como funnel: cada job card tiene "Adapt my CV for this →" con JD pre-cargado.
- Chrome extension que detecta JDs en LinkedIn/Wellfound.

**Criterio de éxito:** el Job Board genera al menos 20% de los nuevos usuarios. La extension tiene al menos 50 installs.

**Costo adicional:** ~$0 (Chrome Web Store es gratis para publicar).

---

### Fase 5 — Escala

- MercadoPago para mercado LATAM (precio en pesos).
- Plantillas premium pagas individualmente.
- Plan team para reclutadores.

**Criterio de éxito:** revenue mensual > costos de infra × 3 (margen sostenible).

---

## 4. Política de errores del pipeline

### Estados de un pipeline run

```
CREATED → EXTRACTING → ADAPTING → VALIDATING → COMPLETED
                ↓            ↓           ↓
            FAILED_EXTRACT  FAILED_ADAPT  PARTIAL
```

- **CREATED:** crédito decrementado provisionalmente.
- **EXTRACTING:** LiteParse intenta extraer texto del CV.
- **FAILED_EXTRACT:** PDF es imagen sin OCR, DOCX corrupto, o texto insuficiente. **Crédito restaurado.** Usuario ve: "No pudimos leer tu CV. Intentá con otro formato (PDF con texto seleccionable o DOCX)."
- **ADAPTING:** Etapa 2 del pipeline. Tiene budget de 2 retries máximo.
- **FAILED_ADAPT:** 3 intentos fallidos de generar output válido contra el schema. **Crédito restaurado.** Usuario ve: "Hubo un problema adaptando tu CV a este puesto. Intentá de nuevo o probá con otro JD." Se loggea para debugging.
- **VALIDATING:** Etapa 3, similarity check por embeddings.
- **PARTIAL:** Output generado pero algunos bullets no pasaron el threshold de similitud después del retry. **Crédito confirmado (se consumió).** Usuario recibe el CV adaptado con un warning: "Revisá los items marcados — algunos podrían no reflejar exactamente tu experiencia." Los bullets sospechosos se marcan visualmente.
- **COMPLETED:** Todo pasó validación. **Crédito confirmado.**

### Regla de créditos

**Si el usuario no recibió un output usable, no pierde el crédito.** La extracción se ejecuta antes de decrementar, así que si el CV no se puede leer, no hay costo. El decremento provisional ocurre al entrar en ADAPTING. Se confirma o restaura según el estado final.

### Retry budget

- Etapa 2 (adaptación): máximo 2 retries (3 intentos total). Cada retry incluye feedback de qué falló ("bullets X e Y no tienen correspondencia con el schema original").
- Etapa 3 (validación): 1 re-run de etapa 2 con feedback. Si el segundo intento tampoco pasa, se entrega como PARTIAL.
- Costo de peor caso con retries: ~$0.06 por adapter (ver sección 2). Aceptable.

### Implementación

Tabla `pipeline_runs` en Supabase:

```sql
CREATE TABLE pipeline_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id),
    status TEXT NOT NULL DEFAULT 'created',
    -- posibles: created, extracting, adapting, validating, completed, failed_extract, failed_adapt, partial
    cv_input_hash TEXT NOT NULL,
    jd_input_hash TEXT NOT NULL,
    cv_schema JSONB,
    adapted_schema JSONB,
    gaps JSONB,
    cover_letter TEXT,
    tokens_input INT,
    tokens_output INT,
    cost_usd NUMERIC(6,4),
    retries INT DEFAULT 0,
    error_message TEXT,
    duration_ms INT,
    created_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);
```

---

## 5. Costos totales proyectados por fase

| Fase | Duración | Costo fijo/mes | Costo variable/mes (estimado) | Total mes |
|------|----------|---------------:|------------------------------:|----------:|
| 0 — Cortar | 3-4 días | $0 | $0 | **$0** |
| 1a — Validación | ~10 días | $0 | ~$2 (API testing) | **~$2** |
| 1b — Cobrable | 2 sem build + 3 sem obs. | $10 | ~$4 (API) | **~$14** |
| 2 — Retención | 2 semanas | $10 | ~$10 (API + storage) | **~$20** |
| 3 — Moat | 3-4 semanas | $10-35 | ~$15 (API + más uso) | **~$25-50** |
| 4 — Distribución | 1 mes | $35 | ~$20 | **~$55** |

### Breakeven

A precio de $4.99 por 5 créditos, con ~$0.15 de fee LS por tx + ~$0.20 de API por pack:

**Ingreso neto por pack vendido: ~$4.64**

Para cubrir $14/mes (Fase 1b), necesitás **3 packs/mes** (15 créditos, ~$14 de ingreso).
Para cubrir $50/mes (Fase 3), necesitás **~11 packs/mes** (~$51 de ingreso).

Con un usuario Pro ($9.99/mes, ~$0.50 fee LS, ~$0.60 de API): **ingreso neto ~$8.89/mes**.
Para cubrir $50/mes con solo Pro: **6 suscriptores Pro**.

---

## 6. Decisiones abiertas que requieren datos (no opinión)

1. **¿Haiku o Sonnet para la etapa de adaptación?** Medir con 20 CVs reales. Criterio: si Haiku produce output que 3/5 testers aceptan, quedarse con Haiku. Si no, probar Sonnet y comparar costo incremental vs mejora de calidad.

2. **¿Threshold de similitud para validación?** Empezar con 0.65, calibrar con las primeras 50 runs. Si hay muchos false positives (bullets inventados que pasan) bajar. Si hay muchos false negatives (bullets legítimos rechazados por traducción ES→EN) subir y/o migrar a `paraphrase-multilingual-MiniLM-L12-v2`.

3. **¿LangChain o SDK directo?** Evaluar después de Fase 1a. Si `with_structured_output` es lo único que se usa de LangChain, el overhead no se justifica. Migración estimada: 1-2 días.

4. **¿Vanilla JS o framework para Fase 3?** Decisión se toma al inicio de Fase 3 con datos de cuánto cuesta mantener vanilla. Si Gap Interview requiere state management complejo, migrar a Astro/htmx. Costo: ~1 semana.

5. **¿Lemon Squeezy o alternativa?** LS fue adquirido por Stripe. Riesgo aceptable para MVP. Si hay problemas, Polar.sh o DodoPayments son alternativas con API similar. Migración estimada: 3-5 días.

---

## 7. Riesgos actualizados

### Riesgos cerrados (resueltos en este documento)

- ~~No hay criterio de éxito por fase~~ → Definido en sección 3.
- ~~No hay política de errores~~ → Definido en sección 4.
- ~~Costo por adapter no calculado~~ → Definido en sección 2.
- ~~Cover letter dejada para después sin justificación~~ → Movida a Fase 1b.
- ~~Free sin cuenta introduce complejidad~~ → Ahora requiere email.
- ~~No hay observabilidad~~ → `pipeline_runs` en Fase 1a.

### Riesgos abiertos

1. **MiniLM cross-lingual ES↔EN:** threshold de similitud puede no funcionar bien para traducciones. Mitigación: calibrar con datos reales en Fase 1a, tener `paraphrase-multilingual-MiniLM-L12-v2` como fallback.

2. **Gap Interview UX:** "El JD pide X pero no veo nada en tu CV" puede leerse como acusación. Mitigación: UX writing dedicado en Fase 3, testing con usuarios no técnicos.

3. **Supabase free tier (500MB DB, 1GB storage):** con ~1000 usuarios y historial, se llega al límite. Mitigación: monitorear en Fase 2, tener plan de upgrade a Supabase Pro ($25/mes) cuando se acerque.

4. **GDPR/LGPD:** si hay usuarios EU, hay obligaciones de data handling. Mitigación: agregar delete account + data export en Fase 2. No bloquea MVP.

5. **Lemon Squeezy post-adquisición:** riesgo de cambios en pricing o API. Mitigación: webhook handler abstraído detrás de interfaz; migración a alternativa estimada en 3-5 días.

---

## 8. Lo que se mantiene del plan original (sin cambios)

- Secciones 1-4 completas (estado actual, pivote, target, pipeline anti-alucinación).
- Stack propuesto (Supabase, Lemon Squeezy, Railway, vanilla frontend en MVP).
- Lo que se mantiene del código actual (sección 8 original).
- Lo que se corta del código actual (sección 9 original).

## 9. Lo que reemplaza este documento

- Sección 6 original (roadmap) → reemplazada por sección 3 de este documento.
- Sección 7 original (pricing) → reemplazada por pricing en Fase 1b de sección 3.
- Sección 10 original (riesgos) → reemplazada por sección 7 de este documento.
- Sección 11 original (preguntas) → parcialmente respondidas en las auditorías; las que requieren datos están en sección 6.
