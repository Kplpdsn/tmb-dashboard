"""Compare periods view - side-by-side comparison of two time periods."""

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from config import FIRST_SALE_DATE, COLOR_POSITIVE, COLOR_NEGATIVE
from services.data_processor import process_gdrive_files
from reports.comparison import generate as generate_comparison_pdf


def render(service, folder_id, current_start, current_end,
           selected_category="All Categories", selected_product="All Products",
           day_filter_mode="All Days", selected_days=None):
    """Render the period comparison view."""
    st.markdown("## Compare Periods")

    # Active filter indicator
    active = []
    if selected_category != "All Categories":
        active.append(f"Category: {selected_category}")
    if selected_product != "All Products":
        active.append(f"Product: {selected_product}")
    if day_filter_mode != "All Days":
        active.append(f"Days: {day_filter_mode}")
    if active:
        st.info(f"**Filters Active:** {' | '.join(active)}")

    today = datetime.now().date()

    # Auto-populate Period A from already-loaded data
    if "period_a_raw" not in st.session_state and "df" in st.session_state and current_start and current_end:
        st.session_state.period_a_raw = st.session_state.df
        st.session_state.dates_a = (current_start, current_end)

    # Quick compare presets
    with st.expander("Quick Compare Presets", expanded=False):
        pc1, pc2 = st.columns(2)
        with pc1:
            if st.button("This Week vs Last Week", use_container_width=True, key="preset_wk"):
                # This week = Mon to today; Last week = Mon-Sun prior
                weekday = today.weekday()
                this_week_start = today - timedelta(days=weekday)
                last_week_start = this_week_start - timedelta(days=7)
                last_week_end = this_week_start - timedelta(days=1)
                st.session_state._compare_preset = (
                    this_week_start, today, last_week_start, last_week_end
                )
        with pc2:
            if st.button("This Month vs Last Month", use_container_width=True, key="preset_mo"):
                this_month_start = today.replace(day=1)
                last_month_end = this_month_start - timedelta(days=1)
                last_month_start = last_month_end.replace(day=1)
                st.session_state._compare_preset = (
                    this_month_start, today, last_month_start, last_month_end
                )

    # Period A and B selectors
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("### Period A")
        default_a_start = current_start if current_start else today - timedelta(days=6)
        default_a_end = current_end if current_end else today
        p1_start = st.date_input("Start Date A", value=default_a_start,
                                 min_value=FIRST_SALE_DATE, max_value=today, key="p1_start")
        p1_end = st.date_input("End Date A", value=default_a_end,
                               min_value=p1_start, max_value=today, key="p1_end")
        if st.button("Load Period A", key="load_a", use_container_width=True):
            with st.spinner("Loading Period A..."):
                df_a, error = process_gdrive_files(service, folder_id, pd.Timestamp(p1_start), pd.Timestamp(p1_end))
                if error:
                    st.error(error)
                elif not df_a.empty:
                    st.session_state.period_a_raw = df_a
                    st.session_state.dates_a = (p1_start, p1_end)
                    st.success(f"Loaded {len(df_a):,} records")
                    st.rerun()
        if "period_a_raw" in st.session_state:
            st.success(f"Period A: {st.session_state.dates_a[0]} to {st.session_state.dates_a[1]}")

    with col_b:
        st.markdown("### Period B")
        p2_start = st.date_input("Start Date B", value=today - timedelta(days=13),
                                 min_value=FIRST_SALE_DATE, max_value=today, key="p2_start")
        p2_end = st.date_input("End Date B", value=today - timedelta(days=7),
                               min_value=p2_start, max_value=today, key="p2_end")
        if st.button("Load Period B", key="load_b", use_container_width=True):
            with st.spinner("Loading Period B..."):
                df_b, error = process_gdrive_files(service, folder_id, pd.Timestamp(p2_start), pd.Timestamp(p2_end))
                if error:
                    st.error(error)
                elif not df_b.empty:
                    st.session_state.period_b_raw = df_b
                    st.session_state.dates_b = (p2_start, p2_end)
                    st.success(f"Loaded {len(df_b):,} records")
                    st.rerun()
        if "period_b_raw" in st.session_state:
            st.success(f"Period B: {st.session_state.dates_b[0]} to {st.session_state.dates_b[1]}")

    # Handle quick preset auto-load
    if "_compare_preset" in st.session_state:
        a_start, a_end, b_start, b_end = st.session_state._compare_preset
        del st.session_state._compare_preset
        with st.spinner("Loading preset comparison periods..."):
            df_a, err_a = process_gdrive_files(service, folder_id, pd.Timestamp(a_start), pd.Timestamp(a_end))
            if not err_a and not df_a.empty:
                st.session_state.period_a_raw = df_a
                st.session_state.dates_a = (a_start, a_end)
            df_b, err_b = process_gdrive_files(service, folder_id, pd.Timestamp(b_start), pd.Timestamp(b_end))
            if not err_b and not df_b.empty:
                st.session_state.period_b_raw = df_b
                st.session_state.dates_b = (b_start, b_end)
            if err_a:
                st.error(f"Period A: {err_a}")
            if err_b:
                st.error(f"Period B: {err_b}")
            if not err_a and not err_b:
                st.rerun()

    # Show comparison results
    if "period_a_raw" not in st.session_state or "period_b_raw" not in st.session_state:
        st.info("Load both periods to see comparison")
        return

    st.markdown("---")
    st.markdown("## Comparison Results")

    df_a = _apply_comparison_filters(
        st.session_state.period_a_raw, selected_category, selected_product, day_filter_mode, selected_days
    )
    df_b = _apply_comparison_filters(
        st.session_state.period_b_raw, selected_category, selected_product, day_filter_mode, selected_days
    )

    _render_comparison_metrics(df_a, df_b)
    _render_category_comparison(df_a, df_b)
    _render_product_comparison(df_a, df_b)

    # PDF export
    st.markdown("---")
    st.markdown("### Export Comparison Report")
    if st.button("Generate Comparison PDF", use_container_width=True, type="primary"):
        with st.spinner("Generating comparison PDF report..."):
            hour_range = None
            if "Hour" in df_a.columns and "Hour" in df_b.columns:
                h_min = min(df_a["Hour"].min(), df_b["Hour"].min())
                h_max = max(df_a["Hour"].max(), df_b["Hour"].max())
                hour_range = (int(h_min), int(h_max))

            pdf_buf = generate_comparison_pdf(
                df_a, df_b,
                st.session_state.dates_a[0], st.session_state.dates_a[1],
                st.session_state.dates_b[0], st.session_state.dates_b[1],
                selected_category, selected_product, day_filter_mode, hour_range,
            )
            da = f"{st.session_state.dates_a[0].strftime('%Y%m%d')}_{st.session_state.dates_a[1].strftime('%Y%m%d')}"
            db = f"{st.session_state.dates_b[0].strftime('%Y%m%d')}_{st.session_state.dates_b[1].strftime('%Y%m%d')}"
            st.download_button(
                "Download Comparison Report", data=pdf_buf,
                file_name=f"TMB_Compare_{da}_vs_{db}.pdf", mime="application/pdf",
                use_container_width=True,
            )
            st.success("Comparison report generated successfully!")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _apply_comparison_filters(df, category, product, day_mode, days):
    """Apply active filters to a comparison dataframe."""
    out = df.copy()
    if category != "All Categories":
        out = out[out["Category"] == category]
    if product != "All Products":
        out = out[out["Description"] == product]
    if day_mode == "Weekdays":
        out = out[out["Date"].dt.dayofweek < 5]
    elif day_mode == "Weekends":
        out = out[out["Date"].dt.dayofweek >= 5]
    elif day_mode == "Custom" and days:
        out = out[out["Date"].dt.dayofweek.isin(days)]
    return out


