#!/usr/bin/env python
""""Trend to date" companion rasters: docs/rasters/<key>_trend/<YYYY>.png + meta.json.

For every time-varying raster layer, and for each end year YYYY = 2020..2025, the PNG shows the per-pixel
Theil-Sen (Sen's) slope of the layer's YEARLY values from 2018 through YYYY (>= 3 years with a value), in
<units>/yr. The slope formula is trend_stats.sens_slope (median of all pairwise slopes (x_j - x_i)/(t_j - t_i)),
vectorised over pixels here and checked against trend_stats.sens_slope on random pixels at run time.

Colour: diverging map centred on 0, with ONE fixed symmetric scale per layer: +-(98th percentile of |slope| over
all in-country pixels and all end years), so the map visibly "grows" as the record lengthens. Colour meaning:
water variables  brown = drier / less water, teal = wetter / more water  (div_brbg; reversed for deficit)
temperature      blue = cooling, red = warming                           (div_rdbu)
NDVI             brown = browning, green = greening                      (div_brgn)
other            purple = decrease, orange = increase                    (div_puor)

Yearly value per pixel (the `basis` field of each meta.json says which):
  * annual mean (Jan-Dec) for state variables (NDVI, temperature, soil-water deficit, PDSI, wind, GRACE storage, S5P)
  * wet-season (Jun-Sep) mean for rainfall / ET / flood / soil water, so dry-season zeros do not flatten the slope
  * Sudd inundation: Sep-Dec high-water season (the product's own "annual peak" window; Jun-Sep is mostly cloud)
  * VIIRS fire: annual total of detections
  * MODIS annual ET (MOD16A3GF): the annual product value itself
Missing months are handled with a climatology-anomaly mean so a gap does not bias a year:
    yearly(y) = mean_{m in season} clim_m  +  mean_{m in season, observed in y} (x_{y,m} - clim_m)
with clim_m = the pixel's 2018-2025 mean for calendar month m. A year needs >= half of its season's months
(composites for Sudd) to be observed, otherwise it is left out (e.g. Sudd 2025, MODIS reflectance gap Jul-Nov 2025).

Usage: python scripts/raster_trends.py [--continuous] [key ...]   (default: all layers; re-runnable, overwrites outputs)

--continuous: render each slope map as a smooth continuous diverging ramp red #b2182b (decrease) -> white #ffffff (0)
-> green #1b7837 (increase), symmetric about 0 with the layer's fixed +-limit (kept from an existing meta.json when
there is one), instead of the original ColorBrewer ramp that scripts/recolor_rasters*.py later binned into 7 colours.
Coarse products (GLDAS / GRACE-DA 0.25 deg, SMAP 9 km, IMERG 0.1 deg) are first averaged back onto their native cells
and then bilinearly interpolated to the output pixels, so cells blend instead of looking blocky. Pixels with data but
too few years for a slope are hatched black. meta.json gets "continuous": true, "palette": "rwg-continuous",
"colors": [3 anchors], "vmin"/"vmax", "bins": null. Do NOT run recolor_rasters*.py on these layers afterwards.
"""
import glob
import json
import os
import sys
import time

import numpy as np
from rasterio import features
from rasterio.transform import from_origin

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import overlay_utils as ou  # noqa: E402
from trend_stats import sens_slope  # noqa: E402

ROOT = ou.ROOT
RASTERS = ou.RASTERS
SCRATCH = os.environ.get(
    "RT_SCRATCH", "/tmp/claude-0/-home-user-yale-nov27-hackathon/b7acc7ce-9c21-59ae-8208-6da6aae060da/scratchpad")
APPEEARS = os.environ.get("APPEEARS_GRIDS", os.path.join(SCRATCH, "appeears", "work", "grids"))
MODIS_PC = os.environ.get("MODIS_GRIDS", os.path.join(SCRATCH, "modis", "work", "grids"))
GLDAS = os.environ.get("GLDAS_GRIDS", os.path.join(SCRATCH, "gldas", "work", "grids"))
GRACEDM = os.environ.get("GRACEDM_GRIDS", os.path.join(SCRATCH, "gldas", "gracedm_work", "grids"))
MAIAC = os.environ.get("MAIAC_GRIDS", os.path.join(SCRATCH, "maiac", "work", "grids"))
TC_RAW = os.environ.get("TC_RAW", os.path.join(SCRATCH, "climate", "tc_raw"))
GEE_CLIMATE = os.environ.get("GEE_CLIMATE_GRIDS", os.path.join(SCRATCH, "gee_climate", "work", "grids"))
LULC = os.environ.get("LULC_GRIDS", os.path.join(SCRATCH, "lulc", "work", "grids"))
CONTINUOUS = False  # set by --continuous

