#!/usr/bin/env python
"""NASA AppEEARS pull for South Sudan counties, 2018-01..2025-12.

AppEEARS (https://appeears.earthdatacloud.nasa.gov/api/) area requests, clipped to the
South Sudan outline (dissolved data/counties.geojson), GeoTIFF / NetCDF4 in geographic
(EPSG:4326) projection. Credentials are read from EARTHDATA_USERNAME / EARTHDATA_PASSWORD.

Stages (all resumable; state lives in $APPEEARS_WORK, default data/raw/appeears/_cache):
  submit   -> submits one area task per entry in TASKS, task ids saved to <work>/tasks.json
  status   -> prints task status
  process  -> for every finished task: downloads bundle files one at a time, aggregates
              them to county x month on a common 0.01 deg grid, saves monthly grids
              (<work>/grids/<var>/YYYY-MM.npy) for overlays and deletes the GeoTIFFs
  assemble -> writes data/processed/appeears_county_monthly.csv + meta/appeears.json,
              renders docs/rasters/<key>/ overlays and an overlap comparison against
              the existing Planetary Computer series (<work>/consistency.json)

Products
  MOD16A2GF.061  ET_500m (8-day, gap-filled)        -> modis_et_monthly_mm (monthly total)
  MOD13A3.061    monthly 1 km NDVI/EVI              -> modis13a3_ndvi, modis13a3_evi
  MOD11A2.061    8-day LST day/night (2022-2025)    -> appeears_lst_day_c / _night_c
  MCD64A1.061    monthly burned area                -> appeears_burned_area_km2 / _pct
  SPL4SMGP.008   SMAP L4 3-hourly surface/rootzone  -> smap_sm_surface, smap_sm_rootzone

VIIRS Black Marble (VNP46A3) night lights are NOT offered by AppEEARS (checked /api/product),
nor is any GRACE/GRACE-FO or GLDAS product.

Usage: python scripts/fetch_appeears.py [submit|status|process|assemble|all] [--only NAME ...]
"""
import argparse
import calendar
import datetime as dt
import json
import os
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
WORK = Path(os.environ.get("APPEEARS_WORK", ROOT / "data" / "raw" / "appeears" / "_cache"))
API = "https://appeears.earthdatacloud.nasa.gov/api"
BBOX = [23.4, 3.4, 36.0, 12.3]
RES = 0.01
W = int(round((BBOX[2] - BBOX[0]) / RES))
H = int(round((BBOX[3] - BBOX[1]) / RES))
MONTHS = [f"{y}-{m:02d}" for y in range(2018, 2026) for m in range(1, 13)]
MIN_VALID_FRAC = 0.05


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def _d(s):  # YYYY-MM-DD -> MM-DD-YYYY (AppEEARS date format)
    y, m, d = s.split("-")
    return f"{m}-{d}-{y}"


def _tasks():
    T = []
    for y in range(2018, 2026):
        T.append(dict(name=f"et_{y}", product="MOD16A2GF.061", layers=["ET_500m"],
                      start=f"{y}-01-01", end=f"{y}-12-31", fmt="geotiff"))
    T.append(dict(name="ndvi13a3", product="MOD13A3.061",
                  layers=["_1_km_monthly_NDVI", "_1_km_monthly_EVI", "_1_km_monthly_pixel_reliability"],
                  start="2018-01-01", end="2025-12-31", fmt="geotiff"))
    T.append(dict(name="lst_2022_2025", product="MOD11A2.061",
                  layers=["LST_Day_1km", "QC_Day", "LST_Night_1km", "QC_Night"],
                  start="2022-01-01", end="2025-12-31", fmt="geotiff"))
    for a, b in (("2018-01-01", "2021-12-31"), ("2022-01-01", "2025-12-31")):
        T.append(dict(name=f"burn_{a[:4]}", product="MCD64A1.061", layers=["Burn_Date", "QA"],
                      start=a, end=b, fmt="geotiff"))
    for y in range(2018, 2026):
        T.append(dict(name=f"smap_{y}", product="SPL4SMGP.008",
                      layers=["Geophysical_Data_sm_surface", "Geophysical_Data_sm_rootzone"],
                      start=f"{y}-01-01", end=f"{y}-12-31", fmt="netcdf4"))
    return T


TASKS = _tasks()


# ------------------------------------------------------------------ API helpers
class Api:
    def __init__(self):
        self.s = requests.Session()
        self.login()

    def login(self):
        r = requests.post(f"{API}/login", auth=(os.environ["EARTHDATA_USERNAME"],
                                                 os.environ["EARTHDATA_PASSWORD"]), timeout=60)
        r.raise_for_status()
        self.s.headers["Authorization"] = "Bearer " + r.json()["token"]

    def req(self, method, path, **kw):
        for attempt in range(6):
            try:
                r = self.s.request(method, f"{API}/{path}", timeout=kw.pop("timeout", 120), **kw)
                if r.status_code == 401 or r.status_code == 403:
                    self.login()
                    continue
                if r.status_code >= 500 or r.status_code == 429:
                    raise requests.HTTPError(f"{r.status_code}: {r.text[:200]}")
                r.raise_for_status()
                return r
            except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
                if attempt == 5:
                    raise
                log("retry", path, e)
                time.sleep(10 * (attempt + 1))


