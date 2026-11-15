"""MODIS water / inundation index for the Sudd wetland (South Sudan), 8-day and monthly, 2018-01..2025-12.

Mirrors the team's Inner Niger Delta product (MOD09A1 green + SWIR band 6 -> MNDWI, QA cloud screening, 8-day,
annual peak Sep-Dec and low Mar-May) and adds a flooded-vegetation rule, because the Sudd is mostly papyrus /
Typha / grass swamp that MNDWI alone misses.

AOI ("Sudd counties"): the 16 counties of data/counties.geojson that overlap the wetland (SUDD_COUNTIES below),
103 478 km2. No official Sudd / Ramsar (site 1622) boundary polygon is openly published (the Ramsar RSIS
geoserver only holds a centroid for site 1622; WDPA needs an account), so no core-wetland total is computed
from an official outline; an internal "frequently inundated zone" is reported instead (see VALIDATION doc).

Input: Terra MOD09A1 v061 8-day 500 m surface reflectance (Microsoft Planetary Computer STAC `modis-09A1-061`,
tiles h20v08 + h21v08), read as windows straight from the cloud COGs (nothing is downloaded to disk).
Aqua (MYD09A1) is NOT used: its band 6 is ~55 % fill in this AOI (dead detectors). Where a Terra tile-composite is
missing on Planetary Computer (2022 day 265/273/281/289/297, 2023 day 001 and 305; 12 tile-composites),
the MCD43A4 v061 NBAR of the composite's mid-date is substituted (only full-inversion pixels, BRDF quality 0, count as observed). On a test date with both
(2021-11-01, h20v08+h21v08) NBAR agreed with MOD09A1 on 99.8 % of pixels for open water and 92 % for inundation,
but gave ~27 % less inundated area, so 2022 Sep-Dec values are conservative. Planetary Computer holds NO MODIS
reflectance for 2022 day 337 and 345 (3-18 Dec 2022, gap-filled) nor at all for 2025 day 185-321 (4 Jul - 24 Nov 2025): those composites are reported as missing and
the months 2025-07..2025-11 are not written.

Per pixel and 8-day composite:
  clear   = sur_refl_state_500m cloud state clear (00) or assumed clear (11), no cloud shadow, no internal cloud
            flag, cirrus none/small, all used reflectances valid, and blue (b3) < 0.20 (residual cloud / haze screen
            of Xiao et al. 2005, Sakamoto et al. 2007). The "adjacent to cloud" bit was tested and does not inflate
            inundation, so it is not used.
  MNDWI   = (b4 green - b6 SWIR1 1.64um) / (b4 + b6)                               (Xu 2006)
  EVI     = 2.5 (b2 - b1) / (b2 + 6 b1 - 7.5 b3 + 1)                              (Huete et al. 2002)
  LSWI    = (b2 NIR - b6 SWIR1) / (b2 + b6)                                       (Xiao et al. 2002)
  OPEN WATER = MNDWI > 0. A per-scene Otsu threshold was tested and rejected: water is < 2 % of the AOI, the
            MNDWI histogram is unimodal and Otsu returns -0.39..-0.43, i.e. it splits the land mode and would flag
            ~90 % of the AOI. 0 is the physical green = SWIR crossover used by Xu (2006) and the Delta product.
  INUNDATED = open water OR (EVI - LSWI <= 0.05)  - the MODIS flooding signal of Xiao et al. (2005, 2006) and
            Sakamoto et al. (2007): standing water raises SWIR absorption so LSWI approaches or exceeds EVI.
            Sub-classes kept for diagnostics: EVI <= 0.3 = "mixed water/vegetation" (Sakamoto's flood class),
            EVI > 0.3 = "flooded dense vegetation" (papyrus/Typha). Sakamoto's EVI <= 0.3 cap is NOT applied to
            the total: in the Sudd it removes 40-60 % of the wet-season inundation that is visibly flooded swamp
            (e.g. 20 Oct 2020: 20 500 km2 -> 12 000 km2).
Class codes in the cache: 0 dry, 1 mixed, 3 dense flooded veg, 2 open water, 255 not clear, 254 no source.

Gap filling (in time order, per pixel): a non-clear pixel takes its most recent clear class if that is <= 3
composites (24 days) old ("carried"); otherwise the probability-weighted climatological state of the same
composite-of-year (share of clear 2018-2025 observations that were open water / inundated, pooled over the
composite and its two neighbours, widened to +-3 if no clear observation; "climatology"). Areas are summed as
hard classes for observed + carried pixels and as probabilities for climatology pixels.

Monthly value = mean of the 8-day values overlapping the month, weighted by the number of days of each composite
inside the month; a county-month is written only if >= 14 days of the month (about two composites) are covered by
composites that exist on Planetary Computer (drops 2025-07..2025-11).

Outputs
  data/processed/sudd_water_county_monthly.csv (+ meta/sudd_water.json): sudd_openwater_km2, sudd_inundation_km2,
      sudd_inundation_pct, sudd_clear_pct, sudd_climfill_pct for the 16 counties
  data/processed/sudd_water_8day.csv   AOI totals per composite (+ observed / carried / climatology shares)
  data/processed/sudd_water_annual.csv annual peak (Sep-Dec) and low (Mar-May), AOI + per county
  data/raw/sudd_water/sudd_water_county_8day.csv  per-county 8-day series
  data/raw/sudd_water/sudd_inundation_frequency_2018_2025.tif  share of clear obs inundated / open water (%)
  docs/rasters/sudd_inundation/YYYY-MM.png + meta.json  monthly class map (open water / flooded veg / dry)
Cache (gitignored): data/raw/sudd_water/_cache/ (STAC item list + one compressed class grid per composite,
  ~0.1 MB each); `--clean-cache` deletes it after a successful run.

Usage: python scripts/sudd_water_index.py [--workers 12] [--pass1-only] [--refresh-items] [--clean-cache]
Re-runnable / resumable: composites already in the cache are skipped. Logs progress with flush (nohup-friendly).
"""
import argparse
import datetime as dt
import json
import shutil
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import planetary_computer as pc
from affine import Affine
from rasterio import features
from rasterio.transform import from_bounds
from rasterio.warp import reproject, Resampling, transform_bounds
from rasterio.windows import Window

