"""Sentinel-5P TROPOMI (L2, Microsoft Planetary Computer) -> monthly county means for South Sudan.

Products / variables
  aer-ai : aerosol_index_354_388 (UV absorbing aerosol index; dust & smoke), qa_value > 0.8 -> s5p_aerosol_index
  no2    : nitrogendioxide_tropospheric_column (mol m-2), qa_value > 0.75               -> s5p_no2 (umol m-2)
  co     : carbonmonoxide_total_column (mol m-2), qa_value > 0.5                          -> s5p_co (mmol m-2)

L2 swaths are large (100-450 MB). To stay within time/disk limits we SAMPLE N_ORBITS orbits per month
(evenly spaced in time, orbits crossing central South Sudan) and read only the scanlines over South
Sudan via HTTP range requests (h5py + fsspec). Valid pixels are binned onto a 0.05 deg grid; county
value = mean of all valid pixel observations whose centre falls in the county.
Monthly 0.05 deg means are also rendered as overlays (docs/rasters/s5p_aerosol_index, s5p_no2).

Usage: python scripts/s5p_pipeline.py [N_ORBITS]
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import fsspec
import h5py
import planetary_computer as pc
from rasterio import features
from rasterio.transform import from_origin
from rasterio.warp import Resampling

sys.path.insert(0, str(Path(__file__).parent))
import hazards_common as hc

N_ORBITS = int(sys.argv[1]) if len(sys.argv) > 1 else 6
RES = 0.05
X0, Y1 = 24.0, 12.35
NX, NY = int((36.1 - X0) / RES), int((Y1 - 3.4) / RES)
GT = from_origin(X0, Y1, RES, RES)
CACHE = hc.REPO / "data" / "raw" / "s5p" / "monthly_grids"
OUT = hc.PROC / "s5p_county_monthly.csv"

PRODUCTS = {
    "aer-ai": dict(var="aerosol_index_354_388", qa=0.8, scale=1.0, vid="s5p_aerosol_index"),
    "no2": dict(var="nitrogendioxide_tropospheric_column", qa=0.75, scale=1e6, vid="s5p_no2"),
    "co": dict(var="carbonmonoxide_total_column", qa=0.5, scale=1e3, vid="s5p_co"),
}


def pick_orbits(product, month):
    last = pd.Timestamp(month + "-01").days_in_month
    items = hc.search("sentinel-5p-l2-netcdf", f"{month}-01/{month}-{last:02d}", bbox=[29.5, 6.5, 31.5, 8.5],
                      query={"s5p:product_name": {"eq": product}})
    by_orbit = {}
    rank = {"RPRO": 0, "OFFL": 1, "NRTI": 2}
    for it in items:
        o = it.properties.get("sat:absolute_orbit")
        k = (rank.get(it.properties.get("s5p:processing_mode"), 3), it.properties.get("s5p:collection_identifier", ""))
        if o not in by_orbit or k < by_orbit[o][0]:
            by_orbit[o] = (k, it)
    its = sorted((v[1] for v in by_orbit.values()), key=lambda i: i.properties["start_datetime"])
    if len(its) > N_ORBITS:
        idx = np.linspace(0, len(its) - 1, N_ORBITS).round().astype(int)
        its = [its[i] for i in sorted(set(idx))]
    return its


def read_orbit(item, cfg):
    href = pc.sign(list(item.assets.values())[0].href.split("?")[0])
    for attempt in range(3):
        try:
            fs = fsspec.filesystem("https")
            with fs.open(href, block_size=2 * 1024 * 1024, cache_type="blockcache") as f, h5py.File(f, "r") as h:
                P = h["PRODUCT"]
                lat = P["latitude"][0]
                rows = np.where(((lat > 3.3) & (lat < 12.4)).any(1))[0]
                if rows.size == 0:
                    return None
                r0, r1 = rows.min(), rows.max() + 1
                lat = lat[r0:r1]
                lon = P["longitude"][0, r0:r1]
                val = P[cfg["var"]][0, r0:r1].astype("float64")
                qa = P["qa_value"][0, r0:r1]
                qa = qa * 0.01 if qa.dtype.kind in "ui" else qa
            ok = (qa > cfg["qa"]) & (np.abs(val) < 1e30) & (lon >= X0) & (lon < X0 + NX * RES) & (lat > Y1 - NY * RES) & (lat <= Y1)
            ix = ((lon[ok] - X0) / RES).astype(int); iy = ((Y1 - lat[ok]) / RES).astype(int)
            return iy * NX + ix, val[ok] * cfg["scale"]
        except Exception as e:  # noqa
            err = e
            time.sleep(5)
    print("FAILED", item.id, err, flush=True)
    return None


def month_grid(product, month):
    cf = CACHE / f"{product}_{month}.npz"
    if cf.exists():
        z = np.load(cf)
        return z["s"], z["n"], int(z["norb"])
    its = pick_orbits(product, month)
    s = np.zeros(NX * NY); n = np.zeros(NX * NY)
    norb = 0
    if its:
        with ThreadPoolExecutor(6) as ex:
            res = list(ex.map(lambda it: read_orbit(it, PRODUCTS[product]), its))
        for r in res:
            if r is None:
                continue
            norb += 1
            idx, v = r
            s += np.bincount(idx, weights=v, minlength=NX * NY)
            n += np.bincount(idx, minlength=NX * NY)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cf, s=s, n=n, norb=norb)
    return s, n, norb


RSCALE = {"s5p_aerosol_index": (-2.0, 2.0, "RdYlBu_r", "unitless (UV aerosol index)"),
          "s5p_no2": (0.0, 40.0, "magma_r", "umol/m2 tropospheric NO2"),
          "s5p_co": (25.0, 45.0, "YlOrBr", "mmol/m2 total CO")}


def main():
    g = hc.counties()
    lab = features.rasterize(zip(g.geometry, g.label), out_shape=(NY, NX), transform=GT, fill=0, dtype="int32").ravel()
    ids = hc.county_ids()
    canvas = hc.Canvas()
    rows, log = [], []
    dates = {p: [] for p in PRODUCTS}
    for m in hc.months("2018-04-01"):
        for p, cfg in PRODUCTS.items():
            t0 = time.time()
            s, n, norb = month_grid(p, m)
            log.append((m, p, norb))
            if norb == 0:
                continue
            cs = np.bincount(lab, weights=s, minlength=len(ids) + 1)
            cn = np.bincount(lab, weights=n, minlength=len(ids) + 1)
            for i, cid in enumerate(ids, start=1):
                if cn[i] >= 5:
                    rows.append((cid, m + "-01", cfg["vid"], round(cs[i] / cn[i], 4)))
            grid = np.where(n > 0, s / np.maximum(n, 1), np.nan).reshape(NY, NX).astype("float32")
            vmin, vmax, cmap, _ = RSCALE[cfg["vid"]]
            img = canvas.add(canvas.new(), grid, GT, "EPSG:4326", Resampling.bilinear)
            canvas.save_png(img, hc.RASTERS / cfg["vid"] / f"{m}.png", vmin, vmax, cmap, nodata_rgba=(150, 150, 150, 90))
            dates[p].append(m)
            print(f"s5p {m} {p} orbits={norb} valid_px={int(n.sum())} {time.time()-t0:.0f}s", flush=True)
        pd.DataFrame(rows, columns=["county_id", "date", "variable", "value"]).to_csv(OUT, index=False)
    pd.DataFrame(log, columns=["month", "product", "orbits_used"]).to_csv(CACHE.parent / "orbits_used.csv", index=False)
    df = pd.DataFrame(rows, columns=["county_id", "date", "variable", "value"]).sort_values(["variable", "county_id", "date"])
    df.to_csv(OUT, index=False)
    for p, cfg in PRODUCTS.items():
        vmin, vmax, cmap, units = RSCALE[cfg["vid"]]
        hc.write_raster_meta(cfg["vid"], f"Sentinel-5P {cfg['vid'][4:]} (monthly, sampled orbits)", units, canvas,
                             vmin, vmax, cmap, "~5.5x3.5 km (TROPOMI), gridded 0.05 deg", dates[p],
                             "Sentinel-5P TROPOMI L2 via Microsoft Planetary Computer",
                             notes=f"Mean of up to {N_ORBITS} sampled orbits per month; grey = no valid retrieval.")
    common = dict(category="environment", group="Air quality", source="Copernicus Sentinel-5P TROPOMI L2 (OFFL/RPRO) "
                  "via Microsoft Planetary Computer", source_url="https://planetarycomputer.microsoft.com/dataset/sentinel-5p-l2-netcdf",
                  native_resolution="5.5 x 3.5 km (7 x 3.5 km before Aug 2019)", temporal="monthly")
    samp = (f"Monthly value = mean of all quality-filtered pixels in county from {N_ORBITS} evenly spaced sampled orbits "
            "(not all ~45 overpasses) - noisy, cloud-affected in wet season. Starts 2018-04/07 (S5P operational "
            "data begins mid-2018), so the 2018 baseline is partial.")
    hc.write_meta("s5p", [
        dict(id="s5p_aerosol_index", label="UV aerosol index (dust/smoke)", units="unitless",
             aggregation="mean of pixels with qa_value>0.8", higher_is="worse", index_ok=False, raster="s5p_aerosol_index",
             notes="Positive = absorbing aerosol (Saharan dust, biomass-burning smoke); can be negative. " + samp, **common),
        dict(id="s5p_no2", label="Tropospheric NO2", units="umol/m2", aggregation="mean of pixels with qa_value>0.75",
             higher_is="worse", index_ok=True, raster="s5p_no2",
             notes="Near detection limit away from towns/fires; dry-season peaks from biomass burning. " + samp, **common),
        dict(id="s5p_co", label="Carbon monoxide total column", units="mmol/m2", aggregation="mean of pixels with qa_value>0.5",
             higher_is="worse", index_ok=True, raster="s5p_co",
             notes="Dominated by biomass burning in the dry season. " + samp, **common),
    ])
    print("wrote", OUT, len(df))


if __name__ == "__main__":
    main()
