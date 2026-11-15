"""Flood exposure of people and oil infrastructure per county-month (contamination-pathway proxies), from the
Sentinel-1 flood layer (flood_s1_pipeline.py: flooded class = inundation beyond the dry-season reference).

These are EXPOSURE indicators, not measured contamination: no open dataset measures water quality (faecal
bacteria, hydrocarbons, salinity) in South Sudan county by month. They identify where flood water overlaps with
the two documented contamination sources:
  flood_population_exposed      people (WorldPop R2025A constrained 1 km, UN-adjusted, year-matched) living in
                                cells that are flooded, weighted by the flooded fraction of each 1 km cell.
                                Pathway: flooded pit latrines / open defecation (ISNA: ~50% of households practise
                                open defecation) -> faecal contamination of drinking water (cholera, AWD, hepatitis E).
  flood_population_exposed_pct  same, % of county population.
  flood_oilfield_exposure_km2   flooded area within 5 km of an oil well or oil-field centre (docs/data/points_oil.geojson,
                                OSM wells + GEM GOGET field centres, Unity / Ruweng / Upper Nile). Pathway: produced-water
                                pits and spills spread by flood water (documented around Thar Jath, Unity and Paloich).
  flood_oil_wells_flooded       number of oil wells/fields whose location (440 m cell) or any cell within 1 km is flooded.
Usage: python scripts/flood_exposure.py   (after flood_s1_pipeline.py)
"""
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio import features
from rasterio.warp import reproject, Resampling
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).parent))
import hazards_common as hc
import flood_s1_pipeline as f

SRC = "flood_exposure"
OUT = hc.PROC / f"{SRC}_county_monthly.csv"
BUF_KM = 5.0


