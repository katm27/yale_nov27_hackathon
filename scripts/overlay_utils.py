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
    from points_temporal import keep_plain  # keep curated label/notes (scripts/team_dynamic_layers.py)
    entry = keep_plain(lst, entry)
    lst = [e for e in lst if e.get("key") != entry["key"]] + [entry]
    with open(p, "w") as f:
        json.dump(lst, f, indent=1, ensure_ascii=False)


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


# ----------------------------------------------------------------------------- continuous gradient overlays
RWG = ["#b2182b", "#ffffff", "#1b7837"]   # red (low / decrease) -> white (middle / no change) -> green (high / increase)
NODATA_HATCH = "black diagonal hatching (no valid data)"
_DST_CACHE = {}


def to_native(grid, res, origin=(-180.0, 90.0), src_transform=None):
    """Average a fine grid that was filled by nearest-neighbour from a coarse product (e.g. GLDAS 0.25 deg copied onto
    the 0.01 deg grid) back onto that product's native cells, so the overlay can be smoothed from the true cell values.
    Returns (array, transform) on the snapped native grid covering the 0.01 deg bbox."""
    from rasterio.transform import from_origin
    import fetch_appeears as fa
    W_, S_, E_, N_ = fa.BBOX
    x0 = origin[0] + np.floor((W_ - origin[0]) / res + 1e-9) * res
    y1 = origin[1] - np.floor((origin[1] - N_) / res + 1e-9) * res
    w = int(np.ceil((E_ - x0) / res - 1e-9))
    h = int(np.ceil((y1 - S_) / res - 1e-9))
    tf = from_origin(x0, y1, res, res)
    out = np.full((h, w), np.nan, "float32")
    reproject(grid.astype("float32"), out, src_transform=src_transform or fa.grid_tf(), src_crs="EPSG:4326",
              dst_transform=tf, dst_crs="EPSG:4326", src_nodata=np.nan, dst_nodata=np.nan,
              resampling=Resampling.average)
    return out, tf


def _dst_grid(shape, transform, crs, max_px, min_px):
    k = (shape, tuple(transform)[:6], str(crs), max_px, min_px)
    if k not in _DST_CACHE:
        h, w = shape
        left, top = transform.c, transform.f
        right, bottom = left + transform.a * w, top + transform.e * h
        dst_t, dw, dh = calculate_default_transform(crs, "EPSG:3857", w, h, left, bottom, right, top)
        target = min(max(max(dw, dh), min_px), max_px)
        scale = max(dw, dh) / target
        if scale != 1:
            dw, dh = int(round(dw / scale)), int(round(dh / scale))
            dst_t, dw, dh = calculate_default_transform(crs, "EPSG:3857", w, h, left, bottom, right, top,
                                                        dst_width=dw, dst_height=dh)
        c = counties().to_crs(3857)
        inside = ~geometry_mask(c.geometry, out_shape=(dh, dw), transform=dst_t, invert=False)
        from pyproj import Transformer
        tr = Transformer.from_crs(3857, 4326, always_xy=True)
        x0, y1 = dst_t.c, dst_t.f
        x1, y0 = x0 + dst_t.a * dw, y1 + dst_t.e * dh
        lon0, lat0 = tr.transform(x0, y0)
        lon1, lat1 = tr.transform(x1, y1)
        _DST_CACHE[k] = (dst_t, dw, dh, scale, inside, [[lat0, lon0], [lat1, lon1]])
    return _DST_CACHE[k]


def write_overlay_continuous(arr, transform, crs, key, date, vmin, vmax, colors=RWG, domain=None, log=False,
                             max_px=1000, min_px=700, levels=61, alpha=220, hatch=True,
                             transparent_below=None, upsample="bilinear"):
    """Continuous-colour overlay: reproject to EPSG:3857 (average when shrinking, BILINEAR when enlarging, so coarse
    cells blend smoothly instead of showing blocks), map vmin..vmax linearly (or log10) onto the colour ramp `colors`
    (61 evenly spaced shades = visually continuous), clip to the country. Pixels inside the country and inside
    `domain` (bool array on the source grid; default = whole country) with no value are drawn as black diagonal hatching.
    `upsample`: resampling when enlarging ("bilinear"; "nearest" for binned point counts such as fire detections).
    `transparent_below`: values <= this are left transparent (e.g. no fire / no flooding), not hatched.
    Saved as a palette PNG (<= 64 colours). Returns dict(bounds, width, height)."""
    dst_t, dw, dh, scale, inside, bounds = _dst_grid(arr.shape, transform, crs, max_px, min_px)
    dst = np.full((dh, dw), np.nan, dtype="float32")
    reproject(arr.astype("float32"), dst, src_transform=transform, src_crs=crs, dst_transform=dst_t,
              dst_crs="EPSG:3857", resampling=Resampling.average if scale > 1 else getattr(Resampling, upsample),
              src_nodata=np.nan, dst_nodata=np.nan)
    if domain is not None:
        dom = np.zeros((dh, dw), "uint8")
        reproject(domain.astype("uint8"), dom, src_transform=transform, src_crs=crs, dst_transform=dst_t,
                  dst_crs="EPSG:3857", resampling=Resampling.nearest, src_nodata=None, dst_nodata=0)
        dom = dom.astype(bool) & inside
    else:
        dom = inside
    if log:
        t = (np.log10(np.clip(dst, vmin, None)) - np.log10(vmin)) / (np.log10(vmax) - np.log10(vmin))
    else:
        t = (dst - vmin) / (vmax - vmin)
    t = np.clip(np.nan_to_num(t), 0, 1)
    rgb = np.array([[int(h[i:i + 2], 16) for i in (1, 3, 5)] for h in colors], "float32")
    xs = np.linspace(0, 1, len(colors))
    ramp = np.stack([np.interp(np.linspace(0, 1, levels), xs, rgb[:, k]) for k in range(3)], 1).round().astype("uint8")
    # palette: 0 transparent, 1..levels ramp, levels+1 hatch stripe, levels+2 hatch background
    pal = np.zeros((levels + 3, 3), "uint8")
    pal[1:levels + 1] = ramp
    idx = (1 + np.round(t * (levels - 1))).astype("uint8")
    ok = np.isfinite(dst) & inside
    if transparent_below is not None:
        ok &= ~(dst <= transparent_below)
    idx[~ok] = 0
    if hatch:
        yy, xx = np.indices(idx.shape)
        nd = dom & ~np.isfinite(dst)
        idx[nd] = np.where(((xx + yy) % 6 < 2)[nd], levels + 1, levels + 2)
    im = Image.fromarray(idx, "P")
    im.putpalette(pal.ravel().tolist())
    os.makedirs(os.path.join(RASTERS, key), exist_ok=True)
    im.save(os.path.join(RASTERS, key, f"{date}.png"), optimize=True,
            transparency=bytes([0] + [alpha] * levels + [235, 110]))
    return {"bounds": bounds, "width": dw, "height": dh}


def continuous_meta(meta, vmin, vmax, colors=RWG, how=""):
    """Update a raster meta.json dict for a continuous ramp (fields read by the app legend)."""
    meta.update({"continuous": True, "colors": list(colors), "vmin": vmin, "vmax": vmax, "palette": "rwg-continuous",
                 "bins": None, "colormap": "continuous red -> white -> green (red = low / decrease, white = middle / "
                                           "no change, green = high / increase)" + (f"; {how}" if how else ""),
                 "nodata_color": NODATA_HATCH, "crs": "EPSG:3857"})
    for k in ("recolored", "bin_labels"):
        meta.pop(k, None)
    return meta