sys.path.insert(0, str(Path(__file__).parent))
import hazards_common as hc

SUDD_COUNTIES = ["Panyijiar", "Mayendit", "Leer", "Guit", "Fangak", "Ayod", "Canal/Pigi", "Duk", "Twic East",
                 "Bor South", "Yirol East", "Awerial", "Rubkona", "Koch", "Nyirol", "Uror"]
# MODIS sinusoidal grid (500 m)
PIX = 463.31271652791656
X0, Y0, TILE = -20015109.354, 10007554.677, 2400
SIN = "+proj=sinu +lon_0=0 +x_0=0 +y_0=0 +R=6371007.181 +units=m +no_defs"
PIX_KM2 = PIX * PIX / 1e6
TILES = ["h20v08", "h21v08"]

MNDWI_T, DVEL_T, EVI_DENSE, BLUE_CLOUD, MAX_CARRY = 0.0, 0.05, 0.3, 0.2, 3
DRY, MIXED, OW, DENSE, CLOUD, NOSRC = 0, 1, 2, 3, 255, 254
YEARS = list(range(2018, 2026))
MIN_MONTH_DAYS = 14  # a month needs >= 14 days (~two 8-day composites) of available composites
CLIM_HALF = 1  # climatology pooled over composite-of-year k-1..k+1

RAW = hc.REPO / "data" / "raw" / "sudd_water"
CACHE = RAW / "_cache"
CLS = CACHE / "cls"
ITEMS_JSON = CACHE / "items.json"
OUT_MONTHLY = hc.PROC / "sudd_water_county_monthly.csv"
OUT_8DAY = hc.PROC / "sudd_water_8day.csv"
OUT_ANNUAL = hc.PROC / "sudd_water_annual.csv"
COUNTY_8DAY = RAW / "sudd_water_county_8day.csv"
FREQ_TIF = RAW / "sudd_inundation_frequency_2018_2025.tif"
RKEY = "sudd_inundation"
MOD_BANDS = {"red": "sur_refl_b01", "nir": "sur_refl_b02", "blue": "sur_refl_b03", "green": "sur_refl_b04",
             "swir": "sur_refl_b06", "state": "sur_refl_state_500m"}
NBAR_BANDS = {"red": "Nadir_Reflectance_Band1", "nir": "Nadir_Reflectance_Band2", "blue": "Nadir_Reflectance_Band3",
              "green": "Nadir_Reflectance_Band4", "swir": "Nadir_Reflectance_Band6",
              "q1": "BRDF_Albedo_Band_Mandatory_Quality_Band1", "q2": "BRDF_Albedo_Band_Mandatory_Quality_Band2",
              "q3": "BRDF_Albedo_Band_Mandatory_Quality_Band3", "q4": "BRDF_Albedo_Band_Mandatory_Quality_Band4",
              "q6": "BRDF_Albedo_Band_Mandatory_Quality_Band6"}
CLASS_COLORS = {DRY: (232, 220, 192, 90), MIXED: (65, 171, 93, 225), DENSE: (65, 171, 93, 225), OW: (8, 81, 156, 235)}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# --------------------------------------------------------------------------- AOI grid
_grid = None


