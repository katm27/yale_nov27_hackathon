#!/usr/bin/env python3
"""TerraClimate (~4 km, monthly) for South Sudan: county means, extreme-weather flags, raster overlays.

Source: Abatzoglou et al. 2018, TerraClimate v1.1, served by the Northwest Knowledge Network THREDDS
  https://thredds.northwestknowledge.net/thredds/catalog/TERRACLIMATE_ALL/data/catalog.html
Subsets are pulled with THREDDS NCSS (one request per variable-year, bbox only, all 12 months):
  https://thredds.northwestknowledge.net/thredds/ncss/TERRACLIMATE_ALL/data/TerraClimate_<var>_<year>.nc
     ?var=<var>&north=12.4&south=3.3&west=23.3&east=36.1&temporal=all&accept=netcdf

Outputs
  data/processed/terraclimate_county_monthly.csv   (long format, 2018-01..2025-12, ids prefixed tc_)
  data/processed/meta/terraclimate.json
  docs/rasters/tc_<var>/YYYY-MM.png + meta.json   (ppt, tmax, soil, aet, pdsi, def, ws)

County aggregation: area-weighted mean. Each 1/24° cell gets a weight = fraction of the cell covered by the
county (estimated by rasterising the county on a 5x5 sub-grid per cell), times cos(latitude).

Extreme-weather flags (0/1 per county-month), against the county's own 1991-2020 climatology for the same
calendar month (county-mean series, 30 values per calendar month, empirical percentiles):
  tc_extreme_wet  : ppt  > 90th percentile
  tc_extreme_dry  : ppt  < 10th percentile (only where the 10th pct > 0, i.e. not in normally rain-free months)
  tc_extreme_heat : tmax > 90th percentile
  tc_extreme_count: sum of the three flags

Usage:  python scripts/fetch_terraclimate.py [--no-download] [--no-rasters] [--workdir DIR]
Raw subsets (~350 MB) are cached in --workdir (default: $TC_WORKDIR or /tmp/terraclimate_raw), not committed.
"""
import argparse
import json
import os
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr
from affine import Affine
from PIL import Image
from pyproj import Transformer
from rasterio.features import geometry_mask, rasterize
from rasterio.warp import Resampling, calculate_default_transform, reproject

ROOT = Path(__file__).resolve().parents[1]
COUNTIES = ROOT / "data/counties.geojson"
OUT_CSV = ROOT / "data/processed/terraclimate_county_monthly.csv"
OUT_META = ROOT / "data/processed/meta/terraclimate.json"
RASTERS = ROOT / "docs/rasters"
SOURCE_MD = ROOT / "data/raw/terraclimate/SOURCE.md"

BBOX = dict(north=12.4, south=3.3, west=23.3, east=36.1)
YEARS = list(range(2018, 2026))
BASE_YEARS = list(range(1991, 2021))
BASE_VARS = ["ppt", "tmax"]
NCSS = "https://thredds.northwestknowledge.net/thredds/ncss/TERRACLIMATE_ALL/data/TerraClimate_{f}_{y}.nc"
SRC_URL = "https://www.climatologylab.org/terraclimate.html"
SRC = "TerraClimate v1.1 (Abatzoglou et al. 2018) via NKN THREDDS"
RES = "1/24° (~4 km)"