YEARS = list(range(2018, 2026))
END_YEARS = list(range(2020, 2026))
ALL = tuple(range(1, 13))
WET = (6, 7, 8, 9)
GRID001 = from_origin(23.4, 12.3, 0.01, 0.01)  # AppEEARS / MODIS (Planetary Computer) 0.01 deg grids

ANNUAL_MEAN = "annual mean (Jan-Dec) of the monthly values"
WET_MEAN = ("wet-season mean (Jun-Sep) of the monthly values, so dry-season zeros do not flatten the slope")
ANOM = (" Missing months are filled by the climatology-anomaly method (yearly = mean monthly climatology + mean anomaly"
        " of the observed months); a year needs >= half of the season observed unless stated otherwise.")


# ----------------------------------------------------------------------------- yearly aggregation
def yearly_from_months(get, season, agg="mean", min_frac=0.5):
    """get(y, m) -> 2-D array (NaN = no data) or None. Returns (n_years, H, W) float32 yearly values."""
    if agg == "sum":
        # annual total; a missing month is filled with the pixel's mean for that calendar month (<= 4 per year)
        data = {(y, m): get(y, m) for y in YEARS for m in season}
        shape = next(a.shape for a in data.values() if a is not None)
        clim = {}
        for m in season:
            have = [data[(y, m)] for y in YEARS if data[(y, m)] is not None]
            clim[m] = np.nanmean(have, axis=0) if have else None
        out = np.full((len(YEARS), *shape), np.nan, "float32")
        for i, y in enumerate(YEARS):
            miss = [m for m in season if data[(y, m)] is None]
            if len(miss) > 4 or any(clim[m] is None for m in miss):
                continue
            out[i] = np.sum([data[(y, m)] if data[(y, m)] is not None else clim[m] for m in season], axis=0)
            if miss:
                print(f"  {y}: months {miss} missing, filled with climatology", flush=True)
        return out
    # pass 1: per-season-month climatology
    csum, ccnt, shape = {}, {}, None
    for y in YEARS:
        for m in season:
            a = get(y, m)
            if a is None:
                continue
            shape = a.shape
            ok = np.isfinite(a)
            csum[m] = csum.get(m, 0) + np.where(ok, a, 0)
            ccnt[m] = ccnt.get(m, 0) + ok
    with np.errstate(invalid="ignore", divide="ignore"):
        clim = {m: np.where(ccnt[m] > 0, csum[m] / np.maximum(ccnt[m], 1), np.nan).astype("float32") for m in csum}
    climall = np.nanmean(np.stack([clim[m] for m in season if m in clim]), axis=0) if clim else None
    # pass 2: yearly mean anomaly
    out = np.full((len(YEARS), *shape), np.nan, "float32")
    need = max(1, int(np.ceil(min_frac * len(season))))
    for i, y in enumerate(YEARS):
        asum = np.zeros(shape, "float32")
        acnt = np.zeros(shape, "int16")
        for m in season:
            if m not in clim:
                continue
            a = get(y, m)
            if a is None:
                continue
            d = a - clim[m]
            ok = np.isfinite(d)
            asum += np.where(ok, d, 0)
            acnt += ok
        with np.errstate(invalid="ignore", divide="ignore"):
            out[i] = np.where(acnt >= need, climall + asum / np.maximum(acnt, 1), np.nan)
    return out


# ----------------------------------------------------------------------------- Sen's slope, vectorised
def sen_stack(Y, years):
    """Y (n, H, W) -> (H, W) Sen's slope over the given years (NaN where < 3 finite values)."""
    t = np.asarray(years, float)
    i, j = np.triu_indices(len(t), 1)
    H, W = Y.shape[1:]
    out = np.full((H, W), np.nan, "float32")
    nval = np.isfinite(Y).sum(0)
    for r0 in range(0, H, 128):  # row blocks keep memory small
        y = Y[:, r0:r0 + 128].astype("float64")
        s = (y[j] - y[i]) / (t[j] - t[i])[:, None, None]
        with np.errstate(all="ignore"):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                out[r0:r0 + 128] = np.nanmedian(s, axis=0)
    out[nval < 3] = np.nan
    return out


