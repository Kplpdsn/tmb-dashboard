# TMB Dashboard UX Overhaul - Design Document

**Date:** 2026-02-26
**Status:** Approved for implementation
**Constraint:** All changes must respect the "select date first, then analyze" architecture.

---

## Project Structure (20 files)

```
D:\TMB 2.0\
  app.py                          # Main entry (~330 lines)
  config.py                       # Constants (~62 lines)
  styles.py                       # CSS (~338 lines)
  category_config.json            # 36 product-to-category mappings
  requirements.txt                # Dependencies
  service_account.json            # Google Drive auth (DO NOT MODIFY)
  components/
    __init__.py
    header.py                     # Header + date banner (~44 lines)
    date_picker.py                # Date selection UI (~143 lines)
    filters.py                    # Category/product/day/hour filters (~247 lines)
  views/
    __init__.py
    daily.py                      # Single-day analysis (~131 lines)
    weekly.py                     # 2-14 day analysis (~127 lines)
    monthly.py                    # 15+ day analysis (~243 lines)
    average_day.py                # Average day model (~339 lines)
    basket.py                     # Basket analysis (~336 lines)
    compare.py                    # Period comparison (~270 lines)
  reports/
    __init__.py
    standard.py                   # Standard PDF report (~375 lines)
    average_day.py                # Average Day PDF report (~467 lines)
    comparison.py                 # Comparison PDF report (~322 lines)
  services/
    __init__.py
    gdrive.py                     # Google Drive API (~67 lines)
    data_processor.py             # Data loading & category mapping (~289 lines)
```

---

## PHASE 1: Layout & Navigation Overhaul

### 1.1 Move filters to sidebar (`app.py` + `components/filters.py`)

**Problem:** Filters create a "wall of controls" between mode selection and charts. ~500px of controls before any data.

**Changes:**
- Move category/product dropdowns into `st.sidebar`
- Move day-of-week filter into `st.sidebar`
- Move hour range slider into `st.sidebar`
- Show a one-line filter summary in main area: "Filters: All Categories | All Days | 6:00-21:00" with a "Reset" button
- Remove the "Quick Filters" subheader, "Day of Week Analysis" subheader+caption, "Time Range Filter" subheader+caption
- Remove `st.markdown("---")` dividers between filter sections in sidebar

**In `components/filters.py`:**
- `render_category_product_filters()` -> wrap internals with `st.sidebar` context
- `render_day_of_week_filter()` -> wrap with `st.sidebar`, remove the caption "Filter by weekday to identify recurring patterns across multiple weeks"
- `render_hour_range_filter()` -> wrap with `st.sidebar`, remove the caption "Select hour range to analyze specific dayparts"
- Remove all `st.markdown("---")` inside these functions
- Add new `render_sidebar_filter_summary()` function that returns a compact one-line string for the main area

**In `app.py`:**
- Replace inline filter calls with sidebar-wrapped versions
- Add compact filter summary after mode selector

### 1.2 Simplify mode selector (`app.py` lines 76-98)

**Problem:** 4 equal-weight buttons + captions. "Simple Analysis" is meaningless. Advanced modes clutter the default view.

**Changes:**
- Rename modes:
  - "Simple Analysis" -> "Sales Overview"
  - "Compare Periods" -> "Compare"
  - "Basket Analysis" -> "What Sells Together"
  - "Average Day" -> "Typical Day"
- Make "Sales Overview" visually dominant (larger/primary)
- Put Compare, What Sells Together, Typical Day behind `st.expander("More Analysis Modes", expanded=False)`
- Remove all `st.caption()` descriptions under mode buttons

### 1.3 Move export to bottom (`app.py` lines 144-208)

**Problem:** Export buttons appear above the charts they describe.

**Changes:**
- Move the entire export section (PDF/CSV/Excel) to AFTER the view rendering (after line ~278)
- Wrap in `st.expander("Export & Download", expanded=False)`
- Combine PDF "Generate" + "Download" into single flow using `st.download_button` with data generation
- Remove raw traceback display on PDF error (lines 165-166, 184-185) - show user-friendly message instead

### 1.4 Remove excessive dividers and captions (all files)

**Problem:** 8+ horizontal rules per page, redundant captions everywhere.

