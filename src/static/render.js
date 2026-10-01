// render.js — render compartido de resultados (CV adaptado, gaps, interview,
// job cards) y descargas. Funciones puras que devuelven HTML ya escapado.
'use strict';

(function () {
  const esc = (s) => window.aurea.escHtml(s);
  const t = (k, f) => window.aurea.t(k, f);

  const BADGES = {
    completed: { key: 'result.badge_completed', text: 'Completed', cls: 'badge-success' },
    partial: { key: 'result.badge_partial', text: 'Partial — review flagged items', cls: 'badge-warning' },
    failed_extract: { key: 'result.badge_failed_extract', text: 'Extraction failed', cls: 'badge-error' },
    failed_adapt: { key: 'result.badge_failed_adapt', text: 'Adaptation failed', cls: 'badge-error' },
  };

  function statusBadge(status) {
    const b = BADGES[status];
    return b ? { text: t(b.key, b.text), cls: b.cls } : { text: status || '', cls: '' };
  }

  function cvPreviewHtml(schema, suspiciousBullets) {
    const suspicious = new Set(suspiciousBullets || []);
    let html = `
      <div class="cv-preview-header">
        <h2 class="cv-preview-name">${esc(schema.candidate_name)}</h2>
        ${schema.contact_info ? `<p class="cv-preview-contact">${esc(schema.contact_info)}</p>` : ''}
      </div>`;
    if (schema.summary) {
      html += `<div class="cv-section"><h4 class="cv-section-title">${esc(t('cvp.summary', 'Professional Summary'))}</h4><p class="cv-summary">${esc(schema.summary)}</p></div>`;
    }
    if (schema.experiences && schema.experiences.length) {
      html += `<div class="cv-section"><h4 class="cv-section-title">${esc(t('cvp.experience', 'Experience'))}</h4>`;
      for (const exp of schema.experiences) {
        const range = `${exp.start_date} – ${exp.end_date || t('cvp.present', 'Present')}`;
        html += `
          <div class="cv-exp-block">
            <div class="cv-exp-header"><span class="cv-exp-role">${esc(exp.role)}</span><span class="cv-exp-date">${esc(range)}</span></div>
            <span class="cv-exp-company">${esc(exp.company)}</span>
            <ul class="cv-bullets">${(exp.bullets || []).map((b) => {
              const flagged = suspicious.has(b);
              return `<li class="cv-bullet${flagged ? ' cv-bullet--suspicious' : ''}">${esc(b)}${flagged ? ` <span class="suspicious-tag" title="${esc(t('cvp.flagged', 'This bullet was flagged — review carefully'))}">⚠️</span>` : ''}</li>`;
            }).join('')}</ul>
          </div>`;
      }
      html += '</div>';
    }
    if (schema.skills && schema.skills.length) {
      html += `<div class="cv-section"><h4 class="cv-section-title">${esc(t('cvp.skills', 'Skills'))}</h4><div class="cv-skills-cloud">${schema.skills.map((s) => `<span class="cv-skill-tag">${esc(s)}</span>`).join('')}</div></div>`;
    }
    if (schema.education && schema.education.length) {
      html += `<div class="cv-section"><h4 class="cv-section-title">${esc(t('cvp.education', 'Education'))}</h4>`;
      for (const edu of schema.education) {
        html += `<div class="cv-edu-block"><span class="cv-exp-role">${esc(edu.degree)}${edu.field ? ` — ${esc(edu.field)}` : ''}</span><span class="cv-exp-company">${esc(edu.institution)}${edu.year ? ` · ${esc(edu.year)}` : ''}</span></div>`;
      }
      html += '</div>';
    }
    if ((schema.languages && schema.languages.length) || (schema.certifications && schema.certifications.length)) {
      html += `<div class="cv-section"><h4 class="cv-section-title">${esc(t('cvp.additional', 'Additional'))}</h4>`;
      if (schema.languages && schema.languages.length) {
        html += `<p class="cv-additional"><strong>${esc(t('cvp.languages', 'Languages'))}:</strong> ${esc(schema.languages.join(', '))}</p>`;
      }
      if (schema.certifications && schema.certifications.length) {
        html += `<ul class="cv-bullets">${schema.certifications.map((c) => `<li class="cv-bullet">${esc(c)}</li>`).join('')}</ul>`;
      }
      html += '</div>';
    }
    return html;
  }

  function gapsHtml(gaps) {
    return (gaps || []).map((gap) => `
      <div class="gap-item">
        <div class="gap-item-header">
          <span class="gap-confidence gap-confidence--${gap.confidence === 'hard' ? 'hard' : 'soft'}">${esc(gap.confidence)}</span>
          <span class="gap-requirement">${esc(gap.jd_requirement)}</span>
        </div>
        <p class="gap-suggestion">💡 ${esc(gap.suggestion)}</p>
      </div>`).join('');
  }

  const KIND_LABEL = { technical: ['interview.technical', 'Technical'], behavioral: ['interview.behavioral', 'Behavioral'], gap: ['interview.gap', 'Gap'] };

  function interviewHtml(questions) {
    return (questions || []).map((q) => {
      const kind = KIND_LABEL[q.kind] ? q.kind : 'technical';
      const source = q.based_on ? `<p class="interview-source">${esc(t('interview.drawn_from', 'Drawn from'))}: ${esc(q.based_on)}</p>` : '';
      return `
        <details class="interview-item">
          <summary>
            <span class="interview-kind interview-kind--${kind}">${esc(t(KIND_LABEL[kind][0], KIND_LABEL[kind][1]))}</span>
            <span class="interview-question">${esc(q.question)}</span>
          </summary>
          <div class="interview-body">
            <p class="interview-why">${esc(t('interview.why', 'Why they ask'))}: ${esc(q.why_asked)}</p>
            <p class="interview-answer">${esc(q.suggested_answer)}</p>
            ${source}
          </div>
        </details>`;
    }).join('');
  }

  function jobCardHtml(job) {
    const score = job.similarity_score != null
      ? `<span class="job-mini-score">${Math.round(job.similarity_score * 100)}% ${esc(t('jobs.match', 'match'))}</span>`
      : '';
    return `
      <a class="job-mini" href="job-detail.html?id=${encodeURIComponent(job.id)}">
        <span class="job-mini-title">${esc(job.title)}</span>
        <span class="job-mini-company">${esc(job.company)}${job.location ? ` · ${esc(job.location)}` : ''}</span>
        ${score}
      </a>`;
  }

  function saveBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  async function downloadPdf(url, filename) {
    const res = await window.aurea.authFetch(url);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(detailText(err.detail, t('result.pdf_failed', 'PDF download failed. Please try again.')));
    }
    saveBlob(await res.blob(), filename);
  }

  function downloadText(text, filename) {
    saveBlob(new Blob([text], { type: 'text/plain;charset=utf-8' }), filename);
  }

  // detail de FastAPI: string, o array de {msg,...} en un 422
  function detailText(detail, fallback) {
    if (Array.isArray(detail)) return detail.map((d) => (d && d.msg) || String(d)).join('; ') || fallback;
    return typeof detail === 'string' && detail ? detail : fallback;
  }

  window.aureaRender = { detailText, statusBadge, cvPreviewHtml, gapsHtml, interviewHtml, jobCardHtml, downloadPdf, downloadText };
})();
