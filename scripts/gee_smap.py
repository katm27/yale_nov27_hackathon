#!/usr/bin/env python
"""SMAP L4 soil moisture (surface 0-5 cm, root zone 0-100 cm) from Google Earth Engine, South Sudan, 2018-01..2025-12.

Earth Engine asset NASA/SMAP/SPL4SMGP/008 (3-hourly, 9 km EASE-Grid 2.0), bands sm_surface and sm_rootzone (m3/m3).
For each month: server-side mean of all 3-hourly images in the month, clipped to the South Sudan bbox
[23.4, 3.4, 36.0, 12.3], downloaded as one small 2-band GeoTIFF (EPSG:4326, 0.08 deg ~ 9 km grid, nearest-neighbour
from the native 9 km cells, ~160 x 110 px). Each monthly grid is then put on the shared 0.01 deg grid (nearest, as
fetch_appeears.proc_smap does) and averaged per county with fetch_appeears.county_rows.

Writes exactly what the AppEEARS SMAP path writes, so scripts/finish_smap.sh runs unchanged afterwards:
  $APPEEARS_WORK/grids/smap_sm_surface/YYYY-MM.npy, $APPEEARS_WORK/grids/smap_sm_rootzone/YYYY-MM.npy
  $APPEEARS_WORK/partials/smap_gee_YYYY.csv   (county_id,date,variable,value; ids smap_sm_surface / smap_sm_rootzone)
Years already produced by AppEEARS (partials/smap_YYYY.csv) are skipped unless --replace-appeears is given, in which
case those AppEEARS partials are renamed *.csv.appeears (kept, but ignored by `fetch_appeears.py assemble`).

Auth: EE_SERVICE_ACCOUNT_KEY = path to a service-account JSON key (see gee_utils.py). pip install earthengine-api.
Usage:
  APPEEARS_WORK=<dir> python scripts/gee_smap.py [--years 2020 2021 ...] [--replace-appeears] [--dry-run]
  APPEEARS_WORK=<dir> bash scripts/finish_smap.sh
"""
import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gee_utils as gu  # noqa: E402

ASSET = "NASA/SMAP/SPL4SMGP/008"
BANDS = {"sm_surface": "smap_sm_surface", "sm_rootzone": "smap_sm_rootzone"}
RES = 0.08  # deg, ~9 km
CRS_TF, DIMS = gu.snapped_grid(RES, origin=(gu.BBOX[0], gu.BBOX[3]))


def work():
    return Path(os.environ.get("APPEEARS_WORK", gu.fa.WORK))


def plan(years):
    return [mk for mk in gu.MONTHS if int(mk[:4]) in years]


def run(years, replace, tifdir):
    ee = gu.init()
    W = work()
    pdir = W / "partials"
    pdir.mkdir(parents=True, exist_ok=True)
    col = ee.ImageCollection(ASSET).select(list(BANDS))
    for y in years:
        ae = pdir / f"smap_{y}.csv"
        if ae.exists():
            if not replace:
                gu.log(f"{y}: AppEEARS partial exists, skipped (use --replace-appeears)")
                continue
            ae.rename(ae.with_suffix(".csv.appeears"))
        rows = []
        for mk in plan([y]):
            a, b = gu.month_range(mk)
            mc = col.filterDate(a, b)
            n = mc.size().getInfo()
            if n == 0:
                gu.log(mk, "no images")
                continue
            if n < 0.5 * 8 * 28:
                gu.log(f"{mk}: sparse ({n} 3-hourly steps)")
            img = mc.mean().toFloat()
            p = gu.download(img, list(BANDS), CRS_TF, DIMS, tifdir / f"smap_{mk}.tif")
            arrs, tf = gu.read_bands(p)
            for i, (band, var) in enumerate(BANDS.items()):
                arr = arrs.get(band, arrs.get(str(i + 1)))
                arr = np.where(arr >= 0, arr, np.nan).astype("float32")
                g = gu.to_grid(arr, tf, "nearest")
                gu.save_grid(W, var, mk, g)
                rows += gu.fa.county_rows(g, mk, var)
            gu.log(f"{mk}: {n} steps, surface median {np.nanmedian(arrs.get('sm_surface', arrs.get('1'))):.3f}")
        pd.DataFrame(rows, columns=["county_id", "date", "variable", "value"]).to_csv(pdir / f"smap_gee_{y}.csv",
                                                                                     index=False)
        gu.log(f"{y}: {len(rows)} rows -> {pdir / f'smap_gee_{y}.csv'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs="*", type=int, default=list(range(2018, 2026)))
    ap.add_argument("--replace-appeears", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--tifdir", default=None, help="GeoTIFF cache (default $APPEEARS_WORK/gee_smap_tif)")
    a = ap.parse_args()
    tifdir = Path(a.tifdir) if a.tifdir else work() / "gee_smap_tif"
    if a.dry_run:
        W = work()
        print(f"asset {ASSET} bands {list(BANDS)} -> ids {list(BANDS.values())}")
        print(f"grid EPSG:4326 crs_transform={CRS_TF} dimensions={DIMS[0]}x{DIMS[1]} (~9 km)")
        for y in a.years:
            have = (W / "partials" / f"smap_{y}.csv").exists()
            act = ("skip (AppEEARS done)" if have and not a.replace_appeears else "fetch 12 monthly means")
            print(f"  {y}: {act} -> {W / 'partials' / f'smap_gee_{y}.csv'}")
        print(f"grids -> {W / 'grids'}/smap_sm_*/YYYY-MM.npy ; tifs -> {tifdir}")
        ids, lab = gu.fa.label_grid()
        print(f"county label grid OK: {len(ids)} counties, {lab.shape}")
        return
    run(a.years, a.replace_appeears, tifdir)


if __name__ == "__main__":
    main()
