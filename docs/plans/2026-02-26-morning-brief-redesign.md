# TMB Dashboard Redesign: "Morning Brief"

**Date:** 2026-02-26
**Status:** Approved
**Supersedes:** 2026-02-26-ux-overhaul-design.md (phases 1-7)

---

## Problem

The dashboard is choppy. It forces users to pick an analysis "mode" (Daily / Weekly / Monthly / Typical Day / Compare / Baskets) before seeing anything. A bakery manager opening the app on Monday morning just wants to know: how did yesterday go, how's the week looking, and what's selling. They shouldn't need to understand the difference between "Daily Analysis" and "Weekly Analysis."

Additional problems:
- "Sales Overview" secretly means 3 different things depending on date span
- Day-of-week filter is redundant with Typical Day's day picker
- Metrics are inconsistent across views (3 in Daily, 6 in Typical Day)
- Same chart code is copy-pasted across 3 report files
- PDF reports are data dumps, not narratives — the owner/stakeholder who reads them can't tell what matters

## Design Decisions (from user input)

1. **Primary use case:** "All of the above at once" — yesterday's numbers, week trend, product performance on one page
2. **PDF audience:** Owner/stakeholder who doesn't use the app — PDF must tell the full story standalone
3. **Day-of-week filter:** Kill it entirely — if they want Mondays, they use Typical Day
4. **Tools navigation:** Separate pages (not inline) — click "Model a Typical Day" replaces dashboard, "Back" returns

---

## Architecture

### Page Flow

```
Load Data → Dashboard (always lands here)
                ├── [Model a Typical Day] → Typical Day view (full page, "← Back" at top)
                ├── [Compare Two Periods] → Compare view (full page, "← Back" at top)
                └── [Basket Patterns] → Basket view (full page, "← Back" at top)
```

No mode selector. No auto-detect daily/weekly/monthly. The dashboard adapts to the loaded date range automatically.

### Dashboard Layout (views/dashboard.py)

Three sections, all visible immediately:

