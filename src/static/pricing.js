'use strict';

const BACKEND_URL = (() => {
  const h = window.location.hostname;
  return (h !== 'localhost' && h !== '127.0.0.1')
    ? 'https://bot-curriculum.onrender.com'
    : '';
})();

const $notifyBtn      = document.getElementById('notify-btn');
const $waitlistInline = document.getElementById('waitlist-inline');
const $waitlistEmail  = document.getElementById('waitlist-email');
const $waitlistSubmit = document.getElementById('waitlist-submit');
const $waitlistError  = document.getElementById('waitlist-error');
const $waitlistConfirm      = document.getElementById('waitlist-confirm');
const $waitlistConfirmEmail = document.getElementById('waitlist-confirm-email');

function show(el) { el.classList.remove('hidden'); }
function hide(el) { el.classList.add('hidden'); }

let _session = null;

async function init() {
  try {
    const res = await fetch(`${BACKEND_URL}/config`);
    if (!res.ok) return;
    const cfg = await res.json();
    if (!cfg.supabase_url || !cfg.supabase_anon_key) return;

    const sb = window.supabase.createClient(cfg.supabase_url, cfg.supabase_anon_key);
    const { data } = await sb.auth.getSession();
    _session = data.session || null;

    if (_session) {
      $notifyBtn.textContent = 'Notify me when Pro launches';
    }
  } catch (_) {}
}

async function submitWaitlist(email) {
  const headers = { 'Content-Type': 'application/json' };
  if (_session) headers['Authorization'] = `Bearer ${_session.access_token}`;

  const res = await fetch(`${BACKEND_URL}/waitlist`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ email }),
  });

  if (res.status === 201 || res.ok) {
    hide($notifyBtn);
    hide($waitlistInline);
    $waitlistConfirmEmail.textContent = email;
    show($waitlistConfirm);
  } else {
    const data = await res.json().catch(() => ({}));
    $waitlistError.textContent = data.detail || 'Something went wrong. Please try again.';
    show($waitlistError);
    $waitlistSubmit.disabled = false;
  }
}

$notifyBtn.addEventListener('click', async () => {
  if (_session) {
    $notifyBtn.disabled = true;
    $notifyBtn.textContent = 'Saving…';
    await submitWaitlist(_session.user.email);
    $notifyBtn.disabled = false;
  } else {
    hide($notifyBtn);
    show($waitlistInline);
    $waitlistEmail.focus();
  }
});

$waitlistEmail.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') $waitlistSubmit.click();
});

$waitlistSubmit.addEventListener('click', async () => {
  const email = $waitlistEmail.value.trim();
  if (!email || !/\S+@\S+\.\S+/.test(email)) {
    $waitlistError.textContent = 'Please enter a valid email address.';
    show($waitlistError);
    return;
  }
  hide($waitlistError);
  $waitlistSubmit.disabled = true;
  $waitlistSubmit.textContent = 'Saving…';
  await submitWaitlist(email);
});

init();
