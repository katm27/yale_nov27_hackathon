"""Monthly flood / surface-water extent per county from Sentinel-1 C-band SAR (radar sees through cloud),
2018-01..2025-12. Source: Microsoft Planetary Computer `sentinel-1-rtc` (Sentinel-1 IW GRD, radiometrically
terrain corrected gamma0 by Catalyst/PCI, 10 m, linear power, VV+VH).

Why SAR: the MODIS MNDWI water layer (water_pipeline.py) loses most wet-season months to cloud and does not see
water under emergent vegetation. C-band SAR sees through cloud and detects open water and *sparse* flooded
vegetation (calm water = specular reflection = very low backscatter). Dense papyrus/Typha swamp in the Sudd gives
double-bounce (HIGH backscatter) and is NOT detected by this low-backscatter rule (documented caveat).

Stage 1 `grids` (heavy, ~2-3 h): for each month, every RTC scene intersecting South Sudan is read at its 1/16
COG overview (160 m; overviews are block averages of the 10 m linear gamma0, so speckle is reduced), edge pixels
are eroded, the scene is converted to dB and reprojected (average) onto a fixed EPSG:4326 0.004 deg (~440 m)
grid. Per pixel and month we keep: mean VV dB, mean VH dB, minimum VV dB, number of acquisitions
-> data/raw/s1_flood/grids/YYYY-MM.npz (uint8 quantised, 0.25 dB steps; raw, not committed).

Stage 2 `finalize`: per pixel-month   water = mean VH dB < -17 (open water: specular, dark)  OR
mean (VV - VH) dB > 8.5 (flooded herbaceous vegetation: double bounce raises VV far more than VH).
A pure low-backscatter rule (VV < -18 dB) finds almost nothing in the Sudd because most flood water there stands
under grass/papyrus and is BRIGHT. Thresholds were calibrated on ONE UNOSAT VIIRS flood map (4-8 Oct 2022,
pixel F1 0.61, area ratio 1.09) and validated on the other UNOSAT dates (scripts/flood_s1_validate.py).
Pixels without any acquisition inherit the previous month (max 2 months). Permanent water = water in >= 10 of 12
months in at least 6 of the 8 years. County outputs (data/processed/flood_s1_county_monthly.csv):
  flood_s1_water_km2      all SAR-detected water (open water + flooded sparse vegetation)
  flood_s1_water_pct      same as % of county
  flood_s1_flood_km2      water outside the permanent-water mask ("flood" = seasonal/abnormal inundation)
  flood_s1_obs_pct        % of county with >=1 Sentinel-1 acquisition in the month (quality flag)
Overlay: docs/rasters/flood_s1/YYYY-MM.png (water fraction per display pixel).
Validation vs UNOSAT state tables: scripts/flood_s1_validate.py.

Usage: python scripts/flood_s1_pipeline.py grids [YYYY-MM ...]  |  python scripts/flood_s1_pipeline.py finalize
"""
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import planetary_computer as pc
from rasterio.transform import from_origin
from rasterio.warp import reproject, Resampling, transform_bounds
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).parent))
import hazards_common as hc

RES = 0.004
OVR = 16
GRID_DIR = hc.REPO / "data" / "raw" / "s1_flood" / "grids"
OUT = hc.PROC / "flood_s1_county_monthly.csv"
VH_T = -17.0    # dB: open water (specular, dark in cross-pol)
RATIO_T = 8.5   # dB: VV-VH, flooded herbaceous vegetation (double bounce brightens VV much more than VH)
MAX_CARRY = 2
KEY = "flood_s1"


def grid():
    b = hc.counties().total_bounds
    w, s, e, n = np.floor(b[0] * 10) / 10 - 0.1, np.floor(b[1] * 10) / 10 - 0.1, np.ceil(b[2] * 10) / 10 + 0.1, np.ceil(b[3] * 10) / 10 + 0.1
    width, height = int(round((e - w) / RES)), int(round((n - s) / RES))
    return from_origin(w, n, RES, RES), (height, width), "EPSG:4326"


