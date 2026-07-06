"""Date picker with three modes: Yesterday, Custom Range, Specific Dates."""

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from config import FIRST_SALE_DATE, CHART_HIGHLIGHT
from services.data_processor import process_gdrive_files, get_available_dates


def _parse_specific_dates(text: str, available_dates: list) -> tuple[list, str | None]:
    """Parse comma-separated DD/MM/YYYY dates from user input.

    Returns (sorted_date_list, error_message).
    """
    if not text or not text.strip():
        return [], "Enter at least one date"

    today = datetime.now().date()
    dates = []
    errors = []

    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            dt = datetime.strptime(part, "%d/%m/%Y").date()
        except ValueError:
            errors.append(f"'{part}' — use DD/MM/YYYY format")
            continue

        if dt > today:
            errors.append(f"'{part}' is in the future")
        elif dt < FIRST_SALE_DATE:
            errors.append(
                f"'{part}' is before data availability "
                f"({FIRST_SALE_DATE.strftime('%d/%m/%Y')})"
            )
        elif available_dates and dt not in available_dates:
            errors.append(f"'{part}' — no data file found")
        else:
            dates.append(dt)

    if errors:
        return [], "**Invalid dates:**\n" + "\n".join(f"- {e}" for e in errors)
    if not dates:
        return [], "No valid dates entered"

    return sorted(set(dates)), None


def render_date_picker(service, folder_id):
    """Render the date selection UI. Loads data into session_state on submit."""
    st.markdown("## Select Dates to Load")

    today = datetime.now().date()

    # --- Data availability banner ---
    available_dates = get_available_dates(service, folder_id)
    if available_dates:
        latest = available_dates[-1]
        earliest = available_dates[0]
        total_days = len(available_dates)
        days_stale = (today - latest).days

        avail_text = (
            f"Data available from **{earliest.strftime('%d %b %Y')}** "
            f"to **{latest.strftime('%d %b %Y')}** ({total_days} days)"
        )
        if days_stale <= 1:
            freshness = "Data is current (today)" if days_stale == 0 else "Last data: yesterday"
            color = CHART_HIGHLIGHT
        elif days_stale <= 3:
            freshness = f"Last data: {days_stale} days ago ({latest.strftime('%d %b')})"
            color = "#f59e0b"
        else:
            freshness = f"Last data: {days_stale} days ago ({latest.strftime('%d %b')})"
            color = "#ef4444"

        st.info(avail_text)
        st.markdown(
            f"<span style='font-size:13px; font-weight:600; color:{color};'>{freshness}</span>",
            unsafe_allow_html=True,
        )
    else:
        st.info("Sales data available from **29 May 2024** onwards")

    # --- Yesterday button ---
    yesterday = today - timedelta(days=1)
    if st.button(
        "View Yesterday's Sales",
        type="primary",
        use_container_width=True,
        key="quick_yesterday_top",
    ):
        st.session_state._auto_load_start = yesterday
        st.session_state._auto_load_end = yesterday

    st.markdown("---")

    # --- Two tabs: Range vs Specific Dates ---
    tab_range, tab_specific = st.tabs(["Custom Date Range", "Specific Dates"])

    with tab_range:
        default_start = st.session_state.get(
            "_auto_load_start", today - timedelta(days=6)
        )
        default_end = st.session_state.get("_auto_load_end", today)

        dc1, dc2, dc3 = st.columns([2, 2, 1])
        with dc1:
            start_date = st.date_input(
                "From Date",
                value=default_start,
                min_value=FIRST_SALE_DATE,
                max_value=today,
                format="DD/MM/YYYY",
                help="Select start date (data available from 29 May 2024)",
            )
        with dc2:
            end_date = st.date_input(
                "To Date",
                value=default_end,
                min_value=start_date,
                max_value=today,
                format="DD/MM/YYYY",
                help="Select end date",
            )
        with dc3:
            st.markdown("<br>", unsafe_allow_html=True)
            range_load = st.button(
                "Load Data", type="primary", use_container_width=True, key="load_range"
            )

    with tab_specific:
        st.markdown(
            "Enter dates separated by commas (DD/MM/YYYY). "
            "Handy for comparing like-for-like days — e.g. the last 4 Saturdays."
        )
        dates_text = st.text_input(
            "Dates",
            placeholder="01/03/2026, 22/02/2026, 15/02/2026, 08/02/2026",
            key="specific_dates_input",
            label_visibility="collapsed",
        )
        specific_load = st.button(
            "Load Specific Dates",
            type="primary",
            use_container_width=True,
            key="load_specific",
        )

    # --- Auto-load from yesterday button ---
    auto_load = (
        "_auto_load_start" in st.session_state
        and "_auto_load_end" in st.session_state
    )
    if auto_load:
        start_date = st.session_state._auto_load_start
        end_date = st.session_state._auto_load_end
        del st.session_state._auto_load_start
        del st.session_state._auto_load_end

    # --- Execute load ---
    if range_load or auto_load:
        with st.spinner("Loading data from Google Drive..."):
            df, error = process_gdrive_files(
                service, folder_id, pd.Timestamp(start_date), pd.Timestamp(end_date)
            )
            if error:
                st.error(error)
            elif not df.empty:
                st.session_state.df = df
                st.session_state.data_loaded = True
                st.success(
                    f"Loaded {len(df):,} records from {df['Date'].nunique()} days!"
                )
                st.rerun()
            else:
                st.warning("No data found in selected range")

    elif specific_load:
        parsed_dates, parse_error = _parse_specific_dates(dates_text, available_dates)
        if parse_error:
            st.error(parse_error)
        else:
            with st.spinner(
                f"Loading {len(parsed_dates)} specific dates from Google Drive..."
            ):
                df, error = process_gdrive_files(
                    service, folder_id, specific_dates=parsed_dates
                )
                if error:
                    st.error(error)
                elif not df.empty:
                    st.session_state.df = df
                    st.session_state.data_loaded = True
                    st.success(
                        f"Loaded {len(df):,} records from {df['Date'].nunique()} days!"
                    )
                    st.rerun()
                else:
                    st.warning("No data found for the selected dates")
