#!/usr/bin/env python
"""Map VALUE rasters of the curated climate variables as a continuous red -> white -> green gradient, rendered from the
raw grids (the same grids the county series are averaged from), plus new rasters for climate variables that had none.

Colour: continuous ramp #b2182b (low) -> #ffffff (middle) -> #1b7837 (high) between the layer's 2nd and 98th
percentile over all dates and all in-country pixels (log10 for VIIRS fire counts). 61 evenly spaced shades in a palette
PNG (EPSG:3857, clipped to the country, black hatching = no valid data). Coarse products are averaged back onto their
native cells (GLDAS / GRACE-DA / IMERG / SMAP) and bilinearly interpolated to the display pixels so cells blend;
1 km products are averaged into the display pixels. meta.json: "continuous": true, "palette": "rwg-continuous",
"colors": 3 anchors, "vmin"/"vmax" (p2/p98), "bins": null.

Layers (key -> grid):
  existing  maiac_aod, modis_et_monthly, modis_lst_day, modis_ndvi, smap_sm_rootzone, gldas_gws, gracedm_gws, viirs_fire,
            flood_s1                     (re-rendered; label/source/notes kept from meta.json)
  new       imerg_precip  (precip_mm, GPM IMERG V07 0.1 deg, scripts/gee_climate_grids.py)
            fldas_tair    (tair_c, NASA FLDAS Noah 0.1 deg, scripts/gee_climate_grids.py)
            lulc_built, lulc_crop, lulc_flooded_veg (Impact Observatory annual 10 m LULC, class share per 0.01 deg cell,
                          scripts/landcover_grids.py), one image per year (date YYYY-07)
            soil_clay     (data/raw/ss_clay_soilgrids_0_30.tif, SoilGrids 2.0 0-30 cm clay at ~1 km; date "static")
            elevation     (data/raw/ss_nasadem_elev_1km_fast.tif, ~1 km; date "static")
Not re-rendered: sudd_inundation (a categorical class map: dry / flooded vegetation / open water, not a continuous value).

Usage: python scripts/continuous_rasters.py [--width N] [--levels N] [key ...]
Environment: same grid locations as scripts/raster_trends.py.
"""
import argparse
import glob
import json
import os
import sys
import time

import numpy as np
import rasterio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import overlay_utils as ou  # noqa: E402
import raster_trends as rt  # noqa: E402

RASTERS = ou.RASTERS
MONTHS = [(y, m) for y in range(2018, 2026) for m in range(1, 13)]
G25 = (0.25, (-180.0, 90.0))


def npy_dates(d):
    return [(int(os.path.basename(p)[:4]), int(os.path.basename(p)[5:7]))
            for p in sorted(glob.glob(os.path.join(d, "????-??.npy"))) if "2018-01" <= os.path.basename(p)[:7] <= "2025-12"]


def npy_src(d):
    get = rt.npy_monthly(d)
    return lambda: ([(f"{y}-{m:02d}", (lambda y=y, m=m: get(y, m))) for y, m in npy_dates(d)], rt.GRID001, "EPSG:4326")


def viirs_src():
    get, tf = rt.load_viirs()
    return [(f"{y}-{m:02d}", (lambda y=y, m=m: get(y, m))) for y, m in MONTHS], tf, "EPSG:4326"


def flood_src():
    """Sentinel-1 FLOODED share (class 1 = flooded vegetation/land, not permanent open water) of the known (observed or
    gap-filled) area of each 0.012 deg cell = exactly the definition of the county series flood_s1_flood_pct."""
    import flood_s1_pipeline as fs
    from rasterio.transform import from_origin
    tr, (h, w), crs = fs.grid()
    f = 3
    H, W = h // f, w // f
    tf = from_origin(tr.c, tr.f, tr.a * f, -tr.e * f)
    cache = {}
    for m, cls, _obs in fs.water_series():
        c = cls[:H * f, :W * f].reshape(H, f, W, f)
        known = (c >= 0).mean(axis=(1, 3))
        fl = (c == 1).mean(axis=(1, 3))
        with np.errstate(invalid="ignore", divide="ignore"):
            cache[m] = np.where(known >= 0.5, 100 * fl / np.maximum(known, 1e-9), np.nan).astype("float32")
    return [(m, (lambda m=m: cache[m])) for m in sorted(cache)], tf, crs


