"""Sidebar filter components."""

import streamlit as st


def render_category_product_filters(df):
    """Render category and product dropdown filters in sidebar. Returns (selected_category, selected_product)."""
    with st.sidebar:
        st.markdown("### Filters")
        selected_category = st.selectbox(
            "Category",
            options=["All Categories"] + sorted(df["Category"].unique()),
            index=0,
            key="main_category_filter",
        )

        if selected_category != "All Categories":
            available = sorted(df[df["Category"] == selected_category]["Description"].unique())
            product_label = f"All Products in {selected_category}"
        else:
            available = sorted(df["Description"].unique())
            product_label = "All Products"

        selected_product = st.selectbox(
            "Product",
            options=[product_label] + available,
            index=0,
            key="main_product_filter",
        )

        # Normalize display-friendly label back to code-friendly sentinel
        if selected_product.startswith("All Products"):
            selected_product = "All Products"

    return selected_category, selected_product


# DEPRECATED — will be removed when app.py is rewritten (Task 7)
def render_day_of_week_filter(days_span):
    """Render the day-of-week filter in sidebar. Returns (day_filter_mode, selected_days)."""
    selected_days = None

    if days_span < 7:
        st.session_state.day_filter_mode = "All Days"
        return "All Days", None

    with st.sidebar:
        if "day_filter_mode" not in st.session_state:
            st.session_state.day_filter_mode = "All Days"

        day_options = ["All Days", "Weekdays", "Weekends", "Custom"]
        current_idx = day_options.index(st.session_state.day_filter_mode) if st.session_state.day_filter_mode in day_options else 0
        day_filter_mode = st.radio(
            "Day Filter",
            options=day_options,
            index=current_idx,
            key="day_filter_radio",
            horizontal=True,
        )
        if day_filter_mode != st.session_state.day_filter_mode:
            st.session_state.day_filter_mode = day_filter_mode
            st.rerun()

        if st.session_state.day_filter_mode == "Custom":
            st.markdown("**Select days:**")
            lc, rc = st.columns(2)
            with lc:
                mon = st.checkbox("Mon", value=True, key="mon")
                tue = st.checkbox("Tue", value=True, key="tue")
                wed = st.checkbox("Wed", value=True, key="wed")
                thu = st.checkbox("Thu", value=True, key="thu")
            with rc:
                fri = st.checkbox("Fri", value=True, key="fri")
                sat = st.checkbox("Sat", value=True, key="sat")
                sun = st.checkbox("Sun", value=True, key="sun")
            selected_days = [i for i, checked in enumerate([mon, tue, wed, thu, fri, sat, sun]) if checked]

    return st.session_state.day_filter_mode, selected_days


def render_hour_range_filter(df):
    """Render the hour-range slider in sidebar. Returns (start_hour, end_hour) tuple."""
    with st.sidebar:
        if "Hour" in df.columns:
            min_hour = int(df["Hour"].min())
            max_hour = int(df["Hour"].max())
        else:
            min_hour, max_hour = 6, 21

        hour_range = st.slider(
            "Hour Range",
            min_value=min_hour,
            max_value=max_hour,
            value=(min_hour, max_hour),
            step=1,
            format="%d:00",
            key="hour_range_slider",
        )

    return hour_range


def render_reset_filters():
    """Render a 'Reset Filters' button in the sidebar."""
    with st.sidebar:
        if st.button("Reset Filters", key="reset_all_filters", use_container_width=True):
            keys_to_clear = [k for k in st.session_state if "filter" in k or k == "hour_range_slider"]
            for key in keys_to_clear:
                del st.session_state[key]
            st.rerun()


def apply_filters(df, selected_category, selected_product, day_filter_mode="All Days", selected_days=None, hour_range=(0, 23)):
    """Apply all active filters to the dataframe. Returns filtered df."""
    filtered = df.copy()

    start_hour, end_hour = hour_range
    filtered = filtered[(filtered["Hour"] >= start_hour) & (filtered["Hour"] <= end_hour)]

    if selected_category != "All Categories":
        filtered = filtered[filtered["Category"] == selected_category]
    if selected_product != "All Products":
        filtered = filtered[filtered["Description"] == selected_product]

    # DEPRECATED day filtering — kept for backward compat until app.py rewrite
    if day_filter_mode == "Weekdays":
        filtered = filtered[filtered["Date"].dt.dayofweek < 5]
    elif day_filter_mode == "Weekends":
        filtered = filtered[filtered["Date"].dt.dayofweek >= 5]
    elif day_filter_mode == "Custom" and selected_days:
        filtered = filtered[filtered["Date"].dt.dayofweek.isin(selected_days)]

    return filtered


def render_filter_summary(filtered_df, selected_category, selected_product, day_filter_mode="All Days", selected_days=None):
    """Show a compact filter summary when filters are active."""
    any_filter = (
        selected_category != "All Categories"
        or selected_product != "All Products"
        or day_filter_mode != "All Days"
    )
    if not any_filter:
        return

    parts = []
    if selected_category != "All Categories":
        parts.append(selected_category)
    if selected_product != "All Products":
        parts.append(selected_product)
    if day_filter_mode != "All Days":
        if day_filter_mode == "Custom" and selected_days is not None:
            day_map = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}
            parts.append("Days: " + ", ".join(day_map[d] for d in sorted(selected_days)))
        else:
            parts.append(day_filter_mode)

    unique_days = filtered_df["Date"].nunique() if not filtered_df.empty else 0
    num_transactions = len(filtered_df)

    st.caption(f"Filtered: {' | '.join(parts)} ({unique_days} days, {num_transactions:,} rows)")
