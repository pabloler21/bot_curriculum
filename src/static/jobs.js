// src/static/jobs.js

const BACKEND_URL = window.location.hostname === 'bot-curriculum-1.onrender.com'
  ? 'https://bot-curriculum.onrender.com'
  : '';

const jobsGrid     = document.getElementById('jobs-grid');
const loadingEl    = document.getElementById('loading-jobs');
const errorEl      = document.getElementById('error-jobs');
const sortDateBtn  = document.getElementById('sort-date');
const sortScoreBtn = document.getElementById('sort-score');

const cvUploadBtn  = document.getElementById('cv-upload-btn');
const cvFileInput  = document.getElementById('cv-file-input');
const cvUploadArea = document.getElementById('cv-upload-area');
const cvActiveArea = document.getElementById('cv-active-area');
const cvChipName   = document.getElementById('cv-chip-name');
const cvRemoveBtn  = document.getElementById('cv-remove-btn');
const cvError      = document.getElementById('cv-error');

let allJobs = [];
let currentSort = 'date';   // 'date' | 'score'
let scoresByJobId = {};      // populated in Phase 3
let cvSessionToken = null;
let rankingBanner = null;

// ── Format helpers ─────────────────────────────────────────────────────────

function formatDate(dateStr) {
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function safeUrl(u) {
  try {
    const parsed = new URL(u);
    return (parsed.protocol === 'https:' || parsed.protocol === 'http:') ? u : '#';
  } catch {
    return '#';
  }
}

function formatEmploymentType(type) {
  return type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function simBarClass(score) {
  if (score >= 0.6) return 'sim-high';
  if (score >= 0.4) return 'sim-mid';
  return 'sim-low';
}

function scoreBadgeClass(score) {
  if (score >= 75) return 'score-strong';
  if (score >= 50) return 'score-good';
  return 'score-weak';
}

// ── Render ─────────────────────────────────────────────────────────────────

function renderJobCard(job, index) {
  const article = document.createElement('article');
  article.className = 'job-card';
  article.setAttribute('tabindex', '0');
  article.setAttribute(
    'aria-label',
    `${escHtml(job.title)} at ${escHtml(job.company)}`
  );
  article.style.animationDelay = `${Math.min(index * 0.04, 0.4)}s`;
  article.dataset.jobId = job.id;

  const tags = job.tags
    .slice(0, 5)
    .map((t) => `<span class="tag found">${escHtml(t)}</span>`)
    .join('');

  const salaryHtml = job.salary_range
    ? `<span class="job-salary">${escHtml(job.salary_range)}</span>`
    : '';

  const simBar = (job.similarity_score != null)
    ? `<div class="similarity-bar-wrap" aria-label="Relevance: ${Math.round(job.similarity_score * 100)}%">
         <div class="similarity-bar ${simBarClass(job.similarity_score)}" style="width:${Math.round(job.similarity_score * 100)}%"></div>
       </div>`
    : '';

  article.innerHTML = `
    <div class="job-card-header">
      <h2 class="job-title">${escHtml(job.title)}</h2>
      <span class="score-badge" aria-label="Match score" aria-hidden="true"></span>
    </div>
    ${simBar}
    <div class="job-meta">
      <span class="job-company">${escHtml(job.company)}</span>
      <span class="job-meta-sep" aria-hidden="true">·</span>
      <span class="job-location">${escHtml(job.location)}</span>
      <span class="job-type-badge">${escHtml(formatEmploymentType(job.employment_type))}</span>
      ${salaryHtml}
    </div>
    ${tags ? `<div class="job-tags" aria-label="Skills">${tags}</div>` : ''}
    <p class="job-date">Posted ${formatDate(job.posted_at)}</p>
    <div class="card-actions">
      <a
        href="job-detail.html?id=${encodeURIComponent(job.id)}"
        class="btn-match"
        aria-label="See full analysis for ${escHtml(job.title)}"
      >See full analysis →</a>
      <a
        href="${safeUrl(job.url)}"
        target="_blank"
        rel="noopener noreferrer"
        class="view-original"
        aria-label="View original posting for ${escHtml(job.title)} (opens in new tab)"
        onclick="event.stopPropagation()"
      >View original posting ↗</a>
    </div>
  `;

  // Keyboard: Enter/Space activates primary CTA
  article.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      if (e.target !== article) return; // let child links/buttons handle their own events
      e.preventDefault();
      window.location.href = `job-detail.html?id=${encodeURIComponent(job.id)}`;
    }
  });

  return article;
}