def lulc_src(var):
    d = os.path.join(rt.LULC, var)
    files = sorted(glob.glob(os.path.join(d, "????.npy")))
    return lambda: ([(f"{os.path.basename(p)[:4]}-07", (lambda p=p: np.load(p))) for p in files], rt.GRID001, "EPSG:4326")


def tif_src(path):
    def run():
        with rasterio.open(os.path.join(ou.ROOT, path)) as s:
            a = s.read(1, masked=True).astype("float32").filled(np.nan)
            tf, crs = s.transform, s.crs
        a[(a <= 0) | ~np.isfinite(a)] = np.nan
        return [("static", lambda: a)], tf, crs
    return run


CLIM_NOTE = " Map: continuous colour from the 2nd (red) to the 98th (green) percentile of all months; white = middle."
LAYERS = {
    "maiac_aod": dict(src=npy_src(os.path.join(rt.MAIAC, "maiac_aod_055"))),
    "modis_et_monthly": dict(src=npy_src(os.path.join(rt.APPEEARS, "modis_et_monthly_mm"))),
    "modis_lst_day": dict(src=npy_src(os.path.join(rt.MODIS_PC, "modis_lst_day_c"))),
    "modis_ndvi": dict(src=npy_src(os.path.join(rt.MODIS_PC, "modis_ndvi"))),
    "smap_sm_rootzone": dict(src=npy_src(os.path.join(rt.APPEEARS, "smap_sm_rootzone")), native=(0.08, (23.4, 12.3)),
                             meta=dict(source="SMAP L4 SPL4SMGP v008 (3-hourly, 9 km) via Google Earth Engine "
                                              "(NASA/SMAP/SPL4SMGP/008)")),
    "gldas_gws": dict(src=npy_src(os.path.join(rt.GLDAS, "gldas_gws_anom_cm")), native=G25,
                      meta=dict(native_resolution="0.25° (~28 km) GLDAS grid, bilinear smoothing between cell centres")),
    "gracedm_gws": dict(src=npy_src(os.path.join(rt.GRACEDM, "gracedm_gws_pctl")), native=G25,
                        meta=dict(native_resolution="0.25° (~28 km) model grid, bilinear smoothing between cell centres")),
    # fire detections are point counts binned per 0.05 deg cell: no interpolation (it would invent low-count rings)
    "viirs_fire": dict(src=viirs_src, log=True, zero_transparent=0.5, fixed_vmin=1.0, hatch=False, upsample="nearest"),
    "flood_s1": dict(src=flood_src, zero_transparent=1e-6,
                     meta=dict(units="% of known area flooded", label="Flooded area (monthly, Sentinel-1 SAR)",
                               notes=("Share of each ~1.3 km cell classified as flooded (vegetation/land under water; "
                                      "permanent open water excluded), as % of the observed (or gap-filled) area: the same "
                                      "definition as the county series flood_s1_flood_pct. Transparent = no flooding; "
                                      "black hatching = no Sentinel-1 acquisition within 2 months."))),
    "imerg_precip": dict(src=npy_src(os.path.join(rt.GEE_CLIMATE, "precip_mm")), native=(0.1, (-180.0, 90.0)), new=dict(
        label="Rainfall (NASA GPM IMERG V07, monthly)", units="mm/month",
        native_resolution="0.1° (~11 km), bilinear smoothing between cell centres",
        source="NASA GPM IMERG V07 Final monthly (GPM_3IMERGM) via Google Earth Engine (NASA/GPM_L3/IMERG_MONTHLY_V07)",
        notes="Monthly rainfall total = IMERG mean rate (mm/hr) x 24 x days. The county series precip_mm is the mean "
              "of these same 0.1° cells inside each county." + CLIM_NOTE)),
    "fldas_tair": dict(src=npy_src(os.path.join(rt.GEE_CLIMATE, "tair_c")), native=(0.1, (-180.0, 90.0)), new=dict(
        label="Air temperature at 2 m (NASA FLDAS Noah, monthly mean)", units="°C",
        native_resolution="0.1° (~11 km), bilinear smoothing between cell centres",
        source="NASA FLDAS Noah monthly 0.1° (FLDAS_NOAH01_C_GL_M, Tair_f_tavg; MERRA-2 temperature downscaled) via "
               "Google Earth Engine (NASA/FLDAS/NOAH01/C/GL/M/V001)",
        notes="Monthly mean near-surface air temperature. The county series tair_c is the mean of these same 0.1° cells "
              "inside each county." + CLIM_NOTE)),
    "lulc_built": dict(src=lulc_src("lulc_built_pct"), zero_transparent=0.0, fixed_vmin=0.0, new=dict(
        label="Built-up land (share of each ~1 km cell, Impact Observatory 10 m land cover)", units="% of cell",
        temporal="annual")),
    "lulc_crop": dict(src=lulc_src("lulc_crop_pct"), zero_transparent=0.0, fixed_vmin=0.0, new=dict(
        label="Cropland (share of each ~1 km cell, Impact Observatory 10 m land cover)", units="% of cell",
        temporal="annual")),
    "lulc_flooded_veg": dict(src=lulc_src("lulc_flooded_veg_pct"), zero_transparent=0.0, fixed_vmin=0.0, new=dict(
        label="Flooded vegetation (share of each ~1 km cell, Impact Observatory 10 m land cover)", units="% of cell",
        temporal="annual")),
    "soil_clay": dict(src=tif_src("data/raw/ss_clay_soilgrids_0_30.tif"), new=dict(
        label="Clay in topsoil, 0-30 cm (ISRIC SoilGrids 2.0)", units="% (mass)", temporal="static",
        native_resolution="250 m SoilGrids, stored at ~1 km (0.009°) in data/raw/ss_clay_soilgrids_0_30.tif",
        source="ISRIC SoilGrids 2.0, 0-30 cm depth-weighted clay (data/raw/ss_clay_soilgrids_0_30.tif)",
        notes="The county series soil_clay_0_30cm is the county mean of the same SoilGrids 0-30 cm clay at ~1 km "
              "(re-averaging this file reproduces it: r = 0.9998)." + " Map: continuous colour from the 2nd (red) to "
              "the 98th (green) percentile; white = middle.")),
    "elevation": dict(src=tif_src("data/raw/ss_nasadem_elev_1km_fast.tif"), new=dict(
        label="Elevation (1 km)", units="m", temporal="static",
        native_resolution="~1 km (0.009°) DEM (data/raw/ss_nasadem_elev_1km_fast.tif)",
        source="NASADEM / Copernicus DEM elevation at ~1 km (data/raw/ss_nasadem_elev_1km_fast.tif)",
        notes="The county series elevation_mean (Copernicus GLO-90 read at ~370 m) is reproduced by averaging this "
              "1 km grid over each county (r = 0.99999, mean difference 0.06 m)." + " Map: continuous colour from the "
              "2nd (red) to the 98th (green) percentile; white = middle.")),
}
LULC_NOTE = ("Share (%) of the 10 m Impact Observatory land-cover map's {cls} class in each 0.01° (~1 km) cell, from the "
             "same 1-in-64 nearest-neighbour sample (~80 m) as the county series {var} (the county value is the "
             "sample-weighted mean of these cells; r > 0.9998). One map per year 2017-2023 (the latest published); "
             "later months show 2023." + CLIM_NOTE.replace("all months", "all years"))
