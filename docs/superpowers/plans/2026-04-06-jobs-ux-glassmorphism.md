# Jobs UX + Glassmorphism Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 7 UX/functional issues in the job board and apply a glassmorphism aesthetic (Steam colors, rounded corners, pill badges, glass buttons) to `jobs.html`.

**Architecture:** All changes are frontend-only — HTML, CSS, and vanilla JS. No backend changes. Five files modified: `jobs.html`, `jobs.css`, `jobs.js`, `style.css`. `index.html` already has the back button.

**Tech Stack:** Vanilla JS (no framework, no build step), CSS3 custom properties (defined in `style.css`), HTML5

---

## File Map

| File | What changes |
|---|---|
| `src/static/jobs.html` | Remove `#cv-bar` sticky div; add `#cv-banner` between `<header>` and `<main>` |
| `src/static/jobs.css` | Glassmorphism: cards, pill badges, glass buttons, sort pills, nav-link radius, cv-bar→cv-banner CSS |
| `src/static/style.css` | `.tag` border-radius: 2px → 20px |
| `src/static/jobs.js` | 4 fixes: applyScoresToCards helper, cvActive param, enable sort on upload, auto-switch sort |
| `src/static/index.html` | No change — `← Job Board` link already present |

---

### Task 1: Confirm index.html back button (verification only)

**Files:**
- Read: `src/static/index.html`

- [ ] **Step 1: Verify the link exists**

Open `src/static/index.html`. Confirm lines 17–19 contain:
```html
<nav class="header-nav" aria-label="App navigation" style="margin-top:8px">
  <a href="jobs.html" class="nav-link" style="font-size:11px">← Job Board</a>
</nav>
```

This requirement is already met. No changes needed.

- [ ] **Step 2: No commit needed**

Nothing to commit — this task is a verification only.

---

### Task 2: Replace #cv-bar with #cv-banner in jobs.html

**Files:**
- Modify: `src/static/jobs.html`

- [ ] **Step 1: Remove #cv-bar and add #cv-banner**

Replace the entire `<body>` of `src/static/jobs.html` with:

```html
<body>

  <header class="header">
    <div class="header-inner">
      <div>
        <h1>CV Evaluator</h1>
        <p>Remote Tech Job Board</p>
      </div>
      <nav class="header-nav" aria-label="App navigation">
        <a href="index.html" class="nav-link">ATS Evaluator</a>
      </nav>
    </div>
  </header>

  <!-- CV banner (below header, scrolls with page) -->
  <div id="cv-banner" class="cv-banner" role="complementary" aria-label="CV upload status">
    <div class="cv-banner-inner">
      <div id="cv-upload-area">
        <button id="cv-upload-btn" class="cv-banner-btn" aria-label="Upload your CV to see match scores">
          ↑ Upload CV
        </button>
        <input type="file" id="cv-file-input" accept=".pdf,.docx" hidden aria-label="Select CV file">
      </div>
      <div id="cv-active-area" class="hidden">
        <div class="cv-chip" role="status" aria-live="polite">
          <span class="cv-chip-icon" aria-hidden="true">📄</span>
          <span id="cv-chip-name" class="cv-chip-name"></span>
          <button id="cv-remove-btn" class="cv-chip-remove" aria-label="Remove uploaded CV">×</button>
        </div>
        <span id="cv-scoring-status" class="cv-scoring-status hidden" aria-live="polite">
          <span class="spinner-small" aria-hidden="true"></span>
          Scoring jobs against your CV…
        </span>
      </div>
      <p id="cv-error" class="cv-error hidden" role="alert"></p>
      <p id="cv-banner-copy" class="cv-banner-copy"><strong>Upload your CV</strong> to see how well you match each role</p>
    </div>
  </div>

  <main class="container">

    <!-- Sort toolbar -->
    <div class="toolbar" role="toolbar" aria-label="Sort options">
      <span class="toolbar-label">Sort by:</span>
      <button id="sort-date" class="sort-btn active" aria-pressed="true">Date posted</button>
      <button id="sort-score" class="sort-btn" aria-pressed="false" disabled title="Upload your CV to sort by match score">Match score</button>
    </div>

    <!-- Loading -->
    <div id="loading-jobs" class="loading-state" aria-live="polite">
      <div class="spinner"></div>
      <p class="loading-text">Loading job listings...</p>
    </div>

    <!-- Error -->
    <p id="error-jobs" class="error-msg hidden" role="alert"></p>

    <!-- Job grid -->
    <div id="jobs-grid" class="jobs-grid" aria-label="Job listings"></div>

  </main>

  <script src="jobs.js"></script>
</body>
```

