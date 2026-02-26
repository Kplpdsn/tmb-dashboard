# DEPRECATED: This view has been merged into views/dashboard.py.
# Kept for reference — will be removed in a future cleanup.
"""Weekly analysis view (2-14 days of data)."""

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import CHART_HIGHLIGHT, CHART_PRIMARY


def render(df, min_date, max_date, selected_category):
    """Render the weekly analysis dashboard."""
    st.caption(f"**Period:** {min_date.strftime('%A, %B %d, %Y')} to {max_date.strftime('%A, %B %d, %Y')}")

    # Primary metrics (3 only)
    c1, c2, c3 = st.columns(3)
    num_baskets = df["Basket_ID"].nunique()
    total_rev = df["Revenue"].sum()
    avg_basket = total_rev / num_baskets if num_baskets > 0 else 0

    with c1:
        st.metric("Revenue", f"${total_rev:,.2f}")
    with c2:
        st.metric("Transactions", f"{num_baskets:,}")
    with c3:
        st.metric("Avg Basket", f"${avg_basket:.2f}")

    # Secondary metrics in expander
    with st.expander("More Details"):
        d1, d2, d3 = st.columns(3)
        with d1:
            st.metric("Units Sold", f"{int(df['Quantity'].sum()):,}")
        with d2:
            avg_items = df["Quantity"].sum() / num_baskets if num_baskets > 0 else 0
            st.metric("Avg Items/Trans", f"{avg_items:.1f}")
        with d3:
            avg_daily = df.groupby("Date")["Revenue"].sum().mean()
            st.metric("Avg Daily Rev", f"${avg_daily:,.2f}")

    # Day-by-day breakdown
    hdr, toggle = st.columns([3, 1])
    with hdr:
        st.subheader("Day-by-Day Breakdown")
    with toggle:
        metric = st.radio("View:", ["Revenue ($)", "Quantity"], horizontal=True, key="weekly_daily_toggle")

    daily = df.groupby("Date").agg({"Revenue": "sum", "Quantity": "sum"}).reset_index()
    daily["DayName"] = daily["Date"].dt.day_name()
    daily["DateLabel"] = daily["Date"].dt.strftime("%b %d") + " (" + daily["DayName"] + ")"

    if metric == "Revenue ($)":
        y, y_title, color, fmt = daily["Revenue"], "Revenue ($)", CHART_HIGHLIGHT, "$,.0f"
        hover = "<b>%{x}</b><br>Revenue: $%{y:,.2f}<extra></extra>"
    else:
        y, y_title, color, fmt = daily["Quantity"], "Quantity", CHART_PRIMARY, ",.0f"
        hover = "<b>%{x}</b><br>Quantity: %{y:,.0f}<extra></extra>"

    fig = go.Figure()
    fig.add_trace(go.Bar(x=daily["DateLabel"], y=y, marker_color=color, hovertemplate=hover))
    fig.update_layout(
        height=400, margin=dict(l=0, r=0, t=20, b=0),
        xaxis_title="Date", yaxis_title=y_title, yaxis=dict(tickformat=fmt),
        xaxis=dict(tickangle=-45), showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Best/worst day insight
    from components.insight_card import render_insight

    if len(daily) > 1:
        best_day = daily.loc[daily["Revenue"].idxmax()]
        worst_day = daily.loc[daily["Revenue"].idxmin()]
        render_insight(
            f"Best day: {best_day['DayName']} {best_day['Date'].strftime('%b %d')} "
            f"(${best_day['Revenue']:,.0f}) | "
            f"Slowest: {worst_day['DayName']} {worst_day['Date'].strftime('%b %d')} "
            f"(${worst_day['Revenue']:,.0f})"
        )

    # Two-column section
    left, right = st.columns(2)

    with left:
        st.subheader("Top Performers")
        top = df.groupby("Description").agg({"Revenue": "sum", "Quantity": "sum"}).sort_values(
            "Revenue", ascending=False
        ).head(5)

        rank_badges = {1: "1", 2: "2", 3: "3"}
        labels = []
        for i, (prod, row) in enumerate(top.iterrows(), 1):
            badge = rank_badges.get(i, f"#{i}")
            short = prod if len(prod) <= 25 else prod[:22] + "..."
            labels.append(f"{badge} {short}")

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=labels, y=top["Revenue"], marker_color=CHART_PRIMARY,
            text=[f"${r:,.0f}" for r in top["Revenue"]], textposition="outside",
            textfont=dict(size=10, color="#5A6B5E"),
            hovertemplate="<b>%{x}</b><br>$%{y:,.0f} - %{customdata} units<extra></extra>",
            customdata=top["Quantity"].astype(int),
        ))
        fig.update_layout(
            showlegend=False, height=400, margin=dict(l=0, r=0, t=50, b=100),
            xaxis=dict(tickangle=-45, title="", tickfont=dict(size=9)),
            yaxis=dict(tickformat="$,.0f", title="Revenue"),
        )
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("Category Performance")
        _render_category_chart(df, selected_category)


def _render_category_chart(df, selected_category):
    """Category donut chart or product breakdown."""
    if selected_category == "All Categories":
        data = df.groupby("Category")["Revenue"].sum().sort_values(ascending=False)
    else:
        data = df.groupby("Description")["Revenue"].sum().sort_values(ascending=False)
        top6 = data.nlargest(6)
        other = data[~data.index.isin(top6.index)].sum()
        if other > 0:
            import pandas as pd
            data = pd.concat([top6, pd.Series({"Others": other})])
        else:
            data = top6

    fig = go.Figure(data=[go.Pie(
        labels=data.index, values=data.values, hole=0.5,
        marker=dict(colors=px.colors.qualitative.Pastel if selected_category == "All Categories"
                    else px.colors.qualitative.Set2),
        texttemplate="%{percent}", textposition="inside",
        textfont=dict(size=12, color="white"),
        hovertemplate="<b>%{label}</b><br>$%{value:,.0f} - %{percent}<extra></extra>",
    )])
    fig.update_layout(
        height=450, margin=dict(l=20, r=20, t=20, b=20), showlegend=True,
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.05, font=dict(size=10)),
        annotations=[dict(text=f"${data.sum():,.0f}<br>Total", x=0.5, y=0.5, font_size=18, showarrow=False)],
    )
    st.plotly_chart(fig, use_container_width=True)
