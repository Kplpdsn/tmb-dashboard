"""Data loading, cleaning, category mapping, and processing."""

import json
import os
import re
from datetime import timedelta

import pandas as pd
import streamlit as st

from config import REQUIRED_COLUMNS
from services.gdrive import list_files_in_folder, download_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_date_from_filename(filename):
    """Extract date from filename containing YYYYMMDD pattern."""
    match = re.search(r"(\d{8})", filename)
    if match:
        try:
            return pd.to_datetime(match.group(1), format="%Y%m%d")
        except Exception:
            return None
    return None


def clean_product_name(name):
    """Remove TMB prefix from product names."""
    name = str(name).strip()
    if name.upper().startswith("TMB "):
        name = name[4:]
    return name.strip()


# ---------------------------------------------------------------------------
# Category mapping
# ---------------------------------------------------------------------------

def _load_category_config():
    """Load category mappings from CSV (preferred) or JSON fallback."""
    base = os.path.dirname(os.path.dirname(__file__))
    try:
        csv_path = os.path.join(base, "category_config.csv")
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            return dict(zip(df["Product"].str.strip(), df["Category"].str.strip()))
        json_path = os.path.join(base, "category_config.json")
        if os.path.exists(json_path):
            with open(json_path, "r") as f:
                return json.load(f)
        st.warning("No category config found. Using keyword fallback only.")
        return {}
    except Exception as e:
        st.error(f"Error loading category config: {e}")
        return {}


@st.cache_data
def get_category_mappings():
    """Cached category mappings."""
    return _load_category_config()


def get_bakery_category(item):
    """Categorize bakery items using config file + keyword fallback."""
    item = str(item).upper().strip()
    if not item or item in ("NAN", "BLANK"):
        return "Ignore"

    # Exact match from config
    category_map = get_category_mappings()
    if item in category_map:
        return category_map[item]

    # Keyword fallback
    if any(k in item for k in ("BAKE AT HOME", "BAH", "S/ROLL", "CHEESY VEG", "SHARE PIE")):
        return "Bake at Home"
    if any(k in item for k in ("STOLLEN", "SALT & PEPPER BAGUETTE", "SALT AND PEPPER BAGUETTE")):
        return "Weekend Special"
    if any(k in item for k in ("SOURDOUGH", "BATARD", "BAGUETTE", "S/DOUGH")):
        return "XL Loaves" if "XL" in item else "Standard Loaves"
    if any(k in item for k in ("DANISH", "CROISSANT", "SCROLL", "PASTRY", "ESCARGOT")):
        return "Pastries"
    if any(k in item for k in ("FMT", "GINGER SNAP", "TART")):
        return "FMT"
    if any(k in item for k in ("COOKIE", "GRANOLA", "COFFEE", "REDBRICK", "HONEY", "BEYOND BREAD", "BAKERS OVEN")) or "B&B" in item:
        return "Retail Items"
    if any(k in item for k in ("BUN", "ROLL")):
        return "Buns & Rolls"
    return "Other"


# ---------------------------------------------------------------------------
# Data processing
# ---------------------------------------------------------------------------

def _validate_date_range(files, start_date, end_date):
    """Validate files cover the expected date range. Returns (filtered_files, error_msg)."""
    filtered_files = []
    file_dates_found = {}

    for f in files:
        file_date = extract_date_from_filename(f["name"])
        if not file_date:
            continue
        if start_date and file_date < start_date:
            continue
        if end_date and file_date > end_date:
            continue
        filtered_files.append(f)
        date_key = file_date.strftime("%Y-%m-%d")
        file_dates_found.setdefault(date_key, []).append(f["name"])

    if not (start_date and end_date):
        return filtered_files, None

    expected_days = (end_date - start_date).days + 1
    expected_dates = []
    current = start_date
    while current <= end_date:
        expected_dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)

    missing = [d for d in expected_dates if d not in file_dates_found]
    duplicates = {d: flist for d, flist in file_dates_found.items() if len(flist) > 1}

    if missing:
        return pd.DataFrame(), (
            f"**DATA INCOMPLETE - CANNOT PROCEED**\n\n"
            f"**Expected:** {expected_days} files "
            f"({start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')})\n"
            f"**Found:** {len(file_dates_found)} files\n"
            f"**Missing dates:** {', '.join(missing)}\n\n"
            f"Check if files exist in Google Drive folder or select a different date range."
        )

    if duplicates:
        dup_lines = "\n".join(
            f"- **{d}**: {len(fl)} files - {', '.join(fl)}" for d, fl in duplicates.items()
        )
        return pd.DataFrame(), (
            f"**DUPLICATE FILES DETECTED - CANNOT PROCEED**\n\n"
            f"**Duplicate dates:**\n{dup_lines}\n\n"
            f"Remove duplicate files from Google Drive folder."
        )

    st.success(
        f"**Data Complete:** All {expected_days} files found "
        f"({start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')})"
    )
    return filtered_files, None


