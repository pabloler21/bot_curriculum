# Global Tab Navigation — Design Spec

**Date:** 2026-04-10
**Scope:** Frontend only — HTML + CSS, no JS, no backend changes
**Goal:** Replace the per-page nav links with a persistent sticky tab strip that always shows both app sections ("ATS Evaluator" / "Job Board"), giving users constant orientation across the three pages.

---

## Background

Currently each page has an isolated nav element:
- `index.html` → pill button "← Job Board"
- `jobs.html` → text link "ATS Evaluator"
- `job-detail.html` → two links: "← Back to jobs" + "ATS Evaluator"

The feedback: users lack awareness that they have two main sections. The fix is a shared tab strip — visible always, sticky on scroll.

---

## Architecture

Pure HTML/CSS change across 3 files. No JS, no routing, no shared template — vanilla multi-page app, each file gets the strip added manually.

| File | Change |
|------|--------|
| `src/static/style.css` | Make `.header` sticky; add `.tab-strip` + `.tab-strip-item` classes |
| `src/static/index.html` | Add tab strip inside header; remove `.cv-back-btn` pill |
| `src/static/jobs.html` | Add tab strip inside header; remove existing nav link |
| `src/static/job-detail.html` | Add tab strip inside header; remove both existing nav links |

---

## Components

### `.tab-strip`

Sits inside `<header>`, below `.header-inner`. Full-width flex row, no gap between items. Has a bottom border that merges with the header's existing glowing `::after` line.

```html
<div class="tab-strip" role="tablist" aria-label="App sections">
  <a href="index.html" class="tab-strip-item [active|inactive]" role="tab" aria-selected="[true|false]">ATS Evaluator</a>
  <a href="jobs.html"  class="tab-strip-item [active|inactive]" role="tab" aria-selected="[true|false]">Job Board</a>
</div>
```

Active tab: blue text + 2px bottom border in `var(--accent-blue)`, margin-bottom `-1px` to sit flush with header border.  
Inactive tab: `var(--text-secondary)`, transparent border, hover to `var(--text-primary)`.

### `.header` — sticky

```css
.header {
  position: sticky;
  top: 0;
  z-index: 100;
}
```

Existing background gradient, border, and `::after` glow line are unchanged.

---

## Active tab per page

| Page | ATS Evaluator tab | Job Board tab |
|------|:-----------------:|:-------------:|
| `index.html` | active | inactive |
| `jobs.html` | inactive | active |
| `job-detail.html` | inactive | active (sub-page of Job Board) |

---

## What gets removed

- `.cv-back-btn` styles from `style.css` (the blue pill button)
- The `<a href="jobs.html" class="cv-back-btn">← Job Board</a>` from `index.html`
- The `<a href="index.html" class="nav-link">ATS Evaluator</a>` from `jobs.html`
- Both nav links from `job-detail.html` header

The `.header-nav` element and its styles can be removed from all pages since the tab strip replaces the nav entirely.

---

## CSS spec

```css
/* ── Header — sticky ─────────────────────── */
.header {
  position: sticky;
  top: 0;
  z-index: 100;
  padding-bottom: 0; /* tab strip provides bottom spacing */
  /* all other existing properties unchanged */
}

/* ── Tab strip ───────────────────────────── */
.tab-strip {
  display: flex;
  margin-top: 12px;
}

.tab-strip-item {
  padding: 8px 20px 7px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  font-family: 'Inter', Arial, sans-serif;
  text-decoration: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: color 0.15s, border-color 0.15s;
  color: var(--text-secondary);
}

.tab-strip-item.active {
  color: var(--accent-blue);
  border-bottom-color: var(--accent-blue);
}

.tab-strip-item:hover:not(.active) {
  color: var(--text-primary);
}
```

---

## Accessibility

- `role="tablist"` on `.tab-strip`, `role="tab"` on each item
- `aria-selected="true"` on active tab, `aria-selected="false"` on inactive
- `aria-label="App sections"` on the tablist
- Tab items are `<a>` tags (native keyboard focus)

---

## Out of scope

- No JS routing / SPA behavior — full page load on tab click (acceptable for this app's scale)
- No mobile-specific tab behavior changes beyond what's inherited from header sticky
- No changes to the cv-banner, job cards, evaluator layout, or any other component
