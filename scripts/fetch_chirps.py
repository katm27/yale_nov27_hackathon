#!/usr/bin/env python3
"""CHIRPS v3.0 monthly rainfall (0.05°) for South Sudan counties, 2018-01..2025-12, plus a cross-validation of
the project's three rainfall sources (CHIRPS v3, IMERG precip_mm, TerraClimate tc_ppt).

Source: Climate Hazards Center, UCSB (no login)
    https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/africa/tifs/chirps-v3.0.YYYY.MM.tif
Each Africa GeoTIFF (~5 MB) is downloaded to a cache, cropped to the South Sudan bbox, and the crop stack is
saved to data/raw/chirps/chirps_v3_ssd_2018_2025.nc (~small, committed).

County aggregation: area-weighted mean of 0.05° cells (cell-coverage fraction x cos lat; same method as
fetch_terraclimate.py).

Outputs
  data/processed/chirps_county_monthly.csv          chirps_precip_mm
  data/processed/meta/chirps.json
  docs/rasters/chirps/YYYY-MM.png + meta.json        (blues, fixed scale)
  data/processed/validation/rainfall_source_comparison.csv
  docs/VALIDATION_rainfall.md

Usage: python scripts/fetch_chirps.py [--no-download] [--no-rasters] [--cache DIR]
"""
import argparse
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import xarray as xr
from rasterio.windows import from_bounds

sys.path.insert(0, str(Path(__file__).parent))
from fetch_terraclimate import Overlay, weights, county_means  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
COUNTIES = ROOT / "data/counties.geojson"
RAW = ROOT / "data/raw/chirps"
STACK = RAW / "chirps_v3_ssd_2018_2025.nc"
OUT = ROOT / "data/processed/chirps_county_monthly.csv"
META = ROOT / "data/processed/meta/chirps.json"
RASTERS = ROOT / "docs/rasters/chirps"
VAL = ROOT / "data/processed/validation/rainfall_source_comparison.csv"
DOC = ROOT / "docs/VALIDATION_rainfall.md"
URL = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/africa/tifs/chirps-v3.0.{y}.{m:02d}.tif"
BBOX = (23.3, 3.3, 36.1, 12.4)  # W S E N
MONTHS = pd.date_range("2018-01-01", "2025-12-01", freq="MS")
SRC = "CHIRPS v3.0 monthly (Climate Hazards Center, UCSB)"
SRC_URL = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/"
BLUES = ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"]


def fetch(t, cache):
    out = cache / f"chirps-v3.0.{t.year}.{t.month:02d}.tif"
    if out.exists() and out.stat().st_size > 100000:
        return out
    url = URL.format(y=t.year, m=t.month)
    for i in range(6):
        try:
            tmp = out.with_suffix(".part")
            with urllib.request.urlopen(url, timeout=300) as r, open(tmp, "wb") as fh:
                fh.write(r.read())
            tmp.rename(out)
            return out
        except Exception as e:  # noqa: BLE001
            print("retry", url, e, flush=True)
            time.sleep(5 * (i + 1))
    print("FAILED", url, flush=True)
    return None


def build_stack(cache):
    arrs, times, lat, lon = [], [], None, None
    for t in MONTHS:
        p = cache / f"chirps-v3.0.{t.year}.{t.month:02d}.tif"
        if not p.exists():
            continue
        with rasterio.open(p) as src:
            win = from_bounds(*BBOX, src.transform).round_offsets().round_lengths()
            a = src.read(1, window=win).astype("float32")
            nod = src.nodata
            tr = src.window_transform(win)
        if nod is not None:
            a[a == nod] = np.nan
        a[a < 0] = np.nan
        if lat is None:
            h, w = a.shape
            lon = tr.c + tr.a * (np.arange(w) + 0.5)
            lat = tr.f + tr.e * (np.arange(h) + 0.5)
        arrs.append(a)
        times.append(t)
    da = xr.DataArray(np.stack(arrs), coords=dict(time=times, lat=np.round(lat, 4), lon=np.round(lon, 4)),
                      dims=("time", "lat", "lon"), name="precip",
                      attrs=dict(units="mm/month", source=SRC, url=SRC_URL))
    RAW.mkdir(parents=True, exist_ok=True)
    da.to_dataset().to_netcdf(STACK, encoding={"precip": dict(zlib=True, complevel=5, least_significant_digit=1)})
    return da


