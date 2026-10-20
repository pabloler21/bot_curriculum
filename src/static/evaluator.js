// evaluator.js — funnel de onboarding (spec §5): upload → analizando → resultados,
// y las acciones pagas (Apply / Cover / Tailor) detrás de aurea.requireAuth().
'use strict';

const SESSION_KEY = 'cv_session_token';
const CLAIMED_KEY = 'aurea_claimed_token';
const EVAL_KEY = 'aurea_last_evaluation';
const ALT_KEY = 'aurea_last_evaluation_alt';  // la misma evaluación en el otro idioma: volver no pide otra traducción
const RESULT_KEY = 'aurea_last_result';
const PENDING_JD_KEY = 'aurea_pending_jd';
const MAX_BYTES = 5 * 1024 * 1024;
const MIN_JD_CHARS = 50;

const $ = (id) => document.getElementById(id);
const show = (el) => el.classList.remove('hidden');
const hide = (el) => el.classList.add('hidden');
const t = (k, f) => aurea.t(k, f);
const esc = (s) => aurea.escHtml(s);

let evaluation = null;
let actionBusy = false;

function showError(el, msg) { el.textContent = msg; show(el); }
function networkError() { return t('err.network', 'Network error. Check your connection and try again.'); }

async function errorDetail(res) {
  if (res.status === 429) return t('err.rate', 'Too many requests — please wait a minute before trying again.');
  const data = await res.json().catch(() => ({}));
  return aureaRender.detailText(data.detail, `${t('err.server', 'Server error')} (${res.status})`);
}

// ── Estados 1 y 2 ─────────────────────────────────────────────────────────
function setIntakeBusy(busy, translating = false) {
  $('ev-drop-idle').classList.toggle('hidden', busy);
  $('ev-drop-busy').classList.toggle('hidden', !busy);
  $('ev-busy-title').textContent = translating ? t('ev.translating', 'Translating your analysis…') : t('ev.analyzing', 'Analyzing your CV…');
  $('ev-busy-hint').textContent = translating ? t('ev.translating_hint', 'This takes about 15 seconds.') : t('ev.analyzing_hint', 'This takes about 20 seconds.');
}

function showIntake() {
  hide($('ev-results'));
  show($('ev-intake'));
  setIntakeBusy(false);
}

function fileError(file) {
  const ext = (file.name.split('.').pop() || '').toLowerCase();
  if (!['pdf', 'docx'].includes(ext)) return t('ev.err_type', 'Only PDF and DOCX files are supported.');
  if (file.size > MAX_BYTES) return t('ev.err_size', 'File exceeds the 5 MB limit.');
  return null;
}

async function uploadAndEvaluate(file) {
  if (!file) return;
  const err = fileError(file);
  if (err) return showError($('ev-error'), err);
  hide($('ev-error'));
  setIntakeBusy(true);
  try {
    const fd = new FormData();
    fd.append('file', file);
    const up = await fetch('/session', { method: 'POST', body: fd });
    if (!up.ok) throw new Error(await errorDetail(up));
    const { token } = await up.json();
    localStorage.setItem(SESSION_KEY, token);

    if (aurea.session) {
      // Con sesión, el CV subido pasa a ser el CV base antes de evaluarlo.
      const put = await aurea.authFetch('/cv', { method: 'PUT', headers: { 'X-CV-Session-Token': token }, body: new FormData() });
      if (!put.ok) throw new Error(await errorDetail(put));
      localStorage.setItem(CLAIMED_KEY, token);
    }
    await evaluate({ 'X-CV-Session-Token': token });
  } catch (e) {
    setIntakeBusy(false);
    showError($('ev-error'), e instanceof TypeError ? networkError() : e.message);
  }
}