def check_against_trend_stats(Y, slope, years, rng=np.random.default_rng(0)):
    ii = np.argwhere(np.isfinite(slope))
    if len(ii) == 0:
        return
    for r, c in ii[rng.choice(len(ii), min(25, len(ii)), replace=False)]:
        ref = sens_slope(np.asarray(years, float), Y[:, r, c].astype(float))
        assert np.isclose(ref, slope[r, c], rtol=1e-4, atol=1e-6), (r, c, ref, slope[r, c])


# ----------------------------------------------------------------------------- loaders
def npy_monthly(d):
    def get(y, m):
        p = os.path.join(d, f"{y}-{m:02d}.npy")
        return np.load(p).astype("float32") if os.path.exists(p) else None
    return get


def load_chirps():
    import xarray as xr
    ds = xr.open_dataset(os.path.join(ROOT, "data", "raw", "chirps", "chirps_v3_ssd_2018_2025.nc"))
    da = ds["precip"].load()
    lat, lon = da.lat.values, da.lon.values
    tf = from_origin(lon[0] - (lon[1] - lon[0]) / 2, lat[0] + (lat[0] - lat[1]) / 2, lon[1] - lon[0], lat[0] - lat[1])
    idx = {str(t)[:7]: k for k, t in enumerate(da.time.values)}
    vals = da.values.astype("float32")
    vals[vals < 0] = np.nan

    def get(y, m):
        k = idx.get(f"{y}-{m:02d}")
        return None if k is None else vals[k]
    return get, tf


def load_tc(var):
    import xarray as xr
    cache, tf = {}, [None]

    def year(y):
        if y not in cache:
            p = os.path.join(TC_RAW, f"{var}_{y}.nc")
            if not os.path.exists(p):
                cache[y] = None
            else:
                with xr.open_dataset(p) as ds:
                    v = [k for k in ds.data_vars if ds[k].ndim == 3][0]
                    da = ds[v].load()
                lat, lon = da.lat.values, da.lon.values
                tf[0] = from_origin(lon[0] - (lon[1] - lon[0]) / 2, lat[0] + (lat[0] - lat[1]) / 2,
                                    lon[1] - lon[0], lat[0] - lat[1])
                cache[y] = {int(str(t)[5:7]): da.values[k].astype("float32") for k, t in enumerate(da.time.values)}
        return cache[y]

    def get(y, m):
        d = year(y)
        if d is None or m not in d:
            return None
        a = d[m]
        return np.where(np.isfinite(a) & (np.abs(a) < 1e6), a, np.nan).astype("float32")
    for y in YEARS:
        year(y)
    return get, tf[0]


def load_grace():
    import xarray as xr
    import fetch_grace as fg
    t = xr.open_dataset(os.path.join(ROOT, "data", "raw", "grace", "_cache", "tws_costg.nc"))
    da = fg.to_monthly(t["tws"]).sortby("lat", ascending=False).load()
    lat, lon = da.lat.values, da.lon.values
    tf = from_origin(lon[0] - (lon[1] - lon[0]) / 2, lat[0] + (lat[0] - lat[1]) / 2, lon[1] - lon[0], lat[0] - lat[1])
    months = {str(m): k for k, m in enumerate(da.month.values)}
    vals = da.values.astype("float32")

    def get(y, m):
        k = months.get(f"{y}-{m:02d}")
        return None if k is None else vals[k]
    return get, tf


S5P_X0, S5P_Y1, S5P_RES = 24.0, 12.35, 0.05


def load_s5p(prod):
    nx, ny = int((36.1 - S5P_X0) / S5P_RES), int((S5P_Y1 - 3.4) / S5P_RES)
    d = os.path.join(ROOT, "data", "raw", "s5p", "monthly_grids")

    def get(y, m):
        p = os.path.join(d, f"{prod}_{y}-{m:02d}.npz")
        if not os.path.exists(p):
            return None
        z = np.load(p)
        if int(z["norb"]) < 2:
            return None
        s, n = z["s"], z["n"]
        assert s.size == nx * ny
        return np.where(n > 0, s / np.maximum(n, 1), np.nan).reshape(ny, nx).astype("float32")
    return get, from_origin(S5P_X0, S5P_Y1, S5P_RES, S5P_RES)


