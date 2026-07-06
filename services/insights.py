"""Template-based insight engine for dashboard cards and PDF bullet points.

Each template has a guard condition: if the data doesn't support the insight,
it is silently skipped. All output uses plain English suited for a bakery
manager — no analyst jargon.

Public API
----------
generate_insights(df, days_span)        – all applicable insights (priority order)
generate_yesterday_insights(df, ...)    – "Yesterday" dashboard section
generate_period_insights(df, days_span) – "This Period" dashboard section
generate_product_insights(df, days_span)– "What's Selling" dashboard section
"""

import numpy as np
import pandas as pd

from config import (
    INSIGHT_TREND_MIN_DAYS,
    INSIGHT_SLOW_MOVER_MIN_DAYS,
    INSIGHT_SLOW_MOVER_THRESHOLD,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _days_in_df(df):
    """Return the number of unique calendar dates in the dataframe."""
    if df is None or df.empty or "Date" not in df.columns:
        return 0
    return int(df["Date"].dt.date.nunique())


def _safe_pct(part, whole):
    """Return percentage (0-100) or 0.0 when *whole* is zero-ish."""
    if whole is None or whole == 0:
        return 0.0
    return float(part / whole * 100)


# ---------------------------------------------------------------------------
# Private template helpers
# ---------------------------------------------------------------------------

def _add_peak_hour(insights, day_df):
    """Peak trading: {hour}:00 -- busiest hour of the day.

    Guard: day_df must have at least one row with Revenue > 0.
    """
    if day_df is None or day_df.empty or "Hour" not in day_df.columns:
        return
    if "Revenue" not in day_df.columns or day_df["Revenue"].sum() <= 0:
        return

    hourly = day_df.groupby("Hour")["Revenue"].sum()
    if hourly.empty:
        return

    peak_hour = int(hourly.idxmax())
    peak_rev = hourly.max()
    total_rev = day_df["Revenue"].sum()
    peak_pct = _safe_pct(peak_rev, total_rev)

    insights.append(
        f"Peak trading: {peak_hour}:00 with ${peak_rev:,.0f} "
        f"({peak_pct:.0f}% of the day)"
    )


def _add_top_seller(insights, df):
    """'{product}' is your top seller at ${amount}/day, making up {X}% of revenue.

    Guard: df must have Description and Revenue columns with data.
    """
    if df is None or df.empty:
        return
    if "Description" not in df.columns or "Revenue" not in df.columns:
        return
    if df["Revenue"].sum() <= 0:
        return

    n_days = max(_days_in_df(df), 1)
    product_rev = df.groupby("Description")["Revenue"].sum()
    if product_rev.empty:
        return

    top_product = product_rev.idxmax()
    top_rev = product_rev.max()
    daily_avg = top_rev / n_days
    pct_of_total = _safe_pct(top_rev, df["Revenue"].sum())

    insights.append(
        f"'{top_product}' is your top seller at ${daily_avg:,.0f}/day, "
        f"making up {pct_of_total:.0f}% of revenue."
    )


def _add_day_vs_typical(insights, df, latest_date):
    """This {day_name}: ${amount} | Your average {day_name}: ${avg} ({+/-X}%).

    Guard: Need at least 2 instances of the same weekday in df.
    *latest_date* should be a date or Timestamp for the day to compare.
    """
    if df is None or df.empty or latest_date is None:
        return
    if "Date" not in df.columns or "Revenue" not in df.columns or "DayName" not in df.columns:
        return

    latest_ts = pd.Timestamp(latest_date)
    day_name = latest_ts.day_name()

    # Revenue on the specific date
    day_mask = df["Date"].dt.date == latest_ts.date()
    today_rev = df.loc[day_mask, "Revenue"].sum()

    # All instances of this weekday
    same_day = df[df["DayName"] == day_name]
    daily_totals = same_day.groupby(same_day["Date"].dt.date)["Revenue"].sum()
    if len(daily_totals) < 2:
        return

    avg_for_day = daily_totals.mean()
    if avg_for_day <= 0:
        return

    pct_vs_avg = _safe_pct(today_rev - avg_for_day, avg_for_day)
    sign = "+" if pct_vs_avg >= 0 else ""

    insights.append(
        f"This {day_name}: ${today_rev:,.0f} | "
        f"Your average {day_name}: ${avg_for_day:,.0f} ({sign}{pct_vs_avg:.0f}%)."
    )


def _add_best_worst_day(insights, df):
    """{best_day} was your strongest day at ${amount}.

    Guard: Need at least 2 distinct dates.
    """
    if df is None or df.empty:
        return
    if "Date" not in df.columns or "Revenue" not in df.columns:
        return

    daily = df.groupby(df["Date"].dt.date).agg(
        Revenue=("Revenue", "sum"),
    ).reset_index()
    daily.columns = ["Date", "Revenue"]

    if len(daily) < 2:
        return

    best_row = daily.loc[daily["Revenue"].idxmax()]
    best_date = pd.Timestamp(best_row["Date"])
    best_rev = best_row["Revenue"]
    avg_rev = daily["Revenue"].mean()

    if avg_rev <= 0:
        return

    pct_vs_avg = _safe_pct(best_rev - avg_rev, avg_rev)

    insights.append(
        f"{best_date.strftime('%A %d %b')} was your strongest day "
        f"at ${best_rev:,.0f} (+{pct_vs_avg:.0f}% vs average)."
    )


def _add_category_driver(insights, df):
    """Revenue driven by {top_category} ({X}% of total).

    Guard: df must have Category and Revenue with data.
    """
    if df is None or df.empty:
        return
    if "Category" not in df.columns or "Revenue" not in df.columns:
        return

    total = df["Revenue"].sum()
    if total <= 0:
        return

    cat_rev = df.groupby("Category")["Revenue"].sum().sort_values(ascending=False)
    if cat_rev.empty:
        return

    top_cat = cat_rev.index[0]
    top_pct = _safe_pct(cat_rev.iloc[0], total)

    insights.append(
        f"Top category: {top_cat} ({top_pct:.0f}% of revenue)."
    )


def _add_trend(insights, df):
    """Revenue trending {up/down} {X}% over the period.

    Guard: Need INSIGHT_TREND_MIN_DAYS (21) or more days of data.
    Uses weekly aggregation + numpy polyfit (degree 1) to determine trend.
    """
    if df is None or df.empty:
        return
    if "Date" not in df.columns or "Revenue" not in df.columns:
        return

    n_days = _days_in_df(df)
    if n_days < INSIGHT_TREND_MIN_DAYS:
        return

    # Weekly aggregation
    daily = df.groupby(df["Date"].dt.date)["Revenue"].sum().reset_index()
    daily.columns = ["Date", "Revenue"]
    daily["Date"] = pd.to_datetime(daily["Date"])
    daily = daily.sort_values("Date")

    weekly = daily.set_index("Date").resample("W-MON")["Revenue"].sum().reset_index()
    weekly.columns = ["Week", "Revenue"]

    # Drop partial weeks (first and last) if they seem too low
    if len(weekly) < 3:
        return

    # Fit a linear trend
    x = np.arange(len(weekly), dtype=float)
    y = weekly["Revenue"].values.astype(float)

    # Avoid fitting on all-zero data
    if y.sum() <= 0:
        return

    coeffs = np.polyfit(x, y, 1)
    slope = coeffs[0]

    # Percentage change from first fitted value to last fitted value
    first_val = np.polyval(coeffs, x[0])
    last_val = np.polyval(coeffs, x[-1])

    if first_val <= 0:
        return

    pct_change = _safe_pct(last_val - first_val, first_val)
    direction = "up" if pct_change >= 0 else "down"
    abs_pct = abs(pct_change)

    # Only report if the trend is meaningful (> 1%)
    if abs_pct < 1:
        return

    insights.append(
        f"Revenue trending {direction} {abs_pct:.0f}% over the period."
    )


def _add_slow_movers(insights, df, days_span):
    """Slow movers: {products} averaged under ${threshold}/day.

    Guard: Need INSIGHT_SLOW_MOVER_MIN_DAYS (7) or more days.
    Shows up to 5 product names; if there are more, mentions the total count.
    """
    if df is None or df.empty:
        return
    if "Description" not in df.columns or "Revenue" not in df.columns:
        return

    n_days = days_span if days_span and days_span > 0 else _days_in_df(df)
    if n_days < INSIGHT_SLOW_MOVER_MIN_DAYS:
        return

    product_daily = df.groupby("Description")["Revenue"].sum() / n_days
    slow = product_daily[product_daily < INSIGHT_SLOW_MOVER_THRESHOLD].sort_values()

    if slow.empty:
        return

    names = slow.index.tolist()
    count = len(names)
    shown = names[:5]
    label = ", ".join(shown)

    threshold = INSIGHT_SLOW_MOVER_THRESHOLD

    if count > 5:
        label += f" and {count - 5} more"

    insights.append(
        f"Slow movers: {label} averaged under ${threshold}/day."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_insights(df, days_span=None):
    """Return all applicable insights for the given data in priority order.

    Parameters
    ----------
    df : pd.DataFrame
        The (filtered) sales data.
    days_span : int | None
        Number of calendar days in the period. Computed from *df* if not given.

    Returns
    -------
    list[str]
        Plain-English insight strings, ordered by importance.
    """
    if df is None or df.empty:
        return []

    if days_span is None:
        days_span = _days_in_df(df)

    insights = []

    # 1. Trend (most strategic)
    _add_trend(insights, df)

    # 2. Best day
    _add_best_worst_day(insights, df)

    # 3. Top seller
    _add_top_seller(insights, df)

    # 4. Peak hour (use latest day if multi-day, otherwise full df)
    if days_span <= 1:
        _add_peak_hour(insights, df)
    else:
        latest = df["Date"].dt.date.max()
        latest_df = df[df["Date"].dt.date == latest]
        _add_peak_hour(insights, latest_df)

    # 5. Category driver
    _add_category_driver(insights, df)

    # 6. Slow movers
    _add_slow_movers(insights, df, days_span)

    return insights


def generate_yesterday_insights(df, latest_day_df, latest_date):
    """Insights for the 'Yesterday' dashboard section.

    Parameters
    ----------
    df : pd.DataFrame
        Full loaded data (for weekday comparison context).
    latest_day_df : pd.DataFrame
        Data filtered to the latest day only.
    latest_date : date-like
        The date of the latest day.

    Returns
    -------
    list[str]
    """
    if latest_day_df is None or latest_day_df.empty:
        return []

    insights = []

    # Peak hour for the day
    _add_peak_hour(insights, latest_day_df)

    # Compare vs typical same-weekday
    _add_day_vs_typical(insights, df, latest_date)

    # Top seller for the day
    _add_top_seller(insights, latest_day_df)

    return insights


def generate_period_insights(df, days_span):
    """Insights for the 'This Period' dashboard section.

    Parameters
    ----------
    df : pd.DataFrame
        Data for the selected period.
    days_span : int
        Number of calendar days in the period.

    Returns
    -------
    list[str]
    """
    if df is None or df.empty:
        return []

    insights = []

    # Trend (if enough data)
    _add_trend(insights, df)

    # Best day in the period
    _add_best_worst_day(insights, df)

    # Category driver
    _add_category_driver(insights, df)

    return insights


def generate_product_insights(df, days_span):
    """Insights for the 'What's Selling' dashboard section.

    Parameters
    ----------
    df : pd.DataFrame
        Data for the selected period.
    days_span : int
        Number of calendar days in the period.

    Returns
    -------
    list[str]
    """
    if df is None or df.empty:
        return []

    insights = []

    # Top seller
    _add_top_seller(insights, df)

    # Slow movers
    _add_slow_movers(insights, df, days_span)

    return insights
