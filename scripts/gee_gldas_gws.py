#!/usr/bin/env python
"""Groundwater storage anomaly from NASA GLDAS-2.2 Catchment (CLSM) with GRACE data assimilation, via Google Earth Engine.

Earth Engine asset NASA/GLDAS/V022/CLSM/G025/DA1D (= GES DISC GLDAS_CLSM025_DA1_D 2.2), band GWS_tavg
(groundwater storage, mm water equivalent; daily, 0.25 deg, 2003-02 .. ~present with a few months' latency).

Steps (server side in Earth Engine, then locally):
  1. baseline  = per-pixel mean of all daily GWS_tavg, 2004-01-01 .. 2020-12-31 (17 full years; close to the
                 2002-2020 reference of the GRACE/G3P layers already in the app)
  2. monthly   = per-pixel mean of the daily GWS_tavg in each calendar month, 2018-01 .. 2025-12
  3. anomaly   = (monthly - baseline) / 10  -> cm water equivalent
  Each month is downloaded as a small GeoTIFF on the native 0.25 deg grid (EPSG:4326, 51 x 37 px covering the
  South Sudan bbox), put on the shared 0.01 deg grid (nearest) and averaged per county with
  fetch_appeears.county_rows (mean of ~1 km cells inside the county; >=5% valid).

Outputs
  data/processed/gldas_gws_county_monthly.csv   variable gldas_gws_anom_cm
  data/processed/meta/gldas_gws.json
  docs/rasters/gldas_gws/YYYY-MM.png + meta.json  (then: python scripts/raster_trends.py gldas_gws;
       python scripts/recolor_rasters.py gldas_gws gldas_gws_trend; python scripts/recolor_rasters_rwg.py gldas_gws gldas_gws_trend)
  monthly 0.01 deg grids in $GLDAS_WORK/grids/gldas_gws_anom_cm/YYYY-MM.npy (default <scratch>/gldas/work)

Why Earth Engine: GES DISC (hydro1 OPeNDAP, data.gesdisc, s3credentials) and opendap.earthdata.nasa.gov all redirect
to urs.earthdata.nasa.gov, which is unreachable from the build environment, and AppEEARS does not offer GLDAS.

Auth: EE_SERVICE_ACCOUNT_KEY = path to a service-account JSON key (see gee_utils.py). pip install earthengine-api.
Usage: python scripts/gee_gldas_gws.py [--dry-run]
"""
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gee_utils as gu  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ASSET = "NASA/GLDAS/V022/CLSM/G025/DA1D"
BAND = "GWS_tavg"
VAR = "gldas_gws_anom_cm"
KEY = "gldas_gws"
SOURCE = "gldas_gws"
BASE = ("2004-01-01", "2021-01-01")  # end exclusive -> 2004-2020
CRS_TF, DIMS = gu.snapped_grid(0.25)  # native GLDAS 0.25 deg grid, origin (-180, 90)
SCRATCH = os.environ.get("RT_SCRATCH",
                         "/tmp/claude-0/-home-user-yale-nov27-hackathon/b7acc7ce-9c21-59ae-8208-6da6aae060da/scratchpad")
WORK = Path(os.environ.get("GLDAS_WORK", os.path.join(SCRATCH, "gldas", "work")))
SUDD_NOTE = ("Less conclusive in and around the Sudd wetland, where flood water on the surface can be mistaken for "
             "groundwater.")

META = [{
    "id": VAR, "label": "Groundwater storage anomaly (NASA GLDAS-2.2 + GRACE)", "category": "environment",
    "group": "Water storage & groundwater (GRACE)", "units": "cm water",
    "source": "NASA GLDAS-2.2 Catchment Land Surface Model with GRACE/GRACE-FO data assimilation "
              "(GLDAS_CLSM025_DA1_D v2.2, band GWS_tavg) via Google Earth Engine (NASA/GLDAS/V022/CLSM/G025/DA1D)",
    "source_url": "https://doi.org/10.5067/TXBMLX370XX8", "native_resolution": "0.25° (~28 km) model grid; "
    "GRACE information it assimilates is ~300 km", "temporal": "monthly",
    "aggregation": "per-pixel monthly mean of daily groundwater storage minus the pixel's 2004-2020 mean, in cm; "
                   "then mean of ~1 km cells inside the county", "higher_is": "better", "index_ok": False,
    "raster": KEY,
    "notes": ("Groundwater only: the Catchment model splits the GRACE total-storage signal into soil moisture, snow "
              "and groundwater, and this is the groundwater part, as a difference (cm of water) from its own "
              "2004-2020 average. Negative = less groundwater than usual. The model is nudged toward GRACE, so the "
              "detail finer than ~300 km comes from the model and its rainfall forcing, not from the satellite. "
              + SUDD_NOTE),
}]