**Files to modify:**
- `app.py`: Remove `st.markdown("---")` at lines 73, 99, 145, 208. Keep only the one before the view routing.
- `views/daily.py`: Remove `st.markdown("---")` at lines 34, 71. Remove caption "What a typical Monday looks like hour by hour" equivalent.
- `views/weekly.py`: Keep minimal dividers.
- `views/monthly.py`: Remove excessive `st.markdown("---")`.
- `views/average_day.py`: Remove `st.markdown("---")` at lines 89, 142, 175, 227, 273. Remove caption at line 95 "What a typical {day} looks like hour by hour". Remove caption at line 181 "Each dot is one instance; line shows rolling average".
- `views/basket.py`: Remove `st.markdown("<br><br>", unsafe_allow_html=True)` spacers (lines 32, 37, 42, 47, 52, 57). Replace with smaller `st.markdown("")`.
- `components/filters.py`: Remove caption at line 51 "Filter by weekday to identify recurring patterns...". Remove caption at line 105 "Select hour range to analyze specific dayparts".

---

## PHASE 2: Visual Design Cleanup

### 2.1 Reduce metrics to 3 per view (all view files)

**Problem:** 6 metrics in 2 rows. "Avg Items/Trans" and "Avg Price/Unit" are analyst metrics, not manager metrics.

**Changes in every view file:**
- Show only 3 primary metrics: **Revenue, Transactions, Avg Basket**
- Put secondary metrics (Avg Items/Trans, Avg Price/Unit, Avg Daily Rev) inside an expander: `st.expander("More Details")`

**Files:**
- `views/daily.py` lines 12-32: Keep c1 (Revenue), c3 (Transactions), c4 (Avg Basket). Move c2 (Units), c5, c6 into expander.
- `views/weekly.py` lines 12-32: Same pattern.
- `views/monthly.py` lines 14-34: Same pattern.
- `views/average_day.py` lines 79-87: Keep Revenue, Transactions, Avg Basket Value. Move Units into expander.

### 2.2 Fix color consistency (`config.py` + all chart files)

**Problem:** `#10b981` (teal), `#7D8570` (olive), `#2E7D32` (dark green) mixed randomly.

**Changes in `config.py`:**
- Remove `CHART_POSITIVE = "#10b981"` - replace with `CHART_HIGHLIGHT = "#5B8C5A"` (a cohesive green that works with olive)
- Keep `CHART_PRIMARY = "#7D8570"` as the main chart color
- Update `COLOR_POSITIVE = "#5B8C5A"` (was `#2E7D32`)
- Keep `CHART_NEGATIVE = "#DC2626"` (red is fine)

**Files to update (replace `#10b981` with `CHART_HIGHLIGHT` or `CHART_PRIMARY`):**
- `views/daily.py` line 46: `color = "#10b981"` -> use `CHART_HIGHLIGHT`
- `views/weekly.py` line 48: same
- `views/monthly.py` line 52: same
- `views/average_day.py`: uses config constants already (good)
- `components/filters.py` line 193: `"#10b981"` -> `CHART_HIGHLIGHT`
- `components/date_picker.py` lines 32, 35: `"#10b981"` -> `CHART_HIGHLIGHT`

### 2.3 Fix the styled DataFrame bug (`views/average_day.py` line 311)

**Bug:** Line 310 computes `styled = display.style.apply(_highlight_row, axis=1).hide(axis="index")` but line 311 renders the plain `display` DataFrame instead.

**Fix:** Change line 311 from:
```python
st.dataframe(display, use_container_width=True, hide_index=True)
```
to:
```python
st.dataframe(styled, use_container_width=True, hide_index=True)
```

### 2.4 Fix "+/- $200" notation (`views/average_day.py` lines 81-87)

**Problem:** Standard deviation notation is meaningless to a bakery manager.

**Change:** Replace `delta=f"+/- ${std_rev:,.0f}"` with a range display:
```python
# Instead of st.metric delta, add a caption below each metric
st.metric("Avg Revenue", f"${avg_rev:,.2f}")
if num_instances > 1:
    st.caption(f"Range: ${daily_totals['Revenue'].min():,.0f} - ${daily_totals['Revenue'].max():,.0f}")
```

---

## PHASE 3: Smart Insights

### 3.1 Add insight cards to daily view (`views/daily.py`)

**Add after metrics, before hourly chart:**

```python
# Peak hour insight
peak_hour = hourly.loc[hourly["Revenue"].idxmax(), "Hour"]
peak_rev = hourly["Revenue"].max()
total_rev = df["Revenue"].sum()
peak_pct = peak_rev / total_rev * 100 if total_rev > 0 else 0
_insight_card(f"Peak hour: {int(peak_hour)}:00 with ${peak_rev:,.0f} revenue ({peak_pct:.0f}% of daily total)")
```

Extract the `_insight_card()` function from `views/basket.py` into a shared `components/insight_card.py` module and import it everywhere.

