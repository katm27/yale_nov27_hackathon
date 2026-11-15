"""Education: schools + enrolment.

 - South Sudan Schools Attendance Monitoring System (SSSAMS) 2015 schools & enrolment (HDX, CC0): ~5,000 schools with
   coordinates, type and enrolment by sex. Most recent open school-level census with enrolment; NO open county-level
   EMIS series exists for 2018-2025 (EMIS reports are national/state PDFs).
 - OpenStreetMap education facilities (HOT export on HDX, Nov 2026) added to the point layer as a second source.
County vars are static snapshots (2015 data, dated 2018-07-01 per contract).
"""
import os
import sys
import zipfile
import io
import numpy as np
import pandas as pd
import geopandas as gpd
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from overlay_utils import ROOT, PROC, DOCS_DATA, counties, write_long, write_meta, add_points_meta, assign_county

RAW = os.path.join(ROOT, "data", "raw", "education")
SSSAMS = ("https://data.humdata.org/dataset/811c4282-2223-4fc9-9b40-43223c4e3c3e/resource/"
          "7cd16811-0d41-480f-8aec-d75e837cb1d3/download/south-sudan-schools-and-enrolment-data-2015-sssams.xlsx")
PAGE = "https://data.humdata.org/dataset/south-sudan-schools-and-enrolment-data-2015-sssams"
OSM_URL = ("https://production-raw-data-api.s3.amazonaws.com/ISO3/SSD/education_facilities/"
           "hotosm_ssd_education_facilities_osm_geojson.zip")
OSM = os.path.join(ROOT, "data", "raw", "osm", "education_facilities", "education_facilities.geojson")
NAME_FIX = {"abiemnom": "Abiemnhom", "akoka": "Baliet", "aweil town": "Aweil Centre", "bor": "Bor South",
            "longchok": "Longochuk", "malut": "Melut", "mayiandit": "Mayendit", "nasir": "Luakpiny/Nasir",
            "nyirol (diror)": "Nyirol", "old fangak": "Fangak", "panyinjiar": "Panyijiar", "piji": "Canal/Pigi",
            "ruweng": "Pariang", "uror (wunror)": "Uror", "yei river": "Yei"}
TYPES = {"PRI": "primary school", "SEC": "secondary school", "ALP": "accelerated learning", "PRE": "pre-school",
         "ECD": "early childhood", "NUR": "nursery"}