- [ ] **Step 2: Manual verification**

Serve with `uvicorn src.main:app --reload` and open `http://localhost:8000/jobs.html`. Confirm:
- Header is at the top with "ATS Evaluator" nav link
- "↑ Upload CV" button appears immediately below the header
- Copy text "Upload your CV to see how well you match each role" appears on the right of the banner
- No sticky bar at the very top before the header

- [ ] **Step 3: Commit**

```bash
git add src/static/jobs.html
git commit -m "feat: replace sticky cv-bar with cv-banner below header"
```

---

### Task 3: Glassmorphism CSS update

**Files:**
- Modify: `src/static/jobs.css`
- Modify: `src/static/style.css`

- [ ] **Step 1: Update .nav-link border-radius in jobs.css**

Find this rule in `jobs.css`:
```css
.nav-link {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  text-decoration: none;
  padding: 5px 10px;
  border: 1px solid rgba(76, 107, 138, 0.45);
  border-radius: 2px;
  transition: color 0.15s, border-color 0.15s;
}
```

Change `border-radius: 2px` to `border-radius: 20px`.

- [ ] **Step 2: Replace cv-bar CSS block with cv-banner CSS**

Remove the entire `/* ── CV Bar ──────────────────────────────── */` section (`.cv-bar`, `.cv-bar::after`, `.cv-bar-inner`, `.cv-upload-trigger`) and replace with:

```css
/* ── CV Banner ───────────────────────────── */
.cv-banner {
  background: rgba(255, 255, 255, 0.03);
  border-bottom: 1px solid rgba(102, 192, 244, 0.18);
  backdrop-filter: blur(8px);
}

.cv-banner-inner {
  max-width: 960px;
  margin: 0 auto;
  padding: 12px 40px;
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.cv-banner-btn {
  background: rgba(102, 192, 244, 0.12);
  border: 1px solid rgba(102, 192, 244, 0.4);
  border-radius: 20px;
  color: var(--accent-blue);
  font-family: 'Inter', Arial, sans-serif;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  padding: 7px 18px;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s, border-color 0.15s;
}

.cv-banner-btn:hover,
.cv-banner-btn:focus-visible {
  background: rgba(102, 192, 244, 0.2);
  outline: none;
}

.cv-banner-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.cv-banner-copy {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
  margin-left: auto;
}

.cv-banner-copy strong {
  color: var(--text-primary);
}
```

- [ ] **Step 3: Update .job-card to glassmorphism**

Find the `.job-card` rule in `jobs.css`. Replace it with:

```css
.job-card {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-top: 1px solid rgba(102, 192, 244, 0.22);
  border-radius: 12px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.06);
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
  animation: slideUp 0.3s cubic-bezier(0.22, 1, 0.36, 1) both;
  position: relative;
}
```

- [ ] **Step 4: Update .score-badge to pill shape**

Find the `.score-badge` rule in `jobs.css`. Replace it with:

```css
.score-badge {
  display: none;
  flex-shrink: 0;
  border-radius: 20px;
  border: 1px solid var(--border);
  padding: 3px 10px;
  align-items: center;
  justify-content: center;
  font-family: 'Inter', Arial, sans-serif;
  font-size: 12px;
  font-weight: 700;
  color: var(--text-secondary);
  white-space: nowrap;
}
```

