"""Basket analysis view - transaction behavior and product associations."""

from collections import Counter
from itertools import combinations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import (
    BASKET_VALUE_BINS,
    BASKET_VALUE_LABELS,
    BASKET_ITEM_BINS,
    BASKET_ITEM_LABELS,
    CHART_PRIMARY,
    CHART_SECONDARY,
)
from components.insight_card import render_insight as _insight_card


def render(df):
    """Render the basket analysis dashboard."""
    st.markdown("## Basket Analysis")

    total_revenue = df["Revenue"].sum()
    num_baskets = df["Basket_ID"].nunique()
    total_items = df["Quantity"].sum()

    basket_revenue = df.groupby("Basket_ID")["Revenue"].sum()
    basket_items = df.groupby("Basket_ID")["Quantity"].sum()

    avg_basket_value = basket_revenue.mean() if num_baskets > 0 else 0
    avg_items_per_basket = basket_items.mean() if num_baskets > 0 else 0

    # Hero metrics
    _render_hero_metrics(avg_basket_value, avg_items_per_basket, num_baskets, total_revenue)

    st.markdown("")

    # Basket size distribution
    _render_basket_distribution(basket_revenue)

    st.markdown("")

    # Items per transaction
    _render_items_per_transaction(basket_items, num_baskets)

    st.markdown("")

    # Product penetration
    _render_product_penetration(df, num_baskets)

    st.markdown("")

    # Product pairs
    _render_product_pairs(df)

    st.markdown("")

    # Category penetration
    _render_category_penetration(df, num_baskets)

    st.markdown("")

    # Noteworthy baskets
    _render_noteworthy_baskets(df, basket_revenue, avg_basket_value, total_revenue, num_baskets)


# ---------------------------------------------------------------------------
# Sub-sections
# ---------------------------------------------------------------------------