def load_viirs():
    import pandas as pd
    W, S, E, N, G = 23.4, 3.4, 36.0, 12.3, 0.05
    nx, ny = int(round((E - W) / G)), int(round((N - S) / G))
    grids = {}
    for y in YEARS:
        p = os.path.join(ROOT, "data", "raw", "viirs_fire", f"viirs_snpp_{y}.csv.gz")
        df = pd.read_csv(p, usecols=["latitude", "longitude", "acq_date"])
        ix = ((df.longitude - W) / G).astype(int).clip(0, nx - 1).values
        iy = ((N - df.latitude) / G).astype(int).clip(0, ny - 1).values
        mo = df.acq_date.str[5:7].astype(int).values
        for m in ALL:
            g = np.zeros((ny, nx), "float32")
            k = mo == m
            np.add.at(g, (iy[k], ix[k]), 1)
            grids[(y, m)] = g
    return (lambda y, m: grids.get((y, m))), from_origin(W, N, G, G)


BURN_CACHE = os.path.join(ROOT, "data", "raw", "fire", "_cache", "burned_grids")  # gitignored


def burned_month_grid(y, m):
    """MCD64A1 burned fraction (0..1) of each 0.01 deg cell for one month, cached as .npy (re-derived from
    Planetary Computer: the original monthly grids of fire_pipeline.py were not kept)."""
    p = os.path.join(BURN_CACHE, f"{y}-{m:02d}.npy")
    if os.path.exists(p):
        return np.load(p)
    import calendar
    from concurrent.futures import ThreadPoolExecutor
    from rasterio.warp import reproject, Resampling
    import fire_pipeline as fp
    import hazards_common as hc
    mm = f"{y}-{m:02d}"
    items = hc.search("modis-64A1-061", f"{mm}-01/{mm}-{calendar.monthrange(y, m)[1]:02d}")
    items = [it for it in items if it.properties["start_datetime"][:7] == mm]
    if not items:
        return None
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(lambda it: fp.read_window(it.assets["Burn_Date"].href, 1), items))
    H, W = 890, 1260
    tot = np.zeros((H, W), "float32")
    cnt = np.zeros((H, W), "float32")
    for r in res:
        if r is None:
            continue
        arr, tr, crs = r
        frac = np.where(arr == -1, np.nan, (arr > 0).astype("float32"))
        dst = np.full((H, W), np.nan, "float32")
        reproject(frac, dst, src_transform=tr, src_crs=crs, dst_transform=GRID001, dst_crs="EPSG:4326",
                  src_nodata=np.nan, dst_nodata=np.nan, resampling=Resampling.average)
        ok = np.isfinite(dst)
        tot += np.where(ok, dst, 0)
        cnt += ok
    g = np.where(cnt > 0, tot / np.maximum(cnt, 1), np.nan).astype("float32")
    os.makedirs(BURN_CACHE, exist_ok=True)
    np.save(p, g)
    return g


def load_burned():
    def get(y, m):
        g = burned_month_grid(y, m)
        return None if g is None else np.nan_to_num(g) * 100.0  # % of cell burned; unmapped counts as unburned
    return get, GRID001


def yearly_modis_et_annual():
    d = os.path.join(MODIS_PC, "modis_et_mm")
    out = []
    for y in YEARS:
        p = os.path.join(d, f"{y}-07.npy")
        out.append(np.load(p).astype("float32") if os.path.exists(p) else None)
    shape = next(a.shape for a in out if a is not None)
    Y = np.stack([a if a is not None else np.full(shape, np.nan, "float32") for a in out])
    Y[(Y < 0) | (Y > 6000)] = np.nan
    return Y, GRID001, "EPSG:4326"


def yearly_sudd():
    """Sudd: % of clear 8-day composites inundated (open water / flooded vegetation), Sep-Dec, anomaly method."""
    import sudd_water_index as swi
    G = swi.grid()
    files = sorted(glob.glob(os.path.join(ROOT, "data", "raw", "sudd_water", "_cache", "cls", "A*.npz")))
    comp = {}
    for f in files:
        b = os.path.basename(f)
        y, doy = int(b[1:5]), int(b[5:8])
        if y in YEARS and doy >= 241:  # composites starting 29 Aug .. 27 Dec = Sep-Dec high-water season
            comp[(y, doy)] = f
    doys = tuple(sorted({d for (_, d) in comp}))

    def get(y, doy):
        f = comp.get((y, doy))
        if f is None:
            return None
        c = np.load(f)["cls"]
        v = np.where(c < 4, np.isin(c, (1, 2, 3)) * 100.0, np.nan).astype("float32")
        v[~G["aoi"]] = np.nan
        return v
    return yearly_from_months(get, doys), G["transform"], swi.SIN