def outline_geojson():
    import geopandas as gpd
    g = gpd.read_file(ROOT / "data" / "counties.geojson")
    geom = g.geometry.union_all().buffer(0.02).simplify(0.01)
    return {"type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": {}, "geometry": geom.__geo_interface__}]}


def state():
    p = WORK / "tasks.json"
    return json.loads(p.read_text()) if p.exists() else {}


def save_state(st):
    WORK.mkdir(parents=True, exist_ok=True)
    tmp = WORK / "tasks.json.tmp"
    tmp.write_text(json.dumps(st, indent=1))
    tmp.replace(WORK / "tasks.json")


def submit(api, only=None):
    st = state()
    gj = outline_geojson()
    for t in TASKS:
        if only and t["name"] not in only:
            continue
        if t["name"] in st and st[t["name"]].get("task_id"):
            continue
        body = {"task_type": "area", "task_name": f"ssd_{t['name']}",
                "params": {"dates": [{"startDate": _d(t["start"]), "endDate": _d(t["end"])}],
                           "layers": [{"product": t["product"], "layer": L} for L in t["layers"]],
                           "geo": gj,
                           "output": {"format": {"type": t["fmt"]}, "projection": "geographic"}}}
        r = api.req("POST", "task", json=body)
        tid = r.json()["task_id"]
        st[t["name"]] = {"task_id": tid, "product": t["product"], "submitted": time.strftime("%Y-%m-%d %H:%M")}
        save_state(st)
        log("submitted", t["name"], tid)


def status(api):
    st = state()
    for name, v in st.items():
        r = api.req("GET", f"task/{v['task_id']}").json()
        v["status"] = r.get("status")
        log(f"{name:16s} {v['task_id']} {r.get('status')} {r.get('progress', {}).get('summary', '')}"
            f" processed={v.get('processed', False)}")
    save_state(st)
    return st


# ------------------------------------------------------------------ download
def bundle_files(api, tid):
    return api.req("GET", f"bundle/{tid}").json()["files"]


def download(api, tid, f, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size == f.get("file_size", -1):
        return dest
    for attempt in range(6):
        try:
            with api.s.get(f"{API}/bundle/{tid}/{f['file_id']}", stream=True, timeout=300,
                           allow_redirects=True) as r:
                if r.status_code in (401, 403):
                    api.login()
                    raise requests.HTTPError(str(r.status_code))
                r.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + ".part")
                with open(tmp, "wb") as fh:
                    for chunk in r.iter_content(1 << 20):
                        fh.write(chunk)
                tmp.replace(dest)
            return dest
        except Exception as e:  # noqa
            if attempt == 5:
                raise
            log("download retry", f["file_name"], e)
            time.sleep(5 * (attempt + 1))


# ------------------------------------------------------------------ grids
_LAB = None


def label_grid():
    global _LAB
    if _LAB is None:
        import geopandas as gpd
        from rasterio import features
        from rasterio.transform import from_origin
        g = gpd.read_file(ROOT / "data" / "counties.geojson")
        ids = g["district_id"].tolist()
        lab = features.rasterize(((geom, i + 1) for i, geom in enumerate(g.geometry)),
                                 out_shape=(H, W), transform=from_origin(BBOX[0], BBOX[3], RES, RES),
                                 fill=0, dtype="int32")
        _LAB = (ids, lab)
    return _LAB


def grid_tf():
    from rasterio.transform import from_origin
    return from_origin(BBOX[0], BBOX[3], RES, RES)


def cell_area_km2():
    lat = BBOX[3] - RES * (np.arange(H) + 0.5)
    a = (RES * 111.32) ** 2 * np.cos(np.radians(lat))
    return np.repeat(a[:, None], W, axis=1).astype("float64")


def to_grid(arr, tf, crs="EPSG:4326", resampling="average"):
    from rasterio.warp import Resampling, reproject
    dst = np.full((H, W), np.nan, dtype="float32")
    reproject(arr.astype("float32"), dst, src_transform=tf, src_crs=crs, src_nodata=np.nan,
              dst_transform=grid_tf(), dst_crs="EPSG:4326", dst_nodata=np.nan,
              resampling=getattr(Resampling, resampling))
    return dst


def read_tif(path):
    import rasterio
    with rasterio.open(path) as s:
        return s.read(1), s.transform, s.nodata


def county_rows(grid, key, var, rnd=4, mode="mean"):
    ids, lab = label_grid()
    nlab = len(ids) + 1
    tot = np.bincount(lab.ravel(), minlength=nlab).astype(float)
    fin = np.isfinite(grid)
    s = np.bincount(lab[fin], weights=grid[fin].astype("float64"), minlength=nlab)
    n = np.bincount(lab[fin], minlength=nlab)
    rows = []
    for j, cid in enumerate(ids, start=1):
        if n[j] > 0 and n[j] >= MIN_VALID_FRAC * tot[j]:
            v = s[j] / n[j] if mode == "mean" else s[j]
            rows.append((cid, f"{key}-01", var, round(float(v), rnd)))
    return rows


def save_grid(var, key, grid):
    d = WORK / "grids" / var
    d.mkdir(parents=True, exist_ok=True)
    np.save(d / f"{key}.npy", grid.astype("float32"))


DOY = re.compile(r"_doy(\d{4})(\d{3})")


