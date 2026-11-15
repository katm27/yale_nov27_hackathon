#!/usr/bin/env python3
"""NASA FIRMS VIIRS 375 m active fires for South Sudan counties, 2018-01..2025-12.

Source: NASA FIRMS area API (standard-processing "SP" archive, collection 2):
    https://firms.modaps.eosdis.nasa.gov/api/area/csv/<MAP_KEY>/<SOURCE>/<W,S,E,N>/<days<=10>/<YYYY-MM-DD>
  - VIIRS_SNPP_SP   (Suomi-NPP)  2018-01-01..2025-12-31  -> trend series (one consistent sensor)
  - VIIRS_NOAA20_SP (NOAA-20)    2020-01-01..2025-12-31  -> reported separately (noaa20_* variables)
The MAP_KEY is read from the environment variable FIRMS_MAP_KEY and never written anywhere.
Requests are paced against /mapserver/mapkey_status/ (limit 5000 transactions per 10 min).

Filtering (per detection):
  * confidence in {n, h}  (nominal / high; 'l' = low is excluded)
  * type == 0 (presumed vegetation fire) where the SP 'type' field is present; type 2 = other static
    land source (gas flares at the oil fields of Unity / Upper Nile), 1 = volcano, 3 = offshore are excluded
  * point inside a county polygon (data/counties.geojson)

Outputs
  data/processed/viirs_fire_county_monthly.csv  viirs_fire_count, viirs_frp_sum (S-NPP),
                                                viirs_noaa20_fire_count, viirs_noaa20_frp_sum (NOAA-20, 2020+)
  data/processed/meta/viirs_fire.json
  docs/rasters/viirs_fire/YYYY-MM.png + meta.json  (S-NPP detections per 0.05 deg cell, log colour)
  data/raw/viirs_fire/viirs_<sensor>_<year>.csv.gz (filtered in-country detections) + SOURCE.md
  data/processed/validation/viirs_vs_modis_fire.csv (county correlation / ratio vs MODIS fire_count)

Usage: FIRMS_MAP_KEY=... python scripts/fetch_firms_viirs.py [--no-download] [--cache DIR]
"""
import argparse
import datetime as dt
import gzip
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import hazards_common as hc  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/viirs_fire"
OUT = ROOT / "data/processed/viirs_fire_county_monthly.csv"
VAL = ROOT / "data/processed/validation/viirs_vs_modis_fire.csv"
API = "https://firms.modaps.eosdis.nasa.gov"
BBOX = "23.4,3.4,36.0,12.3"  # W,S,E,N
SENSORS = {"VIIRS_SNPP_SP": ("2018-01-01", "2025-12-31"), "VIIRS_NOAA20_SP": ("2020-01-01", "2025-12-31")}
SHORT = {"VIIRS_SNPP_SP": "snpp", "VIIRS_NOAA20_SP": "noaa20"}
GRID = 0.05
SRC_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/"


