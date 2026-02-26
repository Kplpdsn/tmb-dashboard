"""Shared insight card component."""

import streamlit as st


def render_insight(text):
    """Render a styled insight card with left border."""
    st.markdown(
        f"""
        <div style='background:#F9FAFB; padding:15px 20px; border-radius:6px;
                    border-left:3px solid #4B5563; margin:10px 0;'>
            <p style='font-size:13px; color:#1F2933; line-height:1.5; margin:0;'>{text}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