def grid():
    """AOI grid aligned to the MODIS sinusoidal grid, with county labels 1..16 (0 = outside AOI)."""
    global _grid
    if _grid is None:
        g = hc.counties()
        a = g[g["name"].isin(SUDD_COUNTIES)].reset_index(drop=True)
        assert len(a) == len(SUDD_COUNTIES), "Sudd county names not found in counties.geojson"
        s = a.to_crs(SIN)
        l, b, r, t = s.total_bounds
        c0 = int(np.floor((l - X0) / PIX)) - 2; c1 = int(np.ceil((r - X0) / PIX)) + 2
        r0 = int(np.floor((Y0 - t) / PIX)) - 2; r1 = int(np.ceil((Y0 - b) / PIX)) + 2
        tr = Affine(PIX, 0, X0 + c0 * PIX, 0, -PIX, Y0 - r0 * PIX)
        shape = (r1 - r0, c1 - c0)
        lab = features.rasterize(zip(s.geometry, range(1, len(s) + 1)), out_shape=shape, transform=tr, fill=0,
                                 dtype="int32")
        _grid = dict(c0=c0, r0=r0, shape=shape, transform=tr, labels=lab, aoi=lab > 0, counties=a,
                     n=len(a) + 1, area_km2=np.bincount(lab.ravel(), minlength=len(a) + 1) * PIX_KM2)
    return _grid


def tile_window(tile):
    G = grid()
    h, v = int(tile[1:3]), int(tile[4:6])
    tc0, tr0 = h * TILE, v * TILE
    gc0, gr0 = G["c0"], G["r0"]
    gc1, gr1 = gc0 + G["shape"][1], gr0 + G["shape"][0]
    cc0, cc1 = max(gc0, tc0), min(gc1, tc0 + TILE)
    rr0, rr1 = max(gr0, tr0), min(gr1, tr0 + TILE)
    if cc1 <= cc0 or rr1 <= rr0:
        return None, None
    return Window(cc0 - tc0, rr0 - tr0, cc1 - cc0, rr1 - rr0), (rr0 - gr0, rr1 - gr0, cc0 - gc0, cc1 - gc0)


# --------------------------------------------------------------------------- calendar + STAC items
def calendar():
    """All 8-day composites: 4 warm-up composites of Dec 2017 + 46 per year 2018-2025."""
    out = []
    for y in [2017] + YEARS:
        ndays = 366 if pd.Timestamp(f"{y}-12-31").dayofyear == 366 else 365
        for doy in range(1, 362, 8):
            if y == 2017 and doy < 337:
                continue
            start = pd.Timestamp(dt.date(y, 1, 1) + dt.timedelta(days=doy - 1))
            out.append(dict(adate=f"A{y}{doy:03d}", year=y, doy=doy, k=(doy - 1) // 8, start=start,
                            ndays=min(8, ndays - doy + 1), warmup=(y == 2017)))
    return out


def list_items(refresh=False):
    if ITEMS_JSON.exists() and not refresh:
        return json.loads(ITEMS_JSON.read_text())
    G = grid()
    bbox = list(G["counties"].total_bounds)
    items = {}
    for y in [2017] + YEARS:
        dr = f"{y}-12-01/{y}-12-31" if y == 2017 else f"{y}-01-01/{y}-12-31"
        for it in sorted(hc.search("modis-09A1-061", dr, bbox=bbox), key=lambda i: i.id):
            p = it.id.split(".")
            if p[0] != "MOD09A1" or p[2] not in TILES:
                continue
            # duplicates (reprocessed granules) -> sorted by id, the latest production time wins
            items.setdefault(p[1], {})[p[2]] = {"src": "MOD", "id": it.id,
                                                 "hrefs": {k: it.assets[b].href.split("?")[0] for k, b in MOD_BANDS.items()}}
        log("items", y, sum(1 for a in items if a[1:5] == str(y)))
    # Terra tile missing -> MCD43A4 NBAR of the composite's mid-date
    for c in calendar():
        have = items.get(c["adate"], {})
        missing = [t for t in TILES if t not in have]
        if not missing or len(have) == 0 and c["year"] == 2025:
            continue  # whole composite missing (2025 gap) -> nothing to substitute either (checked: none on PC)
        mid = c["start"] + pd.Timedelta(days=min(4, c["ndays"] - 1))
        found = hc.search("modis-43A4-061", mid.strftime("%Y-%m-%d") + "/" + mid.strftime("%Y-%m-%d"), bbox=bbox)
        for it in sorted(found, key=lambda i: i.id):
            p = it.id.split(".")
            if p[2] in missing and p[1] == "A" + mid.strftime("%Y%j"):
                items.setdefault(c["adate"], {})[p[2]] = {
                    "src": "NBAR", "id": it.id, "hrefs": {k: it.assets[b].href.split("?")[0] for k, b in NBAR_BANDS.items()}}
        log("NBAR substitute", c["adate"], missing, "->", [items.get(c["adate"], {}).get(t, {}).get("id") for t in missing])
    CACHE.mkdir(parents=True, exist_ok=True)
    ITEMS_JSON.write_text(json.dumps(items))
    return items


# --------------------------------------------------------------------------- pass 1: classify composites
def _read(href, win):
    err = None
    for attempt in range(6):
        try:
            with rasterio.open(pc.sign(href)) as src:
                return src.read(1, window=win)
        except Exception as e:  # noqa
            err = e
            time.sleep(3 * (attempt + 1))
    log("FAILED", href, err)
    return None