for k, cls, var in (("lulc_built", "built area", "lulc_built_pct"), ("lulc_crop", "crops", "lulc_crop_pct"),
                    ("lulc_flooded_veg", "flooded vegetation", "lulc_flooded_veg_pct")):
    LAYERS[k]["new"].update(source="Esri / Impact Observatory 10 m Annual Land Use Land Cover (io-lulc-annual-v02) via "
                                   "Microsoft Planetary Computer",
                            native_resolution="10 m map, sampled at ~80 m, shown as class share per 0.01° (~1 km) cell",
                            notes=LULC_NOTE.format(cls=cls, var=var))


def render(key, L, width, levels):
    t0 = time.time()
    items, tf, crs = L["src"]()
    if not items:
        print(key, "no grids", flush=True)
        return
    mask = rt.country_mask(items[0][1]().shape, tf, crs)
    vals, arrs = [], []
    for d, get in items:
        a = get()
        if a is None:
            continue
        a = a.astype("float32")
        a[~mask] = np.nan
        if L.get("native"):
            a, rtf = ou.to_native(a, *L["native"], src_transform=tf)
        else:
            rtf = tf
        arrs.append((d, a))
        v = a[np.isfinite(a)]
        if L.get("zero_transparent") is not None:
            v = v[v > L["zero_transparent"]]
        if L.get("log"):
            v = np.log10(v[v > 0])
        if v.size:
            vals.append(np.random.default_rng(0).choice(v, min(v.size, 200000), replace=False))
    allv = np.concatenate(vals)
    p2, p98 = (float(x) for x in np.percentile(allv, [2, 98]))
    if L.get("log"):
        p2, p98 = 10 ** p2, 10 ** p98
    vmin = L.get("fixed_vmin", p2)
    vmin, vmax = float(f"{vmin:.3g}"), float(f"{p98:.3g}")
    od = os.path.join(RASTERS, key)
    mp = os.path.join(od, "meta.json")
    meta = json.load(open(mp)) if os.path.exists(mp) and not L.get("new") else {"key": key}
    meta.update(L.get("new", {}))
    meta.update(L.get("meta", {}))
    for p in glob.glob(os.path.join(od, "*.png")):
        os.remove(p)
    dates, info = [], None
    for d, a in arrs:
        info = ou.write_overlay_continuous(a, rtf, crs, key, d, vmin, vmax, ou.RWG, log=bool(L.get("log")),
                                           max_px=width, min_px=min(width, 700), levels=levels,
                                           hatch=L.get("hatch", True), transparent_below=L.get("zero_transparent"),
                                           upsample=L.get("upsample", "bilinear"))
        dates.append(d)
    ou.continuous_meta(meta, vmin, vmax, ou.RWG, "2nd-98th percentile of all dates" +
                       (", log10 scale (1 detection = red end)" if L.get("log") else ""))
    meta.update(bounds=info["bounds"], width=info["width"], height=info["height"], dates=dates,
                scale="log10" if L.get("log") else "linear",
                smoothing=("averaged onto the native cells, then bilinear interpolation to display pixels"
                           if L.get("native") else "none (each 0.05° cell drawn as a block)" if key == "viirs_fire"
                           else "average of the grid cells in each display pixel"))
    if L.get("zero_transparent") is not None:
        meta["transparent"] = "zero / none (and the colour scale starts at the lowest non-zero values)"
    with open(mp, "w") as f:
        json.dump(meta, f, indent=1, ensure_ascii=False)
    sz = sum(os.path.getsize(p) for p in glob.glob(os.path.join(od, "*.png")))
    print(f"{key}: {len(dates)} images {info['width']}x{info['height']} vmin={vmin:g} vmax={vmax:g} "
          f"{sz / 1e6:.2f} MB {time.time() - t0:.0f}s", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("keys", nargs="*")
    ap.add_argument("--width", type=int, default=900)
    ap.add_argument("--levels", type=int, default=61)
    a = ap.parse_args()
    for k, L in LAYERS.items():
        if a.keys and k not in a.keys:
            continue
        render(k, L, L.get("width", a.width), L.get("levels", a.levels))


if __name__ == "__main__":
    main()
