"""Inject daily data arrays into the HTML report."""

import json
from pathlib import Path

metrics = json.loads(Path(r"D:\TMB 2.0\analysis\kapil_metrics.json").read_text())

pas_daily = json.dumps(metrics["pastries"]["daily"])
kids_daily = json.dumps(metrics["kids_sroll"]["daily"])

html_path = Path(r"D:\TMB 2.0\reports\Pastries_BAH_Kids_SRoll_Report_2026-02-01_to_2026-05-27.html")
html = html_path.read_text(encoding="utf-8")
html = html.replace("__DAILY_PAS__", pas_daily)
html = html.replace("__DAILY_KIDS__", kids_daily)
html_path.write_text(html, encoding="utf-8")

print(f"Pastries daily points injected: {len(metrics['pastries']['daily'])}")
print(f"Kids daily points injected:     {len(metrics['kids_sroll']['daily'])}")
print(f"Wrote: {html_path}")
print(f"File size: {html_path.stat().st_size:,} bytes")
