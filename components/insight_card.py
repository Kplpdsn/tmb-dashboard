"""Shared insight card component."""

import streamlit as st


def render_insight(text):
    """Render a styled insight card with caramel left rule and tag."""
    st.markdown(
        f"""
        <div class="tmb-insight">
            <p class="tmb-tag">Insight</p>
            <p>{text}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