def clear_mask(state):
    cs = state & 0b11
    shadow = (state >> 2) & 1
    cirrus = (state >> 8) & 0b11
    internal = (state >> 10) & 1
    return ((cs == 0) | (cs == 3)) & (shadow == 0) & (cirrus <= 1) & (internal == 0) & (state != 65535)


def classify(bands, src):
    """bands: dict of int arrays -> uint8 class grid for one tile window."""
    f = {k: bands[k].astype("float32") * 1e-4 for k in ("red", "nir", "blue", "green", "swir")}
    if src == "MOD":
        valid = clear_mask(bands["state"].astype("uint16"))
        for k in ("red", "nir", "blue", "green", "swir"):
            valid &= (bands[k] > -100) & (bands[k] <= 16000)
    else:  # NBAR: full BRDF inversion only, fill = 32767
        valid = np.ones(bands["red"].shape, bool)
        for k in ("red", "nir", "blue", "green", "swir"):
            valid &= (bands[k] >= 0) & (bands[k] < 32767)
        for q in ("q1", "q2", "q3", "q4", "q6"):
            valid &= bands[q] == 0
    valid &= f["blue"] < BLUE_CLOUD
    with np.errstate(all="ignore"):
        mndwi = (f["green"] - f["swir"]) / (f["green"] + f["swir"])
        lswi = (f["nir"] - f["swir"]) / (f["nir"] + f["swir"])
        evi = 2.5 * (f["nir"] - f["red"]) / (f["nir"] + 6 * f["red"] - 7.5 * f["blue"] + 1)
    valid &= np.isfinite(mndwi) & np.isfinite(lswi) & np.isfinite(evi)
    cls = np.full(mndwi.shape, CLOUD, "uint8")
    flood = (evi - lswi) <= DVEL_T
    cls[valid] = DRY
    cls[valid & flood & (evi <= EVI_DENSE)] = MIXED
    cls[valid & flood & (evi > EVI_DENSE)] = DENSE
    cls[valid & (mndwi > MNDWI_T)] = OW
    return cls


def process_composite(adate, tiles, ex):
    G = grid()
    cls = np.full(G["shape"], NOSRC, "uint8")
    src = np.zeros(G["shape"], "uint8")  # 0 none, 1 MOD, 2 NBAR
    jobs = []
    for tile, rec in tiles.items():
        win, sl = tile_window(tile)
        if win is None:
            continue
        for k, href in rec["hrefs"].items():
            jobs.append((tile, k, href, win))
    res = list(ex.map(lambda j: _read(j[2], j[3]), jobs))
    data = {}
    for (tile, k, _, _), r in zip(jobs, res):
        data.setdefault(tile, {})[k] = r
    for tile, rec in tiles.items():
        win, (a0, a1, b0, b1) = tile_window(tile)
        d = data.get(tile, {})
        if not d or any(v is None for v in d.values()):
            log("  tile read failed -> treated as missing", adate, tile)
            continue
        cls[a0:a1, b0:b1] = classify(d, rec["src"])
        src[a0:a1, b0:b1] = 1 if rec["src"] == "MOD" else 2
    return cls, src


def pass1(items, workers=12):
    CLS.mkdir(parents=True, exist_ok=True)
    G = grid()
    todo = [c for c in calendar() if c["adate"] in items and not (CLS / f"{c['adate']}.npz").exists()]
    log(f"pass1: {len(todo)} composites to classify ({len(items)} with data on PC)")
    with ThreadPoolExecutor(workers) as ex:
        for i, c in enumerate(todo):
            t0 = time.time()
            cls, src = process_composite(c["adate"], items[c["adate"]], ex)
            tmp = CLS / f"{c['adate']}.tmp.npz"
            np.savez_compressed(tmp, cls=cls, src=src)
            tmp.rename(CLS / f"{c['adate']}.npz")
            aoi = G["aoi"]
            clr = (cls[aoi] < 4).mean()
            log(f"  {c['adate']} {c['start'].date()} clear={clr:.2f} srcs={[v['src'] for v in items[c['adate']].values()]} "
                f"inund_obs_km2={((cls[aoi] < 4) & (cls[aoi] > 0)).sum() * PIX_KM2:.0f} {time.time() - t0:.1f}s [{i + 1}/{len(todo)}]")
    for p in CLS.glob("*.tmp.npz"):
        p.unlink()


def load_cls(adate):
    p = CLS / f"{adate}.npz"
    if not p.exists():
        return None, None
    z = np.load(p)
    return z["cls"], z["src"]


