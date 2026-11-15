"""GRACE / GRACE-FO water storage for South Sudan counties (no login needed: GFZ ISDC open archive).

Sources (GFZ GravIS, https://isdc-data.gfz.de/grace-fo/GravIS/):
  * Terrestrial water storage anomaly (TWSA), COST-G combined GRACE+GRACE-FO Level-3 grid, 1 degree, monthly,
    2002-04 .. present, cm equivalent water height, with per-cell uncertainty (std_tws).
    DOI 10.5880/COST-G.GRAVIS_02_L3_TWS
  * Groundwater storage anomaly (GWSA), G3P v1.12 (Global Gravity-based Groundwater Product), 0.5 degree, monthly,
    2002-04 .. 2023-09, mm; GWSA = GRACE TWSA minus soil moisture, surface water, snow and glacier storage.
    DOI 10.5880/G3P.2024.001

Effective spatial resolution of GRACE is ~300 km (a few hundred km Gaussian smoothing), so county values are
heavily smoothed: neighbouring counties share most of their signal. Use them for regional (e.g. Sudd-wide) change,
not county contrasts. GRACE ended Jun 2017 and GRACE-FO began Jun 2018, so 2018-01..05 is empty; 2018 baseline is partial.

Outputs: data/processed/grace_county_monthly.csv, data/processed/meta/grace.json,
         docs/rasters/grace_tws/YYYY-MM.png (+ meta.json)
Usage:   python scripts/fetch_grace.py
"""
import glob
import json
import os
import subprocess
import sys
import zipfile

import numpy as np
import pandas as pd
import rasterio.features
import xarray as xr
from affine import Affine

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import overlay_utils as ou  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "raw", "grace", "_cache")  # gitignored
BASE = "https://isdc-data.gfz.de/grace-fo/GravIS"
TWS_URL = f"{BASE}/COST-G/Level-3/TWS/GRAVIS-3_COSTG_0200_TWS_GRID_GFZ_0001.nc"
G3P_URL = f"{BASE}/G3P/v1.12/G3P_v1.12.zip"
BBOX = dict(lat=(3.0, 13.0), lon=(23.0, 37.0))
FINE = 0.05  # degrees, for area-weighted county means of coarse cells
MONTHS = pd.period_range("2018-01", "2025-12", freq="M")
ou.CMAPS.setdefault("brbg", ["#8c510a", "#d8b365", "#f6e8c3", "#f5f5f5", "#c7eae5", "#5ab4ac", "#01665e"])


def fetch():
    os.makedirs(CACHE, exist_ok=True)
    tws = os.path.join(CACHE, "tws_costg.nc")
    if not os.path.exists(tws):
        subprocess.run(["curl", "-sSL", "--retry", "4", "-o", tws, TWS_URL], check=True)
    gw = glob.glob(os.path.join(CACHE, "G3P_v1.12", "GWSA", "*.nc"))
    if not gw:
        z = os.path.join(CACHE, "g3p.zip")
        subprocess.run(["curl", "-sSL", "--retry", "4", "-o", z, G3P_URL], check=True)
        with zipfile.ZipFile(z) as zf:
            zf.extractall(CACHE, [n for n in zf.namelist() if "/GWSA/" in n])
        os.remove(z)
        gw = glob.glob(os.path.join(CACHE, "G3P_v1.12", "GWSA", "*.nc"))
    return tws, gw[0]


def to_monthly(da):
    """Subset to the bbox, convert lon to -180..180, average to calendar months 2018-2025."""
    if float(da.lon.max()) > 180:
        da = da.assign_coords(lon=((da.lon + 180) % 360) - 180).sortby("lon")
    da = da.sortby("lat")
    da = da.sel(lat=slice(*BBOX["lat"]), lon=slice(*BBOX["lon"]))
    da = da.sel(time=slice("2018-01-01", "2025-12-31"))
    da = da.assign_coords(month=("time", pd.to_datetime(da.time.values).to_period("M").astype(str)))
    return da.groupby("month").mean("time")


def county_means(da, counties):
    """Area-weighted county means: nearest-upsample coarse cells to 0.05 deg and average inside each county."""
    lat = np.arange(BBOX["lat"][1] - FINE / 2, BBOX["lat"][0], -FINE)
    lon = np.arange(BBOX["lon"][0] + FINE / 2, BBOX["lon"][1], FINE)
    fine = da.interp(lat=lat, lon=lon, method="nearest")
    tr = Affine(FINE, 0, BBOX["lon"][0], 0, -FINE, BBOX["lat"][1])
    ids = rasterio.features.rasterize(((g, i + 1) for i, g in enumerate(counties.geometry)),
                                      out_shape=(len(lat), len(lon)), transform=tr, fill=0, dtype="int32")
    rows = []
    for m in fine.month.values:
        a = fine.sel(month=m).values
        for i, cid in enumerate(counties.district_id):
            v = a[(ids == i + 1) & np.isfinite(a)]
            if v.size:
                rows.append((cid, f"{m}-01", float(v.mean())))
    return rows, fine, tr


