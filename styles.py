"""Design system for the Streamlit app: CSS + shared Plotly theme.

Aesthetic: "artisan ledger" -- editorial, print-inspired. Fraunces for
display type, Archivo for UI and figures, a flour/ink palette with sage
and burnt-caramel accents. Refinement comes from hairline rules and
spacing, not gradients or shadows.

Chart color constants live in config.py; this module owns the CSS tokens
and the global Plotly template.
"""

import plotly.graph_objects as go
import plotly.io as pio

from config import CHART_NEGATIVE, CHART_POSITIVE, PIE_COLORS

# Core palette (mirrored as CSS variables below)
INK = "#23281F"
INK_SOFT = "#5E6556"
FLOUR = "#FAF7F1"
LINE = "#E4DCCC"


def register_plotly_theme():
    """Register the 'tmb' Plotly template and set it as default.

    Call once at app start, before any figure is created. Views only need
    to set data colors; fonts, backgrounds, grid, and hover styling come
    from here.
    """
    tmpl = go.layout.Template()
    tmpl.layout = go.Layout(
        font=dict(family="Archivo, sans-serif", size=12.5, color=INK),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=PIE_COLORS,
        xaxis=dict(
            showgrid=False,
            linecolor=LINE,
            tickcolor=LINE,
            zeroline=False,
            title_font=dict(size=11, color=INK_SOFT),
            tickfont=dict(size=11, color=INK_SOFT),
        ),
        yaxis=dict(
            gridcolor="rgba(35, 40, 31, 0.08)",
            zeroline=False,
            linecolor="rgba(0,0,0,0)",
            title_font=dict(size=11, color=INK_SOFT),
            tickfont=dict(size=11, color=INK_SOFT),
        ),
        hoverlabel=dict(
            bgcolor=INK,
            bordercolor=INK,
            font=dict(family="Archivo, sans-serif", size=12.5, color=FLOUR),
        ),
        legend=dict(font=dict(size=11, color=INK_SOFT)),
    )
    pio.templates["tmb"] = tmpl
    pio.templates.default = "tmb"


MAIN_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:ital,wght@0,400..700;1,400..700&family=Fraunces:ital,opsz,wght@0,9..144,300..700;1,9..144,300..700&display=swap');

/* ========================================
   ARTISAN LEDGER -- DESIGN TOKENS
   ======================================== */

:root {
    --flour: #FAF7F1;        /* app background */
    --linen: #F3EEE3;        /* sidebar, tint blocks */
    --card: #FFFFFF;
    --line: #E4DCCC;         /* hairline rules and borders */
    --ink: #23281F;
    --ink-soft: #5E6556;
    --ink-faint: #9B9F90;
    --sage: #6F7A64;
    --sage-deep: #48513E;
    --caramel: #B4642A;      /* accent: insights, emphasis */
    --positive: #4C7A46;
    --negative: #AC3B2A;
    --font-display: 'Fraunces', Georgia, serif;
    --font-ui: 'Archivo', -apple-system, sans-serif;
}

/* ========================================
   BASE & CHROME
   ======================================== */

.stApp {
    background: var(--flour);
}

/* Faint paper grain over the whole app */
.stApp::before {
    content: "";
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: 0;
    opacity: 0.035;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2'/%3E%3C/filter%3E%3Crect width='140' height='140' filter='url(%23n)'/%3E%3C/svg%3E");
}

#MainMenu, footer,
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
[data-testid="stAppDeployButton"],
.stAppDeployButton {
    display: none !important;
}

header[data-testid="stHeader"] {
    background: transparent;
}

.block-container {
    max-width: 1180px;
    padding-top: 1.4rem;
    padding-bottom: 2rem;
}

html, body, .stApp, [data-testid="stAppViewContainer"] {
    font-family: var(--font-ui);
    color: var(--ink);
}

p, li, label, .stMarkdown {
    font-family: var(--font-ui);
}