# --------------------------------------------------------------------------- pass 2: climatology, gap fill, aggregate
def climatology(cal):
    G = grid()
    H, W = G["shape"]
    n_clear = np.zeros((46, H, W), "uint8"); n_ow = np.zeros((46, H, W), "uint8"); n_in = np.zeros((46, H, W), "uint8")
    for c in cal:
        if c["warmup"]:
            continue
        cls, _ = load_cls(c["adate"])
        if cls is None:
            continue
        o = cls < 4
        n_clear[c["k"]] += o
        n_ow[c["k"]] += o & (cls == OW)
        n_in[c["k"]] += o & (cls != DRY)
    # frequency raster (all composites)
    tot = n_clear.sum(0, dtype="int32"); tin = n_in.sum(0, dtype="int32"); tow = n_ow.sum(0, dtype="int32")
    with np.errstate(all="ignore"):
        freq_in = np.where(tot > 0, 100.0 * tin / tot, np.nan)
        freq_ow = np.where(tot > 0, 100.0 * tow / tot, np.nan)
    p_ow = np.zeros((46, H, W), "float32"); p_in = np.zeros((46, H, W), "float32")
    allp_ow = np.where(tot > 0, tow / np.maximum(tot, 1), 0).astype("float32")
    allp_in = np.where(tot > 0, tin / np.maximum(tot, 1), 0).astype("float32")
    for k in range(46):
        done = np.zeros((H, W), bool)
        for half in (CLIM_HALF, 3):
            ks = [(k + d) % 46 for d in range(-half, half + 1)]
            den = n_clear[ks].sum(0, dtype="int32")
            ok = (den > 0) & ~done
            p_ow[k][ok] = (n_ow[ks].sum(0, dtype="int32")[ok] / den[ok])
            p_in[k][ok] = (n_in[ks].sum(0, dtype="int32")[ok] / den[ok])
            done |= ok
        p_ow[k][~done] = allp_ow[~done]; p_in[k][~done] = allp_in[~done]
    return p_ow, p_in, freq_in, freq_ow, tot


def month_overlaps(start, ndays):
    """{YYYY-MM: days of the composite inside that month}"""
    out = {}
    for d in pd.date_range(start, periods=ndays, freq="D"):
        out[d.strftime("%Y-%m")] = out.get(d.strftime("%Y-%m"), 0) + 1
    return out


def pass2(cal):
    G = grid()
    lab, aoi, n = G["labels"], G["aoi"], G["n"]
    log("pass2: climatology")
    p_ow, p_in, freq_in, freq_ow, n_obs = climatology(cal)
    write_freq_tif(freq_in, freq_ow, n_obs)
    last_cls = np.full(G["shape"], CLOUD, "uint8")
    last_i = np.full(G["shape"], -999, "int32")
    rows = []
    macc = {}  # month -> [wsum, acc_ow, acc_in]
    canvas = AoiCanvas()
    RDIR = hc.RASTERS / RKEY
    RDIR.mkdir(parents=True, exist_ok=True)
    png_dates = []

    def flush(m):
        wsum, aow, ain = macc.pop(m)
        if wsum < MIN_MONTH_DAYS:
            return
        fow, fin = aow / wsum, ain / wsum
        cl = np.full(G["shape"], DRY, "uint8")  # whole grid; the canvas mask clips to the AOI
        cl[fin >= 0.5] = MIXED
        cl[fow >= 0.5] = OW
        canvas.save(cl, RDIR / f"{m}.png")
        png_dates.append(m)

    for i, c in enumerate(cal):
        cls, src = load_cls(c["adate"])
        if cls is None:
            # no granule at all on PC (2025 gap): time passes, nothing observed
            continue
        obs = cls < 4
        carry = ~obs & (last_cls < 4) & ((i - last_i) <= MAX_CARRY)
        clim = ~obs & ~carry
        ow = np.where(obs | carry, (np.where(obs, cls, last_cls) == OW), 0).astype("float32")
        inn = np.where(obs | carry, (np.where(obs, cls, last_cls) != DRY), 0).astype("float32")
        ow[clim] = p_ow[c["k"]][clim]
        inn[clim] = p_in[c["k"]][clim]
        dense = (obs | carry) & (np.where(obs, cls, last_cls) == DENSE)
        last_cls[obs] = cls[obs]
        last_i[obs] = i
        if c["warmup"]:
            continue
        b = lambda v: hc.bincount(lab, v, n)
        s_ow, s_in, s_dense = b(ow), b(inn), b(dense)
        s_obs, s_car, s_clim, s_nbar = b(obs), b(carry), b(clim), b(src == 2)
        s_tot = hc.bincount(lab, None, n)
        for j in range(1, n):
            cc = G["counties"].iloc[j - 1]
            rows.append(dict(county_id=cc.district_id, name=cc["name"], adate=c["adate"],
                             composite_start=c["start"].strftime("%Y-%m-%d"), ndays=c["ndays"],
                             openwater_km2=s_ow[j] * PIX_KM2, inundation_km2=s_in[j] * PIX_KM2,
                             dense_floodedveg_km2=s_dense[j] * PIX_KM2,
                             observed_share=s_obs[j] / s_tot[j], carried_share=s_car[j] / s_tot[j],
                             climatology_share=s_clim[j] / s_tot[j], nbar_share=s_nbar[j] / s_tot[j],
                             county_km2=s_tot[j] * PIX_KM2))
        for m, w in month_overlaps(c["start"], c["ndays"]).items():
            acc = macc.setdefault(m, [0.0, np.zeros(G["shape"], "float32"), np.zeros(G["shape"], "float32")])
            acc[0] += w; acc[1] += w * ow; acc[2] += w * inn
        for m in [m for m in macc if pd.Timestamp(m + "-01") + pd.offsets.MonthEnd(0) < c["start"]]:
            flush(m)
        if i % 46 == 0:
            log("  pass2 at", c["adate"])
    for m in sorted(macc):
        flush(m)
    write_raster_meta(canvas, sorted(png_dates))
    df = pd.DataFrame(rows)
    df.to_csv(COUNTY_8DAY, index=False, float_format="%.4f")
    return df