def main():
    gtr, gs, gc = f.grid()
    lab = hc.labels_for(gc, gtr, gs)
    area = f.pixel_area_km2(gtr, gs)
    ids = hc.county_ids()
    pass
    # oil zone
    oil = gpd.read_file(hc.REPO / "docs/data/points_oil.geojson").to_crs(4326)
    zone = oil.to_crs(32636).buffer(BUF_KM * 1000).to_crs(4326)
    oz = features.rasterize(((g, 1) for g in zone), out_shape=gs, transform=gtr, fill=0, dtype="uint8").astype(bool)
    rows_c, cols_c = rasterio.transform.rowcol(gtr, oil.geometry.x.values, oil.geometry.y.values)
    wells = [(r, c, cid) for r, c, cid in zip(rows_c, cols_c, oil.county_id)]
    print("oil zone km2:", round(float((area * oz)[lab > 0].sum())), "points", len(oil))
    # population grids by year, aligned to the 1 km WorldPop grid
    pop = {}
    for y in range(2018, 2026):
        p = hc.REPO / f"data/raw/worldpop/ssd_pop_{y}_CN_1km_R2025A_UA_v1.tif"
        with rasterio.open(p) as s:
            a = s.read(1).astype("float32"); a[(a < 0) | ~np.isfinite(a)] = 0
            pop[y] = (a, s.transform, s.crs)
    ptr, pcrs = pop[2018][1], pop[2018][2]
    plab = hc.labels_for(pcrs, ptr, pop[2018][0].shape)
    rows = []
    for m, w, obs in f.water_series():
        flood = (w == 1).astype("float32")
        flood[w < 0] = np.nan
        a, _, _ = pop[int(m[:4])]
        frac = np.full(a.shape, np.nan, "float32")
        reproject(flood, frac, src_transform=gtr, src_crs=gc, src_nodata=np.nan, dst_transform=ptr, dst_crs=pcrs,
                  dst_nodata=np.nan, resampling=Resampling.average)
        known = np.isfinite(frac)
        exp = hc.bincount(plab, np.where(known, a * frac, 0)); ptot = hc.bincount(plab, a)
        pknown = hc.bincount(plab, np.where(known, a, 0))
        fz = hc.bincount(lab, area * ((w == 1) & oz)); kz = hc.bincount(lab, area * ((w >= 0) & oz))
        tz = hc.bincount(lab, area * oz)
        wet = ndimage.binary_dilation(w == 1, iterations=2)
        nw = {}
        for r, c, cid in wells:
            if 0 <= r < gs[0] and 0 <= c < gs[1] and w[r, c] >= 0:
                nw[cid] = nw.get(cid, 0) + int(wet[r, c])
        for i, cid in enumerate(ids, start=1):
            if ptot[i] > 0 and pknown[i] >= 0.5 * ptot[i]:
                e = exp[i] * ptot[i] / pknown[i]
                rows.append((cid, m + "-01", "flood_population_exposed", round(float(e))))
                rows.append((cid, m + "-01", "flood_population_exposed_pct", round(float(100 * e / ptot[i]), 3)))
            if tz[i] > 0 and kz[i] >= 0.5 * tz[i]:
                rows.append((cid, m + "-01", "flood_oilfield_exposure_km2", round(float(fz[i] * tz[i] / kz[i]), 2)))
            if cid in set(oil.county_id):
                if cid in nw:
                    rows.append((cid, m + "-01", "flood_oil_wells_flooded", float(nw[cid])))
        print(m, "pop exposed", round(float(exp[1:].sum())), "oil-zone flood km2", round(float(fz[1:].sum())), flush=True)
    df = pd.DataFrame(rows, columns=["county_id", "date", "variable", "value"]).sort_values(["variable", "county_id", "date"])
    df.to_csv(OUT, index=False)
    src = ("Derived: Sentinel-1 flood (flood_s1_pipeline.py) x WorldPop R2025A 1 km / oil wells & fields "
           "(OSM, GEM GOGET); scripts/flood_exposure.py")
    common = dict(category="environment", group="Water & flooding", source=src,
                  source_url="https://planetarycomputer.microsoft.com/dataset/sentinel-1-rtc", temporal="monthly",
                  native_resolution="~440 m flood x 1 km population", raster=None)
    caveat = (" Exposure, not measured contamination: no open county-level water-quality data exist for South Sudan. "
              "Flood = Sentinel-1 flooded class (VV-VH rise >3 dB over the March reference; reliable Jul-Nov, under-detects receding Dec-Jun water).")
    hc.write_meta(SRC, [
        dict(id="flood_population_exposed", label="People living in flooded areas", units="people",
             aggregation="sum over 1 km cells of population x flooded fraction (scaled up if <100% of the county observed)",
             higher_is="worse", index_ok=False, notes="Faecal-contamination exposure: about half of households practise "
             "open defecation (ISNA 2022-24) and pit latrines flood, so people in flooded cells are exposed to "
             "contaminated water (cholera, AWD, hepatitis E). WorldPop places people on their usual settlements; "
             "displaced people and dyke-protected towns (Bentiu, Rubkona) are not modelled." + caveat, **common),
        dict(id="flood_population_exposed_pct", label="Share of population in flooded areas", units="% of county population",
             aggregation="flood_population_exposed / WorldPop county total x 100", higher_is="worse", index_ok=False,
             notes="See flood_population_exposed." + caveat, **common),
        dict(id="flood_oilfield_exposure_km2", label="Flooded area near oil wells/fields (5 km)", units="km2",
             aggregation=f"flooded area within {BUF_KM:.0f} km of any oil well / field point", higher_is="worse",
             index_ok=False, notes="Oil-pollution spread proxy for Unity, Ruweng and Upper Nile oil fields (Thar Jath, "
             "Unity, Toma South, Paloich/Adar...), where produced-water pits, leaking flowlines and spills have been "
             "documented (e.g. Sign of Hope / Hoffnungszeichen field studies 2014-2019 in Unity and Ruweng). Only counties with oil infrastructure have values; "
             "OSM well locations are incomplete." + caveat, **common),
        dict(id="flood_oil_wells_flooded", label="Oil wells/fields in or within 1 km of flood water", units="count",
             aggregation="count of oil well/field points with a flooded cell within ~1 km", higher_is="worse",
             index_ok=False, notes="See flood_oilfield_exposure_km2." + caveat, **common),
    ])
    print("wrote", OUT, len(df))


if __name__ == "__main__":
    main()
    from trend_stats import write_trends
    write_trends(SRC)  # Mann-Kendall + Sen's slope (scripts/trend_stats.py)