def _get(url, timeout=180):
    req = urllib.request.Request(url, headers={"User-Agent": "ssd-hackathon-pipeline"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode()


def get(url, tries=8):
    key = os.environ["FIRMS_MAP_KEY"]
    err = None
    for i in range(tries):
        try:
            return _get(url)
        except Exception as e:  # noqa: BLE001 (flaky connection resets via proxy)
            err = str(e).replace(key, "<MAP_KEY>")
            time.sleep(min(60, 4 * (i + 1)))
    raise RuntimeError(f"failed after {tries}: {err}")


def pace():
    key = os.environ["FIRMS_MAP_KEY"]
    try:
        s = json.loads(get(f"{API}/mapserver/mapkey_status/?MAP_KEY={key}", tries=3))
        used = int(s.get("current_transactions", 0))
        if used > 4000:
            print(f"  {used} transactions used; sleeping 5 min", flush=True)
            time.sleep(300)
        return used
    except Exception:  # noqa: BLE001
        return None


def fetch_chunk(src, d, days, cache):
    """One cached API call (gzip on disk). Long requests can be cut by the network after ~10 s, so a failed
    multi-day chunk is retried as single days."""
    key = os.environ["FIRMS_MAP_KEY"]
    f = cache / f"{src}_{d}_{days}.csv.gz"
    if f.exists() and f.stat().st_size > 0:
        return 0
    try:
        txt = get(f"{API}/api/area/csv/{key}/{src}/{BBOX}/{days}/{d}", tries=3 if days > 1 else 10)
        if not txt.startswith("latitude"):
            raise RuntimeError(txt[:200])
    except Exception as e:  # noqa: BLE001
        if days == 1:
            raise RuntimeError(f"{src} {d}: {e}")
        return sum(fetch_chunk(src, d + dt.timedelta(days=i), 1, cache) for i in range(days))
    with gzip.open(f, "wt") as fh:
        fh.write(txt)
    return 1


def download(cache, chunk=4):
    if not os.environ.get("FIRMS_MAP_KEY"):
        sys.exit("FIRMS_MAP_KEY not set")
    cache.mkdir(parents=True, exist_ok=True)
    n = 0
    for src, (a, b) in SENSORS.items():
        d = dt.date.fromisoformat(a)
        end = dt.date.fromisoformat(b)
        while d <= end:
            days = min(chunk, (end - d).days + 1)
            # skip if this window is already fully covered by single-day files
            if not all((cache / f"{src}_{d + dt.timedelta(days=i)}_1.csv.gz").exists() for i in range(days)):
                n += fetch_chunk(src, d, days, cache)
                if n and n % 50 == 0:
                    print(f"  {src} {d} requests {n}; transactions used {pace()}", flush=True)
            d += dt.timedelta(days=days)
    print("download complete; new requests:", n, flush=True)


def load(cache, src):
    fs = sorted(cache.glob(f"{src}_*.csv.gz"))
    cols = ["latitude", "longitude", "acq_date", "acq_time", "satellite", "confidence", "frp", "bright_ti4",
            "daynight", "type"]
    df = pd.concat([pd.read_csv(f, usecols=lambda c: c in cols) for f in fs], ignore_index=True)
    df = df.drop_duplicates(["latitude", "longitude", "acq_date", "acq_time", "satellite"])
    a, b = SENSORS[src]
    df = df[(df.acq_date >= a) & (df.acq_date <= b)]
    n0 = len(df)
    conf = df.confidence.astype(str).str.lower().str[0]
    df = df[conf.isin(["n", "h"])]
    n1 = len(df)
    if "type" in df.columns:
        df = df[df["type"].fillna(0).astype(int) == 0]
    n2 = len(df)
    g = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.longitude, df.latitude), crs=4326)
    cty = gpd.read_file(hc.COUNTIES)[["district_id", "geometry"]]
    j = gpd.sjoin(g, cty, how="inner", predicate="within")
    j = j[~j.index.duplicated()]
    out = pd.DataFrame(j.drop(columns=["geometry", "index_right"])).rename(columns={"district_id": "county_id"})
    print(f"{src}: bbox {n0}, conf n/h {n1}, type0 {n2}, in-country {len(out)}", flush=True)
    return out, dict(bbox=n0, conf_nh=n1, type0=n2, in_country=len(out))


def county_month(df, prefix, ids, months):
    df = df.assign(month=df.acq_date.str[:7] + "-01")
    g = df.groupby(["county_id", "month"]).agg(cnt=("frp", "size"), frp=("frp", "sum"))
    idx = pd.MultiIndex.from_product([ids, months], names=["county_id", "month"])
    g = g.reindex(idx, fill_value=0).reset_index()
    a = g.assign(variable=f"{prefix}_fire_count", value=g.cnt)
    b = g.assign(variable=f"{prefix}_frp_sum", value=g.frp.round(2))
    out = pd.concat([a, b]).rename(columns={"month": "date"})
    return out[["county_id", "date", "variable", "value"]]


def rasters(df):
    canvas = hc.Canvas()
    W, S, E, N = 23.4, 3.4, 36.0, 12.3
    nx, ny = int(round((E - W) / GRID)), int(round((N - S) / GRID))
    from rasterio.transform import from_origin
    tr = from_origin(W, N, GRID, GRID)
    df = df.assign(month=df.acq_date.str[:7],
                   ix=((df.longitude - W) / GRID).astype(int).clip(0, nx - 1),
                   iy=((N - df.latitude) / GRID).astype(int).clip(0, ny - 1))
    vmin, vmax = 0.0, 2.0  # log10(count): 1 .. 100 detections per cell per month
    dates = []
    from rasterio.warp import Resampling
    for m in hc.months():
        grid = np.zeros((ny, nx), dtype="float32")
        sub = df[df.month == m]
        np.add.at(grid, (sub.iy.values, sub.ix.values), 1)
        lg = np.where(grid > 0, np.log10(grid), -1.0)  # -1 => transparent
        img = canvas.new()
        canvas.add(img, lg, tr, "EPSG:4326", Resampling.max)
        img[img < 0] = -1.0
        canvas.save_png(img, hc.RASTERS / "viirs_fire" / f"{m}.png", vmin - 0.001, vmax, "YlOrRd",
                        zero_transparent=True)
        dates.append(m)
    hc.write_raster_meta(
        "viirs_fire", "VIIRS active fires (S-NPP, per 0.05° cell)", "detections per 0.05° cell per month (log10)",
        canvas, vmin, vmax, "YlOrRd", "375 m detections binned to 0.05° (~5.5 km)", dates,
        "NASA FIRMS VIIRS S-NPP 375 m standard processing (VNP14IMGTDL SP)",
        notes="Colour = log10(number of nominal/high-confidence vegetation-fire detections in each 0.05° cell "
              "that month): 0 = 1 detection, 1 = 10, 2 = 100+. Transparent = no detection.")
    meta = json.loads((hc.RASTERS / "viirs_fire" / "meta.json").read_text())
    meta["scale"] = "log10"
    (hc.RASTERS / "viirs_fire" / "meta.json").write_text(json.dumps(meta, indent=1))


