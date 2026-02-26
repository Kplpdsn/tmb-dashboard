# Morning Brief Redesign — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the 6-mode analysis selector with a single unified dashboard that shows yesterday's numbers, period trends, and product performance at once. Tools (Typical Day, Compare, Baskets) become separate pages with back navigation.

**Architecture:** New `views/dashboard.py` renders three sections (Yesterday, This Period, What's Selling) using data from `services/insights.py` (template-based insight engine) and `components/metrics.py` (shared metric cards). PDF reports get narrative page 1 via shared `reports/charts.py`. Mode selector and day-of-week filter are removed entirely.

**Tech Stack:** Streamlit, Plotly, ReportLab, pandas, numpy (all existing — no new dependencies)

**Design Doc:** `docs/plans/2026-02-26-morning-brief-redesign.md`

**Testing:** No test framework exists. Verify each task by running `streamlit run app.py` and checking visually. Each task should leave the app in a working state.

---

## Task Dependency Graph

```
Task 1: config.py ──────────┐
Task 2: services/insights.py ┼──→ Task 6: views/dashboard.py ──→ Task 7: app.py ──→ Task 8-10: tool views
Task 3: components/metrics.py┘                                                    ──→ Task 13: cleanup
Task 4: reports/charts.py ──────→ Task 11-12: report rewrites
Task 5: components/filters.py ─→ Task 7: app.py
```

---

## Task 1: Update config.py — Add Insight Thresholds, Remove Day Filter Constants

**Files:**
- Modify: `config.py`

**What changes:**
- Remove `DAILY_MAX_DAYS` and `WEEKLY_MAX_DAYS` (no longer needed — no auto-detect)
- Add insight engine thresholds and template config

**Step 1: Edit config.py**

Remove these lines:
```python
# Analysis mode thresholds (days)
DAILY_MAX_DAYS = 1
WEEKLY_MAX_DAYS = 14
```

Add after the `CHART_CONFIDENCE_BAND` line:
```python
# Insight engine thresholds
INSIGHT_TREND_MIN_DAYS = 21       # need 21+ days for trend insights
INSIGHT_SLOW_MOVER_MIN_DAYS = 7   # need 7+ days for slow mover callout
INSIGHT_SLOW_MOVER_THRESHOLD = 5  # products averaging < $5/day are "slow"
INSIGHT_TOP_PRODUCTS = 8          # number of products in "What's Selling"
INSIGHT_WEEKLY_AGGREGATE_DAYS = 15  # 15+ days → aggregate to weekly bars
```

**Step 2: Verify no other files import removed constants**

Search for `DAILY_MAX_DAYS` and `WEEKLY_MAX_DAYS` — only `app.py` imports them, and `app.py` will be rewritten in Task 7. For now, leave the imports in `app.py` (they won't break — the constants still exist until we remove them). Actually, remove them from config now and we'll fix the app.py import in Task 7.

Wait — the app must remain runnable after each task. So keep the constants for now, just add the new ones. We'll remove the old constants in Task 7 when we rewrite app.py.

**Revised Step 1: Only add new constants to config.py**

Add after `CHART_CONFIDENCE_BAND`:
```python
# Insight engine thresholds
INSIGHT_TREND_MIN_DAYS = 21       # need 21+ days for trend insights
INSIGHT_SLOW_MOVER_MIN_DAYS = 7   # need 7+ days for slow mover callout
INSIGHT_SLOW_MOVER_THRESHOLD = 5  # products averaging < $5/day are "slow"
INSIGHT_TOP_PRODUCTS = 8          # number of products in "What's Selling"
INSIGHT_WEEKLY_AGGREGATE_DAYS = 15  # 15+ days → aggregate to weekly bars
```

**Step 3: Verify app still runs**

Run: `streamlit run app.py` — should work exactly as before (additive change only).

**Step 4: Commit**

```bash
git add config.py
git commit -m "feat: add insight engine threshold constants to config"
```

---

## Task 2: Create services/insights.py — Template-Based Insight Engine

**Files:**
- Create: `services/insights.py`

**What it does:**
Generate a list of plain-English insight strings from a DataFrame. Used by both the dashboard (rendered as cards) and PDF reports (rendered as bullet points on page 1). Each template has a guard condition — if the data doesn't support the insight, it's skipped.

**Step 1: Create services/insights.py**

```python
"""Template-based insight generation for dashboard and PDF reports."""

import numpy as np
import pandas as pd

from config import (
    INSIGHT_TREND_MIN_DAYS,
    INSIGHT_SLOW_MOVER_MIN_DAYS,
    INSIGHT_SLOW_MOVER_THRESHOLD,
)


def generate_insights(df, days_span=None):
    """Generate a list of insight strings from the loaded data.

    Args:
        df: Filtered DataFrame with columns: Revenue, Quantity, Hour, Date,
            Basket_ID, Description, Category, DayName.
        days_span: Number of days in the loaded range. Computed from df if None.

    Returns:
        List of plain-English insight strings. Order = priority.
    """
    if df.empty:
        return []

    if days_span is None:
        days_span = (df["Date"].max() - df["Date"].min()).days + 1

    insights = []

    # --- Latest day insights ---
    latest_date = df["Date"].max()
    latest_day = df[df["Date"] == latest_date]

    if not latest_day.empty:
        _add_peak_hour(insights, latest_day)
        _add_top_seller(insights, latest_day)
        if days_span > 1:
            _add_day_vs_typical(insights, df, latest_date)

    # --- Period insights (multi-day only) ---
    if days_span > 1:
        _add_best_worst_day(insights, df)
        _add_category_driver(insights, df)

    if days_span >= INSIGHT_TREND_MIN_DAYS:
        _add_trend(insights, df)

    if days_span >= INSIGHT_SLOW_MOVER_MIN_DAYS:
        _add_slow_movers(insights, df, days_span)

    return insights


def generate_yesterday_insights(df, latest_day_df, latest_date):
    """Generate insights specifically for the 'Yesterday' section.

    Returns list of insight strings about the latest day.
    """
    insights = []
    _add_peak_hour(insights, latest_day_df)

    day_name = latest_date.day_name() if hasattr(latest_date, 'day_name') else pd.Timestamp(latest_date).day_name()
    same_day = df[df["DayName"] == day_name]
    day_count = same_day["Date"].dt.date.nunique()
    if day_count > 1:
        avg_rev = same_day.groupby(same_day["Date"].dt.date)["Revenue"].sum().mean()
        actual_rev = latest_day_df["Revenue"].sum()
        pct = ((actual_rev - avg_rev) / avg_rev * 100) if avg_rev > 0 else 0
        direction = "above" if pct > 0 else "below"
        insights.append(
            f"{abs(pct):.0f}% {direction} your typical {day_name} (${avg_rev:,.0f} average)"
        )

    _add_top_seller(insights, latest_day_df)
    return insights


def generate_period_insights(df, days_span):
    """Generate insights for the 'This Period' section.

    Returns list of insight strings about the full loaded range.
    """
    insights = []
    _add_best_worst_day(insights, df)

    if days_span >= INSIGHT_TREND_MIN_DAYS:
        _add_trend(insights, df)
    else:
        _add_category_driver(insights, df)

    return insights


def generate_product_insights(df, days_span):
    """Generate insights for the 'What's Selling' section.

    Returns list of insight strings about product performance.
    """
    insights = []
    _add_top_seller(insights, df)
    if days_span >= INSIGHT_SLOW_MOVER_MIN_DAYS:
        _add_slow_movers(insights, df, days_span)
    return insights


# --- Private template functions ---


def _add_peak_hour(insights, day_df):
    """Peak trading hour insight."""
    hourly = day_df.groupby("Hour")["Revenue"].sum()
    if hourly.empty:
        return
    peak_hour = int(hourly.idxmax())
    peak_rev = hourly.max()
    total = day_df["Revenue"].sum()
    pct = (peak_rev / total * 100) if total > 0 else 0
    insights.append(
        f"Peak hour: {peak_hour}:00 with ${peak_rev:,.0f} ({pct:.0f}% of revenue)"
    )


def _add_top_seller(insights, df):
    """Top-selling product insight."""
    product_rev = df.groupby("Description")["Revenue"].sum()
    if product_rev.empty:
        return
    top = product_rev.idxmax()
    top_rev = product_rev.max()
    total = df["Revenue"].sum()
    pct = (top_rev / total * 100) if total > 0 else 0
    days = df["Date"].dt.date.nunique() or 1
    daily_avg = top_rev / days
    if days > 1:
        insights.append(f"Top seller: {top} at ${daily_avg:,.0f}/day ({pct:.0f}% of revenue)")
    else:
        insights.append(f"Top seller: {top} at ${top_rev:,.0f} ({pct:.0f}% of revenue)")


def _add_day_vs_typical(insights, df, latest_date):
    """Compare latest day revenue to same-weekday average."""
    day_name = latest_date.day_name() if hasattr(latest_date, 'day_name') else pd.Timestamp(latest_date).day_name()
    latest_rev = df[df["Date"] == latest_date]["Revenue"].sum()
    same_day = df[df["DayName"] == day_name]
    day_count = same_day["Date"].dt.date.nunique()
    if day_count <= 1:
        return
    avg_rev = same_day.groupby(same_day["Date"].dt.date)["Revenue"].sum().mean()
    pct = ((latest_rev - avg_rev) / avg_rev * 100) if avg_rev > 0 else 0
    direction = "above" if pct >= 0 else "below"
    insights.append(
        f"{latest_date.strftime('%A')}: ${latest_rev:,.0f} — "
        f"{abs(pct):.0f}% {direction} typical {day_name} (${avg_rev:,.0f})"
    )


def _add_best_worst_day(insights, df):
    """Best and worst day in the period."""
    daily_rev = df.groupby("Date")["Revenue"].sum()
    if len(daily_rev) < 2:
        return
    best_date = daily_rev.idxmax()
    best_rev = daily_rev.max()
    best_name = best_date.day_name() if hasattr(best_date, 'day_name') else pd.Timestamp(best_date).day_name()
    avg = daily_rev.mean()
    pct_above = ((best_rev - avg) / avg * 100) if avg > 0 else 0
    insights.append(
        f"Best day: {best_name} {best_date.strftime('%b %d')} "
        f"at ${best_rev:,.0f} (+{pct_above:.0f}% vs daily average)"
    )


def _add_category_driver(insights, df):
    """Top category by revenue."""
    cat_rev = df.groupby("Category")["Revenue"].sum()
    if cat_rev.empty:
        return
    top_cat = cat_rev.idxmax()
    top_val = cat_rev.max()
    total = df["Revenue"].sum()
    pct = (top_val / total * 100) if total > 0 else 0
    insights.append(f"Top category: {top_cat} at ${top_val:,.0f} ({pct:.0f}% of revenue)")


def _add_trend(insights, df):
    """Revenue trend direction over the period (requires 21+ days)."""
    daily = df.groupby("Date")["Revenue"].sum().sort_index()
    if len(daily) < 14:
        return
    # Weekly aggregation for smoother trend
    weekly = daily.resample("W").sum()
    if len(weekly) < 3:
        return
    x = np.arange(len(weekly))
    slope, _ = np.polyfit(x, weekly.values, 1)
    pct_change = (slope * len(weekly)) / weekly.mean() * 100 if weekly.mean() > 0 else 0
    direction = "up" if slope > 0 else "down"
    insights.append(f"Revenue trending {direction} {abs(pct_change):.0f}% over the period")


def _add_slow_movers(insights, df, days_span):
    """Products averaging below threshold per day."""
    product_daily = df.groupby("Description")["Revenue"].sum() / days_span
    slow = product_daily[product_daily < INSIGHT_SLOW_MOVER_THRESHOLD]
    if slow.empty:
        return
    names = slow.sort_values().head(5).index.tolist()
    threshold = INSIGHT_SLOW_MOVER_THRESHOLD
    if len(slow) > 5:
        insights.append(
            f"Slow movers ({len(slow)} products under ${threshold}/day): "
            f"{', '.join(names)} and {len(slow) - 5} more"
        )
    elif len(slow) > 0:
        insights.append(
            f"Slow movers (under ${threshold}/day): {', '.join(names)}"
        )
```

**Step 2: Verify import works**

Run: `python -c "from services.insights import generate_insights; print('OK')"`

**Step 3: Commit**

```bash
git add services/insights.py
git commit -m "feat: add template-based insight engine for dashboard and PDF"
```

---

## Task 3: Create components/metrics.py — Shared Metric Cards

**Files:**
- Create: `components/metrics.py`

**What it does:**
Render a consistent 3-metric row (Revenue, Transactions, Avg Basket) with optional delta values, plus a "More Details" expander with secondary metrics. Replaces the copy-pasted metric blocks in daily.py, weekly.py, monthly.py.

**Step 1: Create components/metrics.py**

```python
"""Shared metric card rendering for dashboard and tool views."""

import streamlit as st


def render_primary_metrics(df, delta_label=None, delta_values=None):
    """Render the 3 primary metric cards: Revenue, Transactions, Avg Basket.

    Args:
        df: DataFrame with Revenue, Basket_ID, Quantity columns.
        delta_label: Optional label for delta (e.g., "vs typical Monday").
        delta_values: Optional dict with keys 'revenue', 'transactions', 'basket'
                      containing (value, is_positive) tuples for delta display.
    """
    num_baskets = df["Basket_ID"].nunique()
    total_rev = df["Revenue"].sum()
    avg_basket = total_rev / num_baskets if num_baskets > 0 else 0

    c1, c2, c3 = st.columns(3)

    rev_delta = None
    trans_delta = None
    basket_delta = None

    if delta_values:
        if "revenue" in delta_values:
            rev_delta = delta_values["revenue"]
        if "transactions" in delta_values:
            trans_delta = delta_values["transactions"]
        if "basket" in delta_values:
            basket_delta = delta_values["basket"]

    with c1:
        st.metric(
            "Revenue", f"${total_rev:,.2f}",
            delta=rev_delta, help=delta_label,
        )
    with c2:
        st.metric(
            "Transactions", f"{num_baskets:,}",
            delta=trans_delta, help=delta_label,
        )
    with c3:
        st.metric(
            "Avg Basket", f"${avg_basket:.2f}",
            delta=basket_delta, help=delta_label,
        )

    return total_rev, num_baskets, avg_basket


def render_period_metrics(df):
    """Render period-specific 3 metrics: Total Revenue, Daily Average, Best Day.

    Used in the 'This Period' section of the dashboard when range > 1 day.
    """
    total_rev = df["Revenue"].sum()
    daily_rev = df.groupby("Date")["Revenue"].sum()
    daily_avg = daily_rev.mean()
    best_date = daily_rev.idxmax()
    best_rev = daily_rev.max()
    best_name = best_date.strftime("%a %b %d")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total Revenue", f"${total_rev:,.2f}")
    with c2:
        st.metric("Daily Average", f"${daily_avg:,.2f}")
    with c3:
        st.metric("Best Day", f"${best_rev:,.2f}", delta=best_name)

    return total_rev, daily_avg, best_rev


def render_secondary_metrics(df):
    """Render the secondary metrics expander: Units, Avg Items/Trans, Avg Price or Daily Rev."""
    num_baskets = df["Basket_ID"].nunique()
    total_rev = df["Revenue"].sum()
    days = df["Date"].dt.date.nunique()

    with st.expander("More Details"):
        d1, d2, d3 = st.columns(3)
        with d1:
            st.metric("Units Sold", f"{int(df['Quantity'].sum()):,}")
        with d2:
            avg_items = df["Quantity"].sum() / num_baskets if num_baskets > 0 else 0
            st.metric("Avg Items/Trans", f"{avg_items:.1f}")
        with d3:
            if days > 1:
                avg_daily = total_rev / days
                st.metric("Avg Daily Rev", f"${avg_daily:,.0f}")
            else:
                avg_price = total_rev / df["Quantity"].sum() if df["Quantity"].sum() > 0 else 0
                st.metric("Avg Price/Unit", f"${avg_price:.2f}")
```

**Step 2: Verify import works**

Run: `python -c "from components.metrics import render_primary_metrics; print('OK')"`

**Step 3: Commit**

```bash
git add components/metrics.py
git commit -m "feat: add shared metric card component"
```

---

## Task 4: Create reports/charts.py — Shared PDF Chart Rendering

**Files:**
- Create: `reports/charts.py`

**What it does:**
Extract the duplicated ReportLab chart rendering code from `reports/standard.py`, `reports/average_day.py`, and `reports/comparison.py` into shared functions. Each function returns a ReportLab `Drawing` object.

**Step 1: Create reports/charts.py**

```python
"""Shared ReportLab chart rendering for PDF reports."""

from reportlab.graphics.charts.barcharts import HorizontalBarChart, VerticalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors

from config import PDF_HEADER_BG, PDF_POSITIVE, PDF_NEGATIVE, PIE_COLORS


def render_horizontal_bar_chart(
    labels, values, width=420, height=250, bar_color=None,
    label_format="${:,.0f}", value_suffix="",
):
    """Horizontal bar chart (e.g., top products, category revenue).

    Args:
        labels: List of category/product names (will be truncated to 22 chars).
        values: List of numeric values.
        width, height: Drawing dimensions.
        bar_color: Hex color string. Defaults to PDF_HEADER_BG.
        label_format: Format string for axis labels.

    Returns:
        ReportLab Drawing object.
    """
    if not values:
        return Drawing(width, height)

    bar_color = bar_color or PDF_HEADER_BG
    d = Drawing(width, height)
    bc = HorizontalBarChart()
    bc.x = 130
    bc.y = 20
    bc.height = height - 40
    bc.width = width - 160
    bc.data = [values]
    bc.categoryAxis.categoryNames = [
        f"{name[:22]} ({label_format.format(val)}{value_suffix})"
        for name, val in zip(labels, values)
    ]
    bc.categoryAxis.labels.fontSize = 7
    bc.categoryAxis.labels.dx = -5
    bc.valueAxis.labels.fontSize = 7
    bc.valueAxis.valueMin = 0
    bc.bars[0].fillColor = colors.HexColor(bar_color)
    d.add(bc)
    return d


def render_vertical_bar_chart(
    labels, values, width=420, height=250, bar_color=None,
):
    """Vertical bar chart (e.g., hourly distribution, basket sizes).

    Args:
        labels: List of x-axis labels.
        values: List of numeric values.
        width, height: Drawing dimensions.
        bar_color: Hex color string. Defaults to PDF_HEADER_BG.

    Returns:
        ReportLab Drawing object.
    """
    if not values:
        return Drawing(width, height)

    bar_color = bar_color or PDF_HEADER_BG
    d = Drawing(width, height)
    bc = VerticalBarChart()
    bc.x = 50
    bc.y = 30
    bc.height = height - 60
    bc.width = width - 80
    bc.data = [values]
    bc.categoryAxis.categoryNames = labels
    bc.categoryAxis.labels.fontSize = 7
    bc.categoryAxis.labels.angle = 0
    bc.valueAxis.labels.fontSize = 7
    bc.valueAxis.valueMin = 0
    bc.bars[0].fillColor = colors.HexColor(bar_color)
    d.add(bc)
    return d


def render_delta_bar_chart(
    labels, values, width=420, height=250,
):
    """Vertical bar chart with per-bar coloring (green/red by sign).

    Used for comparison deltas — positive bars green, negative bars red.
    """
    if not values:
        return Drawing(width, height)

    d = Drawing(width, height)
    bc = VerticalBarChart()
    bc.x = 50
    bc.y = 30
    bc.height = height - 60
    bc.width = width - 80
    bc.data = [values]
    bc.categoryAxis.categoryNames = labels
    bc.categoryAxis.labels.fontSize = 7
    bc.categoryAxis.labels.angle = 45
    bc.valueAxis.labels.fontSize = 7
    for i, val in enumerate(values):
        bc.bars[(0, i)].fillColor = colors.HexColor(
            PDF_POSITIVE if val >= 0 else PDF_NEGATIVE
        )
    d.add(bc)
    return d


def render_line_chart(
    labels, data_series, width=420, height=200,
    line_colors=None, dash_patterns=None,
):
    """Line chart for time-series data.

    Args:
        labels: List of x-axis labels (e.g., hours, dates).
        data_series: List of lists — each inner list is one line's y-values.
        width, height: Drawing dimensions.
        line_colors: List of hex color strings, one per series.
        dash_patterns: List of dash arrays (e.g., [4,2]) or None for solid.

    Returns:
        ReportLab Drawing object.
    """
    if not data_series or not data_series[0]:
        return Drawing(width, height)

    line_colors = line_colors or [PDF_HEADER_BG]
    d = Drawing(width, height)
    lc = HorizontalLineChart()
    lc.x = 50
    lc.y = 30
    lc.height = height - 50
    lc.width = width - 80
    lc.data = data_series
    lc.categoryAxis.categoryNames = labels

    # Show every Nth label for readability
    n = len(labels)
    step = max(1, n // 10)
    for i, label in enumerate(labels):
        if i % step != 0:
            lc.categoryAxis.categoryNames[i] = ""

    lc.categoryAxis.labels.fontSize = 7
    lc.categoryAxis.labels.angle = 45
    lc.valueAxis.labels.fontSize = 7

    for i, series in enumerate(data_series):
        color = line_colors[i] if i < len(line_colors) else PDF_HEADER_BG
        lc.lines[i].strokeColor = colors.HexColor(color)
        lc.lines[i].strokeWidth = 2.5
        if dash_patterns and i < len(dash_patterns) and dash_patterns[i]:
            lc.lines[i].strokeDashArray = dash_patterns[i]

    d.add(lc)
    return d


def render_pie_chart(labels, values, width=300, height=200):
    """Pie chart for category distribution.

    Args:
        labels: List of category names.
        values: List of numeric values.
        width, height: Drawing dimensions.

    Returns:
        ReportLab Drawing object.
    """
    if not values:
        return Drawing(width, height)

    d = Drawing(width, height)
    pie = Pie()
    pie.x = width // 2 - 70
    pie.y = 10
    pie.width = 140
    pie.height = 140
    pie.data = values
    total = sum(values) or 1
    pie.labels = [
        f"{name[:15]}\n{val / total * 100:.1f}%"
        for name, val in zip(labels, values)
    ]
    for i in range(len(values)):
        color_idx = i % len(PIE_COLORS)
        pie.slices[i].fillColor = colors.HexColor(PIE_COLORS[color_idx])
        # Hide labels for tiny slices
        pct = values[i] / total * 100
        if pct < 3:
            pie.slices[i].fontSize = 6
    pie.slices.fontSize = 8
    d.add(pie)
    return d
```

**Step 2: Verify import works**

Run: `python -c "from reports.charts import render_horizontal_bar_chart; print('OK')"`

**Step 3: Commit**

```bash
git add reports/charts.py
git commit -m "feat: extract shared PDF chart rendering into reports/charts.py"
```

---

## Task 5: Simplify components/filters.py — Remove Day-of-Week Filter

**Files:**
- Modify: `components/filters.py`

**What changes:**
- Delete `render_day_of_week_filter()` function entirely
- Simplify `apply_filters()` — remove `day_filter_mode` and `selected_days` params
- Simplify `render_filter_summary()` — remove day filter references
- Add "Reset Filters" as a clean link (replaces fragile key-deletion logic)

**Step 1: Rewrite components/filters.py**

Replace the entire file with:

```python
"""Sidebar filter components."""

import streamlit as st


def render_category_product_filters(df):
    """Render category and product dropdown filters in sidebar. Returns (selected_category, selected_product)."""
    with st.sidebar:
        st.markdown("### Filters")
        selected_category = st.selectbox(
            "Category",
            options=["All Categories"] + sorted(df["Category"].unique()),
            index=0,
            key="main_category_filter",
        )

        if selected_category != "All Categories":
            available = sorted(df[df["Category"] == selected_category]["Description"].unique())
            product_label = f"All Products in {selected_category}"
        else:
            available = sorted(df["Description"].unique())
            product_label = "All Products"

        selected_product = st.selectbox(
            "Product",
            options=[product_label] + available,
            index=0,
            key="main_product_filter",
        )

        # Normalize "All Products in X" back to "All Products" for downstream code
        if selected_product.startswith("All Products"):
            selected_product = "All Products"

    return selected_category, selected_product


def render_hour_range_filter(df):
    """Render the hour-range slider in sidebar. Returns (start_hour, end_hour) tuple."""
    with st.sidebar:
        if "Hour" in df.columns:
            min_hour = int(df["Hour"].min())
            max_hour = int(df["Hour"].max())
        else:
            min_hour, max_hour = 6, 21

        hour_range = st.slider(
            "Hour Range",
            min_value=min_hour,
            max_value=max_hour,
            value=(min_hour, max_hour),
            step=1,
            format="%d:00",
            key="hour_range_slider",
        )

    return hour_range


def render_reset_filters():
    """Render a 'Reset Filters' link in the sidebar."""
    with st.sidebar:
        if st.button("Reset Filters", key="reset_all_filters", use_container_width=True):
            keys_to_clear = [k for k in st.session_state if "filter" in k or k == "hour_range_slider"]
            for key in keys_to_clear:
                del st.session_state[key]
            st.rerun()


def apply_filters(df, selected_category, selected_product, hour_range):
    """Apply all active filters to the dataframe. Returns filtered df."""
    filtered = df.copy()

    start_hour, end_hour = hour_range
    filtered = filtered[(filtered["Hour"] >= start_hour) & (filtered["Hour"] <= end_hour)]

    if selected_category != "All Categories":
        filtered = filtered[filtered["Category"] == selected_category]
    if selected_product != "All Products":
        filtered = filtered[filtered["Description"] == selected_product]

    return filtered


def render_filter_summary(filtered_df, selected_category, selected_product):
    """Show a compact filter summary when filters are active."""
    any_filter = (
        selected_category != "All Categories"
        or selected_product != "All Products"
    )
    if not any_filter:
        return

    parts = []
    if selected_category != "All Categories":
        parts.append(selected_category)
    if selected_product != "All Products":
        parts.append(selected_product)

    unique_days = filtered_df["Date"].nunique() if not filtered_df.empty else 0
    num_transactions = len(filtered_df)

    st.caption(f"Filtered: {' | '.join(parts)} ({unique_days} days, {num_transactions:,} rows)")
```

**Important:** This will break `app.py` temporarily because app.py imports `render_day_of_week_filter` and calls `apply_filters` with 6 args. That's OK — we fix app.py in Task 7. The new filter functions are ready for the new routing.

Actually, we need the app to keep working. Let's keep backward compatibility temporarily:

**Revised approach:** Add the new simplified functions alongside the old ones. The old functions stay until Task 7 removes them. Add `# DEPRECATED` comments.

Replace `render_filter_summary` signature to accept optional day params:

Actually the simplest approach: keep the old `apply_filters` signature working by making the day params optional with defaults:

```python
def apply_filters(df, selected_category, selected_product, day_filter_mode="All Days", selected_days=None, hour_range=(0, 23)):
```

This way existing calls still work. The new dashboard code just won't pass the day params.

**Revised Step 1: Edit components/filters.py to:**
1. Keep `render_day_of_week_filter` but add `# DEPRECATED — remove in Task 7`
2. Make `apply_filters` day params optional with defaults
3. Add `render_reset_filters()` function
4. Make `render_filter_summary` day params optional

```python
"""Sidebar filter components."""

import streamlit as st


def render_category_product_filters(df):
    """Render category and product dropdown filters in sidebar. Returns (selected_category, selected_product)."""
    with st.sidebar:
        st.markdown("### Filters")
        selected_category = st.selectbox(
            "Category",
            options=["All Categories"] + sorted(df["Category"].unique()),
            index=0,
            key="main_category_filter",
        )

        if selected_category != "All Categories":
            available = sorted(df[df["Category"] == selected_category]["Description"].unique())
            product_label = f"All Products in {selected_category}"
        else:
            available = sorted(df["Description"].unique())
            product_label = "All Products"

        selected_product = st.selectbox(
            "Product",
            options=[product_label] + available,
            index=0,
            key="main_product_filter",
        )

        # Normalize display-friendly label back to code-friendly sentinel
        if selected_product.startswith("All Products"):
            selected_product = "All Products"

    return selected_category, selected_product


# DEPRECATED — will be removed when app.py is rewritten (Task 7)
def render_day_of_week_filter(days_span):
    """Render the day-of-week filter in sidebar. Returns (day_filter_mode, selected_days)."""
    selected_days = None

    if days_span < 7:
        st.session_state.day_filter_mode = "All Days"
        return "All Days", None

    with st.sidebar:
        if "day_filter_mode" not in st.session_state:
            st.session_state.day_filter_mode = "All Days"

        day_options = ["All Days", "Weekdays", "Weekends", "Custom"]
        current_idx = day_options.index(st.session_state.day_filter_mode) if st.session_state.day_filter_mode in day_options else 0
        day_filter_mode = st.radio(
            "Day Filter",
            options=day_options,
            index=current_idx,
            key="day_filter_radio",
            horizontal=True,
        )
        if day_filter_mode != st.session_state.day_filter_mode:
            st.session_state.day_filter_mode = day_filter_mode
            st.rerun()

        if st.session_state.day_filter_mode == "Custom":
            st.markdown("**Select days:**")
            lc, rc = st.columns(2)
            with lc:
                mon = st.checkbox("Mon", value=True, key="mon")
                tue = st.checkbox("Tue", value=True, key="tue")
                wed = st.checkbox("Wed", value=True, key="wed")
                thu = st.checkbox("Thu", value=True, key="thu")
            with rc:
                fri = st.checkbox("Fri", value=True, key="fri")
                sat = st.checkbox("Sat", value=True, key="sat")
                sun = st.checkbox("Sun", value=True, key="sun")
            selected_days = [i for i, checked in enumerate([mon, tue, wed, thu, fri, sat, sun]) if checked]

    return st.session_state.day_filter_mode, selected_days


def render_hour_range_filter(df):
    """Render the hour-range slider in sidebar. Returns (start_hour, end_hour) tuple."""
    with st.sidebar:
        if "Hour" in df.columns:
            min_hour = int(df["Hour"].min())
            max_hour = int(df["Hour"].max())
        else:
            min_hour, max_hour = 6, 21

        hour_range = st.slider(
            "Hour Range",
            min_value=min_hour,
            max_value=max_hour,
            value=(min_hour, max_hour),
            step=1,
            format="%d:00",
            key="hour_range_slider",
        )

    return hour_range


def render_reset_filters():
    """Render a 'Reset Filters' link in the sidebar."""
    with st.sidebar:
        if st.button("Reset Filters", key="reset_all_filters", use_container_width=True):
            keys_to_clear = [k for k in st.session_state if "filter" in k or k == "hour_range_slider"]
            for key in keys_to_clear:
                del st.session_state[key]
            st.rerun()


def apply_filters(df, selected_category, selected_product, day_filter_mode="All Days", selected_days=None, hour_range=(0, 23)):
    """Apply all active filters to the dataframe. Returns filtered df."""
    filtered = df.copy()

    start_hour, end_hour = hour_range
    filtered = filtered[(filtered["Hour"] >= start_hour) & (filtered["Hour"] <= end_hour)]

    if selected_category != "All Categories":
        filtered = filtered[filtered["Category"] == selected_category]
    if selected_product != "All Products":
        filtered = filtered[filtered["Description"] == selected_product]

    # DEPRECATED day filtering — kept for backward compat until app.py rewrite
    if day_filter_mode == "Weekdays":
        filtered = filtered[filtered["Date"].dt.dayofweek < 5]
    elif day_filter_mode == "Weekends":
        filtered = filtered[filtered["Date"].dt.dayofweek >= 5]
    elif day_filter_mode == "Custom" and selected_days:
        filtered = filtered[filtered["Date"].dt.dayofweek.isin(selected_days)]

    return filtered


def render_filter_summary(filtered_df, selected_category, selected_product, day_filter_mode="All Days", selected_days=None):
    """Show a compact filter summary when filters are active."""
    any_filter = (
        selected_category != "All Categories"
        or selected_product != "All Products"
        or day_filter_mode != "All Days"
    )
    if not any_filter:
        return

    parts = []
    if selected_category != "All Categories":
        parts.append(selected_category)
    if selected_product != "All Products":
        parts.append(selected_product)
    if day_filter_mode != "All Days":
        if day_filter_mode == "Custom" and selected_days is not None:
            day_map = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}
            parts.append("Days: " + ", ".join(day_map[d] for d in sorted(selected_days)))
        else:
            parts.append(day_filter_mode)

    unique_days = filtered_df["Date"].nunique() if not filtered_df.empty else 0
    num_transactions = len(filtered_df)

    st.caption(f"Filtered: {' | '.join(parts)} ({unique_days} days, {num_transactions:,} rows)")
```

**Step 2: Verify app still runs**

Run: `streamlit run app.py` — should work identically to before (backward-compatible changes).

**Step 3: Commit**

```bash
git add components/filters.py
git commit -m "feat: add reset filters, make day-of-week params optional for deprecation"
```

---

## Task 6: Create views/dashboard.py — Unified Dashboard

**Files:**
- Create: `views/dashboard.py`

**What it does:**
The core new view. Three sections always visible:
- **Section A ("Yesterday")**: Latest day metrics + insights + delta vs typical day
- **Section B ("This Period")**: Full range metrics + revenue bar chart (only if range > 1 day)
- **Section C ("What's Selling")**: Top 8 products bar + category pie + slow movers

Below the fold: "More Tools" buttons + Export section.

**Step 1: Create views/dashboard.py**

```python
"""Unified dashboard view — replaces daily/weekly/monthly modes."""

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from components.insight_card import render_insight
from components.metrics import render_primary_metrics, render_period_metrics, render_secondary_metrics
from config import (
    CHART_HIGHLIGHT, CHART_PRIMARY,
    INSIGHT_TOP_PRODUCTS, INSIGHT_WEEKLY_AGGREGATE_DAYS,
)
from services.insights import generate_yesterday_insights, generate_period_insights, generate_product_insights


def render(df, selected_category, selected_product):
    """Render the unified dashboard.

    Args:
        df: Filtered DataFrame.
        selected_category: Currently selected category filter value.
        selected_product: Currently selected product filter value.
    """
    min_date = df["Date"].min()
    max_date = df["Date"].max()
    days_span = (max_date - min_date).days + 1

    # --- Section A: Yesterday (latest day) ---
    latest_date = max_date
    latest_day = df[df["Date"] == latest_date]
    day_name = latest_date.strftime("%A")

    st.markdown(f"## {day_name}'s Numbers")
    st.caption(f"{latest_date.strftime('%B %d, %Y')}")

    # Compute delta vs typical same-weekday
    delta_label = None
    delta_values = None
    same_day_data = df[df["DayName"] == day_name]
    day_count = same_day_data["Date"].dt.date.nunique()

    if day_count > 1 and not latest_day.empty:
        # Average for this weekday across loaded data (excluding the latest day itself for cleaner comparison)
        other_days = same_day_data[same_day_data["Date"] != latest_date]
        if not other_days.empty:
            avg_rev = other_days.groupby(other_days["Date"].dt.date)["Revenue"].sum().mean()
            avg_trans = other_days.groupby(other_days["Date"].dt.date)["Basket_ID"].nunique().mean()
            avg_basket_val = avg_rev / avg_trans if avg_trans > 0 else 0

            actual_rev = latest_day["Revenue"].sum()
            actual_trans = latest_day["Basket_ID"].nunique()
            actual_basket = actual_rev / actual_trans if actual_trans > 0 else 0

            rev_pct = ((actual_rev - avg_rev) / avg_rev * 100) if avg_rev > 0 else 0
            trans_pct = ((actual_trans - avg_trans) / avg_trans * 100) if avg_trans > 0 else 0
            basket_pct = ((actual_basket - avg_basket_val) / avg_basket_val * 100) if avg_basket_val > 0 else 0

            delta_label = f"vs typical {day_name}"
            delta_values = {
                "revenue": f"{rev_pct:+.0f}%",
                "transactions": f"{trans_pct:+.0f}%",
                "basket": f"{basket_pct:+.0f}%",
            }

    render_primary_metrics(latest_day, delta_label=delta_label, delta_values=delta_values)

    # Yesterday insights
    yesterday_insights = generate_yesterday_insights(df, latest_day, latest_date)
    for text in yesterday_insights[:2]:
        render_insight(text)

    # --- Section B: This Period (multi-day only) ---
    if days_span > 1:
        st.markdown("---")
        st.markdown("## This Period")
        st.caption(f"{min_date.strftime('%B %d')} — {max_date.strftime('%B %d, %Y')} ({days_span} days)")

        render_period_metrics(df)

        # Revenue chart: bars for <=14 days, weekly aggregated for 15+
        if days_span <= INSIGHT_WEEKLY_AGGREGATE_DAYS:
            _render_daily_bar_chart(df)
        else:
            _render_weekly_bar_chart(df)

        # Period insights
        period_insights = generate_period_insights(df, days_span)
        for text in period_insights[:2]:
            render_insight(text)

    # --- Section C: What's Selling ---
    st.markdown("---")
    st.markdown("## What's Selling")

    left, right = st.columns(2)

    with left:
        _render_top_products(df, selected_category)

    with right:
        # Hide category pie if a single category is filtered (pointless)
        if selected_category == "All Categories":
            _render_category_pie(df)
        else:
            # Show product breakdown within category instead
            _render_product_breakdown(df, selected_category)

    # Slow movers
    product_insights = generate_product_insights(df, days_span)
    for text in product_insights:
        if "slow" in text.lower():
            render_insight(text)

    # More details
    render_secondary_metrics(df)

    # --- More Tools ---
    st.markdown("---")
    st.markdown("### More Tools")

    tc1, tc2, tc3 = st.columns(3)
    with tc1:
        if st.button("Model a Typical Day", use_container_width=True, key="tool_typical_day"):
            st.session_state.active_tool = "Typical Day"
            st.rerun()
    with tc2:
        if st.button("Compare Two Periods", use_container_width=True, key="tool_compare"):
            st.session_state.active_tool = "Compare"
            st.rerun()
    with tc3:
        if st.button("Basket Patterns", use_container_width=True, key="tool_baskets"):
            st.session_state.active_tool = "Baskets"
            st.rerun()


# --- Private chart rendering functions ---


def _render_daily_bar_chart(df):
    """Revenue by day — bar chart for short date ranges (<=14 days)."""
    daily = df.groupby("Date").agg({"Revenue": "sum"}).reset_index()
    daily["DayName"] = daily["Date"].dt.day_name()
    daily["Label"] = daily["Date"].dt.strftime("%b %d") + " (" + daily["DayName"].str[:3] + ")"

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=daily["Label"], y=daily["Revenue"], marker_color=CHART_HIGHLIGHT,
        text=[f"${r:,.0f}" for r in daily["Revenue"]], textposition="outside",
        textfont=dict(size=10),
        hovertemplate="<b>%{x}</b><br>Revenue: $%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        height=350, margin=dict(l=0, r=0, t=20, b=40),
        xaxis=dict(title="", tickangle=-45, showgrid=False),
        yaxis=dict(title="Revenue ($)", tickformat="$,.0f",
                   showgrid=True, gridcolor="rgba(0,0,0,0.05)"),
        plot_bgcolor="white", showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_weekly_bar_chart(df):
    """Revenue by week — aggregated bars for longer ranges (15+ days)."""
    tmp = df.copy()
    start = tmp["Date"].min()
    tmp["WeekNum"] = ((tmp["Date"] - start).dt.days // 7) + 1

    weekly = tmp.groupby("WeekNum").agg(
        Revenue=("Revenue", "sum"),
        StartDate=("Date", "min"),
        EndDate=("Date", "max"),
    ).reset_index()

    labels = []
    for _, row in weekly.iterrows():
        s, e = row["StartDate"], row["EndDate"]
        if s.strftime("%b") != e.strftime("%b"):
            labels.append(f"{s.strftime('%b')} {s.day}-{e.strftime('%b')} {e.day}")
        else:
            labels.append(f"{s.strftime('%b')} {s.day}-{e.day}")
    weekly["Label"] = labels

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=weekly["Label"], y=weekly["Revenue"], marker_color=CHART_HIGHLIGHT,
        text=[f"${r:,.0f}" for r in weekly["Revenue"]], textposition="outside",
        textfont=dict(size=10),
        hovertemplate="<b>%{x}</b><br>Revenue: $%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        height=350, margin=dict(l=0, r=0, t=20, b=40),
        xaxis=dict(title="Week", showgrid=False),
        yaxis=dict(title="Revenue ($)", tickformat="$,.0f",
                   showgrid=True, gridcolor="rgba(0,0,0,0.05)"),
        plot_bgcolor="white", showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_top_products(df, selected_category):
    """Top N products horizontal bar chart."""
    n = INSIGHT_TOP_PRODUCTS
    if selected_category != "All Categories":
        st.caption(f"Top products in: **{selected_category}**")

    top = df.groupby("Description").agg({"Revenue": "sum", "Quantity": "sum"}).sort_values(
        "Revenue", ascending=True
    ).tail(n)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=top.index, x=top["Revenue"], orientation="h", marker_color=CHART_PRIMARY,
        text=[f"${r:,.0f}" for r in top["Revenue"]], textposition="outside",
        textfont=dict(size=11, color="#5A6B5E"),
        hovertemplate="<b>%{y}</b><br>$%{x:,.0f} - %{customdata} units<extra></extra>",
        customdata=top["Quantity"].astype(int),
    ))
    fig.update_layout(
        showlegend=False, height=400, margin=dict(l=0, r=80, t=20, b=0),
        xaxis=dict(title="Revenue ($)", tickformat="$,.0f"), yaxis=dict(title=""),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_category_pie(df):
    """Category mix donut chart."""
    data = df.groupby("Category")["Revenue"].sum().sort_values(ascending=False)

    fig = go.Figure(data=[go.Pie(
        labels=data.index, values=data.values, hole=0.5,
        marker=dict(colors=px.colors.qualitative.Pastel),
        texttemplate="%{percent}", textposition="inside",
        textfont=dict(size=11, color="white"),
        hovertemplate="<b>%{label}</b><br>$%{value:,.0f} - %{percent}<extra></extra>",
    )])
    fig.update_layout(
        height=400, margin=dict(l=20, r=20, t=20, b=20), showlegend=True,
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.05, font=dict(size=10)),
        annotations=[dict(text=f"${data.sum():,.0f}<br>Total", x=0.5, y=0.5, font_size=16, showarrow=False)],
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_product_breakdown(df, selected_category):
    """Product breakdown within a filtered category — replaces pie when single category selected."""
    st.caption(f"Product mix within: **{selected_category}**")
    data = df.groupby("Description")["Revenue"].sum().sort_values(ascending=False)
    top6 = data.nlargest(6)
    other = data[~data.index.isin(top6.index)].sum()

    import pandas as pd
    if other > 0:
        plot_data = pd.concat([top6, pd.Series({"Others": other})])
    else:
        plot_data = top6

    fig = go.Figure(data=[go.Pie(
        labels=plot_data.index, values=plot_data.values, hole=0.5,
        marker=dict(colors=px.colors.qualitative.Set2),
        texttemplate="%{percent}", textposition="inside",
        textfont=dict(size=11, color="white"),
        hovertemplate="<b>%{label}</b><br>$%{value:,.0f} - %{percent}<extra></extra>",
    )])
    fig.update_layout(
        height=400, margin=dict(l=20, r=20, t=20, b=20), showlegend=True,
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.05, font=dict(size=10)),
    )
    st.plotly_chart(fig, use_container_width=True)
```

**Step 2: Verify import works**

Run: `python -c "from views.dashboard import render; print('OK')"`

**Step 3: Commit**

```bash
git add views/dashboard.py
git commit -m "feat: add unified dashboard view replacing daily/weekly/monthly"
```

---

## Task 7: Rewrite app.py — New Routing, Kill Mode Selector

**Files:**
- Modify: `app.py`

**What changes:**
- Remove mode selector buttons entirely
- Remove `analysis_view_mode` session state
- Remove day-of-week filter calls
- Remove `DAILY_MAX_DAYS` / `WEEKLY_MAX_DAYS` imports
- Default to dashboard view
- Route to tool views via `st.session_state.active_tool`
- Tool views get "Back to Dashboard" button
- Simplify filter pipeline (no day filter)

**Step 1: Rewrite app.py**

Replace the entire file with:

```python
"""TMB Harris Farm - Retail Sales Analytics Dashboard.

Main entry point. Run with: streamlit run app.py
"""

import streamlit as st

from config import TMB_SALES_FOLDER_ID
from styles import MAIN_CSS
from services.gdrive import get_service
from components.header import render_header, render_date_banner
from components.date_picker import render_date_picker
from components.filters import (
    render_category_product_filters,
    render_hour_range_filter,
    render_reset_filters,
    apply_filters,
    render_filter_summary,
)
from views import dashboard, basket, compare, average_day
from reports.standard import generate as generate_pdf
from reports.average_day import generate as generate_avg_day_pdf


# --- Page Config ---
st.set_page_config(page_title="Three Mills Analytics Pro", layout="wide", page_icon="🥖")
st.markdown(MAIN_CSS, unsafe_allow_html=True)

# --- Header ---
render_header()

# --- Google Drive Connection ---
service, error = get_service()

if service:
    st.session_state.folder_id = TMB_SALES_FOLDER_ID
else:
    st.error("Google Drive Not Connected")
    st.error(error)
    with st.expander("How to set up Google Drive"):
        st.markdown(
            """
            **Quick Setup (5 minutes):**

            1. Go to [Google Cloud Console](https://console.cloud.google.com/)
            2. Create a project & enable Google Drive API
            3. Create a Service Account and download the JSON key
            4. Rename it to `service_account.json` and put it in the app folder
            5. Share your Drive folder with the service account email
            """
        )


# =====================================================================
# DATA LOADED - Main dashboard
# =====================================================================
if "df" in st.session_state and not st.session_state.df.empty:
    df = st.session_state.df

    # Unmapped products warning
    other_products = df[df["Category"] == "Other"]["Description"].unique()
    if len(other_products) > 0:
        with st.sidebar:
            st.warning(f"{len(other_products)} product(s) categorized as 'Other': {', '.join(other_products[:5])}")

    # Category manager in sidebar
    with st.sidebar:
        with st.expander("Manage Categories"):
            from components.category_manager import render_category_manager
            render_category_manager()

    min_date = df["Date"].min()
    max_date = df["Date"].max()
    days_span = (max_date - min_date).days + 1

    # Date banner
    render_date_banner(min_date, max_date, days_span)

    if st.button("Change Date Range", type="secondary"):
        del st.session_state.df
        if "data_loaded" in st.session_state:
            del st.session_state.data_loaded
        if "active_tool" in st.session_state:
            del st.session_state.active_tool
        st.rerun()

    st.markdown("---")

    # --- Filters (sidebar) ---
    selected_category, selected_product = render_category_product_filters(df)
    hour_range = render_hour_range_filter(df)
    render_reset_filters()

    # Apply filters (no day-of-week filter anymore)
    filtered_df = apply_filters(df, selected_category, selected_product, hour_range=hour_range)

    # Filter summary
    active_tool = st.session_state.get("active_tool")
    if active_tool != "Typical Day":
        render_filter_summary(filtered_df, selected_category, selected_product)

    # --- Route: Tool view or Dashboard ---
    if active_tool == "Typical Day":
        # "Back to Dashboard" button
        if st.button("← Back to Dashboard", key="back_from_typical"):
            del st.session_state.active_tool
            st.rerun()

        from config import DAY_NAMES_ORDERED, MONTH_NAMES

        st.markdown("### Typical Day Settings")
        ad_col1, ad_col2 = st.columns(2)
        with ad_col1:
            selected_day = st.selectbox(
                "Day of the week to model:",
                options=DAY_NAMES_ORDERED,
                key="avg_day_selector",
            )
        with ad_col2:
            available_months = sorted(df["Date"].dt.month.unique())
            month_options = [MONTH_NAMES[m - 1] for m in available_months]
            selected_month_names = st.multiselect(
                "Filter by months (optional):",
                options=month_options,
                default=month_options,
                key="avg_day_months",
                help="Select specific months to model seasonal patterns",
            )
            if len(selected_month_names) < len(month_options):
                selected_months = [MONTH_NAMES.index(m) + 1 for m in selected_month_names]
            else:
                selected_months = None

        # Check sample size
        day_instances = filtered_df[filtered_df["DayName"] == selected_day]["Date"].dt.date.nunique()
        if day_instances < 4:
            st.warning(
                f"Only **{day_instances}** {selected_day}(s) found in loaded data. "
                f"Load a wider date range for more accurate averages."
            )
        average_day.render(filtered_df, selected_day, selected_category, selected_months)

    elif active_tool == "Compare":
        if st.button("← Back to Dashboard", key="back_from_compare"):
            del st.session_state.active_tool
            st.rerun()

        compare.render(
            service, st.session_state.folder_id,
            min_date.date(), max_date.date(),
            selected_category, selected_product,
            hour_range=hour_range,
        )

    elif active_tool == "Baskets":
        if st.button("← Back to Dashboard", key="back_from_baskets"):
            del st.session_state.active_tool
            st.rerun()

        # Filtered basket warning
        any_filter = (
            selected_category != "All Categories"
            or selected_product != "All Products"
        )
        if any_filter:
            parts = []
            if selected_category != "All Categories":
                parts.append(selected_category)
            if selected_product != "All Products":
                parts.append(selected_product)
            st.warning(
                f"**Filtered View Active:** {' | '.join(parts)}. "
                f"Baskets may contain other products not shown."
            )
        basket.render(filtered_df)

    else:
        # Default: unified dashboard
        dashboard.render(filtered_df, selected_category, selected_product)

    # --- Export (at bottom, after view content) ---
    if active_tool != "Compare":  # Compare has its own export
        with st.expander("Export & Download", expanded=False):
            export_cols = st.columns([1, 1, 1])

            with export_cols[0]:
                if active_tool == "Typical Day":
                    if st.button("Generate Average Day PDF", type="primary", use_container_width=True):
                        with st.spinner("Generating Average Day PDF..."):
                            try:
                                pdf_buf = generate_avg_day_pdf(
                                    filtered_df, selected_day, selected_category, selected_months,
                                )
                                st.download_button(
                                    "Download PDF", data=pdf_buf,
                                    file_name=f"TMB_Average_{selected_day}_Report.pdf",
                                    mime="application/pdf", key="avg_day_pdf",
                                )
                                import base64
                                b64 = base64.b64encode(pdf_buf.getvalue()).decode()
                                st.markdown(
                                    f'<iframe src="data:application/pdf;base64,{b64}" '
                                    f'width="100%" height="500" type="application/pdf"></iframe>',
                                    unsafe_allow_html=True,
                                )
                            except Exception as e:
                                st.error(f"PDF generation failed: {e}")
                else:
                    if st.button("Generate PDF Report", type="primary", use_container_width=True):
                        with st.spinner("Generating PDF report..."):
                            try:
                                pdf_buf = generate_pdf(
                                    filtered_df, min_date, max_date,
                                    selected_category, selected_product,
                                    "All Days", hour_range,
                                )
                                date_str = f"{min_date.strftime('%Y%m%d')}_{max_date.strftime('%Y%m%d')}"
                                st.download_button(
                                    "Download PDF Report", data=pdf_buf,
                                    file_name=f"TMB_Report_{date_str}.pdf", mime="application/pdf",
                                    key=f"pdf_{date_str}",
                                )
                                import base64
                                b64 = base64.b64encode(pdf_buf.getvalue()).decode()
                                st.markdown(
                                    f'<iframe src="data:application/pdf;base64,{b64}" '
                                    f'width="100%" height="500" type="application/pdf"></iframe>',
                                    unsafe_allow_html=True,
                                )
                            except Exception as e:
                                st.error(f"PDF generation failed: {e}")

            with export_cols[1]:
                csv_data = filtered_df.to_csv(index=False).encode("utf-8")
                date_str = f"{min_date.strftime('%Y%m%d')}_{max_date.strftime('%Y%m%d')}"
                st.download_button(
                    "Download CSV", data=csv_data,
                    file_name=f"TMB_Data_{date_str}.csv", mime="text/csv",
                    key="csv_export", use_container_width=True,
                )

            with export_cols[2]:
                from io import BytesIO
                excel_buf = BytesIO()
                filtered_df.to_excel(excel_buf, index=False, engine="openpyxl")
                excel_buf.seek(0)
                st.download_button(
                    "Download Excel", data=excel_buf,
                    file_name=f"TMB_Data_{date_str}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="excel_export", use_container_width=True,
                )


# =====================================================================
# NO DATA - Show date picker
# =====================================================================
elif service and st.session_state.get("folder_id"):
    render_date_picker(service, st.session_state.folder_id)


# =====================================================================
# NO CONNECTION - Welcome screen
# =====================================================================
else:
    st.markdown("### What You Can Do:")
    feat = [
        ("Morning Brief", "Revenue, trends & what's selling — all on one page"),
        ("Typical Day Model", "Model a typical Monday, Tuesday, etc. from historical data"),
        ("Period Compare", "Side-by-side comparison of any two time periods"),
    ]
    cols = st.columns(3)
    for col, (title, desc) in zip(cols, feat):
        with col:
            st.markdown(
                f"""
                <div style='padding:20px; background:linear-gradient(135deg,#B5C99A 0%,#7D8570 100%);
                            border-radius:12px; text-align:center; height:180px;'>
                    <h4 style='color:white; margin:0;'>{title}</h4>
                    <p style='color:#FAF9F6; font-size:14px; margin-top:8px;'>{desc}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("### Ready to Get Started?")
    st.info(
        "**Sales data available from May 29, 2024 onwards.**\n\n"
        "Connect Google Drive and select a date range to begin!"
    )


# --- Footer ---
st.markdown("---")
st.markdown(
    """
    <div style='text-align:center; padding:20px; color:#1F2933; font-size:13px;'>
        <p style='margin:0;'><strong>TMB Harris Farm</strong> | Retail Sales Analytics Dashboard</p>
        <p style='margin:5px 0 0 0; opacity:0.7;'>Created by Kapil Pudasaini</p>
    </div>
    """,
    unsafe_allow_html=True,
)
```

**Step 2: Update compare.py to accept hour_range kwarg**

The current `compare.render()` signature is:
```python
def render(service, folder_id, current_start, current_end, selected_category="All Categories", selected_product="All Products", day_filter_mode="All Days", selected_days=None)
```

We need it to also accept `hour_range`. Edit `views/compare.py` — change the signature to:
```python
def render(service, folder_id, current_start, current_end, selected_category="All Categories", selected_product="All Products", day_filter_mode="All Days", selected_days=None, hour_range=None)
```

This is a minimal change — just adding the kwarg. The compare view's internal filtering can use it later.

**Step 3: Clean up config.py — remove old constants**

Now that app.py no longer imports `DAILY_MAX_DAYS` or `WEEKLY_MAX_DAYS`, remove them from config.py:

Delete:
```python
# Analysis mode thresholds (days)
DAILY_MAX_DAYS = 1
WEEKLY_MAX_DAYS = 14
```

**Step 4: Verify app runs**

Run: `streamlit run app.py`
- Load data → should see unified dashboard (Section A, B, C)
- Click "Model a Typical Day" → should navigate to Typical Day with Back button
- Click "← Back to Dashboard" → should return to dashboard
- Repeat for Compare and Baskets

**Step 5: Commit**

```bash
git add app.py views/dashboard.py views/compare.py config.py
git commit -m "feat: replace mode selector with unified dashboard routing"
```

---

## Task 8: Update views/average_day.py — Back Navigation + Bug Fix

**Files:**
- Modify: `views/average_day.py`

**What changes:**
- Back navigation is handled by `app.py` now (done in Task 7) — no changes needed in the view itself for back button
- Fix the styled DataFrame bug at line 311 (if it still exists after exploration — the explore agent noted it may already be fixed)
- Use shared metrics from `components/metrics.py` (optional — can be done later to reduce scope)

**Step 1: Verify the styled DataFrame bug**

Read `views/average_day.py` around line 311. If the bug exists (plain DataFrame rendered instead of styled), fix it. If already fixed, skip.

**Step 2: Fix `.applymap()` deprecation in compare.py**

Read `views/compare.py` around lines 242 and 267. Change `.applymap()` to `.map()`.

**Step 3: Verify app runs with Typical Day tool**

Run: `streamlit run app.py` → Load data → Click "Model a Typical Day" → Verify it renders correctly.

**Step 4: Commit**

```bash
git add views/average_day.py views/compare.py
git commit -m "fix: styled DataFrame bug and .applymap() deprecation"
```

---

## Task 9: Rewrite reports/standard.py — Narrative PDF

**Files:**
- Modify: `reports/standard.py`

**What changes:**
- Page 1 becomes "The Story" — executive brief with headline template, 3 key numbers, and 3 insight bullets from the insight engine
- Page 2 becomes revenue detail (one chart + one table)
- Page 3 becomes product performance (top products bar + category pie)
- Conditional pages (hourly, trend) only appear if data warrants them
- Use `reports/charts.py` shared functions where possible
- Use `services/insights.py` for page 1 bullet points

**This is the largest single task. The approach:**
1. Read the current `reports/standard.py` thoroughly
2. Rewrite it section by section, keeping the ReportLab infrastructure (page templates, styles, `_styled_table`)
3. Replace the page content with narrative structure

**Step 1: Edit reports/standard.py**

The rewrite preserves the existing `generate()` function signature so nothing upstream breaks. Internally restructure pages:

- Keep: header/footer page template, color definitions, `_styled_table` helper
- Replace: page content order and layout
- Add: insight engine integration on page 1
- Add: conditional page logic (only render if data supports it)

Key code changes:
- Import `from services.insights import generate_insights`
- Page 1: render headline + 3 metrics + insight bullets
- Page 2: revenue chart (daily or weekly) + breakdown table
- Page 3: product bar + category pie
- Page 4+: only if data warrants (hourly pattern for single day, trend for 21+ days)

**Full implementation code is too long to inline here.** The executor should:
1. Read the full `reports/standard.py`
2. Reorganize pages following the structure above
3. Replace chart rendering with calls to `reports/charts.py`
4. Add insight engine integration

**Step 2: Verify PDF generation works**

Run app → load data → Export → Generate PDF Report → check it opens and has narrative page 1.

**Step 3: Commit**

```bash
git add reports/standard.py
git commit -m "feat: rewrite standard PDF report as narrative with executive brief"
```

---

## Task 10: Rewrite reports/average_day.py — Narrative PDF

**Files:**
- Modify: `reports/average_day.py`

**Same pattern as Task 9:**
- Page 1 becomes executive brief for Typical Day
- Use insight engine for bullet points
- Use shared charts where applicable
- Conditional pages based on data

**Step 1: Read full reports/average_day.py and restructure**

Key changes:
- Page 1: "Your Typical {DayName}" headline + key metrics + insights
- Page 2: Hourly pattern chart + top products
- Page 3: Category distribution + best sellers table
- Page 4: Conditional — trend + seasonality (only if enough data)

**Step 2: Verify**

Run app → Typical Day → Export → Generate Average Day PDF → check narrative page 1.

**Step 3: Commit**

```bash
git add reports/average_day.py
git commit -m "feat: rewrite average day PDF report as narrative"
```

---

## Task 11: Rewrite reports/comparison.py — Narrative PDF

**Files:**
- Modify: `reports/comparison.py`

**Same pattern:**
- Page 1: Executive brief comparing the two periods
- Headline: "Revenue {up/down} {X}% from Period A to Period B"
- 3 key comparison metrics
- Top insight bullets

**Step 1: Read full reports/comparison.py and restructure**

**Step 2: Verify**

Run app → Compare → load both periods → Export → check PDF.

**Step 3: Commit**

```bash
git add reports/comparison.py
git commit -m "feat: rewrite comparison PDF report as narrative"
```

---

## Task 12: Deprecate Old View Files + Final Cleanup

**Files:**
- Deprecate: `views/daily.py`, `views/weekly.py`, `views/monthly.py`
- Modify: `config.py` (final cleanup)

**Step 1: Add deprecation notice to old view files**

At the top of each file, add:
```python
"""DEPRECATED: This view has been merged into views/dashboard.py.
Kept for reference — will be removed in a future cleanup."""
```

**Step 2: Remove unused imports from config.py**

Verify that `DAILY_MAX_DAYS` and `WEEKLY_MAX_DAYS` are gone (should be done in Task 7). If any other constants are now orphaned, clean them up.

**Step 3: Remove deprecated imports from app.py**

In app.py, remove:
```python
from views import daily, weekly, monthly
```
(These should already not be imported after Task 7 rewrite.)

**Step 4: Final verification**

Run: `streamlit run app.py`
- Full dashboard flow: load data → see unified dashboard
- Navigate to each tool and back
- Generate PDF from dashboard
- Generate PDF from Typical Day
- Generate PDF from Compare

**Step 5: Commit**

```bash
git add views/daily.py views/weekly.py views/monthly.py app.py config.py
git commit -m "chore: deprecate old view files, final cleanup"
```

---

## Implementation Notes for the Executor

### Critical things to know:

1. **The app has NO test framework.** Verification is visual: `streamlit run app.py`. Every task must leave the app runnable.

2. **Session state keys matter.** The new routing uses `st.session_state.active_tool` (values: `"Typical Day"`, `"Compare"`, `"Baskets"`, or absent for dashboard). Don't conflict with existing keys like `analysis_view_mode`.

3. **The `compare.render()` signature is complex.** It loads its own data (Period B) from Google Drive. The `day_filter_mode` param still gets passed as `"All Days"` for backward compat. The hour_range fix (design doc bug) should be addressed but is secondary to the routing change.

4. **PDF reports are ~300-500 lines each.** The narrative rewrite (Tasks 9-11) is the most labor-intensive work. Focus on getting page 1 right — subsequent pages can be incremental improvements.

5. **User preference: no AI-looking code.** Keep the UI language practical and bakery-manager-friendly. "What's Selling" not "Product Performance Analytics." "Yesterday's Numbers" not "Latest Day Metrics."

6. **The `INSIGHT_WEEKLY_AGGREGATE_DAYS = 15` threshold** replaces the old `DAILY_MAX_DAYS = 1` / `WEEKLY_MAX_DAYS = 14` logic. The dashboard shows daily bars for <=14 days, weekly bars for 15+. No mode switching.

### Task priority if time is short:

**Must have (core redesign):** Tasks 1-7 (config, insights, metrics, charts, filters, dashboard, app routing)

**Should have (polish):** Task 8 (bug fixes), Task 12 (cleanup)

**Nice to have (PDF narrative):** Tasks 9-11 — these can be done in a follow-up session since the existing PDFs still work, just without the narrative page 1.