/* ========================================
   TYPOGRAPHY
   ======================================== */

h1, h2, h3,
[data-testid="stHeading"] h1,
[data-testid="stHeading"] h2,
[data-testid="stHeading"] h3,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3 {
    font-family: var(--font-display) !important;
    font-weight: 500 !important;
    color: var(--ink) !important;
    letter-spacing: -0.01em;
}

h2, [data-testid="stMarkdownContainer"] h2 { font-size: 1.7rem !important; }
h3, [data-testid="stMarkdownContainer"] h3 { font-size: 1.4rem !important; }

h4, h5, h6 {
    font-family: var(--font-ui);
    font-weight: 650;
    color: var(--ink);
}

a { color: var(--sage-deep); }

.stCaption, [data-testid="stCaptionContainer"] {
    color: var(--ink-soft) !important;
}

hr {
    border: none;
    border-top: 1px solid var(--line);
    margin: 1.5rem 0;
}

/* ========================================
   MASTHEAD, EDITION STRIP, FOOTER
   ======================================== */

.tmb-masthead {
    padding: 20px 0 16px 0;
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
}

.tmb-masthead .tmb-kicker {
    font-size: 11px;
    font-weight: 650;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: var(--ink-soft);
    margin: 0 0 10px 0;
}

.tmb-masthead h1 {
    font-family: var(--font-display);
    font-size: 42px;
    font-weight: 480;
    line-height: 1.02;
    margin: 0;
    letter-spacing: -0.015em;
}

.tmb-masthead h1 em {
    font-style: italic;
    font-weight: 420;
    color: var(--sage-deep);
}

.tmb-masthead .tmb-dateline {
    font-family: var(--font-display);
    font-style: italic;
    font-size: 14px;
    color: var(--ink-soft);
    text-align: right;
    padding-bottom: 6px;
    white-space: nowrap;
}

/* Classic double rule: thick over thin */
.tmb-rule-double {
    border-top: 2.5px solid var(--ink);
    border-bottom: 1px solid var(--ink);
    height: 4px;
    margin: 0 0 22px 0;
}

.tmb-edition {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
    background: var(--card);
    border: 1px solid var(--line);
    border-left: 3px solid var(--sage-deep);
    border-radius: 2px;
    padding: 16px 22px;
    margin: 2px 0 10px 0;
}

.tmb-edition .tmb-label {
    font-size: 10.5px;
    font-weight: 650;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--ink-soft);
    margin: 0 0 3px 0;
}

.tmb-edition .tmb-dates {
    font-family: var(--font-display);
    font-size: 23px;
    font-weight: 500;
    color: var(--ink);
    margin: 0;
    line-height: 1.15;
}

.tmb-edition .tmb-days {
    font-size: 11.5px;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--caramel);
    text-align: right;
}

.tmb-footer {
    text-align: center;
    padding: 18px 0 10px 0;
}

.tmb-footer .tmb-brand {
    font-size: 10.5px;
    font-weight: 650;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: var(--ink-soft);
    margin: 0;
}

.tmb-footer .tmb-byline {
    font-family: var(--font-display);
    font-style: italic;
    font-size: 13px;
    color: var(--ink-faint);
    margin: 6px 0 0 0;
}

/* ========================================
   CARDS
   ======================================== */

.tmb-insight {
    background: var(--card);
    border: 1px solid var(--line);
    border-left: 3px solid var(--caramel);
    border-radius: 2px;
    padding: 13px 18px 12px 18px;
    margin: 10px 0;
}

.tmb-insight .tmb-tag {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--caramel);
    margin: 0 0 4px 0;
}

.tmb-insight p {
    font-size: 13.5px;
    line-height: 1.55;
    color: var(--ink);
    margin: 0;
}

.tmb-feature {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 2px;
    padding: 24px 26px;
    height: 100%;
}

.tmb-feature .tmb-no {
    font-family: var(--font-display);
    font-style: italic;
    font-size: 15px;
    color: var(--caramel);
    margin: 0;
}

