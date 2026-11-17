#!/usr/bin/env python
"""Rainfall (GPM IMERG V07 monthly, 0.1 deg) and 2 m air temperature (GLDAS-2.1 Noah, 0.25 deg) via Google Earth Engine,
so the county series used for the trend statistics and the map raster come from the SAME grid.

Replaces the county series of `precip_mm` and `tair_c`, which used to come from the Drive table (NASA POWER:
IMERG / MERRA-2 regridded to POWER's 0.5 x 0.625 deg cells). The ids are kept; the POWER versions stay in
data/processed/drive_climate_county_monthly.csv as hidden `precip_mm_power` / `tair_c_power` for provenance.

  precip_mm : NASA/GPM_L3/IMERG_MONTHLY_V07, band `precipitation` (mm/hr, month mean rate) x 24 x days in month
              -> mm/month; native 0.1 deg grid.
  tair_c    : NASA/GLDAS/V021/NOAH/G025/T3H, band `Tair_f_inst` (K, 3-hourly); per-pixel mean of all 3-hourly steps
              in the month - 273.15 -> deg C; native 0.25 deg grid (the finest NASA air-temperature product on GEE
              covering 2018-2025 continuously).

Each month is downloaded on the product's native grid (EPSG:4326, snapped to the global origin), put on the shared
0.01 deg South Sudan grid by nearest neighbour (so every ~1 km cell carries its native cell's value) and averaged per
county with fetch_appeears.county_rows (mean of the ~1 km cells inside the county = area-weighted mean of the native
cells). The 0.01 deg grids are kept in $GEE_CLIMATE_WORK/grids/<var>/YYYY-MM.npy for the map rasters
(scripts/continuous_rasters.py) and the per-pixel trend rasters (scripts/raster_trends.py --continuous).

Outputs: data/processed/gee_climate_county_monthly.csv, data/processed/meta/gee_climate.json, trends via write_trends.
Usage: python scripts/gee_climate_grids.py [--only precip_mm|tair_c]
"""
import argparse
import calendar
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gee_utils as gu  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = os.environ.get("RT_SCRATCH",
                         "/tmp/claude-0/-home-user-yale-nov27-hackathon/b7acc7ce-9c21-59ae-8208-6da6aae060da/scratchpad")
WORK = Path(os.environ.get("GEE_CLIMATE_WORK", os.path.join(SCRATCH, "gee_climate", "work")))
SOURCE = "gee_climate"

PRODUCTS = {
    "precip_mm": dict(asset="NASA/GPM_L3/IMERG_MONTHLY_V07", band="precipitation", res=0.1),
    "tair_c": dict(asset="NASA/GLDAS/V021/NOAH/G025/T3H", band="Tair_f_inst", res=0.25),
}

META = [
    dict(id="precip_mm", label="Precipitation (IMERG)", category="environment", group="Precipitation",
         units="mm/month", temporal="monthly",
         source="NASA GPM IMERG V07 Final, monthly (GPM_3IMERGM) via Google Earth Engine (NASA/GPM_L3/IMERG_MONTHLY_V07)",
         source_url="https://doi.org/10.5067/GPM/IMERG/3B-MONTH/07", native_resolution="0.1° (~11 km)",
         aggregation="monthly mean rate (mm/hr) x 24 x days in month per 0.1° cell; then mean of the ~1 km cells inside "
                     "the county (nearest-neighbour from the 0.1° grid = area-weighted mean of the 0.1° cells)",
         higher_is="better", index_ok=True, raster="imerg_precip",
         notes="Satellite rainfall estimate (microwave + infrared, gauge-calibrated in the Final run). Until Nov 2026 "
               "this series came from NASA POWER's 0.5° x 0.625° regridding of IMERG; it now comes from the native "
               "0.1° grid shown on the map (the POWER version is kept as precip_mm_power, hidden)."),
    dict(id="tair_c", label="Mean air temperature (2 m)", category="environment", group="Temperature",
         units="°C", temporal="monthly",
         source="NASA GLDAS-2.1 Noah land surface model, 3-hourly 0.25° (GLDAS_NOAH025_3H v2.1, Tair_f_inst) via "
                "Google Earth Engine (NASA/GLDAS/V021/NOAH/G025/T3H)",
         source_url="https://doi.org/10.5067/E7TYRXPJKWOQ", native_resolution="0.25° (~28 km)",
         aggregation="per-pixel mean of all 3-hourly near-surface air temperatures in the month (K - 273.15); then mean "
                     "of the ~1 km cells inside the county (nearest-neighbour from the 0.25° grid)",
         higher_is="worse", index_ok=False, raster="gldas_tair",
         notes="Model forcing temperature (GDAS analysis, bias-corrected). Until Nov 2026 this series came from MERRA-2 "
               "via NASA POWER (0.5° x 0.625°); it now comes from the 0.25° GLDAS grid shown on the map (the MERRA-2 "
               "version is kept as tair_c_power, hidden)."),
]


def run(only):
    ee = gu.init()
    rows = []
    for var, P in PRODUCTS.items():
        crs_tf, dims = gu.snapped_grid(P["res"])
        col = ee.ImageCollection(P["asset"]).select(P["band"])
        tifdir = WORK / "tif" / var
        for mk in gu.MONTHS:
            gd = WORK / "grids" / var / f"{mk}.npy"
            if only and var not in only:
                if gd.exists():
                    rows += gu.fa.county_rows(np.load(gd), mk, var, rnd=3)
                continue
            if not gd.exists():
                a, b = gu.month_range(mk)
                mc = col.filterDate(a, b)
                n = mc.size().getInfo()
                if n == 0:
                    gu.log(var, mk, "no images")
                    continue
                p = gu.download(mc.mean().rename(P["band"]).toFloat(), [P["band"]], crs_tf, dims, tifdir / f"{mk}.tif")
                arrs, tf = gu.read_bands(p)
                arr = next(iter(arrs.values()))
                y, m = int(mk[:4]), int(mk[5:])
                if var == "precip_mm":
                    arr = np.where(arr >= 0, arr * 24 * calendar.monthrange(y, m)[1], np.nan)
                else:
                    arr = np.where(arr > 150, arr - 273.15, np.nan)
                g = gu.to_grid(arr.astype("float32"), tf, "nearest")
                gu.save_grid(WORK, var, mk, g)
                gu.log(f"{var} {mk}: {n} images, SSD median {np.nanmedian(arr):.2f}")
            rows += gu.fa.county_rows(np.load(gd), mk, var, rnd=3)
    df = pd.DataFrame(rows, columns=["county_id", "date", "variable", "value"])
    out = ROOT / "data" / "processed" / f"{SOURCE}_county_monthly.csv"
    df.sort_values(["variable", "county_id", "date"]).to_csv(out, index=False)
    (ROOT / "data" / "processed" / "meta" / f"{SOURCE}.json").write_text(json.dumps(META, indent=1, ensure_ascii=False))
    gu.log(f"wrote {out}: {len(df)} rows; " + ", ".join(
        f"{v}: {g.date.nunique()} months {g.date.min()}..{g.date.max()}" for v, g in df.groupby("variable")))
    from trend_stats import write_trends
    write_trends(SOURCE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None)
    a = ap.parse_args()
    run(set(a.only) if a.only else None)


if __name__ == "__main__":
    main()