def main():
    os.makedirs(RAW, exist_ok=True)
    p = os.path.join(RAW, "sssams_2015.xlsx")
    if not os.path.exists(p):
        open(p, "wb").write(requests.get(SSSAMS, timeout=300).content)
    if not os.path.exists(OSM):
        zipfile.ZipFile(io.BytesIO(requests.get(OSM_URL, timeout=300).content)).extractall(os.path.dirname(OSM))
    with open(os.path.join(RAW, "SOURCE.md"), "w") as f:
        f.write(f"SSSAMS 2015 schools & enrolment (HDX {PAGE}): {SSSAMS}\nOSM education (HOT): {OSM_URL}\n"
                "Also checked: IOM DTM village assessment education facilities 2019-20 (HDX), facility presence only.\n")
    c = counties()
    a = pd.read_excel(p, sheet_name=0)
    a = a[a.Closed == 0].copy()
    # county: by coordinates where available, else by (fixed) county name
    byname = {n.lower(): i for n, i in zip(c.name, c.district_id)}
    a["cname_id"] = a.County.str.lower().map(lambda n: byname.get(str(n).lower()) or byname.get(NAME_FIX.get(n, "").lower()))
    ok = a.Latitude.between(3, 13) & a.Longitude.between(23, 36.5)
    g = gpd.GeoDataFrame(a[ok], geometry=gpd.points_from_xy(a[ok].Longitude, a[ok].Latitude), crs=4326)
    g = assign_county(g)
    a["county_id"] = a["cname_id"]
    a.loc[g.index, "county_id"] = g["county_id"].fillna(g["cname_id"])
    print("unassigned schools:", a.county_id.isna().sum(), "of", len(a))
    # points
    sp = gpd.GeoDataFrame(dict(name=g["Name"], type=g["Type"].map(TYPES).fillna("school"), managed=g["Managed"],
                               enrol_female=g["Enrolment Female"], enrol_male=g["Enrolment Male"], year=2015,
                               source="SSSAMS 2015 (HDX)", county_id=a.loc[g.index, "county_id"]),
                          geometry=g.geometry.values, crs=4326)
    o = gpd.read_file(OSM)
    o["geometry"] = o.geometry.representative_point()
    o = o[o.amenity.isin(["school", "college", "kindergarten", "university"])]
    op = gpd.GeoDataFrame(dict(name=o["name"], type=o["amenity"].map(
        {"school": "school (OSM)", "college": "college", "kindergarten": "kindergarten", "university": "university"}),
        year=2026, source="OpenStreetMap (HOT/HDX), ODbL"), geometry=o.geometry.values, crs=4326)
    op = assign_county(op)
    pts = pd.concat([sp, op], ignore_index=True)
    for col in ["enrol_female", "enrol_male"]:
        pts[col] = pd.to_numeric(pts[col], errors="coerce")
    gpd.GeoDataFrame(pts, crs=4326).to_file(os.path.join(DOCS_DATA, "points_schools.geojson"), driver="GeoJSON",
                                            COORDINATE_PRECISION=5)
    print("points", len(pts))
    # county vars
    ids = sorted(c.district_id)
    a["F"] = pd.to_numeric(a["Enrolment Female"], errors="coerce")
    a["M"] = pd.to_numeric(a["Enrolment Male"], errors="coerce")
    rep = a[a.F.notna() | a.M.notna()]
    n = a.groupby("county_id").size().reindex(ids, fill_value=0)
    enr = rep.groupby("county_id")[["F", "M"]].sum().reindex(ids)
    tot = enr.F.fillna(0) + enr.M.fillna(0)
    share = (enr.F / tot.replace(0, np.nan))
    pop = pd.read_csv(os.path.join(PROC, "worldpop_county_monthly.csv"))
    pop = pop[pop.date == "2018-07-01"].set_index("county_id").value.reindex(ids)
    rows = []
    for v, s in [("schools_count", n), ("schools_per100k", n / pop * 1e5),
                 ("edu_enrolment", tot.where(tot > 0)), ("edu_girls_share", share)]:
        rows += [(cid, "2018-07-01", v, float(x)) for cid, x in s.items() if pd.notna(x) and np.isfinite(x)]
    write_long("education", pd.DataFrame(rows, columns=["county_id", "date", "variable", "value"]))
    base = {"category": "human", "group": "Education", "source": "SSSAMS 2015 schools & enrolment (HDX, CC0)",
            "source_url": PAGE, "native_resolution": "school", "temporal": "static", "index_ok": False}
    note = "2015 school census (SSSAMS) - latest open school-level data; treated as static baseline. "
    write_meta("education", [
        dict(base, id="schools_count", label="Schools (open, 2015)", units="schools", higher_is="better",
             aggregation="count of open schools (all levels) by county", notes=note),
        dict(base, id="schools_per100k", label="Schools per 100k people", units="per 100k", higher_is="better",
             aggregation="schools_count / WorldPop 2018 population", notes=note),
        dict(base, id="edu_enrolment", label="School enrolment (2015)", units="pupils", higher_is="better",
             aggregation="sum of reported enrolment (female+male) over reporting schools", notes=note + "Only schools that reported enrolment (~3,300 of ~4,900)."),
        dict(base, id="edu_girls_share", label="Girls' share of enrolment (2015)", units="fraction 0-1", higher_is="better",
             aggregation="female / total enrolment over reporting schools", notes=note + "National 2015 average ~0.38."),
    ])
    add_points_meta({"key": "schools", "label": "Schools", "category": "human",
                     "source": "SSSAMS 2015 (HDX, CC0) + OpenStreetMap education facilities (HOT/HDX, ODbL)",
                     "source_url": PAGE,
                     "notes": "SSSAMS points carry type and 2015 enrolment by sex (year=2015); OSM points year=2026. "
                              "The two sources overlap (duplicates possible)."})


if __name__ == "__main__":
    main()
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from trend_stats import write_trends
    write_trends("education")  # Mann-Kendall + Sen's slope (scripts/trend_stats.py)
    import points_snapshots  # snapshot temporal fields (valid_from/valid_to/date_basis)
    points_snapshots.schools()