def q(db):  # dB -> uint8 (0 = nodata), 0.25 dB steps from -40 dB
    v = np.clip(np.round((db + 40.0) * 4) + 1, 1, 255)
    return np.where(np.isfinite(db), v, 0).astype("uint8")


def dq(u):
    return np.where(u > 0, (u.astype("float32") - 1) / 4.0 - 40.0, np.nan)


def read_scene(item, gtr, gshape, gcrs):
    out = {}
    for pol in ("vv", "vh"):
        if pol not in item.assets:
            return None
        href = item.assets[pol].href
        for attempt in range(4):
            try:
                with rasterio.open(pc.sign(href.split("?")[0])) as src:
                    h, w = src.height // OVR, src.width // OVR
                    a = src.read(1, out_shape=(h, w)).astype("float32")
                    tr = src.transform * src.transform.scale(src.width / w, src.height / h)
                    crs = src.crs
                    bnds = transform_bounds(crs, gcrs, *src.bounds)
                break
            except Exception as e:  # noqa
                err = e
                time.sleep(3 * (attempt + 1))
        else:
            print("FAILED", item.id, pol, err, flush=True)
            return None
        valid = np.isfinite(a) & (a > 0)
        valid = ndimage.binary_erosion(valid, iterations=3)
        db = np.where(valid, 10 * np.log10(np.where(valid, a, 1)), np.nan)
        db[db < -35] = np.nan
        out[pol] = db
    # grid sub-window covering the scene
    c0 = max(0, int((bnds[0] - gtr.c) / RES) - 1); c1 = min(gshape[1], int((bnds[2] - gtr.c) / RES) + 2)
    r0 = max(0, int((gtr.f - bnds[3]) / RES) - 1); r1 = min(gshape[0], int((gtr.f - bnds[1]) / RES) + 2)
    if c1 <= c0 or r1 <= r0:
        return None
    sub_tr = gtr * gtr.translation(c0, r0)
    res = {}
    for pol, db in out.items():
        dst = np.full((r1 - r0, c1 - c0), np.nan, "float32")
        reproject(db, dst, src_transform=tr, src_crs=crs, src_nodata=np.nan, dst_transform=sub_tr, dst_crs=gcrs,
                  dst_nodata=np.nan, resampling=Resampling.average)
        res[pol] = dst
    return (r0, r1, c0, c1), res


def month_grids(m):
    gtr, gshape, gcrs = grid()
    last = pd.Timestamp(m + "-01").days_in_month
    items = hc.search("sentinel-1-rtc", f"{m}-01/{m}-{last:02d}")
    s_vv = np.zeros(gshape, "float32"); s_vh = np.zeros(gshape, "float32")
    n = np.zeros(gshape, "uint8"); mn = np.full(gshape, np.nan, "float32")
    t0 = time.time()
    with ThreadPoolExecutor(8) as ex:
        for r in ex.map(lambda it: read_scene(it, gtr, gshape, gcrs), items):
            if r is None:
                continue
            (r0, r1, c0, c1), d = r
            ok = np.isfinite(d["vv"]) & np.isfinite(d["vh"])
            sl = (slice(r0, r1), slice(c0, c1))
            s_vv[sl][ok] += d["vv"][ok]; s_vh[sl][ok] += d["vh"][ok]; n[sl][ok] += 1
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                mn[sl] = np.where(ok, np.fmin(mn[sl], d["vv"]), mn[sl])
    with np.errstate(all="ignore"):
        mvv = np.where(n > 0, s_vv / n, np.nan); mvh = np.where(n > 0, s_vh / n, np.nan)
    GRID_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(GRID_DIR / f"{m}.npz", vv=q(mvv), vh=q(mvh), vvmin=q(mn), n=n)
    print(f"s1 {m} scenes={len(items)} covered={100*(n>0).mean():.0f}% of bbox {time.time()-t0:.0f}s", flush=True)


def run_grids(months):
    for m in months:
        if (GRID_DIR / f"{m}.npz").exists():
            continue
        month_grids(m)