.tmb-feature h4 {
    font-family: var(--font-display);
    font-size: 21px;
    font-weight: 500;
    margin: 6px 0 8px 0;
}

.tmb-feature p {
    font-size: 13.5px;
    line-height: 1.55;
    color: var(--ink-soft);
    margin: 0;
}

/* Big standalone stat (basket view cards) */
.tmb-stat {
    background: var(--card);
    border: 1px solid var(--line);
    border-top: 2px solid var(--sage);
    border-radius: 2px;
    padding: 18px 20px 16px 20px;
    text-align: center;
}

.tmb-stat .tmb-label {
    font-size: 10.5px;
    font-weight: 650;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--ink-soft);
    margin: 0;
}

.tmb-stat .tmb-value {
    font-family: var(--font-display);
    font-size: 34px;
    font-weight: 500;
    color: var(--ink);
    margin: 8px 0 2px 0;
    line-height: 1;
}

.tmb-stat .tmb-sub {
    font-size: 12px;
    color: var(--ink-faint);
    margin: 0;
}

/* ========================================
   METRICS (st.metric)
   ======================================== */

[data-testid="stMetric"] {
    background: var(--card);
    border: 1px solid var(--line);
    border-top: 2px solid var(--sage);
    border-radius: 2px;
    padding: 16px 20px 12px 20px;
}

[data-testid="stMetricLabel"] p {
    font-size: 11px !important;
    font-weight: 650;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--ink-soft);
}

[data-testid="stMetricValue"] {
    font-family: var(--font-display);
    font-size: clamp(21px, 1.9vw, 29px);
    font-weight: 500;
    color: var(--ink);
}

[data-testid="stMetricDelta"] {
    font-size: 13px;
    font-weight: 600;
    font-feature-settings: 'tnum';
}

/* ========================================
   BUTTONS
   ======================================== */

.stButton > button, .stDownloadButton > button {
    border-radius: 2px;
    font-family: var(--font-ui);
    font-weight: 600;
    font-size: 13.5px;
    letter-spacing: 0.03em;
    padding: 9px 20px;
    transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
    box-shadow: none;
}

.stButton > button[kind="primary"],
.stDownloadButton > button {
    background: var(--sage-deep);
    color: #FDFCF8;
    border: 1px solid var(--sage-deep);
}

.stButton > button[kind="primary"]:hover,
.stDownloadButton > button:hover {
    background: var(--ink);
    border-color: var(--ink);
    color: #FDFCF8;
}

.stButton > button[kind="secondary"] {
    background: transparent;
    color: var(--ink);
    border: 1px solid var(--ink-faint);
}

.stButton > button[kind="secondary"]:hover {
    background: var(--card);
    border-color: var(--ink);
    color: var(--ink);
}

/* ========================================
   TABS, EXPANDERS, INPUTS
   ======================================== */

.stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    border-bottom: 1px solid var(--line);
}

.stTabs [data-baseweb="tab"] {
    font-family: var(--font-ui);
    font-size: 12px;
    font-weight: 650;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--ink-soft);
    background: transparent;
}

.stTabs [aria-selected="true"] {
    color: var(--ink) !important;
}

.stTabs [data-baseweb="tab-highlight"] {
    background-color: var(--caramel);
}

[data-testid="stExpander"] {
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 2px;
}

[data-testid="stExpander"] summary {
    font-size: 12px;
    font-weight: 650;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--ink-soft);
}

[data-testid="stExpander"] summary:hover {
    color: var(--ink);
}

.stSelectbox [data-baseweb="select"] > div,
.stDateInput input,
.stTextInput input {
    background: var(--card) !important;
    border-color: var(--line) !important;
    color: var(--ink) !important;
    border-radius: 2px !important;
    font-family: var(--font-ui);
}

/* ========================================
   SIDEBAR
   ======================================== */

[data-testid="stSidebar"] {
    background: var(--linen);
    border-right: 1px solid var(--line);
}