function renderJobs(jobs) {
  jobsGrid.innerHTML = '';
  if (jobs.length === 0) {
    jobsGrid.innerHTML = '<p class="empty-state">No job listings available right now.</p>';
    return;
  }

  const cvActive = jobs.some(j => j.similarity_score != null);

  if (cvActive) {
    const relevant = jobs.filter(j => j.similarity_score == null || j.similarity_score >= 0.25);
    const lowRelevance = jobs.filter(j => j.similarity_score != null && j.similarity_score < 0.25);

    relevant.forEach((job, i) => jobsGrid.appendChild(renderJobCard(job, i)));

    if (lowRelevance.length > 0) {
      const toggle = document.createElement('button');
      toggle.className = 'low-relevance-toggle';
      toggle.textContent = `Show ${lowRelevance.length} low-relevance jobs`;
      toggle.setAttribute('aria-expanded', 'false');
      toggle.setAttribute('aria-controls', 'low-relevance-jobs');

      const lowSection = document.createElement('div');
      lowSection.id = 'low-relevance-jobs';
      lowSection.className = 'hidden';
      lowRelevance.forEach((job, i) => lowSection.appendChild(renderJobCard(job, relevant.length + i)));

      toggle.addEventListener('click', () => {
        const expanded = toggle.getAttribute('aria-expanded') === 'true';
        toggle.setAttribute('aria-expanded', String(!expanded));
        toggle.textContent = expanded
          ? `Show ${lowRelevance.length} low-relevance jobs`
          : `Hide ${lowRelevance.length} low-relevance jobs`;
        lowSection.classList.toggle('hidden', expanded);
      });

      jobsGrid.appendChild(toggle);
      jobsGrid.appendChild(lowSection);
    }
  } else {
    jobs.forEach((job, i) => jobsGrid.appendChild(renderJobCard(job, i)));
  }
}

// ── Sort ───────────────────────────────────────────────────────────────────

function sortedJobs() {
  const jobs = [...allJobs];
  if (currentSort === 'date') {
    jobs.sort((a, b) => new Date(b.posted_at) - new Date(a.posted_at));
  } else if (currentSort === 'score') {
    jobs.sort((a, b) => {
      const sa = scoresByJobId[a.id]?.score ?? -1;
      const sb = scoresByJobId[b.id]?.score ?? -1;
      return sb - sa;
    });
  }
  return jobs;
}

function setSort(mode) {
  currentSort = mode;
  sortDateBtn.classList.toggle('active', mode === 'date');
  sortDateBtn.setAttribute('aria-pressed', String(mode === 'date'));
  sortScoreBtn.classList.toggle('active', mode === 'score');
  sortScoreBtn.setAttribute('aria-pressed', String(mode === 'score'));
  renderJobs(sortedJobs());
}

sortDateBtn.addEventListener('click', () => setSort('date'));
sortScoreBtn.addEventListener('click', () => {
  if (!sortScoreBtn.disabled) setSort('score');
});

// ── CV Session ─────────────────────────────────────────────────────────────

function showCvChip(filename) {
  cvChipName.textContent = filename;   // textContent is safe, no escHtml needed
  cvUploadArea.classList.add('hidden');
  cvActiveArea.classList.remove('hidden');
  cvError.classList.add('hidden');
  cvError.textContent = '';
}

function showCvButton() {
  cvActiveArea.classList.add('hidden');
  cvUploadArea.classList.remove('hidden');
  cvError.classList.add('hidden');
  cvError.textContent = '';
}

function showCvError(msg) {
  cvError.textContent = msg;
  cvError.classList.remove('hidden');
}

cvUploadBtn.addEventListener('click', () => cvFileInput.click());