### 3.2 Add day-of-week context to daily view (`views/daily.py`)

**Requires:** Pass the full unfiltered `df` as an additional parameter to `daily.render()`.

**Add after metrics:**
```python
day_name = min_date.strftime("%A")
# Get all instances of this day type from full data
all_same_day = full_df[full_df["DayName"] == day_name]
if all_same_day["Date"].dt.date.nunique() > 1:
    avg_for_day = all_same_day.groupby(all_same_day["Date"].dt.date)["Revenue"].sum().mean()
    pct_vs_avg = ((today_rev - avg_for_day) / avg_for_day * 100) if avg_for_day > 0 else 0
    _insight_card(f"This {day_name}: ${today_rev:,.0f} | Your average {day_name}: ${avg_for_day:,.0f} ({pct_vs_avg:+.0f}%)")
```

**In `app.py`:** Change `daily.render(filtered_df, min_date, selected_category)` to `daily.render(filtered_df, min_date, selected_category, full_df=df)`.

### 3.3 Add best/worst day callout to weekly view (`views/weekly.py`)

**Add after day-by-day chart:**
```python
best_day = daily.loc[daily["Revenue"].idxmax()]
worst_day = daily.loc[daily["Revenue"].idxmin()]
_insight_card(
    f"Best day: {best_day['DayName']} {best_day['Date'].strftime('%b %d')} (${best_day['Revenue']:,.0f}) | "
    f"Slowest: {worst_day['DayName']} {worst_day['Date'].strftime('%b %d')} (${worst_day['Revenue']:,.0f})"
)
```

### 3.4 Add "Unmapped Products" warning (`app.py`)

**Add after line 58 where `df` is set from session state:**
```python
other_products = df[df["Category"] == "Other"]["Description"].unique()
if len(other_products) > 0:
    with st.sidebar:
        st.warning(f"{len(other_products)} product(s) in 'Other': {', '.join(other_products[:5])}")
```

### 3.5 Lower trend threshold in monthly view (`views/monthly.py` line 117)

**Change:** `if days_span > 60:` -> `if days_span > 21:`

---

## PHASE 4: Date Picker Improvements

### 4.1 Auto-load on preset click (`components/date_picker.py`)

**Problem:** Clicking a preset only prefills dates. User must still click "Load Data".

**Change:** When a preset button is clicked, immediately trigger data loading instead of just setting session state. Refactor the preset buttons to set a flag that triggers the load logic:

```python
for col, (label, start, end) in zip(cols, quick_presets):
    with col:
        if st.button(label, use_container_width=True, key=f"quick_{label}"):
            st.session_state.auto_load_start = start
            st.session_state.auto_load_end = end
            st.session_state.trigger_load = True

# At the bottom of the function, check for auto-load trigger
if st.session_state.get("trigger_load"):
    start_date = st.session_state.auto_load_start
    end_date = st.session_state.auto_load_end
    del st.session_state.trigger_load
    # ... load data logic (same as existing load_clicked block)
```

### 4.2 Prominent "View Yesterday" button (`components/date_picker.py`)

**Add before preset rows:**
```python
st.markdown("### Quick Start")
if st.button("View Yesterday's Sales", type="primary", use_container_width=True, key="quick_yesterday_hero"):
    # Auto-load yesterday
    ...
st.markdown("---")
```

### 4.3 Remove redundant info box (`components/date_picker.py` lines 124-127)

**Remove:** The `st.info(f"Selected: ...")` box at the bottom. The date inputs already show the selected range.

---

## PHASE 5: Category Management

### 5.1 Switch to CSV backing store

**Create `category_config.csv`:**
```csv
Product,Category
HOUSE SOURDOUGH,Standard Loaves
HOUSE SOURDOUGH XL,XL Loaves
...
```

**Modify `services/data_processor.py`:**
- Change `_load_category_config()` to read CSV instead of JSON
- Keep JSON as fallback for backwards compatibility
- Remove duplicate keyword fallback rules that are already in the config

### 5.2 Add in-app category editor

**Create new file `components/category_manager.py`:**

```python
def render_category_editor():
    """Render in-app category editor using st.data_editor."""
    st.subheader("Product Categories")

    # Load current mappings
    mappings = load_category_csv()

    # Show uncategorized products
    if "df" in st.session_state:
        all_products = st.session_state.df["Description"].unique()
        unmapped = [p for p in all_products if p.upper() not in mappings]
        if unmapped:
            st.warning(f"{len(unmapped)} unmapped products found")

    # Editable table
    edited = st.data_editor(mappings_df, num_rows="dynamic")

    if st.button("Save Changes"):
        save_category_csv(edited)
        st.cache_data.clear()
        st.success("Categories updated!")
```