def fdate(name):
    m = DOY.search(name)
    return dt.date(int(m.group(1)), 1, 1) + dt.timedelta(days=int(m.group(2)) - 1)


def mkey(d):
    return f"{d.year}-{d.month:02d}"


# ------------------------------------------------------------------ per-product processors
# Each takes (api, name, tid, files, tmpdir) and returns a list of county rows.
# GeoTIFFs are downloaded one (or a few) at a time and deleted after use.

def _fetch_group(api, tid, files, tmpdir):
    paths = []
    for f in files:
        paths.append(download(api, tid, f, tmpdir / f["file_name"]))
    return paths


def _cleanup(paths):
    for p in paths:
        try:
            p.unlink()
        except FileNotFoundError:
            pass


def proc_et(api, name, tid, files, tmpdir):
    """MOD16A2GF 8-day ET totals -> calendar-month totals (prorated by day overlap)."""
    tifs = sorted([f for f in files if f["file_name"].endswith(".tif") and "_ET_500m_" in f["file_name"]],
                  key=lambda f: fdate(f["file_name"]))
    acc, vdays = {}, {}
    for f in tifs:
        d0 = fdate(f["file_name"])
        yend = dt.date(d0.year, 12, 31)
        L = min(8, (yend - d0).days + 1)
        p = download(api, tid, f, tmpdir / f["file_name"])
        a, tf, nod = read_tif(p)
        raw = np.issubdtype(a.dtype, np.integer)
        a = a.astype("float32")
        # raw int16 (scale 0.1, kg/m2/8day); 32761-32767 = fill / non-vegetated classes
        if raw:
            a = np.where((a >= 0) & (a < 32700), a * 0.1, np.nan)
        else:  # already scaled
            a = np.where((a >= 0) & (a < 3270), a, np.nan)
        g = to_grid(a, tf)
        _cleanup([p])
        for k in range(L):
            day = d0 + dt.timedelta(days=k)
            mk = mkey(day)
            if mk not in acc:
                acc[mk] = np.zeros((H, W), "float32")
                vdays[mk] = np.zeros((H, W), "uint8")
            fin = np.isfinite(g)
            acc[mk][fin] += g[fin] / L
            vdays[mk] += fin.astype("uint8")
        log(f"[{name}] {d0} L={L}")
    rows = []
    for mk in sorted(acc):
        ndays = calendar.monthrange(int(mk[:4]), int(mk[5:]))[1]
        ok = vdays[mk] >= 0.75 * ndays
        grid = np.where(ok, acc[mk] / np.maximum(vdays[mk], 1) * ndays, np.nan).astype("float32")
        save_grid("modis_et_monthly_mm", mk, grid)
        rows += county_rows(grid, mk, "modis_et_monthly_mm", 2)
    return rows


def proc_ndvi13a3(api, name, tid, files, tmpdir):
    by = {}
    for f in files:
        if f["file_name"].endswith(".tif") and "_doy" in f["file_name"]:
            by.setdefault(fdate(f["file_name"]), []).append(f)
    rows = []
    for d0 in sorted(by):
        mk = mkey(d0)
        fl = {("rel" if "pixel_reliability" in f["file_name"] else "evi" if "_EVI_" in f["file_name"] else "ndvi"): f
              for f in by[d0] if any(s in f["file_name"] for s in ("pixel_reliability", "_EVI_", "_NDVI_"))}
        paths = {k: download(api, tid, f, tmpdir / f["file_name"]) for k, f in fl.items()}
        rel, tf, _ = read_tif(paths["rel"])
        ok = (rel == 0) | (rel == 1)
        for k in ("ndvi", "evi"):
            a, tf, _ = read_tif(paths[k])
            raw = np.issubdtype(a.dtype, np.integer)
            a = a.astype("float32")
            if raw:
                a = a * 1e-4
            a = np.where(ok & (a >= -0.2) & (a <= 1.0), a, np.nan)
            g = to_grid(a, tf)
            var = f"modis13a3_{k}"
            if k == "ndvi":
                save_grid(var, mk, g)
            rows += county_rows(g, mk, var)
        _cleanup(paths.values())
        log(f"[{name}] {mk}")
    return rows


def proc_lst(api, name, tid, files, tmpdir):
    """MOD11A2 8-day LST, same QC + month-of-mid-date assignment as fetch_modis_land.py."""
    by = {}
    for f in files:
        if f["file_name"].endswith(".tif") and "_doy" in f["file_name"]:
            by.setdefault(fdate(f["file_name"]), []).append(f)
    acc = {}
    for d0 in sorted(by):
        mk = mkey(d0 + dt.timedelta(days=4))
        fl = {}
        for f in by[d0]:
            for k in ("LST_Day_1km", "QC_Day", "LST_Night_1km", "QC_Night"):
                if f"_{k}_" in f["file_name"]:
                    fl[k] = f
        paths = {k: download(api, tid, f, tmpdir / f["file_name"]) for k, f in fl.items()}
        for var, lk, qk in (("appeears_lst_day_c", "LST_Day_1km", "QC_Day"),
                            ("appeears_lst_night_c", "LST_Night_1km", "QC_Night")):
            x, tf, _ = read_tif(paths[lk])
            qc, _, _ = read_tif(paths[qk])
            x = x.astype("float32")
            qc = qc.astype("int64")
            if np.nanmax(x) < 1000:  # already scaled to K
                x = x / 0.02
            ok = (x >= 7500) & ((qc & 0b11) <= 1) & (((qc >> 6) & 0b11) <= 1)
            g = to_grid(np.where(ok, x * 0.02 - 273.15, np.nan), tf)
            s, n = acc.setdefault((var, mk), [np.zeros((H, W), "float32"), np.zeros((H, W), "uint8")])
            fin = np.isfinite(g)
            s[fin] += g[fin]
            n += fin.astype("uint8")
        _cleanup(paths.values())
        log(f"[{name}] {d0} -> {mk}")
    rows = []
    for (var, mk), (s, n) in sorted(acc.items()):
        g = np.where(n > 0, s / np.maximum(n, 1), np.nan)
        rows += county_rows(g, mk, var)
    return rows


