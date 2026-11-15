"""Shared helpers for the Google Earth Engine pipelines (gee_smap.py, gee_gldas_gws.py, gee_maiac_aod.py).

Authentication: a service-account JSON key whose PATH is in env var EE_SERVICE_ACCOUNT_KEY
(the account must be registered for Earth Engine and the key's project must have the Earth Engine API enabled;
override the project with EE_PROJECT). Nothing is printed from the key except the account e-mail.

Downloads are small monthly GeoTIFFs from ee.Image.getDownloadURL (GEO_TIFF, explicit crs_transform + dimensions so
every month lands on exactly the same grid). They are then regridded onto the shared 0.01 deg South Sudan grid of
scripts/fetch_appeears.py and averaged per county with fetch_appeears.county_rows (same zonal approach, same
>=5%-valid-cells rule), so GEE-derived series are directly comparable with the AppEEARS ones.

`--dry-run` in each script prints the request plan without importing credentials or contacting Earth Engine.
"""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_appeears as fa  # noqa: E402  (grid, county_rows, to_grid, render_rasters)

BBOX = fa.BBOX  # [W, S, E, N] = [23.4, 3.4, 36.0, 12.3]
MONTHS = fa.MONTHS  # 2018-01 .. 2025-12


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def init():
    """Initialise earthengine-api from the service-account key in EE_SERVICE_ACCOUNT_KEY."""
    import ee
    kp = os.environ.get("EE_SERVICE_ACCOUNT_KEY")
    if not kp or not Path(kp).exists():
        sys.exit("EE_SERVICE_ACCOUNT_KEY must point to a service-account JSON key file")
    info = json.loads(Path(kp).read_text())
    creds = ee.ServiceAccountCredentials(info["client_email"], key_file=kp)
    ee.Initialize(creds, project=os.environ.get("EE_PROJECT", info.get("project_id")),
                  opt_url="https://earthengine-highvolume.googleapis.com")
    log("Earth Engine initialised as", info["client_email"])
    return ee


def snapped_grid(res, origin=(-180.0, 90.0)):
    """Grid of cell size `res` deg aligned to `origin` that covers BBOX. Returns (crs_transform, (w, h))."""
    x0 = origin[0] + np.floor((BBOX[0] - origin[0]) / res) * res
    y1 = origin[1] - np.floor((origin[1] - BBOX[3]) / res) * res
    w = int(np.ceil((BBOX[2] - x0) / res - 1e-9))
    h = int(np.ceil((y1 - BBOX[1]) / res - 1e-9))
    return [float(res), 0.0, round(float(x0), 6), 0.0, -float(res), round(float(y1), 6)], (w, h)


def month_range(mk):
    y, m = int(mk[:4]), int(mk[5:])
    nxt = f"{y + (m == 12)}-{(m % 12) + 1:02d}-01"
    return f"{mk}-01", nxt


def download(img, bands, crs_transform, dims, dest, retries=5):
    """img: ee.Image (float); writes a multi-band GeoTIFF to dest (skips if present)."""
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    params = {"bands": bands, "crs": "EPSG:4326", "crs_transform": crs_transform,
              "dimensions": f"{dims[0]}x{dims[1]}", "format": "GEO_TIFF", "filePerBand": False}
    for a in range(retries):
        try:
            url = img.getDownloadURL(params)
            r = requests.get(url, timeout=600)
            r.raise_for_status()
            if r.content[:2] not in (b"II", b"MM"):
                raise RuntimeError(f"not a GeoTIFF: {r.content[:200]!r}")
            tmp = dest.with_suffix(".part")
            tmp.write_bytes(r.content)
            tmp.replace(dest)
            return dest
        except Exception as e:  # noqa
            if a == retries - 1:
                raise
            log("retry", dest.name, e)
            time.sleep(10 * (a + 1))


def read_bands(path):
    """-> dict band_description_or_index -> float32 array (nodata -> NaN), transform."""
    import rasterio
    out = {}
    with rasterio.open(path) as s:
        for i in range(1, s.count + 1):
            a = s.read(i).astype("float32")
            if s.nodata is not None:
                a[a == s.nodata] = np.nan
            out[s.descriptions[i - 1] or str(i)] = a
        return out, s.transform


def to_grid(arr, tf, resampling="nearest"):
    return fa.to_grid(arr, tf, resampling=resampling)


def save_grid(work, var, mk, grid):
    d = Path(work) / "grids" / var
    d.mkdir(parents=True, exist_ok=True)
    np.save(d / f"{mk}.npy", grid.astype("float32"))


def render(work, raster_defs):
    """Render docs/rasters/<key>/ PNGs with fetch_appeears.render_rasters from <work>/grids/<var>/*.npy."""
    old_w, old_r = fa.WORK, fa.RASTERS
    try:
        fa.WORK, fa.RASTERS = Path(work), raster_defs
        fa.render_rasters()
    finally:
        fa.WORK, fa.RASTERS = old_w, old_r
