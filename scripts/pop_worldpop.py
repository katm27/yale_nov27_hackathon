"""WorldPop Global2 (R2025A, 2015-2030) constrained 1 km population -> county pop_total 2018-2025
+ population density overlay docs/rasters/population/2020.png"""
import os
import sys
import numpy as np
import pandas as pd
import rasterio
from rasterstats import zonal_stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from overlay_utils import ROOT, counties, write_long, write_meta, write_overlay

RAW = os.path.join(ROOT, "data", "raw", "worldpop")
URL = ("https://data.worldpop.org/GIS/Population/Global_2015_2030/R2025A/{y}/SSD/v1/1km_ua/constrained/"
       "ssd_pop_{y}_CN_1km_R2025A_UA_v1.tif")
URL_SDN = URL.replace("/SSD/", "/SDN/").replace("ssd_pop", "sdn_pop")
YEARS = range(2018, 2026)
# Abyei Special Administrative Area is not covered by the SSD raster (WorldPop puts it in Sudan's grid)
SDN_COUNTIES = ["SS0001"]


def fetch():
    import requests
    os.makedirs(RAW, exist_ok=True)
    for y in YEARS:
      for u in (URL, URL_SDN):
        p = os.path.join(RAW, os.path.basename(u.format(y=y)))
        if not os.path.exists(p):
            r = requests.get(u.format(y=y), timeout=300)
            r.raise_for_status()
            open(p, "wb").write(r.content)
    with open(os.path.join(RAW, "SOURCE.md"), "w") as f:
        f.write("WorldPop Global2 R2025A constrained 1km population (UN-adjusted), 2018-2025.\n"
                "URL pattern: " + URL + "\nSudan grid (for Abyei): " + URL_SDN + "\nLicense: CC-BY 4.0\n")


def main():
    fetch()
    c = counties()
    rows = []
    for y in YEARS:
        p = os.path.join(RAW, os.path.basename(URL.format(y=y)))
        zs = zonal_stats(c, p, stats=["sum"], all_touched=False)
        ps = os.path.join(RAW, os.path.basename(URL_SDN.format(y=y)))
        cs = c[c.district_id.isin(SDN_COUNTIES)]
        zsd = dict(zip(cs.district_id, zonal_stats(cs, ps, stats=["sum"])))
        for cid, z in zip(c.district_id, zs):
            if cid in zsd:
                z = {"sum": (z["sum"] or 0) + (zsd[cid]["sum"] or 0)}
            rows.append((cid, f"{y}-07-01", "pop_total", float(z["sum"] or 0)))
    df = write_long("worldpop", pd.DataFrame(rows, columns=["county_id", "date", "variable", "value"]))
    print(df.groupby("date").value.sum())
    write_meta("worldpop", [{
        "id": "pop_total", "label": "Population (WorldPop)", "category": "human", "group": "Population",
        "units": "people", "source": "WorldPop Global2 R2025A constrained 1 km (UN-adjusted), 2015-2030 series",
        "source_url": "https://hub.worldpop.org/project/categories?id=3", "native_resolution": "1 km",
        "temporal": "annual", "aggregation": "sum of pixels within county", "higher_is": "neutral",
        "index_ok": True, "raster": "population",
        "notes": "Modelled estimates; 2018-2025 from the R2025A 2015-2030 projection product. Denominator for per-capita rates. "
                 "Abyei summed from the Sudan (SDN) grid since the SSD grid excludes it. Does not capture conflict displacement dynamics well."}])
    # density overlay (people per km2 ~ people per 1km pixel; adjust for latitude)
    p = os.path.join(RAW, os.path.basename(URL.format(y=2020)))
    with rasterio.open(p) as src:
        a = src.read(1).astype("float32")
        nod = src.nodata
        mask = (a == nod) if nod is not None else np.zeros_like(a, bool)
        a[mask] = np.nan
        # pixel area km2 at row latitude
        rows_lat = src.transform.f + src.transform.e * (np.arange(a.shape[0]) + 0.5)
        px_km2 = (abs(src.transform.a) * 111.32 * np.cos(np.radians(rows_lat)))[:, None] * abs(src.transform.e) * 110.57
        dens = a / px_km2
        dens[np.isnan(dens)] = 0  # constrained product: unsettled = 0 people
        write_overlay(dens, src.transform, src.crs, "population", "2020", 1, 2000, "magma_r",
                      {"label": "Population density 2020", "units": "people / km²", "native_resolution": "1 km",
                       "dates": ["2020"], "source": "WorldPop Global2 R2025A constrained 1 km"},
                      log=True, nodata_mask=(dens < 0.5))


if __name__ == "__main__":
    main()
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from trend_stats import write_trends
    write_trends("worldpop")  # Mann-Kendall + Sen's slope (scripts/trend_stats.py)
