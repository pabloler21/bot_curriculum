// shell.js — piezas compartidas por todas las páginas (spec §4.1):
// auth con Supabase, topbar, sidebar, chip de créditos, modal de login/signup,
// acción pendiente tras el login, reclamo del CV anónimo e idioma.
// Las páginas lo usan vía window.aurea; nunca crean su propio cliente de Supabase.
'use strict';

(function () {
  const PENDING_KEY = 'aurea_pending_action';
  const SESSION_TOKEN_KEY = 'cv_session_token';
  const CLAIMED_KEY = 'aurea_claimed_token';
  const LANG_KEY = 'aurea_lang';

  const NAV = [
    { page: 'evaluator', href: 'evaluator.html', key: 'nav.evaluator', label: 'Evaluator', icon: '◎' },
    { page: 'tailor', href: 'tailor.html', key: 'nav.tailor', label: 'Tailor', icon: '✦' },
    { page: 'cover', href: 'cover.html', key: 'nav.cover', label: 'Cover', icon: '✉' },
    { page: 'jobs', href: 'jobs.html', key: 'nav.jobs', label: 'Jobs', icon: '▤' },
    { page: 'cv', href: 'cv.html', key: 'nav.cv', label: 'CV', icon: '⎙' },
    { page: 'settings', href: 'settings.html', key: 'nav.settings', label: 'Settings', icon: '⚙' },
  ];

  const body = document.body;
  const page = body.dataset.page || '';
  const isLanding = page === 'landing';
  const requiresAuth = body.dataset.requiresAuth === 'true';

  let client = null;
  let ready = false;
  let signingOut = false;
  const readyCallbacks = [];

  function store(key, value) { try { value === null ? localStorage.removeItem(key) : localStorage.setItem(key, value); } catch (_) {} }
  function load(key) { try { return localStorage.getItem(key); } catch (_) { return null; } }

  const lang = load(LANG_KEY) === 'es' ? 'es' : 'en';

  function escHtml(value) {
    if (value === null || value === undefined) return '';
    return String(value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function t(key, fallback) {
    if (lang === 'es' && window.I18N_ES && window.I18N_ES[key]) return window.I18N_ES[key];
    return fallback;
  }

  const aurea = (window.aurea = {
    session: null,
    credits: null,
    lang,
    escHtml,
    t,
    isUrl(text) { return /^https?:\/\/\S+$/i.test((text || '').trim()); },
    authHeaders(extra) {
      const headers = Object.assign({}, extra || {});
      if (aurea.session) headers.Authorization = `Bearer ${aurea.session.access_token}`;
      return headers;
    },
    authFetch(url, opts) {
      const o = Object.assign({}, opts || {});
      o.headers = aurea.authHeaders(o.headers);
      return fetch(url, o);
    },
    async refreshCredits() {
      if (!aurea.session) return null;
      try {
        const res = await aurea.authFetch('/credits');
        if (!res.ok) return null;
        const { balance } = await res.json();
        aurea.credits = balance;
        const el = document.getElementById('shell-credits');
        if (el) el.textContent = balance;
        return balance;
      } catch (_) { return null; }
    },
    requireAuth(action, payload) {
      if (aurea.session) return true;
      store(PENDING_KEY, JSON.stringify({ action, payload: payload || null }));
      openAuthModal('signup');
      return false;
    },
    takePendingAction() {
      if (!aurea.session) return null;
      const raw = load(PENDING_KEY);
      store(PENDING_KEY, null);
      try { return raw ? JSON.parse(raw) : null; } catch (_) { return null; }
    },
    onReady(cb) { if (ready) cb(); else readyCallbacks.push(cb); },
    openAuthModal,
    signOut,
  });

  // ── Markup ────────────────────────────────────────────────────────────────
  function topbarHtml() {
    return `
    <header class="topbar">
      <button type="button" class="topbar-menu hidden" id="shell-menu" aria-label="${escHtml(t('shell.menu', 'Open menu'))}" aria-controls="shell-sidebar" aria-expanded="false">☰</button>
      <a href="/" class="brand"><div class="brand-mark">✦</div><span class="brand-name">Aurea</span></a>
      <div class="topbar-right">
        <div class="ui-lang" role="group" aria-label="Language">
          <button type="button" data-set-lang="en">EN</button><button type="button" data-set-lang="es">ES</button>
        </div>
        <a href="settings.html#usage" class="credit-chip hidden" data-auth="user" title="Credits"><span id="shell-credits">–</span> 🪙</a>
        <button type="button" class="btn-primary btn-sm hidden" data-auth="guest" data-open-auth="signup" data-i18n="shell.signup">Sign up</button>
      </div>
    </header>`;
  }

  function offerBarHtml() {
    return `
    <div class="offer-bar hidden" data-auth="guest">
      <span data-i18n="shell.offer">Offer! Sign up now and get 5 credits</span>
      <button type="button" class="offer-bar-btn" data-open-auth="signup" data-i18n="shell.offer_cta">Claim them</button>
    </div>`;
  }

  function sidebarHtml() {
    const items = NAV.map((n) => {
      const active = n.page === page;
      return `<a href="${n.href}" class="sidebar-item${active ? ' active' : ''}"${active ? ' aria-current="page"' : ''}>
        <span class="sidebar-icon" aria-hidden="true">${n.icon}</span><span data-i18n="${n.key}">${n.label}</span></a>`;
    }).join('');
    return `
    <nav class="sidebar" id="shell-sidebar" aria-label="App">
      ${items}
      <button type="button" class="sidebar-item sidebar-logout" id="shell-logout">
        <span class="sidebar-icon" aria-hidden="true">⎋</span><span data-i18n="nav.logout">Log out</span>
      </button>
    </nav>`;
  }

  function modalHtml() {
    return `
    <div id="auth-modal" class="auth-modal hidden" role="dialog" aria-modal="true" aria-labelledby="auth-modal-title">
      <div class="auth-modal-backdrop" data-close-auth></div>
      <div class="auth-modal-content">
        <button type="button" class="auth-modal-close" data-close-auth aria-label="Close">✕</button>
        <div class="auth-modal-brand"><div class="brand-mark">✦</div><span class="brand-name">Aurea</span></div>
        <p class="auth-offer" id="auth-offer" data-i18n="auth.offer">Sign up now and get 5 free credits</p>
        <h2 id="auth-modal-title" class="auth-modal-title" data-i18n="auth.title">Create your account</h2>
        <div id="auth-form">
          <button type="button" id="auth-google" class="btn-google">
            <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/><path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"/></svg>
            <span data-i18n="auth.google">Continue with Google</span>
          </button>
          <div class="auth-divider"><span data-i18n="auth.or">or use your email</span></div>
          <input type="email" id="auth-email" class="auth-email-input" placeholder="you@example.com" autocomplete="email" data-i18n-placeholder="auth.email_placeholder">
          <button type="button" id="auth-send" class="btn-primary btn-full" data-i18n="auth.send">Send magic link</button>
          <p id="auth-error" class="error-msg hidden" role="alert"></p>
        </div>
        <div id="auth-sent" class="auth-modal-sent hidden">
          <div class="auth-modal-sent-icon" aria-hidden="true">✉️</div>
          <p class="auth-modal-sent-text"><span data-i18n="auth.sent">Check your inbox — we sent a link to</span> <strong id="auth-sent-email"></strong></p>
        </div>
      </div>
    </div>`;
  }

  // ── Modal ─────────────────────────────────────────────────────────────────
  function $(id) { return document.getElementById(id); }

  function showAuthError(message) {
    const el = $('auth-error');
    el.textContent = message;
    el.classList.remove('hidden');
  }

  function openAuthModal(mode) {
    const signup = mode !== 'login';
    $('auth-offer').classList.toggle('hidden', !signup);
    $('auth-modal-title').textContent = signup ? t('auth.title', 'Create your account') : t('auth.title_login', 'Log in to Aurea');
    $('auth-form').classList.remove('hidden');
    $('auth-sent').classList.add('hidden');
    $('auth-error').classList.add('hidden');
    $('auth-email').value = '';
    $('auth-modal').classList.remove('hidden');
    $('auth-email').focus();
  }

  function closeAuthModal() {
    $('auth-modal').classList.add('hidden');
    // Cerrar sin loguearse descarta la acción pendiente: no debe dispararse en otro login futuro.
    store(PENDING_KEY, null);
  }

  function currentUrl() { return window.location.href.split('#')[0]; }

  async function signInWithGoogle() {
    if (!client) return showAuthError(t('auth.unavailable', 'Auth service unavailable — reload the page.'));
    const { error } = await client.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: currentUrl() } });
    if (error) showAuthError(error.message);
  }

  async function sendMagicLink() {
    if (!client) return showAuthError(t('auth.unavailable', 'Auth service unavailable — reload the page.'));
    const email = $('auth-email').value.trim();
    if (!/\S+@\S+\.\S+/.test(email)) return showAuthError(t('auth.invalid_email', 'Please enter a valid email address.'));
    const btn = $('auth-send');
    btn.disabled = true;
    btn.textContent = t('auth.sending', 'Sending…');
    try {
      const { error } = await client.auth.signInWithOtp({ email, options: { emailRedirectTo: currentUrl() } });
      if (error) throw error;
      $('auth-sent-email').textContent = email;
      $('auth-form').classList.add('hidden');
      $('auth-sent').classList.remove('hidden');
    } catch (err) {
      showAuthError(err.message || t('auth.send_failed', 'Failed to send the link. Please try again.'));
    } finally {
      btn.disabled = false;
      btn.textContent = t('auth.send', 'Send magic link');
    }
  }

  // Supabase devuelve los errores del magic link en el fragmento (#error=...&error_code=otp_expired).
  function showAuthErrorFromUrl() {
    const hash = window.location.hash.slice(1);
    if (!hash || hash.indexOf('error') === -1) return;
    const params = new URLSearchParams(hash);
    const description = params.get('error_description');
    if (!description) return;
    const hint = params.get('error_code') === 'otp_expired'
      ? ' ' + t('auth.link_expired', 'Request a new link and open it right away — each new link cancels the previous one.')
      : '';
    openAuthModal('login');
    showAuthError(description + hint);
    history.replaceState(null, '', window.location.pathname + window.location.search);
  }

  async function signOut() {
    signingOut = true;
    try { if (client) await client.auth.signOut(); } catch (_) {}
    aurea.session = null;
    window.location.href = '/';
  }

  // ── Estado ────────────────────────────────────────────────────────────────
  function applyAuthVisibility() {
    const loggedIn = !!aurea.session;
    document.querySelectorAll('[data-auth]').forEach((el) => {
      el.classList.toggle('hidden', (el.dataset.auth === 'user') !== loggedIn);
    });
  }

  function markLang() {
    document.querySelectorAll('[data-set-lang]').forEach((btn) => {
      const active = btn.dataset.setLang === lang;
      btn.classList.toggle('active', active);
      btn.setAttribute('aria-pressed', String(active));
    });
  }

  async function claimAnonymousCv() {
    const token = load(SESSION_TOKEN_KEY);
    if (!token || token === load(CLAIMED_KEY)) return;
    try {
      const res = await aurea.authFetch('/cv', { method: 'PUT', headers: { 'X-CV-Session-Token': token }, body: new FormData() });
      // 400 = sesión anónima vencida: marcarla igual para no reintentar en cada carga.
      if (res.ok || res.status === 400) store(CLAIMED_KEY, token);
    } catch (_) {}
  }

  async function initSupabase() {
    try {
      const res = await fetch('/config');
      if (!res.ok) return;
      const cfg = await res.json();
      if (!cfg.supabase_url || !cfg.supabase_anon_key || !window.supabase) return;
      client = window.supabase.createClient(cfg.supabase_url, cfg.supabase_anon_key);
      const { data } = await client.auth.getSession();
      aurea.session = data.session || null;
      client.auth.onAuthStateChange((_event, session) => {
        const was = !!aurea.session;
        aurea.session = session || null;
        // Login o logout desde otra pestaña/redirect: recargar es lo más simple para re-render.
        if (was !== !!session && !signingOut) window.location.reload();
      });
    } catch (_) {}
  }

  function wire() {
    document.addEventListener('click', (e) => {
      const langBtn = e.target.closest('[data-set-lang]');
      if (langBtn) { store(LANG_KEY, langBtn.dataset.setLang); window.location.reload(); return; }
      const openBtn = e.target.closest('[data-open-auth]');
      if (openBtn) { openAuthModal(openBtn.dataset.openAuth); return; }
      if (e.target.closest('[data-close-auth]')) { closeAuthModal(); return; }
      if (e.target.closest('#shell-logout')) { signOut(); return; }
      if (e.target.closest('#shell-menu')) {
        const open = body.classList.toggle('sidebar-open');
        $('shell-menu').setAttribute('aria-expanded', String(open));
      }
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !$('auth-modal').classList.contains('hidden')) closeAuthModal();
    });
    $('auth-google').addEventListener('click', signInWithGoogle);
    $('auth-send').addEventListener('click', sendMagicLink);
    $('auth-email').addEventListener('keydown', (e) => { if (e.key === 'Enter') sendMagicLink(); });
  }

  async function init() {
    if (!isLanding) {
      body.insertAdjacentHTML('afterbegin', topbarHtml() + (page === 'evaluator' ? offerBarHtml() : ''));
    }
    body.insertAdjacentHTML('beforeend', modalHtml());
    wire();
    showAuthErrorFromUrl();

    await initSupabase();

    if (requiresAuth && !aurea.session) { window.location.replace('evaluator.html'); return; }

    if (aurea.session && !isLanding) {
      body.insertAdjacentHTML('afterbegin', sidebarHtml());
      body.classList.add('has-sidebar');
      $('shell-menu').classList.remove('hidden');
    }
    applyAuthVisibility();
    if (window.applyI18n) window.applyI18n(document, lang);
    markLang();

    if (aurea.session) {
      await claimAnonymousCv();
      aurea.refreshCredits();
    }

    body.classList.add('shell-ready');
    ready = true;
    readyCallbacks.splice(0).forEach((cb) => { try { cb(); } catch (err) { console.error(err); } });
  }

  init();
})();
