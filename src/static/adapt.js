// adapt.js — Aurea CV Adapter frontend logic
// Handles: session detection, file upload, JD input, pipeline submission,
// result rendering (CV preview + gaps + cover letter), PDF download.

'use strict';

// ── Config ────────────────────────────────────────────────────────────────────
const BACKEND_URL = (() => {
  if (typeof window !== 'undefined' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
    return 'https://bot-curriculum.onrender.com';
  }
  return '';
})();

const SESSION_KEY = 'cv_session_token';
const MAX_JD_CHARS = 8000;
const MIN_JD_CHARS = 50;

// ── Auth state ────────────────────────────────────────────────────────────────
let authToken = null;
let _supabaseClient = null;
let _pendingAdaptation = false;

// ── State ─────────────────────────────────────────────────────────────────────
let cvSessionToken = null;
let selectedFile = null;
let selectedLang = 'en';
let currentRunId = null;

// ── DOM refs ──────────────────────────────────────────────────────────────────
const $inputSection    = document.getElementById('adapt-input-section');
const $loadingSection  = document.getElementById('adapt-loading-section');
const $resultsSection  = document.getElementById('adapt-results-section');

const $sessionChip     = document.getElementById('adapt-session-chip');
const $sessionName     = document.getElementById('adapt-session-name');
const $sessionChange   = document.getElementById('adapt-session-change');

const $uploadSection   = document.getElementById('adapt-upload-section');
const $dropZone        = document.getElementById('adapt-drop-zone');
const $fileInput       = document.getElementById('adapt-file-input');
const $selectBtn       = document.getElementById('adapt-select-btn');
const $fileName        = document.getElementById('adapt-file-name');
const $uploadError     = document.getElementById('adapt-upload-error');

const $jdInput         = document.getElementById('adapt-jd-input');
const $jdError         = document.getElementById('adapt-jd-error');

const $langEn          = document.getElementById('lang-en');
const $langEs          = document.getElementById('lang-es');

const $adaptBtn        = document.getElementById('adapt-btn');
const $globalError     = document.getElementById('adapt-global-error');
const $noCreditsBanner = document.getElementById('adapt-no-credits-banner');

const $resetBtn        = document.getElementById('adapt-reset-btn');
const $downloadBtn     = document.getElementById('adapt-download-btn');

const $partialBanner   = document.getElementById('adapt-partial-banner');
const $statusBadge     = document.getElementById('adapt-status-badge');
const $cvPreview       = document.getElementById('adapt-cv-preview');
const $gapsList        = document.getElementById('adapt-gaps-list');
const $gapsCount       = document.getElementById('adapt-gaps-count');
const $noGaps          = document.getElementById('adapt-no-gaps');
const $coverLetterText = document.getElementById('adapt-cover-letter-text');
const $noCover         = document.getElementById('adapt-no-cover');
const $copyCoverBtn    = document.getElementById('adapt-copy-cover-btn');

const $pstepExtract    = document.getElementById('pstep-extract');
const $pstepAdapt      = document.getElementById('pstep-adapt');
const $pstepValidate   = document.getElementById('pstep-validate');
const $pstepLetter     = document.getElementById('pstep-letter');
const $loadingTitle    = document.getElementById('adapt-loading-title');

// ── Utilities ─────────────────────────────────────────────────────────────────
function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function show(el) { el.classList.remove('hidden'); }
function hide(el) { el.classList.add('hidden'); }
function showError(el, msg) { el.textContent = msg; show(el); }
function clearError(el) { el.textContent = ''; hide(el); }

// ── Session management ────────────────────────────────────────────────────────
async function checkExistingSession() {
  const token = localStorage.getItem(SESSION_KEY);
  if (!token) return;

  try {
    const res = await fetch(`${BACKEND_URL}/session/${token}`);
    if (res.ok) {
      const data = await res.json();
      cvSessionToken = token;
      showSessionChip(data.filename);
    } else {
      localStorage.removeItem(SESSION_KEY);
    }
  } catch (_) {
    // Network error: silently fall through
  }
}

function showSessionChip(filename) {
  hide($uploadSection);
  $sessionName.textContent = filename;
  show($sessionChip);
  updateAdaptBtn();
}

async function clearSession() {
  if (cvSessionToken) {
    try { await fetch(`${BACKEND_URL}/session/${cvSessionToken}`, { method: 'DELETE' }); } catch (_) {}
    localStorage.removeItem(SESSION_KEY);
  }
  cvSessionToken = null;
  selectedFile = null;
  hide($sessionChip);
  show($uploadSection);
  $fileInput.value = '';
  hide($fileName);
  clearError($uploadError);
  updateAdaptBtn();
}