- [ ] **Step 5: Update score badge state rules**

Find the `/* ── Score badge states (Phase 3) ────────── */` section in `jobs.css`. Replace the three state rules with:

```css
.score-badge.score-strong {
  border-color: var(--success-green);
  color: var(--success-green);
  background: rgba(87, 203, 222, 0.12);
}

.score-badge.score-good {
  border-color: var(--warning-amber);
  color: var(--warning-amber);
  background: rgba(229, 163, 48, 0.1);
}

.score-badge.score-weak {
  border-color: var(--danger-red);
  color: var(--danger-red);
  background: rgba(231, 76, 60, 0.08);
}
```

- [ ] **Step 6: Update .sort-btn to pill shape**

Find `.sort-btn` in `jobs.css`. Change `border-radius: 2px` to `border-radius: 20px`.

- [ ] **Step 7: Update .sort-btn.active**

Find `.sort-btn.active` in `jobs.css`. Change `background: rgba(102, 192, 244, 0.08)` to `background: rgba(102, 192, 244, 0.1)`.

- [ ] **Step 8: Update .btn-match to glass button (remove gradient)**

Find the `.btn-match` rule in `jobs.css`. Replace it with:

```css
.btn-match {
  background: rgba(102, 192, 244, 0.1);
  border: 1px solid rgba(102, 192, 244, 0.35);
  border-radius: 8px;
  color: var(--accent-blue);
  padding: 8px 16px;
  font-family: 'Inter', Arial, sans-serif;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  cursor: pointer;
  text-align: center;
  text-decoration: none;
  display: block;
  transition: background 0.15s, border-color 0.15s;
}

.btn-match:hover,
.btn-match:focus-visible {
  background: rgba(102, 192, 244, 0.18);
  border-color: rgba(102, 192, 244, 0.6);
  outline: none;
}
```

- [ ] **Step 9: Update .job-type-badge border-radius to pill**

Find `.job-type-badge` in `jobs.css`. Change `border-radius: 2px` to `border-radius: 20px`.

- [ ] **Step 10: Update similarity bar**

Find `.similarity-bar-wrap` in `jobs.css`. Change:
- `height: 3px` → `height: 4px`
- `border-radius: 2px` → `border-radius: 10px`

Find `.similarity-bar` in `jobs.css`. Change `border-radius: 2px` → `border-radius: 10px`.

Find `.similarity-bar.sim-high` in `jobs.css`. Change:
```css
.similarity-bar.sim-high { background: linear-gradient(90deg, rgba(87, 203, 222, 0.7), #66c0f4); }
```

- [ ] **Step 11: Update .tag border-radius in style.css**

Find `.tag` in `src/static/style.css` (around line 479). Change `border-radius: 2px` to `border-radius: 20px`.

- [ ] **Step 12: Manual verification**

Open `http://localhost:8000/jobs.html` and confirm:
- Cards have rounded corners (12px) and a subtle glass background
- Sort buttons are pill-shaped
- "See full analysis" button is glass (blue text, no gradient)
- Nav link "ATS Evaluator" is pill-shaped
- Tags and employment type badges are pill-shaped
- CV banner upload button is pill-shaped

- [ ] **Step 13: Commit**

```bash
git add src/static/jobs.css src/static/style.css
git commit -m "feat: glassmorphism redesign — cards, pills, glass buttons, cv-banner CSS"
```

---

### Task 4: JS — fix score persistence on filter change

**Files:**
- Modify: `src/static/jobs.js`

Root cause: `setSort()` calls `renderJobs()` which rebuilds the DOM from scratch, discarding score badges and matched-skill highlights previously applied by `startBackgroundScoring()`.

Fix: extract `applyScoresToCards()` and call it after every `renderJobs()`.

- [ ] **Step 1: Add applyScoresToCards() function**

In `jobs.js`, after the `renderJobs()` function (after line 185) and before the `// ── Sort ─` section, insert:

