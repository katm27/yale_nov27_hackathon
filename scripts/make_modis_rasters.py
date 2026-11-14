#!/usr/bin/env python
"""Render MODIS monthly grids (from fetch_modis_land.py) to web-map PNG overlays.

Writes docs/rasters/<key>/YYYY-MM.png + meta.json (DATA_CONTRACT section 3):
EPSG:3857, transparent outside South Sudan, fixed colour scale, 8-bit palette PNG.
In-country pixels with no valid observation (cloud / water fill) are drawn light grey,
semi-transparent.

Usage: MODIS_WORK=<work dir> python scripts/make_modis_rasters.py [--width 1000]
"""
import argparse
import json
import os
from pathlib import Path

import geopandas as gpd
import numpy as np
from matplotlib import colormaps
from matplotlib.colors import LinearSegmentedColormap
from PIL import Image
from rasterio import features
from rasterio.transform import from_bounds
from rasterio.warp import Resampling, reproject, transform_bounds

import fetch_modis_land as F

ROOT = F.ROOT
OUT = ROOT / "docs" / "rasters"

NDVI_CMAP = LinearSegmentedColormap.from_list(
    "ndvi", ["#7f4a10", "#b8863b", "#e3cf8c", "#d9ef8b", "#91cf60", "#3f9a3f", "#145a24", "#06331a"])
ET_CMAP = LinearSegmentedColormap.from_list("et", colormaps["Blues"](np.linspace(0.12, 1.0, 256)))

LAYERS = [
    dict(key="modis_ndvi", var="modis_ndvi", label="NDVI (MODIS, monthly max)", units="NDVI",
         vmin=0.1, vmax=0.9, cmap=NDVI_CMAP, cmap_name="brown-yellow-green",
         native="500 m MODIS, rendered from ~1 km (0.01°) grid",
         source="MODIS MOD13A1/MYD13A1 v061 via Microsoft Planetary Computer"),
    dict(key="modis_lst_day", var="modis_lst_day_c", label="Daytime land surface temperature (MODIS)",
         units="°C", vmin=20.0, vmax=55.0, cmap=colormaps["inferno"], cmap_name="inferno",
         native="1 km MODIS (0.01° grid)",
         source="MODIS MOD11A2 v061 (Terra) via Microsoft Planetary Computer"),
    dict(key="modis_et", var="modis_et_mm", label="Annual evapotranspiration (MODIS)", units="mm/year",
         vmin=100.0, vmax=1500.0, cmap=ET_CMAP, cmap_name="blues", temporal="annual",
         native="500 m MODIS, rendered from ~1 km (0.01°) grid",
         source="MODIS MOD16A3GF v061 (annual, gap-filled) via Microsoft Planetary Computer"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=900)
    ap.add_argument("--levels", type=int, default=48, help="number of colour steps")
    a = ap.parse_args()

    g = gpd.read_file(ROOT / "data" / "counties.geojson")
    w, s, e, n = g.total_bounds
    pad = 0.05
    w, s, e, n = w - pad, s - pad, e + pad, n + pad
    mx0, my0, mx1, my1 = transform_bounds("EPSG:4326", "EPSG:3857", w, s, e, n)
    width = a.width
    height = int(round(width * (my1 - my0) / (mx1 - mx0)))
    dtf = from_bounds(mx0, my0, mx1, my1, width, height)
    gm = g.to_crs("EPSG:3857")
    inside = features.rasterize(((geom, 1) for geom in gm.geometry), out_shape=(height, width),
                                transform=dtf, fill=0, dtype="uint8").astype(bool)

    for L in LAYERS:
        gdir = F.WORK / "grids" / L["var"]
        files = sorted(gdir.glob("*.npy"))
        if not files:
            print("no grids for", L["var"])
            continue
        od = OUT / L["key"]
        od.mkdir(parents=True, exist_ok=True)
        # palette: 0 transparent, 1..254 colour ramp, 255 no-data grey
        ramp = (L["cmap"](np.linspace(0, 1, 254))[:, :3] * 255).astype("uint8")
        pal = np.zeros((256, 3), "uint8")
        pal[1:255] = ramp
        pal[255] = (190, 190, 190)
        alpha = bytes([0] + [255] * 254 + [110])
        dates = []
        tot = 0
        for f in files:
            grid = np.load(f)
            dst = np.full((height, width), np.nan, "float32")
            reproject(grid, dst, src_transform=F.GRID_TF, src_crs="EPSG:4326", src_nodata=np.nan,
                      dst_transform=dtf, dst_crs="EPSG:3857", dst_nodata=np.nan,
                      resampling=Resampling.average)
            t = np.clip((dst - L["vmin"]) / (L["vmax"] - L["vmin"]), 0, 1)
            # quantise to a.levels discrete steps (keeps PNGs small), mapped onto the 254-entry ramp
            q = np.minimum(np.floor(t * a.levels), a.levels - 1) / (a.levels - 1)
            idx = np.where(np.isfinite(dst), 1 + np.round(q * 253), 255).astype("uint8")
            idx[~inside] = 0
            im = Image.fromarray(idx, mode="P")
            im.putpalette(pal.ravel().tolist())
            im.info["transparency"] = alpha
            p = od / f"{f.stem}.png"
            im.save(p, optimize=True, transparency=alpha)
            tot += p.stat().st_size
            dates.append(f.stem)
        meta = {"key": L["key"], "label": L["label"], "units": L["units"],
                "bounds": [[round(s, 5), round(w, 5)], [round(n, 5), round(e, 5)]],
                "vmin": L["vmin"], "vmax": L["vmax"], "colormap": L["cmap_name"],
                "colors": ["#%02x%02x%02x" % tuple(c) for c in ramp[::25]] + ["#%02x%02x%02x" % tuple(ramp[-1])],
                "nodata_color": "#bebebe (semi-transparent: cloud-masked / water / no retrieval)",
                "native_resolution": L["native"], "dates": dates, "source": L["source"],
                "crs": "EPSG:3857", "width": width, "height": height}
        if L.get("temporal"):
            meta["temporal"] = L["temporal"]
            meta["notes"] = "Annual product: one image per year, file named YYYY-07.png."
        (od / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
        print(f"{L['key']}: {len(dates)} images, {tot/1e6:.1f} MB, max {max((od/(d+'.png')).stat().st_size for d in dates)/1e3:.0f} KB")


if __name__ == "__main__":
    main()
