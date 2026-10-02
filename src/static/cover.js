// cover.js — pantalla Cover: form (job-form.js, mode=cover) + la carta.
'use strict';

const RESULT_KEY = 'aurea_last_result';
const PENDING_JD_KEY = 'aurea_pending_jd';
const $ = (id) => document.getElementById(id);
const show = (el) => el.classList.remove('hidden');
const hide = (el) => el.classList.add('hidden');
const t = (k, f) => aurea.t(k, f);

let current = null;

function startLoading() { hide($('cv-input-section')); hide($('cv-result')); show($('cv-loading')); }
function showForm() { hide($('cv-loading')); hide($('cv-result')); show($('cv-input-section')); }

function renderResult(data) {
  hide($('cv-loading'));
  if (data.status !== 'completed' || !data.cover_letter) {
    showForm();
    $('job-error').textContent = t('cover.err', 'Could not write the cover letter. Your credit was restored — try again.');
    show($('job-error'));
    return;
  }
  current = data;
  $('cv-letter').textContent = data.cover_letter;
  hide($('cv-input-section'));
  show($('cv-result'));
}

$('cv-reset').addEventListener('click', showForm);
$('cv-copy').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(current.cover_letter);
    $('cv-copy').textContent = t('tailor.copied', '✓ Copied!');
    setTimeout(() => { $('cv-copy').textContent = t('tailor.copy', 'Copy'); }, 2000);
  } catch (_) {}
});
$('cv-download').addEventListener('click', () => aureaRender.downloadText(current.cover_letter, 'aurea_cover_letter.txt'));
$('cv-tailor-link').addEventListener('click', () => {
  if (current && current.job_input) localStorage.setItem(PENDING_JD_KEY, current.job_input);
});

aurea.onReady(() => {
  initJobForm({ mode: 'cover', onStart: startLoading, onResult: renderResult, onFail: showForm });
  if (new URLSearchParams(window.location.search).get('result') === '1') {
    try {
      const saved = JSON.parse(localStorage.getItem(RESULT_KEY));
      if (saved && saved.kind === 'cover') renderResult(saved);
    } catch (_) {}
  }
});
