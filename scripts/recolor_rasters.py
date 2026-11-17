"""Recolour every raster overlay to ONE consistent 7-bin red → green scale.

Each overlay PNG was rendered with its own colormap on a fixed scale (vmin..vmax in its meta.json). Because the raw
grids are not kept for every layer, we recover each pixel's position t in [0, 1] on the ORIGINAL colour ramp (nearest
colour on the ramp), split [0, 1] into 7 equal bins and repaint with a shared palette:

    bin 1 (lowest) ... bin 7 (highest) = #d73027 #fc8d59 #fee08b #ffffbf #d9ef8b #91cf60 #1a9850   (ColorBrewer RdYlGn-7)

Red = least, green = most for every variable (for trend layers: red = largest decrease, pale yellow = little change,
green = largest increase). This is a colour convention only, not "bad/good". Bin edges in data units are written to
meta.json ("bins"), honouring log scales. Semi-transparent no-data/cloud pixels become light grey.

Idempotent: layers already recoloured (meta "recolored": true) are skipped. Usage: python scripts/recolor_rasters.py [key ...]
"""
import glob
import json
import os
import re
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import overlay_utils as ou  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RASTERS = os.path.join(ROOT, "docs", "rasters")
PALETTE7 = ["#d73027", "#fc8d59", "#fee08b", "#ffffbf", "#d9ef8b", "#91cf60", "#1a9850"]
P7 = np.array([[int(h[i:i + 2], 16) for i in (1, 3, 5)] for h in PALETTE7], float)
EXTRA = {  # ramps used by the trend script (div_*) and others, if not given in meta "colors"
    "div_brbg": ["#543005", "#8c510a", "#bf812d", "#dfc27d", "#f6e8c3", "#f5f5f5", "#c7eae5", "#80cdc1", "#35978f", "#01665e", "#003c30"],
}


def hex2rgb(h):
    h = h.strip().lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def ramp_for(meta):
    """Return an (N,3) array sampling the original colour ramp from low to high."""
    cols = meta.get("colors")
    if cols and len(cols) >= 3 and all(isinstance(c, str) and c.startswith("#") for c in cols):
        base = np.array([hex2rgb(c) for c in cols], float)
    else:
        name = str(meta.get("colormap", ""))
        hexes = re.findall(r"#[0-9a-fA-F]{6}", name)
        if len(hexes) >= 2:
            base = np.array([hex2rgb(c) for c in hexes], float)
        elif name.lower() in ou.CMAPS:
            base = np.array([hex2rgb(c) for c in ou.CMAPS[name.lower()]], float)
        elif name in EXTRA:
            base = np.array([hex2rgb(c) for c in EXTRA[name]], float)
        else:
            import matplotlib
            names = {n.lower(): n for n in matplotlib.colormaps}
            cm = matplotlib.colormaps[names.get(name.lower(), name)]
            return (np.array([cm(i / 255)[:3] for i in range(256)]) * 255).astype(float)
    xs = np.linspace(0, 1, len(base))
    t = np.linspace(0, 1, 256)
    return np.stack([np.interp(t, xs, base[:, k]) for k in range(3)], 1)


def bin_edges(meta):
    lo, hi = float(meta["vmin"]), float(meta["vmax"])
    sc = str(meta.get("scale", "")).lower()
    k = np.arange(8) / 7
    if "log" in sc:
        if lo > 0:
            return list(np.exp(np.log(lo) + k * (np.log(hi) - np.log(lo))))
        return list(10 ** (lo + k * (hi - lo)))           # values were already log10
    return list(lo + k * (hi - lo))


def recolor_layer(key):
    mpath = os.path.join(RASTERS, key, "meta.json")
    meta = json.load(open(mpath))
    if meta.get("recolored") or meta.get("no_recolor") or meta.get("continuous"):  # continuous ramps stay continuous
        return None
    if "categorical" in str(meta.get("colormap", "")):
        # Sudd classes: dry / flooded vegetation / open water -> bins 1, 5, 7 (least to most water)
        cls_cols = meta.get("colors") or []
        mapping = {tuple(hex2rgb(c)): P7[[0, 4, 6][i]] for i, c in enumerate(cls_cols[:3])}
        ramp = None
    else:
        ramp = ramp_for(meta)
    errs = []
    for f in sorted(glob.glob(os.path.join(RASTERS, key, "*.png"))):
        im = Image.open(f).convert("RGBA")
        a = np.array(im).astype(float)
        rgb, alpha = a[..., :3], a[..., 3]
        vis = alpha > 0
        out = a.copy()
        if ramp is None:
            for src, dst in mapping.items():
                m = vis & (np.abs(rgb - np.array(src)).sum(-1) < 30)
                out[m, :3] = dst
        else:
            cols, inv = np.unique(rgb[vis].reshape(-1, 3), axis=0, return_inverse=True)
            d = ((cols[:, None, :] - ramp[None, :, :]) ** 2).sum(-1)
            j = d.argmin(1)
            errs.append(float(np.sqrt(d.min(1)).mean()))
            t = j / (len(ramp) - 1)
            b = np.minimum(6, (t * 7).astype(int))
            newc = P7[b]
            out[vis, :3] = newc[inv.ravel()]
            faint = vis & (alpha < 150)                       # cloud / no-data veil
            out[faint, :3] = [189, 189, 189]
        Image.fromarray(out.astype("uint8"), "RGBA").quantize(colors=16, method=Image.Quantize.FASTOCTREE).save(f, optimize=True)
    meta["original_colormap"] = meta.get("colormap")
    meta["original_colors"] = meta.get("colors")
    meta["colormap"] = "RdYlGn 7 bins (red = lowest, green = highest)"
    meta["colors"] = PALETTE7
    meta["bins"] = None if ramp is None else [float(f"{x:.4g}") for x in bin_edges(meta)]
    if ramp is None:
        meta["bin_labels"] = ["dry", "flooded vegetation", "open water"]
    meta["recolored"] = True
    json.dump(meta, open(mpath, "w"), indent=1)
    return float(np.mean(errs)) if errs else 0.0


if __name__ == "__main__":
    keys = sys.argv[1:] or sorted(os.path.basename(os.path.dirname(f)) for f in glob.glob(os.path.join(RASTERS, "*", "meta.json")))
    for k in keys:
        e = recolor_layer(k)
        print(f"{k:28s} {'skipped (already recoloured)' if e is None else f'mean colour-match error {e:.1f}'}")