```js
// ── Score application ──────────────────────────────────────────────────────

function applyScoresToCards() {
  Object.entries(scoresByJobId).forEach(([jobId, r]) => {
    const card = jobsGrid.querySelector(`[data-job-id="${CSS.escape(String(jobId))}"]`);
    if (!card || r.score == null) return;

    const badge = card.querySelector('.score-badge');
    if (badge) {
      badge.textContent = r.score;
      badge.style.display = 'flex';
      badge.className = `score-badge ${scoreBadgeClass(r.score)}`;
    }

    if (r.one_line_summary && !card.querySelector('.job-one-line')) {
      const titleEl = card.querySelector('.job-title');
      if (titleEl) {
        const summary = document.createElement('p');
        summary.className = 'job-one-line';
        summary.textContent = r.one_line_summary;
        titleEl.insertAdjacentElement('afterend', summary);
      }
    }

    if (r.matched_skills && r.matched_skills.length > 0) {
      card.querySelectorAll('.tag').forEach(tag => {
        const tagText = tag.textContent.toLowerCase();
        if (r.matched_skills.some(s => tagText.includes(s.toLowerCase()))) {
          tag.classList.add('matched');
          tag.classList.remove('found');
        }
      });
    }
  });
}
```

- [ ] **Step 2: Update setSort() to call applyScoresToCards() after renderJobs()**

Find the `setSort()` function in `jobs.js`:
```js
function setSort(mode) {
  currentSort = mode;
  sortDateBtn.classList.toggle('active', mode === 'date');
  sortDateBtn.setAttribute('aria-pressed', String(mode === 'date'));
  sortScoreBtn.classList.toggle('active', mode === 'score');
  sortScoreBtn.setAttribute('aria-pressed', String(mode === 'score'));
  renderJobs(sortedJobs());
}
```

Replace it with:
```js
function setSort(mode) {
  currentSort = mode;
  sortDateBtn.classList.toggle('active', mode === 'date');
  sortDateBtn.setAttribute('aria-pressed', String(mode === 'date'));
  sortScoreBtn.classList.toggle('active', mode === 'score');
  sortScoreBtn.setAttribute('aria-pressed', String(mode === 'score'));
  renderJobs(sortedJobs());
  applyScoresToCards();
}
```

- [ ] **Step 3: Remove the duplicated badge/summary/skills logic from startBackgroundScoring()**

In `startBackgroundScoring()`, find the `results.forEach(r => { ... })` block that updates badges, adds `job-one-line`, and highlights matched skills. Replace that entire block with a call to `applyScoresToCards()`:

Find in `startBackgroundScoring()`:
```js
    results.forEach(r => { scoresByJobId[r.job_id] = r; });

    results.forEach(r => {
      const card = jobsGrid.querySelector(`[data-job-id="${CSS.escape(String(r.job_id))}"]`);
      if (!card) return;
      const badge = card.querySelector('.score-badge');
      if (!badge) return;

      if (r.score == null) {
        badge.style.display = 'none';
        badge.className = 'score-badge';
        return;
      }

      // Animate counter 0 → score
      let current = 0;
      badge.style.display = 'flex';
      badge.className = `score-badge ${scoreBadgeClass(r.score)}`;
      const target = r.score;
      const interval = setInterval(() => {
        current = Math.min(current + 3, target);
        badge.textContent = current;
        if (current >= target) clearInterval(interval);
      }, 20);

      // Add one_line_summary subtitle
      if (r.one_line_summary) {
        const titleEl = card.querySelector('.job-title');
        if (titleEl && !card.querySelector('.job-one-line')) {
          const summary = document.createElement('p');
          summary.className = 'job-one-line';
          summary.textContent = r.one_line_summary;
          titleEl.insertAdjacentElement('afterend', summary);
        }
      }

      // Highlight matched skills
      if (r.matched_skills && r.matched_skills.length > 0) {
        card.querySelectorAll('.tag').forEach(tag => {
          const tagText = tag.textContent.toLowerCase();
          if (r.matched_skills.some(s => tagText.includes(s.toLowerCase()))) {
            tag.classList.add('matched');
            tag.classList.remove('found');
          }
        });
      }
    });
```

