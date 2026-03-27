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

let selectedFile = null;

// ── Drag & Drop ───────────────────────────────────────────────────────────────

dropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});

dropZone.addEventListener('dragleave', () => {
  dropZone.classList.remove('drag-over');
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
    showError('Solo se aceptan archivos PDF o DOCX.');
    return;
  }
  selectedFile = file;
  fileNameEl.textContent = file.name;
  fileNameEl.classList.remove('hidden');
  analyzeBtn.classList.remove('hidden');
  hideError();
}

// ── Analyze ───────────────────────────────────────────────────────────────────

analyzeBtn.addEventListener('click', async () => {
  if (!selectedFile) return;

  setLoading(true);
  hideError();

  const formData = new FormData();
  formData.append('file', selectedFile);

  try {
    const response = await fetch('/evaluate', {
      method: 'POST',
      body: formData,
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || `Error ${response.status}`);
    }

    renderResults(data);
    showResults();
  } catch (err) {
    setLoading(false);
    showError(err.message);
  }
});

// ── State helpers ─────────────────────────────────────────────────────────────

function setLoading(active) {
  if (active) {
    uploadSection.classList.add('hidden');
    loadingSection.classList.remove('hidden');
  } else {
    loadingSection.classList.add('hidden');
    uploadSection.classList.remove('hidden');
  }
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

function renderResults(data) {
  // Panel 1 — Score + Verdict
  const scoreCircle = document.getElementById('score-circle');
  document.getElementById('score-value').textContent = data.overall_score;
  scoreCircle.classList.remove('score-high', 'score-low');
  scoreCircle.classList.add(data.approved ? 'score-high' : 'score-low');

  document.getElementById('candidate-name').textContent = data.candidate_name;

  const badge = document.getElementById('verdict-badge');
  badge.textContent = data.approved ? 'APROBADO' : 'RECHAZADO';
  badge.className   = 'badge ' + (data.approved ? 'approved' : 'rejected');

  // Panel 2 — Resumen
  document.getElementById('summary-text').textContent = data.summary;

  // Panel 3 — Keywords Encontradas
  document.getElementById('keywords-found').innerHTML =
    data.keywords_found.map(k => `<span class="tag found">${k}</span>`).join('');

  // Panel 4 — Keywords Faltantes
  document.getElementById('keywords-missing').innerHTML =
    data.keywords_missing.map(k => `<span class="tag missing">${k}</span>`).join('');

  // Panel 5 — Problemas de Formato
  document.getElementById('formatting-issues').innerHTML =
    data.formatting_issues.map(i => `<li>${i}</li>`).join('');

  // Panel 6 — Recomendaciones
  document.getElementById('recommendations').innerHTML =
    data.recommendations.map(r => `<li>${r}</li>`).join('');
}

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