def yearly_flood_s1():
    """Sentinel-1 water/flooded fraction (%), aggregated to 0.02 deg, wet-season Jun-Sep mean."""
    import flood_s1_pipeline as fs
    tr, (h, w), crs = fs.grid()
    f = 5
    H, W = h // f, w // f
    months = {}
    for m, cls, _obs in fs.water_series():
        y, mm = int(m[:4]), int(m[5:7])
        if mm not in WET:
            continue
        c = cls[:H * f, :W * f].reshape(H, f, W, f)
        known = (c >= 0).mean(axis=(1, 3))
        water = (c >= 1).mean(axis=(1, 3))
        with np.errstate(invalid="ignore", divide="ignore"):
            months[(y, mm)] = np.where(known >= 0.5, 100 * water / known, np.nan).astype("float32")
    tf = from_origin(tr.c, tr.f, tr.a * f, -tr.e * f)
    return yearly_from_months(lambda y, m: months.get((y, m)), WET), tf, crs


def yearly_lulc(var):
    """Impact Observatory annual land-cover share grids (scripts/landcover_grids.py), one value per year (2017-2023;
    2024-2025 not published) -> used directly as the yearly values."""
    def run():
        out = []
        for y in YEARS:
            p = os.path.join(LULC, var, f"{y}.npy")
            out.append(np.load(p).astype("float32") if os.path.exists(p) else None)
        shape = next(a.shape for a in out if a is not None)
        return np.stack([a if a is not None else np.full(shape, np.nan, "float32") for a in out]), GRID001, "EPSG:4326"
    return run


def monthly(loader, season, agg="mean", min_frac=0.5):
    def run():
        get, tf = loader()
        return yearly_from_months(get, season, agg, min_frac), tf, "EPSG:4326"
    return run


def npy_layer(d):
    return lambda: (npy_monthly(d), GRID001)


# ----------------------------------------------------------------------------- colormaps
CMAPS = {
    "div_brbg": ["#543005", "#8c510a", "#bf812d", "#dfc27d", "#f6e8c3", "#f5f5f5",
                 "#c7eae5", "#80cdc1", "#35978f", "#01665e", "#003c30"],
    "div_rdbu": ["#053061", "#2166ac", "#4393c3", "#92c5de", "#d1e5f0", "#f7f7f7",
                 "#fddbc7", "#f4a582", "#d6604d", "#b2182b", "#67001f"],
    "div_brgn": ["#543005", "#8c510a", "#bf812d", "#dfc27d", "#f6e8c3", "#f7f7f7",
                 "#d9f0d3", "#a6dba0", "#5aae61", "#1b7837", "#00441b"],
    "div_puor": ["#2d004b", "#542788", "#8073ac", "#b2abd2", "#d8daeb", "#f7f7f7",
                 "#fee0b6", "#fdb863", "#e08214", "#b35806", "#7f3b08"],
}
CMAPS["div_brbg_r"] = CMAPS["div_brbg"][::-1]
CMAP_NOTE = {
    "div_brbg": "brown = drier / less water, teal = wetter / more water",
    "div_brbg_r": "teal = deficit shrinking (wetter), brown = deficit growing (drier)",
    "div_rdbu": "blue = cooling, red = warming",
    "div_brgn": "brown = browning, green = greening",
    "div_puor": "purple = decreasing, orange = increasing",
}
for k, v in CMAPS.items():
    ou.CMAPS.setdefault(k, v)