async function evaluate(headers) {
  const fd = new FormData();
  fd.append('output_language', aurea.lang);  // el análisis sale en el idioma de la página
  const res = await aurea.authFetch('/evaluate', { method: 'POST', headers, body: fd });
  if (!res.ok) throw new Error(await errorDetail(res));
  evaluation = await res.json();
  try {
    localStorage.setItem(EVAL_KEY, JSON.stringify(evaluation));
    localStorage.removeItem(ALT_KEY);
  } catch (_) {}
  renderResults(evaluation);
}

// La evaluación guardada puede estar en otro idioma (se cambió EN/ES, o es de antes de la 4.22): se traduce
// en vez de re-evaluar, que podía cambiar el puntaje. La otra versión queda guardada para volver sin llamar.
async function inPageLanguage(ev) {
  if (ev.language === aurea.lang) return ev;
  let alt = null;
  try { alt = JSON.parse(localStorage.getItem(ALT_KEY)); } catch (_) {}
  let out = alt && alt.language === aurea.lang && alt.evaluated_at && alt.evaluated_at === ev.evaluated_at ? alt : null;
  if (!out) {
    setIntakeBusy(true, true);
    try {
      const res = await aurea.authFetch('/evaluate/translate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ evaluation: ev, output_language: aurea.lang }),
      });
      if (!res.ok) throw new Error(String(res.status));
      out = await res.json();
    } catch (_) {
      return ev;  // sin traducción se ve en el otro idioma, pero se ve
    } finally {
      setIntakeBusy(false);
    }
  }
  try {
    localStorage.setItem(EVAL_KEY, JSON.stringify(out));
    localStorage.setItem(ALT_KEY, JSON.stringify(ev));
  } catch (_) {}
  return out;
}

// ── Estado 3 ──────────────────────────────────────────────────────────────
function initials(name) {
  return (name || '?').split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join('');
}

// Fortalezas y debilidades: filas con un ícono gris, como las recomendaciones numeradas.
function rowsHtml(items, icon) {
  return items.map((i) => `<li><span class="ev-ico" aria-hidden="true">${icon}</span><span>${esc(i)}</span></li>`).join('');
}

// Prioridad de Jev: barras de señal en gris (sin color: el color es de los botones pagos).
const PRIO = { essential: [3, 'Essential'], important: [2, 'Important'], optional: [1, 'Nice to have'] };

// Solo si vienen completos: una evaluación vieja o con un largo distinto se ve sin barras.
function levelsFor(items, levels) {
  return Array.isArray(levels) && levels.length === items.length ? levels : null;
}

function prioLevel(level) { return PRIO[level] ? level : 'optional'; }

function barsHtml(level) {
  const lv = prioLevel(level);
  const [bars, name] = PRIO[lv];
  return `<span class="bars l${bars}" role="img" aria-label="${esc(t(`ev.prio_${lv}`, name))}"><b></b><b></b><b></b></span>`;
}

function renderPriorities(ev) {
  const kws = ev.keywords_missing || [];
  const kwLevels = levelsFor(kws, ev.keywords_missing_priority);
  $('ev-keywords').innerHTML = kws.map((k, i) => (kwLevels
    ? `<span class="tag ev-kw is-${prioLevel(kwLevels[i])}">${barsHtml(kwLevels[i])}${esc(k)}</span>`
    : `<span class="tag ev-kw">${esc(k)}</span>`)).join('');
  $('ev-kw-count').textContent = kws.length;
  $('ev-kw-block').classList.toggle('hidden', !kws.length);

  const recs = ev.recommendations || [];
  const recLevels = levelsFor(recs, ev.recommendations_priority);
  $('ev-recs').innerHTML = recs.map((r, i) =>
    `<li><span class="rec-text">${esc(r)}</span>${recLevels ? barsHtml(recLevels[i]) : ''}</li>`).join('');

  // La leyenda va con las keywords; si no hay keywords, con las recomendaciones.
  const legend = $('ev-legend');
  const label = kwLevels && kws.length ? $('ev-kw-label') : recLevels && recs.length ? $('ev-recs-label') : null;
  legend.classList.toggle('hidden', !label);
  if (label) label.append(legend);
}

