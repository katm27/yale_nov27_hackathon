"""UCDP Georeferenced Event Dataset (GED) v26.1 -> South Sudan county-month + event points.

- Downloads the global GED CSV zip (~40 MB; cached outside the repo), keeps events 2018-2025 whose
  coordinates fall inside data/counties.geojson (this also captures Abyei events that UCDP codes
  under Sudan), and saves the filtered subset to data/raw/ucdp/ged261_ssd_2018_2025.csv.
- County counts use only events located at admin-2 precision or better (where_prec <= 3);
  coarser events (admin-1 centroid / country-level) are kept in the points file but not counted.
- County-months with no event are true zeros (GED is exhaustive within its definitions).
- Oil-related flag: keyword match in source text / location / actors (oil field, pipeline,
  Heglig, Paloich, Thar Jath, Adar, Toma South, Mala, Munga, Unity oil, ...).
"""
import json
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from human_common import (RAW, DOCS_DATA, MONTHS, download, load_counties, finalize, base_meta,
                          upsert_points_meta)

SRC = "ucdp"
URL = "https://ucdp.uu.se/downloads/ged/ged261-csv.zip"
RAWD = RAW / "ucdp"
CACHE = Path(os.environ.get("UCDP_CACHE", RAW / "ucdp" / "_cache")) / "ged261-csv.zip"  # _cache is gitignored
TYPES = {1: "state_based", 2: "non_state", 3: "one_sided"}
OIL = re.compile(r"(?i)\boil\b|oil ?-?fields?|oilfield|pipeline|petroleum|\bpetrol\b|heglig|paloi?ch|palouch|"
                 r"thar ?jath|tharjieth|adar ?yel|toma south|\bmala oil|\bmunga\b|petrodar|\bgpoc\b|"
                 r"unity oil|\bdpoc\b|nilepet|\bspoc\b")


def load_ged():
    out = RAWD / "ged261_ssd_2018_2025.csv"
    if out.exists():
        return pd.read_csv(out, low_memory=False)
    download(URL, CACHE)
    with zipfile.ZipFile(CACHE) as z:
        name = [n for n in z.namelist() if n.endswith(".csv")][0]
        with z.open(name) as f:
            g = pd.read_csv(f, low_memory=False)
    g = g[(g.year >= 2018) & (g.year <= 2025)]
    # bbox prefilter (South Sudan incl. Abyei)
    g = g[g.latitude.between(3.0, 10.5) & g.longitude.between(23.0, 36.5)]
    RAWD.mkdir(parents=True, exist_ok=True)
    g.to_csv(out, index=False)
    return g