def proc_burn(api, name, tid, files, tmpdir):
    ids, lab = label_grid()
    nlab = len(ids) + 1
    area = cell_area_km2()
    county_area = np.bincount(lab.ravel(), weights=area.ravel(), minlength=nlab)
    by = {}
    for f in files:
        if f["file_name"].endswith(".tif") and "_Burn_Date_" in f["file_name"]:
            by[fdate(f["file_name"])] = f
    rows = []
    for d0 in sorted(by):
        mk = mkey(d0)
        p = download(api, tid, by[d0], tmpdir / by[d0]["file_name"])
        a, tf, _ = read_tif(p)
        # Burn_Date: 1-366 burned, 0 unburned, -1 unmapped, -2 water; fill outside polygon
        b = np.where(a > 0, 1.0, np.where((a == 0) | (a == -1) | (a == -2), 0.0, np.nan)).astype("float32")
        mapped = np.where(a >= 0, 1.0, np.where((a == -1) | (a == -2), 0.0, np.nan)).astype("float32")
        g = to_grid(b, tf)
        gm = to_grid(mapped, tf)
        _cleanup([p])
        fin = np.isfinite(g)
        km2 = np.bincount(lab[fin], weights=(g[fin] * area[fin]), minlength=nlab)
        mfrac = np.bincount(lab[np.isfinite(gm)], weights=(gm * area)[np.isfinite(gm)], minlength=nlab)
        for j, cid in enumerate(ids, start=1):
            if county_area[j] > 0 and mfrac[j] >= 0.5 * county_area[j]:
                rows.append((cid, f"{mk}-01", "appeears_burned_area_km2", round(float(km2[j]), 3)))
                rows.append((cid, f"{mk}-01", "appeears_burned_area_pct",
                             round(float(100 * km2[j] / county_area[j]), 4)))
        log(f"[{name}] {mk} SS total km2 {km2.sum():.0f}")
    return rows


def proc_smap(api, name, tid, files, tmpdir):
    """SPL4SMGP 3-hourly NetCDF4 -> per-pixel monthly mean -> county mean."""
    import xarray as xr
    from rasterio.transform import from_origin
    ncs = [f for f in files if f["file_name"].endswith(".nc")]
    paths = _fetch_group(api, tid, ncs, tmpdir)
    rows = []
    for p in paths:
        ds = xr.open_dataset(p, decode_times=True)
        lat = ds["lat"].values
        lon = ds["lon"].values
        tf = from_origin(lon[0] - (lon[1] - lon[0]) / 2, lat[0] - (lat[1] - lat[0]) / 2,
                         lon[1] - lon[0], lat[0] - lat[1])
        flip = lat[0] < lat[-1]
        for v, var in (("Geophysical_Data_sm_surface", "smap_sm_surface"),
                       ("Geophysical_Data_sm_rootzone", "smap_sm_rootzone")):
            if v not in ds:
                continue
            da = ds[v].where(ds[v] >= 0)
            mon = da.resample(time="MS").mean("time", skipna=True)
            cnt = da.notnull().resample(time="MS").sum("time")
            for t in range(mon.sizes["time"]):
                mk = str(mon["time"].values[t])[:7]
                arr = mon.isel(time=t).values.astype("float32")
                if flip:
                    arr = arr[::-1]
                if int(cnt.isel(time=t).max()) < 0.5 * 8 * 28:
                    log(f"[{name}] {var} {mk}: sparse ({int(cnt.isel(time=t).max())} steps)")
                g = to_grid(arr, tf, resampling="nearest")
                save_grid(var, mk, g)
                rows += county_rows(g, mk, var)
        ds.close()
        log(f"[{name}] {p.name}")
    _cleanup(paths)
    return rows


PROCESSORS = {"et": proc_et, "ndvi13a3": proc_ndvi13a3, "lst": proc_lst, "burn": proc_burn, "smap": proc_smap}