def run():
    ee = gu.init()
    col = ee.ImageCollection(ASSET).select(BAND)
    tifdir = WORK / "tif"
    base = col.filterDate(*BASE).mean().rename("base").toFloat()
    pb = gu.download(base, ["base"], CRS_TF, DIMS, tifdir / "baseline_2004_2020.tif")
    b, tf = gu.read_bands(pb)
    base_arr = next(iter(b.values()))
    rows = []
    for mk in gu.MONTHS:
        a, e = gu.month_range(mk)
        mc = col.filterDate(a, e)
        n = mc.size().getInfo()
        if n == 0:
            gu.log(mk, "no daily images (not yet published?)")
            continue
        p = gu.download(mc.mean().rename(BAND).toFloat(), [BAND], CRS_TF, DIMS, tifdir / f"gws_{mk}.tif")
        m, tf = gu.read_bands(p)
        arr = next(iter(m.values()))
        anom = ((arr - base_arr) / 10.0).astype("float32")  # mm -> cm
        g = gu.to_grid(anom, tf, "nearest")
        gu.save_grid(WORK, VAR, mk, g)
        rows += gu.fa.county_rows(g, mk, VAR, rnd=3)
        gu.log(f"{mk}: {n} days, SSD median anomaly {np.nanmedian(anom):+.2f} cm")
    write(rows)


def write(rows):
    df = pd.DataFrame(rows, columns=["county_id", "date", "variable", "value"])
    out = ROOT / "data" / "processed" / f"{SOURCE}_county_monthly.csv"
    df.sort_values(["variable", "county_id", "date"]).to_csv(out, index=False)
    (ROOT / "data" / "processed" / "meta" / f"{SOURCE}.json").write_text(json.dumps(META, indent=1, ensure_ascii=False))
    lim = float(np.ceil(np.nanpercentile(np.abs(df.value), 98)))
    gu.render(WORK, [dict(key=KEY, var=VAR, label="Groundwater storage anomaly (GLDAS-2.2 CLSM + GRACE DA)",
                          units="cm water", vmin=-lim, vmax=lim,
                          colors=["#8c510a", "#d8b365", "#f6e8c3", "#f5f5f5", "#c7eae5", "#5ab4ac", "#01665e"],
                          cmap_name="brown-teal (diverging, 0 = 2004-2020 mean)",
                          native="0.25° (~28 km) GLDAS grid, nearest-neighbour",
                          source="NASA GLDAS-2.2 CLSM GRACE-DA (GWS_tavg) via Google Earth Engine")])
    gu.log(f"wrote {out}: {len(df)} rows, {df.county_id.nunique()} counties, {df.date.nunique()} months, "
           f"range {df.value.min():.2f}..{df.value.max():.2f} cm")
    from trend_stats import write_trends
    write_trends(SOURCE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.dry_run:
        print(f"asset {ASSET} band {BAND}; baseline mean {BASE[0]}..{BASE[1]} (excl.)")
        print(f"grid EPSG:4326 crs_transform={CRS_TF} dimensions={DIMS[0]}x{DIMS[1]}")
        print(f"{len(gu.MONTHS)} monthly means {gu.MONTHS[0]}..{gu.MONTHS[-1]} -> {VAR} (cm), raster {KEY}")
        print(f"work dir {WORK}; outputs data/processed/{SOURCE}_county_monthly.csv, meta/{SOURCE}.json")
        ids, lab = gu.fa.label_grid()
        print(f"county label grid OK: {len(ids)} counties")
        return
    run()


if __name__ == "__main__":
    main()