**Wire into `app.py`:** Add a "Manage Categories" option in the sidebar.

---

## PHASE 6: Export Improvements

### 6.1 In-browser PDF preview

**Add to export section:**
```python
import base64
if pdf_buf:
    pdf_base64 = base64.b64encode(pdf_buf.getvalue()).decode()
    st.markdown(
        f'<iframe src="data:application/pdf;base64,{pdf_base64}" '
        f'width="100%" height="500px"></iframe>',
        unsafe_allow_html=True,
    )
```

### 6.2 Copy summary for sharing (`views/daily.py`)

**Add at bottom of daily view:**
```python
day_name = min_date.strftime("%A")
summary_text = (
    f"TMB Harris Farm | {min_date.strftime('%b %d, %Y')} ({day_name})\n"
    f"Revenue: ${total_rev:,.0f} | Transactions: {num_baskets} | "
    f"Avg Basket: ${avg_basket:.2f}\n"
    f"Top: {top_product} (${top_rev:,.0f})"
)
st.code(summary_text, language=None)
st.caption("Copy the above to share via WhatsApp, Slack, or email")
```

### 6.3 Slow sellers section in monthly view (`views/monthly.py`)

**Add after Top 10 Products section:**
```python
st.subheader("Slow Sellers")
bottom = df.groupby("Description")["Revenue"].sum().sort_values().head(5)
# Render as simple table
```

---

## PHASE 7: Compare Mode Improvements

### 7.1 Pre-load Period A from existing data (`views/compare.py`)

**Change:** When entering Compare mode, auto-populate Period A with the already-loaded data instead of requiring a separate load.

```python
# In compare.render(), at the top:
if "period_a_raw" not in st.session_state and "df" in st.session_state:
    st.session_state.period_a_raw = st.session_state.df
    st.session_state.dates_a = (current_start, current_end)
```

### 7.2 Add comparison presets (`views/compare.py`)

**Add before date pickers:**
```python
st.markdown("**Quick Compare:**")
qc1, qc2, qc3 = st.columns(3)
with qc1:
    if st.button("This Week vs Last Week"): ...
with qc2:
    if st.button("This Month vs Last Month"): ...
with qc3:
    if st.button("vs Same Period Last Year"): ...
```

---

## Bug Fixes (do these first)

1. **`views/average_day.py` line 311:** Use `styled` instead of `display` in `st.dataframe()`
2. **`views/compare.py` line 242:** `.applymap()` is deprecated -> use `.map()` (pandas 2.1+)
3. **`app.py` lines 165-166, 184-185:** Remove `traceback.format_exc()` display - show user-friendly error only

---

## Implementation Order

1. Bug fixes (3 bugs above)
2. Phase 1: Layout overhaul (sidebar filters, mode rename, export move)
3. Phase 2: Visual cleanup (3 metrics, colors, divider removal)
4. Phase 3: Smart insights (insight cards, day context, warnings)
5. Phase 4: Date picker (auto-load, prominent yesterday)
6. Phase 5: Category management (CSV + editor)
7. Phase 6: Export improvements (preview, copy summary, slow sellers)
8. Phase 7: Compare mode improvements (pre-load, presets)

---

## Files Created

| File | Description |
|------|-------------|
| `components/insight_card.py` | Shared insight card component |
| `components/category_manager.py` | In-app category editor |
| `category_config.csv` | CSV version of category mappings |

## Files Modified

| File | Summary of Changes |
|------|-------------------|
| `app.py` | Sidebar filters, mode rename, export to bottom, insight wiring |
| `config.py` | Color consistency, new CHART_HIGHLIGHT constant |
| `styles.py` | Minor sidebar styling adjustments |
| `components/filters.py` | Sidebar-wrapped filters, remove captions/dividers |
| `components/date_picker.py` | Auto-load, prominent yesterday, remove redundant info |
| `components/header.py` | No changes needed |
| `views/daily.py` | 3 metrics, insight cards, day-of-week context, copy summary |
| `views/weekly.py` | 3 metrics, best/worst day callout |
| `views/monthly.py` | 3 metrics, lower trend threshold, slow sellers |
| `views/average_day.py` | Fix styled bug, fix +/- notation, remove dividers |
| `views/basket.py` | Extract insight_card, remove spacers |
| `views/compare.py` | Pre-load Period A, presets, fix .applymap() |
| `services/data_processor.py` | CSV category loading |
| `reports/standard.py` | No changes |
| `reports/average_day.py` | No changes |
| `reports/comparison.py` | No changes |
