// settings.js — idioma (lo maneja shell.js), uso, paquetes "coming soon", billing y borrado de cuenta.
'use strict';

const $ = (id) => document.getElementById(id);
const show = (el) => el.classList.remove('hidden');
const t = (k, f) => aurea.t(k, f);

async function loadUsage() {
  $('st-email').textContent = aurea.session.user.email || '';
  const credits = await aurea.refreshCredits();
  $('st-credits').textContent = credits ?? '–';
  try {
    const res = await aurea.authFetch('/history');
    if (res.ok) $('st-generations').textContent = (await res.json()).length;
  } catch (_) {}
}

async function notify() {
  try {
    const res = await aurea.authFetch('/waitlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: aurea.session.user.email }),
    });
    if (!res.ok) throw new Error();
    show($('st-notify-ok'));
    document.querySelectorAll('[data-pack]').forEach((b) => { b.disabled = true; });
  } catch (_) {
    $('st-notify-error').textContent = t('err.network', 'Network error. Check your connection and try again.');
    show($('st-notify-error'));
  }
}

async function deleteAccount() {
  $('st-delete').disabled = true;
  try {
    const res = await aurea.authFetch('/account', { method: 'DELETE' });
    if (res.status !== 204) throw new Error();
    await aurea.signOut(); // ya limpia las claves del usuario y redirige a '/'
  } catch (_) {
    $('st-delete-error').textContent = t('settings.delete_error', 'Could not delete your account. Please try again.');
    show($('st-delete-error'));
    $('st-delete').disabled = false;
  }
}

document.querySelectorAll('[data-pack]').forEach((b) => b.addEventListener('click', notify));
$('st-delete-confirm').addEventListener('input', () => { $('st-delete').disabled = $('st-delete-confirm').value.trim() !== 'DELETE'; });
$('st-delete').addEventListener('click', deleteAccount);

aurea.onReady(loadUsage);