// ── File handling ─────────────────────────────────────────────────────────────
function handleFile(file) {
  if (!file) return;
  const allowed = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
  const ext = file.name.split('.').pop().toLowerCase();
  if (!allowed.includes(file.type) && !['pdf', 'docx'].includes(ext)) {
    showError($uploadError, 'Only PDF and DOCX files are supported.');
    return;
  }
  if (file.size > 5 * 1024 * 1024) {
    showError($uploadError, 'File exceeds the 5 MB limit.');
    return;
  }
  clearError($uploadError);
  selectedFile = file;
  $fileName.textContent = `✓ ${file.name}`;
  show($fileName);
  $dropZone.classList.add('drop-zone--has-file');
  updateAdaptBtn();
}

$selectBtn.addEventListener('click', () => $fileInput.click());
$fileInput.addEventListener('change', () => handleFile($fileInput.files[0]));

$dropZone.addEventListener('dragover', (e) => { e.preventDefault(); $dropZone.classList.add('drop-zone--drag'); });
$dropZone.addEventListener('dragleave', () => $dropZone.classList.remove('drop-zone--drag'));
$dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  $dropZone.classList.remove('drop-zone--drag');
  handleFile(e.dataTransfer.files[0]);
});
$dropZone.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' || e.key === ' ') $fileInput.click();
});

$sessionChange.addEventListener('click', clearSession);

// ── Language toggle ────────────────────────────────────────────────────────────
[$langEn, $langEs].forEach(btn => {
  btn.addEventListener('click', () => {
    selectedLang = btn.dataset.lang;
    $langEn.classList.toggle('active', selectedLang === 'en');
    $langEs.classList.toggle('active', selectedLang === 'es');
    $langEn.setAttribute('aria-pressed', selectedLang === 'en');
    $langEs.setAttribute('aria-pressed', selectedLang === 'es');
  });
});

// ── Adapt button state ────────────────────────────────────────────────────────
function updateAdaptBtn() {
  const hasCV = cvSessionToken || selectedFile;
  const hasJD = $jdInput.value.trim().length >= MIN_JD_CHARS;
  $adaptBtn.disabled = !(hasCV && hasJD);
}

$jdInput.addEventListener('input', () => {
  clearError($jdError);
  updateAdaptBtn();
});

// ── Pipeline loading steps animation ─────────────────────────────────────────
const STAGES = [
  { el: $pstepExtract,  label: 'Extracting structure',     delay: 0 },
  { el: $pstepAdapt,    label: 'Adapting to role',         delay: 5000 },
  { el: $pstepValidate, label: 'Validating output',        delay: 12000 },
  { el: $pstepLetter,   label: 'Writing cover letter',     delay: 18000 },
];

let _stageTimers = [];

function startLoadingStages() {
  STAGES.forEach(s => s.el.classList.remove('active', 'done'));
  STAGES[0].el.classList.add('active');
  $loadingTitle.textContent = STAGES[0].label;

  _stageTimers = STAGES.slice(1).map((s, i) =>
    setTimeout(() => {
      STAGES[i].el.classList.remove('active');
      STAGES[i].el.classList.add('done');
      s.el.classList.add('active');
      $loadingTitle.textContent = s.label;
    }, s.delay)
  );
}

function stopLoadingStages() {
  _stageTimers.forEach(clearTimeout);
  _stageTimers = [];
}

// ── Main adapt flow ───────────────────────────────────────────────────────────
$adaptBtn.addEventListener('click', runAdaptation);