function openSummary(open) {
  $('ev-summary').classList.toggle('is-open', open);
  const btn = $('ev-summary-more');
  btn.textContent = open ? t('ev.read_less', 'Show less') : t('ev.read_more', 'Read more');
  btn.setAttribute('aria-expanded', String(open));
}

const RECS_SHOWN = 4;  // con texto de 16 px entran 4 sin scroll en 1920×945; el resto, detrás de "Show all"
let recsShown = RECS_SHOWN;

function showAllRecs(all) {
  const items = [...$('ev-recs').children];
  items.forEach((li, i) => li.classList.toggle('hidden', !all && i >= recsShown));
  const btn = $('ev-recs-more');
  btn.classList.toggle('hidden', items.length <= recsShown);
  btn.textContent = all ? t('ev.recs_less', 'Show fewer') : `${t('ev.recs_all', 'Show all recommendations')} (${items.length})`;
  btn.setAttribute('aria-expanded', String(all));
  // En escritorio se despliegan dentro de la pestaña, debajo de lo visible: sin bajar, no se notaba el cambio.
  // Se mueve solo la pestaña (scrollIntoView también movería la página si tiene scroll).
  const pane = $('ev-pane-fix');
  if (all && getComputedStyle(pane).overflowY === 'auto' && items[recsShown]) {
    pane.scrollTop += items[recsShown].getBoundingClientRect().top - pane.getBoundingClientRect().top;
  }
}

// En escritorio la pestaña tiene alto fijo (el de la columna del adapter): se muestran las recomendaciones
// que entran sin scroll, hasta RECS_SHOWN, porque su largo cambia con el CV y el idioma. Se recalcula
// cuando cambia el alto (cargan los jobs, cambia la ventana); con "Show all" abierto no se toca.
function fitRecs() {
  const pane = $('ev-pane-fix');
  if (pane.hidden || getComputedStyle(pane).overflowY !== 'auto' || $('ev-recs-more').getAttribute('aria-expanded') === 'true') return;
  recsShown = RECS_SHOWN;
  showAllRecs(false);
  while (recsShown > 1 && pane.scrollHeight > pane.clientHeight) {
    recsShown -= 1;
    showAllRecs(false);
  }
}

function renderStrengthsAndWeaknesses(ev) {
  const strengths = ev.strengths || [];
  const weaknesses = ev.weaknesses || [];
  const formatting = ev.formatting_issues || [];
  $('ev-strengths').innerHTML = rowsHtml(strengths, '✓');
  $('ev-weaknesses').innerHTML = rowsHtml(weaknesses, '!');
  $('ev-formatting').innerHTML = rowsHtml(formatting, '!');
  $('ev-formatting-label').classList.toggle('hidden', !formatting.length);
  $('ev-strengths-count').textContent = strengths.length;
  $('ev-weak-count').textContent = weaknesses.length + formatting.length;
}

// ── Pestañas: What to fix / Strengths / Weaknesses ──
const TABS = [...document.querySelectorAll('.ev-tabs [role="tab"]')];

function selectTab(tab, focus) {
  TABS.forEach((x) => {
    const on = x === tab;
    x.setAttribute('aria-selected', String(on));
    x.tabIndex = on ? 0 : -1;
    $(x.getAttribute('aria-controls')).hidden = !on;
  });
  $('ev-fix-foot').hidden = tab.id !== 'ev-tab-fix';  // "Show all" y "Apply" son de las recomendaciones
  if (focus) tab.focus();
}

function renderResults(ev) {
  $('ev-avatar').textContent = initials(ev.candidate_name);
  $('ev-name').textContent = ev.candidate_name || '';
  $('ev-score').textContent = ev.overall_score ?? '–';
  $('ev-summary').textContent = ev.summary || '';
  renderStrengthsAndWeaknesses(ev);
  selectTab(TABS[0]);
  renderPriorities(ev);
  showAllRecs(false);
  $('ev-apply').disabled = !(ev.recommendations || []).length;
  hide($('ev-intake'));
  show($('ev-results'));
  openSummary(false);
  const sum = $('ev-summary');  // se mide ya visible: si entra en 2 líneas, no hace falta "Read more"
  $('ev-summary-more').classList.toggle('hidden', sum.scrollHeight <= sum.clientHeight);
  fitRecs();
  loadJobs();
}

