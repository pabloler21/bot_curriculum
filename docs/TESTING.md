# Manual QA Checklist

## Setup
- [ ] Server running: `uvicorn src.main:app --reload`
- [ ] Open `http://localhost:8000/jobs.html` in browser

## Job Board — No CV

- [ ] Job listings load and display as cards (date-sorted by default)
- [ ] Sort by "Date posted" works
- [ ] "Sort by match score" button is disabled
- [ ] Clicking a card → job detail page (`job-detail.html?id=...`)
- [ ] Job detail: "← Back to jobs" link visible, full description shown
- [ ] Job detail without CV: CTA says "Upload your CV to see your match score" → links to index.html

## CV Upload Flow

- [ ] Click "Upload your CV" → file picker opens (PDF/DOCX only)
- [ ] Select a wrong file type → inline error message shown
- [ ] Select a file > 5MB → inline error message shown
- [ ] Select valid PDF → uploads, chip shows filename, error cleared
- [ ] Chip shows "📄 filename.pdf ×"
- [ ] Click × → chip disappears, upload button restored, list re-sorts by date

## Embedding Ranking (Phase 2.5)

- [ ] After upload → job list re-loads with "Showing X jobs ranked by relevance to your CV."
- [ ] Jobs have thin colored bars under the title (green/yellow/gray)
- [ ] Raw similarity score numbers NOT visible
- [ ] Jobs with very low relevance (< 25%) collapsed under toggle "Show X low-relevance jobs"
- [ ] Toggle expands/collapses low-relevance section
- [ ] Click × to remove CV → banner disappears, bars disappear, list re-sorts by date

## LLM Scoring (Phase 3)

- [ ] After ranking, score badges show "—" (skeleton) on top 8 cards briefly
- [ ] Badges animate in with a counter 0→score
- [ ] Badge colors: green (≥75), yellow (50–74), red (<50)
- [ ] Matched skills highlighted in green on scored cards
- [ ] One-line summary appears under job title on scored cards
- [ ] "By match score" sort becomes enabled after scoring
- [ ] If > 8 jobs: "Score more jobs" button appears below the grid
- [ ] Null/failed score: silently shows nothing (no badge)

## Session Persistence (Page Reload)

- [ ] Upload CV, then reload the page → chip still shows (session restored from localStorage)
- [ ] Simulate 60-min expiry: token in localStorage but session expired on server → chip disappears silently, upload button shown

## Job Detail (Phase 4)

- [ ] With active CV: job detail CTA says "See how to improve your match →" → links to index.html?job_id=...
- [ ] index.html with job_id param: badge shows "Evaluating for: [Job Title] at [Company]"
- [ ] Evaluate button: runs evaluation with job context injected into prompt

## ATS Evaluator (index.html)

- [ ] Navigate directly (no job_id param) → generic evaluation works
- [ ] Upload CV file → evaluation runs, results shown
- [ ] With session token in localStorage → no need to re-upload (session CV used if file is empty)
- [ ] "← Job Board" link in header navigates back

## Error States

- [ ] Backend offline → "Could not connect to the server" shown on jobs page
- [ ] Remotive API down → 502 error handled gracefully on job board
- [ ] Invalid session token → 400 returned (tested via API)
