"""App header component."""

import streamlit as st


def render_header():
    """Render the main application header."""
    st.markdown(
        """
        <div class="main-header">
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <div>
                    <h1 class="main-title">TMB Harris Farm</h1>
                    <p class="main-subtitle">TMB HARRIS RETAIL SALES ANALYTICS DASHBOARD</p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_date_banner(min_date, max_date, days_span):
    """Render the loaded-data date range banner."""
    st.markdown(
        f"""
        <div style='background: linear-gradient(90deg, #7D8570 0%, #B5C99A 100%);
                    padding: 20px 30px; border-radius: 12px; margin-bottom: 25px;
                    box-shadow: 0 4px 15px rgba(125, 133, 112, 0.25);'>
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <div>
                    <h3 style='color: white; margin: 0; font-family: Georgia, serif; font-size: 24px;'>
                        {min_date.strftime('%B %d, %Y')} &mdash; {max_date.strftime('%B %d, %Y')}
                    </h3>
                    <p style='color: #FAF9F6; margin: 5px 0 0 0; opacity: 0.95; font-size: 14px;'>
                        {days_span} day{'s' if days_span != 1 else ''} of data loaded
                    </p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
