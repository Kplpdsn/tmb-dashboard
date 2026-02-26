# Continuous Prompt - TMB Dashboard UX Overhaul

Copy everything below this line and paste into a new Claude Code session:

---

## Context

You are working on the TMB Harris Farm bakery sales analytics dashboard at `D:\TMB 2.0\`. It is a Streamlit app that loads daily sales Excel files from Google Drive, processes them with pandas, displays interactive Plotly charts, and generates ReportLab PDF reports.

The full design document is at `D:\TMB 2.0\docs\plans\2026-02-26-ux-overhaul-design.md`. Read it first.

## Your Task

Implement ALL 7 phases of the UX overhaul in one continuous session. Read every file before modifying it. After completing all changes, run `python -c "import app"` to verify imports work.

## Critical Rules

1. **Read before edit** - Always read a file completely before modifying it
2. **Respect "select date first"** - The app loads data from Google Drive for a user-selected date range. Never add auto-loading of all historical data.
3. **No new dependencies** - Everything must work with current requirements.txt can add with user approval.
4. **Preserve all existing functionality** - Compare, Basket, Average Day, all PDF reports must continue working
5. **Test imports** after each phase by running: `python -c "from app import *"` (or individual module imports)

## Implementation Steps (in order)

### Step 0: Read all files
Read every .py file and category_config.json before starting. Understand the full codebase.

### Step 1: Bug Fixes
1. `views/average_day.py` line 311: Change `st.dataframe(display, ...)` to `st.dataframe(styled, ...)` - the styled variable is computed on line 310 but never used
2. `views/compare.py` line 242: Change `.applymap(_color_cell, ...)` to `.map(_color_cell, ...)` (applymap is deprecated in pandas 2.1+). Do the same on line 267.
3. `app.py` lines 165-166 and 184-185: Remove `import traceback` and `st.error(traceback.format_exc())` - replace with `st.error(f"PDF generation failed: {e}")`

### Step 2: Create shared insight card component
Create `components/insight_card.py`:
```python
"""Shared insight card component."""
import streamlit as st