Replace with:
```js
    results.forEach(r => { scoresByJobId[r.job_id] = r; });
    applyScoresToCards();
```

Note: the animated counter is removed by this change — scores appear instantly. This is intentional (simpler, no animation artifacts on re-sort).

- [ ] **Step 4: Add cvBannerCopy DOM reference at top of jobs.js**

Find the block of `const` DOM references at the top of `jobs.js`:
```js
const cvUploadBtn  = document.getElementById('cv-upload-btn');
const cvFileInput  = document.getElementById('cv-file-input');
const cvUploadArea = document.getElementById('cv-upload-area');
const cvActiveArea = document.getElementById('cv-active-area');
const cvChipName   = document.getElementById('cv-chip-name');
const cvRemoveBtn  = document.getElementById('cv-remove-btn');
const cvError      = document.getElementById('cv-error');
```

Add one line after `cvError`:
```js
const cvBannerCopy = document.getElementById('cv-banner-copy');
```

- [ ] **Step 5: Update showCvChip() to hide banner copy**

Find `showCvChip()`:
```js
function showCvChip(filename) {
  cvChipName.textContent = filename;
  cvUploadArea.classList.add('hidden');
  cvActiveArea.classList.remove('hidden');
  cvError.classList.add('hidden');
  cvError.textContent = '';
}
```

Replace with:
```js
function showCvChip(filename) {
  cvChipName.textContent = filename;
  cvUploadArea.classList.add('hidden');
  cvActiveArea.classList.remove('hidden');
  cvError.classList.add('hidden');
  cvError.textContent = '';
  if (cvBannerCopy) cvBannerCopy.classList.add('hidden');
}
```

- [ ] **Step 6: Update showCvButton() to show banner copy**

Find `showCvButton()`:
```js
function showCvButton() {
  cvActiveArea.classList.add('hidden');
  cvUploadArea.classList.remove('hidden');
  cvError.classList.add('hidden');
  cvError.textContent = '';
}
```

Replace with:
```js
function showCvButton() {
  cvActiveArea.classList.add('hidden');
  cvUploadArea.classList.remove('hidden');
  cvError.classList.add('hidden');
  cvError.textContent = '';
  if (cvBannerCopy) cvBannerCopy.classList.remove('hidden');
}
```

- [ ] **Step 7: Manual verification**

1. Upload a CV. Let it score. Scores appear on cards.
2. Click "Date posted" sort. Confirm scores are still visible on the re-sorted cards.
3. Click "Match score" sort. Confirm scores are still visible.
4. Banner copy disappears when CV chip is shown; reappears when CV is removed.

- [ ] **Step 8: Commit**

```bash
git add src/static/jobs.js
git commit -m "fix: scores persist on sort change via applyScoresToCards helper"
```

---

### Task 5: JS — cvActive param, enable sort on upload, auto-switch sort

**Files:**
- Modify: `src/static/jobs.js`

This task covers fixes #1, #4, #6, and completes #7 (fallback sort key).

- [ ] **Step 1: Add cvActive param to renderJobCard()**

Find the `renderJobCard` function signature:
```js
function renderJobCard(job, index) {
```

Replace with:
```js
function renderJobCard(job, index, cvActive = false) {
```

- [ ] **Step 2: Conditionally render "See full analysis" in renderJobCard()**

Find this block inside `renderJobCard()`:
```js
    <div class="card-actions">
      <a
        href="job-detail.html?id=${encodeURIComponent(job.id)}"
        class="btn-match"
        aria-label="See full analysis for ${escHtml(job.title)}"
      >See full analysis →</a>
      <a
        href="${safeUrl(job.url)}"
        target="_blank"
        rel="noopener noreferrer"
        class="view-original"
        aria-label="View original posting for ${escHtml(job.title)} (opens in new tab)"
        onclick="event.stopPropagation()"
      >View original posting ↗</a>
    </div>
```

