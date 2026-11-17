#!/usr/bin/env python
"""Per-cell land-cover class shares on the shared 0.01 deg (~1 km) South Sudan grid, from the Esri / Impact Observatory
10 m annual land use / land cover maps (io-lulc-annual-v02, Microsoft Planetary Computer), one grid per year.

Exactly the same sample as scripts/landcover_pipeline.py (the county shares lulc_*_pct): each UTM-zone tile is read
at its factor-8 COG overview (nearest-neighbour systematic 1-in-64 sample of the 10 m map, ~80 m), clipped to its own
6 x 8 deg grid cell so nothing is counted twice, and every sample pixel is assigned to the 0.01 deg cell it falls in.
Share (%) of class c in a cell = class-c samples / classified samples (no-data and cloud excluded) x 100.
The county value of landcover_pipeline.py is the same ratio summed over the county's samples, so the map and the
county series come from the same pixels (the county share = the sample-weighted mean of its cells' shares).

Output: $LULC_WORK/grids/lulc_<class>_pct/YYYY.npy (float32, NaN = no classified sample), used by
scripts/continuous_rasters.py (map) and scripts/raster_trends.py --continuous (per-pixel Sen's slope).
Usage: python scripts/landcover_grids.py
"""
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import planetary_computer as pc
import rasterio
from rasterio import features
from rasterio.enums import Resampling
from rasterio.warp import reproject

sys.path.insert(0, str(Path(__file__).parent))
import hazards_common as hc  # noqa: E402
import fetch_appeears as fa  # noqa: E402
from landcover_pipeline import CLASSES, FACTOR, cell_box  # noqa: E402

SCRATCH = os.environ.get("RT_SCRATCH",
                         "/tmp/claude-0/-home-user-yale-nov27-hackathon/b7acc7ce-9c21-59ae-8208-6da6aae060da/scratchpad")
WORK = Path(os.environ.get("LULC_WORK", os.path.join(SCRATCH, "lulc", "work")))
NCELL = fa.H * fa.W


def process(item):
    tile, year = item.id.split("-")[0], item.id.split("-")[1]
    with rasterio.open(pc.sign(item.assets["data"].href.split("?")[0])) as src:
        win = hc.window_for_bbox(src)
        if win is None:
            return None
        out_shape = (int(win.height // FACTOR), int(win.width // FACTOR))
        arr = src.read(1, window=win, out_shape=out_shape, resampling=Resampling.nearest)
        wt = src.window_transform(win) * rasterio.Affine.scale(win.width / out_shape[1], win.height / out_shape[0])
        crs = src.crs
    # 0.01 deg cell index of every sample pixel (nearest = the cell containing the pixel centre)
    cid = np.arange(NCELL, dtype="int32").reshape(fa.H, fa.W)
    idx = np.full(arr.shape, -1, "int32")
    reproject(cid, idx, src_transform=fa.grid_tf(), src_crs="EPSG:4326", src_nodata=-1, dst_transform=wt, dst_crs=crs,
              dst_nodata=-1, resampling=Resampling.nearest)
    import geopandas as gpd
    inbox = features.rasterize([(gpd.GeoSeries([cell_box(tile)], crs=4326).to_crs(crs).iloc[0], 1)],
                               out_shape=arr.shape, transform=wt, fill=0, dtype="uint8").astype(bool)
    ok = inbox & (idx >= 0)
    res = {c: np.bincount(idx[ok & (arr == c)], minlength=NCELL) for c in CLASSES}
    print(item.id, arr.shape, int(ok.sum()), flush=True)
    return year, res


def main():
    items = [it for it in hc.search("io-lulc-annual-v02", None)
             if it.id.split("-")[0][:2] in ("34", "35", "36", "37") and it.id.split("-")[0][2] in "NP"]
    print(len(items), "items, years", sorted({it.id.split("-")[1] for it in items}), flush=True)
    tot = {}
    with ThreadPoolExecutor(3) as ex:
        for r in ex.map(process, items):
            if not r:
                continue
            year, res = r
            t = tot.setdefault(year, {c: np.zeros(NCELL) for c in CLASSES})
            for c, v in res.items():
                t[c] += v
    for year, t in sorted(tot.items()):
        valid = sum(t.values())
        for c, name in CLASSES.items():
            with np.errstate(invalid="ignore", divide="ignore"):
                g = np.where(valid > 0, 100 * t[c] / np.maximum(valid, 1), np.nan).reshape(fa.H, fa.W).astype("float32")
            d = WORK / "grids" / f"lulc_{name}_pct"
            d.mkdir(parents=True, exist_ok=True)
            np.save(d / f"{year}.npy", g)
        # also keep the sample counts so county shares can be re-derived exactly (sample-weighted)
        np.save(WORK / "grids" / f"valid_{year}.npy", valid.reshape(fa.H, fa.W).astype("float32"))
        print(year, "done", flush=True)


if __name__ == "__main__":
    main()
