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
  // ── Shell / navegación ──
  'nav.evaluator': 'Evaluador',
  'nav.tailor': 'Adaptar',
  'nav.cover': 'Carta',
  'nav.jobs': 'Empleos',
  'nav.cv': 'CV',
  'nav.settings': 'Ajustes',
  'nav.logout': 'Cerrar sesión',
  'shell.menu': 'Abrir menú',
  'shell.signup': 'Registrarme',
  'shell.offer': '¡Oferta! Registrate ahora y llevate 5 créditos',
  'shell.offer_cta': 'Quiero mis créditos',
  // ── Modal de auth ──
  'auth.offer': 'Registrate ahora y llevate 5 créditos gratis',
  'auth.title': 'Creá tu cuenta',
  'auth.title_login': 'Ingresá a Aurea',
  'auth.google': 'Continuar con Google',
  'auth.or': 'o usá tu email',
  'auth.email_placeholder': 'vos@ejemplo.com',
  'auth.send': 'Enviar link mágico',
  'auth.sending': 'Enviando…',
  'auth.sent': 'Revisá tu bandeja: te mandamos un link a',
  'auth.invalid_email': 'Ingresá un email válido.',
  'auth.unavailable': 'El servicio de login no está disponible: recargá la página.',
  'auth.send_failed': 'No pudimos enviar el link. Probá de nuevo.',
  'auth.link_expired': 'Pedí un link nuevo y abrilo enseguida: cada link nuevo anula el anterior.',
  // ── Render de resultados ──
  'result.badge_completed': 'Completado',
  'result.badge_partial': 'Parcial: revisá lo marcado',
  'result.badge_failed_extract': 'Falló la extracción',
  'result.badge_failed_adapt': 'Falló la adaptación',
  'result.pdf_failed': 'No se pudo descargar el PDF. Probá de nuevo.',
  'cvp.summary': 'Resumen profesional',
  'cvp.experience': 'Experiencia',
  'cvp.present': 'Actualidad',
  'cvp.flagged': 'Este punto quedó marcado: revisalo con cuidado',
  'cvp.skills': 'Habilidades',
  'cvp.education': 'Educación',
  'cvp.additional': 'Adicional',
  'cvp.languages': 'Idiomas',
  'interview.technical': 'Técnica',
  'interview.behavioral': 'Conductual',
  'interview.gap': 'Brecha',
  'interview.drawn_from': 'Basado en',
  'interview.why': 'Por qué la preguntan',
  'jobs.match': 'de coincidencia',
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
