"""Shared metric card component for the bakery dashboard.

Renders revenue, transaction, and basket metrics in a consistent layout.
Used by the dashboard view and tool views (average_day, baskets).
"""

import streamlit as st


def render_primary_metrics(df, delta_label=None, delta_values=None):
    """Render 3 primary metric cards: Revenue, Transactions, Avg Basket Value.

    Args:
        df: DataFrame with columns Revenue, Quantity, Date, Basket_ID.
        delta_label: Optional tooltip string (e.g. "vs typical Monday").
        delta_values: Optional dict with keys 'revenue', 'transactions',
            'basket' — each a string like "+12%" passed to st.metric delta.

    Returns:
        Tuple of (total_rev, num_baskets, avg_basket).
    """
    num_baskets = df["Basket_ID"].nunique()
    total_rev = df["Revenue"].sum()
    avg_basket = total_rev / num_baskets if num_baskets > 0 else 0

    deltas = delta_values or {}

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric(
            "Revenue",
            f"${total_rev:,.2f}",
            delta=deltas.get("revenue"),
            help=delta_label,
        )
    with c2:
        st.metric(
            "Transactions",
            f"{num_baskets:,}",
            delta=deltas.get("transactions"),
            help=delta_label,
        )
    with c3:
        st.metric(
            "Avg Basket",
            f"${avg_basket:.2f}",
            delta=deltas.get("basket"),
            help=delta_label,
        )

    return total_rev, num_baskets, avg_basket


def render_period_metrics(df):
    """Render 3 period-level metric cards: Total Revenue, Daily Average, Best Day.

    Designed for multi-day views where period context matters.

    Args:
        df: DataFrame with columns Revenue, Date.

    Returns:
        Tuple of (total_rev, daily_avg, best_rev).
    """
    total_rev = df["Revenue"].sum()

    daily_rev = df.groupby("Date")["Revenue"].sum()
    daily_avg = daily_rev.mean() if len(daily_rev) > 0 else 0

    if len(daily_rev) > 0:
        best_date = daily_rev.idxmax()
        best_rev = daily_rev.max()
        best_label = best_date.strftime("%a %b %d")
    else:
        best_rev = 0
        best_label = None

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total Revenue", f"${total_rev:,.2f}")
    with c2:
        st.metric("Daily Average", f"${daily_avg:,.2f}")
    with c3:
        st.metric("Best Day", f"${best_rev:,.2f}", delta=best_label)

    return total_rev, daily_avg, best_rev


def render_secondary_metrics(df):
    """Render a 'More Details' expander with Units Sold, Avg Items/Trans, and a third metric.

    The third metric adapts to the data span:
    - Single day: Avg Price/Unit
    - Multi-day: Avg Daily Rev

    Args:
        df: DataFrame with columns Revenue, Quantity, Date, Basket_ID.
    """
    num_baskets = df["Basket_ID"].nunique()
    total_qty = df["Quantity"].sum()
    total_rev = df["Revenue"].sum()
    num_days = df["Date"].dt.date.nunique()
    is_single_day = num_days <= 1

    with st.expander("More Details"):
        d1, d2, d3 = st.columns(3)
        with d1:
            st.metric("Units Sold", f"{int(total_qty):,}")
        with d2:
            avg_items = total_qty / num_baskets if num_baskets > 0 else 0
            st.metric("Avg Items/Trans", f"{avg_items:.1f}")
        with d3:
            if is_single_day:
                avg_price = total_rev / total_qty if total_qty > 0 else 0
                st.metric("Avg Price/Unit", f"${avg_price:.2f}")
            else:
                avg_daily = df.groupby("Date")["Revenue"].sum().mean()
                st.metric("Avg Daily Rev", f"${avg_daily:,.2f}")