async function loadJobs() {
  const box = $('ev-jobs');
  box.innerHTML = `<p class="secondary-text">${esc(t('ev.jobs_loading', 'Finding matching jobs…'))}</p>`;
  const token = localStorage.getItem(SESSION_KEY);
  const url = aurea.session || !token ? '/jobs/ranked' : `/jobs/ranked?token=${encodeURIComponent(token)}`;
  try {
    const res = await aurea.authFetch(url);
    if (!res.ok) throw new Error();
    const jobs = (await res.json()).slice(0, 4);  // 2×2 en la columna lateral
    box.innerHTML = jobs.length
      ? jobs.map(aureaRender.jobCardHtml).join('')
      : `<p class="secondary-text">${esc(t('ev.jobs_empty', 'No jobs available right now.'))}</p>`;
  } catch (_) {
    box.innerHTML = `<p class="secondary-text">${esc(t('ev.jobs_error', 'Could not load job recommendations.'))}</p>`;
  }
}

// ── Acciones pagas ────────────────────────────────────────────────────────
function jobInputError(value) {
  if (!value) return t('job.err_empty', 'Paste a job link or description.');
  if (!aurea.isUrl(value) && value.length < MIN_JD_CHARS) return t('job.err_short', 'Please paste the full job description (at least 50 characters).');
  return null;
}

function setActionsBusy(busy) {
  actionBusy = busy;
  ['ev-apply', 'ev-cover', 'ev-tailor'].forEach((id) => { $(id).disabled = busy; });
  $('ev-working').classList.toggle('hidden', !busy);
}

function runAction(action, payload) {
  hide($('ev-action-error'));
  hide($('ev-no-credits'));
  if (actionBusy) return;
  if (action !== 'improve') {
    const err = jobInputError(payload.job_input);
    if (err) return showError($('ev-action-error'), err);
  }
  if (!aurea.requireAuth(action, payload)) return;
  if (action === 'improve') return improve(payload.recommendations);
  return adapt(action === 'cover' ? 'cover' : 'both', payload.job_input);
}

async function paidJson(res) {
  if (res.status === 402) { show($('ev-no-credits')); return null; }
  if (res.status === 401) { aurea.openAuthModal('login'); return null; }
  if (!res.ok) { showError($('ev-action-error'), await errorDetail(res)); return null; }
  return res.json();
}

function goToResult(data, kind, jobInput) {
  data.kind = kind;
  data.job_input = jobInput || '';
  localStorage.setItem(RESULT_KEY, JSON.stringify(data));
  window.location.href = kind === 'cover' ? 'cover.html?result=1' : 'tailor.html?result=1';
}

async function adapt(mode, jobInput) {
  setActionsBusy(true);
  try {
    const fd = new FormData();
    fd.append('job_input', jobInput);
    fd.append('mode', mode);
    fd.append('output_language', aurea.lang);
    const data = await paidJson(await aurea.authFetch('/adapt', { method: 'POST', body: fd }));
    if (data) { goToResult(data, mode, jobInput); return; }  // navegando: dejar las acciones deshabilitadas
    setActionsBusy(false);
  } catch (_) {
    showError($('ev-action-error'), networkError());
    setActionsBusy(false);
  }
  aurea.refreshCredits();
}

