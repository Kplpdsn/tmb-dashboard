"""TMB Harris Farm - Retail Sales Analytics Dashboard.

Main entry point. Run with: streamlit run app.py
"""

import streamlit as st

from config import TMB_SALES_FOLDER_ID, DAILY_MAX_DAYS, WEEKLY_MAX_DAYS
from styles import MAIN_CSS
from services.gdrive import get_service
from components.header import render_header, render_date_banner
from components.date_picker import render_date_picker
from components.filters import (
    render_category_product_filters,
    render_day_of_week_filter,
    render_hour_range_filter,
    apply_filters,
    render_filter_summary,
)
from views import daily, weekly, monthly, basket, compare, average_day
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
        st.rerun()

    st.markdown("---")

    # --- Mode Selector ---
    if "analysis_view_mode" not in st.session_state:
        st.session_state.analysis_view_mode = "Sales Overview"

    # Migrate old mode names
    _mode_migration = {
        "Simple Analysis": "Sales Overview",
        "Compare Periods": "Compare",
        "Basket Analysis": "What Sells Together",
        "Average Day": "Typical Day",
    }
    if st.session_state.analysis_view_mode in _mode_migration:
        st.session_state.analysis_view_mode = _mode_migration[st.session_state.analysis_view_mode]

    if st.button(
        "Sales Overview", use_container_width=True,
        type="primary" if st.session_state.analysis_view_mode == "Sales Overview" else "secondary",
    ):
        st.session_state.analysis_view_mode = "Sales Overview"
        st.rerun()

    with st.expander("More Analysis Modes", expanded=False):
        ec1, ec2, ec3 = st.columns(3)
        extra_modes = ["Compare", "What Sells Together", "Typical Day"]
        for col, label in zip([ec1, ec2, ec3], extra_modes):
            with col:
                if st.button(
                    label, use_container_width=True,
                    type="primary" if st.session_state.analysis_view_mode == label else "secondary",
                ):
                    st.session_state.analysis_view_mode = label
                    st.rerun()

    mode = st.session_state.analysis_view_mode

    # --- Filters ---
    selected_category, selected_product = render_category_product_filters(df)

    # Average Day mode: skip day-of-week filter (user picks the day directly), add month filter
    selected_months = None
    if mode == "Typical Day":
        day_filter_mode, selected_days = "All Days", None
    else:
        day_filter_mode, selected_days = render_day_of_week_filter(days_span)

    hour_range = render_hour_range_filter(df)

    # Apply filters (category, product, day-of-week, hour)
    filtered_df = apply_filters(df, selected_category, selected_product, day_filter_mode, selected_days, hour_range)

    # --- Average Day specific controls ---
    if mode == "Typical Day":
        from config import DAY_NAMES_ORDERED, MONTH_NAMES

        st.markdown("---")
        st.markdown("### Average Day Settings")
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
                help="Select specific months to model seasonal patterns (e.g., only December for Christmas)",
            )
            if len(selected_month_names) < len(month_options):
                selected_months = [MONTH_NAMES.index(m) + 1 for m in selected_month_names]
            else:
                selected_months = None  # All months = no filter

    # Filter summary
    if mode != "Typical Day":
        render_filter_summary(filtered_df, selected_category, selected_product, day_filter_mode, selected_days)

    # --- Route to view ---
    if mode == "Typical Day":
        # Check sample size
        day_instances = filtered_df[filtered_df["DayName"] == selected_day]["Date"].dt.date.nunique()
        if day_instances < 4:
            st.warning(
                f"Only **{day_instances}** {selected_day}(s) found in loaded data. "
                f"Load a wider date range for more accurate averages."
            )
        average_day.render(filtered_df, selected_day, selected_category, selected_months)

    elif mode == "Compare":
        compare.render(
            service, st.session_state.folder_id,
            min_date.date(), max_date.date(),
            selected_category, selected_product, day_filter_mode, selected_days,
        )

    elif mode == "What Sells Together":
        # Filtered basket warning
        any_filter = (
            selected_category != "All Categories"
            or selected_product != "All Products"
            or day_filter_mode != "All Days"
        )
        if any_filter:
            if day_filter_mode != "All Days":
                st.warning(
                    f"**Weekday Filtering Active:** Basket analysis with **{day_filter_mode}** "
                    f"filter may not show full customer behavior. "
                    f"Use 'All Days' for comprehensive basket analysis."
                )
            else:
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
        # Simple Analysis - auto-detect mode
        if days_span <= DAILY_MAX_DAYS:
            analysis_mode = "Daily"
        elif days_span <= WEEKLY_MAX_DAYS:
            analysis_mode = "Weekly"
        else:
            analysis_mode = "Monthly"

        mode_emoji = {"Daily": "📆", "Weekly": "📊", "Monthly": "📑"}
        st.markdown(f"## {mode_emoji[analysis_mode]} {analysis_mode} Analysis")

        if analysis_mode == "Daily":
            daily.render(filtered_df, min_date, selected_category, full_df=df)
        elif analysis_mode == "Weekly":
            weekly.render(filtered_df, min_date, max_date, selected_category)
        else:
            monthly.render(filtered_df, min_date, max_date, selected_category, selected_product)

    # --- Export (at bottom, after view content) ---
    if mode != "Compare":  # Compare mode has its own export
        with st.expander("Export & Download", expanded=False):
            export_cols = st.columns([1, 1, 1])

            with export_cols[0]:
                if mode == "Typical Day":
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
                                # In-browser preview
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
                                    selected_category, selected_product, day_filter_mode, hour_range,
                                )
                                date_str = f"{min_date.strftime('%Y%m%d')}_{max_date.strftime('%Y%m%d')}"
                                st.download_button(
                                    "Download PDF Report", data=pdf_buf,
                                    file_name=f"TMB_Report_{date_str}.pdf", mime="application/pdf",
                                    key=f"pdf_{date_str}",
                                )
                                # In-browser preview
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
        ("Smart Analytics", "Daily, weekly & monthly views with automatic insights"),
        ("Average Day Model", "Model a typical Monday, Tuesday, etc. from historical data"),
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
