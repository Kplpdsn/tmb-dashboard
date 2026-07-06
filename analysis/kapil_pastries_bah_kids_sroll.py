"""Pull last 4 months of Pastries + BAH Kids S/Roll sales."""

import sys
sys.path.insert(0, r"D:\TMB 2.0")
import warnings; warnings.filterwarnings("ignore")
import json
import pandas as pd
from datetime import date
from services.gdrive import get_service, list_files_in_folder, download_file
from services.data_processor import (
    extract_date_from_filename, clean_product_name, get_bakery_category,
)
from config import TMB_SALES_FOLDER_ID

START, END = date(2026, 2, 1), date(2026, 5, 28)

service, err = get_service()
if err:
    raise RuntimeError(err)

files = list_files_in_folder(service, TMB_SALES_FOLDER_ID, file_pattern=r"\d{8}")
wanted = []
dates_present = set()
for f in files:
    d = extract_date_from_filename(f["name"])
    if d and START <= d.date() <= END:
        wanted.append(f)
        dates_present.add(d.date())

# Check for missing dates
all_expected = set()
cur = START
while cur <= END:
    all_expected.add(cur)
    cur = cur.replace(day=cur.day + 1) if cur.day < 28 else (
        date(cur.year, cur.month + 1, 1) if cur.month < 12 else date(cur.year + 1, 1, 1)
    )

# Simpler missing-date check
all_expected = set()
from datetime import timedelta
d = START
while d <= END:
    all_expected.add(d)
    d += timedelta(days=1)

missing = sorted(all_expected - dates_present)
if missing:
    print(f"MISSING DATES: {len(missing)} days")
    for m in missing[:20]:
        print(f"  {m}")
    if len(missing) > 20:
        print(f"  ... and {len(missing) - 20} more")

print(f"Files to load: {len(wanted)}")

frames = []
for i, f in enumerate(wanted):
    buf = download_file(service, f["id"])
    if buf is None:
        continue
    raw = pd.read_excel(buf)
    if "Saledate" in raw.columns:
        raw["Date"] = pd.to_datetime(raw["Saledate"])
    else:
        raw["Date"] = extract_date_from_filename(f["name"])
    frames.append(raw)
    if (i + 1) % 20 == 0:
        print(f"  loaded {i+1}/{len(wanted)}")

df = pd.concat(frames, ignore_index=True)
df = df[df["Description"].notna()]
df["Description"] = df["Description"].apply(clean_product_name)
df["Revenue"]  = pd.to_numeric(df["ExtendedNetAmount"], errors="coerce").fillna(0)
df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce").fillna(0)
df["Category"] = df["Description"].apply(get_bakery_category)
df = df[df["Category"] != "Ignore"]

# Save raw to parquet for fast follow-up
df.to_parquet(r"D:\TMB 2.0\analysis\kapil_4mo_data.parquet")
print(f"\nTotal rows: {len(df):,}")
print(f"Date range: {df['Date'].min()} -> {df['Date'].max()}")
print(f"Unique dates: {df['Date'].dt.date.nunique()}")

# === ANALYSIS ===

# 1. PASTRIES
pastries = df[df["Category"] == "Pastries"].copy()
print(f"\n=== PASTRIES ===")
print(f"Rows: {len(pastries):,}")
print(f"Total revenue: ${pastries['Revenue'].sum():,.2f}")
print(f"Total qty: {pastries['Quantity'].sum():,.0f}")
print(f"\nUnique pastry products:")
print(pastries.groupby("Description").agg(
    qty=("Quantity", "sum"),
    revenue=("Revenue", "sum"),
).sort_values("revenue", ascending=False))

# 2. BAH KIDS S/ROLL — search for variants
print(f"\n=== Searching for BAH kids sausage roll variants ===")
bah_all = df[df["Description"].str.upper().str.contains("BAH", na=False)]
print("All BAH products in data:")
print(bah_all["Description"].value_counts())

print(f"\nProducts with KIDS:")
kids = df[df["Description"].str.upper().str.contains("KID", na=False)]
print(kids["Description"].value_counts())

print(f"\nProducts with S/ROLL or SROLL or SAUSAGE:")
sroll = df[df["Description"].str.upper().str.contains("S/ROLL|SROLL|SAUSAGE", na=False, regex=True)]
print(sroll["Description"].value_counts())