Replace with:
```js
    <div class="card-actions">
      ${cvActive ? `<a
        href="job-detail.html?id=${encodeURIComponent(job.id)}"
        class="btn-match"
        aria-label="See full analysis for ${escHtml(job.title)}"
      >See full analysis →</a>` : ''}
      <a
        href="${safeUrl(job.url)}"
        target="_blank"
        rel="noopener noreferrer"
        class="view-original"
        aria-label="View original posting for ${escHtml(job.title)} (opens in new tab)"
        onclick="event.stopPropagation()"
      >View original posting ↗</a>
    </div>
```

- [ ] **Step 3: Pass cvActive to renderJobCard() in renderJobs()**

In `renderJobs()`, find the existing `cvActive` variable:
```js
  const cvActive = jobs.some(j => j.similarity_score != null);
```

Replace with:
```js
  const cvActive = cvSessionToken != null;
```

Then find all calls to `renderJobCard()` inside `renderJobs()` and add the third argument:

Change:
```js
    relevant.forEach((job, i) => jobsGrid.appendChild(renderJobCard(job, i)));
```
To:
```js
    relevant.forEach((job, i) => jobsGrid.appendChild(renderJobCard(job, i, cvActive)));
```

Change:
```js
      lowRelevance.forEach((job, i) => lowSection.appendChild(renderJobCard(job, relevant.length + i)));
```
To:
```js
      lowRelevance.forEach((job, i) => lowSection.appendChild(renderJobCard(job, relevant.length + i, cvActive)));
```

Change:
```js
    jobs.forEach((job, i) => jobsGrid.appendChild(renderJobCard(job, i)));
```
To:
```js
    jobs.forEach((job, i) => jobsGrid.appendChild(renderJobCard(job, i, cvActive)));
```

- [ ] **Step 4: Enable sortScoreBtn immediately on CV upload**

In the `cvFileInput` change handler, find:
```js
    showCvChip(data.filename);
    loadRankedJobs(data.token);
```

Replace with:
```js
    showCvChip(data.filename);
    sortScoreBtn.disabled = false;
    sortScoreBtn.title = '';
    loadRankedJobs(data.token);
```

- [ ] **Step 5: Enable sortScoreBtn immediately on session restore**

In `restoreCvSession()`, find:
```js
    cvSessionToken = token;
    showCvChip(data.filename);
    loadRankedJobs(token);
```

Replace with:
```js
    cvSessionToken = token;
    showCvChip(data.filename);
    sortScoreBtn.disabled = false;
    sortScoreBtn.title = '';
    loadRankedJobs(token);
```

- [ ] **Step 6: Update sortedJobs() to use similarity_score as fallback**

Find the `sortedJobs()` function:
```js
function sortedJobs() {
  const jobs = [...allJobs];
  if (currentSort === 'date') {
    jobs.sort((a, b) => new Date(b.posted_at) - new Date(a.posted_at));
  } else if (currentSort === 'score') {
    jobs.sort((a, b) => {
      const sa = scoresByJobId[a.id]?.score ?? -1;
      const sb = scoresByJobId[b.id]?.score ?? -1;
      return sb - sa;
    });
  }
  return jobs;
}
```

Replace with:
```js
function sortedJobs() {
  const jobs = [...allJobs];
  if (currentSort === 'date') {
    jobs.sort((a, b) => new Date(b.posted_at) - new Date(a.posted_at));
  } else if (currentSort === 'score') {
    jobs.sort((a, b) => {
      const sa = scoresByJobId[a.id]?.score ?? (a.similarity_score != null ? a.similarity_score * 100 : -1);
      const sb = scoresByJobId[b.id]?.score ?? (b.similarity_score != null ? b.similarity_score * 100 : -1);
      return sb - sa;
    });
  }
  return jobs;
}
```