cvFileInput.addEventListener('change', async () => {
  const file = cvFileInput.files[0];
  if (!file) return;

  // Reset input so the same file can be re-selected
  cvFileInput.value = '';

  // Client-side validation
  const ext = file.name.split('.').pop().toLowerCase();
  if (!['pdf', 'docx'].includes(ext)) {
    showCvError('Only PDF and DOCX files are supported.');
    return;
  }
  if (file.size > 5 * 1024 * 1024) {
    showCvError('File must be under 5 MB.');
    return;
  }

  cvError.classList.add('hidden');
  cvUploadBtn.disabled = true;
  cvUploadBtn.textContent = 'Uploading…';

  try {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${BACKEND_URL}/session`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Upload failed (${res.status})`);
    }
    const data = await res.json();
    cvSessionToken = data.token;
    localStorage.setItem('cv_session_token', data.token);
    showCvChip(data.filename);
    loadRankedJobs(data.token);
  } catch (err) {
    showCvError(err instanceof TypeError
      ? 'Could not connect. Check your connection.'
      : err.message);
  } finally {
    cvUploadBtn.disabled = false;
    cvUploadBtn.textContent = 'Upload your CV';
  }
});

cvRemoveBtn.addEventListener('click', async () => {
  const token = cvSessionToken || localStorage.getItem('cv_session_token');
  if (token) {
    try {
      await fetch(`${BACKEND_URL}/session/${encodeURIComponent(token)}`, {
        method: 'DELETE',
      });
    } catch {
      // ignore network errors on removal
    }
  }
  cvSessionToken = null;
  localStorage.removeItem('cv_session_token');
  // Reset LLM scoring state
  scoresByJobId = {};
  sortScoreBtn.disabled = true;
  sortScoreBtn.title = 'Upload your CV to sort by match score';
  const scoreMore = document.getElementById('score-more-btn');
  if (scoreMore) scoreMore.remove();
  showCvButton();
  loadJobs();
});

async function restoreCvSession() {
  const token = localStorage.getItem('cv_session_token');
  if (!token) return;
  try {
    const res = await fetch(`${BACKEND_URL}/session/${encodeURIComponent(token)}`);
    if (!res.ok) {
      localStorage.removeItem('cv_session_token');
      return;
    }
    const data = await res.json();
    cvSessionToken = token;
    showCvChip(data.filename);
    loadRankedJobs(token);
  } catch {
    localStorage.removeItem('cv_session_token');
  }
}

// ── Ranking banner ─────────────────────────────────────────────────────────

function showRankingBanner(count) {
  if (!rankingBanner) {
    rankingBanner = document.createElement('p');
    rankingBanner.className = 'ranking-banner';
    jobsGrid.parentNode.insertBefore(rankingBanner, jobsGrid);
  }
  rankingBanner.textContent = `Showing ${count} jobs ranked by relevance to your CV.`;
  rankingBanner.classList.remove('hidden');
}

function hideRankingBanner() {
  if (rankingBanner) rankingBanner.classList.add('hidden');
}

// ── Fetch ──────────────────────────────────────────────────────────────────

async function loadJobs() {
  loadingEl.classList.remove('hidden');
  errorEl.classList.add('hidden');
  jobsGrid.innerHTML = '';
  hideRankingBanner();

  try {
    const res = await fetch(`${BACKEND_URL}/jobs`);
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Error ${res.status}`);
    }
    allJobs = await res.json();
    loadingEl.classList.add('hidden');
    renderJobs(sortedJobs());
  } catch (err) {
    loadingEl.classList.add('hidden');
    errorEl.textContent = err instanceof TypeError
      ? 'Could not connect to the server. Check your connection.'
      : err.message;
    errorEl.classList.remove('hidden');
  }
}

async function loadRankedJobs(token) {
  loadingEl.classList.remove('hidden');
  errorEl.classList.add('hidden');
  jobsGrid.innerHTML = '';
  hideRankingBanner();

  try {
    const res = await fetch(`${BACKEND_URL}/jobs/ranked?token=${encodeURIComponent(token)}`);
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Error ${res.status}`);
    }
    allJobs = await res.json();
    loadingEl.classList.add('hidden');
    const rankedCount = allJobs.filter(j => j.similarity_score != null).length;
    if (rankedCount > 0) showRankingBanner(rankedCount);
    renderJobs(allJobs);
    // Start background LLM scoring — do not await, progressive enhancement
    startBackgroundScoring(token);
  } catch (err) {
    loadingEl.classList.add('hidden');
    errorEl.textContent = err instanceof TypeError
      ? 'Could not connect to the server. Check your connection.'
      : err.message;
    errorEl.classList.remove('hidden');
  }
}

