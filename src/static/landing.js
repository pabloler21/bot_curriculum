// landing.js — waitlist del plan Pro (pricing.html). El dropdown del nav lo maneja shell.js.
'use strict';

const $btn = document.getElementById('waitlist-btn');
const $email = document.getElementById('waitlist-email');
const $err = document.getElementById('waitlist-error');
const $ok = document.getElementById('waitlist-ok');

$btn.addEventListener('click', async () => {
  const email = aurea.session ? aurea.session.user.email : $email.value.trim();
  if (!/\S+@\S+\.\S+/.test(email || '')) {
    $err.textContent = aurea.t('auth.invalid_email', 'Please enter a valid email address.');
    $err.classList.remove('hidden');
    return;
  }
  $err.classList.add('hidden');
  $btn.disabled = true;
  try {
    const res = await aurea.authFetch('/waitlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });
    if (!res.ok) throw new Error();
    $ok.classList.remove('hidden');
    $btn.classList.add('hidden');
    document.getElementById('waitlist-guest').classList.add('hidden');
  } catch (_) {
    $err.textContent = aurea.t('err.network', 'Network error. Check your connection and try again.');
    $err.classList.remove('hidden');
    $btn.disabled = false;
  }
});