# --------------------------------------------------------------------------- rasters
class AoiCanvas:
    """EPSG:3857 canvas over the Sudd AOI, ~1000 px on the long side, transparent outside the 16 counties."""

    def __init__(self, max_px=1000):
        G = grid()
        b = G["counties"].total_bounds
        pad = 0.02
        self.ll = (b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad)
        l, bt, r, t = transform_bounds("EPSG:4326", "EPSG:3857", *self.ll)
        w, h = r - l, t - bt
        if w >= h:
            self.width, self.height = max_px, int(round(max_px * h / w))
        else:
            self.height, self.width = max_px, int(round(max_px * w / h))
        self.transform = from_bounds(l, bt, r, t, self.width, self.height)
        self.shape = (self.height, self.width)
        g = G["counties"].to_crs("EPSG:3857")
        self.mask = features.rasterize(((geom, 1) for geom in g.geometry), out_shape=self.shape,
                                       transform=self.transform, fill=0, dtype="uint8").astype(bool)
        self.bounds_latlon = [[self.ll[1], self.ll[0]], [self.ll[3], self.ll[2]]]

    def save(self, cl, path):
        from PIL import Image
        G = grid()
        out = np.full(self.shape, 255, "uint8")
        reproject(cl, out, src_transform=G["transform"], src_crs=SIN, src_nodata=255, dst_transform=self.transform,
                  dst_crs="EPSG:3857", dst_nodata=255, resampling=Resampling.nearest)
        rgba = np.zeros(self.shape + (4,), "uint8")
        for k, col in CLASS_COLORS.items():
            rgba[out == k] = col
        rgba[~self.mask | (out == 255)] = (0, 0, 0, 0)
        img = Image.fromarray(rgba, "RGBA").quantize(colors=8, method=Image.Quantize.FASTOCTREE)
        img.save(path, optimize=True)


def write_raster_meta(canvas, dates):
    meta = {"key": RKEY, "label": "Sudd inundation (MODIS, monthly)", "units": "class",
            "bounds": canvas.bounds_latlon, "vmin": 0, "vmax": 2,
            "colormap": "categorical: dry / flooded vegetation / open water",
            "colors": ["#e8dcc0", "#41ab5d", "#08519c"],
            "classes": [{"value": 0, "label": "dry (not inundated)", "color": "#e8dcc0"},
                        {"value": 1, "label": "flooded vegetation / mixed water (EVI-LSWI<=0.05)", "color": "#41ab5d"},
                        {"value": 2, "label": "open water (MNDWI>0)", "color": "#08519c"}],
            "native_resolution": "500 m (MOD09A1), displayed at ~400 m", "dates": dates,
            "source": "MODIS MOD09A1 v061 (Terra) 8-day via Microsoft Planetary Computer; MCD43A4 NBAR for 12 missing "
                      "Terra tile-composites (Sep-Oct 2022, Jan and Nov 2023)",
            "crs": "EPSG:3857",
            "notes": "Sudd AOI only (16 counties); transparent outside. A pixel's class is the day-weighted majority "
                     "over the month's 8-day composites after gap filling (cloudy pixels: last clear state <=24 days, "
                     "else same-composite 2018-2025 climatology). 2025-07..2025-11 missing: no MODIS on Planetary "
                     "Computer for 4 Jul-24 Nov 2025."}
    (hc.RASTERS / RKEY / "meta.json").write_text(json.dumps(meta, indent=1))


def write_freq_tif(freq_in, freq_ow, n_obs):
    G = grid()
    RAW.mkdir(parents=True, exist_ok=True)
    arr = np.stack([np.where(np.isnan(freq_in) | ~G["aoi"], 255, np.round(freq_in)),
                    np.where(np.isnan(freq_ow) | ~G["aoi"], 255, np.round(freq_ow))]).astype("uint8")
    prof = dict(driver="GTiff", dtype="uint8", count=2, width=G["shape"][1], height=G["shape"][0], crs=SIN,
                transform=G["transform"], nodata=255, compress="deflate")
    with rasterio.open(FREQ_TIF, "w", **prof) as dst:
        dst.write(arr)
        dst.set_band_description(1, "inundation frequency % of clear 8-day obs 2018-2025")
        dst.set_band_description(2, "open water frequency % of clear 8-day obs 2018-2025")


