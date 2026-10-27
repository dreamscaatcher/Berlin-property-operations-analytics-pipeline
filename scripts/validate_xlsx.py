#!/usr/bin/env python3
"""Check the Power BI workbook: every sheet has one Excel Table whose size matches the rows."""
import sys, zipfile, re, openpyxl, datetime as dt
import os
p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "powerbi", "Berlin_Property_Ops_33k.xlsx")
z = zipfile.ZipFile(p)
tabs = {}
for n in z.namelist():
    if n.startswith("xl/tables/"):
        x = z.read(n).decode()
        tabs[re.search(r'displayName="([^"]+)"', x).group(1)] = re.search(r' ref="([^"]+)"', x).group(1)
wb = openpyxl.load_workbook(p, read_only=True)
bad = 0
for ws in wb.worksheets:
    n = 0; types = {}
    hdr = None
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            hdr = row; continue
        n += 1
        if i <= 2000:
            for h, v in zip(hdr, row):
                if v is not None:
                    types.setdefault(h, set()).add(type(v).__name__)
    ref = tabs.get(ws.title)
    ok = ref is not None and int(re.search(r"(\d+)$", ref).group(1)) == max(n, 1) + 1 if ws.title != "README" else True
    bad += (not ok)
    print(f"{ws.title:32s} rows={n:>9,} table={ref} ok={ok} max_rows_ok={n < 1048576}")
    if ws.title != "README":
        print("    ", {h: "/".join(sorted(t)) for h, t in types.items()})
print("TABLES:", len(tabs), "BAD:", bad)
