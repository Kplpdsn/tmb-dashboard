"""Monthly analysis view (15+ days of data)."""

import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import CHART_HIGHLIGHT, CHART_PRIMARY


def render(df, min_date, max_date, selected_category, selected_product):
    """Render the monthly analysis dashboard."""
    st.caption(f"**Period:** {min_date.strftime('%B %d, %Y')} to {max_date.strftime('%B %d, %Y')}")
    days_span = (max_date - min_date).days + 1

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
            st.metric("Avg Daily Rev", f"${avg_daily:,.0f}")

    # Weekly performance bar chart
    hdr, toggle = st.columns([3, 1])
    with hdr:
        st.subheader("Weekly Performance")
        if selected_product != "All Products":
            st.caption(f"Showing trend for: **{selected_product}**")
        elif selected_category != "All Categories":
            st.caption(f"Showing trend for category: **{selected_category}**")
    with toggle:
        metric = st.radio("View:", ["Revenue ($)", "Quantity"], horizontal=True, key="monthly_weekly_toggle")

    weekly = _compute_weekly(df)

    if metric == "Revenue ($)":
        y, y_title, color, fmt = weekly["Revenue"], "Revenue ($)", CHART_HIGHLIGHT, "$,.0f"
        hover = "<b>%{x}</b><br>Revenue: $%{y:,.0f}<extra></extra>"
    else:
        y, y_title, color, fmt = weekly["Quantity"], "Quantity", CHART_PRIMARY, ",.0f"
        hover = "<b>%{x}</b><br>Quantity: %{y:,.0f}<extra></extra>"

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=weekly["WeekLabel"], y=y, marker_color=color,
        text=[f"{v:,.0f}" for v in y], textposition="outside", textfont=dict(size=10),
        hovertemplate=hover,
    ))
    fig.update_layout(
        height=400, margin=dict(l=0, r=0, t=20, b=40),
        xaxis=dict(title="Week", showgrid=False),
        yaxis=dict(title=y_title, tickformat=fmt, showgrid=True, gridcolor="rgba(0,0,0,0.05)"),
        plot_bgcolor="white", showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Two-column section
    left, right = st.columns(2)

    with left:
        st.subheader("Top 10 Products")
        if selected_category != "All Categories":
            st.caption(f"Top products in: **{selected_category}**")

        top = df.groupby("Description")["Revenue"].sum().sort_values(ascending=True).tail(10)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=top.index, x=top.values, orientation="h", marker_color=CHART_PRIMARY,
            text=[f"${r:,.0f}" for r in top.values], textposition="outside", textfont=dict(size=10),
            hovertemplate="<b>%{y}</b><br>Revenue: $%{x:,.2f}<extra></extra>",
        ))
        fig.update_layout(
            showlegend=False, height=450, margin=dict(l=0, r=60, t=20, b=40),
            xaxis=dict(title="Revenue ($)", tickformat="$,.0f"),
            yaxis=dict(title="", tickfont=dict(size=9)),
        )
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("Performance Summary")
        if selected_category == "All Categories":
            cat = df.groupby("Category").agg({"Revenue": "sum", "Quantity": "sum"}).sort_values(
                "Revenue", ascending=False
            )
            cat["% of Total"] = (cat["Revenue"] / cat["Revenue"].sum() * 100).round(1)
            st.dataframe(
                cat.style.format({"Revenue": "${:,.2f}", "Quantity": "{:,.0f}", "% of Total": "{:.1f}%"}),
                use_container_width=True,
            )
        else:
            prod = df.groupby("Description").agg({"Revenue": "sum", "Quantity": "sum"}).sort_values(
                "Revenue", ascending=False
            )
            prod["Avg Price"] = (prod["Revenue"] / prod["Quantity"]).round(2)
            st.dataframe(
                prod.style.format({"Revenue": "${:,.2f}", "Quantity": "{:,.0f}", "Avg Price": "${:.2f}"}),
                use_container_width=True, height=400,
            )

    # Slow sellers section
    from components.insight_card import render_insight

    all_products = df.groupby("Description")["Revenue"].sum().sort_values()
    if len(all_products) > 5:
        bottom5 = all_products.head(5)
        slow_list = ", ".join(f"{p} (${r:,.0f})" for p, r in bottom5.items())
        render_insight(f"Slowest sellers: {slow_list}")

    # Trend analysis (21+ days)
    if days_span > 21:
        _render_trend_analysis(df, min_date, max_date)