# --------------------------------------------------------------------------- tables
def write_tables(c8, cal):
    G = grid()
    have = {c["adate"] for c in cal if (CLS / f"{c['adate']}.npz").exists()}
    # ---- 8-day AOI totals
    w = c8.county_km2
    aoi = c8.groupby(["adate", "composite_start", "ndays"]).apply(lambda d: pd.Series({
        "openwater_km2": d.openwater_km2.sum(), "inundation_km2": d.inundation_km2.sum(),
        "flooded_veg_km2": d.inundation_km2.sum() - d.openwater_km2.sum(),
        "dense_floodedveg_observed_km2": d.dense_floodedveg_km2.sum(),
        "observed_share": np.average(d.observed_share, weights=d.county_km2),
        "carried_share": np.average(d.carried_share, weights=d.county_km2),
        "climatology_share": np.average(d.climatology_share, weights=d.county_km2),
        "nbar_share": np.average(d.nbar_share, weights=d.county_km2),
        "aoi_km2": d.county_km2.sum()}), include_groups=False).reset_index()
    aoi["gapfilled_share"] = aoi.carried_share + aoi.climatology_share
    aoi["source"] = np.where(aoi.nbar_share > 0, "MOD09A1+MCD43A4", "MOD09A1")
    miss = [dict(adate=c["adate"], composite_start=c["start"].strftime("%Y-%m-%d"), ndays=c["ndays"], source="none (not on PC)")
            for c in cal if not c["warmup"] and c["adate"] not in have]
    aoi = pd.concat([aoi, pd.DataFrame(miss)], ignore_index=True).sort_values("composite_start")
    cols = ["composite_start", "adate", "ndays", "openwater_km2", "flooded_veg_km2", "inundation_km2",
            "dense_floodedveg_observed_km2", "observed_share", "gapfilled_share", "carried_share",
            "climatology_share", "nbar_share", "aoi_km2", "source"]
    aoi[cols].to_csv(OUT_8DAY, index=False, float_format="%.4f")
    log("wrote", OUT_8DAY, len(aoi))

    # ---- monthly county values (day-weighted)
    recs = []
    for _, r in c8.iterrows():
        for m, d in month_overlaps(pd.Timestamp(r.composite_start), int(r.ndays)).items():
            recs.append((r.county_id, m, d, r.openwater_km2, r.inundation_km2, r.observed_share, r.climatology_share,
                         r.county_km2))
    md = pd.DataFrame(recs, columns=["county_id", "month", "w", "ow", "inn", "obs", "clim", "area"])
    md = md[(md.month >= "2018-01") & (md.month <= "2025-12")]
    g = md.groupby(["county_id", "month"])
    agg = g.apply(lambda d: pd.Series({"w": d.w.sum(), "ow": np.average(d.ow, weights=d.w),
                                       "inn": np.average(d.inn, weights=d.w), "obs": np.average(d.obs, weights=d.w),
                                       "clim": np.average(d.clim, weights=d.w), "area": d.area.iloc[0]}),
                  include_groups=False).reset_index()
    agg["days"] = pd.to_datetime(agg.month + "-01").dt.days_in_month
    agg = agg[agg.w >= MIN_MONTH_DAYS]
    out = []
    for _, r in agg.iterrows():
        dte = r.month + "-01"
        out += [(r.county_id, dte, "sudd_openwater_km2", round(r.ow, 3)),
                (r.county_id, dte, "sudd_inundation_km2", round(r.inn, 3)),
                (r.county_id, dte, "sudd_inundation_pct", round(100 * r.inn / r.area, 4)),
                (r.county_id, dte, "sudd_clear_pct", round(100 * r.obs, 2)),
                (r.county_id, dte, "sudd_climfill_pct", round(100 * r.clim, 2))]
    mdf = pd.DataFrame(out, columns=["county_id", "date", "variable", "value"]).sort_values(["variable", "county_id", "date"])
    mdf.to_csv(OUT_MONTHLY, index=False)
    log("wrote", OUT_MONTHLY, len(mdf), "rows,", mdf.date.nunique(), "months")

    # ---- annual peak (Sep-Dec) and low (Mar-May)
    series = [("SUDD_AOI", "Sudd AOI (16 counties)", "", aoi[aoi.source != "none (not on PC)"].copy())]
    cmeta = G["counties"].set_index("district_id")
    for cid, d in c8.groupby("county_id"):
        series.append((cid, cmeta.loc[cid, "name"], cmeta.loc[cid, "admin1"], d.copy()))
    arows = []
    expected_sepnov = {y: {c["start"].strftime("%Y-%m-%d") for c in cal if c["year"] == y and 9 <= c["start"].month <= 11}
                       for y in YEARS}
    for cid, name, adm, d in series:
        d = d.sort_values("composite_start").reset_index(drop=True)
        d["start"] = pd.to_datetime(d.composite_start)
        # 3-composite running median (robust to single-composite cloud/haze artefacts), only across
        # consecutive available composites
        for v in ("inundation_km2", "openwater_km2"):
            d[v + "_rm"] = d[v].rolling(3, center=True, min_periods=2).median()
        for y in YEARS:
            pk = d[(d.start.dt.year == y) & (d.start.dt.month >= 9)]
            lo = d[(d.start.dt.year == y) & d.start.dt.month.between(3, 5)]
            row = dict(district_id=cid, year=y, name=name, admin1=adm)
            if len(pk):
                ip = pk.inundation_km2_rm.idxmax()
                row.update(peak_inundation_km2=pk.inundation_km2_rm.max(), peak_inundation_raw_km2=pk.inundation_km2.max(),
                           peak_openwater_km2=pk.openwater_km2_rm.max(), peak_date=d.composite_start[ip],
                           peak_observed_share=d.observed_share[ip], peak_n_composites=len(pk),
                           peak_complete=bool(expected_sepnov[y] <= set(pk.composite_start)))
            if len(lo):
                il = lo.inundation_km2_rm.idxmin()
                row.update(low_inundation_km2=lo.inundation_km2_rm.min(), low_inundation_raw_km2=lo.inundation_km2.min(),
                           low_openwater_km2=lo.openwater_km2_rm.min(), low_date=d.composite_start[il],
                           low_observed_share=d.observed_share[il], low_n_composites=len(lo))
            arows.append(row)
    ann = pd.DataFrame(arows)
    ann.to_csv(OUT_ANNUAL, index=False, float_format="%.3f")
    log("wrote", OUT_ANNUAL, len(ann))
    return aoi, mdf, ann


