"""Water points (WPDx) -> docs/data/points_water_points.geojson

Source: Water Point Data Exchange, WPDx-Basic (Socrata dataset eqje-vguj, https://data.waterpointdata.org),
South Sudan subset (6,099 points; same data as HDX 'wpdx_ssd'). Underlying inventories: OCHA/WASH-cluster WIMS
2006-2013, ACF/RWSS 2016, Water for South Sudan 2011-2015, UNHCR camps (reports Sep 2019).
No other open South Sudan water-point inventory with dates was found on HDX (searched 'water points boreholes').

Temporal standard:
  valid_from = install year (YYYY-01) when the install year is 2018 or later, else null (built before 2018 or
               install year unknown - WPDx gives install_year for only ~150 SSD points, all <= 2015);
  valid_to   = null (decommissioning not recorded);
  status     = functional status at the report date (status_clean); when the point's water_point_history has
               reports inside 2018-2025, one feature per status period (period starts at that report month).
  date_basis states install year and status report date. Nearly all reports are pre-2018: the status is a
  pre-window snapshot and should be read as 'last known', flagged by status_stale = true.
"""
import json
import os
import sys

import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from points_temporal import ROOT, point, write_fc, set_validity, update_points_meta, assign_county_fc

RAW = os.path.join(ROOT, "data", "raw", "wpdx")
API = "https://data.waterpointdata.org/resource/eqje-vguj.json"
FIELDS = ["row_id", "wpdx_id", "source", "lat_deg", "lon_deg", "report_date", "install_year", "status_id", "status_clean",
          "water_source_clean", "water_tech_clean", "facility_type", "management_clean", "clean_adm1", "clean_adm2",
          "water_point_history", "served_population", "dataset_title"]


def download():
    os.makedirs(RAW, exist_ok=True)
    p = os.path.join(RAW, "wpdx_ssd.json")
    if not os.path.exists(p):
        rows, off = [], 0
        while True:
            r = requests.get(API, params={"$where": "clean_country_name='South Sudan'", "$limit": 5000, "$offset": off,
                                          "$order": "row_id"}, timeout=180)
            r.raise_for_status()
            b = r.json()
            rows += b
            if len(b) < 5000:
                break
            off += 5000
        json.dump(rows, open(p, "w"))
        with open(os.path.join(RAW, "SOURCE.md"), "w") as f:
            f.write(f"WPDx-Basic, Socrata {API}?$where=clean_country_name='South Sudan' (downloaded Nov 2026, "
                    f"{len(rows)} rows). Licence CC BY 4.0. Also on HDX: https://data.humdata.org/dataset/wpdx_ssd\n")
    return json.load(open(p))


def main():
    rows = download()
    feats = []
    for r in rows:
        try:
            lat, lon = float(r["lat_deg"]), float(r["lon_deg"])
        except (KeyError, ValueError):
            continue
        iy = r.get("install_year")
        iy = int(float(iy)) if iy not in (None, "") else None
        hist = {}
        try:
            hist = json.loads(r.get("water_point_history") or "{}")
        except ValueError:
            pass
        rep = (r.get("report_date") or "")[:10]
        if rep and rep not in hist:
            hist[rep] = {"status_id": r.get("status_id")}
        reports = sorted((d, h) for d, h in hist.items() if d >= "1990")
        pre = [x for x in reports if x[0] < "2018-01"]
        inwin = [x for x in reports if "2018-01" <= x[0] <= "2025-12"]
        stat = {"Yes": "functional", "No": "non-functional"}
        periods = []
        last_pre = pre[-1] if pre else None
        start = f"{iy:04d}-01" if iy and iy >= 2018 else None
        if last_pre:
            periods.append((start, last_pre[0], last_pre[1]))
        elif not inwin:
            periods.append((start, rep or None, {"status_id": r.get("status_id")}))
        elif not iy or iy < 2018:  # existed before its first (in-window) report: status unknown until then
            periods.append((start, None, {}))
        for i, (d, h) in enumerate(inwin):
            periods.append((d[:7], d, h))
        for i, (vf, d, h) in enumerate(periods):
            vt = None
            if i + 1 < len(periods) and periods[i + 1][0]:
                vt = (pd.Period(periods[i + 1][0], "M") - 1).strftime("%Y-%m")
            st = stat.get(h.get("status_id"), r.get("status_clean") or "unknown") if h else "not reported before first in-window report"
            if h and i == len(periods) - 1 and r.get("status_clean"):
                st = r["status_clean"].lower() if h.get("status_id") == r.get("status_id") else st
            basis = (f"install year {iy}" if iy else "install year unknown") + \
                    (f"; status as reported {d}" if d else "; no report date") + \
                    ("; pre-2018 snapshot (last known)" if (not d or d < "2018-01") else "")
            props = dict(name=f"{r.get('water_source_clean') or 'water point'} ({r.get('clean_adm2') or ''})",
                         type=r.get("water_source_clean") or "water point")
            set_validity(props, vf, vt, basis)
            props.update(status=st, status_report_date=d, status_stale=bool(not d or d < "2018-01"),
                         install_year=iy, technology=r.get("water_tech_clean"), facility_type=r.get("facility_type"),
                         management=r.get("management_clean"), admin1=r.get("clean_adm1"), admin2=r.get("clean_adm2"),
                         wpdx_id=r.get("wpdx_id"), data_source=r.get("source"), dataset=r.get("dataset_title"),
                         source="Water Point Data Exchange (WPDx-Basic), CC BY 4.0")
            feats.append(point(lon, lat, props))
    feats = [f for f in feats if 3 <= f["geometry"]["coordinates"][1] <= 13 and 23 <= f["geometry"]["coordinates"][0] <= 36.5]
    assign_county_fc(feats)
    write_fc("points_water_points.geojson", feats)
    s = pd.DataFrame([f["properties"] for f in feats])
    print(len(feats), "features;", s.status.value_counts().to_dict(), "; stale:", int(s.status_stale.sum()),
          "; valid_from set:", int(s.valid_from.notna().sum()))
    update_points_meta({
        "key": "water_points", "label": "Water points (WPDx, last known status)", "category": "human",
        "source": "Water Point Data Exchange WPDx-Basic (OCHA/WASH WIMS 2006-13, ACF/RWSS 2016, Water for South Sudan "
                  "2011-15, UNHCR 2019), CC BY 4.0",
        "source_url": "https://data.waterpointdata.org/dataset/Water-Point-Data-Exchange-Basic-WPDx-Basic-/eqje-vguj",
        "notes": ("Temporal: valid_from = install year if >= 2018 (none in the data: install years <= 2015 or unknown) "
                  "else null; valid_to null (decommissioning not recorded). status = functional status at "
                  "status_report_date; almost all reports predate 2018 (status_stale=true: last known status, not "
                  "current). UNHCR camp points reported Sep 2019 get a separate status period from 2019-09. "
                  "Not a complete inventory of current water points.")})


if __name__ == "__main__":
    main()
