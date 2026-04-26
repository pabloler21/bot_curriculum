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
    // Use relative URLs directly — safeUrl() rejects relative paths (no protocol)
    const ctaHref = cvToken
      ? `index.html?job_id=${encodeURIComponent(job.id)}`
      : 'index.html';
    const ctaText = cvToken
      ? 'See how to improve your match →'
      : 'Upload your CV to see your match score';
    const ctaHtml = `<a href="${escHtml(ctaHref)}" class="btn-match detail-cta">${escHtml(ctaText)}</a>`;

    const tags = (job.tags || [])
      .map(t => `<span class="tag found">${escHtml(t)}</span>`)
      .join('');

    const ctaClass = cvToken ? 'btn-match detail-cta' : 'btn-match-ghost';
    detailEl.innerHTML = `
      <div class="detail-card">
        <div class="detail-header">
          <h1 class="detail-title">${escHtml(job.title)}</h1>
          <div class="job-meta">
            <span class="job-company">${escHtml(job.company)}</span>
            <span class="job-meta-sep" aria-hidden="true">·</span>
            <span class="job-location">${escHtml(job.location)}</span>
          </div>
          ${tags ? `<div class="job-tags" aria-label="Skills" style="margin-top:12px">${tags}</div>` : ''}
        </div>
        <div class="detail-body">
          <p class="detail-description">${escHtml(job.description)}</p>
          <div class="card-actions">
            <a href="${safeUrl(job.url)}" target="_blank" rel="noopener noreferrer" class="view-original"
               aria-label="View original posting (opens in new tab)">View original posting ↗</a>
          </div>
        </div>
      </div>
      <div class="detail-cta-wrap">
        <a href="${escHtml(ctaHref)}" class="${ctaClass}">${escHtml(ctaText)}</a>
      </div>
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