def main():
    tws_path, gw_path = fetch()
    counties = ou.counties()
    t = xr.open_dataset(tws_path)
    tws = to_monthly(t["tws"])            # cm
    tws_sd = to_monthly(t["std_tws"])     # cm
    g = xr.open_dataset(gw_path)
    gw = to_monthly(g["gwsa"]) / 10.0     # mm -> cm
    gw_sd = to_monthly(g["uncertainty"]) / 10.0

    out = []
    for var, da in [("grace_tws_cm", tws), ("grace_tws_unc_cm", tws_sd), ("g3p_gwsa_cm", gw), ("g3p_gwsa_unc_cm", gw_sd)]:
        rows, fine, tr = county_means(da, counties)
        out += [(c, d, var, v) for c, d, v in rows]
        if var == "grace_tws_cm":
            vals = fine.values[np.isfinite(fine.values)]
            lim = float(np.percentile(np.abs(vals), 98))
            for m in fine.month.values:
                meta = ou.write_overlay(fine.sel(month=m).values, tr, "EPSG:4326", "grace_tws", str(m), -lim, lim, "brbg",
                                        {"label": "Water storage anomaly (GRACE/GRACE-FO)", "units": "cm water",
                                         "native_resolution": "1° grid, ~300 km effective",
                                         "source": "GFZ GravIS COST-G GRACE/GRACE-FO Level-3 TWS"})
            meta["dates"] = [str(m) for m in fine.month.values]
            meta["notes"] = "Anomaly vs the 2002–2020 mean. Brown = less water stored than usual, teal = more. ~300 km blur."
            with open(os.path.join(ROOT, "docs", "rasters", "grace_tws", "meta.json"), "w") as fh:
                json.dump(meta, fh, indent=1)
    df = pd.DataFrame(out, columns=["county_id", "date", "variable", "value"])
    df["value"] = df["value"].round(3)
    df.to_csv(os.path.join(ROOT, "data", "processed", "grace_county_monthly.csv"), index=False)

    common = {"category": "environment", "group": "Water storage & groundwater (GRACE)", "temporal": "monthly",
              "index_ok": False, "aggregation": "area-weighted mean of grid cells inside the county (0.05° resampling)"}
    meta = [
        dict(common, id="grace_tws_cm", label="Total water storage anomaly (GRACE/GRACE-FO)", units="cm water",
             source="GFZ GravIS COST-G combined GRACE/GRACE-FO Level-3 TWS (DOI 10.5880/COST-G.GRAVIS_02_L3_TWS)",
             source_url="https://isdc-data.gfz.de/grace-fo/GravIS/COST-G/Level-3/TWS/", native_resolution="1° grid; ~300 km effective",
             higher_is="neutral", raster="grace_tws",
             notes="All water on and below the land surface (surface water, soil moisture, groundwater) relative to the 2002–2020 mean. "
                   "~300 km effective resolution: neighbouring counties share most of the signal, so read it regionally (e.g. the Sudd). "
                   "No data Jan–May 2018 (gap between GRACE and GRACE-FO), so the 2018 baseline is Jun–Dec only. "
                   "High values in the Sudd mostly reflect flood water, not groundwater."),
        dict(common, id="grace_tws_unc_cm", label="Water storage uncertainty (GRACE, 1σ)", units="cm water",
             source="GFZ GravIS COST-G Level-3 TWS (std_tws)", source_url="https://isdc-data.gfz.de/grace-fo/GravIS/",
             native_resolution="1° grid", higher_is="neutral", notes="One-standard-deviation uncertainty of the storage anomaly."),
        dict(common, id="g3p_gwsa_cm", label="Groundwater storage anomaly (G3P, from GRACE)", units="cm water",
             source="G3P v1.12 Global Gravity-based Groundwater Product, GFZ (DOI 10.5880/G3P.2024.001)",
             source_url="https://isdc-data.gfz.de/grace-fo/GravIS/G3P/v1.12/", native_resolution="0.5° grid; ~250–300 km effective",
             higher_is="better",
             notes="GRACE total storage minus modelled soil moisture, surface water, snow and glaciers, vs the 2002–2020 mean. "
                   "Ends Sep 2023 (latest G3P release). In the Sudd, errors in the surface-water term can leak into this series; "
                   "treat it as indicative. No data Jan–May 2018."),
        dict(common, id="g3p_gwsa_unc_cm", label="Groundwater anomaly uncertainty (G3P, 1σ)", units="cm water",
             source="G3P v1.12 (uncertainty)", source_url="https://isdc-data.gfz.de/grace-fo/GravIS/G3P/v1.12/",
             native_resolution="0.5° grid", higher_is="neutral", notes="One-standard-deviation uncertainty of the groundwater anomaly."),
    ]
    with open(os.path.join(ROOT, "data", "processed", "meta", "grace.json"), "w") as fh:
        json.dump(meta, fh, indent=1)
    os.makedirs(os.path.join(ROOT, "data", "raw", "grace"), exist_ok=True)
    with open(os.path.join(ROOT, "data", "raw", "grace", "SOURCE.md"), "w") as fh:
        fh.write(f"# GRACE / GRACE-FO water storage (GFZ GravIS, open access, no login)\n\n"
                 f"- TWSA: {TWS_URL}\n  COST-G combined GRACE/GRACE-FO Level-3, 1°, monthly 2002-04..2026-07 (file dated 2026-10-04), cm EWH.\n"
                 f"- GWSA: {G3P_URL}\n  G3P v1.12, 0.5°, monthly 2002-04..2023-09, mm (converted to cm).\n"
                 f"- Downloaded files are cached in `_cache/` (gitignored, ~0.9 GB); `python scripts/fetch_grace.py` re-downloads.\n"
                 f"- Cite: Boergens, Dobslaw, Dill (GFZ) COST-G GravIS L3 TWS; Güntner et al. (2024) G3P v1.12, GFZ Data Services.\n")
    print(df.groupby("variable").agg(n=("value", "size"), months=("date", "nunique"), lo=("value", "min"), hi=("value", "max")))


if __name__ == "__main__":
    main()
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from trend_stats import write_trends
    write_trends("grace")
