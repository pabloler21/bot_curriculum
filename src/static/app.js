const BACKEND_URL = window.location.hostname === 'bot-curriculum-1.onrender.com'
  ? 'https://bot-curriculum.onrender.com'
  : '';

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
  if (!selectedFile) return;

  setLoading(true);
  hideError();

  await waitForServer();
  setLoadingMessage('Analyzing your resume...');

  const formData = new FormData();
  formData.append('file', selectedFile);

  try {
    const response = await fetch(`${BACKEND_URL}/evaluate`, {
      method: 'POST',
      body: formData,
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
    uploadSection.classList.add('hidden');
    loadingSection.classList.remove('hidden');
    setLoadingMessage('Analyzing your resume...');
  } else {
    loadingSection.classList.add('hidden');
    uploadSection.classList.remove('hidden');
  }
}

function setLoadingMessage(msg) {
  loadingText.textContent = msg;
}

function showResults() {
  loadingSection.classList.add('hidden');
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

function escHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

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

// ── Reset ─────────────────────────────────────────────────────────────────────

resetBtn.addEventListener('click', () => {
  selectedFile      = null;
  fileInput.value   = '';
  fileNameEl.classList.add('hidden');
  analyzeBtn.classList.add('hidden');
  hideError();
  resultsSection.classList.add('hidden');
  uploadSection.classList.remove('hidden');
});