async function runAdaptation() {
  // Auth gate — show login modal if not signed in
  if (!authToken) {
    _pendingAdaptation = true;
    showAuthModal();
    return;
  }

  const jd = $jdInput.value.trim();

  // Validate JD
  if (jd.length < MIN_JD_CHARS) {
    showError($jdError, `Please paste a job description (at least ${MIN_JD_CHARS} characters).`);
    return;
  }
  if (jd.length > MAX_JD_CHARS) {
    showError($jdError, `Job description is too long. Please trim it to ${MAX_JD_CHARS} characters.`);
    return;
  }

  clearError($jdError);
  clearError($globalError);
  hide($noCreditsBanner);

  // Upload file to session if needed
  if (selectedFile && !cvSessionToken) {
    try {
      cvSessionToken = await uploadSession(selectedFile);
    } catch (err) {
      showError($uploadError, err.message);
      return;
    }
  }

  // Switch to loading state
  hide($inputSection);
  show($loadingSection);
  startLoadingStages();

  // Build form data
  const fd = new FormData();
  fd.append('job_description', jd);
  fd.append('output_language', selectedLang);
  if (selectedFile && !cvSessionToken) {
    fd.append('file', selectedFile);
  }

  const headers = { 'Authorization': `Bearer ${authToken}` };
  if (cvSessionToken) {
    headers['X-CV-Session-Token'] = cvSessionToken;
  }

  try {
    const res = await fetch(`${BACKEND_URL}/adapt`, {
      method: 'POST',
      headers,
      body: fd,
    });

    stopLoadingStages();

    if (res.status === 401) {
      authToken = null;
      hideUserArea();
      hide($loadingSection);
      show($inputSection);
      _pendingAdaptation = true;
      showAuthModal();
      return;
    }

    if (res.status === 402) {
      hide($loadingSection);
      show($inputSection);
      hide($globalError);
      show($noCreditsBanner);
      return;
    }

    const data = await res.json();

    if (!res.ok) {
      hide($loadingSection);
      show($inputSection);
      hide($noCreditsBanner);
      showError($globalError, data.detail || `Server error (${res.status}). Please try again.`);
      return;
    }

    currentRunId = data.run_id;
    renderResults(data);

  } catch (err) {
    stopLoadingStages();
    hide($loadingSection);
    show($inputSection);
    showError($globalError, 'Network error. Check your connection and try again.');
  }
}

async function uploadSession(file) {
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch(`${BACKEND_URL}/session`, { method: 'POST', body: fd });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to upload CV. Try again.');
  }
  const { token } = await res.json();
  cvSessionToken = token;
  localStorage.setItem(SESSION_KEY, token);
  return token;
}

// ── Result rendering ──────────────────────────────────────────────────────────
function renderResults(data) {
  hide($loadingSection);

  const status = data.status;
  const schema = data.adapted_schema;

  // Status badge
  const badgeMap = {
    completed: { text: 'Completed', cls: 'badge-success' },
    partial:   { text: 'Partial — review flagged items', cls: 'badge-warning' },
    failed_extract: { text: 'Extraction failed', cls: 'badge-error' },
    failed_adapt:   { text: 'Adaptation failed', cls: 'badge-error' },
  };
  const badge = badgeMap[status] || { text: status, cls: '' };
  $statusBadge.textContent = badge.text;
  $statusBadge.className = `badge ${badge.cls}`;

  // Handle hard failures
  if (status === 'failed_extract' || status === 'failed_adapt') {
    show($inputSection);
    const msg = status === 'failed_extract'
      ? 'Could not read your CV. Please use a PDF with selectable text or a DOCX file.'
      : 'Could not adapt your CV for this role. Try again or paste a different job description.';
    showError($globalError, msg);
    return;
  }

  // Partial warning
  if (status === 'partial' && data.suspicious_bullets?.length > 0) {
    show($partialBanner);
  } else {
    hide($partialBanner);
  }

  // CV Preview
  if (schema) {
    $cvPreview.innerHTML = renderCVPreview(schema, data.suspicious_bullets || []);
  }

  // PDF download button
  if (currentRunId && schema) {
    show($downloadBtn);
  } else {
    hide($downloadBtn);
  }

  // Gaps
  renderGaps(data.gaps || []);

  // Cover letter
  if (data.cover_letter) {
    hide($noCover);
    $coverLetterText.textContent = data.cover_letter;
    show(document.getElementById('adapt-cover-letter-panel'));
  } else {
    hide($coverLetterText);
    show($noCover);
  }

  show($resultsSection);
}