def process(api, only=None):
    st = state()
    pdir = WORK / "partials"
    pdir.mkdir(parents=True, exist_ok=True)
    for name, v in st.items():
        if only and name not in only:
            continue
        if (pdir / f"{name}.csv").exists():
            continue
        r = api.req("GET", f"task/{v['task_id']}").json()
        if r.get("status") != "done":
            log(f"{name}: {r.get('status')}")
            continue
        files = bundle_files(api, v["task_id"])
        tmpdir = WORK / "tmp" / name
        fn = PROCESSORS[name.split("_")[0]]
        log(f"processing {name}: {len(files)} files, {sum(f.get('file_size', 0) for f in files)/1e9:.2f} GB")
        rows = fn(api, name, v["task_id"], files, tmpdir)
        # keep small provenance files (README / csv lists), drop the rest
        for f in files:
            if f["file_name"].endswith((".txt", ".json", ".xml")) and f.get("file_size", 0) < 5e6:
                try:
                    download(api, v["task_id"], f, WORK / "bundle_meta" / name / Path(f["file_name"]).name)
                except Exception:  # noqa
                    pass
        shutil.rmtree(tmpdir, ignore_errors=True)
        pd.DataFrame(rows, columns=["county_id", "date", "variable", "value"]).to_csv(pdir / f"{name}.csv", index=False)
        st = state()
        st[name]["processed"] = True
        save_state(st)
        log(f"{name}: {len(rows)} rows")


# ------------------------------------------------------------------ consistency vs existing series
# (new appeears variable, existing variable, existing csv, gap-fill target id if comparable)
COMPARE = [
    ("modis13a3_ndvi", "modis_ndvi", "modis_land_county_monthly.csv"),
    ("modis13a3_evi", "modis_evi", "modis_land_county_monthly.csv"),
    ("appeears_lst_day_c", "modis_lst_day_c", "modis_land_county_monthly.csv"),
    ("appeears_lst_night_c", "modis_lst_night_c", "modis_land_county_monthly.csv"),
    ("appeears_burned_area_km2", "burned_area_km2", "fire_county_monthly.csv"),
    ("appeears_burned_area_pct", "burned_area_pct", "fire_county_monthly.csv"),
]
# Same product, same QA/aggregation as the existing pipeline -> gap months may reuse the existing id
SPLICE_IF_OK = {"appeears_lst_day_c", "appeears_lst_night_c", "appeears_burned_area_km2", "appeears_burned_area_pct"}


def consistency(df):
    out = {}
    gaps = []
    for new, old, csv in COMPARE:
        a = df[df.variable == new]
        if a.empty or not (ROOT / "data" / "processed" / csv).exists():
            continue
        b = pd.read_csv(ROOT / "data" / "processed" / csv)
        b = b[b.variable == old]
        m = a.merge(b, on=["county_id", "date"], suffixes=("_new", "_old"))
        x, y = m.value_new.to_numpy(float), m.value_old.to_numpy(float)
        r = float(np.corrcoef(x, y)[0, 1]) if len(m) > 2 else float("nan")
        slope, icpt = (np.polyfit(y, x, 1) if len(m) > 2 else (np.nan, np.nan))
        # national monthly totals/means
        agg = "sum" if old.endswith("km2") else "mean"
        na = m.groupby("date")[["value_new", "value_old"]].agg(agg)
        rn = float(np.corrcoef(na.value_new, na.value_old)[0, 1]) if len(na) > 2 else float("nan")
        res = {"existing": old, "n_overlap": int(len(m)), "months_overlap": int(m.date.nunique()),
               "pearson_r_county_month": round(r, 4), "national_series_r": round(rn, 4),
               "mean_bias_new_minus_old": round(float(np.mean(x - y)), 4),
               "mean_old": round(float(np.mean(y)), 4), "mean_new": round(float(np.mean(x)), 4),
               "ols_new_on_old": [round(float(slope), 4), round(float(icpt), 4)],
               "rmse": round(float(np.sqrt(np.mean((x - y) ** 2))), 4)}
        if old.endswith("km2"):
            res["ratio_of_totals_new_over_old"] = round(float(x.sum() / y.sum()), 4) if y.sum() else None
        ok = new in SPLICE_IF_OK and r >= 0.95 and (
            abs(res["mean_bias_new_minus_old"]) <= (0.5 if "lst" in new else 0.1 * max(abs(res["mean_old"]), 1e-9)))
        res["spliced_gap_months_under_existing_id"] = bool(ok)
        if ok:
            have = set(b.date)
            g = a[~a.date.isin(have)].copy()
            g["variable"] = old
            res["gap_months_filled"] = sorted(g.date.str[:7].unique().tolist())
            gaps.append(g)
        else:
            res["gap_months_available"] = sorted(set(a.date.str[:7]) - set(b.date.str[:7]))
        out[new] = res
    # monthly ET vs annual MOD16A3GF
    a = df[df.variable == "modis_et_monthly_mm"].copy()
    p = ROOT / "data" / "processed" / "modis_land_county_monthly.csv"
    if len(a) and p.exists():
        b = pd.read_csv(p)
        b = b[b.variable == "modis_et_mm"].copy()
        a["year"] = a.date.str[:4]
        cnt = a.groupby(["county_id", "year"]).value.count()
        s = a.groupby(["county_id", "year"]).value.sum()[cnt == 12].rename("new").reset_index()
        b["year"] = b.date.str[:4]
        m = s.merge(b[["county_id", "year", "value"]], on=["county_id", "year"])
        if len(m) > 2:
            out["modis_et_monthly_mm (annual sum)"] = {
                "existing": "modis_et_mm (MOD16A3GF annual)", "n_overlap": int(len(m)),
                "pearson_r_county_year": round(float(np.corrcoef(m.new, m.value)[0, 1]), 4),
                "mean_bias_new_minus_old": round(float((m.new - m.value).mean()), 2),
                "ratio": round(float(m.new.sum() / m.value.sum()), 4)}
    return out, (pd.concat(gaps, ignore_index=True) if gaps else None)


