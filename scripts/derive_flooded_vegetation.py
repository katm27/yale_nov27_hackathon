"""Flooded vegetation in the Sudd = MODIS inundation (incl. flooded vegetation) minus open water.

Input : data/processed/sudd_water_county_monthly.csv (scripts/sudd_water_index.py)
Output: data/processed/sudd_floodedveg_county_monthly.csv + data/processed/meta/sudd_floodedveg.json
Flooded papyrus/grass swamp is what Sentinel-1 radar and plain water indices miss; this isolates it.
"""
import json
import os

import geopandas as gpd
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    d = pd.read_csv(os.path.join(ROOT, "data", "processed", "sudd_water_county_monthly.csv"))
    w = d.pivot_table(index=["county_id", "date"], columns="variable", values="value").reset_index()
    w["fv"] = (w["sudd_inundation_km2"] - w["sudd_openwater_km2"]).clip(lower=0)
    area = gpd.read_file(os.path.join(ROOT, "data", "counties.geojson")).to_crs(6933)
    area = dict(zip(area.district_id, area.area / 1e6))
    w["fv_pct"] = 100 * w["fv"] / w["county_id"].map(area)
    out = pd.concat([w[["county_id", "date"]].assign(variable="sudd_floodedveg_km2", value=w["fv"].round(2)),
                     w[["county_id", "date"]].assign(variable="sudd_floodedveg_pct", value=w["fv_pct"].round(3))])
    out.dropna().to_csv(os.path.join(ROOT, "data", "processed", "sudd_floodedveg_county_monthly.csv"), index=False)
    common = {"category": "environment", "group": "Water & floods (Sudd)", "temporal": "monthly", "higher_is": "neutral",
              "index_ok": True, "source": "Derived from the Sudd MODIS water index (MOD09A1, Planetary Computer)",
              "source_url": "docs/VALIDATION_sudd_water.md", "native_resolution": "500 m (MODIS), Sudd counties only",
              "aggregation": "inundated area minus open-water area per county-month (gap-filled 8-day composites)"}
    meta = [dict(common, id="sudd_floodedveg_km2", label="Flooded vegetation, Sudd (MODIS)", units="km²",
                 notes="Swamp and grassland standing in water (papyrus, reeds, flooded grass). Radar and plain water maps often miss it."),
            dict(common, id="sudd_floodedveg_pct", label="Flooded vegetation, Sudd (% of county)", units="% of county area",
                 notes="Flooded vegetation as a share of the county's area.")]
    json.dump(meta, open(os.path.join(ROOT, "data", "processed", "meta", "sudd_floodedveg.json"), "w"), indent=1)
    print(out.groupby("variable").value.describe())


if __name__ == "__main__":
    main()
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from trend_stats import write_trends
    write_trends("sudd_floodedveg")
