# TMB Sales Dashboard

A Streamlit app for reading Three Mills Bakery's daily sales out of Harris Farm's
point-of-sale exports. It pulls the day files from Google Drive, cleans them, and
turns them into something a bakery manager can act on without knowing what a
pivot table is.

## What it does

Pick your dates first, then explore. The app loads only the days you asked for,
so a single Tuesday is fast and a full quarter is still workable.

Once data is loaded you get three tools:

- **Dashboard** — revenue, units, and category mix over the selected period, with
  written callouts on what moved and what stalled.
- **Baskets** — average basket size and value, plus which products get bought
  together. Basket identity comes from `Reference2` + `Till`.
- **Typical Day** — model an average Monday (or any weekday) from the days
  already loaded, including hour-by-hour trade.

Every view exports to PDF and Excel. The PDFs are written to be read on their
own, without someone standing next to you explaining the charts.

## Setup

You need Python 3.10+ and read access to the sales folder on Drive.

```bash
pip install -r requirements.txt
```

Then get a Google service account key, name it `service_account.json`, and drop
it in the project root. Share the Drive folder with that service account's email
address, read-only. The file is gitignored and must stay that way.

```bash
streamlit run app.py
```

On Windows, `run_dashboard.bat` does the same thing.

## Data

There is no master spreadsheet. Each trading day is one file named `YYYYMMDD.xlsx`
in the Drive folder set by `TMB_SALES_FOLDER_ID` in `config.py`. History starts
29 May 2024.

Two things about those files that will bite you if you write your own scripts
against them:

1. Every daily file ends with a totals footer row. Filter on `Description.notna()`
   before you sum anything, or you will double the day's revenue.
2. `20250510.xlsx` has its `Description` column header named `4`. The main
   pipeline drops those rows silently until someone fixes the file at source.

Product-to-category mapping lives in `category_config.csv`. Edit it in Excel and
add a row; anything unmatched falls through to a keyword rule and then to
"Other", which the sidebar warns you about.

## Layout

```
app.py              entry point, mode routing, filter orchestration
config.py           constants, colours, thresholds
styles.py           CSS tokens and the shared Plotly template
components/         date picker, filters, header, metric tiles
views/              dashboard, basket, average day
reports/            PDF and Excel generators
services/           Drive auth and download, cleaning, insight engine
tests/              coverage for the Excel export
```

## Notes

Caching keeps the Drive file list for 10 minutes and loaded data for an hour, so
if a new day lands mid-session you may need to rerun.

Streamlit must be 1.38 or newer. Older versions break on `LargeUtf8` when pandas
hands them PyArrow-backed strings.
