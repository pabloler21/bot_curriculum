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

function safeUrl(u) {
  try {
    const parsed = new URL(u);
    return (parsed.protocol === 'https:' || parsed.protocol === 'http:') ? u : '#';
  } catch { return '#'; }
}

const loadingEl = document.getElementById('loading-detail');
const errorEl   = document.getElementById('error-detail');
const detailEl  = document.getElementById('job-detail');

const params = new URLSearchParams(window.location.search);
const jobId  = params.get('id');

async function loadJobDetail() {
  if (!jobId) {
    errorEl.textContent = 'No job ID specified.';
    errorEl.classList.remove('hidden');
    loadingEl.classList.add('hidden');
    return;
  }

  try {
    const res = await fetch(`${BACKEND_URL}/jobs`);
    if (!res.ok) throw new Error(`Error ${res.status}`);
    const jobs = await res.json();
    const job = jobs.find(j => String(j.id) === String(jobId));

    if (!job) {
      errorEl.textContent = 'Job not found.';
      errorEl.classList.remove('hidden');
      loadingEl.classList.add('hidden');
      return;
    }

    const cvToken = localStorage.getItem('cv_session_token');
    const ctaHref = cvToken
      ? `index.html?job_id=${encodeURIComponent(job.id)}`
      : null;
    const ctaText = cvToken
      ? 'See how to improve your match →'
      : 'Upload your CV to see your match score';
    const ctaHtml = cvToken
      ? `<a href="${safeUrl(ctaHref)}" class="btn-match detail-cta">${escHtml(ctaText)}</a>`
      : `<a href="jobs.html" class="btn-match detail-cta">${escHtml(ctaText)}</a>`;

    const tags = (job.tags || [])
      .map(t => `<span class="tag found">${escHtml(t)}</span>`)
      .join('');

    detailEl.innerHTML = `
      <article class="job-detail-card">
        <h2 class="job-title" style="font-size:20px">${escHtml(job.title)}</h2>
        <div class="job-meta" style="margin-bottom:8px">
          <span class="job-company">${escHtml(job.company)}</span>
          <span class="job-meta-sep" aria-hidden="true">·</span>
          <span class="job-location">${escHtml(job.location)}</span>
        </div>
        ${tags ? `<div class="job-tags" aria-label="Skills" style="margin-bottom:16px">${tags}</div>` : ''}
        <div class="job-description" style="font-size:13px;line-height:1.6;color:var(--text-secondary);white-space:pre-line;margin-bottom:24px">${escHtml(job.description)}</div>
        <div class="card-actions">
          ${ctaHtml}
          <a href="${safeUrl(job.url)}" target="_blank" rel="noopener noreferrer" class="view-original"
             aria-label="View original posting (opens in new tab)">View original posting ↗</a>
        </div>
      </article>
    `;

    loadingEl.classList.add('hidden');
    detailEl.classList.remove('hidden');
  } catch (err) {
    loadingEl.classList.add('hidden');
    errorEl.textContent = err instanceof TypeError
      ? 'Could not connect to the server.'
      : err.message;
    errorEl.classList.remove('hidden');
  }
}

loadJobDetail();
