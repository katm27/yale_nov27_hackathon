"""Shared helpers: county zonal sums, raster->Web-Mercator PNG overlays, contract writers."""
import json
import os

import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.features import geometry_mask
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COUNTIES = os.path.join(ROOT, "data", "counties.geojson")
PROC = os.path.join(ROOT, "data", "processed")
META = os.path.join(PROC, "meta")
DOCS_DATA = os.path.join(ROOT, "docs", "data")
RASTERS = os.path.join(ROOT, "docs", "rasters")


def counties():
    return gpd.read_file(COUNTIES)[["district_id", "name", "admin1", "geometry"]]


def write_meta(source, items):
    os.makedirs(META, exist_ok=True)
    with open(os.path.join(META, f"{source}.json"), "w") as f:
        json.dump(items, f, indent=1)


def add_points_meta(entry):
    """Append/replace an entry (by key) in data/processed/meta/points.json."""
    os.makedirs(META, exist_ok=True)
    p = os.path.join(META, "points.json")
    lst = []
    if os.path.exists(p):
        with open(p) as f:
            try:
                lst = json.load(f)
            except json.JSONDecodeError:
                lst = []
    lst = [e for e in lst if e.get("key") != entry["key"]] + [entry]
    with open(p, "w") as f:
        json.dump(lst, f, indent=1)


def write_long(source, df):
    """df columns county_id,date,variable,value."""
    os.makedirs(PROC, exist_ok=True)
    df = df.dropna(subset=["value"])[["county_id", "date", "variable", "value"]]
    df = df.sort_values(["variable", "county_id", "date"])
    df.to_csv(os.path.join(PROC, f"{source}_county_monthly.csv"), index=False)
    return df


def assign_county(gdf):
    """Spatial join points to counties -> adds county_id column (nearest for points just outside)."""
    c = counties()
    gdf = gdf.to_crs(4326)
    j = gpd.sjoin(gdf, c[["district_id", "geometry"]], how="left", predicate="within")
    j = j[~j.index.duplicated()]
    miss = j["district_id"].isna()
    if miss.any():
        nn = gpd.sjoin_nearest(gdf[miss].to_crs(32636), c[["district_id", "geometry"]].to_crs(32636),
                               how="left", max_distance=20000)
        nn = nn[~nn.index.duplicated()]
        j.loc[miss, "district_id"] = nn["district_id"]
    gdf = gdf.copy()
    gdf["county_id"] = j["district_id"].values
    return gdf


# anchor colors for simple colormaps (no matplotlib dependency)
CMAPS = {
    "magma_r": ["#fcfdbf", "#fd9f6c", "#de4968", "#8c2981", "#3b0f70", "#000004"],
    "ylorbr": ["#ffffe5", "#fee391", "#fec44f", "#fe9929", "#ec7014", "#cc4c02", "#8c2d04"],
    "greens": ["#f7fcf5", "#c7e9c0", "#74c476", "#31a354", "#006d2c", "#00441b"],
}


def colorize(norm, name):
    cols = CMAPS[name]
    rgb = np.array([[int(h[i:i + 2], 16) for i in (1, 3, 5)] for h in cols], dtype="float32")
    xs = np.linspace(0, 1, len(cols))
    out = np.zeros(norm.shape + (4,), dtype="uint8")
    for k in range(3):
        out[..., k] = np.interp(norm, xs, rgb[:, k]).astype("uint8")
    return out


def write_overlay(arr, transform, crs, key, date, vmin, vmax, cmap_name, meta_extra,
                  log=False, nodata_mask=None, max_px=1000, min_px=700):
    """Reproject arr to EPSG:3857, colorize with fixed scale, clip to country, save PNG + meta."""
    c = counties().to_crs(3857)
    h, w = arr.shape
    left = transform.c
    top = transform.f
    right = left + transform.a * w
    bottom = top + transform.e * h
    dst_t, dw, dh = calculate_default_transform(crs, "EPSG:3857", w, h, left, bottom, right, top)
    # target long side between min_px (crisp country mask for coarse grids) and max_px
    target = min(max(max(dw, dh), min_px), max_px)
    scale = max(dw, dh) / target
    if scale != 1:
        dw, dh = int(round(dw / scale)), int(round(dh / scale))
        dst_t, dw, dh = calculate_default_transform(crs, "EPSG:3857", w, h, left, bottom, right, top,
                                                    dst_width=dw, dst_height=dh)
    src = arr.astype("float32")
    if nodata_mask is not None:
        src = np.where(nodata_mask, np.nan, src)
    dst = np.full((dh, dw), np.nan, dtype="float32")
    reproject(src, dst, src_transform=transform, src_crs=crs, dst_transform=dst_t, dst_crs="EPSG:3857",
              resampling=Resampling.average if scale > 1 else Resampling.nearest, src_nodata=np.nan, dst_nodata=np.nan)
    outside = geometry_mask(c.geometry, out_shape=dst.shape, transform=dst_t, invert=False)
    if log:
        norm = (np.log10(np.clip(dst, vmin, None)) - np.log10(vmin)) / (np.log10(vmax) - np.log10(vmin))
    else:
        norm = (dst - vmin) / (vmax - vmin)
    norm = np.clip(norm, 0, 1)
    rgba = colorize(np.nan_to_num(norm), cmap_name)
    alpha = np.where(np.isnan(dst) | outside, 0, 220).astype("uint8")
    rgba[..., 3] = alpha
    os.makedirs(os.path.join(RASTERS, key), exist_ok=True)
    im = Image.fromarray(rgba, "RGBA").quantize(colors=64, method=Image.Quantize.FASTOCTREE)
    im.save(os.path.join(RASTERS, key, f"{date}.png"), optimize=True)
    # bounds in lat/lon
    from pyproj import Transformer
    tr = Transformer.from_crs(3857, 4326, always_xy=True)
    x0, y1 = dst_t.c, dst_t.f
    x1, y0 = x0 + dst_t.a * dw, y1 + dst_t.e * dh
    lon0, lat0 = tr.transform(x0, y0)
    lon1, lat1 = tr.transform(x1, y1)
    meta = {"key": key, "bounds": [[lat0, lon0], [lat1, lon1]], "vmin": vmin, "vmax": vmax,
            "colormap": cmap_name, "scale": "log10" if log else "linear"}
    meta.update(meta_extra)
    with open(os.path.join(RASTERS, key, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    return meta
