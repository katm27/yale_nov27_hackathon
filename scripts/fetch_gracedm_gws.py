#!/usr/bin/env python
"""Groundwater drought indicator (NASA GRACE data assimilation, Catchment model) for South Sudan counties, 2018-2025.

Source: NASA GSFC Hydrological Sciences Lab / National Drought Mitigation Center "GRACE-based global drought
indicators" (GRACEDADM_CLSM025_GL_7D), public weekly NetCDF files at https://nasagrace.unl.edu/globaldata/YYYYMMDD/
(no login). Variable gws_inst = groundwater storage PERCENTILE (0-100) for that week of the year, from the same
NASA Catchment model + GRACE/GRACE-FO data assimilation system as GLDAS-2.2 CLSM DA (Li et al. 2019, WRR,
doi:10.1029/2018WR024618), on a 0.25 deg grid. It is a ranking against the model's long-term climatology for the
same time of year (low = drier than usual), not storage in cm: the cm anomaly (GWS_tavg) needs the GES DISC / Earth
Engine product (scripts/gee_gldas_gws.py), which is not reachable from the build environment.

Steps: weekly 0.25 deg grids -> per-pixel monthly mean of the weeks dated in that month -> 0.01 deg grid (nearest)
-> county mean (fetch_appeears.county_rows). Weekly files are downloaded once into $GRACEDM_RAW.

Outputs: data/processed/gracedm_county_monthly.csv (variable gracedm_gws_pctl), data/processed/meta/gracedm.json,
         docs/rasters/gracedm_gws/YYYY-MM.png + meta.json, grids in $GRACEDM_WORK/grids/gracedm_gws_pctl/.
Usage:   python scripts/fetch_gracedm_gws.py [--download]
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gee_utils as gu  # noqa: E402  (shared grid / county / render helpers; no Earth Engine used here)

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = os.environ.get("RT_SCRATCH",
                         "/tmp/claude-0/-home-user-yale-nov27-hackathon/b7acc7ce-9c21-59ae-8208-6da6aae060da/scratchpad")
RAW = Path(os.environ.get("GRACEDM_RAW", os.path.join(SCRATCH, "gldas", "gracedm")))
WORK = Path(os.environ.get("GRACEDM_WORK", os.path.join(SCRATCH, "gldas", "gracedm_work")))
URL = "https://nasagrace.unl.edu/globaldata/"
VAR, KEY, SOURCE = "gracedm_gws_pctl", "gracedm_gws", "gracedm"
SUDD_NOTE = ("Less conclusive in and around the Sudd wetland, where flood water on the surface can be mistaken for "
             "groundwater.")


def download():
    import requests
    RAW.mkdir(parents=True, exist_ok=True)
    dirs = sorted(set(re.findall(r"globaldata/(\d{8})/", requests.get(URL, timeout=120).text)))
    for d in dirs:
        if not ("20180101" <= d <= "20260105"):
            continue
        html = requests.get(f"{URL}{d}/", timeout=120).text
        m = re.search(r"GRACEDADM_CLSM025_GL_7D[^\"/]*\.nc4", html)
        if not m or (RAW / m.group(0)).exists():
            continue
        subprocess.run(["curl", "-s", "-m", "300", "-o", str(RAW / m.group(0)), f"{URL}{d}/{m.group(0)}"], check=True)
        gu.log("got", m.group(0))


def build():
    import xarray as xr
    from rasterio.transform import from_origin
    files = sorted(RAW.glob("GRACEDADM_CLSM025_GL_7D.A*.nc4"))
    by = {}
    for f in files:
        d = dt.datetime.strptime(re.search(r"\.A(\d{8})\.", f.name).group(1), "%Y%m%d").date()
        by.setdefault(f"{d.year}-{d.month:02d}", []).append(f)
    rows, weeks = [], {}
    tf = None
    for mk in gu.MONTHS:
        fl = by.get(mk, [])
        if not fl:
            gu.log(mk, "no weekly files")
            continue
        stack = []
        for f in fl:
            with xr.open_dataset(f) as ds:
                a = ds["gws_inst"].isel(time=0).sel(lat=slice(2.9, 12.8), lon=slice(22.9, 36.5))
                lat, lon = a["lat"].values, a["lon"].values
                v = a.values.astype("float32")
                v[(v < 0) | (v > 100)] = np.nan
                stack.append(v[::-1])  # north-up
        tf = from_origin(float(lon[0]) - 0.125, float(lat[-1]) + 0.125, 0.25, 0.25)
        arr = np.nanmean(np.stack(stack), axis=0).astype("float32")
        g = gu.to_grid(arr, tf, "nearest")
        gu.save_grid(WORK, VAR, mk, g)
        rows += gu.fa.county_rows(g, mk, VAR, rnd=2)
        weeks[mk] = len(fl)
    df = pd.DataFrame(rows, columns=["county_id", "date", "variable", "value"]).sort_values(
        ["variable", "county_id", "date"])
    out = ROOT / "data" / "processed" / f"{SOURCE}_county_monthly.csv"
    df.to_csv(out, index=False)
    missing = [m for m in gu.MONTHS if m not in weeks]
    meta = [{
        "id": VAR, "label": "Groundwater drought indicator (NASA GRACE data assimilation)", "category": "environment",
        "group": "Water storage & groundwater (GRACE)", "units": "percentile (0-100)",
        "source": "NASA GSFC / NDMC GRACE-based global drought indicators (GRACEDADM_CLSM025_GL_7D, gws_inst): "
                  "Catchment land surface model with GRACE/GRACE-FO data assimilation",
        "source_url": "https://nasagrace.unl.edu/GlobalData.aspx", "native_resolution": "0.25° (~28 km) model grid; "
        "GRACE information it assimilates is ~300 km", "temporal": "monthly",
        "aggregation": "per-pixel mean of the weekly percentiles dated in the month, then mean of ~1 km cells "
                       "inside the county", "higher_is": "better", "index_ok": False, "raster": KEY,
        "notes": ("Groundwater only. Each week the model's groundwater storage is ranked against its own long-term "
                  "record for the same time of year: 50 = normal, below 20 = unusually dry (drought), above 80 = "
                  "unusually wet. It is a ranking, not an amount of water, so compare counties by how far they are "
                  "from 50, not as cm. Same NASA system as GLDAS-2.2 CLSM GRACE-DA; the GRACE signal it assimilates "
                  "is ~300 km wide, so neighbouring counties move together. "
                  + (f"No data for {', '.join(missing)} (weekly updates paused Oct-Nov 2025). " if missing else "")
                  + SUDD_NOTE),
    }]
    (ROOT / "data" / "processed" / "meta" / f"{SOURCE}.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    gu.render(WORK, [dict(key=KEY, var=VAR, label="Groundwater drought indicator (GRACE-DA percentile)",
                          units="percentile", vmin=0.0, vmax=100.0,
                          colors=["#8c510a", "#d8b365", "#f6e8c3", "#f5f5f5", "#c7eae5", "#5ab4ac", "#01665e"],
                          cmap_name="brown-teal (0 = driest, 50 = normal, 100 = wettest)",
                          native="0.25° (~28 km) model grid, nearest-neighbour",
                          source="NASA GRACE-DA global drought indicator (gws_inst) via nasagrace.unl.edu")])
    gu.log(f"wrote {out}: {len(df)} rows, {df.county_id.nunique()} counties, {df.date.nunique()} months, "
           f"range {df.value.min():.1f}..{df.value.max():.1f}; weeks/month min {min(weeks.values())}; missing {missing}")
    from trend_stats import write_trends
    write_trends(SOURCE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true")
    a = ap.parse_args()
    if a.download or not any(RAW.glob("*.nc4")):
        download()
    build()


if __name__ == "__main__":
    main()
