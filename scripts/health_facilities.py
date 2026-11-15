"""WHO / MoH South Sudan Master Facility List (April 2025, HDX) -> points_health.geojson,
county counts health_facilities, hospitals (+ per 100k pop using WorldPop 2025)."""
import os
import sys
import numpy as np
import pandas as pd
import geopandas as gpd
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from overlay_utils import ROOT, PROC, DOCS_DATA, counties, write_long, write_meta, add_points_meta, assign_county

RAW = os.path.join(ROOT, "data", "raw", "health")
URL = ("https://data.humdata.org/dataset/b60d95d8-c746-4046-93f1-b2dbcb976e29/resource/"
       "69256375-d453-4697-b5ac-fbdc8a351b92/download/who-master-facility-list_april2025.xlsx")
PAGE = "https://data.humdata.org/dataset/south-sudan-health-facilities"


def ftype(name):
    n = str(name).lower()
    for k, v in [("hospital", "hospital"), ("phcc", "PHCC"), ("phcu", "PHCU"), ("clinic", "clinic"),
                 ("health cent", "PHCC"), ("otp", "nutrition (OTP)"), ("mobile", "mobile")]:
        if k in n:
            return v
    return "other"


def main():
    os.makedirs(RAW, exist_ok=True)
    p = os.path.join(RAW, "who_mfl_apr2025.xlsx")
    if not os.path.exists(p):
        open(p, "wb").write(requests.get(URL, timeout=120).content)
    with open(os.path.join(RAW, "SOURCE.md"), "w") as f:
        f.write(f"WHO Master Facility List April 2025 (South Sudan MoH/WHO), HDX {PAGE}\n{URL}\nLicense CC-BY\n")
    d = pd.read_excel(p)
    d["name"] = d["site_dhis2_name"].fillna(d["site"].str.title())
    d["type"] = d["site"].map(ftype)
    d = d.rename(columns={"county_code": "county_id"})
    valid = set(counties().district_id)
    d = d[d.county_id.isin(valid)]
    # points (only those with coordinates inside a sane bbox)
    g = d.dropna(subset=["latitude", "longitude"])
    g = g[g.latitude.between(3, 13) & g.longitude.between(23, 36.5)]
    gdf = gpd.GeoDataFrame(g[["name", "type", "county_id", "payam"]].assign(
        source="WHO Master Facility List (Apr 2025) via HDX", year=2025),
        geometry=gpd.points_from_xy(g.longitude, g.latitude), crs=4326)
    os.makedirs(DOCS_DATA, exist_ok=True)
    gdf.to_file(os.path.join(DOCS_DATA, "points_health.geojson"), driver="GeoJSON",
                COORDINATE_PRECISION=5)
    print("points", len(gdf), "of", len(d), gdf["type"].value_counts().to_dict())
    # county counts (use county code in list, includes facilities without coordinates)
    ids = sorted(valid)
    hf = d.groupby("county_id").size().reindex(ids, fill_value=0)
    hos = d[d.type == "hospital"].groupby("county_id").size().reindex(ids, fill_value=0)
    pop = pd.read_csv(os.path.join(PROC, "worldpop_county_monthly.csv"))
    pop = pop[pop.date == "2025-07-01"].set_index("county_id").value.reindex(ids)
    date = "2018-07-01"
    rows = []
    for v, s in [("health_facilities", hf), ("hospitals", hos),
                 ("health_facilities_per100k", hf / pop * 1e5), ("hospitals_per100k", hos / pop * 1e5)]:
        rows += [(cid, date, v, float(x)) for cid, x in s.items() if np.isfinite(x)]
    write_long("health", pd.DataFrame(rows, columns=["county_id", "date", "variable", "value"]))
    base = {"category": "human", "group": "Health access", "source": "WHO / MoH Master Facility List, April 2025 (HDX)",
            "source_url": PAGE, "native_resolution": "point", "temporal": "static", "index_ok": False,
            "aggregation": "count of listed facilities by county code"}
    write_meta("health", [
        dict(base, id="health_facilities", label="Health facilities (all levels)", units="facilities", higher_is="better",
             notes="Snapshot list (2025) - static; includes hospitals, PHCCs, PHCUs. Functionality status not in list."),
        dict(base, id="hospitals", label="Hospitals", units="facilities", higher_is="better",
             notes="Facilities with 'hospital' in name. Static snapshot (2025)."),
        dict(base, id="health_facilities_per100k", label="Health facilities per 100k people", units="per 100k",
             higher_is="better", notes="Denominator WorldPop 2025 county population."),
        dict(base, id="hospitals_per100k", label="Hospitals per 100k people", units="per 100k", higher_is="better",
             notes="Denominator WorldPop 2025 county population."),
    ])
    add_points_meta({"key": "health", "label": "Health facilities (hospital / PHCC / PHCU)", "category": "human",
                     "source": "WHO / MoH Master Facility List, April 2025 (HDX)", "source_url": PAGE,
                     "notes": "Point per facility with type; functionality not reported. Some listed facilities lack coordinates (counted in county totals only)."})


if __name__ == "__main__":
    main()
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from trend_stats import write_trends
    write_trends("health")  # Mann-Kendall + Sen's slope (scripts/trend_stats.py)
    import points_snapshots  # snapshot temporal fields (valid_from/valid_to/date_basis)
    points_snapshots.health()
