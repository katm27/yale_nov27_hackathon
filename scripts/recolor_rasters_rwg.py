"""Repaint the 7-bin raster overlays (already binned by scripts/recolor_rasters.py) with the app's shared
red -> white -> green palette, and paint no-data as black diagonal hatching.

    bin 1 (lowest / largest decrease) ... bin 4 (middle / little or no change) ... bin 7 (highest / largest increase)
    #b2182b #ef8a62 #fddbc7 #ffffff #d9f0d3 #7fbf7b #1b7837

For the "_trend" layers the bins are symmetric about zero, so the white middle bin is "little or no change".
For value layers the white bin is the middle of the range. The raw grids are not kept in this repo, so the
bin edges stay as they were (7 equal-width bins in data units, listed in each meta.json "bins"); only colours change.
No-data / cloud pixels (light grey from recolor_rasters.py) become black stripes on a translucent black background.

Idempotent (meta "palette": "rwg7"). Usage: python scripts/recolor_rasters_rwg.py key [key ...]
"""
import glob, json, os, sys
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RASTERS = os.path.join(ROOT, "docs", "rasters")
OLD = ["#d73027", "#fc8d59", "#fee08b", "#ffffbf", "#d9ef8b", "#91cf60", "#1a9850"]
NEW = ["#b2182b", "#ef8a62", "#fddbc7", "#ffffff", "#d9f0d3", "#7fbf7b", "#1b7837"]
rgb = lambda h: [int(h[i:i + 2], 16) for i in (1, 3, 5)]
O, N = np.array([rgb(h) for h in OLD], float), np.array([rgb(h) for h in NEW], float)
GREY = np.array([189, 189, 189], float)


def run(key):
    mp = os.path.join(RASTERS, key, "meta.json")
    meta = json.load(open(mp))
    if meta.get("palette") == "rwg7":
        return 0
    n = 0
    for f in sorted(glob.glob(os.path.join(RASTERS, key, "*.png"))):
        a = np.array(Image.open(f).convert("RGBA")).astype(float)
        vis = a[..., 3] > 0
        px = a[..., :3]
        dg = np.abs(px - GREY).sum(-1)
        d = ((px[..., None, :] - O[None, None]) ** 2).sum(-1)       # distance to each old bin colour
        j = d.argmin(-1)
        nodata = vis & (dg < 12) & (d.min(-1) > 300)
        out = a.copy()
        m = vis & ~nodata
        out[m, :3] = N[j[m]]
        if nodata.any():
            yy, xx = np.indices(nodata.shape)
            stripe = ((xx + yy) % 6) < 2
            out[nodata, :3] = 0
            out[nodata, 3] = np.where(stripe[nodata], 235, 110)
        Image.fromarray(out.astype("uint8"), "RGBA").quantize(colors=16, method=Image.Quantize.FASTOCTREE).save(f, optimize=True)
        n += 1
    meta["colors"] = NEW
    meta["colormap"] = "Red-white-green 7 bins (red = lowest / decrease, white = middle / no change, green = highest / increase)"
    meta["nodata_color"] = "black diagonal hatching (no valid data)"
    meta["palette"] = "rwg7"
    json.dump(meta, open(mp, "w"), indent=1)
    return n



def compress(key):
    """Palette-compress already repainted PNGs (only exact colours are present, so this is lossless in practice)."""
    for f in sorted(glob.glob(os.path.join(RASTERS, key, "*.png"))):
        im = Image.open(f)
        if im.mode != "P":
            im.convert("RGBA").quantize(colors=16, method=Image.Quantize.FASTOCTREE).save(f, optimize=True)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--compress"]:
        for k in sys.argv[2:]:
            compress(k)
        sys.exit()
    for k in sys.argv[1:]:
        print(k, run(k))
