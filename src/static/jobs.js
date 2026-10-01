// jobs.js — My Jobs (historial de generaciones) + Recommended jobs (ranker vs CV base).
'use strict';

const $ = (id) => document.getElementById(id);
const t = (k, f) => aurea.t(k, f);
const esc = (s) => aurea.escHtml(s);

const KIND_CHIPS = { cv: ['CV'], cover: ['Cover'], both: ['CV', 'Cover'], improve: ['CV'] };

function kindTitle(kind) {
  return kind === 'improve' ? t('jobs.kind_improve', 'CV improvement') : t('jobs.kind_untitled', 'Untitled job');
}

function safeUrl(u) {
  try { const url = new URL(u); return ['http:', 'https:'].includes(url.protocol) ? url.href : null; } catch (_) { return null; }
}

function formatDate(iso) {
  try { return new Date(iso).toLocaleDateString(aurea.lang === 'es' ? 'es-AR' : 'en-US', { day: 'numeric', month: 'short', year: 'numeric' }); } catch (_) { return ''; }
}

async function loadHistory() {
  const list = $('jobs-history');
  try {
    const res = await aurea.authFetch('/history');
    if (!res.ok) throw new Error();
    const rows = await res.json();
    if (!rows.length) {
      list.innerHTML = `<li class="secondary-text">${esc(t('jobs.empty', 'Nothing yet — tailor your CV to a job and it will show up here.'))} <a href="tailor.html">${esc(t('nav.tailor', 'Tailor'))} →</a></li>`;
      return;
    }
    list.innerHTML = rows.map((r) => `
      <li><button type="button" class="history-item" data-id="${esc(r.id)}">
        <span>${esc(r.job_title || kindTitle(r.kind))}</span>
        <span class="history-meta">${esc(formatDate(r.created_at))} ${(KIND_CHIPS[r.kind] || []).map((c) => `<span class="kind-chip">${c}</span>`).join('')}</span>
      </button></li>`).join('');
  } catch (_) {
    list.innerHTML = `<li class="error-msg">${esc(t('jobs.history_error', 'Could not load your history.'))}</li>`;
  }
}

async function openDetail(id, button) {
  document.querySelectorAll('.history-item').forEach((b) => b.classList.toggle('active', b === button));
  const box = $('jobs-detail');
  box.classList.remove('hidden');
  box.innerHTML = '<div class="spinner" aria-hidden="true"></div>';
  try {
    const res = await aurea.authFetch(`/history/${encodeURIComponent(id)}`);
    if (!res.ok) throw new Error();
    const row = await res.json();
    const result = row.result || {};
    const link = row.job_url && safeUrl(row.job_url);
    let html = `<h3>${esc(row.job_title || kindTitle(row.kind))}</h3>`;
    if (link) html += `<p><a href="${esc(link)}" target="_blank" rel="noopener noreferrer">${esc(t('jobs.open_posting', 'Open job posting'))} ↗</a></p>`;
    if (row.job_description) {
      html += `<details><summary>${esc(t('jobs.jd', 'Job description'))}</summary><p class="jd-text">${esc(row.job_description)}</p></details>`;
    }
    if (result.adapted_schema) {
      html += `<div class="panel-header"><h4>${esc(t('tailor.cv_title', 'Adapted CV'))}</h4>
        <button type="button" class="btn-download" id="jobs-pdf">${esc(t('tailor.download', 'Download PDF'))}</button></div>
        <div class="adapt-cv-preview">${aureaRender.cvPreviewHtml(result.adapted_schema, result.suspicious_bullets)}</div>`;
    }
    if (result.cover_letter) {
      html += `<h4>${esc(t('tailor.cover', 'Cover Letter'))}</h4><p class="cover-letter-body">${esc(result.cover_letter)}</p>`;
    }
    box.innerHTML = html;
    const pdfBtn = $('jobs-pdf');
    if (pdfBtn) {
      pdfBtn.addEventListener('click', async () => {
        pdfBtn.disabled = true;
        try { await aureaRender.downloadPdf(`/history/${encodeURIComponent(id)}/pdf`, 'aurea_cv.pdf'); }
        catch (e) { pdfBtn.insertAdjacentHTML('afterend', `<p class="error-msg">${esc(e.message)}</p>`); }
        finally { pdfBtn.disabled = false; }
      });
    }
  } catch (_) {
    box.innerHTML = `<p class="error-msg">${esc(t('jobs.detail_error', 'Could not open this item.'))}</p>`;
  }
}

async function loadRecommended() {
  const box = $('jobs-recommended');
  box.innerHTML = `<p class="secondary-text">${esc(t('ev.jobs_loading', 'Finding matching jobs…'))}</p>`;
  try {
    const res = await aurea.authFetch('/jobs/ranked');
    if (!res.ok) throw new Error();
    const jobs = (await res.json()).slice(0, 20);
    box.innerHTML = jobs.length ? jobs.map(aureaRender.jobCardHtml).join('') : `<p class="secondary-text">${esc(t('ev.jobs_empty', 'No jobs available right now.'))}</p>`;
  } catch (_) {
    box.innerHTML = `<p class="secondary-text">${esc(t('ev.jobs_error', 'Could not load job recommendations.'))}</p>`;
  }
}

$('jobs-history').addEventListener('click', (e) => {
  const btn = e.target.closest('.history-item');
  if (btn) openDetail(btn.dataset.id, btn);
});

aurea.onReady(() => { loadHistory(); loadRecommended(); });
