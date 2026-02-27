"""Tests for reports/excel_export.py."""

import openpyxl
from io import BytesIO

import pandas as pd
import pytest

from reports.excel_export import _compute_week_ranges, _build_weekly_product_data, generate_excel


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

def _make_test_df():
    """Build a minimal DataFrame spanning 2 weeks for testing."""
    rows = []
    # Week 1: Jan 28-Feb 1 2026 (Wed-Sun) — 2 products
    for date in pd.date_range("2026-01-28", "2026-02-01"):
        rows.append({"Date": date, "Description": "HOUSE SOURDOUGH", "Category": "Standard Loaves",
                      "Revenue": 100, "Quantity": 10, "Hour": 9, "Basket_ID": "B1"})
        rows.append({"Date": date, "Description": "CROISSANT PLAIN", "Category": "Pastries",
                      "Revenue": 50, "Quantity": 15, "Hour": 9, "Basket_ID": "B2"})
    # Week 2: Feb 2-5 2026 (Mon-Thu) — same 2 products
    for date in pd.date_range("2026-02-02", "2026-02-05"):
        rows.append({"Date": date, "Description": "HOUSE SOURDOUGH", "Category": "Standard Loaves",
                      "Revenue": 120, "Quantity": 12, "Hour": 9, "Basket_ID": "B3"})
        rows.append({"Date": date, "Description": "CROISSANT PLAIN", "Category": "Pastries",
                      "Revenue": 60, "Quantity": 18, "Hour": 9, "Basket_ID": "B4"})
    return pd.DataFrame(rows)


def _open_wb(buf):
    buf.seek(0)
    return openpyxl.load_workbook(buf)


# ---------------------------------------------------------------------------
# _compute_week_ranges
# ---------------------------------------------------------------------------

class TestComputeWeekRanges:
    def test_single_week_returns_empty(self):
        # Feb 2-6 2026 is Mon-Fri, all ISO week 6
        dates = pd.to_datetime(["2026-02-02", "2026-02-04", "2026-02-06"])
        assert _compute_week_ranges(dates) == []

    def test_two_weeks_returns_two_ranges(self):
        # Week 5: Jan 26 (Mon) - Feb 1 (Sun)
        # Week 6: Feb 2 (Mon) - Feb 8 (Sun)
        dates = pd.to_datetime(["2026-01-28", "2026-02-01", "2026-02-03", "2026-02-05"])
        result = _compute_week_ranges(dates)
        assert len(result) == 2
        assert result[0] == (pd.Timestamp("2026-01-28"), pd.Timestamp("2026-02-01"))
        assert result[1] == (pd.Timestamp("2026-02-02"), pd.Timestamp("2026-02-05"))

    def test_partial_week_at_start(self):
        # Wed Jan 28 through Mon Feb 9
        dates = pd.to_datetime(["2026-01-28", "2026-02-02", "2026-02-09"])
        result = _compute_week_ranges(dates)
        assert len(result) == 3
        assert result[0][0] == pd.Timestamp("2026-01-28")
        assert result[0][1] == pd.Timestamp("2026-02-01")

    def test_empty_dates_returns_empty(self):
        dates = pd.to_datetime([])
        assert _compute_week_ranges(dates) == []


# ---------------------------------------------------------------------------
# _build_weekly_product_data
# ---------------------------------------------------------------------------

class TestBuildWeeklyProductData:
    def test_returns_dict_per_week(self):
        df = _make_test_df()
        week_ranges = _compute_week_ranges(df["Date"])
        result = _build_weekly_product_data(df, week_ranges)
        assert len(result) == 2

    def test_weekly_sums_are_correct(self):
        df = _make_test_df()
        week_ranges = _compute_week_ranges(df["Date"])
        result = _build_weekly_product_data(df, week_ranges)
        # Week 1: Jan 28-Feb 1 = 5 days, HOUSE SOURDOUGH = 5 * 100 = 500
        w1 = result[week_ranges[0]]
        sourdough_rev = w1.loc[w1["Description"] == "HOUSE SOURDOUGH", "Revenue"].values[0]
        assert sourdough_rev == 500

    def test_products_missing_in_a_week_get_zero(self):
        df = _make_test_df()
        # Add a product only in week 2
        extra = pd.DataFrame([{
            "Date": pd.Timestamp("2026-02-03"), "Description": "BAGUETTE",
            "Category": "Standard Loaves", "Revenue": 30, "Quantity": 5,
            "Hour": 9, "Basket_ID": "B5",
        }])
        df = pd.concat([df, extra], ignore_index=True)
        week_ranges = _compute_week_ranges(df["Date"])
        result = _build_weekly_product_data(df, week_ranges)
        w1 = result[week_ranges[0]]
        baguette = w1.loc[w1["Description"] == "BAGUETTE", "Revenue"].values[0]
        assert baguette == 0


