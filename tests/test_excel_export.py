"""Tests for reports/excel_export.py."""

import openpyxl
from io import BytesIO

import pandas as pd
import pytest

from reports.excel_export import _compute_week_ranges, _compute_day_ranges, _build_weekly_product_data, generate_excel, generate_baskets_excel


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
# _compute_day_ranges
# ---------------------------------------------------------------------------

class TestComputeDayRanges:
    def test_single_day_returns_empty(self):
        dates = pd.to_datetime(["2026-02-02", "2026-02-02"])
        assert _compute_day_ranges(dates) == []

    def test_multiple_days_returns_per_day(self):
        dates = pd.to_datetime(["2026-02-02", "2026-02-03", "2026-02-04"])
        result = _compute_day_ranges(dates)
        assert len(result) == 3
        assert result[0] == (pd.Timestamp("2026-02-02"), pd.Timestamp("2026-02-02"))
        assert result[2] == (pd.Timestamp("2026-02-04"), pd.Timestamp("2026-02-04"))

    def test_empty_dates_returns_empty(self):
        dates = pd.to_datetime([])
        assert _compute_day_ranges(dates) == []


# ---------------------------------------------------------------------------
# generate_excel — single day (flat layout)
# ---------------------------------------------------------------------------

class TestGenerateExcelSingleDay:
    def test_single_day_has_flat_layout(self):
        df = _make_test_df()
        df = df[df["Date"] == "2026-01-28"]  # single day only
        buf = generate_excel(df, df["Date"].min(), df["Date"].max())
        ws = _open_wb(buf).active
        headers = [ws.cell(1, c).value for c in range(1, 7)]
        assert headers == ["Product", "Category", "Total Revenue", "Total Quantity", "Avg Price", "% of Revenue"]

    def test_single_day_totals_use_subtotal_formula(self):
        df = _make_test_df()
        df = df[df["Date"] == "2026-01-28"]
        buf = generate_excel(df, df["Date"].min(), df["Date"].max())
        ws = _open_wb(buf).active
        last_row = ws.max_row
        assert ws.cell(last_row, 1).value == "TOTAL"
        rev_cell = ws.cell(last_row, 3).value
        assert isinstance(rev_cell, str) and "SUBTOTAL" in rev_cell


# ---------------------------------------------------------------------------
# generate_excel — multi day (single week, 2+ days)
# ---------------------------------------------------------------------------

class TestGenerateExcelMultiDay:
    def _single_week_df(self):
        """Week 1 only: Jan 28-Feb 1, 5 days, 2 products."""
        df = _make_test_df()
        return df[df["Date"] < "2026-02-02"].copy()

    def test_daily_has_merged_day_headers(self):
        df = self._single_week_df()
        buf = generate_excel(df, df["Date"].min(), df["Date"].max())
        ws = _open_wb(buf).active
        assert ws.cell(1, 1).value == "Product"
        assert ws.cell(1, 2).value == "Category"
        # Column C should be first day label (Wed Jan 28)
        day1_label = ws.cell(1, 3).value
        assert "Wed" in day1_label
        assert "28" in day1_label

    def test_daily_has_sub_headers(self):
        df = self._single_week_df()
        buf = generate_excel(df, df["Date"].min(), df["Date"].max())
        ws = _open_wb(buf).active
        assert ws.cell(2, 3).value == "Rev"
        assert ws.cell(2, 4).value == "Qty"

    def test_daily_totals_at_end(self):
        df = self._single_week_df()
        buf = generate_excel(df, df["Date"].min(), df["Date"].max())
        ws = _open_wb(buf).active
        max_col = ws.max_column
        assert ws.cell(1, max_col - 3).value == "Total Revenue"
        assert ws.cell(1, max_col - 2).value == "Total Quantity"
        assert ws.cell(1, max_col - 1).value == "Avg Price"
        assert ws.cell(1, max_col).value == "% of Revenue"

    def test_daily_data_values(self):
        df = self._single_week_df()
        buf = generate_excel(df, df["Date"].min(), df["Date"].max())
        ws = _open_wb(buf).active
        # HOUSE SOURDOUGH day 1 rev (col C) = 1 day * $100 = $100
        found = False
        for r in range(3, ws.max_row + 1):
            if ws.cell(r, 1).value == "HOUSE SOURDOUGH":
                assert ws.cell(r, 3).value == 100
                found = True
                break
        assert found, "HOUSE SOURDOUGH not found in data rows"

    def test_daily_totals_row_uses_subtotal(self):
        df = self._single_week_df()
        buf = generate_excel(df, df["Date"].min(), df["Date"].max())
        ws = _open_wb(buf).active
        last_row = ws.max_row
        assert ws.cell(last_row, 1).value == "TOTAL"
        rev_cell = ws.cell(last_row, 3).value
        assert isinstance(rev_cell, str) and "SUBTOTAL" in rev_cell

    def test_daily_frozen_panes_at_a3(self):
        df = self._single_week_df()
        buf = generate_excel(df, df["Date"].min(), df["Date"].max())
        ws = _open_wb(buf).active
        assert ws.freeze_panes == "A3"

    def test_five_days_produce_five_day_columns(self):
        df = self._single_week_df()
        buf = generate_excel(df, df["Date"].min(), df["Date"].max())
        ws = _open_wb(buf).active
        # 5 days * 2 cols (Rev/Qty) + 2 (Product/Category) + 4 (totals) = 16
        assert ws.max_column == 16

    def test_dates_with_time_components_still_group_by_day(self):
        """Real data has timestamps with hours — ensure they collapse to days."""
        rows = []
        for hour in [7, 8, 9, 10]:
            rows.append({
                "Date": pd.Timestamp("2026-02-02") + pd.Timedelta(hours=hour),
                "Description": "SOURDOUGH", "Category": "Loaves",
                "Revenue": 25, "Quantity": 3, "Hour": hour, "Basket_ID": "B1",
            })
            rows.append({
                "Date": pd.Timestamp("2026-02-03") + pd.Timedelta(hours=hour),
                "Description": "SOURDOUGH", "Category": "Loaves",
                "Revenue": 30, "Quantity": 4, "Hour": hour, "Basket_ID": "B2",
            })
        df = pd.DataFrame(rows)
        buf = generate_excel(df, df["Date"].min(), df["Date"].max())
        ws = _open_wb(buf).active
        # 2 days * 2 cols + 2 (Prod/Cat) + 4 (totals) = 10
        assert ws.max_column == 10
        # Day 1 rev = 4 hours * $25 = $100
        assert ws.cell(3, 3).value == 100
        # Day 2 rev = 4 hours * $30 = $120
        assert ws.cell(3, 5).value == 120


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


