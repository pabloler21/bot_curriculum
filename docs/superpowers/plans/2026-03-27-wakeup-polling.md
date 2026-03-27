# Wakeup Polling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a "server is waking up" message with polling when the Render free-tier backend is cold-starting, instead of a frozen spinner.

**Architecture:** Before sending the heavy `/evaluate` request, the frontend pings `/health` with a 5s timeout. If it fails, it updates the spinner message and retries every 3s until the server responds, then proceeds normally.

**Tech Stack:** Vanilla JS, existing `fetch` API, `AbortController` for timeout

---

### Task 1: Add `loadingText` reference and `setLoadingMessage` helper

**Files:**
- Modify: `src/static/app.js:1-11` (DOM references block)
- Modify: `src/static/app.js:100-108` (`setLoading` function)

- [ ] **Step 1: Add `loadingText` to the DOM references block**

At the top of `app.js`, after the existing `const` declarations (line 10), add:

```js
const loadingText    = document.querySelector('#loading-section .loading-text');
```

The block should now end with:
```js
const loadingSection = document.getElementById('loading-section');
const resultsSection = document.getElementById('results-section');
const resetBtn       = document.getElementById('reset-btn');
const loadingText    = document.querySelector('#loading-section .loading-text');
```

- [ ] **Step 2: Add `setLoadingMessage` helper and update `setLoading` to reset message**

Replace the existing `setLoading` function:

```js
function setLoading(active) {
  if (active) {
    uploadSection.classList.add('hidden');
    loadingSection.classList.remove('hidden');
    setLoadingMessage('Analyzing your resume...');
  } else {
    loadingSection.classList.add('hidden');
    uploadSection.classList.remove('hidden');
  }
}

function setLoadingMessage(msg) {
  loadingText.textContent = msg;
}
```

- [ ] **Step 3: Verify manually**

Open `index.html` in a browser (or via the running server). The spinner text should still read the default on load — no visible change yet.

- [ ] **Step 4: Commit**

```bash
git add src/static/app.js
git commit -m "feat: add setLoadingMessage helper and reset message on setLoading"
```

---

### Task 2: Add `waitForServer` polling function

**Files:**
- Modify: `src/static/app.js` — add new function before the `analyzeBtn` click handler

- [ ] **Step 1: Add constants and `waitForServer` after the `// ── Analyze` comment, before the `analyzeBtn.addEventListener` line**

```js
// ── Wakeup polling ────────────────────────────────────────────────────────────

const HEALTH_TIMEOUT_MS = 5000;
const POLL_INTERVAL_MS  = 3000;

async function waitForServer() {
  while (true) {
    try {
      const controller = new AbortController();
      const timeoutId  = setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS);
      const res        = await fetch('/health', { signal: controller.signal });
      clearTimeout(timeoutId);
      if (res.ok) return;
    } catch (_) {
      // server not responding yet — fall through to show waking message
    }
    setLoadingMessage(
      'The server was inactive and is waking up. This may take ~30 seconds, please wait...'
    );
    await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL_MS));
  }
}
```

- [ ] **Step 2: Verify the function is syntactically valid**

Open the browser dev console. There should be no JS errors on page load.

- [ ] **Step 3: Commit**

```bash
git add src/static/app.js
git commit -m "feat: add waitForServer health-check polling"
```

---

### Task 3: Wire `waitForServer` into the analyze flow

**Files:**
- Modify: `src/static/app.js` — `analyzeBtn` click handler

- [ ] **Step 1: Update the click handler to call `waitForServer` before fetching `/evaluate`**

Replace the `analyzeBtn.addEventListener('click', async () => { ... })` block with:

```js
analyzeBtn.addEventListener('click', async () => {
  if (!selectedFile) return;

  setLoading(true);
  hideError();

  await waitForServer();
  setLoadingMessage('Analyzing your resume...');

  const formData = new FormData();
  formData.append('file', selectedFile);

  try {
    const response = await fetch('/evaluate', {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      let detail = `Error ${response.status}`;
      try {
        const errData = await response.json();
        detail = errData.detail || detail;
      } catch (_) { /* non-JSON error body */ }
      throw new Error(detail);
    }

    const data = await response.json();
    renderResults(data);
    showResults();
  } catch (err) {
    setLoading(false);
    const isNetworkError = err instanceof TypeError && err.message === 'Failed to fetch';
    showError(isNetworkError ? 'Could not connect to the server. Check your connection.' : err.message);
  }
});
```

- [ ] **Step 2: Manual test — happy path (server is up)**

1. Start the backend locally: `uvicorn src.main:app --reload`
2. Open the app and submit a PDF
3. Spinner should show `"Analyzing your resume..."` throughout — no waking message
4. Results appear normally

- [ ] **Step 3: Manual test — wakeup path (server is down)**

1. Stop the backend
2. Submit a PDF — spinner should show `"Analyzing your resume..."` briefly, then switch to `"The server was inactive and is waking up. This may take ~30 seconds, please wait..."`
3. Start the backend
4. Within ~3s the spinner reverts to `"Analyzing your resume..."` and the evaluate request is sent
5. Results appear normally

- [ ] **Step 4: Commit**

```bash
git add src/static/app.js
git commit -m "feat: poll /health before /evaluate to handle Render cold start"
```