def _render_trend_analysis(df, min_date, max_date):
    """Render trend analysis section for longer date ranges."""
    st.markdown("---")
    st.subheader("Trend Analysis")

    # Weekly revenue with trendline
    tmp = df.copy()
    start = tmp["Date"].min()
    tmp["WeekNum"] = ((tmp["Date"] - start).dt.days // 7) + 1
    weekly_trend = tmp.groupby("WeekNum").agg(
        Revenue=("Revenue", "sum"),
        StartDate=("Date", "min"),
    ).reset_index()
    weekly_trend["WeekLabel"] = weekly_trend["StartDate"].dt.strftime("%b %d")

    if len(weekly_trend) >= 3:
        x_num = np.arange(len(weekly_trend))
        slope, intercept = np.polyfit(x_num, weekly_trend["Revenue"].values, 1)
        trend_line = slope * x_num + intercept
        pct_change = (slope * len(weekly_trend)) / weekly_trend["Revenue"].mean() * 100 if weekly_trend["Revenue"].mean() > 0 else 0
        trend_dir = "up" if slope > 0 else "down"

        st.caption(f"Weekly revenue trend: **{trend_dir}** ({abs(pct_change):,.1f}% over the period)")

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=weekly_trend["WeekLabel"], y=weekly_trend["Revenue"],
            marker_color=CHART_PRIMARY, opacity=0.7, name="Weekly Revenue",
            hovertemplate="Week of %{x}<br>Revenue: $%{y:,.0f}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=weekly_trend["WeekLabel"], y=trend_line,
            mode="lines", name="Trend",
            line=dict(color="#D97706", width=2.5, dash="dash"),
        ))
        fig.update_layout(
            height=350, margin=dict(l=0, r=0, t=20, b=40),
            xaxis=dict(title="Week", tickangle=-45, showgrid=False),
            yaxis=dict(title="Revenue ($)", tickformat="$,.0f",
                       showgrid=True, gridcolor="rgba(0,0,0,0.05)"),
            plot_bgcolor="white", showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        )
        st.plotly_chart(fig, use_container_width=True)

    # Top/Bottom movers
    st.subheader("Product Movers")

    midpoint = min_date + (max_date - min_date) / 2
    early = df[df["Date"] < midpoint]
    late = df[df["Date"] >= midpoint]

    early_days = early["Date"].dt.date.nunique() or 1
    late_days = late["Date"].dt.date.nunique() or 1

    early_avg = early.groupby("Description")["Revenue"].sum() / early_days
    late_avg = late.groupby("Description")["Revenue"].sum() / late_days

    # Only compare products that exist in both periods
    common = set(early_avg.index) & set(late_avg.index)
    if len(common) >= 5:
        change = (late_avg.loc[list(common)] - early_avg.loc[list(common)]).sort_values()

        gainer_col, decliner_col = st.columns(2)

        with gainer_col:
            st.markdown("**Top 5 Gainers**")
            gainers = change.tail(5).sort_values(ascending=False)
            for product, delta in gainers.items():
                pct = (delta / early_avg.get(product, 1)) * 100
                st.markdown(
                    f"<span style='color:{CHART_HIGHLIGHT}; font-weight:600;'>+${delta:,.2f}/day</span> "
                    f"({pct:+,.0f}%) - {product}",
                    unsafe_allow_html=True,
                )

        with decliner_col:
            st.markdown("**Top 5 Decliners**")
            decliners = change.head(5)
            for product, delta in decliners.items():
                pct = (delta / early_avg.get(product, 1)) * 100
                st.markdown(
                    f"<span style='color:#DC2626; font-weight:600;'>${delta:,.2f}/day</span> "
                    f"({pct:+,.0f}%) - {product}",
                    unsafe_allow_html=True,
                )
    else:
        st.info("Not enough products in common across periods for mover analysis.")


def _compute_weekly(df):
    """Compute weekly aggregates with readable labels."""
    tmp = df.copy()
    start = tmp["Date"].min()
    tmp["DaysSinceStart"] = (tmp["Date"] - start).dt.days
    tmp["WeekNum"] = (tmp["DaysSinceStart"] // 7) + 1

    weekly = tmp.groupby("WeekNum").agg({
        "Revenue": "sum", "Quantity": "sum", "Date": ["min", "max"]
    }).reset_index()

    labels = []
    for _, row in weekly.iterrows():
        s = row[("Date", "min")]
        e = row[("Date", "max")]
        sm, em = s.strftime("%b"), e.strftime("%b")
        if sm != em:
            labels.append(f"{sm} {s.day}-{em} {e.day}")
        else:
            labels.append(f"{sm} {s.day}-{e.day}")

    result = weekly["WeekNum"].to_frame()
    result["Revenue"] = weekly[("Revenue", "sum")]
    result["Quantity"] = weekly[("Quantity", "sum")]
    result["WeekLabel"] = labels
    return result
