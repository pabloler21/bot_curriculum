# Jobs UX Fixes + Glassmorphism Redesign

**Date:** 2026-04-06

## Goal

Fix 7 UX/functional issues in the job board and apply a glassmorphism aesthetic (Steam colors, rounded corners, pill badges, glass buttons) to `jobs.html`.

## Changes

### 1. Hide "See full analysis" when no CV uploaded

`renderJobCard()` receives a `cvActive: boolean` parameter. The "See full analysis" anchor is only included in the card HTML when `cvActive` is `true`. `renderJobs()` passes `cvActive = (cvSessionToken != null)`.

### 2. CV banner below header (replaces sticky cv-bar)

- Remove the `#cv-bar` sticky element from the top of `jobs.html`.
- Add a `#cv-banner` section between the `<header>` and `<main>`:
  - **No CV:** button on left ("↑ Upload CV"), copy on right ("Upload your CV to see how well you match each role")
  - **CV active:** cv-chip (filename + × remove button) on left, scoring status on right
- File input stays hidden, same logic as before.
- `cv-banner` is not sticky — it scrolls with the page.

### 3. Fix: scores disappear on filter change

Root cause: `setSort()` calls `renderJobs()` which rebuilds the DOM, discarding badge updates from `startBackgroundScoring()`.

Fix: after `renderJobs()` in `setSort()`, iterate `scoresByJobId` and re-apply score badges, `job-one-line`, and matched skill highlights to the newly rendered cards. Extract a `applyScoresToCards()` helper that both `startBackgroundScoring()` and `setSort()` call.

### 4. Auto-switch sort to "match score" after CV upload

At the end of `startBackgroundScoring()`, after scores are applied and `sortScoreBtn` is enabled, call `setSort('score')`.

### 5. Back button on ATS Evaluator (`index.html`)

Add a nav link "← Job Board" in the header of `index.html` linking to `jobs.html`. Same pill style as the "ATS Evaluator" link in `jobs.html`.

### 6. Sort buttons enabled immediately on CV upload

Enable `sortScoreBtn` as soon as the CV session is created (in the `cvFileInput` change handler and `restoreCvSession()`), not after LLM scoring completes. Sorting before scoring returns uses `similarity_score` from the embedding ranking as the sort key.

Update `sortedJobs()`: when `currentSort === 'score'`, primary key is `scoresByJobId[id]?.score`, fallback is `job.similarity_score ?? -1` (so embedding-ranked jobs still sort correctly before LLM scores arrive).

### 7. Match score sort: highest to lowest

Already implemented in `sortedJobs()` (`return sb - sa`). Broken only because of bug #3. Fix #3 resolves this automatically.

### 8. Glassmorphism redesign (`jobs.css` + `style.css`)

**Cards (`job-card`):**
- `border-radius: 12px`
- `background: rgba(255, 255, 255, 0.04)`
- `border: 1px solid rgba(255, 255, 255, 0.09)` + `border-top: 1px solid rgba(102, 192, 244, 0.22)`
- `box-shadow: 0 4px 24px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.06)`

**Score badge → pill:**
- Shape: `border-radius: 20px`, `padding: 3px 10px` (not a circle)
- Remove fixed `width/height: 42px`
- Keep color states (strong/good/weak)

**Sort buttons → pills:**
- `border-radius: 20px`
- Active state: `background: rgba(102, 192, 244, 0.1); border-color: rgba(102, 192, 244, 0.5)`

**"See full analysis" button:**
- Remove gradient background
- Use `background: rgba(102, 192, 244, 0.1); border: 1px solid rgba(102, 192, 244, 0.35); border-radius: 8px; color: #66c0f4`

**CV banner:**
- `background: rgba(255, 255, 255, 0.03)`
- `border-bottom: 1px solid rgba(102, 192, 244, 0.18)`
- `backdrop-filter: blur(8px)` (progressive enhancement)
- Button: pill style (`border-radius: 20px`, glass bg)

**Tags → pills:**
- `border-radius: 20px` (from `2px`)

**Nav links → pills:**
- `border-radius: 20px` (from `2px`)

**Type badge → pill:**
- `border-radius: 20px`

**Similarity bar:**
- Height: `4px` (from `3px`)
- Bar: `background: linear-gradient(90deg, rgba(87,203,222,0.7), #66c0f4)`
- Container: `border-radius: 10px`

Steam color palette unchanged (`--bg-main`, `--accent-blue`, etc.).

## Files Changed

| File | Changes |
|---|---|
| `src/static/jobs.html` | Remove `#cv-bar`, add `#cv-banner` between header and main |
| `src/static/jobs.css` | Full glassmorphism update (cards, badges, buttons, banner) |
| `src/static/jobs.js` | Fix #3 (`applyScoresToCards`), fix #4 (auto-sort), fix #6 (enable sort on upload), fix #1 (cvActive param), fix #7 (fallback sort key) |
| `src/static/index.html` | Add "← Job Board" nav link |
| `src/static/style.css` | Nav link border-radius update |

## Out of Scope

- Backend changes (none required)
- `job-detail.html` / `job-detail.js` (separate page, not listed in requirements)
- Mobile-specific layout changes beyond what the grid already handles
