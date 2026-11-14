"""Monthly surface water / flood extent for South Sudan counties from MODIS MOD09A1+MYD09A1 v061
(8-day 500 m surface reflectance, Microsoft Planetary Computer), 2018-01..2025-12.

Method (per 500 m pixel, per month):
  * use every 8-day composite (Terra + Aqua) whose start date is in the month
  * cloud mask from sur_refl_state_500m: cloud state clear (00 or 11), no cloud shadow,
    no internal cloud flag, cirrus none/small; reflectances must be valid
  * MNDWI = (B4 green - B7 SWIR2) / (B4 + B7)   (B7 2.1 um used because Aqua B6 is defective)
  * per observation water = MNDWI > 0.1 (threshold chosen by visual checks: MNDWI>0 flags lush
    green wet-season vegetation, MNDWI>0.1 isolates open water + shallow/inundated areas; the
    Zou-style MNDWI>NDVI rule catches only ~1% of it and misses the known 2019/2021 floods)
  * monthly water = water in >= 50% of the month's clear observations
  * pixels with no clear observation inherit the previous month's water state (max 2 months),
    remaining gaps are left unknown and excluded from the percentage.
County outputs:
  surface_water_pct   = water pixels / known pixels x 100
  surface_water_km2   = surface_water_pct x county area (sinusoidal equal-area pixel count) / 100
  surface_water_obs_pct = share of county pixels with a clear observation that month (quality flag)
Overlay docs/rasters/surface_water/YYYY-MM.png = fraction of water pixels per display pixel.

Usage: python scripts/water_pipeline.py [YYYY-MM ...]   (no args = full run)
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import planetary_computer as pc
from rasterio.warp import Resampling

sys.path.insert(0, str(Path(__file__).parent))
import hazards_common as hc

THRESH = 0.1
MAX_CARRY = 2
OUT = hc.PROC / "water_county_monthly.csv"
PART = hc.REPO / "data" / "raw" / "water"
BANDS = ["sur_refl_b04", "sur_refl_b07", "sur_refl_state_500m"]


def read(href):
    err = None
    for attempt in range(5):
        try:
            with rasterio.open(pc.sign(href.split("?")[0])) as src:
                win = hc.window_for_bbox(src)
                return src.read(1, window=win), src.window_transform(win), src.crs
        except Exception as e:  # noqa
            err = e
            time.sleep(3 * (attempt + 1))
    print("FAILED", href.split("?")[0], err, flush=True)
    return None


def tile_of(item_id):
    return item_id.split(".")[2]  # h20v07


def clear_mask(state):
    cs = state & 0b11
    shadow = (state >> 2) & 1
    cirrus = (state >> 8) & 0b11
    internal = (state >> 10) & 1
    return ((cs == 0) | (cs == 3)) & (shadow == 0) & (cirrus <= 1) & (internal == 0) & (state != 65535)


def month_composite(items):
    """returns {tile: (water frequency among clear obs, n_clear, transform, crs)}"""
    by_tile = {}
    for it in items:
        by_tile.setdefault(tile_of(it.id), []).append(it)
    hrefs = [(t, it.id, b, it.assets[b].href) for t, its in by_tile.items() for it in its for b in BANDS]
    with ThreadPoolExecutor(12) as ex:
        res = list(ex.map(lambda h: read(h[3]), hrefs))
    data = {}
    for (t, iid, b, _), r in zip(hrefs, res):
        data[(t, iid, b)] = r
    out = {}
    for t, its in by_tile.items():
        stack, tr, crs = [], None, None
        for it in its:
            rs = [data[(t, it.id, b)] for b in BANDS]
            if any(r is None for r in rs):
                continue
            g, s, st = (r[0] for r in rs)
            tr, crs = rs[0][1], rs[0][2]
            ok = clear_mask(st) & (g > 0) & (g <= 16000) & (s > -100) & (s <= 16000)
            g = g.astype("float32")
            s = np.maximum(s.astype("float32"), 1.0)
            mndwi = (g - s) / (g + s)
            wobs = (mndwi > THRESH).astype("float32")
            wobs[~ok] = np.nan
            stack.append(wobs)
        if not stack:
            continue
        stack = np.stack(stack)
        n = np.sum(~np.isnan(stack), axis=0)
        with np.errstate(all="ignore"):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                med = np.nanmean(stack, axis=0)  # share of clear obs classified water
        out[t] = (med, n, tr, crs)
    return out


def run(month_list):
    ids = hc.county_ids()
    canvas = hc.Canvas()
    PART.mkdir(parents=True, exist_ok=True)
    state = {}  # tile -> (water int8 [-1 unknown,0,1], age int8)
    rows, dates = [], []
    done_months = set()
    part_csv = PART / "part_water.csv"
    if len(month_list) > 3 and part_csv.exists():  # resume support
        prev = pd.read_csv(part_csv)
        rows = list(prev.itertuples(index=False, name=None))
        done_months = set(prev.date.str[:7])
    for m in month_list:
        last_day = pd.Timestamp(m + "-01").days_in_month
        items = hc.search("modis-09A1-061", f"{m}-01/{m}-{last_day:02d}")
        items = [it for it in items if it.properties["start_datetime"][:7] == m]
        t0 = time.time()
        comp = month_composite(items)
        water_n = np.zeros(len(ids) + 1); known_n = np.zeros(len(ids) + 1)
        obs_n = np.zeros(len(ids) + 1); tot_n = np.zeros(len(ids) + 1)
        img = canvas.new()
        for t, (med, n, tr, crs) in comp.items():
            w = np.where(n > 0, (med >= 0.5).astype("int8"), -1).astype("int8")
            if t in state and state[t][0].shape == w.shape:
                pw, age = state[t]
                fill = (w == -1) & (pw >= 0) & (age < MAX_CARRY)
                w[fill] = pw[fill]
                age = np.where(n > 0, 0, np.where(fill, age + 1, MAX_CARRY)).astype("int8")
            else:
                age = np.where(n > 0, 0, MAX_CARRY).astype("int8")
            state[t] = (w, age)
            lab = hc.labels_for(crs, tr, w.shape)
            water_n += hc.bincount(lab, w == 1)
            known_n += hc.bincount(lab, w >= 0)
            obs_n += hc.bincount(lab, n > 0)
            tot_n += hc.bincount(lab)
            canvas.add(img, np.where(w < 0, np.nan, w.astype("float32")), tr, crs, Resampling.average)
        if m in done_months:
            print("skip (done)", m, flush=True)
            continue
        if not comp:
            print("no data", m, flush=True)
            continue
        pix_km2 = abs(tr.a * tr.e) / 1e6
        canvas.save_png(img, hc.RASTERS / "surface_water" / f"{m}.png", 0.0, 1.0, WATER_CMAP, zero_transparent=True, nodata_rgba=(150, 150, 150, 110))
        dates.append(m)
        for i, cid in enumerate(ids, start=1):
            if tot_n[i] == 0:
                continue
            obs_pct = 100 * obs_n[i] / tot_n[i]
            rows.append((cid, m + "-01", "surface_water_obs_pct", round(obs_pct, 2)))
            if known_n[i] < 0.2 * tot_n[i]:  # too little known area -> no estimate
                continue
            pct = 100 * water_n[i] / known_n[i]
            rows.append((cid, m + "-01", "surface_water_pct", round(pct, 4)))
            rows.append((cid, m + "-01", "surface_water_km2", round(pct / 100 * tot_n[i] * pix_km2, 3)))
        print(f"water {m} items={len(items)} SS water km2={water_n[1:].sum()*pix_km2:.0f} "
              f"known={100*known_n[1:].sum()/tot_n[1:].sum():.0f}% obs={100*obs_n[1:].sum()/tot_n[1:].sum():.0f}% {time.time()-t0:.0f}s",
              flush=True)
        if len(month_list) > 3:
            pd.DataFrame(rows, columns=["county_id", "date", "variable", "value"]).to_csv(part_csv, index=False)
    return rows, dates, canvas


def _cmap():
    from matplotlib.colors import LinearSegmentedColormap
    return LinearSegmentedColormap.from_list("water", ["#9ecae1", "#2171b5", "#08306b"])


WATER_CMAP = _cmap()


def finalize(rows, canvas):
    df = pd.DataFrame(rows, columns=["county_id", "date", "variable", "value"]).drop_duplicates(
        ["county_id", "date", "variable"]).sort_values(["variable", "county_id", "date"])
    df.to_csv(OUT, index=False)
    dates = sorted(p.stem for p in (hc.RASTERS / "surface_water").glob("*.png"))
    hc.write_raster_meta("surface_water", "Surface water (monthly, MODIS)", "fraction of pixel classified water",
                         canvas, 0.0, 1.0, "light blue -> dark blue (#9ecae1,#2171b5,#08306b)",
                         "500 m (MOD09A1/MYD09A1), displayed at ~1.3 km", dates,
                         "MODIS MOD09A1/MYD09A1 v061 via Microsoft Planetary Computer; MNDWI(B4,B7)>0.1 in >=50% of clear obs",
                         notes="Transparent = dry land; grey = no clear observation within 2 months (cloud). "
                               "Open water + shallow inundation; dense flooded vegetation (papyrus) is under-detected.")
    src = "MODIS MOD09A1 + MYD09A1 v061 8-day surface reflectance via Microsoft Planetary Computer"
    url = "https://planetarycomputer.microsoft.com/dataset/modis-09A1-061"
    common = dict(category="environment", group="Water & flooding", source=src, source_url=url,
                  native_resolution="500 m", temporal="monthly")
    note = ("Water = MNDWI (B4 green vs B7 SWIR 2.1um) > 0.1 in >=50% of cloud-free 8-day composites in the "
            "month (Terra+Aqua). Captures open water and shallow inundation; some residual false positives from "
            "dark wet vegetation early in the wet season (Jun-Aug). Cloud gaps filled from previous month (max 2 months); county-months with <20% known "
            "area dropped. Detects open water; under-detects flooded/floating vegetation (Sudd) and is reduced by "
            "persistent wet-season cloud. Validation vs 30 UNOSAT VIIRS water-extent tables (HDX, 2022-10..2025-04, "
            "scripts/water_validate_unosat.py): state-level r = 0.76; MODIS totals ~0.5x UNOSAT (close in Jun-Sep, "
            "2-5x lower in the dry season when UNOSAT counts vegetated swamp water). Treat as a conservative, "
            "relative flood signal.")
    hc.write_meta("water", [
        dict(id="surface_water_km2", label="Surface water extent", units="km2",
             aggregation="water share of known pixels x county area", higher_is="worse", index_ok=True,
             raster="surface_water", notes=note, **common),
        dict(id="surface_water_pct", label="Surface water (% of county)", units="% of county area",
             aggregation="water pixels / known (observed or gap-filled) pixels x 100", higher_is="worse",
             index_ok=True, raster="surface_water", notes=note, **common),
        dict(id="surface_water_obs_pct", label="Cloud-free observation coverage (water layer)",
             units="% of county area", aggregation="share of county pixels with >=1 clear 8-day observation",
             higher_is="neutral", index_ok=False, raster=None,
             notes="Data-quality flag for surface_water_*; low in wet season (Jun-Oct).", **common),
    ])
    print("wrote", OUT, len(df))


if __name__ == "__main__":
    args = sys.argv[1:]
    if args:
        rows, dates, canvas = run(args)
        print(pd.DataFrame(rows, columns=["county_id", "date", "variable", "value"]).groupby(
            ["date", "variable"]).value.describe())
    else:
        rows, dates, canvas = run(hc.months())
        finalize(rows, canvas)
