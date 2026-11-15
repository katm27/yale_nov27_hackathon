"""Monthly 'Water' base layer: where water is, month by month (NASA MODIS).

Built from two existing NASA MODIS overlays (both already on the 7-bin red→green scale, see recolor_rasters.py):
  * docs/rasters/surface_water  — national open water: fraction of clear MODIS MOD09A1/MYD09A1 observations classed as
    water (MNDWI > 0.1), monthly, 500 m. Bins 5–7 (≈ ≥57 % of looks wet) → water (deep blue);
    bin 4 (≈ 43–57 %) → partly / seasonally wet (light blue); lower bins and cloud → transparent.
  * docs/rasters/sudd_inundation — Sudd wetland classes from the MODIS inundation index (Xiao/Sakamoto rule):
    flooded vegetation → teal, open water → deep blue, dry → transparent.
Outputs docs/rasters/water_base_open/YYYY-MM.png and docs/rasters/water_base_floodveg/YYYY-MM.png (+ meta.json),
marked base_layer=true and no_recolor=true so the app draws them as an always-available base layer.
Usage: python scripts/water_base_layer.py
"""
import glob
import json
import os

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(ROOT, "docs", "rasters")
P7 = ["#d73027", "#fc8d59", "#fee08b", "#ffffbf", "#d9ef8b", "#91cf60", "#1a9850"]
rgb = lambda h: np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], float)
BIN = np.stack([rgb(h) for h in P7])
WATER, PARTLY, FLOODVEG = (8, 81, 156), (107, 174, 214), (0, 229, 255)


def classify(path):
    a = np.array(Image.open(path).convert("RGBA")).astype(float)
    d = ((a[..., None, :3] - BIN[None, None]) ** 2).sum(-1)
    b = d.argmin(-1)                       # bin index 0..6
    ok = (a[..., 3] >= 150) & (d.min(-1) < 400)   # visible, not the grey cloud veil
    return b, ok, a.shape[:2]


def write(out_dir, date, layers, shape):
    img = np.zeros(shape + (4,), "uint8")
    for mask, col, alpha in layers:
        img[mask, :3] = col
        img[mask, 3] = alpha
    os.makedirs(out_dir, exist_ok=True)
    Image.fromarray(img, "RGBA").quantize(colors=8, method=Image.Quantize.FASTOCTREE).save(os.path.join(out_dir, f"{date}.png"), optimize=True)


def main():
    src_meta = json.load(open(os.path.join(R, "surface_water", "meta.json")))
    dates = []
    for f in sorted(glob.glob(os.path.join(R, "surface_water", "*.png"))):
        b, ok, shape = classify(f)
        d = os.path.basename(f)[:-4]
        write(os.path.join(R, "water_base_open"), d, [(ok & (b == 3), PARTLY, 150), (ok & (b >= 4), WATER, 230)], shape)
        dates.append(d)
    json.dump({"key": "water_base_open", "label": "Water bodies & flood water (NASA MODIS, monthly)", "base_layer": True, "no_recolor": True,
               "units": "", "bounds": src_meta["bounds"], "dates": dates, "native_resolution": src_meta.get("native_resolution"),
               "source": src_meta.get("source"), "legend": [["#08519c", "Open water"], ["#6baed6", "Partly / seasonally wet"]],
               "notes": "Open water seen by MODIS each month (MNDWI). Misses water under dense vegetation and is blocked by cloud in the rainy season."},
              open(os.path.join(R, "water_base_open", "meta.json"), "w"), indent=1)
    sm = json.load(open(os.path.join(R, "sudd_inundation", "meta.json")))
    dates = []
    for f in sorted(glob.glob(os.path.join(R, "sudd_inundation", "*.png"))):
        b, ok, shape = classify(f)
        d = os.path.basename(f)[:-4]
        write(os.path.join(R, "water_base_floodveg"), d, [(ok & (b == 4), FLOODVEG, 170), (ok & (b == 6), WATER, 230)], shape)
        dates.append(d)
    json.dump({"key": "water_base_floodveg", "label": "Sudd flooded vegetation (NASA MODIS, monthly)", "base_layer": True, "no_recolor": True,
               "units": "", "bounds": sm["bounds"], "dates": dates, "native_resolution": sm.get("native_resolution"), "source": sm.get("source"),
               "legend": [["#00e5ff", "Flooded vegetation (swamp under water, Sudd)"], ["#08519c", "Open water"]],
               "notes": "Sudd counties only. Catches swamp flooding that the open-water layer misses. No MODIS Jul–Nov 2025."},
              open(os.path.join(R, "water_base_floodveg", "meta.json"), "w"), indent=1)
    print("water base layers written")


if __name__ == "__main__":
    main()