# ------------------------------------------------------------------------------------------- stage 2
def classify(z):
    vv, vh = dq(z["vv"]), dq(z["vh"])
    wet = (vh < VH_T) | ((vv - vh) > RATIO_T)
    w = np.where(np.isnan(vv) | np.isnan(vh), -1, wet.astype("int8")).astype("int8")
    return w


def water_series():
    """yield (month, water int8 grid -1/0/1 after gap filling, observed bool)"""
    state = None; age = None
    for m in hc.months():
        f = GRID_DIR / f"{m}.npz"
        if not f.exists():
            continue
        z = np.load(f)
        w = classify(z)
        obs = w >= 0
        if state is not None:
            fill = (w == -1) & (state >= 0) & (age < MAX_CARRY)
            w[fill] = state[fill]
            age = np.where(obs, 0, np.where(fill, age + 1, MAX_CARRY)).astype("int8")
        else:
            age = np.where(obs, 0, MAX_CARRY).astype("int8")
        state = w.copy()
        yield m, w, obs


def permanent_mask():
    gtr, gshape, _ = grid()
    yrs = {}
    cnt = {}
    for m, w, obs in water_series():
        y = m[:4]
        yrs.setdefault(y, np.zeros(gshape, "uint8")); cnt.setdefault(y, np.zeros(gshape, "uint8"))
        yrs[y] += (w == 1); cnt[y] += (w >= 0)
    good_years = np.zeros(gshape, "uint8")
    for y in yrs:
        good_years += ((yrs[y] >= 10) | ((cnt[y] >= 6) & (yrs[y] >= cnt[y] - 1) & (yrs[y] > 0))).astype("uint8")
    perm = good_years >= 6
    np.save(GRID_DIR.parent / "permanent_water.npy", perm)
    return perm


def pixel_area_km2(gtr, gshape):
    lat = gtr.f - (np.arange(gshape[0]) + 0.5) * RES
    return (RES * 111.32) ** 2 * np.cos(np.radians(lat))[:, None] * np.ones((1, gshape[1]), "float32")


