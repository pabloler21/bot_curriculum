// tailor.js — pantalla Tailor: form (job-form.js) + resultado del CV adaptado,
// gaps, carta (si vino de "both"), interview prep y descarga del PDF.
'use strict';

const RESULT_KEY = 'aurea_last_result';
const PENDING_JD_KEY = 'aurea_pending_jd';
const $ = (id) => document.getElementById(id);
const show = (el) => el.classList.remove('hidden');
const hide = (el) => el.classList.add('hidden');
const t = (k, f) => aurea.t(k, f);

let current = null;

// ── Animación de etapas (la duración real no se conoce: es orientativa) ────
const STAGES = [
  { id: 'pstep-extract', key: 'tailor.step_extract', label: 'Extracting structure', delay: 0 },
  { id: 'pstep-adapt', key: 'tailor.step_adapt', label: 'Adapting to role', delay: 5000 },
  { id: 'pstep-validate', key: 'tailor.step_validate', label: 'Validating output', delay: 12000 },
];
let stageTimers = [];

function startLoading() {
  hide($('tl-input-section'));
  hide($('adapt-results-section'));
  show($('adapt-loading-section'));
  STAGES.forEach((s) => $(s.id).classList.remove('active', 'done'));
  $(STAGES[0].id).classList.add('active');
  $('adapt-loading-title').textContent = t(STAGES[0].key, STAGES[0].label);
  stageTimers = STAGES.slice(1).map((s, i) => setTimeout(() => {
    $(STAGES[i].id).classList.replace('active', 'done');
    $(s.id).classList.add('active');
    $('adapt-loading-title').textContent = t(s.key, s.label);
  }, s.delay));
}

function stopLoading() {
  stageTimers.forEach(clearTimeout);
  stageTimers = [];
  hide($('adapt-loading-section'));
}

function showForm() {
  stopLoading();
  hide($('adapt-results-section'));
  show($('tl-input-section'));
}

// ── Resultado ─────────────────────────────────────────────────────────────
function renderResult(data) {
  stopLoading();
  current = data;
  const failed = data.status === 'failed_extract' || data.status === 'failed_adapt';
  if (failed || !data.adapted_schema) {
    showForm();
    $('job-error').textContent = data.status === 'failed_extract'
      ? t('tailor.err_extract', 'Could not read your CV. Please use a PDF with selectable text or a DOCX file.')
      : t('tailor.err_adapt', 'Could not adapt your CV for this role. Your credits were restored — try again.');
    show($('job-error'));
    return;
  }

  const isImprove = data.kind === 'improve';
  $('tl-cv-title').textContent = isImprove ? t('tailor.cv_title_improved', 'Improved CV') : t('tailor.cv_title', 'Adapted CV');
  const badge = aureaRender.statusBadge(data.status);
  $('adapt-status-badge').textContent = badge.text;
  $('adapt-status-badge').className = `badge ${badge.cls}`;
  $('adapt-partial-banner').classList.toggle('hidden', !(data.suspicious_bullets || []).length);
  $('adapt-cv-preview').innerHTML = aureaRender.cvPreviewHtml(data.adapted_schema, data.suspicious_bullets);
  show($('adapt-download-btn'));
  hide($('adapt-download-error'));

  // Gaps: no aplican a "Apply to my CV" (no hay JD)
  $('adapt-gaps-panel').classList.toggle('hidden', isImprove);
  const gaps = data.gaps || [];
  $('adapt-gaps-list').innerHTML = aureaRender.gapsHtml(gaps);
  $('adapt-gaps-count').textContent = gaps.length ? `${gaps.length}` : '';
  $('adapt-no-gaps').classList.toggle('hidden', gaps.length > 0);

  // Carta: solo si se pidió (kind "both")
  const wantsCover = data.kind === 'both';
  $('adapt-cover-letter-panel').classList.toggle('hidden', !wantsCover);
  $('adapt-cover-letter-text').textContent = data.cover_letter || '';
  $('adapt-no-cover').classList.toggle('hidden', !wantsCover || !!data.cover_letter);

  // Interview prep necesita la JD
  const hasJd = !!data.job_description;
  $('adapt-interview-panel').classList.toggle('hidden', !hasJd);
  resetInterview();
  if (hasJd && data.interview_questions && data.interview_questions.length) renderInterview(data.interview_questions);

  $('tl-next').classList.toggle('hidden', !(data.kind === 'cv' && data.job_input));

  hide($('tl-input-section'));
  show($('adapt-results-section'));
}

