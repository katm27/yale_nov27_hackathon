"""Annual land cover shares per South Sudan county from Esri / Impact Observatory 10 m annual LULC
(io-lulc-annual-v02, Microsoft Planetary Computer), 2017-2023 (latest year on PC).

Read at ~80 m by using the COG's internal overview (factor 8 = nearest-neighbour systematic sample
of the 10 m map), so class shares are unbiased sample estimates (built area in small towns is noisy).
Each UTM-zone tile is clipped to its own 6 x 8 deg grid cell so no area is double counted.
Output: data/processed/landcover_county_annual.csv (date YYYY-07-01), meta landcover.json.
"""
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import planetary_computer as pc
from rasterio import features
from rasterio.enums import Resampling
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).parent))
import hazards_common as hc

FACTOR = 8
CLASSES = {1: "water", 2: "trees", 4: "flooded_veg", 5: "crop", 7: "built", 8: "bare", 11: "rangeland"}
LABELS = {"water": "Water", "trees": "Trees", "flooded_veg": "Flooded vegetation", "crop": "Cropland",
          "built": "Built area", "bare": "Bare ground", "rangeland": "Rangeland (grass/shrub)"}
OUT = hc.PROC / "landcover_county_annual.csv"


def cell_box(tile):
    zone, band = int(tile[:2]), tile[2]
    west = -180 + (zone - 1) * 6
    south = {"N": 0, "P": 8}[band]
    return box(west, south, west + 6, south + 8)


def process(item):
    tile = item.id.split("-")[0]
    g = hc.counties()
    clip = g.copy()
    clip["geometry"] = g.geometry.intersection(cell_box(tile))
    clip = clip[~clip.geometry.is_empty]
    if clip.empty:
        return None
    with rasterio.open(pc.sign(item.assets["data"].href.split("?")[0])) as src:
        win = hc.window_for_bbox(src)
        if win is None:
            return None
        out_shape = (int(win.height // FACTOR), int(win.width // FACTOR))
        arr = src.read(1, window=win, out_shape=out_shape, resampling=Resampling.nearest)
        wt = src.window_transform(win) * rasterio.Affine.scale(win.width / out_shape[1], win.height / out_shape[0])
        cl = clip.to_crs(src.crs)
    lab = features.rasterize(zip(cl.geometry, cl.label), out_shape=arr.shape, transform=wt, fill=0, dtype="int32")
    n = len(g) + 1
    res = {c: np.bincount(lab[arr == c], minlength=n) for c in list(CLASSES) + [0, 10]}
    print(item.id, arr.shape, "px", int((lab > 0).sum()), flush=True)
    return item.id.split("-")[1], res


def main():
    items = [it for it in hc.search("io-lulc-annual-v02", None)
             if it.id.split("-")[0][:2] in ("34", "35", "36", "37") and it.id.split("-")[0][2] in "NP"]
    with ThreadPoolExecutor(3) as ex:
        results = [r for r in ex.map(process, items) if r]
    n = len(hc.counties()) + 1
    tot = {}
    for year, res in results:
        t = tot.setdefault(year, {c: np.zeros(n) for c in list(CLASSES) + [0, 10]})
        for c, v in res.items():
            t[c] += v
    ids = hc.county_ids()
    rows = []
    for year, t in sorted(tot.items()):
        valid = sum(t[c] for c in CLASSES)  # exclude no-data and cloud
        for i, cid in enumerate(ids, start=1):
            if valid[i] == 0:
                continue
            for c, name in CLASSES.items():
                rows.append((cid, f"{year}-07-01", f"lulc_{name}_pct", round(100 * t[c][i] / valid[i], 4)))
    df = pd.DataFrame(rows, columns=["county_id", "date", "variable", "value"]).sort_values(["variable", "county_id", "date"])
    df.to_csv(OUT, index=False)
    hib = {"crop": "neutral", "built": "neutral", "trees": "better", "water": "neutral", "flooded_veg": "neutral",
           "bare": "worse", "rangeland": "neutral"}
    hc.write_meta("landcover", [dict(
        id=f"lulc_{k}_pct", label=f"Land cover: {LABELS[k]} share", category="environment", group="Land cover",
        units="% of county land-cover pixels", source="Esri / Impact Observatory 10 m Annual Land Use Land Cover "
        "(io-lulc-annual-v02, Sentinel-2) via Microsoft Planetary Computer",
        source_url="https://planetarycomputer.microsoft.com/dataset/io-lulc-annual-v02",
        native_resolution="10 m (sampled at 80 m via COG overview)", temporal="annual",
        aggregation="class pixels / all classified pixels (excl. no-data, cloud) x 100; nearest-neighbour "
                    "systematic 1-in-64 sample of the 10 m map", higher_is=hib[k], index_ok=False, raster=None,
        notes="Annual product dated YYYY-07-01, years 2017-2023 (2024+ not on Planetary Computer). Year-to-year "
              "changes partly reflect classifier differences; flooded vegetation and water shares react to the "
              "2019-2022 floods.") for k in CLASSES.values()])
    print("wrote", OUT, len(df))


if __name__ == "__main__":
    main()
