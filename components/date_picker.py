"""Date range picker with presets for initial data loading."""

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from config import FIRST_SALE_DATE, CHART_HIGHLIGHT
from services.data_processor import process_gdrive_files, get_available_dates


def render_date_picker(service, folder_id):
    """Render the date selection UI with presets. Loads data into session_state on submit."""
    st.markdown("## Select Date Range to Load Data")

    today = datetime.now().date()

    # Data availability and freshness
    available_dates = get_available_dates(service, folder_id)
    if available_dates:
        latest = available_dates[-1]
        earliest = available_dates[0]
        total_days = len(available_dates)
        days_stale = (today - latest).days

        avail_text = (
            f"Data available from **{earliest.strftime('%b %d, %Y')}** "
            f"to **{latest.strftime('%b %d, %Y')}** ({total_days} days)"
        )
        if days_stale == 0:
            freshness = "Data is current (today)"
            color = CHART_HIGHLIGHT
        elif days_stale == 1:
            freshness = "Last data: yesterday"
            color = CHART_HIGHLIGHT
        elif days_stale <= 3:
            freshness = f"Last data: {days_stale} days ago ({latest.strftime('%b %d')})"
            color = "#f59e0b"
        else:
            freshness = f"Last data: {days_stale} days ago ({latest.strftime('%b %d')})"
            color = "#ef4444"

        st.info(avail_text)
        st.markdown(
            f"<span style='font-size:13px; font-weight:600; color:{color};'>{freshness}</span>",
            unsafe_allow_html=True,
        )
    else:
        st.info(f"Sales data available from **May 29, 2024** onwards")

    # --- Yesterday button (prominent) ---
    yesterday = today - timedelta(days=1)
    if st.button("View Yesterday's Sales", type="primary", use_container_width=True, key="quick_yesterday_top"):
        st.session_state._auto_load_start = yesterday
        st.session_state._auto_load_end = yesterday

    # --- Quick presets (row 1) ---
    st.markdown("**Quick Select:**")
    cols = st.columns(5)
    quick_presets = [
        ("Today", today, today),
        ("Last 7 Days", today - timedelta(days=6), today),
        ("Last 30 Days", today - timedelta(days=29), today),
        ("This Month", today.replace(day=1), today),
        ("Last Month",
         (today.replace(day=1) - timedelta(days=1)).replace(day=1),
         today.replace(day=1) - timedelta(days=1)),
    ]

    for col, (label, start, end) in zip(cols, quick_presets):
        with col:
            if st.button(label, use_container_width=True, key=f"quick_{label}"):
                st.session_state._auto_load_start = start
                st.session_state._auto_load_end = end

    # --- Reporting presets (row 2) ---
    st.markdown("**Reporting Periods:**")
    rcols = st.columns(4)

    # Calculate quarter boundaries
    current_q_month = ((today.month - 1) // 3) * 3 + 1
    this_quarter_start = today.replace(month=current_q_month, day=1)
    last_quarter_end = this_quarter_start - timedelta(days=1)
    last_q_month = ((last_quarter_end.month - 1) // 3) * 3 + 1
    last_quarter_start = last_quarter_end.replace(month=last_q_month, day=1)
    ytd_start = today.replace(month=1, day=1)

    reporting_presets = [
        ("This Quarter", max(this_quarter_start, FIRST_SALE_DATE), today),
        ("Last Quarter", max(last_quarter_start, FIRST_SALE_DATE), last_quarter_end),
        ("YTD", max(ytd_start, FIRST_SALE_DATE), today),
        ("Last 12 Months", max(today - timedelta(days=364), FIRST_SALE_DATE), today),
    ]

    for col, (label, start, end) in zip(rcols, reporting_presets):
        with col:
            if st.button(label, use_container_width=True, key=f"report_{label}"):
                st.session_state._auto_load_start = start
                st.session_state._auto_load_end = end

    st.markdown("---")
    st.markdown("**Or Choose Custom Dates:**")

    # Use auto-load dates as defaults if set by preset
    default_start = st.session_state.get("_auto_load_start", st.session_state.get("preset_start", today - timedelta(days=6)))
    default_end = st.session_state.get("_auto_load_end", st.session_state.get("preset_end", today))

    dc1, dc2, dc3 = st.columns([2, 2, 1])
    with dc1:
        start_date = st.date_input(
            "From Date",
            value=default_start,
            min_value=FIRST_SALE_DATE,
            max_value=today,
            help="Select start date (data available from May 29, 2024)",
        )
    with dc2:
        end_date = st.date_input(
            "To Date",
            value=default_end,
            min_value=start_date,
            max_value=today,
            help="Select end date",
        )
    with dc3:
        st.markdown("<br>", unsafe_allow_html=True)
        load_clicked = st.button("Load Data", type="primary", use_container_width=True)

    # Auto-load from preset click
    auto_load = "_auto_load_start" in st.session_state and "_auto_load_end" in st.session_state
    if auto_load:
        start_date = st.session_state._auto_load_start
        end_date = st.session_state._auto_load_end
        del st.session_state._auto_load_start
        del st.session_state._auto_load_end

    if load_clicked or auto_load:
        with st.spinner("Loading data from Google Drive..."):
            df, error = process_gdrive_files(
                service, folder_id, pd.Timestamp(start_date), pd.Timestamp(end_date)
            )
            if error:
                st.error(error)
            elif not df.empty:
                st.session_state.df = df
                st.session_state.data_loaded = True
                st.success(f"Loaded {len(df):,} records from {df['Date'].nunique()} days!")
                st.rerun()
            else:
                st.warning("No data found in selected range")
