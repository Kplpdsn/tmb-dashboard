"""Data loading, cleaning, category mapping, and processing."""

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
        except ValueError:
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
    """Load category mappings from category_config.csv."""
    base = os.path.dirname(os.path.dirname(__file__))
    csv_path = os.path.join(base, "category_config.csv")
    try:
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            return dict(zip(df["Product"].str.strip().str.upper(), df["Category"].str.strip()))
        st.warning("category_config.csv not found. Using keyword fallback only.")
        return {}
    except (OSError, KeyError, pd.errors.ParserError) as e:
        st.error(f"Error loading category config: {e}")
        return {}


def get_bakery_category(item):
    """Categorize bakery items using CSV config + keyword fallback."""
    item = str(item).upper().strip()
    if not item or item in ("NAN", "BLANK"):
        return "Ignore"

    # Exact match from config
    category_map = _load_category_config()
    if item in category_map:
        return category_map[item]

    # Keyword fallback for products not yet in CSV
    if "BAH" in item or "BAKE AT HOME" in item or "S/ROLL" in item:
        return "Bake at Home"
    if "SOURDOUGH" in item or "BATARD" in item or "BAGUETTE" in item or "S/DOUGH" in item:
        return "XL Loaves" if "XL" in item else "Standard Loaves"
    if "CROISSANT" in item or "DANISH" in item or "ESCARGOT" in item or "SCROLL" in item:
        return "Pastries"
    if "BUN" in item or "ROLL" in item:
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
            f"({start_date.strftime('%d %b')} - {end_date.strftime('%d %b %Y')})\n"
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
        f"({start_date.strftime('%d %b')} - {end_date.strftime('%d %b %Y')})"
    )
    return filtered_files, None


def _validate_specific_dates(files, specific_dates):
    """Validate files exist for each requested specific date (non-continuous).

    Returns (filtered_files, error_msg).
    """
    file_date_map: dict[str, list] = {}
    for f in files:
        file_date = extract_date_from_filename(f["name"])
        if not file_date:
            continue
        date_key = file_date.date() if hasattr(file_date, "date") else file_date
        file_date_map.setdefault(date_key, []).append(f)

    filtered_files = []
    missing = []
    duplicates = {}

    for dt in specific_dates:
        if dt not in file_date_map:
            missing.append(dt.strftime("%d %b %Y"))
        else:
            file_list = file_date_map[dt]
            if len(file_list) > 1:
                duplicates[dt.strftime("%Y-%m-%d")] = [f["name"] for f in file_list]
            filtered_files.extend(file_list)

    if missing:
        return pd.DataFrame(), (
            f"**DATA INCOMPLETE - CANNOT PROCEED**\n\n"
            f"**Requested:** {len(specific_dates)} dates\n"
            f"**Missing dates:** {', '.join(missing)}\n\n"
            f"Check if files exist in Google Drive folder."
        )

    if duplicates:
        dup_lines = "\n".join(
            f"- **{d}**: {len(fl)} files - {', '.join(fl)}"
            for d, fl in duplicates.items()
        )
        return pd.DataFrame(), (
            f"**DUPLICATE FILES DETECTED - CANNOT PROCEED**\n\n"
            f"**Duplicate dates:**\n{dup_lines}\n\n"
            f"Remove duplicate files from Google Drive folder."
        )

    date_strs = [dt.strftime("%d %b") for dt in specific_dates]
    st.success(f"**Data Complete:** All {len(specific_dates)} files found ({', '.join(date_strs)})")
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


def process_gdrive_files(service, folder_id, start_date=None, end_date=None, specific_dates=None):
    """Download and process files from Google Drive.

    Supports two modes:
    - Range mode: start_date + end_date (continuous, all dates must exist)
    - Specific mode: specific_dates list (non-continuous, only listed dates loaded)
    """
    files = list_files_in_folder(service, folder_id, file_pattern=r"\d{8}")
    if not files:
        return pd.DataFrame(), "No files found in the folder"

    # Validate dates
    if specific_dates:
        files, error = _validate_specific_dates(files, specific_dates)
        if error:
            return pd.DataFrame(), error
        # Use min/max for downstream date filtering in _build_dataframe
        start_date = pd.Timestamp(min(specific_dates))
        end_date = pd.Timestamp(max(specific_dates))
    elif start_date or end_date:
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
            # Broad: one malformed file must not abort the whole batch, and
            # openpyxl/xlrd raise a wide range of types on bad workbooks.
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
        # Broad for the same reason as load_data: skip the bad upload, keep the rest.
        except Exception as e:
            st.warning(f"Could not process {file.name}: {e}")

    if not all_data:
        return pd.DataFrame()

    result, _ = _build_dataframe(all_data, None, None)
    return result