function resetInterview() {
  $('adapt-interview-list').innerHTML = '';
  hide($('adapt-interview-list'));
  show($('adapt-interview-intro'));
  hide($('adapt-interview-count'));
  hide($('adapt-interview-error'));
  $('adapt-interview-btn').disabled = false;
}

function renderInterview(questions) {
  hide($('adapt-interview-intro'));
  $('adapt-interview-list').innerHTML = aureaRender.interviewHtml(questions);
  $('adapt-interview-count').textContent = `${questions.length}`;
  show($('adapt-interview-count'));
  show($('adapt-interview-list'));
}

async function prepareInterview() {
  if (!current || !current.adapted_schema || !current.job_description) return;
  const $err = $('adapt-interview-error');
  hide($err);
  $('adapt-interview-btn').disabled = true;
  try {
    const res = await aurea.authFetch('/interview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        adapted_schema: current.adapted_schema,
        job_description: current.job_description,
        gaps: current.gaps || [],
        output_language: aurea.lang,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(res.status === 429 ? t('err.rate', 'Too many requests — please wait a minute before trying again.') : aureaRender.detailText(data.detail, t('err.server', 'Server error')));
    if (!(data.questions || []).length) throw new Error(t('tailor.no_questions', 'No questions came back. Please try again.'));
    renderInterview(data.questions);
    current.interview_questions = data.questions;
    try { localStorage.setItem(RESULT_KEY, JSON.stringify(current)); } catch (_) {}
  } catch (e) {
    $err.textContent = e.message || t('err.network', 'Network error. Check your connection and try again.');
    show($err);
  } finally {
    $('adapt-interview-btn').disabled = false;
  }
}

async function downloadPdf() {
  const btn = $('adapt-download-btn');
  hide($('adapt-download-error'));
  btn.disabled = true;
  try {
    const url = current.history_id ? `/history/${current.history_id}/pdf` : `/adapt/${current.run_id}/pdf`;
    await aureaRender.downloadPdf(url, 'aurea_cv.pdf');
  } catch (e) {
    $('adapt-download-error').textContent = e.message;
    show($('adapt-download-error'));
  } finally {
    btn.disabled = false;
  }
}

async function copyCover() {
  try {
    await navigator.clipboard.writeText($('adapt-cover-letter-text').textContent);
    $('adapt-copy-cover-btn').textContent = t('tailor.copied', '✓ Copied!');
    setTimeout(() => { $('adapt-copy-cover-btn').textContent = t('tailor.copy', 'Copy'); }, 2000);
  } catch (_) {}
}

$('adapt-reset-btn').addEventListener('click', showForm);
$('adapt-download-btn').addEventListener('click', downloadPdf);
$('adapt-interview-btn').addEventListener('click', prepareInterview);
$('adapt-copy-cover-btn').addEventListener('click', copyCover);
$('tl-cover-link').addEventListener('click', () => {
  if (current && current.job_input) localStorage.setItem(PENDING_JD_KEY, current.job_input);
});

aurea.onReady(() => {
  initJobForm({ mode: 'cv', onStart: startLoading, onResult: renderResult, onFail: showForm });
  if (new URLSearchParams(window.location.search).get('result') === '1') {
    try {
      const saved = JSON.parse(localStorage.getItem(RESULT_KEY));
      if (saved && saved.kind !== 'cover') renderResult(saved);
    } catch (_) {}
  }
});
