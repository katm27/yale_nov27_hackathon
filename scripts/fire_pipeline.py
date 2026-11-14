"""Fires for South Sudan counties, 2018-01..2025-12.

1. MODIS active fire (MOD14A1 + MYD14A1 v061, daily 1 km FireMask, Planetary Computer)
   -> fire_count = number of fire pixel-detections (FireMask 7/8/9 = low/nominal/high confidence)
      per county per month, summed over Terra and Aqua daily layers.
2. MODIS burned area (MCD64A1 v061, monthly 500 m, Planetary Computer)
   -> burned_area_km2, burned_area_pct per county-month + web overlay docs/rasters/burned_area/.

Usage: python scripts/fire_pipeline.py [active|burned|all]
"""
import sys
import time
import datetime as dt
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import rasterio
import planetary_computer as pc
from rasterio.warp import Resampling

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import hazards_common as hc

OUT = hc.PROC / "fire_county_monthly.csv"
PART_DIR = hc.REPO / "data" / "raw" / "fire"


def resign(href):
    return pc.sign(href.split("?")[0])


def read_window(href, indexes=None):
    for attempt in range(5):
        try:
            with rasterio.open(resign(href)) as src:
                win = hc.window_for_bbox(src)
                if win is None:
                    return None
                arr = src.read(indexes, window=win)
                return arr, src.window_transform(win), src.crs
        except Exception as e:  # noqa
            err = e
            time.sleep(3 * (attempt + 1))
    print("FAILED", href.split("?")[0], err, flush=True)
    return None


# ------------------------------------------------------------------ active fire
def active():
    ids = hc.county_ids()
    items = []
    for y in range(2018, 2026):
        dtr = f"{y-1}-12-20/{y}-12-31" if y == 2018 else f"{y}-01-01/{y}-12-31"
        items += hc.search("modis-14A1-061", dtr)
    seen = {}
    for it in items:
        seen[it.id] = it
    items = list(seen.values())
    print("14A1 items:", len(items), flush=True)
    counts = defaultdict(float)  # (yyyy-mm, label) -> count
    ndays = defaultdict(set)     # yyyy-mm -> set of (sensor, day) with data

    def work(it):
        r = read_window(it.assets["FireMask"].href)
        if r is None:
            return it, None
        arr, tr, crs = r
        lab = hc.labels_for(crs, tr, arr.shape[1:])
        start = dt.date.fromisoformat(it.properties["start_datetime"][:10])
        out = []
        for i in range(arr.shape[0]):
            d = start + dt.timedelta(days=i)
            if not (dt.date(2018, 1, 1) <= d <= dt.date(2025, 12, 31)):
                continue
            band = arr[i]
            if not (band > 0).any():  # band entirely fill -> no data that day
                continue
            fire = (band >= 7) & (band <= 9)
            out.append((d, hc.bincount(lab, fire)))
        return it, out

    done = 0
    t0 = time.time()
    with ThreadPoolExecutor(8) as ex:
        futs = [ex.submit(work, it) for it in items]
        for f in as_completed(futs):
            it, out = f.result()
            done += 1
            if out:
                sensor = it.id[:3]
                for d, bc in out:
                    m = d.strftime("%Y-%m")
                    ndays[m].add((sensor, d))
                    for lab_i in range(1, len(bc)):
                        counts[(m, lab_i)] += bc[lab_i]
            if done % 100 == 0:
                print(f"active {done}/{len(items)} {time.time()-t0:.0f}s", flush=True)
    rows = []
    for m in hc.months():
        if not ndays.get(m):
            continue
        for lab_i, cid in enumerate(ids, start=1):
            rows.append((cid, m + "-01", "fire_count", counts.get((m, lab_i), 0.0)))
    df = pd.DataFrame(rows, columns=["county_id", "date", "variable", "value"])
    cov = pd.Series({m: len(v) for m, v in ndays.items()}).sort_index()
    PART_DIR.mkdir(parents=True, exist_ok=True)
    cov.to_csv(PART_DIR / "active_fire_sensor_days.csv", header=["sensor_days"])
    df.to_csv(PART_DIR / "part_active.csv", index=False)
    print("active done rows", len(df), "sensor-days min/max", cov.min(), cov.max(), flush=True)


