// feature-visual.js — inclina hacia el cursor el tile de las páginas de features.
// El tile, sus capas y sus animaciones son HTML/CSS (app.css, sección .fv-*).
'use strict';
(function () {
  const fv = document.querySelector('.feature-visual');
  if (!fv) return;
  fv.addEventListener('pointermove', (e) => {
    const r = fv.getBoundingClientRect();
    fv.classList.add('is-tilting');
    fv.style.setProperty('--ry', ((e.clientX - r.left) / r.width - 0.5) * 18 + 'deg');
    fv.style.setProperty('--rx', -((e.clientY - r.top) / r.height - 0.5) * 14 + 'deg');
  });
  fv.addEventListener('pointerleave', () => {
    fv.classList.remove('is-tilting');
    fv.style.removeProperty('--ry');
    fv.style.removeProperty('--rx');
  });
})();