# ------------------------------------------------------------------ rasters
RASTERS = [
    dict(key="modis_et_monthly", var="modis_et_monthly_mm", label="Evapotranspiration, monthly (MODIS MOD16A2GF)",
         units="mm/month", vmin=0.0, vmax=150.0,
         colors=["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"], cmap_name="blues",
         native="500 m MODIS (8-day, gap-filled), rendered from ~1 km (0.01°) grid",
         source="MODIS MOD16A2GF v061 via NASA AppEEARS"),
    dict(key="modis13a3_ndvi", var="modis13a3_ndvi", label="NDVI, monthly 1 km (MODIS MOD13A3)",
         units="NDVI", vmin=0.1, vmax=0.9,
         colors=["#7f4a10", "#b8863b", "#e3cf8c", "#d9ef8b", "#91cf60", "#3f9a3f", "#145a24", "#06331a"],
         cmap_name="brown-yellow-green", native="1 km MODIS (0.01° grid)",
         source="MODIS MOD13A3 v061 via NASA AppEEARS"),
    dict(key="smap_sm_surface", var="smap_sm_surface", label="Surface soil moisture 0-5 cm (SMAP L4)",
         units="m³/m³", vmin=0.0, vmax=0.45,
         colors=["#8c510a", "#d8b365", "#f6e8c3", "#c7eae5", "#5ab4ac", "#01665e", "#003c30"], cmap_name="brown-teal",
         native="9 km (SMAP L4 EASE-Grid 2.0)", source="SMAP SPL4SMGP v008 via NASA AppEEARS"),
    dict(key="smap_sm_rootzone", var="smap_sm_rootzone", label="Root-zone soil moisture 0-100 cm (SMAP L4)",
         units="m³/m³", vmin=0.0, vmax=0.45,
         colors=["#8c510a", "#d8b365", "#f6e8c3", "#c7eae5", "#5ab4ac", "#01665e", "#003c30"], cmap_name="brown-teal",
         native="9 km (SMAP L4 EASE-Grid 2.0)", source="SMAP SPL4SMGP v008 via NASA AppEEARS"),
]


