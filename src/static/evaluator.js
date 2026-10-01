// evaluator.js — funnel de onboarding (spec §5): upload → analizando → resultados,
// y las acciones pagas (Apply / Cover / Tailor) detrás de aurea.requireAuth().
'use strict';

const SESSION_KEY = 'cv_session_token';
const CLAIMED_KEY = 'aurea_claimed_token';
const EVAL_KEY = 'aurea_last_evaluation';
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
function setIntakeBusy(busy) {
  $('ev-drop-idle').classList.toggle('hidden', busy);
  $('ev-drop-busy').classList.toggle('hidden', !busy);
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
  const res = await aurea.authFetch('/evaluate', { method: 'POST', headers, body: new FormData() });
  if (!res.ok) throw new Error(await errorDetail(res));
  evaluation = await res.json();
  try { localStorage.setItem(EVAL_KEY, JSON.stringify(evaluation)); } catch (_) {}
  renderResults(evaluation);
}

// ── Estado 3 ──────────────────────────────────────────────────────────────
function initials(name) {
  return (name || '?').split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join('');
}

function listHtml(items) { return items.map((i) => `<li>${esc(i)}</li>`).join(''); }

function renderResults(ev) {
  $('ev-avatar').textContent = initials(ev.candidate_name);
  $('ev-name').textContent = ev.candidate_name || '';
  $('ev-score').textContent = ev.overall_score ?? '–';
  $('ev-summary').textContent = ev.summary || '';
  $('ev-strengths').innerHTML = listHtml(ev.strengths || []);
  const missing = (ev.keywords_missing || []).map((k) => `${t('ev.missing_kw', 'Missing keyword')}: ${k}`);
  $('ev-weaknesses').innerHTML = listHtml([...(ev.weaknesses || []), ...(ev.formatting_issues || []), ...missing]);
  $('ev-recs').innerHTML = listHtml(ev.recommendations || []);
  $('ev-apply').disabled = !(ev.recommendations || []).length;
  hide($('ev-intake'));
  show($('ev-results'));
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
    const jobs = (await res.json()).slice(0, 6);
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
    if (data) { goToResult(data, 'improve', ''); return; }  // navegando: dejar las acciones deshabilitadas
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
  if (evaluation) renderResults(evaluation);

  const pending = evaluation ? aurea.takePendingAction() : null;
  if (pending) {
    if (pending.payload && pending.payload.job_input) $('ev-job').value = pending.payload.job_input;
    runAction(pending.action, pending.payload || {});
  }
});