async function startBackgroundScoring(token) {
  // Show skeleton badges on top 8 cards
  const topCards = Array.from(jobsGrid.querySelectorAll('.job-card')).slice(0, 8);
  topCards.forEach(card => {
    const badge = card.querySelector('.score-badge');
    if (badge) {
      badge.textContent = '—';
      badge.style.display = 'flex';
      badge.className = 'score-badge score-loading';
    }
  });

  try {
    const res = await fetch(`${BACKEND_URL}/jobs/score`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, limit: 8 }),
    });
    if (!res.ok) {
      // Silently hide skeleton badges
      jobsGrid.querySelectorAll('.score-badge.score-loading').forEach(b => {
        b.style.display = 'none';
        b.className = 'score-badge';
      });
      return;
    }
    const results = await res.json();

    results.forEach(r => { scoresByJobId[r.job_id] = r; });

    results.forEach(r => {
      const card = jobsGrid.querySelector(`[data-job-id="${CSS.escape(String(r.job_id))}"]`);
      if (!card) return;
      const badge = card.querySelector('.score-badge');
      if (!badge) return;

      if (r.score == null) {
        badge.style.display = 'none';
        badge.className = 'score-badge';
        return;
      }

      // Animate counter 0 → score
      let current = 0;
      badge.style.display = 'flex';
      badge.className = `score-badge ${scoreBadgeClass(r.score)}`;
      const target = r.score;
      const interval = setInterval(() => {
        current = Math.min(current + 3, target);
        badge.textContent = current;
        if (current >= target) clearInterval(interval);
      }, 20);

      // Add one_line_summary subtitle
      if (r.one_line_summary) {
        const titleEl = card.querySelector('.job-title');
        if (titleEl && !card.querySelector('.job-one-line')) {
          const summary = document.createElement('p');
          summary.className = 'job-one-line';
          summary.textContent = r.one_line_summary;
          titleEl.insertAdjacentElement('afterend', summary);
        }
      }

      // Highlight matched skills
      if (r.matched_skills && r.matched_skills.length > 0) {
        card.querySelectorAll('.tag').forEach(tag => {
          const tagText = tag.textContent.toLowerCase();
          if (r.matched_skills.some(s => tagText.includes(s.toLowerCase()))) {
            tag.classList.add('matched');
            tag.classList.remove('found');
          }
        });
      }
    });

    // Enable "By match score" sort
    sortScoreBtn.disabled = false;
    sortScoreBtn.title = '';

    // Add "Score more jobs" button if unscored jobs remain
    const scoredCount = results.filter(r => r.score != null).length;
    if (allJobs.length > scoredCount) {
      addScoreMoreButton(scoredCount);
    }

  } catch {
    // Silently fail — progressive enhancement
    jobsGrid.querySelectorAll('.score-badge.score-loading').forEach(b => {
      b.style.display = 'none';
      b.className = 'score-badge';
    });
  }
}

function addScoreMoreButton(alreadyScored) {
  const existing = document.getElementById('score-more-btn');
  if (existing) existing.remove();

  const btn = document.createElement('button');
  btn.id = 'score-more-btn';
  btn.className = 'score-more-btn';
  btn.textContent = 'Score more jobs';
  btn.setAttribute('aria-label', 'Score more jobs with your CV');

  btn.addEventListener('click', async () => {
    const token = cvSessionToken || localStorage.getItem('cv_session_token');
    if (!token) return;
    btn.disabled = true;
    btn.textContent = 'Scoring…';
    try {
      const res = await fetch(`${BACKEND_URL}/jobs/score`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, limit: 12 }),
      });
      if (!res.ok) { btn.disabled = false; btn.textContent = 'Score more jobs'; return; }
      const results = await res.json();
      results.forEach(r => { scoresByJobId[r.job_id] = r; });
      results.slice(alreadyScored).forEach(r => {
        const card = jobsGrid.querySelector(`[data-job-id="${CSS.escape(String(r.job_id))}"]`);
        if (!card || r.score == null) return;
        const badge = card.querySelector('.score-badge');
        if (badge) {
          badge.textContent = r.score;
          badge.style.display = 'flex';
          badge.className = `score-badge ${scoreBadgeClass(r.score)}`;
        }
      });
      btn.remove();
    } catch {
      btn.disabled = false;
      btn.textContent = 'Score more jobs';
    }
  });

  jobsGrid.insertAdjacentElement('afterend', btn);
}

restoreCvSession();
loadJobs();
