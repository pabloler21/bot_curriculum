// landing.js — dropdown de Features y waitlist del plan Pro.
'use strict';

const $dropdown = document.querySelector('.nav-dropdown');
document.querySelectorAll('.nav-dropdown-menu a').forEach((a) => {
  a.addEventListener('click', () => { $dropdown.open = false; });
});
document.addEventListener('click', (e) => {
  if ($dropdown.open && !$dropdown.contains(e.target)) $dropdown.open = false;
});

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