function renderCVPreview(schema, suspiciousBullets) {
  const suspicious = new Set(suspiciousBullets);

  let html = `
    <div class="cv-preview-header">
      <h2 class="cv-preview-name">${escHtml(schema.candidate_name)}</h2>
      ${schema.contact_info ? `<p class="cv-preview-contact">${escHtml(schema.contact_info)}</p>` : ''}
    </div>`;

  if (schema.summary) {
    html += `
      <div class="cv-section">
        <h4 class="cv-section-title">Professional Summary</h4>
        <p class="cv-summary">${escHtml(schema.summary)}</p>
      </div>`;
  }

  if (schema.experiences?.length) {
    html += `<div class="cv-section"><h4 class="cv-section-title">Experience</h4>`;
    for (const exp of schema.experiences) {
      const dateRange = exp.end_date ? `${exp.start_date} – ${exp.end_date}` : `${exp.start_date} – Present`;
      html += `
        <div class="cv-exp-block">
          <div class="cv-exp-header">
            <span class="cv-exp-role">${escHtml(exp.role)}</span>
            <span class="cv-exp-date">${escHtml(dateRange)}</span>
          </div>
          <span class="cv-exp-company">${escHtml(exp.company)}</span>
          <ul class="cv-bullets">`;
      for (const bullet of exp.bullets) {
        const isSuspicious = suspicious.has(bullet);
        html += `<li class="cv-bullet${isSuspicious ? ' cv-bullet--suspicious' : ''}">${escHtml(bullet)}${isSuspicious ? ' <span class="suspicious-tag" title="This bullet was flagged — review carefully">⚠️</span>' : ''}</li>`;
      }
      html += `</ul></div>`;
    }
    html += `</div>`;
  }

  if (schema.skills?.length) {
    html += `
      <div class="cv-section">
        <h4 class="cv-section-title">Skills</h4>
        <div class="cv-skills-cloud">
          ${schema.skills.map(s => `<span class="cv-skill-tag">${escHtml(s)}</span>`).join('')}
        </div>
      </div>`;
  }

  if (schema.education?.length) {
    html += `<div class="cv-section"><h4 class="cv-section-title">Education</h4>`;
    for (const edu of schema.education) {
      html += `
        <div class="cv-edu-block">
          <span class="cv-exp-role">${escHtml(edu.degree)}${edu.field ? ` — ${escHtml(edu.field)}` : ''}</span>
          <span class="cv-exp-company">${escHtml(edu.institution)}${edu.year ? ` · ${escHtml(edu.year)}` : ''}</span>
        </div>`;
    }
    html += `</div>`;
  }

  if (schema.languages?.length || schema.certifications?.length) {
    html += `<div class="cv-section"><h4 class="cv-section-title">Additional</h4>`;
    if (schema.languages?.length) {
      html += `<p class="cv-additional"><strong>Languages:</strong> ${escHtml(schema.languages.join(', '))}</p>`;
    }
    if (schema.certifications?.length) {
      html += `<ul class="cv-bullets">${schema.certifications.map(c => `<li class="cv-bullet">${escHtml(c)}</li>`).join('')}</ul>`;
    }
    html += `</div>`;
  }

  return html;
}

function renderGaps(gaps) {
  if (!gaps.length) {
    hide(document.getElementById('adapt-gaps-panel').querySelector('.adapt-gaps-list'));
    $gapsCount.textContent = '';
    show($noGaps);
    return;
  }

  hide($noGaps);
  $gapsCount.textContent = `${gaps.length} gap${gaps.length !== 1 ? 's' : ''}`;

  $gapsList.innerHTML = gaps.map(gap => `
    <div class="gap-item">
      <div class="gap-item-header">
        <span class="gap-confidence gap-confidence--${gap.confidence}">${gap.confidence}</span>
        <span class="gap-requirement">${escHtml(gap.jd_requirement)}</span>
      </div>
      <p class="gap-suggestion">💡 ${escHtml(gap.suggestion)}</p>
    </div>
  `).join('');
}

