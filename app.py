"""TMB Harris Farm - Retail Sales Analytics Dashboard.

Main entry point. Run with: streamlit run app.py
"""

import streamlit as st

from config import TMB_SALES_FOLDER_ID
from styles import MAIN_CSS
from services.gdrive import get_service
from components.header import render_header, render_date_banner
from components.date_picker import render_date_picker
from components.filters import (
    render_category_product_filters,
    render_hour_range_filter,
    render_reset_filters,
    apply_filters,
    render_filter_summary,
)
from views import dashboard, basket, average_day
from reports.standard import generate as generate_pdf
from reports.average_day import generate as generate_avg_day_pdf
from reports.excel_export import generate_excel, generate_avg_day_excel, generate_baskets_excel


# --- Page Config ---
st.set_page_config(page_title="Three Mills Analytics Pro", layout="wide", page_icon="\U0001F950")
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
        for key in ("data_loaded", "active_tool"):
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

    st.markdown("---")

    # --- Sidebar Filters ---
    selected_category, selected_product = render_category_product_filters(df)
    hour_range = render_hour_range_filter(df)
    render_reset_filters()

    # Apply filters (category, product, hour)
    filtered_df = apply_filters(df, selected_category, selected_product, hour_range=hour_range)

    # --- Route to view ---
    active_tool = st.session_state.get("active_tool")

    if active_tool == "Typical Day":
        # Back button
        if st.button("\u2190 Back to Dashboard"):
            del st.session_state.active_tool
            st.rerun()

        # --- Typical Day specific controls ---
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

        # Check sample size
        day_instances = filtered_df[filtered_df["DayName"] == selected_day]["Date"].dt.date.nunique()
        if day_instances < 4:
            st.warning(
                f"Only **{day_instances}** {selected_day}(s) found in loaded data. "
                f"Load a wider date range for more accurate averages."
            )

        average_day.render(filtered_df, selected_day, selected_category, selected_months)

    elif active_tool == "Baskets":
        # Back button
        if st.button("\u2190 Back to Dashboard"):
            del st.session_state.active_tool
            st.rerun()

        # Basket filter warning
        any_filter = (
            selected_category != "All Categories"
            or selected_product != "All Products"
        )
        if any_filter:
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
        # Default: unified dashboard
        render_filter_summary(filtered_df, selected_category, selected_product)
        dashboard.render(filtered_df, selected_category, selected_product)

    # --- Export (at bottom, after view content) ---
    with st.expander("Export & Download", expanded=False):
        export_cols = st.columns([1, 1])

        with export_cols[0]:
            if active_tool == "Typical Day":
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
                                selected_category, selected_product, "All Days", hour_range,
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
            date_str = f"{min_date.strftime('%Y%m%d')}_{max_date.strftime('%Y%m%d')}"
            try:
                if active_tool == "Typical Day":
                    excel_buf = generate_avg_day_excel(
                        filtered_df, selected_day, selected_category, selected_months,
                    )
                    excel_name = f"TMB_Avg_{selected_day}_{date_str}.xlsx"
                elif active_tool == "Baskets":
                    excel_buf = generate_baskets_excel(filtered_df)
                    excel_name = f"TMB_Baskets_{date_str}.xlsx"
                else:
                    excel_buf = generate_excel(filtered_df, min_date, max_date)
                    excel_name = f"TMB_Product_Sales_{date_str}.xlsx"
                st.download_button(
                    "Download Excel", data=excel_buf,
                    file_name=excel_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="excel_export", use_container_width=True,
                )
            except Exception as e:
                st.error(f"Excel generation failed: {e}")


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
        ("Morning Brief", "Revenue, trends & what's selling \u2014 all on one page"),
        ("Typical Day Model", "Model a typical Monday, Tuesday, etc. from historical data"),
    ]
    cols = st.columns(2)
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
