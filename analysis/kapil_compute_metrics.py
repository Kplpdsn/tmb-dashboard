"""Compute monthly + weekly metrics for Pastries and KIDS BEEF VEGE S/ROLL."""

import json
import pandas as pd
import numpy as np

df = pd.read_parquet(r"D:\TMB 2.0\analysis\kapil_4mo_data.parquet")
df["Date"] = pd.to_datetime(df["Date"])
df["Day"] = df["Date"].dt.normalize()
df["Month"] = df["Date"].dt.to_period("M").astype(str)
df["DOW"] = df["Date"].dt.day_name()
df["Hour"] = pd.to_numeric(df.get("Hour_ID"), errors="coerce")

out = {}

# ============================================================
# 1. ALL PASTRIES
# ============================================================
past = df[df["Category"] == "Pastries"].copy()

out["pastries"] = {}
out["pastries"]["totals"] = {
    "revenue": float(past["Revenue"].sum()),
    "qty": int(past["Quantity"].sum()),
    "transactions": int(len(past)),
    "avg_unit_price": float(past["Revenue"].sum() / past["Quantity"].sum()),
    "days_sold": int(past["Day"].nunique()),
    "avg_daily_revenue": float(past["Revenue"].sum() / past["Day"].nunique()),
    "avg_daily_qty": float(past["Quantity"].sum() / past["Day"].nunique()),
}

# Monthly breakdown
monthly = past.groupby("Month").agg(
    revenue=("Revenue", "sum"),
    qty=("Quantity", "sum"),
    days=("Day", "nunique"),
).reset_index()
monthly["avg_daily_revenue"] = monthly["revenue"] / monthly["days"]
monthly["avg_daily_qty"] = monthly["qty"] / monthly["days"]
monthly["avg_unit_price"] = monthly["revenue"] / monthly["qty"]
out["pastries"]["monthly"] = monthly.to_dict(orient="records")

# Month-over-month change
monthly_sorted = monthly.sort_values("Month").reset_index(drop=True)
monthly_sorted["revenue_mom_pct"] = monthly_sorted["revenue"].pct_change() * 100
monthly_sorted["qty_mom_pct"] = monthly_sorted["qty"].pct_change() * 100
monthly_sorted["avg_daily_rev_mom_pct"] = monthly_sorted["avg_daily_revenue"].pct_change() * 100
out["pastries"]["monthly_with_change"] = monthly_sorted.fillna(0).to_dict(orient="records")

# Product breakdown
products = past.groupby("Description").agg(
    revenue=("Revenue", "sum"),
    qty=("Quantity", "sum"),
).reset_index()
products["share_revenue_pct"] = products["revenue"] / products["revenue"].sum() * 100
products["avg_unit_price"] = products["revenue"] / products["qty"]
products = products.sort_values("revenue", ascending=False)
out["pastries"]["products"] = products.to_dict(orient="records")

# Product by month (qty)
prod_month_qty = past.pivot_table(
    index="Description", columns="Month", values="Quantity", aggfunc="sum", fill_value=0
).round(0).astype(int)
prod_month_qty["Total"] = prod_month_qty.sum(axis=1)
prod_month_qty = prod_month_qty.sort_values("Total", ascending=False)
out["pastries"]["product_month_qty"] = prod_month_qty.reset_index().to_dict(orient="records")

# Product by month (revenue)
prod_month_rev = past.pivot_table(
    index="Description", columns="Month", values="Revenue", aggfunc="sum", fill_value=0
).round(2)
prod_month_rev["Total"] = prod_month_rev.sum(axis=1).round(2)
prod_month_rev = prod_month_rev.sort_values("Total", ascending=False)
out["pastries"]["product_month_rev"] = prod_month_rev.reset_index().to_dict(orient="records")

# Day-of-week pattern
dow = past.groupby("DOW").agg(
    revenue=("Revenue", "sum"),
    qty=("Quantity", "sum"),
    days=("Day", "nunique"),
).reset_index()
dow["avg_revenue"] = dow["revenue"] / dow["days"]
dow["avg_qty"] = dow["qty"] / dow["days"]
dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
dow["DOW"] = pd.Categorical(dow["DOW"], categories=dow_order, ordered=True)
dow = dow.sort_values("DOW")
out["pastries"]["dow"] = dow.to_dict(orient="records")

# Hour-of-day distribution
hr = past.dropna(subset=["Hour"]).groupby(past["Hour"].astype(int)).agg(
    revenue=("Revenue", "sum"),
    qty=("Quantity", "sum"),
).reset_index().rename(columns={"Hour": "Hour"})
hr.columns = ["Hour", "revenue", "qty"]
out["pastries"]["hour"] = hr.to_dict(orient="records")

# Daily revenue series for trend chart
daily = past.groupby("Day").agg(revenue=("Revenue", "sum"), qty=("Quantity", "sum")).reset_index()
daily["Day"] = daily["Day"].dt.strftime("%Y-%m-%d")
out["pastries"]["daily"] = daily.to_dict(orient="records")

# ============================================================
# 2. BAH KIDS S/ROLL = KIDS BEEF VEGE S/ROLL
# ============================================================
kids = df[df["Description"] == "KIDS BEEF VEGE S/ROLL"].copy()