# ----------------------------------------------------------------------------- layer table
TC = lambda v: (lambda: load_tc(v))  # noqa: E731
LAYERS = [
    dict(key="chirps", run=monthly(load_chirps, WET), cmap="div_brbg", basis=WET_MEAN),
    dict(key="grace_tws", run=monthly(load_grace, ALL, min_frac=0.4), cmap="div_brbg",
         basis=ANNUAL_MEAN + " (storage anomaly; no dry-season zeros). GRACE-FO starts Jun 2018: 2018 = 5 months "
         "(Jun, Jul, Oct-Dec), accepted via the anomaly method (threshold lowered to 5 of 12 months)."),
    dict(key="gldas_gws", run=monthly(npy_layer(os.path.join(GLDAS, "gldas_gws_anom_cm")), ALL), cmap="div_brbg",
         native=(0.25, (-180.0, 90.0)),
         basis=ANNUAL_MEAN + " (groundwater storage anomaly vs 2004-2020, GLDAS-2.2 CLSM GRACE-DA)"),
    dict(key="gracedm_gws", run=monthly(npy_layer(os.path.join(GRACEDM, "gracedm_gws_pctl")), ALL), cmap="div_brbg",
         native=(0.25, (-180.0, 90.0)),
         unit_out="percentile points/yr",
         basis=ANNUAL_MEAN + " (weekly groundwater percentiles averaged by month, then by year)"),
    dict(key="maiac_aod", run=monthly(npy_layer(os.path.join(MAIAC, "maiac_aod_055")), ALL), cmap="div_puor",
         basis=ANNUAL_MEAN + " (MODIS MAIAC 1 km AOD, best-quality cloud-free retrievals)"),
    dict(key="modis13a3_ndvi", run=monthly(npy_layer(os.path.join(APPEEARS, "modis13a3_ndvi")), ALL),
         cmap="div_brgn", basis=ANNUAL_MEAN),
    dict(key="modis_et_monthly", run=monthly(npy_layer(os.path.join(APPEEARS, "modis_et_monthly_mm")), WET),
         cmap="div_brbg", basis=WET_MEAN),
    dict(key="tc_tmax", run=monthly(TC("tmax"), ALL), cmap="div_rdbu", basis=ANNUAL_MEAN),
    dict(key="smap_sm_rootzone", run=monthly(npy_layer(os.path.join(APPEEARS, "smap_sm_rootzone")), WET),
         cmap="div_brbg", basis=WET_MEAN, unit_out="m³/m³ per yr", native=(0.08, (23.4, 12.3))),
    dict(key="smap_sm_surface", run=monthly(npy_layer(os.path.join(APPEEARS, "smap_sm_surface")), WET),
         cmap="div_brbg", basis=WET_MEAN, unit_out="m³/m³ per yr", native=(0.08, (23.4, 12.3))),
    dict(key="imerg_precip", run=monthly(npy_layer(os.path.join(GEE_CLIMATE, "precip_mm")), WET), cmap="div_brbg",
         basis=WET_MEAN + " (GPM IMERG V07 monthly, 0.1°)", native=(0.1, (-180.0, 90.0))),
    dict(key="fldas_tair", run=monthly(npy_layer(os.path.join(GEE_CLIMATE, "tair_c")), ALL), cmap="div_rdbu",
         basis=ANNUAL_MEAN + " (NASA FLDAS Noah 2 m air temperature, 0.1°)", native=(0.1, (-180.0, 90.0)),
         unit_out="°C/yr"),
    dict(key="lulc_built", run=yearly_lulc("lulc_built_pct"), cmap="div_puor", unit_out="percentage points/yr",
         basis="the annual Impact Observatory land-cover map itself (2018-2023; one map per year, no seasons)"),
    dict(key="lulc_crop", run=yearly_lulc("lulc_crop_pct"), cmap="div_puor", unit_out="percentage points/yr",
         basis="the annual Impact Observatory land-cover map itself (2018-2023; one map per year, no seasons)"),
    dict(key="lulc_flooded_veg", run=yearly_lulc("lulc_flooded_veg_pct"), cmap="div_brbg",
         unit_out="percentage points/yr",
         basis="the annual Impact Observatory land-cover map itself (2018-2023; one map per year, no seasons)"),
    dict(key="tc_soil", run=monthly(TC("soil"), WET), cmap="div_brbg", basis=WET_MEAN, unit_out="mm/yr"),
    dict(key="sudd_inundation", run=yearly_sudd, cmap="div_brbg",
         units="% of clear Sep-Dec composites inundated", unit_out="percentage points/yr",
         basis=("Sep-Dec high-water-season share (%) of cloud-free MODIS 8-day composites classified as open water or "
                "flooded vegetation (the product's own annual-peak window; Jun-Sep is mostly cloud over the Sudd). "
                "2025 is omitted: Planetary Computer has no MODIS reflectance for 4 Jul - 24 Nov 2025.")),
    dict(key="viirs_fire", run=monthly(load_viirs, ALL, "sum"), cmap="div_puor",
         units="detections per 0.05° cell per year", unit_out="detections per 0.05° cell per year, per yr",
         basis="annual total (Jan-Dec) of nominal/high-confidence VIIRS S-NPP vegetation-fire detections per 0.05° cell"),
    dict(key="tc_ppt", run=monthly(TC("ppt"), WET), cmap="div_brbg", basis=WET_MEAN),
    dict(key="tc_aet", run=monthly(TC("aet"), WET), cmap="div_brbg", basis=WET_MEAN),
    dict(key="tc_def", run=monthly(TC("def"), ALL), cmap="div_brbg_r",
         basis=ANNUAL_MEAN + " (deficit is largest in the dry season, so the whole year is used)"),
    dict(key="tc_pdsi", run=monthly(TC("pdsi"), ALL), cmap="div_brbg", basis=ANNUAL_MEAN),
    dict(key="tc_ws", run=monthly(TC("ws"), ALL), cmap="div_puor", basis=ANNUAL_MEAN),
    dict(key="modis_lst_day", run=monthly(npy_layer(os.path.join(MODIS_PC, "modis_lst_day_c")), ALL),
         cmap="div_rdbu", basis=ANNUAL_MEAN),
    dict(key="modis_ndvi", run=monthly(npy_layer(os.path.join(MODIS_PC, "modis_ndvi")), ALL),
         cmap="div_brgn", basis=ANNUAL_MEAN),
    dict(key="modis_et", run=yearly_modis_et_annual, cmap="div_brbg", unit_out="mm/year per year",
         basis="annual total of the MODIS MOD16A3GF annual product (one value per year)"),
    dict(key="burned_area", run=monthly(load_burned, ALL, "sum"), cmap="div_puor",
         units="% of cell burned per year", unit_out="% of cell burned per year, per yr",
         basis=("annual total (Jan-Dec) of the monthly MODIS MCD64A1 burned share of each 0.01° cell, in % "
                "(a cell burned in two months counts twice); re-derived from Planetary Computer. Months absent on Planetary "
                "Computer (2023-09, 2024-07, 2025-05, 2025-08..10; all outside the Nov-Apr fire season) are filled with "
                "the pixel's 2018-2025 mean for that calendar month")),
    dict(key="flood_s1", run=yearly_flood_s1, cmap="div_brbg", units="% of pixel classified water",
         unit_out="percentage points/yr",
         basis=("wet-season (Jun-Sep) mean water/flooded fraction (%) of each 0.02° cell from the monthly Sentinel-1 "
                "classification (gap-filled as in flood_s1_pipeline)")),
    dict(key="s5p_aerosol_index", run=monthly(lambda: load_s5p("aer-ai"), ALL), cmap="div_puor",
         basis=ANNUAL_MEAN + " (sampled orbits; S5P starts mid-2018)"),
    dict(key="s5p_no2", run=monthly(lambda: load_s5p("no2"), ALL), cmap="div_puor",
         basis=ANNUAL_MEAN + " (sampled orbits; S5P starts mid-2018)"),
    dict(key="s5p_co", run=monthly(lambda: load_s5p("co"), ALL), cmap="div_puor",
         basis=ANNUAL_MEAN + " (sampled orbits; S5P starts mid-2018)"),
]


