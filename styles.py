"""CSS styles for the Streamlit application."""

MAIN_CSS = """
<style>
/* ========================================
   PROFESSIONAL ANALYTICS COLOR PALETTE
   ======================================== */

:root {
    --bg-primary: #FFFFFF;
    --bg-secondary: #F5F5F5;
    --bg-card: #FFFFFF;
    --border-color: #E5E7EB;
    --text-primary: #1F2933;
    --text-secondary: #6B7280;
    --text-muted: #9CA3AF;
    --color-positive: #2E7D32;
    --color-negative: #C62828;
    --color-neutral: #6B7280;
    --accent-color: #4B5563;
    --accent-hover: #374151;
    --bg-info: #F9FAFB;
}

.stApp {
    background: var(--bg-primary);
}

/* Header */
.main-header {
    background: var(--accent-color);
    padding: 30px 40px;
    border-radius: 0;
    margin-bottom: 0;
    box-shadow: none;
    border-bottom: 2px solid var(--border-color);
}

.main-title {
    font-size: 32px;
    font-weight: 700;
    color: #FFFFFF;
    margin: 0;
    text-shadow: none;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    letter-spacing: -0.5px;
}

.main-subtitle {
    font-size: 14px;
    color: #D1D5DB;
    margin: 5px 0 0 0;
    font-weight: 400;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}

/* Metrics */
[data-testid="stMetricValue"] {
    font-size: 28px;
    color: var(--text-primary);
    font-weight: 700;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

[data-testid="stMetricLabel"] {
    font-size: 11px;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 600;
}

[data-testid="stMetricDelta"] > div {
    font-weight: 600;
}

/* Buttons */
.stButton>button {
    background: var(--accent-color);
    color: white;
    border: none;
    border-radius: 6px;
    padding: 10px 20px;
    font-weight: 600;
    letter-spacing: 0;
    transition: background 0.2s ease;
    box-shadow: none;
}

.stButton>button:hover {
    background: var(--accent-hover);
    box-shadow: none;
    transform: none;
}

/* Section Headers */
h1, h2, h3, h4 {
    color: var(--text-primary);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-weight: 700;
    letter-spacing: -0.5px;
}

h2 { font-size: 24px; }
h3 { font-size: 18px; }

div[data-testid="stHorizontalBlock"] {
    gap: 1rem;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: var(--bg-secondary);
}

[data-testid="stSidebar"] > div:first-child {
    color: var(--text-primary);
}

[data-testid="stSidebar"] label {
    color: var(--text-primary) !important;
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
    color: var(--text-primary) !important;
}

[data-testid="stSidebar"] input {
    color: var(--text-primary) !important;
    background-color: var(--bg-primary) !important;
}

[data-testid="stSidebar"] [data-baseweb="select"] {
    color: var(--text-primary) !important;
}

[data-testid="stSidebar"] [data-baseweb="select"] > div {
    color: var(--text-primary) !important;
    background-color: var(--bg-primary) !important;
}

/* Info/Warning/Error Boxes */
.stInfo {
    background-color: var(--bg-info);
    border-left: 3px solid var(--accent-color);
}

.stSuccess {
    background-color: var(--bg-info);
    border-left: 3px solid var(--color-positive);
}

.stWarning {
    background-color: var(--bg-info);
    border-left: 3px solid #F59E0B;
}

.stError {
    background-color: var(--bg-info);
    border-left: 3px solid var(--color-negative);
}

/* Metric Deltas */
[data-testid="stMetricDelta"] svg {
    fill: currentColor;
}

[data-testid="stMetricDelta"][data-trend="positive"] {
    color: var(--color-positive) !important;
}

[data-testid="stMetricDelta"][data-trend="negative"] {
    color: var(--color-negative) !important;
}

/* Inputs */
.stSelectbox, .stDateInput {
    border-radius: 4px;
}

hr {
    border-color: var(--border-color);
}

/* Download Button */
.stDownloadButton>button {
    background: var(--accent-color);
    color: white;
    font-weight: 600;
}

.stDownloadButton>button:hover {
    background: var(--accent-hover);
    color: white;
}

.stCaption {
    color: var(--text-secondary) !important;
    font-style: normal;
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

    .stButton, button,
    [data-testid="stSelectbox"],
    [data-testid="stDateInput"],
    [data-testid="stSlider"],
    .stDownloadButton,
    [data-testid="stCheckbox"] {
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

    .main-header {
        background: #4B5563 !important;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
        padding: 15px 20px !important;
        margin-bottom: 10px !important;
    }

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

    .stRadio { display: none !important; }

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

    .main-title {
        font-size: 24pt !important;
        color: white !important;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
    }

    .main-subtitle {
        font-size: 11pt !important;
        color: #D4A574 !important;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
    }
}
</style>
"""
