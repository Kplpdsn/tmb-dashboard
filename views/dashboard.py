"""Unified dashboard view — replaces daily/weekly/monthly with a single page.

Three sections:
    A. "Yesterday" — latest day in loaded data with weekday comparison deltas
    B. "This Period" — full loaded range overview (hidden if single day)
    C. "What's Selling" — top products, category mix, slow mover callout

Below the fold: navigation buttons for Average Day and Basket tools.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.insight_card import render_insight
from components.metrics import (
    render_primary_metrics,
    render_period_metrics,
    render_secondary_metrics,
)
from config import (
    CHART_HIGHLIGHT,
    CHART_PRIMARY,
    INSIGHT_TOP_PRODUCTS,
    INSIGHT_WEEKLY_AGGREGATE_DAYS,
    PIE_COLORS,
)
from services.insights import (
    generate_yesterday_insights,
    generate_period_insights,
    generate_product_insights,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render(df, selected_category, selected_product):
    """Render the unified dashboard."""
    if df is None or df.empty:
        st.info("No data to display. Select a date range first.")
        return

    min_date = df["Date"].min()
    max_date = df["Date"].max()
    days_span = (max_date - min_date).days + 1
    latest_date = max_date
    latest_day_name = latest_date.day_name()

    # Isolate latest-day data
    latest_day_df = df[df["Date"].dt.date == latest_date.date()]

    # -- Section A: Yesterday's Numbers ------------------------------------
    _render_yesterday_section(df, latest_day_df, latest_date, latest_day_name)

    st.markdown("---")

    # -- Section B: This Period (only if more than one day) -----------------
    if days_span > 1:
        _render_period_section(df, min_date, max_date, days_span)
        st.markdown("---")

    # -- Section C: What's Selling -----------------------------------------
    _render_whats_selling_section(df, days_span, selected_category)

    st.markdown("---")

    # -- Below the fold: More Tools ----------------------------------------
    _render_tools_nav()


# ---------------------------------------------------------------------------
# Section A — "Yesterday"
# ---------------------------------------------------------------------------

def _compute_weekday_deltas(df, latest_day_df, latest_date):
    """Compute delta strings for revenue, transactions, basket vs typical weekday.

    Excludes the latest day itself from the weekday average so the comparison
    is fair (you're comparing *today* against the *other* same-weekdays).

    Returns (delta_label, delta_values dict) or (None, None) when there aren't
    enough same-weekday instances.
    """
    day_name = latest_date.day_name()

    # All rows for the same weekday, excluding the latest day
    same_day = df[(df["DayName"] == day_name) & (df["Date"].dt.date != latest_date.date())]
    same_day_dates = same_day["Date"].dt.date.nunique()

    if same_day_dates < 1:
        return None, None

    # Per-day aggregates for the typical weekday
    per_day = same_day.groupby(same_day["Date"].dt.date).agg(
        Revenue=("Revenue", "sum"),
        Baskets=("Basket_ID", "nunique"),
    )
    avg_rev = per_day["Revenue"].mean()
    avg_baskets = per_day["Baskets"].mean()
    avg_basket_val = avg_rev / avg_baskets if avg_baskets > 0 else 0

    # Latest day actuals
    today_rev = latest_day_df["Revenue"].sum()
    today_baskets = latest_day_df["Basket_ID"].nunique()
    today_basket_val = today_rev / today_baskets if today_baskets > 0 else 0

    def _delta_str(actual, typical):
        if typical == 0:
            return None
        pct = (actual - typical) / typical * 100
        return f"{pct:+.0f}%"

    delta_label = f"vs typical {day_name}"
    delta_values = {
        "revenue": _delta_str(today_rev, avg_rev),
        "transactions": _delta_str(today_baskets, avg_baskets),
        "basket": _delta_str(today_basket_val, avg_basket_val),
    }

    return delta_label, delta_values


def _render_yesterday_section(df, latest_day_df, latest_date, day_name):
    """Section A — latest day metrics + insights."""
    st.markdown(f"### {day_name}'s Numbers")
    st.caption(latest_date.strftime("%A %d %B %Y"))

    delta_label, delta_values = _compute_weekday_deltas(df, latest_day_df, latest_date)

    render_primary_metrics(latest_day_df, delta_label=delta_label, delta_values=delta_values)

    # Insight cards
    insights = generate_yesterday_insights(df, latest_day_df, latest_date)
    for text in insights[:2]:
        render_insight(text)


# ---------------------------------------------------------------------------
# Section B — "This Period"
# ---------------------------------------------------------------------------

def _render_period_section(df, min_date, max_date, days_span):
    """Section B — period overview with metrics, chart, and insights."""
    st.markdown("### This Period")
    st.caption(
        f"{min_date.strftime('%d %b %Y')} \u2013 {max_date.strftime('%d %b %Y')}  "
        f"({days_span} day{'s' if days_span != 1 else ''})"
    )

    render_period_metrics(df)

    # Revenue chart — daily bars or weekly aggregated bars
    if days_span < INSIGHT_WEEKLY_AGGREGATE_DAYS:
        _render_daily_bars(df)
    else:
        _render_weekly_bars(df)

    # Insight cards
    insights = generate_period_insights(df, days_span)
    for text in insights[:2]:
        render_insight(text)


def _render_daily_bars(df):
    """Bar chart with one bar per calendar day."""
    daily = df.groupby("Date").agg(Revenue=("Revenue", "sum")).reset_index()
    daily = daily.sort_values("Date")
    daily["DayName"] = daily["Date"].dt.day_name()
    daily["Label"] = (
        daily["Date"].dt.strftime("%d %b")
        + " ("
        + daily["DayName"].str[:3]
        + ")"
    )

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=daily["Label"],
        y=daily["Revenue"],
        marker_color=CHART_HIGHLIGHT,
        hovertemplate="<b>%{x}</b><br>Revenue: $%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        height=380,
        margin=dict(l=0, r=0, t=20, b=40),
        xaxis=dict(title="", tickangle=-45, showgrid=False),
        yaxis=dict(title="Revenue ($)", tickformat="$,.0f"),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_weekly_bars(df):
    """Bar chart with Monday-based weekly aggregated bars (for 15+ day ranges)."""
    tmp = df.copy()
    # Group by ISO week (Monday start)
    tmp["WeekStart"] = tmp["Date"].dt.normalize() - pd.to_timedelta(tmp["Date"].dt.weekday, unit="D")

    weekly = tmp.groupby("WeekStart").agg(
        Revenue=("Revenue", "sum"),
        StartDate=("Date", "min"),
        EndDate=("Date", "max"),
    ).reset_index().sort_values("WeekStart")

    # Build readable labels like "3-9 Feb" or "28 Jan-3 Feb"
    labels = []
    for _, row in weekly.iterrows():
        s = row["StartDate"]
        e = row["EndDate"]
        s_month = s.strftime("%b")
        e_month = e.strftime("%b")
        if s_month != e_month:
            labels.append(f"{s.day} {s_month}-{e.day} {e_month}")
        else:
            labels.append(f"{s.day}-{e.day} {s_month}")
    weekly["WeekLabel"] = labels

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=weekly["WeekLabel"],
        y=weekly["Revenue"],
        marker_color=CHART_HIGHLIGHT,
        text=[f"${v:,.0f}" for v in weekly["Revenue"]],
        textposition="outside",
        textfont=dict(size=10),
        hovertemplate="<b>%{x}</b><br>Revenue: $%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        height=380,
        margin=dict(l=0, r=0, t=20, b=40),
        xaxis=dict(title="Week", showgrid=False),
        yaxis=dict(title="Revenue ($)", tickformat="$,.0f"),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Section C — "What's Selling"
# ---------------------------------------------------------------------------

def _render_whats_selling_section(df, days_span, selected_category):
    """Section C — top products, category mix, slow movers, secondary metrics."""
    st.markdown("### What's Selling")

    left, right = st.columns(2)

    with left:
        _render_top_products(df)

    with right:
        _render_category_or_product_mix(df, selected_category)

    # Insight cards (slow movers, top seller)
    insights = generate_product_insights(df, days_span)
    for text in insights[:2]:
        render_insight(text)

    # Secondary metrics expander
    render_secondary_metrics(df)


def _render_top_products(df):
    """Horizontal bar chart of top N products by revenue."""
    n = INSIGHT_TOP_PRODUCTS

    top = (
        df.groupby("Description")
        .agg(Revenue=("Revenue", "sum"), Quantity=("Quantity", "sum"))
        .sort_values("Revenue", ascending=True)
        .tail(n)
    )

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=top.index,
        x=top["Revenue"],
        orientation="h",
        marker_color=CHART_PRIMARY,
        text=[f"${r:,.0f}" for r in top["Revenue"]],
        textposition="outside",
        textfont=dict(size=11, color="#5E6556"),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "$%{x:,.0f} \u2014 %{customdata} units<extra></extra>"
        ),
        customdata=top["Quantity"].astype(int),
    ))
    fig.update_layout(
        showlegend=False,
        height=400,
        margin=dict(l=0, r=80, t=20, b=0),
        xaxis=dict(title="Revenue ($)", tickformat="$,.0f"),
        yaxis=dict(title="", tickfont=dict(size=10)),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_category_or_product_mix(df, selected_category):
    """Donut chart — category mix or product breakdown when a single category is filtered."""
    if selected_category != "All Categories":
        # Single category filtered — show product breakdown instead
        st.caption(f"Product mix within **{selected_category}**")
        data = df.groupby("Description")["Revenue"].sum().sort_values(ascending=False)
        top6 = data.nlargest(6)
        other = data[~data.index.isin(top6.index)].sum()
        if other > 0:
            plot_data = pd.concat([top6, pd.Series({"Others": other})])
        else:
            plot_data = top6
    else:
        plot_data = df.groupby("Category")["Revenue"].sum().sort_values(ascending=False)
    palette = PIE_COLORS

    fig = go.Figure(data=[go.Pie(
        labels=plot_data.index,
        values=plot_data.values,
        hole=0.5,
        marker=dict(colors=palette),
        texttemplate="%{percent}",
        textposition="inside",
        textfont=dict(size=11, color="white"),
        hovertemplate="<b>%{label}</b><br>$%{value:,.0f} \u2014 %{percent}<extra></extra>",
    )])
    fig.update_layout(
        height=400,
        margin=dict(l=20, r=20, t=20, b=20),
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.05,
            font=dict(size=10),
        ),
        annotations=[dict(
            text=f"${plot_data.sum():,.0f}<br>Total",
            x=0.5, y=0.5,
            font_size=16,
            showarrow=False,
        )],
    )
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Below the fold — "More Tools"
# ---------------------------------------------------------------------------

def _render_tools_nav():
    """Navigation buttons for Average Day and Basket tools."""
    st.markdown("### More Tools")

    c1, c2 = st.columns(2)

    with c1:
        if st.button("Model a Typical Day", use_container_width=True):
            st.session_state.active_tool = "Typical Day"
            st.rerun()

    with c2:
        if st.button("Basket Patterns", use_container_width=True):
            st.session_state.active_tool = "Baskets"
            st.rerun()