# id, file var, nc var, label, group, units, higher_is, index_ok, notes
VARS = [
    ("ppt", "ppt", "ppt", "Precipitation (TerraClimate)", "Precipitation", "mm/month", "better", True,
     "About 40% lower than IMERG (precip_mm) on average for 2018-2025; use for spatial detail, not absolute totals."),
    ("tmax", "tmax", "tmax", "Max temperature (TerraClimate)", "Temperature", "°C", "worse", False,
     "Monthly mean of daily maximum temperature."),
    ("tmin", "tmin", "tmin", "Min temperature (TerraClimate)", "Temperature", "°C", "worse", False,
     "Monthly mean of daily minimum temperature."),
    ("aet", "aet", "aet", "Actual evapotranspiration", "Water balance", "mm/month", "better", True,
     "Water actually evaporated/transpired; tracks vegetation water use."),
    ("pet", "pet", "pet", "Reference evapotranspiration (Penman-Monteith)", "Water balance", "mm/month",
     "worse", True, ""),
    ("def", "def", "def", "Climatic water deficit", "Water balance", "mm/month", "worse", False,
     "PET minus AET; 0 when demand is fully met, so ratio to 2018 can be undefined."),
    ("soil", "soil", "soil", "Soil moisture (TerraClimate)", "Soil moisture", "mm (end of month)", "better",
     True, "Plant-extractable soil water at end of month."),
    ("ws", "ws", "ws", "Wind speed (10 m)", "Wind", "m/s", "neutral", True, ""),
    ("pdsi", "PDSI", "PDSI", "Palmer Drought Severity Index", "Drought", "index (-4 dry .. +4 wet)", "better",
     False, "Negative = drought. Not ratio-indexable. TerraClimate PDSI is strongly negative across South Sudan "
     "in 2018-2025 (country mean ~ -6.6) because its ERA5-driven precipitation is well below its 1991-2020 "
     "climatology; treat as relative, and cross-check with IMERG-based spei3."),
    ("vpd", "vpd", "vpd", "Vapour pressure deficit", "Atmosphere", "kPa", "worse", True,
     "Atmospheric dryness; high VPD stresses crops."),
    ("srad", "srad", "srad", "Downward shortwave radiation", "Atmosphere", "W/m²", "neutral", True, ""),
    ("q", "q", "q", "Runoff", "Water balance", "mm/month", "neutral", False,
     "Often 0 in the dry season, so ratio to 2018 can be undefined."),
]
NCVAR = {v[0]: v[2] for v in VARS}
FILEVAR = {v[0]: v[1] for v in VARS}