[data-testid="stSidebar"] label,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
    color: var(--ink) !important;
}

[data-testid="stSidebar"] h3 {
    font-size: 1.1rem;
}

/* ========================================
   ALERTS
   ======================================== */

[data-testid="stAlert"],
[data-testid="stAlertContainer"] {
    background: var(--card) !important;
    border: 1px solid var(--line) !important;
    border-left: 3px solid var(--sage) !important;
    border-radius: 2px !important;
    color: var(--ink) !important;
    font-family: var(--font-ui);
}

[data-testid="stAlert"] [data-testid="stAlertContainer"] {
    border: none !important;
    background: transparent !important;
}

[data-testid="stAlert"] p,
[data-testid="stAlertContainer"] p {
    color: var(--ink) !important;
}

[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]),
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) {
    border-left-color: var(--positive) !important;
}

[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]),
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {
    border-left-color: var(--caramel) !important;
}

[data-testid="stAlert"]:has([data-testid="stAlertContentError"]),
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {
    border-left-color: var(--negative) !important;
}

/* ========================================
   MISC
   ======================================== */

div[data-testid="stHorizontalBlock"] {
    gap: 1rem;
}

[data-testid="stDataFrame"] {
    border: 1px solid var(--line);
    border-radius: 2px;
}

/* ===== PRINT-FRIENDLY STYLES ===== */
@media print {
    @page {
        size: A4;
        margin: 1.5cm;
    }

    .stApp, .main {
        max-width: 100% !important;
        padding: 0 !important;
        margin: 0 !important;
    }

    .stApp::before { display: none !important; }

    .stButton, button,
    [data-testid="stSelectbox"],
    [data-testid="stDateInput"],
    [data-testid="stSlider"],
    .stDownloadButton,
    [data-testid="stCheckbox"],
    .stRadio {
        display: none !important;
    }

    body, .stApp {
        background: white !important;
    }

    [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-wrap: wrap !important;
        gap: 0.5rem !important;
    }

    [data-testid="column"] {
        width: 48% !important;
        max-width: 48% !important;
        flex: 0 0 48% !important;
        margin-bottom: 0.5rem !important;
    }

    * { box-shadow: none !important; }

    body {
        color: #000 !important;
        font-size: 9pt !important;
        line-height: 1.3 !important;
    }

    h1 { font-size: 18pt !important; margin: 0 !important; }
    h2 { font-size: 14pt !important; color: #000 !important; page-break-before: auto; margin: 10px 0 5px 0 !important; }
    h3 { font-size: 12pt !important; color: #000 !important; margin: 8px 0 4px 0 !important; }

    .stDataFrame, [data-testid="stMetric"], .element-container {
        page-break-inside: avoid;
    }

    table {
        width: 100% !important;
        max-width: 100% !important;
        font-size: 8pt !important;
        page-break-inside: avoid;
        table-layout: fixed !important;
    }

    td, th {
        padding: 3px !important;
        word-wrap: break-word !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }

    .js-plotly-plot {
        max-width: 100% !important;
        max-height: 300px !important;
        page-break-inside: avoid;
    }

    .js-plotly-plot .plotly {
        width: 100% !important;
    }

    [data-testid="stMetricValue"] { font-size: 14pt !important; color: #000 !important; }
    [data-testid="stMetricLabel"] { font-size: 8pt !important; color: #333 !important; }

    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
    }

    .stInfo, .stWarning, .stSuccess {
        border: 1px solid #ccc !important;
        background: #f9f9f9 !important;
        padding: 8px !important;
        font-size: 9pt !important;
    }

    hr { margin: 10px 0 !important; }

    [data-testid="stDataFrame"] td:first-child {
        max-width: 150px !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }

    .stCaption { font-size: 8pt !important; color: #666 !important; }

    .tmb-masthead h1 { font-size: 24pt !important; }
    .tmb-rule-double {
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
    }
}
</style>
"""
