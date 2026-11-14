#!/usr/bin/env python3
"""NASA POWER monthly wind / heat / precipitation / aerosol at each county centroid (2018-2025).

API (no login): https://power.larc.nasa.gov/api/temporal/monthly/point
Parameters (community AG):
  WS2M, WS10M, WS10M_MAX, T2M_MAX, PRECTOTCORR  -> MERRA-2 (0.5° x 0.625°)
  AOD_55, AOD_84                                -> CERES SYN1deg (1°), as reported in the POWER response header
Sampling: one POWER grid-cell value at the county centroid (lat/lon columns of data/counties.geojson).
POWER grid cells (~50-110 km) are comparable to or larger than most counties, so centroid sampling is close
to a county mean; very large counties may hide within-county variation.

Output: data/processed/nasapower_county_monthly.csv, data/processed/meta/nasapower.json
Raw JSON cached in data/raw/nasa_power/ (small; one file per county).
"""
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/nasa_power"
OUT = ROOT / "data/processed/nasapower_county_monthly.csv"
META = ROOT / "data/processed/meta/nasapower.json"
API = ("https://power.larc.nasa.gov/api/temporal/monthly/point?parameters={p}&community=AG"
       "&longitude={lon:.4f}&latitude={lat:.4f}&start=2018&end=2025&format=JSON")
URL_DOC = "https://power.larc.nasa.gov/"
M2 = ("MERRA-2 via NASA POWER", "0.5° x 0.625° (~55 km)")
SYN = ("CERES SYN1deg via NASA POWER", "1° (~110 km)")

# POWER param, id, label, group, units, higher_is, index_ok, (source, res), scale, notes
PARAMS = [
    ("WS2M", "power_ws2m", "Wind speed at 2 m", "Wind", "m/s", "neutral", True, M2, 1, ""),
    ("WS10M", "power_ws10m", "Wind speed at 10 m", "Wind", "m/s", "neutral", True, M2, 1, ""),
    ("WS10M_MAX", "power_ws10m_max", "Strongest hourly wind at 10 m", "Wind", "m/s", "worse", True, M2, 1,
     "Maximum hourly 10 m wind speed in the month (storm/dust-wind proxy)."),
    ("T2M_MAX", "power_t2m_max", "Hottest hour of the month (2 m)", "Temperature", "°C", "worse", False, M2, 1,
     "Single highest hourly 2 m air temperature in the month."),
    ("PRECTOTCORR", "power_precip_mm", "Precipitation (MERRA-2 bias-corrected)", "Precipitation", "mm/month",
     "better", True, M2, None, "POWER gives mm/day; multiplied by days in month."),
    ("AOD_55", "power_aod_550", "Aerosol optical depth 550 nm (dust/smoke haze)", "Air quality",
     "dimensionless", "worse", True, SYN, 1,
     "Column aerosol optical depth; high values in the dry season reflect Saharan dust and biomass burning."),
    ("AOD_84", "power_aod_840", "Aerosol optical depth 840 nm", "Air quality", "dimensionless", "worse", True,
     SYN, 1, "Longer-wavelength AOD; relatively more sensitive to coarse dust than to smoke."),
]


def fetch(row):
    out = RAW / f"{row.district_id}.json"
    if out.exists():
        return out
    url = API.format(p=",".join(p[0] for p in PARAMS), lon=row.lon, lat=row.lat)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                data = json.load(r)
            data["request_url"] = url
            out.write_text(json.dumps(data))
            return out
        except Exception as e:  # noqa: BLE001
            print("retry", row.district_id, e)
            time.sleep(5 * (attempt + 1))
    return None


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    cty = gpd.read_file(ROOT / "data/counties.geojson")
    with ThreadPoolExecutor(4) as ex:
        paths = list(ex.map(fetch, cty.itertuples()))
    print("failed:", [c for c, p in zip(cty.district_id, paths) if p is None])

    rows = []
    for cid, p in zip(cty.district_id, paths):
        if p is None:
            continue
        d = json.loads(p.read_text())
        fill = d["header"].get("fill_value", -999.0)
        par = d["properties"]["parameter"]
        for (pp, vid, *_rest) in PARAMS:
            scale = _rest[-2]
            for ym, v in par.get(pp, {}).items():
                if ym.endswith("13") or v is None or v == fill:  # month 13 = annual
                    continue
                date = pd.Timestamp(f"{ym[:4]}-{ym[4:]}-01")
                val = v * (date.days_in_month if scale is None else scale)
                rows.append((cid, date.strftime("%Y-%m-%d"), vid, round(val, 3)))
    df = pd.DataFrame(rows, columns=["county_id", "date", "variable", "value"])
    df = df.sort_values(["variable", "county_id", "date"])
    df.to_csv(OUT, index=False)
    print(OUT, len(df), df.county_id.nunique(), df.date.min(), df.date.max())
    print(df.groupby("variable").value.describe().round(2))

    meta = []
    for (pp, vid, label, group, units, hi, iok, (src, res), _s, notes) in PARAMS:
        meta.append(dict(id=vid, label=label, category="environment", group=group, units=units,
                         source=f"{src} (parameter {pp})", source_url=URL_DOC, native_resolution=res,
                         temporal="monthly",
                         aggregation="value of the POWER grid cell containing the county centroid "
                                     "(centroid sampling; grid cells are ~county-sized or larger)",
                         higher_is=hi, index_ok=iok, notes=notes))
    META.write_text(json.dumps(meta, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from trend_stats import write_trends
    write_trends("nasapower")  # Mann-Kendall + Sen's slope (scripts/trend_stats.py)