def _render_hero_metrics(avg_val, avg_items, num_baskets, total_rev):
    """Top-level KPI cards."""
    metrics = [
        ("Avg Basket Value", f"${avg_val:.2f}"),
        ("Avg Items per Basket", f"{avg_items:.1f}"),
        ("Total Baskets", f"{num_baskets:,}"),
        ("Total Revenue", f"${total_rev:,.0f}"),
    ]
    cols = st.columns(4)
    for col, (label, value) in zip(cols, metrics):
        with col:
            st.markdown(
                f"""
                <div class="tmb-stat">
                    <p class="tmb-label">{label}</p>
                    <p class="tmb-value">{value}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_basket_distribution(basket_revenue):
    """Basket value distribution chart."""
    st.subheader("Basket Size Distribution")
    st.caption("Distribution of basket values across price ranges")

    basket_bins = pd.cut(basket_revenue, bins=BASKET_VALUE_BINS, labels=BASKET_VALUE_LABELS)
    dist = basket_bins.value_counts().reindex(BASKET_VALUE_LABELS, fill_value=0)

    chart_col, stat_col = st.columns([2, 1])
    with chart_col:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=dist.index, y=dist.values, marker_color=CHART_PRIMARY,
            text=dist.values, textposition="outside",
            hovertemplate="<b>%{x}</b><br>Baskets: %{y}<extra></extra>",
        ))
        fig.update_layout(height=350, xaxis_title="Basket Size", yaxis_title="Number of Baskets",
                          showlegend=False, margin=dict(t=20))
        st.plotly_chart(fig, use_container_width=True)

    with stat_col:
        st.markdown("**Basket Value Summary:**")
        st.markdown(f"- **Median:** ${basket_revenue.median():.2f}")
        st.markdown(f"- **75th percentile:** ${basket_revenue.quantile(0.75):.2f}")
        st.markdown(f"- **Largest basket:** ${basket_revenue.max():.2f}")
        st.markdown(f"- **Smallest basket:** ${basket_revenue.min():.2f}")

    under_30_pct = (basket_revenue < 30).sum() / len(basket_revenue) * 100 if len(basket_revenue) > 0 else 0
    insight = ("Strong impulse buying behavior. Consider point-of-sale displays."
               if under_30_pct > 70
               else "Healthy mix of small and large purchases.")
    _insight_card(f"<strong>{under_30_pct:.0f}%</strong> of baskets are under $30 &rarr; {insight}")


def _render_items_per_transaction(basket_items, num_baskets):
    """Items-per-transaction distribution."""
    st.subheader("Items Per Transaction")
    st.caption("How many items customers typically buy per visit")

    item_groups = pd.cut(basket_items, bins=BASKET_ITEM_BINS, labels=BASKET_ITEM_LABELS)
    item_dist = item_groups.value_counts().reindex(BASKET_ITEM_LABELS, fill_value=0)

    chart_col, stat_col = st.columns([2, 1])
    with chart_col:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=item_dist.index, y=item_dist.values, marker_color=CHART_SECONDARY,
            text=item_dist.values, textposition="outside",
            hovertemplate="<b>%{x} items</b><br>Baskets: %{y}<extra></extra>",
        ))
        fig.update_layout(height=350, xaxis_title="Items in Basket", yaxis_title="Number of Baskets",
                          showlegend=False, margin=dict(t=20))
        st.plotly_chart(fig, use_container_width=True)

    with stat_col:
        single = (basket_items == 1).sum()
        multi = (basket_items > 1).sum()
        st.markdown("**Transaction Breakdown:**")
        st.markdown(f"- **Single-item:** {single:,} ({single / num_baskets * 100:.1f}%)")
        st.markdown(f"- **Multi-item:** {multi:,} ({multi / num_baskets * 100:.1f}%)")
        st.markdown(f"- **Max items:** {int(basket_items.max())}")


def _render_product_penetration(df, num_baskets):
    """Product basket penetration chart."""
    st.subheader("Most Common Products in Baskets")
    st.caption("Products by basket penetration (% of baskets containing this product)")

    product_baskets = df.groupby("Description")["Basket_ID"].nunique()
    pen_df = pd.DataFrame({
        "Product": product_baskets.index,
        "Baskets": product_baskets.values,
        "Penetration %": product_baskets.values / num_baskets * 100,
    }).sort_values("Penetration %", ascending=False).head(15)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=pen_df["Product"], x=pen_df["Penetration %"], orientation="h", marker_color=CHART_PRIMARY,
        text=pen_df["Penetration %"].apply(lambda x: f"{x:.1f}%"), textposition="outside",
        hovertemplate="<b>%{y}</b><br>In %{x:.1f}% of baskets<extra></extra>",
    ))
    fig.update_layout(height=500, xaxis_title="% of Baskets", yaxis_title="",
                      showlegend=False, margin=dict(l=200, t=20), yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("View detailed penetration table"):
        st.dataframe(
            pen_df.style.format({"Baskets": "{:,}", "Penetration %": "{:.1f}%"}),
            use_container_width=True, hide_index=True, height=500,
        )


def _render_product_pairs(df):
    """Top product pairs analysis."""
    st.subheader("Top Product Pairs")
    st.caption("Products frequently bought together in the same transaction")

    baskets = df.groupby("Basket_ID")["Description"].apply(list)
    pairs = []
    for basket in baskets:
        unique = list(set(basket))
        if len(unique) >= 2:
            pairs.extend(combinations(sorted(unique), 2))

    if not pairs:
        st.info("Not enough multi-item transactions for product pair analysis")
        return

    top_pairs = Counter(pairs).most_common(15)
    pair_df = pd.DataFrame(top_pairs, columns=["Pair", "Count"])
    pair_df["Product A"] = pair_df["Pair"].apply(lambda x: x[0])
    pair_df["Product B"] = pair_df["Pair"].apply(lambda x: x[1])
    pair_df = pair_df[["Product A", "Product B", "Count"]]

    st.dataframe(pair_df.head(5), use_container_width=True, hide_index=True, height=200)

    if len(pair_df) > 5:
        with st.expander(f"View all {len(top_pairs)} product pairs"):
            st.dataframe(pair_df, use_container_width=True, hide_index=True, height=400)

    top = top_pairs[0]
    _insight_card(
        f"<strong>{top[0][0]}</strong> and <strong>{top[0][1]}</strong> "
        f"are bought together {top[1]} times &rarr; Consider creating a bundle or placing them nearby."
    )


def _render_category_penetration(df, num_baskets):
    """Category basket penetration chart."""
    st.subheader("Category Penetration")
    st.caption("% of baskets containing products from each category")

    basket_cats = df.groupby("Basket_ID")["Category"].apply(set)
    counts = {}
    for cats in basket_cats:
        for cat in cats:
            counts[cat] = counts.get(cat, 0) + 1

    cat_pen = pd.DataFrame({
        "Category": counts.keys(),
        "Baskets": counts.values(),
        "Penetration %": [c / num_baskets * 100 for c in counts.values()],
    }).sort_values("Penetration %", ascending=False)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=cat_pen["Category"], y=cat_pen["Penetration %"], marker_color=CHART_SECONDARY,
        text=cat_pen["Penetration %"].apply(lambda x: f"{x:.1f}%"), textposition="outside",
        hovertemplate="<b>%{x}</b><br>%{y:.1f}% of baskets<extra></extra>",
    ))
    fig.update_layout(height=400, xaxis_title="Category", yaxis_title="% of Baskets",
                      showlegend=False, margin=dict(t=20), xaxis=dict(tickangle=-45))
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("View category penetration table"):
        st.dataframe(
            cat_pen.style.format({"Baskets": "{:,}", "Penetration %": "{:.1f}%"}),
            use_container_width=True, hide_index=True, height=400,
        )


def _render_noteworthy_baskets(df, basket_revenue, avg_basket_value, total_revenue, num_baskets):
    """Highlight exceptional transactions."""
    st.subheader("Noteworthy Baskets")
    st.caption("Highlighting exceptional transactions and high-value customers")

    details = df.groupby("Basket_ID").agg({
        "Revenue": "sum", "Quantity": "sum",
        "Description": lambda x: " + ".join(x.tolist()), "Date": "first",
    }).reset_index()

    left, right = st.columns([2, 1])

    with left:
        st.markdown("#### Top 5 Largest Baskets (by Value)")
        top5 = details.nlargest(5, "Revenue")
        display = pd.DataFrame({
            "Date": top5["Date"].dt.strftime("%d %b %Y %I:%M %p"),
            "Products": top5["Description"].str[:60] + "...",
            "Items": top5["Quantity"].astype(int),
            "Total": top5["Revenue"].apply(lambda x: f"${x:,.2f}"),
        })
        st.dataframe(display, use_container_width=True, hide_index=True, height=220)

        st.markdown("#### Largest Basket by Item Count")
        max_item = details.nlargest(1, "Quantity").iloc[0]
        st.markdown(
            f"""
            <div class="tmb-insight" style="border-left-color:#48513E;">
                <p class="tmb-tag" style="color:#48513E;">
                    {max_item['Date'].strftime('%d %b %Y at %I:%M %p')}</p>
                <p style="font-family:var(--font-display); font-size:24px; margin:2px 0 6px 0;">
                    {int(max_item['Quantity'])} Items &bull; ${max_item['Revenue']:,.2f}</p>
                <p style="font-size:12.5px; color:var(--ink-soft);">
                    {max_item['Description'][:100]}...</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right:
        st.markdown("#### High-Value Stats")
        top_10_thresh = basket_revenue.quantile(0.9)
        top_10_baskets = basket_revenue[basket_revenue >= top_10_thresh]
        top_20_thresh = basket_revenue.quantile(0.8)
        top_20_rev = basket_revenue[basket_revenue >= top_20_thresh].sum()
        rev_concentration = top_20_rev / total_revenue * 100

        st.metric("Avg Top 10% Basket", f"${top_10_baskets.mean():.2f}",
                  delta=f"+{((top_10_baskets.mean() / avg_basket_value - 1) * 100):.0f}% vs avg")
        st.metric("Top 20% Revenue Share", f"{rev_concentration:.1f}%",
                  help="% of total revenue from top 20% of baskets")
        st.metric("Largest Single Basket", f"${basket_revenue.max():.2f}")

        st.markdown(
            f"""
            <div class="tmb-insight" style="margin-top:15px;">
                <p class="tmb-tag">Insights</p>
                <p style="font-size:12.5px; line-height:1.6;">
                    Top 10% baskets avg <strong>${top_10_baskets.mean():.0f}</strong><br>
                    Top 20% baskets drive <strong>{rev_concentration:.0f}%</strong> of revenue<br>
                    {"High concentration — focus on retaining top customers"
                     if rev_concentration > 50
                     else "Balanced customer base"}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