# ---------------------------------------------------------------------------
# generate_baskets_excel
# ---------------------------------------------------------------------------

def _make_basket_df():
    """Build a minimal basket DataFrame for testing."""
    rows = [
        # Basket B1: 2 different products, qty 3 total
        {"Date": pd.Timestamp("2026-02-28 09:15:00"), "Description": "HOUSE SOURDOUGH",
         "Category": "Standard Loaves", "Revenue": 10.5, "Quantity": 1, "Hour": 9, "Basket_ID": "B1"},
        {"Date": pd.Timestamp("2026-02-28 09:15:00"), "Description": "CROISSANT PLAIN",
         "Category": "Pastries", "Revenue": 12.0, "Quantity": 2, "Hour": 9, "Basket_ID": "B1"},
        # Basket B2: 1 product, qty 1
        {"Date": pd.Timestamp("2026-02-28 10:30:00"), "Description": "HOUSE SOURDOUGH",
         "Category": "Standard Loaves", "Revenue": 10.5, "Quantity": 1, "Hour": 10, "Basket_ID": "B2"},
        # Basket B3: 1 product, qty 3
        {"Date": pd.Timestamp("2026-03-01 08:00:00"), "Description": "CROISSANT PLAIN",
         "Category": "Pastries", "Revenue": 18.0, "Quantity": 3, "Hour": 8, "Basket_ID": "B3"},
    ]
    return pd.DataFrame(rows)


class TestGenerateBasketsExcel:
    def test_columns_no_basket_id(self):
        """Basket ID column should not be present."""
        df = _make_basket_df()
        ws = _open_wb(generate_baskets_excel(df)).active
        headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
        assert headers == ["Date", "Items", "Total", "Categories", "Products"]

    def test_products_show_quantities(self):
        """Multi-qty products should show count in parentheses."""
        df = _make_basket_df()
        ws = _open_wb(generate_baskets_excel(df)).active
        # Find basket B1 (first row, has CROISSANT PLAIN qty 2)
        products_b1 = ws.cell(2, 5).value
        assert "CROISSANT PLAIN (2)" in products_b1
        assert "HOUSE SOURDOUGH" in products_b1
        # Single qty should NOT have parentheses
        assert "HOUSE SOURDOUGH (" not in products_b1

    def test_single_qty_no_parentheses(self):
        """Basket B3 has qty 3 of one product."""
        df = _make_basket_df()
        ws = _open_wb(generate_baskets_excel(df)).active
        # B3 is last basket (sorted by date) — 3 croissants
        last_data_row = ws.max_row - 1  # exclude TOTAL row
        products_b3 = ws.cell(last_data_row, 5).value
        assert "CROISSANT PLAIN (3)" in products_b3

    def test_categories_column(self):
        """Each basket should have a Categories column with sorted unique categories."""
        df = _make_basket_df()
        ws = _open_wb(generate_baskets_excel(df)).active
        # B1 has Standard Loaves + Pastries
        cats_b1 = ws.cell(2, 4).value
        assert "Pastries" in cats_b1
        assert "Standard Loaves" in cats_b1

    def test_date_format_includes_time(self):
        """Date column should use DD/MM/YYYY HH:MM format."""
        df = _make_basket_df()
        ws = _open_wb(generate_baskets_excel(df)).active
        assert ws.cell(2, 1).number_format == "DD/MM/YYYY HH:MM"

    def test_alternating_row_fill(self):
        """Even data rows should have a grey tint fill."""
        df = _make_basket_df()
        ws = _open_wb(generate_baskets_excel(df)).active
        # Row 2 = even → should have fill
        assert ws.cell(2, 1).fill.start_color.rgb == "00F0F0F0"
        # Row 3 = odd → no fill (white)
        assert ws.cell(3, 1).fill.start_color.rgb == "00000000"

    def test_total_row_subtotal_formulas(self):
        """TOTAL row should have SUBTOTAL formulas for Items and Total."""
        df = _make_basket_df()
        ws = _open_wb(generate_baskets_excel(df)).active
        total_row = ws.max_row
        assert ws.cell(total_row, 1).value == "TOTAL"
        assert "SUBTOTAL" in str(ws.cell(total_row, 2).value)
        assert "SUBTOTAL" in str(ws.cell(total_row, 3).value)

    def test_frozen_panes(self):
        df = _make_basket_df()
        ws = _open_wb(generate_baskets_excel(df)).active
        assert ws.freeze_panes == "A2"

    def test_empty_df(self):
        df = pd.DataFrame(columns=["Date", "Description", "Category", "Revenue", "Quantity", "Hour", "Basket_ID"])
        ws = _open_wb(generate_baskets_excel(df)).active
        assert ws.cell(1, 1).value == "Date"