def finalize():
    from matplotlib.colors import LinearSegmentedColormap
    gtr, gshape, gcrs = grid()
    lab = hc.labels_for(gcrs, gtr, gshape)
    area = pixel_area_km2(gtr, gshape)
    ids = hc.county_ids()
    tot_km2 = hc.bincount(lab, area)
    perm = permanent_mask()
    print("permanent water km2 (SSD):", round(float((area * perm)[lab > 0].sum())))
    canvas = hc.Canvas()
    cmap = LinearSegmentedColormap.from_list("water", ["#9ecae1", "#2171b5", "#08306b"])
    rows, dates = [], []
    for m, w, obs in water_series():
        known = w >= 0
        water = w == 1
        wk = hc.bincount(lab, area * water); kk = hc.bincount(lab, area * known)
        fk = hc.bincount(lab, area * (water & ~perm)); ok_ = hc.bincount(lab, area * obs)
        for i, cid in enumerate(ids, start=1):
            if tot_km2[i] == 0:
                continue
            rows.append((cid, m + "-01", "flood_s1_obs_pct", round(100 * ok_[i] / tot_km2[i], 2)))
            if kk[i] < 0.5 * tot_km2[i]:
                continue
            pct = 100 * wk[i] / kk[i]
            rows.append((cid, m + "-01", "flood_s1_water_pct", round(pct, 4)))
            rows.append((cid, m + "-01", "flood_s1_water_km2", round(pct / 100 * tot_km2[i], 3)))
            rows.append((cid, m + "-01", "flood_s1_flood_km2", round(fk[i] / kk[i] * tot_km2[i], 3)))
        img = canvas.new()
        canvas.add(img, np.where(known, water.astype("float32"), np.nan), gtr, gcrs, Resampling.average)
        canvas.save_png(img, hc.RASTERS / KEY / f"{m}.png", 0.0, 1.0, cmap, zero_transparent=True,
                        nodata_rgba=(150, 150, 150, 110))
        dates.append(m)
        print(m, "SSD water km2", round(float(wk[1:].sum())), "flood km2", round(float(fk[1:].sum())), flush=True)
    df = pd.DataFrame(rows, columns=["county_id", "date", "variable", "value"]).sort_values(["variable", "county_id", "date"])
    df.to_csv(OUT, index=False)
    hc.write_raster_meta(KEY, "Flood / surface water (monthly, Sentinel-1 SAR)", "fraction of pixel classified water",
                         canvas, 0.0, 1.0, "light blue -> dark blue (#9ecae1,#2171b5,#08306b)",
                         "10 m Sentinel-1 RTC read at 160 m, classified on a 0.004 deg (~440 m) grid", dates,
                         "Copernicus Sentinel-1 IW GRD RTC (sentinel-1-rtc) via Microsoft Planetary Computer",
                         notes=f"Water = monthly mean VH < {VH_T} dB (open water) or VV-VH > {RATIO_T} dB (flooded vegetation). "
                               "Sees through cloud. Transparent = dry land; grey = no acquisition within 2 months.")
    src = "Copernicus Sentinel-1 A/B IW GRD, radiometrically terrain-corrected (sentinel-1-rtc) via Microsoft Planetary Computer"
    url = "https://planetarycomputer.microsoft.com/dataset/sentinel-1-rtc"
    note = (f"Radar (C-band SAR) water = monthly mean gamma0 VH < {VH_T} dB (open water) OR VV-VH > {RATIO_T} dB "
            "(flooded herbaceous vegetation, double bounce) on a ~440 m grid (scenes read at 160 m, block-averaged). "
            "Sees through cloud (unlike MODIS) and sees water under grass/papyrus, which is most of the Sudd flood. "
            "Possible false water: wind-roughened lakes are missed, built-up areas and some woody wetlands can pass "
            "the ratio rule. Revisit 6-12 days 2018-2021, ~12-24 days "
            "after Sentinel-1B failed (Dec 2021) until Sentinel-1C (2025); pixels without an acquisition inherit "
            "the previous month (max 2). County-months with <50% known area are dropped. Validation vs UNOSAT: see "
            "docs/CLIMATE_DATA_DECISIONS.md and scripts/flood_s1_validate.py.")
    common = dict(category="environment", group="Water & flooding", source=src, source_url=url,
                  native_resolution="10 m (classified at ~440 m)", temporal="monthly", raster=KEY)
    hc.write_meta(KEY, [
        dict(id="flood_s1_water_km2", label="Surface water incl. flooded land (Sentinel-1 radar)", units="km2",
             aggregation="water share of known area x county area", higher_is="worse", index_ok=True, notes=note, **common),
        dict(id="flood_s1_water_pct", label="Surface water (% of county, Sentinel-1 radar)", units="% of county area",
             aggregation="water area / known area x 100", higher_is="worse", index_ok=True, notes=note, **common),
        dict(id="flood_s1_flood_km2", label="Flooded area beyond permanent water (Sentinel-1 radar)", units="km2",
             aggregation="water outside the 2018-2025 permanent-water mask, scaled to county area", higher_is="worse",
             index_ok=False, notes=note + " Permanent water = water in >=10 of 12 months in >=6 of 8 years. "
             "index_ok false because many counties have ~0 flood in 2018 months.", **common),
        dict(id="flood_s1_obs_pct", label="Sentinel-1 coverage in month (quality flag)", units="% of county area",
             aggregation="share of county area with >=1 acquisition in the month", higher_is="neutral",
             index_ok=False, notes="Quality flag for flood_s1_*; drops after Sentinel-1B failure (Dec 2021).",
             **{**common, "raster": None}),
    ])
    print("wrote", OUT, len(df))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "grids":
        run_grids(sys.argv[2:] or hc.months())
    else:
        if cmd == "all":
            run_grids(hc.months())
        finalize()
        from trend_stats import write_trends
        write_trends(KEY)  # Mann-Kendall + Sen's slope (scripts/trend_stats.py)