- [ ] **Step 7: Auto-switch to score sort after LLM scoring completes**

In `startBackgroundScoring()`, find:
```js
    // Enable "By match score" sort
    sortScoreBtn.disabled = false;
    sortScoreBtn.title = '';
```

Replace with:
```js
    // Auto-switch to match score sort now that LLM scores are ready
    setSort('score');
```

(The `sortScoreBtn.disabled = false` is no longer needed here because sort was already enabled on upload. `setSort('score')` will activate the button's active state.)

- [ ] **Step 8: Reset sortScoreBtn on CV remove**

In the `cvRemoveBtn` click handler, confirm this block already disables the button:
```js
  sortScoreBtn.disabled = true;
  sortScoreBtn.title = 'Upload your CV to sort by match score';
```

Also add a sort reset after it:
```js
  currentSort = 'date';
  sortDateBtn.classList.add('active');
  sortDateBtn.setAttribute('aria-pressed', 'true');
  sortScoreBtn.classList.remove('active');
  sortScoreBtn.setAttribute('aria-pressed', 'false');
```

Find the full cv-remove handler block:
```js
  cvSessionToken = null;
  localStorage.removeItem('cv_session_token');
  // Reset LLM scoring state
  scoresByJobId = {};
  sortScoreBtn.disabled = true;
  sortScoreBtn.title = 'Upload your CV to sort by match score';
  const scoreMore = document.getElementById('score-more-btn');
  if (scoreMore) scoreMore.remove();
  showCvButton();
  loadJobs();
```

Replace with:
```js
  cvSessionToken = null;
  localStorage.removeItem('cv_session_token');
  // Reset LLM scoring state
  scoresByJobId = {};
  sortScoreBtn.disabled = true;
  sortScoreBtn.title = 'Upload your CV to sort by match score';
  sortScoreBtn.classList.remove('active');
  sortScoreBtn.setAttribute('aria-pressed', 'false');
  currentSort = 'date';
  sortDateBtn.classList.add('active');
  sortDateBtn.setAttribute('aria-pressed', 'true');
  const scoreMore = document.getElementById('score-more-btn');
  if (scoreMore) scoreMore.remove();
  showCvButton();
  loadJobs();
```

- [ ] **Step 9: Manual verification**

1. Open jobs page with no CV → confirm "See full analysis" button is NOT shown on any card.
2. Upload a CV → confirm "See full analysis" appears on cards immediately after upload.
3. Confirm sort-by-score button is enabled immediately after upload (before LLM scoring finishes).
4. While LLM scoring runs, click "Match score" sort → cards reorder by similarity score (embedding-based), scores still visible once they arrive.
5. After LLM scoring completes, sort automatically switches to "Match score" with highest scores at top.
6. Remove CV → sort resets to "Date posted", "See full analysis" disappears on re-render.

- [ ] **Step 10: Commit**

```bash
git add src/static/jobs.js
git commit -m "feat: cvActive param, enable sort on upload, auto-switch to score sort"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| #1 Hide "See full analysis" when no CV | Task 5, Steps 1–3 |
| #2 CV banner below header | Tasks 2 + 3 (HTML + CSS) |
| #3 Fix: scores disappear on filter change | Task 4, Steps 1–3 |
| #4 Auto-switch sort to "match score" after CV upload | Task 5, Step 7 |
| #5 Back button on ATS Evaluator | Task 1 (already done) |
| #6 Sort buttons enabled immediately on CV upload | Task 5, Steps 4–5 |
| #7 Match score sort: highest to lowest | Task 5, Steps 6 (fallback key) + Task 4 Step 3 fixes bug that broke it |
| #8 Glassmorphism redesign | Task 3 |

**No placeholders:** All steps include complete code.

**Type consistency:** `applyScoresToCards()` uses `scoresByJobId[jobId]` (same dict populated in `startBackgroundScoring`). `cvActive` is `boolean` throughout. `similarity_score` is `number | null | undefined` — the `!= null` check handles both null and undefined.