def main():
    ged = load_ged()
    counties = load_counties()[["district_id", "name", "geometry"]]
    pts = gpd.GeoDataFrame(ged, geometry=gpd.points_from_xy(ged.longitude, ged.latitude), crs="EPSG:4326")
    j = gpd.sjoin(pts, counties.to_crs(4326), how="inner", predicate="within").drop(columns="index_right")
    j = j.drop_duplicates("id")
    print("GED events 2018-2025 inside SSD polygons:", len(j), "| by country:", j.country.value_counts().to_dict())
    j["date"] = pd.to_datetime(j.date_start.str[:10]).dt.to_period("M").dt.to_timestamp()
    j["type"] = j.type_of_violence.map(TYPES)
    text = j[["source_article", "source_headline", "source_original", "where_description", "where_coordinates",
              "adm_1", "adm_2", "side_a", "side_b", "conflict_name"]].fillna("").astype(str).agg(" | ".join, axis=1)
    j["oil_related"] = text.str.contains(OIL)
    print("oil-related events inside SSD:", int(j.oil_related.sum()))
    # oil-related events just across the border (e.g. Heglig field, Sudan) are kept for the points layer only
    rest = pts[~pts.id.isin(j.id)].copy()
    rtext = rest[["source_article", "source_headline", "source_original", "where_description", "where_coordinates",
                  "side_a", "side_b"]].fillna("").astype(str).agg(" | ".join, axis=1)
    xb = rest[rtext.str.contains(OIL)].copy()
    xb["district_id"] = None
    xb["type"] = xb.type_of_violence.map(TYPES)
    xb["oil_related"] = True
    print("oil-related events outside SSD (bbox, kept as points only):", len(xb))
    allpts = pd.concat([j, xb])

    # ---- points file
    DOCS_DATA.mkdir(parents=True, exist_ok=True)
    feats = []
    for r in allpts.sort_values("date_start").itertuples():
        feats.append({"type": "Feature",
                      "geometry": {"type": "Point", "coordinates": [round(r.longitude, 5), round(r.latitude, 5)]},
                      "properties": {"name": f"{r.where_coordinates}", "type": r.type, "source": "UCDP GED v26.1",
                                     "date": r.date_start[:10], "year": int(r.year), "deaths": int(r.best),
                                     "deaths_civilians": int(r.deaths_civilians),
                                     "side_a": r.side_a, "side_b": r.side_b, "conflict": r.conflict_name,
                                     "county_id": r.district_id, "where_prec": int(r.where_prec),
                                     "oil_related": bool(r.oil_related), "inside_ssd": r.district_id is not None,
                                     "ucdp_id": int(r.id)}})
    (DOCS_DATA / "points_ucdp_events.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":")))
    upsert_points_meta({"key": "ucdp_events", "label": "UCDP GED conflict events (2018-2025)", "category": "human",
                        "source": "UCDP Georeferenced Event Dataset v26.1", "source_url": "https://ucdp.uu.se/downloads/",
                        "notes": "Organized-violence events with >=1 death. type: state_based / non_state / one_sided; "
                                 "deaths = best estimate; where_prec 1=exact .. 3=county, >=4 coarse (admin-1/country). "
                                 f"oil_related = keyword match on oil fields/pipelines ({int(j.oil_related.sum())} inside SSD; "
                                 f"{len(xb)} cross-border oil events e.g. Heglig added with inside_ssd=false)."})

    # ---- county-month
    c = j[j.where_prec <= 3]
    print("events at county precision:", len(c), "| excluded coarse:", len(j) - len(c))
    rows = []
    for var, sub, col in [("ucdp_events", c, None), ("ucdp_deaths_best", c, "best")] + \
            [(f"ucdp_{t}_events", c[c.type == t], None) for t in TYPES.values()] + \
            [(f"ucdp_{t}_deaths", c[c.type == t], "best") for t in TYPES.values()] + \
            [("ucdp_civilian_deaths", c, "deaths_civilians")]:
        s = sub.groupby(["district_id", "date"]).size() if col is None else sub.groupby(["district_id", "date"])[col].sum()
        idx = pd.MultiIndex.from_product([sorted(counties.district_id), MONTHS], names=["county_id", "date"])
        s.index.names = ["county_id", "date"]
        s = s.reindex(idx, fill_value=0).rename("value").reset_index()
        s["variable"] = var
        rows.append(s)
    df = pd.concat(rows)
    df["value"] = df.value.astype(float)

    common = dict(source="UCDP Georeferenced Event Dataset (GED) v26.1", source_url="https://ucdp.uu.se/downloads/",
                  native_resolution="event points (where_prec<=3)", group="Conflict", higher_is="worse",
                  notes="Events with >=1 fatality in conflicts reaching UCDP thresholds; events geolocated only to "
                        "state/country level excluded from county sums. Very sparse after 2021; use rolling sums.")
    lab = {"state_based": "state-based", "non_state": "non-state", "one_sided": "one-sided (vs civilians)"}
    meta = [base_meta(id="ucdp_events", label="UCDP conflict events", units="events/month",
                      aggregation="count of GED events in county-month", **common),
            base_meta(id="ucdp_deaths_best", label="UCDP conflict deaths (best est.)", units="deaths/month",
                      aggregation="sum of GED 'best' in county-month", **common),
            base_meta(id="ucdp_civilian_deaths", label="UCDP civilian deaths", units="deaths/month",
                      aggregation="sum of GED deaths_civilians", **common)]
    for t in TYPES.values():
        meta.append(base_meta(id=f"ucdp_{t}_events", label=f"UCDP {lab[t]} events", units="events/month",
                              aggregation="count of GED events", **common))
        meta.append(base_meta(id=f"ucdp_{t}_deaths", label=f"UCDP {lab[t]} deaths", units="deaths/month",
                              aggregation="sum of GED 'best'", **common))
    finalize(df, SRC, meta)
    (RAWD / "SOURCE.md").write_text(
        f"# UCDP GED v26.1\n\nFull global file (not committed, ~40 MB zip / 270 MB CSV): {URL}\n\n"
        "`ged261_ssd_2018_2025.csv` = events 2018-2025 in a South Sudan bounding box (incl. Abyei), "
        "produced by scripts/ucdp_ssd.py. Codebook: https://ucdp.uu.se/downloads/ged/ged261.pdf\n")


if __name__ == "__main__":
    main()
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from trend_stats import write_trends
    write_trends("ucdp")  # Mann-Kendall + Sen's slope (scripts/trend_stats.py)