out["kids_sroll"] = {}
out["kids_sroll"]["product_name"] = "KIDS BEEF VEGE S/ROLL"
out["kids_sroll"]["category"] = "Bake at Home"

out["kids_sroll"]["totals"] = {
    "revenue": float(kids["Revenue"].sum()),
    "qty": int(kids["Quantity"].sum()),
    "transactions": int(len(kids)),
    "avg_unit_price": float(kids["Revenue"].sum() / kids["Quantity"].sum()) if kids["Quantity"].sum() else 0,
    "days_sold": int(kids["Day"].nunique()),
    "avg_daily_revenue_when_sold": float(kids["Revenue"].sum() / kids["Day"].nunique()) if kids["Day"].nunique() else 0,
    "avg_qty_per_transaction": float(kids["Quantity"].sum() / len(kids)) if len(kids) else 0,
}

# Monthly
k_monthly = kids.groupby("Month").agg(
    revenue=("Revenue", "sum"),
    qty=("Quantity", "sum"),
    days_sold=("Day", "nunique"),
    transactions=("Description", "count"),
).reset_index()
k_monthly["avg_unit_price"] = k_monthly["revenue"] / k_monthly["qty"]
k_monthly = k_monthly.sort_values("Month").reset_index(drop=True)
k_monthly["revenue_mom_pct"] = k_monthly["revenue"].pct_change() * 100
k_monthly["qty_mom_pct"] = k_monthly["qty"].pct_change() * 100
out["kids_sroll"]["monthly"] = k_monthly.fillna(0).to_dict(orient="records")

# Day-of-week
k_dow = kids.groupby("DOW").agg(
    qty=("Quantity", "sum"),
    revenue=("Revenue", "sum"),
    transactions=("Description", "count"),
).reset_index()
k_dow["DOW"] = pd.Categorical(k_dow["DOW"], categories=dow_order, ordered=True)
k_dow = k_dow.sort_values("DOW")
out["kids_sroll"]["dow"] = k_dow.to_dict(orient="records")

# Daily trend
k_daily = kids.groupby("Day").agg(qty=("Quantity", "sum"), revenue=("Revenue", "sum")).reset_index()
k_daily["Day"] = k_daily["Day"].dt.strftime("%Y-%m-%d")
out["kids_sroll"]["daily"] = k_daily.to_dict(orient="records")

# ============================================================
# Range metadata
# ============================================================
out["meta"] = {
    "start": "2026-02-01",
    "end": "2026-05-27",
    "days_in_range": int(df["Day"].nunique()),
    "generated": "2026-05-28",
}

# Convert numpy types
def to_native(obj):
    if isinstance(obj, dict):
        return {k: to_native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_native(x) for x in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj) if not np.isnan(obj) else 0.0
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, pd.Timestamp):
        return obj.strftime("%Y-%m-%d")
    return obj

out = to_native(out)

with open(r"D:\TMB 2.0\analysis\kapil_metrics.json", "w") as f:
    json.dump(out, f, indent=2, default=str)

print("=" * 60)
print("PASTRIES OVERVIEW")
print("=" * 60)
print(f"Total revenue: ${out['pastries']['totals']['revenue']:,.2f}")
print(f"Total units:   {out['pastries']['totals']['qty']:,}")
print(f"Days sold:     {out['pastries']['totals']['days_sold']}")
print(f"Avg unit $:    ${out['pastries']['totals']['avg_unit_price']:.2f}")
print(f"Avg daily $:   ${out['pastries']['totals']['avg_daily_revenue']:,.2f}")

print("\nMONTHLY (Pastries):")
for m in out["pastries"]["monthly_with_change"]:
    print(f"  {m['Month']}: ${m['revenue']:>10,.2f}  qty={m['qty']:>5}  days={m['days']}  "
          f"daily=${m['avg_daily_revenue']:.0f}  MoM rev={m['revenue_mom_pct']:+.1f}%")

print("\nPRODUCTS (Pastries) ranked:")
for p in out["pastries"]["products"]:
    print(f"  {p['Description']:<24} ${p['revenue']:>9,.2f}  qty={p['qty']:>5.0f}  "
          f"share={p['share_revenue_pct']:.1f}%  unit=${p['avg_unit_price']:.2f}")

print("\n" + "=" * 60)
print("KIDS BEEF VEGE S/ROLL")
print("=" * 60)
print(f"Total revenue: ${out['kids_sroll']['totals']['revenue']:,.2f}")
print(f"Total units:   {out['kids_sroll']['totals']['qty']:,}")
print(f"Transactions:  {out['kids_sroll']['totals']['transactions']}")
print(f"Days sold:     {out['kids_sroll']['totals']['days_sold']}")
print(f"Avg unit $:    ${out['kids_sroll']['totals']['avg_unit_price']:.2f}")
print(f"Avg qty/txn:   {out['kids_sroll']['totals']['avg_qty_per_transaction']:.1f}")

print("\nMONTHLY (KIDS BEEF VEGE S/ROLL):")
for m in out["kids_sroll"]["monthly"]:
    print(f"  {m['Month']}: ${m['revenue']:>7,.2f}  qty={m['qty']:>4}  "
          f"days={m['days_sold']}  txn={m['transactions']}  MoM={m['revenue_mom_pct']:+.1f}%")

print(f"\nWrote: D:\\TMB 2.0\\analysis\\kapil_metrics.json")