**Section A — "Yesterday" (latest day in loaded data)**
- 3 metrics: Revenue, Transactions, Avg Basket Value
- Delta shown as "vs typical {DayName}" (computed from loaded data's weekday average)
- One-liner insight: peak hour + top seller
- If loaded range is 1 day, Section B is skipped (Section A covers it)

**Section B — "This Period" (full loaded range)**
- 3 metrics: Total Revenue, Daily Average, Best Day
- One chart: revenue by day (bar chart ≤14 days, weekly aggregated bars 15+ days)
- One-liner insight: trend direction + best/worst day
- Only appears if loaded range > 1 day

**Section C — "What's Selling"**
- Top 8 products horizontal bar chart
- Category pie chart (hidden if a single category is filtered — pointless)
- Slow movers callout if range > 7 days: "These products sold < $X/day: ..."

**Below the fold — "More Tools"**
- 3 buttons: [Model a Typical Day] [Compare Two Periods] [Basket Patterns]
- Each navigates to a full-page tool view with "← Back to Dashboard" at top

**At the bottom — "Export"**
- Same as current: PDF / CSV / Excel in collapsed expander

### Sidebar Filters (Simplified)

**Kept:**
- Category dropdown
- Product dropdown (shows "All Products in {Category}" when category selected)
- Hour range slider (now also applies to Compare mode — currently broken)
- "Manage Categories" expander
- Unmapped products warning

**Killed:**
- Day-of-week filter (Weekdays / Weekends / Custom) — gone entirely
- Mode selector buttons — gone

**New:**
- "Reset Filters" link at bottom of sidebar (replaces fragile key-deletion logic)

### Tool Views

Typical Day, Compare, and Baskets remain as separate views but are accessed from the dashboard, not via mode buttons. Each gets:
- "← Back to Dashboard" button at top
- Shared metric component (3 primary + expander)
- Consistent layout patterns

### Insight Engine (services/insights.py)

Template-based insight generation used by both dashboard and PDF reports:

```
"Revenue {up/down} {X}% this {period}, driven by {top_category}."
"{best_day} was your strongest day at ${amount} ({+X}% vs average {day_name})."
"{product} is your top seller at ${amount}/day, making up {X}% of revenue."
"Peak trading: {hour}:00 — consider staffing up around this time."
"Slow movers: {products} averaged under ${threshold}/day."
"{day_name} revenue trending {up/down} {X}% over the period."
```

Each template has a guard condition (e.g., trend requires 21+ days). Returns a list of insight strings. Dashboard renders as insight cards. PDF renders as bullet points on page 1.

---

## PDF Reports — Narrative Redesign

### Audience

Owner/stakeholder who doesn't use the app. Gets the PDF emailed or printed. Needs to understand what happened without context.

### Structure (all 3 report types)

```
PAGE 1: THE STORY (Executive Brief)
├── Period header and key context
├── Headline: fill-in-the-blank template summarizing the period
├── 3 key numbers (Revenue / Daily Avg / Basket Value)
├── 3 bullet insights from the insight engine
└── "Details on the following pages"

PAGE 2: REVENUE DETAIL
├── One chart (daily bars or weekly trend)
├── One table (day-by-day or week-by-week breakdown)
└── Brief connecting caption

PAGE 3: PRODUCT PERFORMANCE
├── Top products bar chart
├── Category pie chart
└── Slow movers callout

PAGE 4+: CONDITIONAL (only if data warrants it)
├── Hourly pattern (if single day or typical day)
├── Trend analysis (if 21+ days)
├── Seasonality (if 2+ months)
└── Skip entirely if data doesn't justify the page
```

Key principles:
- Page 1 tells the story — owner reads only this page if in a hurry
- Subsequent pages are evidence, not the main event
- Conditional pages eliminate half-empty page 4 problem
- Simple template insights — predictable, always accurate

### Shared Chart Rendering (reports/charts.py)

Extract duplicated chart code from 3 report files into shared functions:
- `render_product_bar_chart(products_series, ...)`
- `render_category_pie_chart(category_series, ...)`
- `render_hourly_line_chart(hourly_data, ...)`
- `render_revenue_bar_chart(daily_data, ...)`
- `_styled_table(data, col_widths)` — already exists, move to shared

---

## File Changes

### New Files

| File | Purpose |
|------|---------|
| `views/dashboard.py` | Unified dashboard replacing daily/weekly/monthly |
| `components/metrics.py` | Shared 3-metric + expander rendering |
| `reports/charts.py` | Shared PDF chart rendering (bar, pie, line, table) |
| `services/insights.py` | Template-based insight generation |

### Modified Files

| File | Changes |
|------|---------|
| `app.py` | Remove mode selector, route to dashboard by default. Tools as conditional renders via session state. Remove day-of-week filter plumbing. |
| `views/average_day.py` | Use shared metrics. Fix styled DataFrame bug (line 311). Add "← Back" nav. |
| `views/compare.py` | Use shared metrics. Fix hour_range filter (currently ignored). Fix .map() deprecation. Add "← Back" nav. |
| `views/basket.py` | Use shared metrics/insights. Add "← Back" nav. |
| `components/filters.py` | Remove day-of-week filter. Simplify to category + product + hour. Clean reset logic. |
| `reports/standard.py` | Rewrite as narrative. Use shared charts. Page 1 = story. |
| `reports/average_day.py` | Rewrite as narrative. Use shared charts. Conditional pages. |
| `reports/comparison.py` | Rewrite as narrative. Use shared charts. |
| `config.py` | Remove day filter constants. Add insight template config. Document thresholds. |
| `styles.py` | Use CSS variables consistently. |

### Deprecated (keep as reference, eventually remove)

| File | Reason |
|------|--------|
| `views/daily.py` | Logic merged into `views/dashboard.py` |
| `views/weekly.py` | Logic merged into `views/dashboard.py` |
| `views/monthly.py` | Logic merged into `views/dashboard.py` |

### No New Dependencies

Everything uses existing: Streamlit, Plotly, ReportLab, pandas, numpy.

---

## Bug Fixes (included in this work)

| Bug | File | Fix |
|-----|------|-----|
| Styled DataFrame not rendered | `views/average_day.py:311` | Already fixed — use `styled` not `display` |
| `.applymap()` deprecated | `views/compare.py:242,267` | Already fixed — changed to `.map()` |
| Hour filter ignored in Compare | `views/compare.py` | Apply hour_range in comparison filter logic |
| ReportLab bars[(0,i)] tuple indexing | `reports/average_day.py`, `reports/comparison.py` | Already fixed — use tuple index for per-bar coloring |
| Day-of-week filter redundant | `components/filters.py` | Removed entirely in this redesign |

---

## What This Does NOT Change

- "Select date first, then analyze" workflow — unchanged
- Google Drive connection flow — unchanged
- Data loading / processing pipeline — unchanged
- Category config (CSV + JSON fallback) — unchanged
- Basket ID construction — unchanged (known imperfection, separate fix)