def country_mask(shape, tf, crs):
    c = ou.counties().to_crs(crs)
    return features.rasterize(((g, 1) for g in c.geometry), out_shape=shape, transform=tf, fill=0,
                              all_touched=True, dtype="uint8").astype(bool)


def nice(x):
    """Round the colour limit to 2 significant figures."""
    if not np.isfinite(x) or x <= 0:
        return 1.0
    p = 10 ** np.floor(np.log10(x))
    return float(np.ceil(x / p * 10) / 10 * p)


def process(L):
    t0 = time.time()
    key = L["key"]
    base_meta = json.load(open(os.path.join(RASTERS, key, "meta.json")))
    Y, tf, crs = L["run"]()
    if L["key"] != "sudd_inundation":
        mask = country_mask(Y.shape[1:], tf, crs)
        Y[:, ~mask] = np.nan
    slopes = {}
    for e in END_YEARS:
        yrs = [y for y in YEARS if y <= e]
        s = sen_stack(Y[:len(yrs)], yrs)
        if np.isfinite(s).any() and np.isfinite(Y[len(yrs) - 1]).any():  # skip end years with no new data
            slopes[e] = s
            check_against_trend_stats(Y[:len(yrs)], s, yrs)
    if not slopes:
        print(key, "no slopes", flush=True)
        return None
    vals = np.concatenate([np.abs(s[np.isfinite(s)]) for s in slopes.values()])
    lim = nice(float(np.percentile(vals, 98)))
    od = key + "_trend"
    old_meta_p = os.path.join(RASTERS, od, "meta.json")
    if CONTINUOUS and os.path.exists(old_meta_p):
        old = json.load(open(old_meta_p))
        if old.get("vmax") and float(old["vmax"]) > 0:
            if abs(float(old["vmax"]) - lim) > 1e-12:
                print(f"  {key}: keeping existing limit ±{old['vmax']} (recomputed would be ±{lim:g})", flush=True)
            lim = float(old["vmax"])
    units = L.get("unit_out") or (L.get("units") or base_meta.get("units", "")) + "/yr"
    for p in glob.glob(os.path.join(RASTERS, od, "*.png")):
        os.remove(p)
    meta = None
    domain = np.isfinite(Y).any(0)
    rtf = tf
    if CONTINUOUS and L.get("native"):
        res, origin = L["native"]
        dn, rtf = ou.to_native(np.where(domain, 1.0, np.nan).astype("float32"), res, origin, tf)
        domain = np.isfinite(dn)
    for e, s in slopes.items():
        if CONTINUOUS:
            if L.get("native"):
                s, _ = ou.to_native(s, res, origin, tf)
            meta = ou.write_overlay_continuous(s, rtf, crs, od, str(e), -lim, lim, ou.RWG, domain=domain,
                                               max_px=1000, min_px=700)
        else:
            meta = ou.write_overlay(s, tf, crs, od, str(e), -lim, lim, L["cmap"], {}, max_px=1000, min_px=700)
    yr_count = {str(e): int(sum(np.isfinite(Y[i]).any() for i in range(len(YEARS)) if YEARS[i] <= e))
                for e in slopes}
    out = {
        "key": od,
        "label": f"{base_meta.get('label', key)} — trend 2018→year (Sen's slope)",
        "units": units,
        "bounds": meta["bounds"],
        "vmin": -lim, "vmax": lim,
        "colormap": L["cmap"],
        "colors": CMAPS[L["cmap"]],
        "scale": "linear, symmetric about 0 (fixed across years: 98th percentile of |slope|)",
        "dates": [str(e) for e in slopes],
        "native_resolution": base_meta.get("native_resolution"),
        "source": base_meta.get("source"),
        "trend_of": key,
        "basis": L["basis"].rstrip(".") + "." + (ANOM if "mean" in L["basis"] and "S-NPP" not in L["basis"] else ""),
        "years_with_data": yr_count,
        "notes": (f"Each image = per-pixel Theil-Sen (Sen's) slope of the yearly values from 2018 through the image year "
                  f"(>= 3 years), in {units}. "
                  + ("Continuous colour: red = decrease, white = no change, green = increase (bilinear smoothing between "
                     "cells; black hatching = data but too few years for a slope). " if CONTINUOUS else
                     f"{CMAP_NOTE[L['cmap']]}; white = no change. ")
                  + "No significance test is applied per pixel: with 3-8 yearly points a slope is a description of "
                  "change, not proof of a trend."),
    }
    if CONTINUOUS:
        ou.continuous_meta(out, -lim, lim, ou.RWG, "symmetric about 0, fixed across years")
        out["scale"] = "linear, symmetric about 0 (fixed across years: 98th percentile of |slope|)"
        if L.get("native"):
            out["smoothing"] = (f"slopes averaged onto the native {L['native'][0]}° cells, then bilinear interpolation "
                                "to the display pixels")
    with open(os.path.join(RASTERS, od, "meta.json"), "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    sz = sum(os.path.getsize(p) for p in glob.glob(os.path.join(RASTERS, od, "*.png")))
    big = max(os.path.getsize(p) for p in glob.glob(os.path.join(RASTERS, od, "*.png")))
    med = {e: float(np.nanmedian(s)) for e, s in slopes.items()}
    print(f"{key}: lim=±{lim:g} {units} dates={out['dates']} total={sz/1e6:.2f} MB max_png={big/1e3:.0f} KB "
          f"median_slope={ {k: round(v, 4) for k, v in med.items()} } {time.time()-t0:.0f}s", flush=True)
    return out


def main():
    global CONTINUOUS
    args = sys.argv[1:]
    if "--continuous" in args:
        CONTINUOUS = True
        args = [a for a in args if a != "--continuous"]
    want = set(args)
    for L in LAYERS:
        if want and L["key"] not in want:
            continue
        try:
            process(L)
        except Exception as ex:  # keep going: one missing source grid must not stop the rest
            import traceback
            traceback.print_exc()
            print("FAILED", L["key"], ex, flush=True)


if __name__ == "__main__":
    main()
