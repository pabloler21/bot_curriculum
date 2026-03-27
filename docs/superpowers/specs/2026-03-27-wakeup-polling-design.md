# Wakeup Polling Design

## Context

The app is deployed on Render's free tier. When the backend is idle, Render spins it down and the first incoming request triggers a cold start (~30–50s). Without feedback, users see a frozen spinner and abandon the page. This feature detects the cold start and shows an honest message while polling until the server is ready.

## Behavior

When the user submits a file:

1. Show spinner with message: `"Analyzing your resume..."`
2. Send `GET /health` with a 5s timeout
3. **If `/health` responds OK** → send `POST /evaluate` immediately (happy path, no visible change)
4. **If `/health` fails or times out** → update spinner message to:
   > `"The server was inactive and is waking up. This may take ~30 seconds, please wait..."`
   Poll `GET /health` every 3s
5. When `/health` responds OK → revert message to `"Analyzing your resume..."` → send `POST /evaluate`
6. On `/evaluate` response → render results or show error as today

## Files Modified

- `src/static/app.js` — all logic lives here
- `src/static/index.html` — no structural changes; loading message element must be reachable by JS (already is via existing selector)

## Implementation Details

### New function: `waitForServer()`

```
async waitForServer():
  loop:
    try GET /health, timeout 5s
    if OK → return
    catch → update spinner message to waking text, wait 3s, retry
```

### Updated submit flow

```
showLoading("Analyzing your resume...")
await waitForServer()
showLoading("Analyzing your resume...")   // reset in case message changed
response = await POST /evaluate
showResults(response) or showError()
```

### Constants

| Name | Value | Purpose |
|---|---|---|
| `HEALTH_TIMEOUT_MS` | 5000 | Time before declaring server asleep |
| `POLL_INTERVAL_MS` | 3000 | Interval between health checks |

## What Does Not Change

- HTML structure (no new elements)
- CSS (no new styles)
- Error handling for `/evaluate` failures
- Copy buttons, drag-and-drop, file validation

## Verification

1. Backend running locally → submit file → spinner shows "Analyzing..." → results appear (no waking message)
2. Stop local backend → submit file → after 5s spinner changes to waking message → restart backend → message reverts → results appear
3. Backend on Render (sleeping) → submit file → waking message appears → results appear after cold start
