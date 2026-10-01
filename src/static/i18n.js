// i18n.js — traducción EN → ES de la interfaz.
// El HTML se escribe en inglés con data-i18n="key" (textContent) y
// data-i18n-placeholder="key" (placeholder). En inglés no se toca nada.
// Toda key nueva va acá: tests/test_i18n.py falla si falta alguna.
'use strict';

window.I18N_ES = {
  // ── Errores genéricos ──
  'err.network': 'Error de red. Revisá tu conexión e intentá de nuevo.',
  'err.rate': 'Demasiadas solicitudes: esperá un minuto y volvé a intentar.',
  'err.server': 'Error del servidor',
};

window.applyI18n = function (root, lang) {
  if (lang !== 'es') return;
  const dict = window.I18N_ES;
  root.querySelectorAll('[data-i18n]').forEach((el) => {
    const value = dict[el.dataset.i18n];
    if (value) el.textContent = value;
  });
  root.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
    const value = dict[el.dataset.i18nPlaceholder];
    if (value) el.placeholder = value;
  });
  document.documentElement.lang = 'es';
};
