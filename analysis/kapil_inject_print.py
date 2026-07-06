"""Inject the daily SVG path/area into the PRINT HTML report."""

import json
from datetime import date, timedelta
from pathlib import Path

metrics = json.loads(Path(r"D:\TMB 2.0\analysis\kapil_metrics.json").read_text())
daily = metrics["pastries"]["daily"]  # list of {Day, revenue, qty}

# Chart geometry (must match the SVG in the HTML)
X0, X1 = 40, 710
Y_BOTTOM = 304    # y for $0
Y_TOP    = 56     # y for $800 (or higher)
START = date(2026, 2, 1)
END   = date(2026, 5, 27)
DAYS_SPAN = (END - START).days  # 115 → so day_index goes 0..115 inclusive = 116 values
SCALE_MAX = 800   # gridline top — values above this exceed gridline (fine)

def x_for_day(i):
    return X0 + (i / DAYS_SPAN) * (X1 - X0)

def y_for_rev(v):
    # 248 px for $800
    return Y_BOTTOM - (v / SCALE_MAX) * (Y_BOTTOM - Y_TOP)

# Build polyline points
pts = []
for r in daily:
    d = date.fromisoformat(r["Day"])
    i = (d - START).days
    x = x_for_day(i)
    y = y_for_rev(r["revenue"])
    pts.append((x, y))

line_points = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)

# Area path: line points then close to baseline
first_x = pts[0][0]
last_x  = pts[-1][0]
area_d = "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
area_d += f" L {last_x:.2f},{Y_BOTTOM} L {first_x:.2f},{Y_BOTTOM} Z"

# Month divider verticals + labels
dividers_svg = ""
for month_start, label in [
    (date(2026, 3, 1), "MARCH"),
    (date(2026, 4, 1), "APRIL"),
    (date(2026, 5, 1), "MAY"),
]:
    x = x_for_day((month_start - START).days)
    dividers_svg += (
        f'\n<line x1="{x:.2f}" y1="56" x2="{x:.2f}" y2="304" '
        f'stroke="var(--rule)" stroke-width=".6" stroke-dasharray="1.5 2"/>'
    )

# Month labels positioned mid-month at top of chart area (small caps)
month_label_y = 50
month_centres = [
    (date(2026, 2, 14), "FEBRUARY"),
    (date(2026, 3, 16), "MARCH"),
    (date(2026, 4, 15), "APRIL"),
    (date(2026, 5, 14), "MAY"),
]
for d, lbl in month_centres:
    x = x_for_day((d - START).days)
    dividers_svg += (
        f'\n<text class="axis" x="{x:.2f}" y="{month_label_y}" text-anchor="middle" '
        f'fill="var(--ink-3)" font-size="8.5" letter-spacing=".18em">{lbl}</text>'
    )

# Highlight the single tallest point (Feb 21 at $848.40)
peak = max(daily, key=lambda r: r["revenue"])
peak_d = date.fromisoformat(peak["Day"])
peak_x = x_for_day((peak_d - START).days)
peak_y = y_for_rev(peak["revenue"])
peak_svg = (
    f'\n<circle cx="{peak_x:.2f}" cy="{peak_y:.2f}" r="3.2" fill="var(--brass)" '
    f'stroke="var(--c1)" stroke-width="1.2"/>'
    f'\n<text class="val" font-size="9" x="{peak_x:.2f}" y="{peak_y-7:.2f}" '
    f'text-anchor="middle" fill="var(--brass-deep)">$848 · 21 Feb</text>'
)

# Build the SVG fragments
area_svg = f'<path d="{area_d}" fill="var(--brass)" fill-opacity=".15" stroke="none"/>'
line_svg = f'<polyline points="{line_points}" fill="none" stroke="var(--c1)" stroke-width="1.1"/>'

# Read HTML and substitute
html_path = Path(r"D:\TMB 2.0\reports\Pastries_BAH_Kids_SRoll_Report_PRINT.html")
html = html_path.read_text(encoding="utf-8")
html = html.replace("<!-- DAILY_AREA -->",     area_svg)
html = html.replace("<!-- DAILY_LINE -->",     line_svg + peak_svg)
html = html.replace("<!-- DAILY_DIVIDERS -->", dividers_svg)
html_path.write_text(html, encoding="utf-8")

print(f"Injected {len(pts)} daily points across {DAYS_SPAN+1} days")
print(f"Peak: ${peak['revenue']} on {peak['Day']}")
print(f"File: {html_path}")
print(f"Size: {html_path.stat().st_size:,} bytes")
