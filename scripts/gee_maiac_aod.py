#!/usr/bin/env python
"""Aerosol optical depth at 1 km: MODIS MAIAC MCD19A2 v061 via Google Earth Engine, South Sudan, 2018-01..2025-12.

Replaces the ~50 km NASA POWER / MERRA-2 AOD (power_aod_550) with the 1 km MAIAC retrieval (Terra + Aqua).
Earth Engine asset MODIS/061/MCD19A2_GRANULES, band Optical_Depth_055 (scale 0.001) + AOD_QA.
A retrieval is kept when AOD_QA says: cloud mask = clear (bits 0-2 == 1), adjacency = normal (bits 5-7 == 0) and
AOD quality = best (bits 8-11 == 0). Per pixel, the monthly value is the mean of all kept retrievals in the month
(each overpass granule counts once), computed in Earth Engine and downloaded directly on the shared 0.01 deg grid
of fetch_appeears.py (EPSG:4326, 1260 x 890 px, ~4.5 MB per month), then averaged per county with
fetch_appeears.county_rows (>=5% of the county's cells must have a value).

Why Earth Engine: AppEEARS no longer lists MCD19A2 (checked /api/product), Planetary Computer has no MAIAC, and the
LP DAAC / LAADS archives need an Earthdata (URS) login that the build environment cannot reach.

Outputs: data/processed/maiac_county_monthly.csv (variable maiac_aod_055), data/processed/meta/maiac.json,
         docs/rasters/maiac_aod/YYYY-MM.png + meta.json, grids in $MAIAC_WORK/grids/maiac_aod_055/YYYY-MM.npy.
Then:    python scripts/raster_trends.py maiac_aod
         python scripts/recolor_rasters.py maiac_aod maiac_aod_trend && python scripts/recolor_rasters_rwg.py maiac_aod maiac_aod_trend
Auth:    EE_SERVICE_ACCOUNT_KEY = path to a service-account JSON key (see gee_utils.py).
Usage:   python scripts/gee_maiac_aod.py [--dry-run] [--months 2018-01 ...]
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
ASSET = "MODIS/061/MCD19A2_GRANULES"
VAR, KEY, SOURCE = "maiac_aod_055", "maiac_aod", "maiac"
CRS_TF = [gu.fa.RES, 0.0, gu.BBOX[0], 0.0, -gu.fa.RES, gu.BBOX[3]]  # identical to the AppEEARS 0.01 deg grid
DIMS = (gu.fa.W, gu.fa.H)
SCRATCH = os.environ.get("RT_SCRATCH",
                         "/tmp/claude-0/-home-user-yale-nov27-hackathon/b7acc7ce-9c21-59ae-8208-6da6aae060da/scratchpad")
WORK = Path(os.environ.get("MAIAC_WORK", os.path.join(SCRATCH, "maiac", "work")))

META = [{
    "id": VAR, "label": "Aerosol optical depth 550 nm, 1 km (MODIS MAIAC)", "category": "environment",
    "group": "Air quality", "units": "AOD (unitless)",
    "source": "MODIS Terra+Aqua MAIAC MCD19A2 v061 via Google Earth Engine (MODIS/061/MCD19A2_GRANULES)",
    "source_url": "https://doi.org/10.5067/MODIS/MCD19A2.061", "native_resolution": "1 km", "temporal": "monthly",
    "aggregation": "per-pixel mean of best-quality, cloud-free daily retrievals in the month (0.01° grid), then "
                   "mean of cells with a value inside the county", "higher_is": "worse", "index_ok": True,
    "raster": KEY,
    "notes": ("Haze from dust and smoke, measured by the MODIS satellites at 1 km (about 50 times finer than the "
              "NASA POWER/MERRA-2 value). Only cloud-free, best-quality retrievals are used, so wet-season months "
              "(Jun-Sep) rest on few days and some cells have none; the county value is the mean of cells that "
              "have a value. Dry-season peaks (Dec-Mar) are mostly smoke from burning plus Saharan dust."),
}]


def qa_ok(qa):
    cloud = qa.bitwiseAnd(0b111)
    adj = qa.rightShift(5).bitwiseAnd(0b111)
    q = qa.rightShift(8).bitwiseAnd(0b1111)
    return cloud.eq(1).And(adj.eq(0)).And(q.eq(0))


def run(months):
    ee = gu.init()
    region = ee.Geometry.Rectangle(gu.BBOX, "EPSG:4326", False)
    col = ee.ImageCollection(ASSET).filterBounds(region).select(["Optical_Depth_055", "AOD_QA"])

    def clean(img):
        return img.select("Optical_Depth_055").multiply(0.001).updateMask(qa_ok(img.select("AOD_QA"))) \
            .rename("aod").toFloat()

    rows = []
    for mk in months:
        a, b = gu.month_range(mk)
        mc = col.filterDate(a, b)
        n = mc.size().getInfo()
        if n == 0:
            gu.log(mk, "no granules")
            continue
        img = mc.map(clean).mean().rename("aod")
        p = gu.download(img, ["aod"], CRS_TF, DIMS, WORK / "tif" / f"aod_{mk}.tif")
        arrs, tf = gu.read_bands(p)
        g = next(iter(arrs.values()))
        g = np.where((g >= 0) & (g < 5), g, np.nan).astype("float32")
        if g.shape != (gu.fa.H, gu.fa.W):
            g = gu.to_grid(g, tf, "average")
        gu.save_grid(WORK, VAR, mk, g)
        rows += gu.fa.county_rows(g, mk, VAR, rnd=4)
        gu.log(f"{mk}: {n} granules, valid {np.isfinite(g).mean():.0%}, median AOD {np.nanmedian(g):.3f}")
    return rows


def write(rows):
    out = ROOT / "data" / "processed" / f"{SOURCE}_county_monthly.csv"
    df = pd.DataFrame(rows, columns=["county_id", "date", "variable", "value"])
    if out.exists():  # resumable: keep months fetched earlier
        df = pd.concat([pd.read_csv(out), df]).drop_duplicates(["county_id", "date", "variable"], keep="last")
    df.sort_values(["variable", "county_id", "date"]).to_csv(out, index=False)
    (ROOT / "data" / "processed" / "meta" / f"{SOURCE}.json").write_text(json.dumps(META, indent=1, ensure_ascii=False))
    gu.render(WORK, [dict(key=KEY, var=VAR, label="Aerosol optical depth 550 nm (MODIS MAIAC, 1 km)", units="AOD",
                          vmin=0.0, vmax=1.0, colors=["#ffffe5", "#fee391", "#fec44f", "#fe9929", "#ec7014",
                                                      "#cc4c02", "#8c2d04"], cmap_name="ylorbr",
                          native="1 km MAIAC (0.01° grid)", source="MODIS MCD19A2 v061 via Google Earth Engine")])
    gu.log(f"wrote {out}: {len(df)} rows, {df.county_id.nunique()} counties, {df.date.nunique()} months, "
           f"range {df.value.min():.3f}..{df.value.max():.3f}")
    from trend_stats import write_trends
    write_trends(SOURCE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", nargs="*", default=gu.MONTHS)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.dry_run:
        print(f"asset {ASSET}: Optical_Depth_055 x0.001, QA clear/normal-adjacency/best -> {VAR}")
        print(f"grid EPSG:4326 crs_transform={CRS_TF} dimensions={DIMS[0]}x{DIMS[1]}; {len(a.months)} months")
        print(f"work {WORK}; outputs data/processed/{SOURCE}_county_monthly.csv, meta/{SOURCE}.json, rasters/{KEY}")
        return
    write(run(a.months))


if __name__ == "__main__":
    main()