def validation(chirps_long):
    c = chirps_long.rename(columns={"value": "chirps"}).drop(columns="variable")
    im = pd.read_csv(ROOT / "data/processed/drive_climate_county_monthly.csv")
    im = im[im.variable == "precip_mm"][["county_id", "date", "value"]].rename(columns={"value": "imerg"})
    tc = pd.read_csv(ROOT / "data/processed/terraclimate_county_monthly.csv")
    tc = tc[tc.variable == "tc_ppt"][["county_id", "date", "value"]].rename(columns={"value": "terraclimate"})
    j = c.merge(im, on=["county_id", "date"], how="outer").merge(tc, on=["county_id", "date"], how="outer")
    j = j[(j.date >= "2018-01-01") & (j.date <= "2025-12-01")]
    pairs = [("chirps", "imerg"), ("chirps", "terraclimate"), ("imerg", "terraclimate")]
    cty = gpd.read_file(COUNTIES)[["district_id", "name"]].rename(columns={"district_id": "county_id"})

    def stats(g):
        r = {"n_months": int(g[["chirps", "imerg", "terraclimate"]].dropna().shape[0])}
        for s in ("chirps", "imerg", "terraclimate"):
            r[f"mean_{s}_mm"] = round(g[s].mean(), 1)
        for a, b in pairs:
            gg = g[[a, b]].dropna()
            r[f"r_{a}_{b}"] = round(gg[a].corr(gg[b]), 3) if len(gg) > 2 else np.nan
            # anomaly correlation: remove each source's own monthly climatology
            if len(gg) > 24:
                mo = pd.to_datetime(g.loc[gg.index, "date"]).dt.month
                an_a = gg[a] - gg[a].groupby(mo).transform("mean")
                an_b = gg[b] - gg[b].groupby(mo).transform("mean")
                r[f"r_anom_{a}_{b}"] = round(an_a.corr(an_b), 3)
            else:
                r[f"r_anom_{a}_{b}"] = np.nan
            r[f"bias_{a}_minus_{b}_mm"] = round((gg[a] - gg[b]).mean(), 1)
            r[f"pct_bias_{a}_vs_{b}"] = round(100 * (gg[a].sum() - gg[b].sum()) / gg[b].sum(), 1) if gg[b].sum() else np.nan
            r[f"rmse_{a}_{b}_mm"] = round(float(np.sqrt(((gg[a] - gg[b]) ** 2).mean())), 1)
        return pd.Series(r)

    rows = j.groupby("county_id").apply(stats, include_groups=False).reset_index()
    rows = cty.merge(rows, on="county_id", how="right")
    VAL.parent.mkdir(parents=True, exist_ok=True)
    rows.to_csv(VAL, index=False)

    # national summaries
    nat = j.dropna(subset=["chirps", "imerg", "terraclimate"])
    ann = nat.assign(y=nat.date.str[:4]).groupby(["y", "county_id"])[["chirps", "imerg", "terraclimate"]].sum() \
        .groupby("y").mean().round(0)
    pooled = {f"{a}-{b}": round(nat[a].corr(nat[b]), 3) for a, b in pairs}
    mo = pd.to_datetime(nat.date).dt.month
    anom = {s: nat[s] - nat.groupby([nat.county_id, mo])[s].transform("mean") for s in ("chirps", "imerg", "terraclimate")}
    pooled_anom = {f"{a}-{b}": round(anom[a].corr(anom[b]), 3) for a, b in pairs}
    # annual-total anomaly correlation (interannual signal)
    annc = nat.assign(y=nat.date.str[:4]).groupby(["county_id", "y"])[["chirps", "imerg", "terraclimate"]].sum()
    annc = annc - annc.groupby("county_id").transform("mean")
    ann_r = {f"{a}-{b}": round(annc[a].corr(annc[b]), 3) for a, b in pairs}
    clim = nat.groupby(mo)[["chirps", "imerg", "terraclimate"]].mean().round(0)
    worst = rows.sort_values("r_chirps_imerg").head(5)[["name", "r_chirps_imerg", "pct_bias_chirps_vs_imerg"]]
    med = rows[[c for c in rows.columns if c.startswith(("r_", "pct_bias"))]].median().round(3)

    def md_table(df):
        cols = [str(c) for c in df.columns]
        out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
        for _, r in df.iterrows():
            out.append("| " + " | ".join(str(v) for v in r.values) + " |")
        return "\n".join(out)

    txt = f"""# Rainfall source cross-validation (South Sudan, 79 counties, 2018-01..2025-12)

Generated by `scripts/fetch_chirps.py`. Per-county table: `data/processed/validation/rainfall_source_comparison.csv`.

Sources (all county area-weighted means, mm/month):
- **CHIRPS v3.0** (`chirps_precip_mm`, 0.05°, IR + station blend, gauge-undercatch corrected; ERA5 fill)
- **IMERG** (`precip_mm`, data/processed/drive_climate_county_monthly.csv, 0.1° satellite, gauge-calibrated)
- **TerraClimate** (`tc_ppt`, 1/24°, climatically-aided interpolation of CRU/JRA/ERA5 anomalies)

There are almost no rain gauges in South Sudan reporting to GTS, so none of these is "truth"; agreement between
independent-ish sources is the best available check.

## Headline numbers ({len(nat)} county-months with all three sources)

| pair | pooled r (raw monthly) | pooled r (monthly anomaly) | r (annual-total anomaly) | median county r | median county % bias (first vs second) |
|---|---|---|---|---|---|
""" + "\n".join(
        f"| {a} vs {b} | {pooled[f'{a}-{b}']} | {pooled_anom[f'{a}-{b}']} | {ann_r[f'{a}-{b}']} | {med[f'r_{a}_{b}']} | {med[f'pct_bias_{a}_vs_{b}']}% |"
        for a, b in pairs) + f"""

Raw monthly correlation is dominated by the shared seasonal cycle (dry Dec-Mar, wet May-Oct), so it is high for
every pair. The anomaly correlations (each county's own calendar-month mean removed) measure agreement on
*unusual* months, which is what matters for drought/flood indicators and trends.

## Mean annual rainfall (mean over counties, mm/yr)

{md_table(ann.reset_index().rename(columns={'y': 'year'}).astype({'chirps': int, 'imerg': int, 'terraclimate': int}))}

## Mean seasonal cycle (mean over counties and years, mm/month)

{md_table(clim.T.reset_index().rename(columns={'index': 'source'}))}

## Counties with the weakest CHIRPS-IMERG agreement

{md_table(worst)}

## Take-aways
- Use **CHIRPS** for rainfall levels and anomalies at county scale (finest grid, station-blended, longest record);
  IMERG and CHIRPS agree closely on anomalies, so IMERG-based indicators (e.g. SPEI) remain consistent.
- **TerraClimate tc_ppt** is systematically drier (see % bias) and has weaker anomaly agreement; use it for its
  water-balance variables (soil, deficit, AET) rather than as a rainfall source.
- Differences are largest in the Sudd/flood-plain and north-eastern counties where satellite IR retrievals and
  ERA5 fill dominate.
"""
    DOC.write_text(txt)
    print(txt[:3000], flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-download", action="store_true")
    ap.add_argument("--no-rasters", action="store_true")
    ap.add_argument("--cache", default=os.environ.get("CHIRPS_CACHE", str(RAW / "_cache")))
    a = ap.parse_args()
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)
    if not a.no_download:
        with ThreadPoolExecutor(4) as ex:
            res = list(ex.map(lambda t: fetch(t, cache), MONTHS))
        print("downloaded", sum(r is not None for r in res), "/", len(MONTHS), flush=True)
        da = build_stack(cache)
    else:
        da = xr.open_dataset(STACK)["precip"].load()
    cty = gpd.read_file(COUNTIES)[["district_id", "geometry"]]
    ids = cty.district_id.tolist()
    W = weights(cty, da.lat.to_index(), da.lon.to_index())
    cm = county_means(da, W)
    df = pd.DataFrame(cm, index=pd.DatetimeIndex(da.time.values).strftime("%Y-%m-01"), columns=ids)
    long = df.stack().rename("value").reset_index()
    long.columns = ["date", "county_id", "value"]
    long["variable"] = "chirps_precip_mm"
    long["value"] = long.value.round(2)
    long = long.dropna()[["county_id", "date", "variable", "value"]].sort_values(["county_id", "date"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    long.to_csv(OUT, index=False)
    print("wrote", OUT, len(long), "months", long.date.nunique(), flush=True)
    span = f"{long.date.min()[:7]}..{long.date.max()[:7]}"
    META.write_text(json.dumps([dict(
        id="chirps_precip_mm", label="Rainfall (CHIRPS v3)", category="environment", group="Precipitation",
        units="mm/month", source=SRC, source_url=SRC_URL, native_resolution="0.05° (~5.5 km)", temporal="monthly",
        aggregation="area-weighted mean of 0.05° cells (cell coverage fraction x cos lat)", higher_is="better",
        index_ok=True, raster="chirps",
        notes=f"Coverage {span}. Satellite IR + station blend with gauge-undercatch correction (v3 is wetter than "
              "v2). Cross-validated against IMERG precip_mm and TerraClimate tc_ppt: see docs/VALIDATION_rainfall.md. "
              "Ratio to 2018 is meaningless in dry-season months near 0 mm; compare wet-season or annual totals.")],
        indent=1, ensure_ascii=False))
    (RAW / "SOURCE.md").write_text(
        "# CHIRPS v3.0 monthly rainfall\n\n"
        f"Per-month Africa GeoTIFFs (0.05°, mm/month), {MONTHS[0]:%Y-%m}..{MONTHS[-1]:%Y-%m}:\n\n"
        "    https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/africa/tifs/chirps-v3.0.YYYY.MM.tif\n\n"
        "The ~5 MB Africa files are cached in `_cache/` (not committed). `chirps_v3_ssd_2018_2025.nc` holds the crop to "
        f"bbox W{BBOX[0]} S{BBOX[1]} E{BBOX[2]} N{BBOX[3]} for all months (re-run with `--no-download`).\n\n"
        "Citation: Funk, C. et al. (2015) Sci. Data 2:150066; CHIRPS v3.0 (Climate Hazards Center, UCSB, 2025).\n")
    validation(long)
    if a.no_rasters:
        return
    ov = Overlay(da.lat.to_index(), da.lon.to_index(), cty)
    inside = (W.sum(0) > 0).reshape(da.shape[1:])
    vals = da.values[:, inside]
    vmin, vmax = 0.0, round(float(np.nanpercentile(vals, 98)), 0)
    RASTERS.mkdir(parents=True, exist_ok=True)
    pal = Overlay.palette(BLUES)
    dates = []
    for i, t in enumerate(pd.DatetimeIndex(da.time.values)):
        ds = t.strftime("%Y-%m")
        ov.save(da.values[i], RASTERS / f"{ds}.png", vmin, vmax, pal)
        dates.append(ds)
    (RASTERS / "meta.json").write_text(json.dumps(dict(
        key="chirps", label="Rainfall (CHIRPS v3)", units="mm/month", bounds=ov.bounds, vmin=vmin, vmax=vmax,
        colormap="blues", colors=BLUES, scale="linear", native_resolution="0.05° (~5.5 km)", dates=dates, source=SRC,
        notes="Fixed colour scale 0 .. 98th percentile of all in-country pixels over all months; bilinear "
              "reprojection to EPSG:3857."), indent=1, ensure_ascii=False))
    sz = sum(p.stat().st_size for p in RASTERS.glob("*.png"))
    print("rasters", len(dates), vmin, vmax, f"{sz / 1e6:.1f} MB", flush=True)


if __name__ == "__main__":
    main()
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from trend_stats import write_trends
    write_trends("chirps")
