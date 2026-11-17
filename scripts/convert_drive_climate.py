#!/usr/bin/env python3
"""Convert the Drive analysis-ready South Sudan county climate table into contract format.

Input : data/drive_mirror/01_analysis_ready/ssd_county_monthly.csv.gz (wide, 2000-2026)
Output: data/processed/drive_climate_county_monthly.csv (long, 2018-01..2025-12)
        data/processed/meta/drive_climate.json
"""
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data/drive_mirror/01_analysis_ready/ssd_county_monthly.csv.gz"
OUT = ROOT / "data/processed/drive_climate_county_monthly.csv"
META = ROOT / "data/processed/meta/drive_climate.json"

POWER = "https://power.larc.nasa.gov/"
M2 = "MERRA-2 reanalysis via NASA POWER"
VARS = [
    # precip_mm / tair_c now come from scripts/gee_climate_grids.py (native IMERG 0.1° / GLDAS 0.25° grids, the
    # same grids as the map rasters); the POWER versions are kept here, hidden, as *_power for provenance.
    dict(id="precip_mm_power", label="Precipitation (IMERG via NASA POWER)", group="Precipitation", units="mm/month",
         source="GPM IMERG V07 Final via NASA POWER (IMERG_PRECTOT)", source_url="https://gpm.nasa.gov/data/imerg",
         native_resolution="0.5° x 0.625° (POWER regridding of 0.1° IMERG)", higher_is="better", index_ok=True,
         notes="mm/day from POWER converted to mm/month. Superseded by precip_mm (native 0.1° IMERG via GEE).",
         hidden=True, src_col="precip_mm"),
    dict(id="tair_c_power", label="Mean air temperature (2 m, MERRA-2 via POWER)", group="Temperature", units="°C",
         source=M2 + " (T2M)", source_url=POWER, native_resolution="0.5° x 0.625° (~50 km)",
         higher_is="worse", index_ok=False, notes="Superseded by tair_c (GLDAS-2.1 0.25° via GEE).",
         hidden=True, src_col="tair_c"),
    dict(id="tmax_c", label="Average daily maximum temperature", group="Temperature", units="°C",
         source=M2 + " (T2M_MAX_AVG)", source_url=POWER, native_resolution="0.5° x 0.625° (~50 km)",
         higher_is="worse", index_ok=False, notes=""),
    dict(id="tmin_c", label="Average daily minimum temperature", group="Temperature", units="°C",
         source=M2 + " (T2M_MIN_AVG)", source_url=POWER, native_resolution="0.5° x 0.625° (~50 km)",
         higher_is="worse", index_ok=False, notes=""),
    dict(id="soilwet_root", label="Root-zone soil wetness (top 1 m)", group="Soil moisture",
         units="fraction 0..1", source=M2 + " (GWETROOT)", source_url=POWER,
         native_resolution="0.5° x 0.625° (~50 km)", higher_is="better", index_ok=True, notes=""),
    dict(id="pet_mm", label="Potential evapotranspiration (Thornthwaite)", group="Water balance",
         units="mm/month", source="Derived (Thornthwaite) from MERRA-2 T2M via NASA POWER", source_url=POWER,
         native_resolution="0.5° x 0.625° (~50 km)", higher_is="worse", index_ok=True,
         notes="Computed by the team from monthly mean temperature."),
    dict(id="spei3", label="SPEI-3 drought index", group="Drought", units="standard deviations",
         source="Derived: IMERG precipitation minus Thornthwaite PET, 3-month SPEI vs county 2000-2026 history",
         source_url="https://spei.csic.es/", native_resolution="county", higher_is="better", index_ok=False,
         notes="Below -1 = dry, above +1 = wet. Not ratio-indexable (can be <= 0)."),
]


def main():
    df = pd.read_csv(SRC)
    df = df[(df.date >= "2018-01-01") & (df.date <= "2025-12-01")]
    df = df.rename(columns={v["src_col"]: v["id"] for v in VARS if "src_col" in v})
    ids = [v["id"] for v in VARS]
    long = df.melt(id_vars=["district_id", "date"], value_vars=ids, var_name="variable", value_name="value")
    long = long.dropna(subset=["value"]).rename(columns={"district_id": "county_id"})
    long = long.sort_values(["variable", "county_id", "date"])
    long["value"] = long["value"].round(4)
    long.to_csv(OUT, index=False)
    meta = [dict(category="environment", temporal="monthly",
                 aggregation="county mean as computed in Drive pipeline (POWER grid cells averaged over county)",
                 **{k: x for k, x in v.items() if k != "src_col"}) for v in VARS]
    META.write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    print(OUT, len(long), long.county_id.nunique(), long.date.min(), long.date.max())


if __name__ == "__main__":
    main()
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from trend_stats import write_trends
    write_trends("drive_climate")  # Mann-Kendall + Sen's slope (scripts/trend_stats.py)