# ------------------------------------------------------------------ burned area
def burned():
    ids = hc.county_ids()
    canvas = hc.Canvas()
    PIX_KM2 = None
    rows, dates = [], []
    for m in hc.months():
        y, mo = map(int, m.split("-"))
        items = hc.search("modis-64A1-061", f"{m}-01/{m}-{pd.Timestamp(m+'-01').days_in_month:02d}")
        items = [it for it in items if it.properties["start_datetime"][:7] == m]
        if not items:
            print("no burned items", m, flush=True)
            continue
        burned_n = np.zeros(len(ids) + 1)
        valid_n = np.zeros(len(ids) + 1)
        total_n = np.zeros(len(ids) + 1)
        img = canvas.new()
        with ThreadPoolExecutor(4) as ex:
            res = list(ex.map(lambda it: read_window(it.assets["Burn_Date"].href, 1), items))
        for r in res:
            if r is None:
                continue
            arr, tr, crs = r
            PIX_KM2 = abs(tr.a * tr.e) / 1e6
            lab = hc.labels_for(crs, tr, arr.shape)
            b = arr > 0
            valid = arr >= 0  # -1 fill/unmapped, -2 water
            burned_n += hc.bincount(lab, b)
            valid_n += hc.bincount(lab, valid)
            total_n += hc.bincount(lab)
            frac = np.where(arr == -1, np.nan, b.astype("float32"))
            canvas.add(img, frac, tr, crs, Resampling.average)
        canvas.save_png(img, hc.RASTERS / "burned_area" / f"{m}.png", 0.0, 1.0, "YlOrRd",
                        zero_transparent=True, nodata_rgba=(160, 160, 160, 90))
        dates.append(m)
        for i, cid in enumerate(ids, start=1):
            if valid_n[i] == 0:
                continue
            km2 = burned_n[i] * PIX_KM2
            rows.append((cid, m + "-01", "burned_area_km2", round(km2, 3)))
            rows.append((cid, m + "-01", "burned_area_pct", round(100 * burned_n[i] / total_n[i], 4)))
        print("burned", m, "SS total km2", round(burned_n.sum() * (PIX_KM2 or 0)), flush=True)
    hc.write_raster_meta("burned_area", "Burned area (monthly)", "fraction of pixel burned", canvas, 0.0, 1.0,
                         "YlOrRd", "500 m (MCD64A1), displayed at ~1.3 km", dates,
                         "MODIS MCD64A1 v061 via Microsoft Planetary Computer",
                         notes="Transparent = not burned this month; grey = unmapped/no data. Value = share of "
                               "500 m pixels burned inside each display pixel.")
    df = pd.DataFrame(rows, columns=["county_id", "date", "variable", "value"])
    PART_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(PART_DIR / "part_burned.csv", index=False)
    print("burned done rows", len(df), flush=True)


def combine():
    parts = []
    if (PART_DIR / "part_active.csv").exists():
        a = pd.read_csv(PART_DIR / "part_active.csv")
        # normalise to a full month of Terra+Aqua daily coverage; drop months with < 50 % coverage
        cov = pd.read_csv(PART_DIR / "active_fire_sensor_days.csv", index_col=0)["sensor_days"]
        m = a.date.str[:7]
        expected = 2 * pd.to_datetime(a.date).dt.days_in_month
        frac = m.map(cov) / expected
        a["value"] = (a.value / frac.clip(upper=1)).round(1)
        a = a[frac >= 0.5]
        parts.append(a)
    if (PART_DIR / "part_burned.csv").exists():
        parts.append(pd.read_csv(PART_DIR / "part_burned.csv"))
    df = pd.concat(parts).sort_values(["variable", "county_id", "date"])
    df.to_csv(OUT, index=False)
    common = dict(category="environment", group="Fire", temporal="monthly", index_ok=False)
    hc.write_meta("fire", [
        dict(id="fire_count", label="Active fire detections", units="fire pixel-detections per month",
             source="MODIS MOD14A1/MYD14A1 v061 (Terra+Aqua daily 1 km FireMask) via Microsoft Planetary Computer",
             source_url="https://planetarycomputer.microsoft.com/dataset/modis-14A1-061",
             native_resolution="1 km", aggregation="count of daily 1 km fire pixels (FireMask 7-9, all confidence "
             "levels) inside county, summed over Terra and Aqua and all days of the month",
             higher_is="worse", raster=None,
             notes="Months with incomplete Terra/Aqua daily coverage on Planetary Computer are scaled to a full "
                   "month (count x expected/available sensor-days; e.g. 2022-12 had 38/62); months with <50% "
                   "coverage are dropped (2025-07..2025-11 missing from the PC catalogue). "
                   "Comparable to FIRMS MODIS counts (FIRMS API not reachable from build env). Strongly seasonal "
                   "(dry season Nov-Mar). index_ok false because many county-months are 0.", **common),
        dict(id="burned_area_km2", label="Burned area", units="km2",
             source="MODIS MCD64A1 v061 burned area via Microsoft Planetary Computer",
             source_url="https://planetarycomputer.microsoft.com/dataset/modis-64A1-061",
             native_resolution="500 m", aggregation="sum of burned 500 m pixels (Burn_Date>0) x pixel area "
             "(sinusoidal equal-area, 0.2147 km2)", higher_is="worse", raster="burned_area",
             notes="Monthly burned area; zero in most wet-season months. Months absent from the Planetary Computer "
                   "catalogue (no rows, no PNG): 2023-09, 2024-07, 2025-05, 2025-08, 2025-09, 2025-10.", **common),
        dict(id="burned_area_pct", label="Burned area (% of county)", units="% of county area",
             source="MODIS MCD64A1 v061 burned area via Microsoft Planetary Computer",
             source_url="https://planetarycomputer.microsoft.com/dataset/modis-64A1-061",
             native_resolution="500 m", aggregation="burned pixels / all pixels in county x 100",
             higher_is="worse", raster="burned_area", notes="", **common),
    ])
    print("wrote", OUT, len(df))


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("active", "all"):
        active()
    if what in ("burned", "all"):
        burned()
    combine()