def _delta_color(val):
    """Return inline color based on sign."""
    if val > 0:
        return COLOR_POSITIVE
    elif val < 0:
        return COLOR_NEGATIVE
    return "#6B705C"


def _render_comparison_metrics(df_a, df_b):
    """Side-by-side metric cards."""
    st.markdown("### Key Metrics Comparison")

    rev_a, rev_b = df_a["Revenue"].sum(), df_b["Revenue"].sum()
    bask_a, bask_b = df_a["Basket_ID"].nunique(), df_b["Basket_ID"].nunique()
    items_a, items_b = df_a["Quantity"].sum(), df_b["Quantity"].sum()
    aov_a = rev_a / bask_a if bask_a > 0 else 0
    aov_b = rev_b / bask_b if bask_b > 0 else 0

    period_a_label = (f"{st.session_state.dates_a[0].strftime('%b %d')} - "
                      f"{st.session_state.dates_a[1].strftime('%b %d')}")
    period_b_label = (f"{st.session_state.dates_b[0].strftime('%b %d')} - "
                      f"{st.session_state.dates_b[1].strftime('%b %d')}")

    pairs = [
        ("REVENUE", f"${rev_a:,.0f}", f"${rev_b:,.0f}",
         rev_b - rev_a, ((rev_b - rev_a) / rev_a * 100) if rev_a > 0 else 0),
        ("BASKETS", f"{bask_a:,}", f"{bask_b:,}",
         bask_b - bask_a, ((bask_b - bask_a) / bask_a * 100) if bask_a > 0 else 0),
        ("AVG BASKET VALUE", f"${aov_a:.2f}", f"${aov_b:.2f}",
         aov_b - aov_a, ((aov_b - aov_a) / aov_a * 100) if aov_a > 0 else 0),
        ("ITEMS SOLD", f"{int(items_a):,}", f"{int(items_b):,}",
         items_b - items_a, ((items_b - items_a) / items_a * 100) if items_a > 0 else 0),
    ]

    left, right = st.columns(2)
    for i, (label, va, vb, delta, pct) in enumerate(pairs):
        col = left if i % 2 == 0 else right
        with col:
            st.markdown(
                f"""
                <div style='background:#FFF; border:1px solid #E5E7EB; padding:20px;
                            border-radius:12px; margin-bottom:15px;'>
                    <div style='font-size:14px; color:#1F2933; font-weight:600; margin-bottom:15px;'>
                        {label}</div>
                    <div style='display:flex; align-items:center; justify-content:space-between;'>
                        <div>
                            <div style='font-size:11px; color:#6B7280; margin-bottom:3px;'>
                                Period A ({period_a_label})</div>
                            <div style='font-size:24px; font-weight:700; color:#1F2933;'>{va}</div>
                        </div>
                        <div style='font-size:32px; color:#A58A6F; margin:0 10px;'>&rarr;</div>
                        <div>
                            <div style='font-size:11px; color:#6B7280; margin-bottom:3px;'>
                                Period B ({period_b_label})</div>
                            <div style='font-size:24px; font-weight:700; color:#1F2933;'>{vb}</div>
                        </div>
                    </div>
                    <div style='margin-top:12px; padding-top:12px;
                                border-top:1px solid rgba(107,112,92,0.2);
                                font-size:16px; font-weight:600; color:{_delta_color(delta)};'>
                        {pct:+.1f}%
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _color_cell(val):
    """Styler for change % cells."""
    if val > 0:
        return f"background-color: rgba(134,179,127,0.15); color: {COLOR_POSITIVE}; font-weight: 600;"
    elif val < 0:
        return f"background-color: rgba(196,108,108,0.15); color: {COLOR_NEGATIVE}; font-weight: 600;"
    return ""


def _render_category_comparison(df_a, df_b):
    """Category revenue comparison table."""
    st.subheader("Category Performance Comparison")

    pa_label = (f"Period A ({st.session_state.dates_a[0].strftime('%b %d')} - "
                f"{st.session_state.dates_a[1].strftime('%b %d')})")
    pb_label = (f"Period B ({st.session_state.dates_b[0].strftime('%b %d')} - "
                f"{st.session_state.dates_b[1].strftime('%b %d')})")

    cat_a = df_a.groupby("Category")["Revenue"].sum().sort_values(ascending=False)
    cat_b = df_b.groupby("Category")["Revenue"].sum()

    comp = pd.DataFrame({pa_label: cat_a, pb_label: cat_b.reindex(cat_a.index, fill_value=0)})
    comp["Change $"] = comp[pb_label] - comp[pa_label]
    comp["Change %"] = ((comp[pb_label] - comp[pa_label]) / comp[pa_label] * 100).replace(
        [float("inf"), -float("inf")], 0
    ).fillna(0)

    st.dataframe(
        comp.style.format({pa_label: "${:,.0f}", pb_label: "${:,.0f}", "Change $": "${:,.0f}", "Change %": "{:+.1f}%"})
        .map(_color_cell, subset=["Change %"]),
        use_container_width=True,
    )


def _render_product_comparison(df_a, df_b):
    """Top products comparison table."""
    st.subheader("Top Products Comparison")

    pa_label = (f"Period A ({st.session_state.dates_a[0].strftime('%b %d')} - "
                f"{st.session_state.dates_a[1].strftime('%b %d')})")
    pb_label = (f"Period B ({st.session_state.dates_b[0].strftime('%b %d')} - "
                f"{st.session_state.dates_b[1].strftime('%b %d')})")

    prod_a = df_a.groupby("Description")["Revenue"].sum().nlargest(10)
    prod_b = df_b.groupby("Description")["Revenue"].sum()

    comp = pd.DataFrame({pa_label: prod_a, pb_label: prod_b.reindex(prod_a.index, fill_value=0)})
    comp["Change $"] = comp[pb_label] - comp[pa_label]
    comp["Change %"] = ((comp[pb_label] - comp[pa_label]) / comp[pa_label] * 100).replace(
        [float("inf"), -float("inf")], 0
    ).fillna(0)

    st.dataframe(
        comp.style.format({pa_label: "${:,.0f}", pb_label: "${:,.0f}", "Change $": "${:,.0f}", "Change %": "{:+.1f}%"})
        .map(_color_cell, subset=["Change %"]),
        use_container_width=True,
    )
