"""Average Day analysis view - model a typical day from historical data."""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import (
    CHART_PRIMARY, CHART_POSITIVE, CHART_CONFIDENCE_BAND,
    AVERAGE_DAY_ROLLING_WINDOW, DAY_NAMES_ORDERED, MONTH_NAMES,
)


def render(df, selected_day_name, selected_category="All Categories", selected_months=None):
    """Render the Average Day analysis dashboard.

    Args:
        df: Full loaded DataFrame (all data in the selected date range).
        selected_day_name: e.g. "Monday".
        selected_category: Category filter already applied or "All Categories".
        selected_months: List of month numbers (1-12) to filter, or None for all.
    """
    # Filter to the selected day of week
    day_df = df[df["DayName"] == selected_day_name].copy()

    # Apply month filter if specified
    if selected_months:
        day_df = day_df[day_df["Date"].dt.month.isin(selected_months)]

    if day_df.empty:
        st.warning(f"No {selected_day_name} data found in the loaded date range.")
        return

    # Per-day aggregates (one row per instance of this day)
    daily_totals = day_df.groupby(day_df["Date"].dt.date).agg(
        Revenue=("Revenue", "sum"),
        Quantity=("Quantity", "sum"),
        Baskets=("Basket_ID", "nunique"),
    ).reset_index()
    daily_totals["AvgBasketValue"] = daily_totals["Revenue"] / daily_totals["Baskets"].replace(0, np.nan)
    daily_totals["Date"] = pd.to_datetime(daily_totals["Date"])

    num_instances = len(daily_totals)
    first_date = daily_totals["Date"].min()
    last_date = daily_totals["Date"].max()

    # ---------------------------------------------------------------
    # 1. Sample size banner
    # ---------------------------------------------------------------
    month_note = ""
    if selected_months:
        month_names = [MONTH_NAMES[m - 1] for m in sorted(selected_months)]
        month_note = f" | Months: {', '.join(month_names)}"

    st.markdown(
        f"<div style='background:#F0F4EF; border-left:4px solid {CHART_PRIMARY}; "
        f"padding:12px 18px; border-radius:0 8px 8px 0; margin-bottom:16px;'>"
        f"<strong>{num_instances} {selected_day_name}{'s' if num_instances != 1 else ''}</strong> analyzed "
        f"({first_date.strftime('%b %d, %Y')} to {last_date.strftime('%b %d, %Y')}){month_note}"
        f"</div>",
        unsafe_allow_html=True,
    )
    if num_instances < 4:
        st.warning("Few data points available. Load a wider date range for more accurate averages.")

    # ---------------------------------------------------------------
    # 2. Key metrics with variability
    # ---------------------------------------------------------------
    avg_rev = daily_totals["Revenue"].mean()
    std_rev = daily_totals["Revenue"].std()
    avg_units = daily_totals["Quantity"].mean()
    std_units = daily_totals["Quantity"].std()
    avg_trans = daily_totals["Baskets"].mean()
    std_trans = daily_totals["Baskets"].std()
    avg_basket = daily_totals["AvgBasketValue"].mean()
    std_basket = daily_totals["AvgBasketValue"].std()

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Avg Revenue", f"${avg_rev:,.2f}")
        if num_instances > 1:
            st.caption(f"Range: ${daily_totals['Revenue'].min():,.0f} - ${daily_totals['Revenue'].max():,.0f}")
    with c2:
        st.metric("Avg Transactions", f"{avg_trans:,.0f}")
        if num_instances > 1:
            st.caption(f"Range: {daily_totals['Baskets'].min():,.0f} - {daily_totals['Baskets'].max():,.0f}")
    with c3:
        st.metric("Avg Basket Value", f"${avg_basket:,.2f}")
        if num_instances > 1:
            st.caption(f"Range: ${daily_totals['AvgBasketValue'].min():,.2f} - ${daily_totals['AvgBasketValue'].max():,.2f}")

    with st.expander("More Details"):
        d1, d2, d3 = st.columns(3)
        with d1:
            st.metric("Avg Units", f"{avg_units:,.0f}")
        with d2:
            avg_items = avg_units / avg_trans if avg_trans > 0 else 0
            st.metric("Avg Items/Trans", f"{avg_items:.1f}")
        with d3:
            avg_price = avg_rev / avg_units if avg_units > 0 else 0
            st.metric("Avg Price/Unit", f"${avg_price:.2f}")

    # ---------------------------------------------------------------
    # 3. Average hourly pattern with confidence band
    # ---------------------------------------------------------------
    st.subheader("Average Hourly Pattern")

    hourly_by_date = day_df.groupby([day_df["Date"].dt.date, "Hour"])["Revenue"].sum().reset_index()
    hourly_stats = hourly_by_date.groupby("Hour")["Revenue"].agg(["mean", "std"]).reset_index()
    hourly_stats["std"] = hourly_stats["std"].fillna(0)
    hourly_stats = hourly_stats[(hourly_stats["Hour"] >= 6) & (hourly_stats["Hour"] <= 22)]
    hourly_stats["upper"] = hourly_stats["mean"] + hourly_stats["std"]
    hourly_stats["lower"] = (hourly_stats["mean"] - hourly_stats["std"]).clip(lower=0)

    # Find peak hour
    if not hourly_stats.empty:
        peak_idx = hourly_stats["mean"].idxmax()
        peak_hour = hourly_stats.loc[peak_idx, "Hour"]
        peak_rev = hourly_stats.loc[peak_idx, "mean"]
        st.caption(f"Peak hour: **{int(peak_hour)}:00** with avg ${peak_rev:,.0f} revenue")

    fig = go.Figure()
    # Upper bound (invisible, for fill reference)
    fig.add_trace(go.Scatter(
        x=hourly_stats["Hour"], y=hourly_stats["upper"],
        mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip",
    ))
    # Lower bound with fill to upper
    fig.add_trace(go.Scatter(
        x=hourly_stats["Hour"], y=hourly_stats["lower"],
        mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip",
        fill="tonexty", fillcolor=CHART_CONFIDENCE_BAND, name="+/- 1 Std Dev",
    ))
    # Mean line
    fig.add_trace(go.Scatter(
        x=hourly_stats["Hour"], y=hourly_stats["mean"],
        mode="lines+markers", name="Average Revenue",
        line=dict(color=CHART_PRIMARY, width=3),
        marker=dict(size=6, color=CHART_PRIMARY),
        hovertemplate="Hour: %{x}:00<br>Avg Revenue: $%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        height=380, margin=dict(l=0, r=0, t=20, b=40),
        xaxis=dict(title="Hour of Day", tickmode="linear", tick0=6, dtick=2,
                   showgrid=True, gridcolor="rgba(0,0,0,0.05)"),
        yaxis=dict(title="Revenue ($)", tickformat="$,.0f",
                   showgrid=True, gridcolor="rgba(0,0,0,0.05)"),
        plot_bgcolor="white", showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ---------------------------------------------------------------
    # 4. Top products + 5. Category mix (two columns)
    # ---------------------------------------------------------------
    left, right = st.columns(2)

    with left:
        st.subheader("Top Products")
        st.caption(f"Average daily revenue per product on {selected_day_name}s")

        product_daily = day_df.groupby([day_df["Date"].dt.date, "Description"])["Revenue"].sum().reset_index()
        avg_product = product_daily.groupby("Description")["Revenue"].mean().sort_values(ascending=True).tail(10)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=avg_product.index, x=avg_product.values, orientation="h",
            marker_color=CHART_PRIMARY,
            text=[f"${v:,.0f}" for v in avg_product.values], textposition="outside",
            textfont=dict(size=11, color="#5A6B5E"),
            hovertemplate="<b>%{y}</b><br>Avg Daily: $%{x:,.0f}<extra></extra>",
        ))
        fig.update_layout(
            showlegend=False, height=400, margin=dict(l=0, r=80, t=20, b=0),
            xaxis=dict(title="Avg Daily Revenue ($)", tickformat="$,.0f"), yaxis=dict(title=""),
        )
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("Category Mix")
        _render_category_pie(day_df, selected_category)

    st.markdown("---")

    # ---------------------------------------------------------------
    # 6. Trend over time
    # ---------------------------------------------------------------
    st.subheader(f"{selected_day_name} Revenue Trend")

    trend = daily_totals.sort_values("Date").copy()
    window = min(AVERAGE_DAY_ROLLING_WINDOW, max(1, num_instances // 2))
    trend["MA"] = trend["Revenue"].rolling(window, min_periods=1).mean()

    # Linear trend
    x_num = np.arange(len(trend))
    if len(trend) >= 2:
        slope, intercept = np.polyfit(x_num, trend["Revenue"].values, 1)
        trend_direction = "up" if slope > 0 else "down"
        pct_change = (slope * len(trend)) / trend["Revenue"].mean() * 100 if trend["Revenue"].mean() > 0 else 0
        st.caption(f"Trend: **{trend_direction}** ({abs(pct_change):,.1f}% over the period)")
    else:
        slope, intercept = 0, trend["Revenue"].mean()

    fig = go.Figure()
    # Actual values as scatter
    fig.add_trace(go.Scatter(
        x=trend["Date"], y=trend["Revenue"],
        mode="markers", name="Actual",
        marker=dict(size=8, color=CHART_PRIMARY, opacity=0.6),
        hovertemplate="%{x|%b %d, %Y}<br>Revenue: $%{y:,.0f}<extra></extra>",
    ))
    # Rolling average
    fig.add_trace(go.Scatter(
        x=trend["Date"], y=trend["MA"],
        mode="lines", name=f"{window}-wk Rolling Avg",
        line=dict(color=CHART_POSITIVE, width=2.5),
    ))
    # Linear trend line
    fig.add_trace(go.Scatter(
        x=trend["Date"], y=slope * x_num + intercept,
        mode="lines", name="Trend",
        line=dict(color="#D97706", width=1.5, dash="dash"),
    ))
    fig.update_layout(
        height=350, margin=dict(l=0, r=0, t=20, b=40),
        xaxis=dict(title="Date", showgrid=True, gridcolor="rgba(0,0,0,0.05)"),
        yaxis=dict(title="Revenue ($)", tickformat="$,.0f",
                   showgrid=True, gridcolor="rgba(0,0,0,0.05)"),
        plot_bgcolor="white", showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # ---------------------------------------------------------------
    # 7. Seasonality by month
    # ---------------------------------------------------------------
    st.subheader("Seasonality by Month")

    day_df_with_month = day_df.copy()
    day_df_with_month["MonthNum"] = day_df_with_month["Date"].dt.month
    monthly_day_rev = day_df_with_month.groupby([day_df_with_month["Date"].dt.date, "MonthNum"])["Revenue"].sum().reset_index()
    monthly_avg = monthly_day_rev.groupby("MonthNum").agg(
        AvgRevenue=("Revenue", "mean"),
        Count=("Revenue", "count"),
    ).reset_index()
    monthly_avg["MonthLabel"] = monthly_avg["MonthNum"].apply(lambda m: MONTH_NAMES[m - 1][:3])

    overall_avg = monthly_avg["AvgRevenue"].mean()

    # Highlight selected months if filter is active
    if selected_months:
        colors = [CHART_POSITIVE if m in selected_months else "#D1D5DB"
                  for m in monthly_avg["MonthNum"]]
    else:
        colors = [CHART_PRIMARY if v >= overall_avg else "#B0B8A8"
                  for v in monthly_avg["AvgRevenue"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=monthly_avg["MonthLabel"], y=monthly_avg["AvgRevenue"],
        marker_color=colors,
        text=[f"${v:,.0f}" for v in monthly_avg["AvgRevenue"]],
        textposition="outside", textfont=dict(size=10),
        customdata=monthly_avg["Count"],
        hovertemplate="<b>%{x}</b><br>Avg Revenue: $%{y:,.0f}<br>Instances: %{customdata}<extra></extra>",
    ))
    # Overall average line
    fig.add_hline(y=overall_avg, line_dash="dash", line_color="#6B705C",
                  annotation_text=f"Overall: ${overall_avg:,.0f}", annotation_position="top left")
    fig.update_layout(
        height=350, margin=dict(l=0, r=0, t=30, b=0),
        xaxis=dict(title="Month"), yaxis=dict(title="Avg Revenue ($)", tickformat="$,.0f"),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # ---------------------------------------------------------------
    # 8. Day comparison table
    # ---------------------------------------------------------------
    st.subheader("Day-of-Week Comparison")

    all_daily = df.groupby([df["Date"].dt.date, "DayName"]).agg(
        Revenue=("Revenue", "sum"),
        Transactions=("Basket_ID", "nunique"),
    ).reset_index()

    comparison = all_daily.groupby("DayName").agg(
        AvgRevenue=("Revenue", "mean"),
        AvgTransactions=("Transactions", "mean"),
        Instances=("Revenue", "count"),
    ).reset_index()

    # Compute avg basket value per day type
    comparison["AvgBasketValue"] = comparison["AvgRevenue"] / comparison["AvgTransactions"].replace(0, np.nan)
    comparison = comparison.sort_values("AvgRevenue", ascending=False)
    comparison["Rank"] = range(1, len(comparison) + 1)

    # Format for display
    display = comparison[["Rank", "DayName", "AvgRevenue", "AvgTransactions", "AvgBasketValue", "Instances"]].copy()
    display.columns = ["Rank", "Day", "Avg Revenue", "Avg Transactions", "Avg Basket Value", "Instances"]
    display["Avg Revenue"] = display["Avg Revenue"].apply(lambda v: f"${v:,.2f}")
    display["Avg Transactions"] = display["Avg Transactions"].apply(lambda v: f"{v:,.0f}")
    display["Avg Basket Value"] = display["Avg Basket Value"].apply(lambda v: f"${v:,.2f}")

    # Highlight the selected day
    def _highlight_row(row):
        if row["Day"] == selected_day_name:
            return [f"background-color: #E8F0E3; font-weight: bold;"] * len(row)
        return [""] * len(row)

    styled = display.style.apply(_highlight_row, axis=1).hide(axis="index")
    st.dataframe(styled, use_container_width=True, hide_index=True)


def _render_category_pie(df, selected_category):
    """Render category or product donut chart."""
    if selected_category != "All Categories":
        data = df.groupby("Description")["Revenue"].sum().sort_values(ascending=False)
        top = data.nlargest(6)
        other = data[~data.index.isin(top.index)].sum()
        if other > 0:
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
