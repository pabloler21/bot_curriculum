// job-form.js — form compartido de Tailor y Cover: CV base, link/descripción del
// puesto, idioma de salida y POST /adapt con el modo de la página.
'use strict';

window.initJobForm = function ({ mode, onStart, onResult, onFail }) {
  const RESULT_KEY = 'aurea_last_result';
  const PENDING_JD_KEY = 'aurea_pending_jd';
  const MIN_JD_CHARS = 50;
  const $ = (id) => document.getElementById(id);
  const t = (k, f) => aurea.t(k, f);

  let outputLang = aurea.lang;
  let hasCv = false;
  let inFlight = false;

  function showError(msg) { $('job-error').textContent = msg; $('job-error').classList.remove('hidden'); }
  function clearMessages() { $('job-error').classList.add('hidden'); $('job-no-credits').classList.add('hidden'); }

  // FastAPI 422 puede devolver detail como array de {msg,...}
  function detailText(detail) {
    if (Array.isArray(detail)) return detail.map((d) => (d && d.msg) || String(d)).join('; ');
    return typeof detail === 'string' ? detail : '';
  }

  function setOutLang(lang) {
    outputLang = lang;
    [['job-out-en', 'en'], ['job-out-es', 'es']].forEach(([id, l]) => {
      $(id).classList.toggle('active', l === lang);
      $(id).setAttribute('aria-pressed', String(l === lang));
    });
  }

  async function loadCv() {
    try {
      const res = await aurea.authFetch('/cv');
      if (res.ok) {
        const cv = await res.json();
        $('job-cv-name').textContent = cv.filename || t('cv.untitled', 'Your CV');
        $('job-cv-chip').classList.remove('hidden');
        hasCv = true;
        return;
      }
    } catch (_) {}
    $('job-no-cv').classList.remove('hidden');
    $('job-submit').disabled = true;
  }

  async function submit() {
    if (inFlight) return;
    clearMessages();
    const jobInput = $('job-input').value.trim();
    if (!jobInput) return showError(t('job.err_empty', 'Paste a job link or description.'));
    if (!aurea.isUrl(jobInput) && jobInput.length < MIN_JD_CHARS) {
      return showError(t('job.err_short', 'Please paste the full job description (at least 50 characters).'));
    }
    if (!hasCv) return;

    inFlight = true;
    $('job-submit').disabled = true;
    onStart();
    try {
      const fd = new FormData();
      fd.append('job_input', jobInput);
      fd.append('mode', mode);
      fd.append('output_language', outputLang);
      const res = await aurea.authFetch('/adapt', { method: 'POST', body: fd });
      if (res.status === 402) { $('job-no-credits').classList.remove('hidden'); onFail(); return; }
      if (res.status === 401) { aurea.openAuthModal('login'); onFail(); return; }
      if (res.status === 429) { showError(t('err.rate', 'Too many requests — please wait a minute before trying again.')); onFail(); return; }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) { showError(detailText(data.detail) || `${t('err.server', 'Server error')} (${res.status})`); onFail(); return; }
      data.kind = mode;
      data.job_input = jobInput;
      try { localStorage.setItem(RESULT_KEY, JSON.stringify(data)); } catch (_) {}
      onResult(data);
    } catch (_) {
      showError(t('err.network', 'Network error. Check your connection and try again.'));
      onFail();
    } finally {
      inFlight = false;
      $('job-submit').disabled = !hasCv;
      aurea.refreshCredits();
    }
  }

  $('job-out-en').addEventListener('click', () => setOutLang('en'));
  $('job-out-es').addEventListener('click', () => setOutLang('es'));
  $('job-submit').addEventListener('click', submit);
  setOutLang(outputLang);

  const pendingJd = localStorage.getItem(PENDING_JD_KEY);
  if (pendingJd) {
    $('job-input').value = pendingJd;
    localStorage.removeItem(PENDING_JD_KEY);
  }
  loadCv();

  return { setJobInput(value) { $('job-input').value = value; } };
};
