// cv.js — CV base: ver cuál está activo y reemplazarlo.
'use strict';

const $ = (id) => document.getElementById(id);
const show = (el) => el.classList.remove('hidden');
const hide = (el) => el.classList.add('hidden');
const t = (k, f) => aurea.t(k, f);

async function load() {
  try {
    const res = await aurea.authFetch('/cv');
    if (!res.ok) { hide($('cvp-current')); return; }
    const cv = await res.json();
    $('cvp-file').textContent = cv.filename || t('cv.untitled', 'Your CV');
    $('cvp-source').textContent = cv.source === 'improved' ? t('cvpage.src_improved', 'Improved by Aurea') : t('cvpage.src_upload', 'Uploaded');
    $('cvp-updated').textContent = cv.updated_at ? new Date(cv.updated_at).toLocaleString(aurea.lang === 'es' ? 'es-AR' : 'en-US') : '–';
    show($('cvp-current'));
  } catch (_) {}
}

async function upload(file) {
  if (!file) return;
  hide($('cvp-ok'));
  hide($('cvp-error'));
  const ext = (file.name.split('.').pop() || '').toLowerCase();
  if (!['pdf', 'docx'].includes(ext)) { $('cvp-error').textContent = t('ev.err_type', 'Only PDF and DOCX files are supported.'); return show($('cvp-error')); }
  if (file.size > 5 * 1024 * 1024) { $('cvp-error').textContent = t('ev.err_size', 'File exceeds the 5 MB limit.'); return show($('cvp-error')); }
  show($('cvp-busy'));
  try {
    const fd = new FormData();
    fd.append('file', file);
    const res = await aurea.authFetch('/cv', { method: 'PUT', body: fd });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(aureaRender.detailText(data.detail, `${t('err.server', 'Server error')} (${res.status})`));
    show($('cvp-ok'));
    await load();
  } catch (e) {
    $('cvp-error').textContent = e.message || t('err.network', 'Network error. Check your connection and try again.');
    show($('cvp-error'));
  } finally {
    hide($('cvp-busy'));
  }
}

const $drop = $('cvp-drop');
$drop.addEventListener('click', () => $('cvp-file-input').click());
$drop.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); $('cvp-file-input').click(); } });
$drop.addEventListener('dragover', (e) => { e.preventDefault(); $drop.classList.add('drop-zone--drag'); });
$drop.addEventListener('dragleave', () => $drop.classList.remove('drop-zone--drag'));
$drop.addEventListener('drop', (e) => { e.preventDefault(); $drop.classList.remove('drop-zone--drag'); upload(e.dataTransfer.files[0]); });
$('cvp-file-input').addEventListener('change', () => { upload($('cvp-file-input').files[0]); $('cvp-file-input').value = ''; });

aurea.onReady(load);