async function improve(recommendations) {
  setActionsBusy(true);
  try {
    const res = await aurea.authFetch('/improve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ recommendations }),
    });
    const data = await paidJson(res);
    if (data) {
      [EVAL_KEY, ALT_KEY].forEach((k) => localStorage.removeItem(k));  // /improve cambió el CV: la evaluación ya es del viejo
      goToResult(data, 'improve', '');
      return;
    }  // navegando: dejar las acciones deshabilitadas
    setActionsBusy(false);
  } catch (_) {
    showError($('ev-action-error'), networkError());
    setActionsBusy(false);
  }
  aurea.refreshCredits();
}

// ── Eventos ───────────────────────────────────────────────────────────────
const $drop = $('ev-drop');
function intakeBusy() { return !$('ev-drop-busy').classList.contains('hidden'); }
$drop.addEventListener('click', () => { if (!intakeBusy()) $('ev-file').click(); });
$drop.addEventListener('keydown', (e) => { if ((e.key === 'Enter' || e.key === ' ') && !intakeBusy()) { e.preventDefault(); $('ev-file').click(); } });
$drop.addEventListener('dragover', (e) => { e.preventDefault(); $drop.classList.add('drop-zone--drag'); });
$drop.addEventListener('dragleave', () => $drop.classList.remove('drop-zone--drag'));
$drop.addEventListener('drop', (e) => {
  e.preventDefault();
  $drop.classList.remove('drop-zone--drag');
  if (!intakeBusy()) uploadAndEvaluate(e.dataTransfer.files[0]);
});
$('ev-file').addEventListener('change', () => { uploadAndEvaluate($('ev-file').files[0]); $('ev-file').value = ''; });
$('ev-new').addEventListener('click', showIntake);
$('ev-summary-more').addEventListener('click', (e) => openSummary(e.currentTarget.getAttribute('aria-expanded') !== 'true'));
$('ev-recs-more').addEventListener('click', (e) => showAllRecs(e.currentTarget.getAttribute('aria-expanded') !== 'true'));
new ResizeObserver(() => fitRecs()).observe($('ev-pane-fix'));
TABS.forEach((tab) => tab.addEventListener('click', () => selectTab(tab)));
document.querySelector('.ev-tabs').addEventListener('keydown', (e) => {
  const i = TABS.indexOf(document.activeElement);
  const next = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: TABS.length - 1 }[e.key];
  if (i < 0 || next === undefined) return;
  e.preventDefault();
  selectTab(TABS[(next + TABS.length) % TABS.length], true);
});
$('ev-apply').addEventListener('click', () => runAction('improve', { recommendations: ((evaluation && evaluation.recommendations) || []).slice(0, 20) }));
$('ev-cover').addEventListener('click', () => runAction('cover', { job_input: $('ev-job').value.trim() }));
$('ev-tailor').addEventListener('click', () => runAction('tailor', { job_input: $('ev-job').value.trim() }));

// ── Init ──────────────────────────────────────────────────────────────────
async function initialEvaluation() {
  if (aurea.session) {
    try {
      const res = await aurea.authFetch('/cv');
      if (res.ok) {
        const cv = await res.json();
        if (cv.last_evaluation) return cv.last_evaluation;
      }
    } catch (_) {}
  }
  try { return JSON.parse(localStorage.getItem(EVAL_KEY)); } catch (_) { return null; }
}

aurea.onReady(async () => {
  const pendingJd = localStorage.getItem(PENDING_JD_KEY);  // la limpia tailor.html al usarla
  if (pendingJd) $('ev-job').value = pendingJd;

  if (aurea.session && new URLSearchParams(window.location.search).get('reevaluate') === '1') {
    setIntakeBusy(true);
    try { await evaluate({}); } catch (e) { setIntakeBusy(false); showError($('ev-error'), e.message || networkError()); }
    return;
  }

  evaluation = await initialEvaluation();
  if (evaluation) evaluation = await inPageLanguage(evaluation);
  if (evaluation) renderResults(evaluation);

  const pending = evaluation ? aurea.takePendingAction() : null;
  if (pending) {
    if (pending.payload && pending.payload.job_input) $('ev-job').value = pending.payload.job_input;
    runAction(pending.action, pending.payload || {});
  }
});
