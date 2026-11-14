#!/usr/bin/env python
"""MODIS land-surface variables for South Sudan counties, 2018-01..2025-12.

Source: Microsoft Planetary Computer STAC (MODIS Collection 6.1 COGs, no login).
Products (tiles h20v07, h20v08, h21v07, h21v08):
  ndvi : MOD13A1 + MYD13A1 (500 m, 16-day)  -> modis_ndvi, modis_evi
  lst  : MOD11A2 (Terra, 1 km, 8-day)        -> modis_lst_day_c, modis_lst_night_c
  refl : MOD09A1 (Terra, 500 m, 8-day)       -> modis_refl_red, modis_refl_nir, modis_refl_swir1
  et   : MOD16A3GF (Terra, 500 m, annual)    -> modis_et_mm   (PC has no 8-day MOD16A2)

Method: every tile asset is read at native resolution, quality-masked, then
area-averaged (rasterio.warp.reproject, Resampling.average, NaN-aware) onto a
common EPSG:4326 0.01 deg (~1.1 km) analysis grid. Composites are assigned to
the calendar month containing their mid-date. Per pixel, months are combined as:
max-value composite for NDVI/EVI, mean for LST/reflectance. County value = mean
of valid grid cells whose centre falls in the county (rasterized label grid).
Counties with < 5 % valid cells in a month are dropped (row absent).

Outputs (resumable; per-month partials in the work dir):
  data/processed/modis_land_county_monthly.csv
  data/processed/meta/modis_land.json
  <work>/grids/<var>/YYYY-MM.npy  (float32 grids used by make_modis_rasters.py)

Usage: python scripts/fetch_modis_land.py [ndvi lst et refl] [--workers 12]
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import planetary_computer as pc
import rasterio
from rasterio import features
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject
from pystac_client import Client

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "5")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")

ROOT = Path(__file__).resolve().parents[1]
WORK = Path(os.environ.get("MODIS_WORK", ROOT / "data" / "raw" / "modis_land" / "work"))
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
BBOX = [23.4, 3.4, 36.0, 12.3]
RES = 0.01
W = int(round((BBOX[2] - BBOX[0]) / RES))
H = int(round((BBOX[3] - BBOX[1]) / RES))
GRID_TF = from_origin(BBOX[0], BBOX[3], RES, RES)
START, END = "2018-01-01", "2025-12-31"
MIN_VALID_FRAC = 0.05


# ---------------------------------------------------------------- QA decoders
def dec_ndvi(a):
    rel = a["500m_16_days_pixel_reliability"]
    ok = (rel == 0) | (rel == 1)  # good / marginal
    out = {}
    for k, v in (("modis_ndvi", "500m_16_days_NDVI"), ("modis_evi", "500m_16_days_EVI")):
        x = a[v].astype("float32")
        out[k] = np.where(ok & (x >= -2000) & (x <= 10000), x * 1e-4, np.nan).astype("float32")
    return out


def dec_lst(a):
    out = {}
    for k, v, q in (("modis_lst_day_c", "LST_Day_1km", "QC_Day"),
                    ("modis_lst_night_c", "LST_Night_1km", "QC_Night")):
        x = a[v].astype("float32")
        qc = a[q]
        mand = qc & 0b11            # 0 good, 1 other quality
        err = (qc >> 6) & 0b11      # LST error: 0 <=1K, 1 <=2K
        ok = (x >= 7500) & (mand <= 1) & (err <= 1)
        out[k] = np.where(ok, x * 0.02 - 273.15, np.nan).astype("float32")
    return out


def dec_refl(a):
    st = a["sur_refl_state_500m"].astype("uint16")
    clear = ((st & 0b11) == 0) & ((st >> 2) & 1 == 0) & ((st >> 8) & 0b11 <= 1) \
        & ((st >> 10) & 1 == 0) & ((st >> 13) & 1 == 0) & (st != 65535)
    out = {}
    for k, v in (("modis_refl_red", "sur_refl_b01"), ("modis_refl_nir", "sur_refl_b02"),
                 ("modis_refl_swir1", "sur_refl_b06")):
        x = a[v].astype("float32")
        out[k] = np.where(clear & (x >= -100) & (x <= 16000), x * 1e-4, np.nan).astype("float32")
    return out


def dec_et(a):
    x = a["ET_500m"].astype("float32")
    # 65529-65535 = fill / non-vegetated classes (water, urban, barren...)
    return {"modis_et_mm": np.where(x < 65500, x * 0.1, np.nan).astype("float32")}


PRODUCTS = {
    "ndvi": dict(collection="modis-13A1-061", platforms=("MOD", "MYD"), half=8,
                 assets=["500m_16_days_NDVI", "500m_16_days_EVI", "500m_16_days_pixel_reliability"],
                 decode=dec_ndvi, combine="max", raster_vars=["modis_ndvi"]),
    "lst": dict(collection="modis-11A2-061", platforms=("MOD",), half=4,
                assets=["LST_Day_1km", "QC_Day", "LST_Night_1km", "QC_Night"],
                decode=dec_lst, combine="mean", raster_vars=["modis_lst_day_c"]),
    "refl": dict(collection="modis-09A1-061", platforms=("MOD",), half=4,
                 assets=["sur_refl_b01", "sur_refl_b02", "sur_refl_b06", "sur_refl_state_500m"],
                 decode=dec_refl, combine="mean", raster_vars=[]),
    "et": dict(collection="modis-16A3GF-061", platforms=("MOD",), half=None,
               assets=["ET_500m"], decode=dec_et, combine="mean", raster_vars=["modis_et_mm"]),
}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def label_grid():
    g = gpd.read_file(ROOT / "data" / "counties.geojson")
    ids = g["district_id"].tolist()
    lab = features.rasterize(((geom, i + 1) for i, geom in enumerate(g.geometry)),
                             out_shape=(H, W), transform=GRID_TF, fill=0, dtype="int32")
    return ids, lab


def period_key(item, half):
    s = pd.Timestamp(item.properties["start_datetime"][:10])
    if half is None:  # annual
        return f"{s.year}-07"
    m = s + pd.Timedelta(days=half)
    return f"{m.year}-{m.month:02d}"


def read_item(item, spec):
    arrs, src_crs, src_tf = {}, None, None
    for k in spec["assets"]:
        for attempt in range(4):
            try:
                with rasterio.open(pc.sign(item.assets[k].href)) as s:
                    arrs[k] = s.read(1)
                    src_crs, src_tf = s.crs, s.transform
                break
            except Exception as e:  # noqa
                if attempt == 3:
                    raise
                time.sleep(3 * (attempt + 1))
    dec = spec["decode"](arrs)
    out = {}
    for k, v in dec.items():
        dst = np.full((H, W), np.nan, dtype="float32")
        reproject(v, dst, src_transform=src_tf, src_crs=src_crs, src_nodata=np.nan,
                  dst_transform=GRID_TF, dst_crs="EPSG:4326", dst_nodata=np.nan,
                  resampling=Resampling.average)
        out[k] = dst
    return out


def run_product(name, workers, client, ids, lab):
    spec = PRODUCTS[name]
    pdir = WORK / "partials" / name
    pdir.mkdir(parents=True, exist_ok=True)
    log(f"[{name}] searching {spec['collection']}")
    items = list(client.search(collections=[spec["collection"]], bbox=BBOX,
                               datetime=f"{START}/{END}").items())
    items = [i for i in items if i.id[:3] in spec["platforms"]]
    groups = {}
    for it in items:
        key = period_key(it, spec["half"])
        if "2018-01" <= key <= "2025-12":
            groups.setdefault(key, []).append(it)
    log(f"[{name}] {len(items)} items in {len(groups)} periods")
    nlab = len(ids) + 1
    tot_cells = np.bincount(lab.ravel(), minlength=nlab).astype(float)
    todo = [k for k in sorted(groups) if not (pdir / f"{k}.csv").exists()]
    with ThreadPoolExecutor(workers) as ex:
        # submit a few periods ahead so the pool stays busy across period boundaries
        pending = {}
        ahead = 3
        for idx, key in enumerate(todo):
            for k2 in todo[idx:idx + ahead]:
                if k2 not in pending:
                    pending[k2] = [ex.submit(read_item, it, spec) for it in groups[k2]]
            futs = pending.pop(key)
            finish_period(name, spec, key, futs, pdir, ids, lab, nlab, tot_cells)


def finish_period(name, spec, key, futs, pdir, ids, lab, nlab, tot_cells):
    part = pdir / f"{key}.csv"
    t0 = time.time()
    acc, cnt = {}, {}
    nfail = 0
    for f in as_completed(futs):
        try:
            res = f.result()
        except Exception as e:  # noqa
            nfail += 1
            log(f"[{name}] {key} read failed: {e}")
            continue
        for v, a in res.items():
            fin = np.isfinite(a)
            if v not in acc:
                acc[v] = np.full((H, W), -np.inf if spec["combine"] == "max" else 0, "float32")
                cnt[v] = np.zeros((H, W), "uint16")
            if spec["combine"] == "max":
                acc[v] = np.where(fin, np.fmax(acc[v], a), acc[v])
            else:
                acc[v][fin] += a[fin]
            cnt[v] += fin
    if nfail:
        log(f"[{name}] {key}: {nfail}/{len(futs)} tile reads failed; not writing partial (rerun to retry)")
        return
    rows = []
    for v in acc:
        grid = np.where(cnt[v] > 0, acc[v] if spec["combine"] == "max" else acc[v] / np.maximum(cnt[v], 1), np.nan).astype("float32")
        if v in spec["raster_vars"]:
            gd = WORK / "grids" / v
            gd.mkdir(parents=True, exist_ok=True)
            np.save(gd / f"{key}.npy", grid)
        fin = np.isfinite(grid)
        s = np.bincount(lab[fin], weights=grid[fin], minlength=nlab)
        n = np.bincount(lab[fin], minlength=nlab)
        for j, cid in enumerate(ids, start=1):
            if n[j] > 0 and n[j] >= MIN_VALID_FRAC * tot_cells[j]:
                rows.append((cid, f"{key}-01", v, round(float(s[j] / n[j]), 4)))
    pd.DataFrame(rows, columns=["county_id", "date", "variable", "value"]).to_csv(part, index=False)
    log(f"[{name}] {key}: {len(futs)} tiles, {len(rows)} rows, {time.time()-t0:.0f}s")

META = [
    dict(id="modis_ndvi", label="NDVI (MODIS vegetation greenness)", group="Vegetation",
         units="index -1..1", src="MOD13A1 + MYD13A1 v061", url="https://planetarycomputer.microsoft.com/dataset/modis-13A1-061",
         res="500 m (aggregated to ~1 km grid)", higher="better", index_ok=True, raster="modis_ndvi",
         agg="per-pixel monthly maximum of 16-day composites (Terra+Aqua, pixel reliability good/marginal), then mean of valid ~1 km cells in county",
         notes="Cloud-masked with pixel_reliability (0/1). Composites assigned to month of their mid-date."),
    dict(id="modis_evi", label="EVI (MODIS enhanced vegetation index)", group="Vegetation",
         units="index -1..1", src="MOD13A1 + MYD13A1 v061", url="https://planetarycomputer.microsoft.com/dataset/modis-13A1-061",
         res="500 m (aggregated to ~1 km grid)", higher="better", index_ok=True, raster=None,
         agg="per-pixel monthly maximum of 16-day composites, then county mean", notes="Same masking as modis_ndvi."),
    dict(id="modis_lst_day_c", label="Land surface temperature, day (MODIS)", group="Temperature",
         units="°C", src="MOD11A2 v061 (Terra, ~10:30 local)", url="https://planetarycomputer.microsoft.com/dataset/modis-11A2-061",
         res="1 km", higher="worse", index_ok=False, raster="modis_lst_day",
         agg="per-pixel monthly mean of clear-sky 8-day composites, then county mean",
         notes="QC: mandatory QA good/other and LST error <= 2 K. Cloudy rainy-season months sample fewer pixels (clear-sky bias)."),
    dict(id="modis_lst_night_c", label="Land surface temperature, night (MODIS)", group="Temperature",
         units="°C", src="MOD11A2 v061 (Terra, ~22:30 local)", url="https://planetarycomputer.microsoft.com/dataset/modis-11A2-061",
         res="1 km", higher="worse", index_ok=False, raster=None,
         agg="per-pixel monthly mean of clear-sky 8-day composites, then county mean", notes="Same QC as day LST."),
    dict(id="modis_et_mm", label="Evapotranspiration, annual (MODIS)", group="Water",
         units="mm/year", src="MOD16A3GF v061 (gap-filled annual)", url="https://planetarycomputer.microsoft.com/dataset/modis-16A3GF-061",
         res="500 m (aggregated to ~1 km grid)", higher="neutral", index_ok=True, raster="modis_et", temporal="annual",
         agg="mean of valid cells in county", notes="Planetary Computer only hosts the annual MOD16A3GF (no 8-day MOD16A2), so ET is annual (date = YYYY-07-01). Open water, urban and barren pixels are fill in MOD16 and excluded (e.g. permanent Sudd open water)."),
    dict(id="modis_refl_red", label="Surface reflectance, red (MODIS band 1)", group="Land surface",
         units="reflectance 0..1", src="MOD09A1 v061 (Terra)", url="https://planetarycomputer.microsoft.com/dataset/modis-09A1-061",
         res="500 m (aggregated to ~1 km grid)", higher="neutral", index_ok=True, raster=None,
         agg="per-pixel monthly mean of clear 8-day composites, then county mean",
         notes="State QA: clear, no shadow, no/low cirrus, no internal cloud, not adjacent to cloud. 620-670 nm."),
    dict(id="modis_refl_nir", label="Surface reflectance, near-infrared (MODIS band 2)", group="Land surface",
         units="reflectance 0..1", src="MOD09A1 v061 (Terra)", url="https://planetarycomputer.microsoft.com/dataset/modis-09A1-061",
         res="500 m (aggregated to ~1 km grid)", higher="neutral", index_ok=True, raster=None,
         agg="per-pixel monthly mean of clear 8-day composites, then county mean", notes="841-876 nm. Same QA as red."),
    dict(id="modis_refl_swir1", label="Surface reflectance, shortwave infrared (MODIS band 6)", group="Land surface",
         units="reflectance 0..1", src="MOD09A1 v061 (Terra)", url="https://planetarycomputer.microsoft.com/dataset/modis-09A1-061",
         res="500 m (aggregated to ~1 km grid)", higher="neutral", index_ok=True, raster=None,
         agg="per-pixel monthly mean of clear 8-day composites, then county mean",
         notes="1628-1652 nm; sensitive to soil/vegetation moisture and burn scars. Same QA as red."),
]


def assemble():
    parts = sorted((WORK / "partials").glob("*/*.csv"))
    df = pd.concat([pd.read_csv(p) for p in parts], ignore_index=True)
    df = df.sort_values(["variable", "county_id", "date"])
    out = ROOT / "data" / "processed" / "modis_land_county_monthly.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    present = set(df["variable"])
    meta = []
    for m in META:
        if m["id"] not in present:
            continue
        d = {"id": m["id"], "label": m["label"], "category": "environment", "group": m["group"],
             "units": m["units"], "source": f"MODIS {m['src']} via Microsoft Planetary Computer",
             "source_url": m["url"], "native_resolution": m["res"], "temporal": m.get("temporal", "monthly"),
             "aggregation": m["agg"], "higher_is": m["higher"], "index_ok": m["index_ok"], "notes": m["notes"]}
        if m["raster"]:
            d["raster"] = m["raster"]
        meta.append(d)
    mp = ROOT / "data" / "processed" / "meta" / "modis_land.json"
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    log(f"wrote {out} ({len(df)} rows) and {mp}")
    print(df.groupby("variable").agg(n=("value", "size"), counties=("county_id", "nunique"),
                                      months=("date", "nunique"), vmin=("value", "min"),
                                      vmed=("value", "median"), vmax=("value", "max")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("products", nargs="*", default=["ndvi", "lst", "et", "refl"])
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--assemble-only", action="store_true")
    a = ap.parse_args()
    if not a.assemble_only:
        ids, lab = label_grid()
        client = Client.open(STAC)
        for p in a.products:
            run_product(p, a.workers, client, ids, lab)
    assemble()


if __name__ == "__main__":
    main()
