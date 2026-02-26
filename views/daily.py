"""Daily analysis view (1 day of data)."""

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import CHART_HIGHLIGHT, CHART_PRIMARY


def render(df, min_date, selected_category, full_df=None):
    """Render the daily analysis dashboard."""
    st.caption(f"**Date:** {min_date.strftime('%A, %B %d, %Y')}")

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
            avg_price = total_rev / df["Quantity"].sum() if df["Quantity"].sum() > 0 else 0
            st.metric("Avg Price/Unit", f"${avg_price:.2f}")

    # Smart insights
    from components.insight_card import render_insight

    hourly = df.groupby("Hour").agg({"Revenue": "sum", "Quantity": "sum"}).reset_index()
    hourly = hourly[(hourly["Hour"] >= 8) & (hourly["Hour"] <= 22)]

    if not hourly.empty:
        peak_hour = hourly.loc[hourly["Revenue"].idxmax(), "Hour"]
        peak_rev = hourly["Revenue"].max()
        peak_pct = peak_rev / total_rev * 100 if total_rev > 0 else 0
        render_insight(f"Peak hour: {int(peak_hour)}:00 with ${peak_rev:,.0f} revenue ({peak_pct:.0f}% of daily total)")

    # Day-of-week context
    if full_df is not None:
        day_name = min_date.strftime("%A")
        all_same_day = full_df[full_df["DayName"] == day_name]
        if all_same_day["Date"].dt.date.nunique() > 1:
            avg_for_day = all_same_day.groupby(all_same_day["Date"].dt.date)["Revenue"].sum().mean()
            pct_vs_avg = ((total_rev - avg_for_day) / avg_for_day * 100) if avg_for_day > 0 else 0
            render_insight(
                f"This {day_name}: ${total_rev:,.0f} | Your average {day_name}: ${avg_for_day:,.0f} ({pct_vs_avg:+.0f}%)"
            )

    # Hourly sales pattern
    st.subheader("Hourly Sales Pattern")
    _, toggle_col = st.columns([3, 1])
    with toggle_col:
        metric = st.radio("View:", ["Revenue ($)", "Quantity"], horizontal=True, key="daily_hourly_toggle")

    if metric == "Revenue ($)":
        y, y_title, color = hourly["Revenue"], "Revenue ($)", CHART_HIGHLIGHT
        hover = "Hour: %{x}<br>Revenue: $%{y:,.0f}<extra></extra>"
    else:
        y, y_title, color = hourly["Quantity"], "Quantity", CHART_PRIMARY
        hover = "Hour: %{x}<br>Quantity: %{y:,.0f}<extra></extra>"

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hourly["Hour"], y=y, mode="lines+markers",
        line=dict(color=color, width=3), marker=dict(size=6, color=color),
        fill="tozeroy",
        fillcolor=f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.2)",
        hovertemplate=hover,
    ))
    fig.update_layout(
        height=350, margin=dict(l=0, r=0, t=20, b=40),
        xaxis=dict(title="Hour of Day", tickmode="linear", tick0=8, dtick=2,
                   showgrid=True, gridcolor="rgba(0,0,0,0.05)"),
        yaxis=dict(title=y_title,
                   tickformat=",.0f" if metric == "Quantity" else "$,.0f",
                   showgrid=True, gridcolor="rgba(0,0,0,0.05)"),
        plot_bgcolor="white", showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Two-column charts
    left, right = st.columns(2)

    with left:
        st.subheader("Top Products")
        if selected_category != "All Categories":
            st.caption(f"Top products in: **{selected_category}**")

        top = df.groupby("Description").agg({"Revenue": "sum", "Quantity": "sum"}).sort_values(
            "Revenue", ascending=True
        ).tail(7)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=top.index, x=top["Revenue"], orientation="h", marker_color=CHART_PRIMARY,
            text=[f"${r:,.0f}" for r in top["Revenue"]], textposition="outside",
            textfont=dict(size=11, color="#5A6B5E"),
            hovertemplate="<b>%{y}</b><br>$%{x:,.0f} - %{customdata} units<extra></extra>",
            customdata=top["Quantity"].astype(int),
        ))
        fig.update_layout(
            showlegend=False, height=400, margin=dict(l=0, r=80, t=40, b=0),
            xaxis=dict(title="Revenue ($)", tickformat="$,.0f"), yaxis=dict(title=""),
        )
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("Category Mix")
        _render_category_pie(df, selected_category)

    # Copy summary for sharing
    top_product_data = df.groupby("Description")["Revenue"].sum().sort_values(ascending=False)
    top_product = top_product_data.index[0] if len(top_product_data) > 0 else "N/A"
    top_rev = top_product_data.iloc[0] if len(top_product_data) > 0 else 0
    day_name = min_date.strftime("%A")
    summary_text = (
        f"TMB Harris Farm | {min_date.strftime('%b %d, %Y')} ({day_name})\n"
        f"Revenue: ${total_rev:,.0f} | Transactions: {num_baskets} | "
        f"Avg Basket: ${avg_basket:.2f}\n"
        f"Top: {top_product} (${top_rev:,.0f})"
    )
    st.code(summary_text, language=None)
    st.caption("Copy the above to share via WhatsApp, Slack, or email")


def _render_category_pie(df, selected_category):
    """Render the pie/donut chart for category or product mix."""
    if selected_category != "All Categories":
        st.caption(f"Product mix within: **{selected_category}**")
        data = df.groupby("Description")["Revenue"].sum().sort_values(ascending=False)
        top = data.nlargest(6)
        other = data[~data.index.isin(top.index)].sum()
        if other > 0:
            import pandas as pd
            plot_data = pd.concat([top, pd.Series({"Others": other})])
        else:
            plot_data = top
    else:
        plot_data = df.groupby("Category")["Revenue"].sum().sort_values(ascending=False)

    fig = go.Figure(data=[go.Pie(
        labels=plot_data.index, values=plot_data.values, hole=0.5,
        marker=dict(colors=px.colors.qualitative.Pastel),
        texttemplate="%{percent}", textposition="inside",
        textfont=dict(size=11, color="white"),
        hovertemplate="<b>%{label}</b><br>$%{value:,.0f} - %{percent}<extra></extra>",
    )])
    fig.update_layout(
        height=450, margin=dict(l=20, r=20, t=20, b=20), showlegend=True,
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.05, font=dict(size=10)),
    )
    st.plotly_chart(fig, use_container_width=True)
