const BACKEND_URL = window.location.hostname === 'bot-curriculum-1.onrender.com'
  ? 'https://bot-curriculum.onrender.com'
  : '';

function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Job context (Phase 4) ──────────────────────────────────────────────────
const urlParams = new URLSearchParams(window.location.search);
const contextJobId = urlParams.get('job_id');
let contextJobData = null;

async function loadJobContext() {
  if (!contextJobId) return;
  try {
    const res = await fetch(`${BACKEND_URL}/jobs`);
    if (!res.ok) return;
    const jobs = await res.json();
    const job = jobs.find(j => String(j.id) === String(contextJobId));
    if (!job) return;
    contextJobData = job;
    const panel = document.getElementById('job-context-badge');
    if (panel) {
      panel.innerHTML = `
        <span class="job-context-label">Evaluating against</span>
        <span class="job-context-title">${escHtml(job.title)}</span>
        <span class="job-context-company">${escHtml(job.company)}</span>
      `;
      panel.classList.remove('hidden');
    }
  } catch { /* silently ignore */ }
}

loadJobContext();

async function checkExistingSession() {
  const token = localStorage.getItem('cv_session_token');
  if (!token) return;
  try {
    const res = await fetch(`${BACKEND_URL}/session/${encodeURIComponent(token)}`);
    if (!res.ok) {
      localStorage.removeItem('cv_session_token');
      return;
    }
    const data = await res.json();
    sessionPreloaded = true;
    sessionChipName.textContent = data.filename;
    sessionChip.classList.remove('hidden');
    dropZone.classList.add('hidden');
    analyzeBtn.classList.remove('hidden');
  } catch {
    // Server unreachable — degrade gracefully, show normal dropzone
  }
}

checkExistingSession();

const dropZone       = document.getElementById('drop-zone');
const fileInput      = document.getElementById('file-input');
const fileNameEl     = document.getElementById('file-name');
const selectBtn      = document.getElementById('select-btn');
const analyzeBtn     = document.getElementById('analyze-btn');
const errorMsg       = document.getElementById('error-msg');
const uploadSection  = document.getElementById('upload-section');
const loadingSection = document.getElementById('loading-section');
const resultsSection = document.getElementById('results-section');
const resetBtn       = document.getElementById('reset-btn');
const loadingText    = document.querySelector('#loading-section .loading-text');
const evaluatorLayout = document.querySelector('.evaluator-layout');
const sessionChip       = document.getElementById('session-chip');
const sessionChipName   = document.getElementById('session-chip-name');
const sessionChipChange = document.getElementById('session-chip-change');

let sessionPreloaded = false;

let selectedFile = null;

// ── Drag & Drop ───────────────────────────────────────────────────────────────

dropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});

dropZone.addEventListener('dragleave', (e) => {
  if (!dropZone.contains(e.relatedTarget)) {
    dropZone.classList.remove('drag-over');
  }
});

dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) handleFile(file);
});

// ── Click to select ───────────────────────────────────────────────────────────

selectBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  fileInput.click();
});

dropZone.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) handleFile(fileInput.files[0]);
});

// ── File validation ───────────────────────────────────────────────────────────

function handleFile(file) {
  const ext = file.name.split('.').pop().toLowerCase();
  if (!['pdf', 'docx'].includes(ext)) {
    showError('Only PDF or DOCX files are accepted.');
    return;
  }
  selectedFile = file;
  fileNameEl.textContent = file.name;
  fileNameEl.classList.remove('hidden');
  analyzeBtn.classList.remove('hidden');
  hideError();
}

// ── Wakeup polling ────────────────────────────────────────────────────────────

const HEALTH_TIMEOUT_MS = 5000;
const POLL_INTERVAL_MS  = 3000;

async function waitForServer() {
  while (true) {
    try {
      const controller = new AbortController();
      const timeoutId  = setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS);
      const res        = await fetch(`${BACKEND_URL}/health`, { signal: controller.signal });
      clearTimeout(timeoutId);
      if (res.ok) return;
    } catch (_) {
      // server not responding yet — fall through to show waking message
    }
    setLoadingMessage(
      'The server was inactive and is waking up. This may take ~30 seconds, please wait...'
    );
    await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL_MS));
  }
}

// ── Analyze ───────────────────────────────────────────────────────────────────

