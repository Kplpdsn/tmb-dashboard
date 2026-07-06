"""Application configuration and constants."""

from datetime import datetime

# Google Drive
TMB_SALES_FOLDER_ID = "1ZvxkD2PGmzx8nTMT9K5w4w5N70IzNe8O"
GDRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
SERVICE_ACCOUNT_FILE = "service_account.json"

# Data
FIRST_SALE_DATE = datetime(2024, 5, 29).date()
REQUIRED_COLUMNS = {"Description", "ExtendedNetAmount", "Quantity", "Hour_ID", "Reference2", "Till"}

# Basket size bins
BASKET_VALUE_BINS = [0, 15, 30, 50, 100, 1000]
BASKET_VALUE_LABELS = ["$0-15", "$15-30", "$30-50", "$50-100", "$100+"]

BASKET_ITEM_BINS = [0, 1, 3, 5, 10, 1000]
BASKET_ITEM_LABELS = ["1", "2-3", "4-5", "6-10", "10+"]

# Chart colors ("artisan ledger" palette — see styles.py)
CHART_PRIMARY = "#6F7A64"    # sage
CHART_SECONDARY = "#98A186"  # light sage
CHART_ACCENT = "#B4642A"     # burnt caramel
CHART_HIGHLIGHT = "#48513E"  # deep sage
CHART_POSITIVE = "#4C7A46"
CHART_NEGATIVE = "#AC3B2A"
CHART_NEUTRAL = "#5E6556"

# PDF colors
PDF_HEADER_BG = "#23281F"
PDF_TEXT_PRIMARY = "#23281F"
PDF_BORDER = "#E4DCCC"
PDF_POSITIVE = "#4C7A46"
PDF_NEGATIVE = "#AC3B2A"

# Pie chart color palette (muted, print-like)
PIE_COLORS = [
    "#48513E", "#B4642A", "#8C9478", "#D9B380",
    "#5E6556", "#A45C48", "#71808C", "#C2B49A",
]

# Semantic colors for UI
COLOR_POSITIVE = "#4C7A46"
COLOR_NEGATIVE = "#AC3B2A"

# Average Day analysis
DAY_NAMES_ORDERED = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
AVERAGE_DAY_ROLLING_WINDOW = 4  # weeks for trend moving average
CHART_CONFIDENCE_BAND = "rgba(111, 122, 100, 0.18)"  # std deviation band fill

# Insight engine thresholds
INSIGHT_TREND_MIN_DAYS = 21       # need 21+ days for trend insights
INSIGHT_SLOW_MOVER_MIN_DAYS = 7   # need 7+ days for slow mover callout
INSIGHT_SLOW_MOVER_THRESHOLD = 5  # products averaging < $5/day are "slow"
INSIGHT_TOP_PRODUCTS = 8          # number of products in "What's Selling"
INSIGHT_WEEKLY_AGGREGATE_DAYS = 15  # 15+ days → aggregate to weekly bars

# Cache TTL (seconds)
FILE_LIST_CACHE_TTL = 600   # 10 minutes
DATA_CACHE_TTL = 3600       # 1 hour
