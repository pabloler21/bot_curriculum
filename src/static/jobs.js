// src/static/jobs.js

const BACKEND_URL = window.location.hostname === 'bot-curriculum-1.onrender.com'
  ? 'https://bot-curriculum.onrender.com'
  : '';

const jobsGrid     = document.getElementById('jobs-grid');
const loadingEl    = document.getElementById('loading-jobs');
const errorEl      = document.getElementById('error-jobs');
const sortDateBtn  = document.getElementById('sort-date');
const sortScoreBtn = document.getElementById('sort-score');

let allJobs = [];
let currentSort = 'date';   // 'date' | 'score'
let scoresByJobId = {};      // populated in Phase 3

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

  article.innerHTML = `
    <div class="job-card-header">
      <h2 class="job-title">${escHtml(job.title)}</h2>
      <span class="score-badge" aria-label="Match score" aria-hidden="true"></span>
    </div>
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
        aria-label="See your match for ${escHtml(job.title)}"
      >See your match →</a>
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
  jobs.forEach((job, i) => jobsGrid.appendChild(renderJobCard(job, i)));
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

// ── Fetch ──────────────────────────────────────────────────────────────────

async function loadJobs() {
  loadingEl.classList.remove('hidden');
  errorEl.classList.add('hidden');
  jobsGrid.innerHTML = '';

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

loadJobs();