analyzeBtn.addEventListener('click', async () => {
  if (!selectedFile && !sessionPreloaded) return;

  setLoading(true);
  hideError();

  await waitForServer();
  setLoadingMessage('Analyzing your resume, this may take a few seconds...');

  // If a new file is being uploaded, create/refresh the session in background
  // so it's available on the Job Board when the user navigates there after analysis
  if (selectedFile) {
    const sessionFormData = new FormData();
    sessionFormData.append('file', selectedFile);
    fetch(`${BACKEND_URL}/session`, { method: 'POST', body: sessionFormData })
      .then(res => res.ok ? res.json() : null)
      .then(data => { if (data?.token) localStorage.setItem('cv_session_token', data.token); })
      .catch(() => {});
  }

  const formData = new FormData();
  if (selectedFile) {
    formData.append('file', selectedFile);
  }
  if (contextJobId) formData.append('job_id', contextJobId);

  const cvToken = localStorage.getItem('cv_session_token');
  try {
    const response = await fetch(`${BACKEND_URL}/evaluate`, {
      method: 'POST',
      body: formData,
      headers: cvToken ? { 'X-CV-Session-Token': cvToken } : {},
    });

    if (!response.ok) {
      let detail = `Error ${response.status}`;
      try {
        const errData = await response.json();
        detail = errData.detail || detail;
      } catch (_) { /* non-JSON error body */ }
      throw new Error(detail);
    }

    const data = await response.json();
    renderResults(data);
    showResults();
  } catch (err) {
    setLoading(false);
    const isNetworkError = err instanceof TypeError && err.message === 'Failed to fetch';
    showError(isNetworkError ? 'Could not connect to the server. Check your connection.' : err.message);
  }
});

// ── State helpers ─────────────────────────────────────────────────────────────

function setLoading(active) {
  if (active) {
    evaluatorLayout.classList.add('hidden');
    loadingSection.classList.remove('hidden');
    setLoadingMessage('Analyzing your resume, this may take a few seconds...');
  } else {
    loadingSection.classList.add('hidden');
    evaluatorLayout.classList.remove('hidden');
  }
}

function setLoadingMessage(msg) {
  loadingText.textContent = msg;
}

function showResults() {
  loadingSection.classList.add('hidden');
  evaluatorLayout.classList.add('hidden');
  resultsSection.classList.remove('hidden');
}

function showError(msg) {
  errorMsg.textContent = msg;
  errorMsg.classList.remove('hidden');
}

function hideError() {
  errorMsg.classList.add('hidden');
}

// ── Render results ────────────────────────────────────────────────────────────

function renderResults(data) {
  // Panel 1 — Score + Verdict
  const scoreCircle = document.getElementById('score-circle');
  document.getElementById('score-value').textContent = data.overall_score;
  scoreCircle.classList.remove('score-high', 'score-low');
  scoreCircle.classList.add(data.approved ? 'score-high' : 'score-low');

  document.getElementById('candidate-name').textContent = data.candidate_name;

  const badge = document.getElementById('verdict-badge');
  badge.textContent = data.approved ? 'APPROVED' : 'REJECTED';
  badge.className   = 'badge ' + (data.approved ? 'approved' : 'rejected');

  // Panel 2 — Resumen
  document.getElementById('summary-text').textContent = data.summary;

  // Panel 3 — Keywords Encontradas
  document.getElementById('keywords-found').innerHTML =
    data.keywords_found.map(k => `<span class="tag found">${escHtml(k)}</span>`).join('');

  // Panel 4 — Keywords Faltantes
  document.getElementById('keywords-missing').innerHTML =
    data.keywords_missing.map(k => `<span class="tag missing">${escHtml(k)}</span>`).join('');

  // Panel 5 — Problemas de Formato
  document.getElementById('formatting-issues').innerHTML =
    data.formatting_issues.map(i => `<li>${escHtml(i)}</li>`).join('');

  // Panel 6 — Recomendaciones
  document.getElementById('recommendations').innerHTML =
    data.recommendations.map(r => `<li>${escHtml(r)}</li>`).join('');
}

// ── Copy buttons ─────────────────────────────────────────────────────────────

document.querySelectorAll('.copy-btn').forEach(btn => {
  btn.addEventListener('click', async (e) => {
    e.stopPropagation();
    const el = document.getElementById(btn.dataset.copyTarget);
    try {
      await navigator.clipboard.writeText(el.innerText.trim());
      btn.textContent = '✓ copied';
      btn.classList.add('copied');
      setTimeout(() => {
        btn.textContent = 'copy';
        btn.classList.remove('copied');
      }, 2000);
    } catch (_) { /* clipboard unavailable (non-HTTPS); silently ignore */ }
  });
});

// ── Session chip change ───────────────────────────────────────────────────────

sessionChipChange.addEventListener('click', () => {
  sessionPreloaded = false;
  sessionChip.classList.add('hidden');
  dropZone.classList.remove('hidden');
  analyzeBtn.classList.add('hidden');
  selectedFile    = null;
  fileInput.value = '';
  fileNameEl.classList.add('hidden');
  hideError();
});

// ── Reset ─────────────────────────────────────────────────────────────────────

resetBtn.addEventListener('click', () => {
  selectedFile      = null;
  fileInput.value   = '';
  fileNameEl.classList.add('hidden');
  analyzeBtn.classList.add('hidden');
  hideError();
  resultsSection.classList.add('hidden');
  evaluatorLayout.classList.remove('hidden');
});