// ── Download PDF ──────────────────────────────────────────────────────────────
$downloadBtn.addEventListener('click', async () => {
  if (!currentRunId) return;
  $downloadBtn.disabled = true;
  $downloadBtn.innerHTML = `<span class="spinner sm"></span> Downloading…`;

  try {
    const res = await fetch(`${BACKEND_URL}/adapt/${currentRunId}/pdf`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(err.detail || 'PDF download failed. Please try again.');
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'aurea_adapted_cv.pdf';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (_) {
    alert('Download failed. Check your connection and try again.');
  } finally {
    $downloadBtn.disabled = false;
    $downloadBtn.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
      Download PDF`;
  }
});

// ── Copy cover letter ─────────────────────────────────────────────────────────
$copyCoverBtn.addEventListener('click', async () => {
  const text = $coverLetterText.textContent;
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    const orig = $copyCoverBtn.innerHTML;
    $copyCoverBtn.textContent = '✓ Copied!';
    setTimeout(() => { $copyCoverBtn.innerHTML = orig; }, 2000);
  } catch (_) {
    alert('Could not copy to clipboard. Please select and copy manually.');
  }
});

// ── Reset ─────────────────────────────────────────────────────────────────────
$resetBtn.addEventListener('click', () => {
  hide($resultsSection);
  hide($partialBanner);
  currentRunId = null;
  $cvPreview.innerHTML = '';
  $gapsList.innerHTML = '';
  $coverLetterText.textContent = '';
  $statusBadge.textContent = '';
  $statusBadge.className = 'badge';
  clearError($globalError);
  show($inputSection);
  updateAdaptBtn();
});

// ── Auth ──────────────────────────────────────────────────────────────────────
const $authModal       = document.getElementById('auth-modal');
const $authModalBd     = document.getElementById('auth-modal-backdrop');
const $authModalClose  = document.getElementById('auth-modal-close');
const $authModalForm   = document.getElementById('auth-modal-form');
const $authModalSent   = document.getElementById('auth-modal-sent');
const $authEmailInput  = document.getElementById('auth-email-input');
const $authSendBtn     = document.getElementById('auth-send-btn');
const $authModalError  = document.getElementById('auth-modal-error');
const $authSentEmail   = document.getElementById('auth-sent-email');
const $authUserArea    = document.getElementById('auth-user-area');
const $authUserEmail   = document.getElementById('auth-user-email-display');
const $authLogoutBtn   = document.getElementById('auth-logout-btn');
const $authSigninBtn   = document.getElementById('auth-signin-btn');

function showAuthModal() {
  show($authModal);
  hide($authModalSent);
  show($authModalForm);
  clearError($authModalError);
  $authEmailInput.value = '';
  $authEmailInput.focus();
}

function hideAuthModal() {
  hide($authModal);
  _pendingAdaptation = false;
}

function showUserArea(email) {
  $authUserEmail.textContent = email;
  show($authUserArea);
  hide($authSigninBtn);
}

function hideUserArea() {
  hide($authUserArea);
  show($authSigninBtn);
}

async function initAuth() {
  let config = { supabase_url: '', supabase_anon_key: '' };
  try {
    const res = await fetch(`${BACKEND_URL}/config`);
    if (res.ok) config = await res.json();
  } catch (_) {}

  if (!config.supabase_url || !config.supabase_anon_key) return;

  _supabaseClient = window.supabase.createClient(config.supabase_url, config.supabase_anon_key);

  _supabaseClient.auth.onAuthStateChange((event, session) => {
    if (session) {
      authToken = session.access_token;
      showUserArea(session.user.email);
      if (_pendingAdaptation) {
        _pendingAdaptation = false;
        hideAuthModal();
        runAdaptation();
      }
    } else {
      authToken = null;
      hideUserArea();
    }
  });

  const { data: { session } } = await _supabaseClient.auth.getSession();
  if (session) {
    authToken = session.access_token;
    showUserArea(session.user.email);
  }
}

$authSigninBtn.addEventListener('click', showAuthModal);
$authModalClose.addEventListener('click', hideAuthModal);
$authModalBd.addEventListener('click', hideAuthModal);

$authEmailInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') $authSendBtn.click();
});

$authSendBtn.addEventListener('click', async () => {
  if (!_supabaseClient) {
    showError($authModalError, 'Auth service unavailable — restart the server and reload the page.');
    return;
  }
  const email = $authEmailInput.value.trim();
  if (!email || !/\S+@\S+\.\S+/.test(email)) {
    showError($authModalError, 'Please enter a valid email address.');
    return;
  }
  clearError($authModalError);
  $authSendBtn.disabled = true;
  $authSendBtn.textContent = 'Sending…';

  try {
    const redirectTo = window.location.href.split('#')[0];
    const { error } = await _supabaseClient.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: redirectTo },
    });
    if (error) throw error;
    $authSentEmail.textContent = email;
    hide($authModalForm);
    show($authModalSent);
  } catch (err) {
    showError($authModalError, err.message || 'Failed to send magic link. Please try again.');
  } finally {
    $authSendBtn.disabled = false;
    $authSendBtn.textContent = 'Send magic link';
  }
});

$authLogoutBtn.addEventListener('click', async () => {
  if (_supabaseClient) await _supabaseClient.auth.signOut();
  authToken = null;
  hideUserArea();
});

// ── Init ──────────────────────────────────────────────────────────────────────
(async () => {
  await initAuth();
  await checkExistingSession();
  updateAdaptBtn();
})();