def compare_modis(viirs):
    p = ROOT / "data/processed/fire_county_monthly.csv"
    if not p.exists():
        return {}
    m = pd.read_csv(p)
    m = m[m.variable == "fire_count"][["county_id", "date", "value"]].rename(columns={"value": "modis"})
    v = viirs[viirs.variable == "viirs_fire_count"][["county_id", "date", "value"]].rename(columns={"value": "viirs"})
    j = v.merge(m, on=["county_id", "date"])
    rows = []
    for cid, g in j.groupby("county_id"):
        r = g.viirs.corr(g.modis) if g.viirs.std() > 0 and g.modis.std() > 0 else np.nan
        rows.append(dict(county_id=cid, n_months=len(g), pearson_r=round(r, 3) if pd.notna(r) else np.nan,
                         spearman_r=round(g.viirs.corr(g.modis, method="spearman"), 3),
                         viirs_total=int(g.viirs.sum()), modis_total=round(g.modis.sum(), 1),
                         ratio_viirs_to_modis=round(g.viirs.sum() / g.modis.sum(), 2) if g.modis.sum() else np.nan))
    out = pd.DataFrame(rows)
    VAL.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(VAL, index=False)
    nat = j.groupby("date")[["viirs", "modis"]].sum()
    s = dict(n_county_months=len(j), pooled_r=round(j.viirs.corr(j.modis), 3),
             pooled_spearman=round(j.viirs.corr(j.modis, method="spearman"), 3),
             national_monthly_r=round(nat.viirs.corr(nat.modis), 3),
             ratio_total=round(j.viirs.sum() / j.modis.sum(), 2),
             median_county_r=round(out.pearson_r.median(), 3),
             annual_national=j.assign(y=j.date.str[:4]).groupby("y")[["viirs", "modis"]].sum().round(0)
             .astype(int).to_dict(orient="index"))
    print("VIIRS vs MODIS:", json.dumps(s), flush=True)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-download", action="store_true")
    ap.add_argument("--no-rasters", action="store_true")
    ap.add_argument("--cache", default=os.environ.get("FIRMS_CACHE", str(RAW / "_api_cache")))
    a = ap.parse_args()
    cache = Path(a.cache)
    if not a.no_download:
        download(cache)
    ids = hc.county_ids()
    frames, stats, pts = [], {}, {}
    for src, (s, e) in SENSORS.items():
        df, st = load(cache, src)
        stats[src] = st
        pts[src] = df
        months = [x + "-01" for x in hc.months(s, e)]
        prefix = "viirs" if src == "VIIRS_SNPP_SP" else "viirs_noaa20"
        frames.append(county_month(df, prefix, ids, months))
        # raw filtered detections per sensor-year (gzip; each well under 50 MB)
        RAW.mkdir(parents=True, exist_ok=True)
        keep = ["latitude", "longitude", "acq_date", "acq_time", "confidence", "frp", "bright_ti4", "daynight",
                "county_id"]
        for y, g in df.groupby(df.acq_date.str[:4]):
            g[keep].sort_values(["acq_date", "acq_time"]).to_csv(
                RAW / f"viirs_{SHORT[src]}_{y}.csv.gz", index=False, compression="gzip")
    out = pd.concat(frames).sort_values(["variable", "county_id", "date"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    print("wrote", OUT, len(out), flush=True)

    cmp_ = compare_modis(out)
    # sensor inter-comparison 2020-2025
    sn = out[out.variable == "viirs_fire_count"].set_index(["county_id", "date"]).value
    n20 = out[out.variable == "viirs_noaa20_fire_count"].set_index(["county_id", "date"]).value
    jj = pd.concat([sn, n20], axis=1, join="inner")
    jj.columns = ["snpp", "noaa20"]
    sens = dict(r=round(jj.snpp.corr(jj.noaa20), 3), ratio_noaa20_to_snpp=round(jj.noaa20.sum() / jj.snpp.sum(), 2))
    print("NOAA-20 vs S-NPP (2020-2025):", sens, flush=True)

    cmp_txt = (f"Versus MODIS fire_count (fire_pipeline.py, same months): pooled county-month Pearson r = "
               f"{cmp_.get('pooled_r')}, Spearman = {cmp_.get('pooled_spearman')}, national monthly r = "
               f"{cmp_.get('national_monthly_r')}, median per-county r = {cmp_.get('median_county_r')}; VIIRS "
               f"detects {cmp_.get('ratio_total')}x as many fires as MODIS (finer 375 m pixels see small fires). "
               f"Per-county table: data/processed/validation/viirs_vs_modis_fire.csv.") if cmp_ else ""
    common = dict(category="environment", group="Fire", temporal="monthly", index_ok=False, source_url=SRC_URL,
                  native_resolution="375 m")
    filt = ("nominal/high confidence only (low excluded), type 0 = presumed vegetation fire (static sources such "
            "as oil-field gas flares excluded), detection point inside county")
    hc.write_meta("viirs_fire", [
        dict(id="viirs_fire_count", label="VIIRS active fire detections (S-NPP)", units="detections per month",
             source="NASA FIRMS VIIRS S-NPP 375 m, standard processing (VIIRS_SNPP_SP)",
             aggregation="count of detections; " + filt, higher_is="worse", raster="viirs_fire",
             notes="Single sensor (Suomi-NPP) for the whole 2018-2025 series so trends are consistent. "
                   "Strongly seasonal (dry season Nov-Mar), zero in most wet-season months. " + cmp_txt, **common),
        dict(id="viirs_frp_sum", label="VIIRS fire radiative power (S-NPP, sum)", units="MW (sum over detections)",
             source="NASA FIRMS VIIRS S-NPP 375 m, standard processing (VIIRS_SNPP_SP)",
             aggregation="sum of per-detection FRP; " + filt, higher_is="worse", raster="viirs_fire",
             notes="Sum of instantaneous FRP at overpass time; a proxy for fire intensity x extent.", **common),
        dict(id="viirs_noaa20_fire_count", label="VIIRS active fire detections (NOAA-20)",
             units="detections per month", source="NASA FIRMS VIIRS NOAA-20 375 m, standard processing",
             aggregation="count of detections; " + filt, higher_is="worse", raster=None,
             notes=f"2020-2025 only; reported separately (not mixed into the S-NPP trend series). NOAA-20 vs "
                   f"S-NPP county-month r = {sens['r']}, NOAA-20/S-NPP total ratio = "
                   f"{sens['ratio_noaa20_to_snpp']}.", **common),
        dict(id="viirs_noaa20_frp_sum", label="VIIRS fire radiative power (NOAA-20, sum)",
             units="MW (sum over detections)", source="NASA FIRMS VIIRS NOAA-20 375 m, standard processing",
             aggregation="sum of per-detection FRP; " + filt, higher_is="worse", raster=None,
             notes="2020-2025 only.", **common),
    ])
    (RAW / "SOURCE.md").write_text(
        "# NASA FIRMS VIIRS 375 m active fires\n\n"
        "Downloaded with `scripts/fetch_firms_viirs.py` (needs env FIRMS_MAP_KEY; free key from "
        "https://firms.modaps.eosdis.nasa.gov/api/map_key/).\n\n"
        "Requests (10-day chunks, bbox W,S,E,N = 23.4,3.4,36.0,12.3):\n\n"
        "    https://firms.modaps.eosdis.nasa.gov/api/area/csv/<MAP_KEY>/VIIRS_SNPP_SP/23.4,3.4,36.0,12.3/10/<YYYY-MM-DD>\n"
        "    https://firms.modaps.eosdis.nasa.gov/api/area/csv/<MAP_KEY>/VIIRS_NOAA20_SP/23.4,3.4,36.0,12.3/10/<YYYY-MM-DD>\n\n"
        "S-NPP 2018-01-01..2025-12-31, NOAA-20 2020-01-01..2025-12-31 (standard-processing archive, collection 2).\n\n"
        "Files here: `viirs_<snpp|noaa20>_<year>.csv.gz` = detections after filtering (confidence n/h, type 0, "
        "inside a county) with the county_id they fall in. The unfiltered bbox API responses are cached in "
        "`_api_cache/` (not committed).\n\n"
        f"Filter counts: {json.dumps(stats)}\n\n"
        "Citation: NASA FIRMS, VIIRS 375 m active fire product VNP14IMGTDL / VJ114IMGTDL (Schroeder et al. 2014). "
        "doi:10.5067/FIRMS/VIIRS/VNP14IMGT_NRT.002\n")
    if not a.no_rasters:
        rasters(pts["VIIRS_SNPP_SP"])
        print("rasters done", flush=True)


if __name__ == "__main__":
    main()
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from trend_stats import write_trends
    write_trends("viirs_fire")  # Mann-Kendall + Sen's slope (scripts/trend_stats.py)
