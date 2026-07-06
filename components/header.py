"""App header component."""

from datetime import datetime

import streamlit as st


def render_header():
    """Render the editorial masthead with double rule."""
    dateline = datetime.now().strftime("%A %d %B %Y")
    st.markdown(
        f"""
        <div class="tmb-masthead">
            <div>
                <p class="tmb-kicker">Three Mills Bakery &times; Harris Farm</p>
                <h1>Sales <em>Intelligence</em></h1>
            </div>
            <div class="tmb-dateline">{dateline}<br>Canberra, ACT</div>
        </div>
        <div class="tmb-rule-double"></div>
        """,
        unsafe_allow_html=True,
    )


def render_date_banner(min_date, max_date, days_span):
    """Render the loaded-data reporting period strip."""
    if min_date.date() == max_date.date():
        dates = min_date.strftime("%A %d %B %Y")
    elif min_date.year == max_date.year:
        dates = f"{min_date.strftime('%d %B')} &mdash; {max_date.strftime('%d %B %Y')}"
    else:
        dates = f"{min_date.strftime('%d %B %Y')} &mdash; {max_date.strftime('%d %B %Y')}"

    st.markdown(
        f"""
        <div class="tmb-edition">
            <div>
                <p class="tmb-label">Reporting Period</p>
                <p class="tmb-dates">{dates}</p>
            </div>
            <div class="tmb-days">{days_span} day{'s' if days_span != 1 else ''} of trading</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
