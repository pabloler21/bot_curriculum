const BACKEND_URL = window.location.hostname === 'bot-curriculum-1.onrender.com'
  ? 'https://bot-curriculum.onrender.com'
  : '';

function sanitizeText(text) {
  return String(text)
    .replace(/\r\n/g, '\n')
    .replace(/\r/g, '\n')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n[ \t]+/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function descriptionToHtml(text) {
  const clean = sanitizeText(text);
  const paragraphs = clean
    .split(/\n{2,}/)
    .map(p => p.trim().replace(/\n/g, ' '))
    .filter(p => p.length > 0);
  return paragraphs.length
    ? paragraphs.map(p => `<p>${escHtml(p)}</p>`).join('')
    : `<p>${escHtml(clean)}</p>`;
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
          <div class="detail-desc-wrap">
            <div class="detail-description">${descriptionToHtml(job.description)}</div>
            <button class="desc-toggle" aria-expanded="false">See more ↓</button>
          </div>
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

    // Reveal element FIRST so scrollHeight is measurable
    loadingEl.classList.add('hidden');
    detailEl.classList.remove('hidden');

    // Description collapse/expand
    const descEl    = detailEl.querySelector('.detail-description');
    const toggleBtn = detailEl.querySelector('.desc-toggle');
    const COLLAPSED = 150;

    if (descEl && toggleBtn) {
      const naturalH = descEl.scrollHeight;
      if (naturalH <= COLLAPSED + 24) {
        toggleBtn.hidden = true;
      } else {
        // Collapse instantly (transition not yet active)
        descEl.style.maxHeight       = COLLAPSED + 'px';
        descEl.style.webkitMaskImage = 'linear-gradient(to bottom, black 50%, transparent 100%)';
        descEl.style.maskImage       = 'linear-gradient(to bottom, black 50%, transparent 100%)';

        // Enable transition after first paint so initial collapse is instant
        requestAnimationFrame(() => {
          descEl.style.transition = 'max-height 0.4s cubic-bezier(0.22, 1, 0.36, 1)';
        });

        toggleBtn.addEventListener('click', () => {
          const expanded = toggleBtn.getAttribute('aria-expanded') === 'true';
          if (expanded) {
            descEl.style.maxHeight       = COLLAPSED + 'px';
            descEl.style.webkitMaskImage = 'linear-gradient(to bottom, black 50%, transparent 100%)';
            descEl.style.maskImage       = 'linear-gradient(to bottom, black 50%, transparent 100%)';
            toggleBtn.setAttribute('aria-expanded', 'false');
            toggleBtn.textContent = 'See more ↓';
          } else {
            descEl.style.maxHeight       = naturalH + 'px';
            descEl.style.webkitMaskImage = 'none';
            descEl.style.maskImage       = 'none';
            toggleBtn.setAttribute('aria-expanded', 'true');
            toggleBtn.textContent = 'See less ↑';
          }
        });
      }
    }
  } catch (err) {
    loadingEl.classList.add('hidden');
    errorEl.textContent = err instanceof TypeError
      ? 'Could not connect to the server.'
      : err.message;
    errorEl.classList.remove('hidden');
  }
}

loadJobDetail();