def _build_dataframe(all_data, start_date, end_date):
    """Combine raw dataframes, clean, and enrich."""
    combined = pd.concat(all_data, ignore_index=True)

    # Validate required columns
    missing_cols = REQUIRED_COLUMNS - set(combined.columns)
    if missing_cols:
        return pd.DataFrame(), f"Missing required columns: {', '.join(missing_cols)}"

    combined = combined[combined["Description"].notna()]
    combined["Description"] = combined["Description"].apply(clean_product_name)
    combined["Revenue"] = pd.to_numeric(combined["ExtendedNetAmount"], errors="coerce").fillna(0)
    combined["Quantity"] = pd.to_numeric(combined["Quantity"], errors="coerce").fillna(0)
    combined["Category"] = combined["Description"].apply(get_bakery_category)
    combined = combined[combined["Category"] != "Ignore"]
    combined["Hour"] = pd.to_numeric(combined["Hour_ID"], errors="coerce").fillna(0).astype(int)

    # Filter to exact date range
    if start_date is not None and end_date is not None:
        end_dt = pd.Timestamp(end_date) + pd.Timedelta(days=1)
        combined = combined[combined["Date"].between(pd.Timestamp(start_date), end_dt, inclusive="left")]
    elif start_date is not None:
        combined = combined[combined["Date"] >= pd.Timestamp(start_date)]
    elif end_date is not None:
        end_dt = pd.Timestamp(end_date) + pd.Timedelta(days=1)
        combined = combined[combined["Date"] < end_dt]

    # Time period columns
    combined["Week"] = combined["Date"].dt.isocalendar().week
    combined["Month"] = combined["Date"].dt.month
    combined["Year"] = combined["Date"].dt.year
    combined["WeekYear"] = combined["Year"].astype(str) + "-W" + combined["Week"].astype(str).str.zfill(2)
    combined["MonthYear"] = combined["Date"].dt.strftime("%Y-%m")
    combined["DayName"] = combined["Date"].dt.day_name()

    # Basket ID
    combined["Basket_ID"] = (
        combined["Reference2"].fillna("X").astype(str)
        + "_"
        + combined["Till"].fillna("0").astype(str)
    )
    return combined, None


def get_available_dates(service, folder_id):
    """Return sorted list of dates that have data files on Drive.

    Uses the already-cached list_files_in_folder so this is lightweight.
    """
    files = list_files_in_folder(service, folder_id, file_pattern=r"\d{8}")
    dates = []
    for f in files:
        dt = extract_date_from_filename(f["name"])
        if dt:
            dates.append(dt.date())
    return sorted(set(dates))


def process_gdrive_files(service, folder_id, start_date=None, end_date=None):
    """Download and process files from Google Drive within the given date range."""
    files = list_files_in_folder(service, folder_id, file_pattern=r"\d{8}")
    if not files:
        return pd.DataFrame(), "No files found in the folder"

    # Validate date range
    if start_date or end_date:
        files, error = _validate_date_range(files, start_date, end_date)
        if error:
            return pd.DataFrame(), error

    if not files:
        return pd.DataFrame(), "No files found in the selected date range"

    # Download and read each file
    all_data = []
    progress = st.progress(0)
    status = st.empty()

    for idx, f in enumerate(files):
        status.text(f"Loading {f['name']}... ({idx + 1}/{len(files)})")
        buf = download_file(service, f["id"])
        if buf:
            try:
                df = pd.read_excel(buf)
                file_date = extract_date_from_filename(f["name"])
                if file_date:
                    df["FileDate"] = file_date
                if "Saledate" in df.columns:
                    df["Date"] = pd.to_datetime(df["Saledate"])
                elif file_date:
                    df["Date"] = file_date
                else:
                    df["Date"] = pd.NaT
                all_data.append(df)
            except Exception as e:
                st.warning(f"Could not process {f['name']}: {e}")
        progress.progress((idx + 1) / len(files))

    progress.empty()
    status.empty()

    if not all_data:
        return pd.DataFrame(), "Could not process any files"

    return _build_dataframe(all_data, start_date, end_date)


def process_uploaded_files(uploaded_files):
    """Process manually uploaded files (fallback when Drive is unavailable)."""
    if not uploaded_files:
        return pd.DataFrame()

    all_data = []
    for file in uploaded_files:
        try:
            if file.name.endswith(".csv"):
                df = pd.read_csv(file, encoding="cp1252")
            else:
                df = pd.read_excel(file)
            file_date = extract_date_from_filename(file.name)
            if file_date:
                df["FileDate"] = file_date
            if "Saledate" in df.columns:
                df["Date"] = pd.to_datetime(df["Saledate"])
            elif file_date:
                df["Date"] = file_date
            else:
                df["Date"] = pd.NaT
            all_data.append(df)
        except Exception as e:
            st.warning(f"Could not process {file.name}: {e}")

    if not all_data:
        return pd.DataFrame()

    result, _ = _build_dataframe(all_data, None, None)
    return result