def render_insight(text):
    """Render a styled insight card with left border."""
    st.markdown(
        f"""
        <div style='background:#F9FAFB; padding:15px 20px; border-radius:6px;
                    border-left:3px solid #4B5563; margin:10px 0;'>
            <p style='font-size:13px; color:#1F2933; line-height:1.5; margin:0;'>{text}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
```

Update `views/basket.py`: Replace the `_insight_card()` function (lines 323-335) to import and use the shared one:
```python
from components.insight_card import render_insight as _insight_card
```
Remove the local `_insight_card` function definition from basket.py.

### Step 3: Move filters to sidebar (`components/filters.py` + `app.py`)

In `components/filters.py`:
- Wrap all filter rendering inside `with st.sidebar:` blocks
- Remove all `st.markdown("---")` dividers inside filter functions
- Remove the explanatory captions ("Filter by weekday to identify recurring patterns...", "Select hour range to analyze specific dayparts")
- Remove `st.markdown("<br>", unsafe_allow_html=True)` spacers
- Add a new function `render_filter_summary(filtered_df, selected_category, selected_product, day_filter_mode, selected_days)` that shows a compact one-line summary in the main area
- Keep the existing `render_filter_summary` function but rename it to `render_filter_detail_summary` (it already exists and shows detailed metrics when filters are active)

In `app.py`:
- The filter calls at lines 102-114 should remain in the same logical order but the filter functions themselves now render in sidebar
- Keep the filter summary rendering in the main area

### Step 4: Simplify mode selector (`app.py`)

Rename modes:
- "Simple Analysis" -> "Sales Overview"
- "Compare Periods" -> "Compare"
- "Basket Analysis" -> "What Sells Together"
- "Average Day" -> "Typical Day"

Change the layout: Show "Sales Overview" as a prominent primary button. Put the other 3 modes inside `st.expander("More Analysis Modes", expanded=False)` using `st.columns(3)`.

Remove all `st.caption(desc)` lines under mode buttons.

Update ALL references to the old mode names throughout app.py (the `mode` variable checks).

### Step 5: Move export to bottom (`app.py`)

Move the entire export section (lines ~144-208) to AFTER the view routing block (after line ~278). Wrap it in:
```python
with st.expander("Export & Download", expanded=False):
    # export buttons here
```

Simplify PDF generation: combine Generate + Download into a single `st.download_button` where possible, or at minimum put them next to each other clearly.

Remove the traceback error displays (already done in Step 1).

### Step 6: Reduce metrics to 3 per view

In each view file, keep only 3 primary metrics in the top row: **Revenue, Transactions, Avg Basket**.

Move secondary metrics (Units Sold, Avg Items/Trans, Avg Price/Unit, Avg Daily Rev) into:
```python
with st.expander("More Details"):
    c1, c2, c3 = st.columns(3)
    # secondary metrics here
```

Files: `views/daily.py`, `views/weekly.py`, `views/monthly.py`, `views/average_day.py`

For `views/average_day.py`, also fix the +/- notation: instead of `delta=f"+/- ${std_rev:,.0f}"`, use:
```python
st.metric("Avg Revenue", f"${avg_rev:,.2f}")
if num_instances > 1:
    st.caption(f"Range: ${daily_totals['Revenue'].min():,.0f} - ${daily_totals['Revenue'].max():,.0f}")
```

### Step 7: Remove excessive dividers and captions

Go through every view file and:
- Remove all `st.markdown("---")` lines EXCEPT where they genuinely separate major sections (keep max 2 per view)
- Remove redundant captions like "What a typical Monday looks like hour by hour", "Each dot is one instance; line shows rolling average", "Analyzing transaction patterns and product associations"
- Replace `st.markdown("<br><br>", unsafe_allow_html=True)` spacers in basket.py with just `st.markdown("")`

### Step 8: Fix color consistency (`config.py` + view files)

In `config.py`:
- Add `CHART_HIGHLIGHT = "#5B8C5A"` (cohesive green)
- Change `COLOR_POSITIVE = "#5B8C5A"` (was `#2E7D32`)

In view files, replace hardcoded `"#10b981"` with the config constant:
- `views/daily.py` line 46
- `views/weekly.py` line 48
- `views/monthly.py` line 52
- `components/filters.py` line 193
- `components/date_picker.py` lines 32, 35

Import `CHART_HIGHLIGHT` from config where needed.

### Step 9: Add smart insights

**In `views/daily.py`:**
- Import `from components.insight_card import render_insight`
- After metrics, add peak hour insight
- Add day-of-week context (change render signature to accept `full_df=None` parameter)
- At bottom, add copy-to-clipboard summary text block using `st.code()`

**In `app.py`:** Update daily.render() call to pass `full_df=df`:
```python
daily.render(filtered_df, min_date, selected_category, full_df=df)
```

**In `views/weekly.py`:**
- Import insight card
- After day-by-day chart, add best/worst day callout

**In `views/monthly.py`:**
- Change trend threshold from `if days_span > 60:` to `if days_span > 21:`
- Add slow sellers section after Top 10 Products

### Step 10: "Unmapped Products" warning (`app.py`)

After line 58 where `df = st.session_state.df`, add:
```python
other_products = df[df["Category"] == "Other"]["Description"].unique()
if len(other_products) > 0:
    with st.sidebar:
        st.warning(f"{len(other_products)} product(s) categorized as 'Other': {', '.join(other_products[:5])}")
```

### Step 11: Date picker improvements (`components/date_picker.py`)

1. Add a prominent "View Yesterday's Sales" button at the top (before other presets)
2. Make preset clicks auto-load data (set a trigger flag, check at bottom of function)
3. Remove the redundant `st.info(f"Selected: ...")` box at the bottom (lines 124-127)

### Step 12: Category management

1. Create `category_config.csv` from the existing JSON data
2. Modify `services/data_processor.py` `_load_category_config()` to prefer CSV, fall back to JSON
3. Create `components/category_manager.py` with `st.data_editor()` for in-app editing
4. Add "Manage Categories" button/expander in sidebar of `app.py`

### Step 13: Compare mode improvements (`views/compare.py`)

1. Auto-populate Period A from already-loaded data when entering Compare mode
2. Add quick compare presets: "This Week vs Last Week", "This Month vs Last Month"
3. Fix `.applymap()` -> `.map()` (already done in Step 1)

### Step 14: Export improvements

1. Add in-browser PDF preview using base64 iframe
2. Move all export to bottom (already done in Step 5)

### Step 15: Final verification

Run these commands to verify everything works:
```bash
cd "D:/TMB 2.0"
python -c "
from config import *
from styles import *
from components.header import *
from components.filters import *
from components.date_picker import *
from components.insight_card import *
from views.daily import *
from views.weekly import *
from views.monthly import *
from views.average_day import *
from views.basket import *
from views.compare import *
from reports.standard import *
from reports.average_day import *
from reports.comparison import *
from services.data_processor import *
from services.gdrive import *
print('All imports successful')
"
```

If any import fails, fix it before moving on.

## Key Data

- DataFrame columns: Date, Description, Revenue, Quantity, Hour, Category, DayName, Basket_ID, Week, Month, Year, WeekYear, MonthYear
- Categories: Standard Loaves, XL Loaves, Pastries, Bake at Home, Weekend Special, FMT, Retail Items, Buns & Rolls, Other
- Date range threshold: <=1 day = Daily, 2-14 = Weekly, 15+ = Monthly
- Google Drive folder: files named YYYYMMDD.xlsx
- Session state keys: `df`, `data_loaded`, `folder_id`, `analysis_view_mode`, `day_filter_mode`, `period_a_raw`, `period_b_raw`, `dates_a`, `dates_b`