def write_meta():
    src = "NASA MODIS Terra MOD09A1 v061 8-day 500 m surface reflectance via Microsoft Planetary Computer"
    url = "https://planetarycomputer.microsoft.com/dataset/modis-09A1-061"
    method = ("Sudd counties only (16). Per 8-day MOD09A1 composite, QA-clear pixels (state flags + blue<0.2) are "
              "classed OPEN WATER if MNDWI(b4,b6)>0 and INUNDATED if open water or EVI-LSWI<=0.05 (Xiao et al. 2006 / "
              "Sakamoto et al. 2007 flooding signal; captures water under papyrus/grass that MNDWI misses). Cloudy "
              "pixels take their last clear state if <=3 composites (24 days) old, else the 2018-2025 probability of "
              "inundation for that composite-of-year. Monthly = day-weighted mean of the 8-day areas. Sep-Oct 2022 "
              "partly from MCD43A4 NBAR (Terra tiles missing on PC). 2025-07..2025-11 missing (no MODIS on PC). "
              "Validation: docs/VALIDATION_sudd_water.md.")
    common = dict(category="environment", group="Water & flooding", source=src, source_url=url,
                  native_resolution="500 m", temporal="monthly")
    hc.write_meta("sudd_water", [
        dict(id="sudd_inundation_km2", label="Sudd inundated area incl. flooded vegetation (MODIS)", units="km2",
             aggregation="sum of inundated pixel area (observed + carried + climatology probability), day-weighted monthly mean of 8-day composites",
             higher_is="worse", index_ok=True, raster=RKEY, notes=method, **common),
        dict(id="sudd_inundation_pct", label="Sudd inundated area (% of county, MODIS)", units="% of county area",
             aggregation="sudd_inundation_km2 / county area x 100", higher_is="worse", index_ok=True, raster=RKEY,
             notes=method, **common),
        dict(id="sudd_openwater_km2", label="Sudd open water (MODIS MNDWI)", units="km2",
             aggregation="sum of open-water pixel area (MNDWI>0), day-weighted monthly mean of 8-day composites",
             higher_is="worse", index_ok=False, raster=RKEY,
             notes="Open water only (MNDWI>0); small (100s-1000s km2) and zero in some counties, so index_ok false. " + method,
             **common),
        dict(id="sudd_clear_pct", label="Cloud-free share (Sudd water layer)", units="% of county area",
             aggregation="day-weighted mean share of county pixels observed clear in the 8-day composites",
             higher_is="neutral", index_ok=False, raster=None,
             notes="Quality flag: share of the value that is directly observed (the rest is gap-filled). Low Jun-Oct.",
             **common),
        dict(id="sudd_climfill_pct", label="Climatology-filled share (Sudd water layer)", units="% of county area",
             aggregation="day-weighted mean share of county pixels filled from the 2018-2025 composite climatology",
             higher_is="neutral", index_ok=False, raster=None,
             notes="Quality flag: pixels cloudy for >24 days, filled with their 2018-2025 inundation probability for "
                   "that time of year; high values pull the month toward the climatological mean.", **common),
    ])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--pass1-only", action="store_true")
    ap.add_argument("--refresh-items", action="store_true")
    ap.add_argument("--clean-cache", action="store_true")
    args, _ = ap.parse_known_args()
    warnings.filterwarnings("ignore")
    t0 = time.time()
    items = list_items(args.refresh_items)
    cal = calendar()
    pass1(items, args.workers)
    if args.pass1_only:
        return
    c8 = pass2(cal)
    write_tables(c8, cal)
    write_meta()
    if args.clean_cache:
        shutil.rmtree(CACHE, ignore_errors=True)
    log(f"done in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from trend_stats import write_trends
    write_trends("sudd_water")