# ---------------------------------------------------------------------------
# generate_excel — single week (flat layout)
# ---------------------------------------------------------------------------

class TestGenerateExcelSingleWeek:
    def test_single_week_has_flat_layout(self):
        df = _make_test_df()
        df = df[df["Date"] < "2026-02-02"]  # week 1 only
        buf = generate_excel(df, df["Date"].min(), df["Date"].max())
        ws = _open_wb(buf).active
        headers = [ws.cell(1, c).value for c in range(1, 7)]
        assert headers == ["Product", "Category", "Total Revenue", "Total Quantity", "Avg Price", "% of Revenue"]

    def test_single_week_totals_use_subtotal_formula(self):
        df = _make_test_df()
        df = df[df["Date"] < "2026-02-02"]
        buf = generate_excel(df, df["Date"].min(), df["Date"].max())
        ws = _open_wb(buf).active
        last_row = ws.max_row
        assert ws.cell(last_row, 1).value == "TOTAL"
        # Revenue total should be a SUBTOTAL formula, not a hardcoded value
        rev_cell = ws.cell(last_row, 3).value
        assert isinstance(rev_cell, str) and "SUBTOTAL" in rev_cell


# ---------------------------------------------------------------------------
# generate_excel — multi week
# ---------------------------------------------------------------------------

class TestGenerateExcelMultiWeek:
    def test_multi_week_has_merged_week_headers(self):
        df = _make_test_df()
        buf = generate_excel(df, df["Date"].min(), df["Date"].max())
        ws = _open_wb(buf).active
        assert ws.cell(1, 1).value == "Product"
        assert ws.cell(1, 2).value == "Category"
        # Column C should be the first week label
        week1_label = ws.cell(1, 3).value
        assert "Jan" in week1_label

    def test_multi_week_has_sub_headers(self):
        df = _make_test_df()
        buf = generate_excel(df, df["Date"].min(), df["Date"].max())
        ws = _open_wb(buf).active
        assert ws.cell(2, 3).value == "Rev"
        assert ws.cell(2, 4).value == "Qty"

    def test_multi_week_totals_at_end(self):
        df = _make_test_df()
        buf = generate_excel(df, df["Date"].min(), df["Date"].max())
        ws = _open_wb(buf).active
        max_col = ws.max_column
        assert ws.cell(1, max_col - 3).value == "Total Revenue"
        assert ws.cell(1, max_col - 2).value == "Total Quantity"
        assert ws.cell(1, max_col - 1).value == "Avg Price"
        assert ws.cell(1, max_col).value == "% of Revenue"

    def test_multi_week_data_values(self):
        df = _make_test_df()
        buf = generate_excel(df, df["Date"].min(), df["Date"].max())
        ws = _open_wb(buf).active
        # HOUSE SOURDOUGH is first (highest rev), data starts row 3
        # Week 1 rev (col C) = 5 days * $100 = $500
        found = False
        for r in range(3, ws.max_row + 1):
            if ws.cell(r, 1).value == "HOUSE SOURDOUGH":
                assert ws.cell(r, 3).value == 500
                found = True
                break
        assert found, "HOUSE SOURDOUGH not found in data rows"

    def test_totals_row_uses_subtotal(self):
        df = _make_test_df()
        buf = generate_excel(df, df["Date"].min(), df["Date"].max())
        ws = _open_wb(buf).active
        last_row = ws.max_row
        assert ws.cell(last_row, 1).value == "TOTAL"
        # Weekly rev total (col C) should be SUBTOTAL formula
        rev_cell = ws.cell(last_row, 3).value
        assert isinstance(rev_cell, str) and "SUBTOTAL" in rev_cell

    def test_frozen_panes_at_a3(self):
        df = _make_test_df()
        buf = generate_excel(df, df["Date"].min(), df["Date"].max())
        ws = _open_wb(buf).active
        assert ws.freeze_panes == "A3"