# raster overlays: key var -> (colormap name, anchor colours)
OVERLAYS = {
    "ppt": ("blues", ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"]),
    "soil": ("ylgnbu", ["#ffffd9", "#c7e9b4", "#41b6c4", "#225ea8", "#081d58"]),
    "aet": ("greens", ["#f7fcf5", "#c7e9c0", "#74c476", "#238b45", "#00441b"]),
    "tmax": ("inferno", ["#000004", "#420a68", "#932667", "#dd513a", "#fca50a", "#fcffa4"]),
    "pdsi": ("brbg", ["#8c510a", "#d8b365", "#f6e8c3", "#f5f5f5", "#c7eae5", "#5ab4ac", "#01665e"]),
    "def": ("oranges", ["#fff5eb", "#fdd0a2", "#fd8d3c", "#d94801", "#7f2704"]),
    "ws": ("purples", ["#fcfbfd", "#dadaeb", "#9e9ac8", "#6a51a3", "#3f007d"]),
}


def fetch(var, year, workdir):
    f = FILEVAR[var]
    out = workdir / f"{var}_{year}.nc"
    if out.exists() and out.stat().st_size > 10000:
        return out
    url = (NCSS.format(f=f, y=year) + f"?var={NCVAR[var]}&north={BBOX['north']}&south={BBOX['south']}"
           f"&west={BBOX['west']}&east={BBOX['east']}&temporal=all&accept=netcdf")
    for attempt in range(4):
        try:
            tmp = out.with_suffix(".part")
            with urllib.request.urlopen(url, timeout=300) as r, open(tmp, "wb") as fh:
                fh.write(r.read())
            tmp.rename(out)
            return out
        except Exception as e:  # noqa: BLE001
            print(f"  retry {var} {year}: {e}")
            time.sleep(5 * (attempt + 1))
    print(f"FAILED {var} {year}")
    return None


def load(var, years, workdir):
    arrs = []
    for y in years:
        p = workdir / f"{var}_{y}.nc"
        if not p.exists():
            continue
        with xr.open_dataset(p, engine="netcdf4") as ds:
            arrs.append(ds[NCVAR[var]].load())
    if not arrs:
        return None
    da = xr.concat(arrs, "time").sortby("time")
    return da.where(np.isfinite(da))


def weights(cty, lat, lon, sub=5):
    """(n_county, ny*nx) area-weight matrix (cell coverage fraction x cos lat)."""
    dy = float(lat[0] - lat[1])
    dx = float(lon[1] - lon[0])
    ny, nx = len(lat), len(lon)
    t = Affine(dx / sub, 0, float(lon[0]) - dx / 2, 0, -dy / sub, float(lat[0]) + dy / 2)
    coslat = np.cos(np.deg2rad(lat.values))[:, None] * np.ones((1, nx))
    W = np.zeros((len(cty), ny * nx), dtype="float64")
    for i, g in enumerate(cty.geometry):
        m = rasterize([(g, 1)], out_shape=(ny * sub, nx * sub), transform=t, dtype="uint8", all_touched=False)
        frac = m.reshape(ny, sub, nx, sub).mean(axis=(1, 3))
        if frac.sum() == 0:  # tiny polygon: fall back to all-touched
            m = rasterize([(g, 1)], out_shape=(ny * sub, nx * sub), transform=t, dtype="uint8",
                          all_touched=True)
            frac = m.reshape(ny, sub, nx, sub).mean(axis=(1, 3))
        W[i] = (frac * coslat).ravel()
    return W


def county_means(da, W):
    v = da.values.reshape(da.shape[0], -1)
    valid = np.isfinite(v)
    num = np.where(valid, v, 0) @ W.T
    den = valid.astype("float64") @ W.T
    with np.errstate(invalid="ignore", divide="ignore"):
        return num / den  # (time, county)


def to_long(arr, times, ids, variable):
    df = pd.DataFrame(arr, index=pd.DatetimeIndex(times).strftime("%Y-%m-01"), columns=ids)
    df = df.stack().rename("value").reset_index()
    df.columns = ["date", "county_id", "value"]
    df["variable"] = variable
    return df


def extremes(base_ts, cur_ts, var, q, above):
    """base_ts/cur_ts: DataFrame time x county. Return 0/1 flags for cur_ts."""
    bm = base_ts.index.month
    thr = base_ts.groupby(bm).quantile(q)  # month x county
    t = thr.loc[cur_ts.index.month].values
    if above:
        flag = cur_ts.values > t
    else:
        flag = (cur_ts.values < t) & (t > 0)
    flag = flag.astype(float)
    flag[np.isnan(cur_ts.values)] = np.nan
    return pd.DataFrame(flag, index=cur_ts.index, columns=cur_ts.columns)


class Overlay:
    def __init__(self, lat, lon, cty, max_px=900):
        dy = float(lat[0] - lat[1])
        dx = float(lon[1] - lon[0])
        self.src_t = Affine(dx, 0, float(lon[0]) - dx / 2, 0, -dy, float(lat[0]) + dy / 2)
        h, w = len(lat), len(lon)
        # crop destination to the country outline
        c3857 = cty.to_crs(3857)
        x0, y0, x1, y1 = c3857.total_bounds
        pad = 5000
        x0, y0, x1, y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
        scale = max(x1 - x0, y1 - y0) / max_px
        self.dw, self.dh = int(np.ceil((x1 - x0) / scale)), int(np.ceil((y1 - y0) / scale))
        self.dst_t = Affine(scale, 0, x0, 0, -scale, y1)
        self.shape = (h, w)
        self.outside = geometry_mask([c3857.union_all().buffer(1500)]  # buffer closes slivers between county polygons
                                     , out_shape=(self.dh, self.dw), transform=self.dst_t)
        tr = Transformer.from_crs(3857, 4326, always_xy=True)
        lon0, lat0 = tr.transform(x0, y1 - scale * self.dh)
        lon1, lat1 = tr.transform(x0 + scale * self.dw, y1)
        self.bounds = [[lat0, lon0], [lat1, lon1]]

    def warp(self, arr):
        dst = np.full((self.dh, self.dw), np.nan, dtype="float32")
        reproject(arr.astype("float32"), dst, src_transform=self.src_t, src_crs="EPSG:4326",
                  dst_transform=self.dst_t, dst_crs="EPSG:3857", resampling=Resampling.bilinear,
                  src_nodata=np.nan, dst_nodata=np.nan)
        return dst

    @staticmethod
    def palette(anchors, n=254):
        rgb = np.array([[int(h[i:i + 2], 16) for i in (1, 3, 5)] for h in anchors], dtype="float64")
        xs = np.linspace(0, 1, len(anchors))
        t = np.linspace(0, 1, n)
        return np.stack([np.interp(t, xs, rgb[:, k]) for k in range(3)], 1).round().astype("uint8")

    def save(self, arr, path, vmin, vmax, pal):
        dst = self.warp(arr)
        n = len(pal)
        idx = np.clip(np.round((dst - vmin) / (vmax - vmin) * (n - 1)), 0, n - 1)
        idx = np.where(np.isnan(dst) | self.outside, 255, idx).astype("uint8")
        im = Image.fromarray(idx, "P")
        full = np.zeros((256, 3), dtype="uint8")
        full[:n] = pal
        im.putpalette(full.ravel().tolist())
        im.info["transparency"] = 255
        im.save(path, optimize=True, transparency=255)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-download", action="store_true")
    ap.add_argument("--no-rasters", action="store_true")
    ap.add_argument("--workdir", default=os.environ.get("TC_WORKDIR", "/tmp/terraclimate_raw"))
    a = ap.parse_args()
    workdir = Path(a.workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    jobs = [(v[0], y) for v in VARS for y in YEARS] + [(v, y) for v in BASE_VARS for y in BASE_YEARS]
    if not a.no_download:
        with ThreadPoolExecutor(4) as ex:
            res = list(ex.map(lambda j: (j, fetch(j[0], j[1], workdir)), jobs))
        missing = [j for j, p in res if p is None]
        print("downloaded; missing:", missing)

    cty = gpd.read_file(COUNTIES)[["district_id", "geometry"]]
    ids = cty.district_id.tolist()
    probe = load("ppt", [YEARS[0]], workdir)
    lat, lon = probe.lat, probe.lon
    W = weights(cty, lat, lon)
    print("weights: min cells-equiv per county", (W > 0).sum(1).min())

    frames, coverage = [], {}
    series = {}
    for v in VARS:
        var = v[0]
        da = load(var, YEARS, workdir)
        if da is None:
            print("no data", var)
            continue
        cm = county_means(da, W)
        series[var] = pd.DataFrame(cm, index=pd.DatetimeIndex(da.time.values).to_period("M").to_timestamp(),
                                   columns=ids)
        frames.append(to_long(cm, series[var].index, ids, f"tc_{var}"))
        coverage[var] = (str(series[var].index.min())[:7], str(series[var].index.max())[:7])
        print(var, coverage[var], np.nanmin(cm).round(2), np.nanmax(cm).round(2))

    # extremes vs 1991-2020 climatology
    base = {}
    for var in BASE_VARS:
        da = load(var, BASE_YEARS, workdir)
        base[var] = pd.DataFrame(county_means(da, W),
                                 index=pd.DatetimeIndex(da.time.values).to_period("M").to_timestamp(), columns=ids)
        print("baseline", var, base[var].index.min(), base[var].index.max(), len(base[var]))
    fl = {
        "tc_extreme_wet": extremes(base["ppt"], series["ppt"], "ppt", 0.9, True),
        "tc_extreme_dry": extremes(base["ppt"], series["ppt"], "ppt", 0.1, False),
        "tc_extreme_heat": extremes(base["tmax"], series["tmax"], "tmax", 0.9, True),
    }
    fl["tc_extreme_count"] = fl["tc_extreme_wet"] + fl["tc_extreme_dry"] + fl["tc_extreme_heat"]
    for k, df in fl.items():
        frames.append(to_long(df.values, df.index, ids, k))
        print(k, "mean rate", np.nanmean(df.values).round(3))

    out = pd.concat(frames)
    out = out.dropna(subset=["value"])
    out["value"] = out["value"].round(3)
    out = out[["county_id", "date", "variable", "value"]].sort_values(["variable", "county_id", "date"])
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False)
    print("wrote", OUT_CSV, len(out))

    meta = []
    for (var, _f, _n, label, group, units, hi, iok, notes) in VARS:
        if var not in coverage:
            continue
        m = dict(id=f"tc_{var}", label=label, category="environment", group=group, units=units, source=SRC,
                 source_url=SRC_URL, native_resolution=RES, temporal="monthly",
                 aggregation="area-weighted mean of 1/24° cells (cell coverage fraction x cos lat)",
                 higher_is=hi, index_ok=iok,
                 notes=(notes + f" Coverage {coverage[var][0]}..{coverage[var][1]}.").strip())
        if var in OVERLAYS:
            m["raster"] = f"tc_{var}"
        meta.append(m)
    xnote = ("County-mean value compared with the same county's 1991-2020 TerraClimate climatology for the "
             "same calendar month (empirical percentile over 30 years). 1 = extreme, 0 = not. 2018-2025 is drier and "
             "hotter than 1991-2020 in TerraClimate, so dry/heat flags fire ~30% of months and wet ~4%.")
    meta += [
        dict(id="tc_extreme_wet", label="Extreme wet month (flag)", group="Extreme weather",
             units="flag 0/1", higher_is="worse", notes="Precipitation above the 90th percentile. " + xnote),
        dict(id="tc_extreme_dry", label="Extreme dry month (flag)", group="Extreme weather",
             units="flag 0/1", higher_is="worse",
             notes="Precipitation below the 10th percentile; never flagged in months whose 10th pct is 0 "
                   "(normal dry season). " + xnote),
        dict(id="tc_extreme_heat", label="Extreme heat month (flag)", group="Extreme weather",
             units="flag 0/1", higher_is="worse", notes="Mean daily max temperature above the 90th percentile. "
             + xnote),
        dict(id="tc_extreme_count", label="Extreme-weather flags (count)", group="Extreme weather",
             units="count 0..3", higher_is="worse",
             notes="Sum of tc_extreme_wet, tc_extreme_dry, tc_extreme_heat. " + xnote),
    ]
    for m in meta[-4:]:
        m.update(category="environment", source=SRC + "; percentiles computed by team", source_url=SRC_URL,
                 native_resolution=RES, temporal="monthly", aggregation="flag on county-mean series",
                 index_ok=False)
    OUT_META.parent.mkdir(parents=True, exist_ok=True)
    OUT_META.write_text(json.dumps(meta, indent=1, ensure_ascii=False))

    SOURCE_MD.parent.mkdir(parents=True, exist_ok=True)
    SOURCE_MD.write_text(
        "# TerraClimate raw subsets (not committed, ~350 MB)\n\n"
        f"Re-create with `python scripts/fetch_terraclimate.py --workdir <dir>`.\n\n"
        "Per variable-year NCSS subset (bbox N12.4 S3.3 W23.3 E36.1, all months):\n\n"
        f"    {NCSS}?var=<var>&north=12.4&south=3.3&west=23.3&east=36.1&temporal=all&accept=netcdf\n\n"
        f"Variables {', '.join(FILEVAR.values())} for {YEARS[0]}-{YEARS[-1]}; "
        f"ppt and tmax also {BASE_YEARS[0]}-{BASE_YEARS[-1]} (climatology baseline for extreme flags).\n\n"
        f"Catalog: https://thredds.northwestknowledge.net/thredds/catalog/TERRACLIMATE_ALL/data/catalog.html\n"
        f"Citation: Abatzoglou, J.T. et al. (2018) Sci. Data 5:170191. License CC0.\n")

    if a.no_rasters:
        return
    ov = Overlay(lat, lon, cty)
    for var, (cmap, anchors) in OVERLAYS.items():
        da = load(var, YEARS, workdir)
        if da is None:
            continue
        # percentile over all in-country pixels and months
        inside = (W.sum(0) > 0).reshape(da.shape[1:])
        vals = da.values[:, inside]
        vmin, vmax = np.nanpercentile(vals, [2, 98]).astype(float)
        if var == "pdsi":  # symmetric for diverging scale
            m = max(abs(vmin), abs(vmax))
            vmin, vmax = -m, m
        vmin, vmax = round(vmin, 2), round(vmax, 2)
        key = f"tc_{var}"
        d = RASTERS / key
        d.mkdir(parents=True, exist_ok=True)
        pal = Overlay.palette(anchors)
        dates = []
        for i, t in enumerate(pd.DatetimeIndex(da.time.values)):
            ds = t.strftime("%Y-%m")
            ov.save(da.values[i], d / f"{ds}.png", vmin, vmax, pal)
            dates.append(ds)
        lbl = next(v for v in VARS if v[0] == var)
        (d / "meta.json").write_text(json.dumps(dict(
            key=key, label=lbl[3], units=lbl[5], bounds=ov.bounds, vmin=vmin, vmax=vmax, colormap=cmap,
            colors=anchors, scale="linear", native_resolution=RES, dates=dates, source=SRC,
            notes="Fixed colour scale = 2nd-98th percentile of all in-country pixels over all months"
                  + (" (symmetric about 0)" if var == "pdsi" else "") + "; bilinear reprojection to EPSG:3857."),
            indent=1, ensure_ascii=False))
        sz = sum(p.stat().st_size for p in d.glob("*.png"))
        print("raster", key, vmin, vmax, len(dates), f"{sz/1e6:.1f} MB")


if __name__ == "__main__":
    main()
