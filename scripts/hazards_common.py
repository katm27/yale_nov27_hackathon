"""Shared helpers for the hazard / land pipelines (fire, water, S5P, land cover, static).

Design: zonal statistics are computed in each source's native grid (MODIS sinusoidal is
equal-area, so pixel counts x pixel area = km2), using county label rasters rasterised onto
that grid. Web overlays are built by reprojecting native tiles onto one fixed EPSG:3857 canvas
(see DATA_CONTRACT.md section 3).
"""
import json
import os
from pathlib import Path

import numpy as np
import geopandas as gpd
import rasterio
from rasterio import features
from rasterio.warp import reproject, Resampling, transform_bounds
from rasterio.transform import from_bounds
from rasterio.windows import Window

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "5")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif,.TIF,.tiff")
os.environ.setdefault("GDAL_CACHEMAX", "512")

REPO = Path(__file__).resolve().parents[1]
COUNTIES = REPO / "data" / "counties.geojson"
PROC = REPO / "data" / "processed"
META = PROC / "meta"
RASTERS = REPO / "docs" / "rasters"
BBOX = [23.4, 3.4, 36.0, 12.3]
STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
START, END = "2018-01-01", "2025-12-31"

_counties = None


def counties():
    global _counties
    if _counties is None:
        g = gpd.read_file(COUNTIES).to_crs("EPSG:4326")
        g = g.reset_index(drop=True)
        g["label"] = np.arange(1, len(g) + 1, dtype=np.int32)
        _counties = g
    return _counties


def county_ids():
    return counties()["district_id"].tolist()


def stac_client():
    import pystac_client
    import planetary_computer as pc
    return pystac_client.Client.open(STAC_URL, modifier=pc.sign_inplace)


def search(collection, datetime, bbox=BBOX, query=None):
    cat = stac_client()
    kw = dict(collections=[collection], bbox=bbox, datetime=datetime)
    if query:
        kw["query"] = query
    return list(cat.search(**kw).items())


# ---------------------------------------------------------------- native-grid zonal stats
_label_cache = {}


def window_for_bbox(src, pad=2):
    """Window of `src` covering the South Sudan bbox (in src CRS), clipped to the raster."""
    b = counties().total_bounds
    l, bt, r, t = transform_bounds("EPSG:4326", src.crs, b[0] - 0.05, b[1] - 0.05, b[2] + 0.05, b[3] + 0.05, densify_pts=50)
    win = rasterio.windows.from_bounds(l, bt, r, t, src.transform)
    c0 = max(0, int(np.floor(win.col_off)) - pad); r0 = max(0, int(np.floor(win.row_off)) - pad)
    c1 = min(src.width, int(np.ceil(win.col_off + win.width)) + pad)
    r1 = min(src.height, int(np.ceil(win.row_off + win.height)) + pad)
    if c1 <= c0 or r1 <= r0:
        return None
    return Window(c0, r0, c1 - c0, r1 - r0)


def labels_for(crs, transform, shape, key=None, all_touched=False):
    """County label raster (0 = outside, 1..N = counties().label) on an arbitrary grid."""
    k = key or (str(crs), tuple(transform)[:6], shape)
    if k not in _label_cache:
        g = counties().to_crs(crs)
        _label_cache[k] = features.rasterize(
            zip(g.geometry, g.label), out_shape=shape, transform=transform, fill=0,
            dtype="int32", all_touched=all_touched)
    return _label_cache[k]


def bincount(labels, values=None, n=None):
    n = n or (len(counties()) + 1)
    lab = labels.ravel()
    if values is None:
        return np.bincount(lab, minlength=n)[:n]
    return np.bincount(lab, weights=np.asarray(values, dtype="float64").ravel(), minlength=n)[:n]


# ---------------------------------------------------------------- web overlay canvas (EPSG:3857)
class Canvas:
    """Fixed EPSG:3857 canvas over South Sudan, max 1000 px on the long side."""

    def __init__(self, max_px=1000):
        b = counties().total_bounds
        pad = 0.02
        self.ll = (b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad)
        l, bt, r, t = transform_bounds("EPSG:4326", "EPSG:3857", *self.ll)
        w, h = r - l, t - bt
        if w >= h:
            self.width = max_px; self.height = int(round(max_px * h / w))
        else:
            self.height = max_px; self.width = int(round(max_px * w / h))
        self.transform = from_bounds(l, bt, r, t, self.width, self.height)
        self.crs = "EPSG:3857"
        self.shape = (self.height, self.width)
        g = counties().to_crs(self.crs)
        self.mask = features.rasterize(((geom, 1) for geom in g.geometry), out_shape=self.shape,
                                       transform=self.transform, fill=0, dtype="uint8", all_touched=True).astype(bool)
        # lat/lon of image corners for Leaflet ImageOverlay: [[south, west], [north, east]]
        self.bounds_latlon = [[self.ll[1], self.ll[0]], [self.ll[3], self.ll[2]]]

    def new(self):
        return np.full(self.shape, np.nan, dtype="float32")

    def add(self, canvas_arr, src_arr, src_transform, src_crs, resampling=Resampling.average, src_nodata=np.nan):
        tmp = np.full(self.shape, np.nan, dtype="float32")
        reproject(np.asarray(src_arr, dtype="float32"), tmp, src_transform=src_transform, src_crs=src_crs,
                  src_nodata=src_nodata, dst_transform=self.transform, dst_crs=self.crs, dst_nodata=np.nan,
                  resampling=resampling)
        fill = np.isnan(canvas_arr) & ~np.isnan(tmp)
        canvas_arr[fill] = tmp[fill]
        return canvas_arr

    def save_png(self, arr, path, vmin, vmax, cmap, zero_transparent=False, nodata_rgba=(0, 0, 0, 0), n_colors=64):
        import matplotlib
        from PIL import Image
        cm = matplotlib.colormaps[cmap] if isinstance(cmap, str) else cmap
        a = np.clip((arr - vmin) / (vmax - vmin), 0, 1)
        q = np.round(a * (n_colors - 1))
        lut = (cm(np.linspace(0, 1, n_colors)) * 255).astype("uint8")
        idx = np.where(np.isnan(arr), 0, q).astype(int)
        rgba = lut[idx]
        rgba[..., 3] = 220
        bad = np.isnan(arr) | ~self.mask
        rgba[bad] = nodata_rgba
        rgba[~self.mask] = (0, 0, 0, 0)
        if zero_transparent:
            rgba[(arr <= vmin) & self.mask & ~np.isnan(arr)] = (0, 0, 0, 0)
        img = Image.fromarray(rgba, "RGBA")
        img = img.quantize(colors=min(n_colors + 4, 255), method=Image.Quantize.FASTOCTREE)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        img.save(path, optimize=True)


def write_raster_meta(key, label, units, canvas, vmin, vmax, cmap, native_res, dates, source, notes=""):
    d = RASTERS / key
    d.mkdir(parents=True, exist_ok=True)
    meta = {"key": key, "label": label, "units": units, "bounds": canvas.bounds_latlon, "vmin": vmin, "vmax": vmax,
            "colormap": cmap, "native_resolution": native_res, "dates": sorted(dates), "source": source,
            "crs": "EPSG:3857", "notes": notes}
    (d / "meta.json").write_text(json.dumps(meta, indent=1))


def write_meta(name, entries):
    META.mkdir(parents=True, exist_ok=True)
    (META / f"{name}.json").write_text(json.dumps(entries, indent=1, ensure_ascii=False))


def months(start=START, end=END):
    import pandas as pd
    return [d.strftime("%Y-%m") for d in pd.date_range(start, end, freq="MS")]