def render_rasters(width=900, levels=48):
    import geopandas as gpd
    from matplotlib.colors import LinearSegmentedColormap
    from PIL import Image
    from rasterio import features
    from rasterio.transform import from_bounds
    from rasterio.warp import Resampling, reproject, transform_bounds
    g = gpd.read_file(ROOT / "data" / "counties.geojson")
    w, s, e, n = g.total_bounds
    w, s, e, n = w - 0.05, s - 0.05, e + 0.05, n + 0.05
    mx0, my0, mx1, my1 = transform_bounds("EPSG:4326", "EPSG:3857", w, s, e, n)
    height = int(round(width * (my1 - my0) / (mx1 - mx0)))
    dtf = from_bounds(mx0, my0, mx1, my1, width, height)
    inside = features.rasterize(((geom, 1) for geom in g.to_crs("EPSG:3857").geometry), out_shape=(height, width),
                                transform=dtf, fill=0, dtype="uint8").astype(bool)
    only = [k for k in os.environ.get("APPEEARS_RENDER", "").split(",") if k]
    for L in RASTERS:
        if only and L["key"] not in only:
            continue
        files = sorted((WORK / "grids" / L["var"]).glob("*.npy"))
        if not files:
            continue
        od = ROOT / "docs" / "rasters" / L["key"]
        od.mkdir(parents=True, exist_ok=True)
        cmap = LinearSegmentedColormap.from_list(L["key"], L["colors"])
        ramp = (cmap(np.linspace(0, 1, 254))[:, :3] * 255).astype("uint8")
        pal = np.zeros((256, 3), "uint8")
        pal[1:255] = ramp
        pal[255] = (190, 190, 190)
        alpha = bytes([0] + [255] * 254 + [110])
        dates, sizes = [], []
        for f in files:
            if not ("2018-01" <= f.stem <= "2025-12"):
                continue
            grid = np.load(f)
            dst = np.full((height, width), np.nan, "float32")
            reproject(grid, dst, src_transform=grid_tf(), src_crs="EPSG:4326", src_nodata=np.nan,
                      dst_transform=dtf, dst_crs="EPSG:3857", dst_nodata=np.nan, resampling=Resampling.average)
            if L.get("log"):
                t = (np.log10(np.clip(dst, L["vmin"], None)) - np.log10(L["vmin"])) / (np.log10(L["vmax"]) - np.log10(L["vmin"]))
            else:
                t = (dst - L["vmin"]) / (L["vmax"] - L["vmin"])
            t = np.clip(t, 0, 1)
            q = np.minimum(np.floor(t * levels), levels - 1) / (levels - 1)
            idx = np.where(np.isfinite(dst), 1 + np.round(np.nan_to_num(q) * 253), 255).astype("uint8")
            idx[~inside] = 0
            im = Image.fromarray(idx, mode="P")
            im.putpalette(pal.ravel().tolist())
            p = od / f"{f.stem}.png"
            im.save(p, optimize=True, transparency=alpha)
            sizes.append(p.stat().st_size)
            dates.append(f.stem)
        meta = {"key": L["key"], "label": L["label"], "units": L["units"],
                "bounds": [[round(s, 5), round(w, 5)], [round(n, 5), round(e, 5)]],
                "vmin": L["vmin"], "vmax": L["vmax"], "colormap": L["cmap_name"],
                "colors": ["#%02x%02x%02x" % tuple(c) for c in ramp[::25]] + ["#%02x%02x%02x" % tuple(ramp[-1])],
                "scale": "log10" if L.get("log") else "linear",
                "nodata_color": "#bebebe (semi-transparent: no valid retrieval / fill e.g. open water)",
                "native_resolution": L["native"], "dates": dates, "source": L["source"],
                "crs": "EPSG:3857", "width": width, "height": height}
        (od / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
        log(f"raster {L['key']}: {len(dates)} images, max {max(sizes)/1e3:.0f} KB")


# ------------------------------------------------------------------ metadata
AE = "https://appeears.earthdatacloud.nasa.gov/"


def _m(id, label, group, units, src, url, res, agg, higher, index_ok, notes, raster=None, hidden=False):
    d = {"id": id, "label": label, "category": "environment", "group": group, "units": units,
         "source": f"{src} via NASA AppEEARS", "source_url": url, "native_resolution": res, "temporal": "monthly",
         "aggregation": agg, "higher_is": higher, "index_ok": index_ok, "notes": notes}
    if raster:
        d["raster"] = raster
    if hidden:
        d["hidden"] = True
    return d


def meta_list(cons):
    def cn(v):
        c = cons.get(v)
        if not c:
            return ""
        return (f" Overlap vs existing {c['existing']} ({c['months_overlap']} months): r={c['pearson_r_county_month']}, "
                f"mean bias {c['mean_bias_new_minus_old']:+g}.")
    M = [
        _m("modis_et_monthly_mm", "Evapotranspiration, monthly (MODIS)", "Water", "mm/month",
           "MODIS MOD16A2GF v061 (Terra, 8-day, gap-filled)", "https://doi.org/10.5067/MODIS/MOD16A2GF.061",
           "500 m (aggregated to ~1 km grid)",
           "8-day ET totals prorated to calendar months by day overlap (last composite of each year is 5/6 days), "
           "per ~1 km cell; then mean of valid cells in county", "neutral", True,
           "Actual ET (Penman-Monteith MOD16). Open water, urban and barren pixels are fill and excluded (e.g. the "
           "permanent Sudd open water), so wetland counties are under-represented. Cells need >=75% of month's days valid."
           + (lambda c: f" Annual sums vs MOD16A3GF modis_et_mm: r={c['pearson_r_county_year']}, ratio {c['ratio']}." if c else "")(
               cons.get("modis_et_monthly_mm (annual sum)")), raster="modis_et_monthly"),
        _m("modis13a3_ndvi", "NDVI, monthly 1 km (MODIS MOD13A3)", "Vegetation", "index -1..1",
           "MODIS MOD13A3 v061 (Terra monthly 1 km)", "https://doi.org/10.5067/MODIS/MOD13A3.061", "1 km",
           "monthly composite (pixel reliability good/marginal), mean of valid ~1 km cells in county", "better", True,
           "Different compositing from modis_ndvi (MOD13A3 is a weighted average of 16-day 1 km composites; "
           "modis_ndvi is the Terra+Aqua 500 m monthly maximum), so kept as a separate id; MOD13A3 runs lower. "
           "Covers Aug-Oct 2025 missing from the Planetary Computer series." + cn("modis13a3_ndvi"),
           raster="modis13a3_ndvi"),
        _m("modis13a3_evi", "EVI, monthly 1 km (MODIS MOD13A3)", "Vegetation", "index -1..1",
           "MODIS MOD13A3 v061 (Terra monthly 1 km)", "https://doi.org/10.5067/MODIS/MOD13A3.061", "1 km",
           "monthly composite (pixel reliability good/marginal), mean of valid ~1 km cells in county", "better", True,
           "See modis13a3_ndvi." + cn("modis13a3_evi")),
        _m("appeears_lst_day_c", "Land surface temperature, day (MODIS, AppEEARS copy)", "Temperature", "°C",
           "MODIS MOD11A2 v061 (Terra)", "https://doi.org/10.5067/MODIS/MOD11A2.061", "1 km",
           "same as modis_lst_day_c (QC good/other, error<=2K, month of composite mid-date, per-cell mean, county mean)",
           "worse", False, "2022-2025 only; hidden duplicate used to verify and gap-fill modis_lst_day_c." + cn("appeears_lst_day_c"),
           hidden=True),
        _m("appeears_lst_night_c", "Land surface temperature, night (MODIS, AppEEARS copy)", "Temperature", "°C",
           "MODIS MOD11A2 v061 (Terra)", "https://doi.org/10.5067/MODIS/MOD11A2.061", "1 km",
           "same as modis_lst_night_c", "worse", False,
           "2022-2025 only; hidden duplicate used to verify and gap-fill modis_lst_night_c." + cn("appeears_lst_night_c"),
           hidden=True),
        _m("appeears_burned_area_km2", "Burned area (MODIS MCD64A1, AppEEARS copy)", "Fire", "km2",
           "MODIS MCD64A1 v061", "https://doi.org/10.5067/MODIS/MCD64A1.061", "500 m",
           "burned 500 m pixels (Burn_Date>0) averaged to ~1 km cells x geodesic cell area, summed in county",
           "worse", False, "Hidden duplicate used to verify and gap-fill burned_area_km2. County-months with <50% "
           "mapped area dropped." + cn("appeears_burned_area_km2"), hidden=True),
        _m("appeears_burned_area_pct", "Burned area % (MODIS MCD64A1, AppEEARS copy)", "Fire", "% of county area",
           "MODIS MCD64A1 v061", "https://doi.org/10.5067/MODIS/MCD64A1.061", "500 m",
           "burned area / county area x 100", "worse", False,
           "Hidden duplicate used to verify and gap-fill burned_area_pct." + cn("appeears_burned_area_pct"), hidden=True),
        _m("smap_sm_surface", "Surface soil moisture 0-5 cm (SMAP L4)", "Water", "m³/m³",
           "SMAP L4 SPL4SMGP v008 (3-hourly, 9 km, NASA GEOS land model + SMAP brightness-temperature assimilation)",
           "https://doi.org/10.5067/LWJ6TF5SZRG3", "9 km",
           "per-cell monthly mean of 3-hourly values, then mean of ~1 km cells (nearest 9 km cell) in county",
           "better", True, "Model-assimilation product (gap-free), not a direct retrieval; L4 surface layer is 0-5 cm.",
           raster="smap_sm_surface"),
        _m("smap_sm_rootzone", "Root-zone soil moisture 0-100 cm (SMAP L4)", "Water", "m³/m³",
           "SMAP L4 SPL4SMGP v008 (3-hourly, 9 km)", "https://doi.org/10.5067/LWJ6TF5SZRG3", "9 km",
           "per-cell monthly mean of 3-hourly values, then county mean", "better", True,
           "Model-assimilation estimate for 0-100 cm; smoother and lagged relative to surface soil moisture.",
           raster="smap_sm_rootzone"),
    ]
    return M


def assemble():
    parts = sorted((WORK / "partials").glob("*.csv"))
    if not parts:
        log("no partials yet")
        return
    df = pd.concat([pd.read_csv(p) for p in parts], ignore_index=True)
    df = df[(df.date >= "2018-01-01") & (df.date <= "2025-12-01")]
    # LST task starts 2022-01-01; drop the partial month from a composite that began in Dec 2021
    df = df[~(df.variable.str.startswith("appeears_lst") & (df.date < "2022-01-01"))]
    cons, gaps = consistency(df)
    (WORK / "consistency.json").write_text(json.dumps(cons, indent=1))
    out = df if gaps is None else pd.concat([df, gaps], ignore_index=True)
    out = out.drop_duplicates(["county_id", "date", "variable"]).sort_values(["variable", "county_id", "date"])
    p = ROOT / "data" / "processed" / "appeears_county_monthly.csv"
    out.to_csv(p, index=False)
    present = set(out.variable)
    meta = [m for m in meta_list(cons) if m["id"] in present]
    gee_smap = sorted(p.stem[-4:] for p in parts if p.stem.startswith("smap_gee_"))
    for m in meta:
        if gee_smap and m["id"].startswith("smap_"):
            ae = sorted(p.stem[-4:] for p in parts if re.fullmatch(r"smap_\d{4}", p.stem))
            m["source"] = m["source"].replace(" via NASA AppEEARS", "") + (
                f" via Google Earth Engine (NASA/SMAP/SPL4SMGP/008; years {', '.join(gee_smap)})"
                + (f" and NASA AppEEARS (years {', '.join(ae)})" if ae else ""))
            m["notes"] += " Monthly means of the 3-hourly fields computed in Earth Engine (scripts/gee_smap.py)."
            continue
        m["notes"] += " AppEEARS area request clipped to the South Sudan outline, geographic projection."
    mp = ROOT / "data" / "processed" / "meta" / "appeears.json"
    mp.write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    (ROOT / "data" / "processed" / "meta").mkdir(exist_ok=True)
    log(f"wrote {p} ({len(out)} rows), {mp}")
    print(out.groupby("variable").agg(n=("value", "size"), counties=("county_id", "nunique"),
                                       months=("date", "nunique"), first=("date", "min"), last=("date", "max"),
                                       vmed=("value", "median")).to_string())
    print(json.dumps(cons, indent=1))
    render_rasters()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", nargs="?", default="all", choices=["submit", "status", "process", "assemble", "all"])
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--wait", action="store_true", help="keep polling until every task is processed")
    a = ap.parse_args()
    if a.stage in ("submit", "status", "process", "all"):
        api = Api()
        if a.stage in ("submit", "all"):
            submit(api, a.only)
        if a.stage == "status":
            status(api)
        if a.stage in ("process", "all"):
            while True:
                process(api, a.only)
                st = state()
                left = [k for k, v in st.items() if not v.get("processed") and (not a.only or k in a.only)]
                if not left or not a.wait:
                    break
                log("waiting for", left)
                time.sleep(120)
    if a.stage in ("assemble", "all"):
        assemble()


if __name__ == "__main__":
    main()
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from trend_stats import write_trends
    write_trends("appeears")
