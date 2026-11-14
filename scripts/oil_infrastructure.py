"""Oil infrastructure -> docs/data/points_oil.geojson, docs/data/lines_pipelines.geojson, county oil vars (static).

Sources
 - Global Energy Monitor GOGET (oil & gas extraction areas, Mar 2026) and GOIT (oil pipelines, Jun 2026), CC-BY 4.0,
   from the GEM interim-map geojsons (publicgemdata CDN).
 - OpenStreetMap: petroleum/oil wells (HOT export on HDX, hotosm_ssd_points_of_interest) and pipeline lines
   (Overture Maps base/infrastructure release 2026-10-21.0, class=pipeline, which is OSM-derived).
 - PRIO PETRODATA v1.2 onshore petroleum zones (polygons, coarse) - used only for a zone count note.
"""
import os
import sys
import numpy as np
import pandas as pd
import geopandas as gpd
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from overlay_utils import ROOT, DOCS_DATA, counties, write_long, write_meta, add_points_meta, assign_county

RAW = os.path.join(ROOT, "data", "raw", "oil")
GOGET = "https://publicgemdata.nyc3.cdn.digitaloceanspaces.com/interim_maps/goget_map_2026-03.geojson"
GOIT = "https://publicgemdata.nyc3.cdn.digitaloceanspaces.com/interim_maps/goit_map_2026-06.1.geojson"
OVERTURE = "az://overturemapswestus2.blob.core.windows.net/release/2026-10-21.0/theme=base/type=infrastructure/*"
OSM_POI = os.path.join(ROOT, "data", "raw", "osm", "points_of_interest", "points_of_interest.geojson")
OSM_POI_URL = ("https://production-raw-data-api.s3.amazonaws.com/ISO3/SSD/points_of_interest/"
               "hotosm_ssd_points_of_interest_osm_geojson.zip")


def get(url, path):
    if not os.path.exists(path):
        r = requests.get(url, timeout=600)
        r.raise_for_status()
        open(path, "wb").write(r.content)
    return path


def get_clipped(url, path, bbox=(23, 2, 41, 20)):
    """Download a (possibly huge) global GEM geojson to a temp file, keep only features in bbox, delete the global file."""
    if not os.path.exists(path):
        tmp = path + ".full.tmp"
        get(url, tmp)
        g = gpd.read_file(tmp, bbox=bbox)
        g.to_file(path, driver="GeoJSON")
        os.remove(tmp)
    return path


def overture_pipelines(path):
    """Extract OSM-derived pipelines from Overture via duckdb (pip install duckdb). Cached as CSV."""
    if os.path.exists(path):
        return pd.read_csv(path)
    import duckdb
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial; INSTALL azure; LOAD azure; SET azure_transport_option_type='curl'")
    con.execute(f"""COPY (SELECT id, names.primary AS name, class, ST_AsText(geometry) AS wkt
        FROM read_parquet('{OVERTURE}', hive_partitioning=1)
        WHERE bbox.xmin > 24.1 AND bbox.xmax < 36.0 AND bbox.ymin > 3.4 AND bbox.ymax < 12.3 AND class = 'pipeline')
        TO '{path}' (HEADER)""")
    return pd.read_csv(path)


def main():
    os.makedirs(RAW, exist_ok=True)
    c = counties()
    ssd = c.union_all()
    near = gpd.GeoSeries([ssd], crs=4326).to_crs(32636).buffer(20000).to_crs(4326).iloc[0]
    # --- GEM fields
    fields = gpd.read_file(get_clipped(GOGET, os.path.join(RAW, "goget_ssd_region_2026-03.geojson")))
    fields = fields[fields.intersects(near)].copy()
    fields = gpd.GeoDataFrame(dict(
        name=fields["name"].str.replace(" (South Sudan)", "", regex=False), type="oil field (extraction area)",
        operator=fields["operator"], status=fields["status"], start_year=fields["start-year"],
        discovery_year=fields["discovery-year"], prod_oil_mbbl_y=pd.to_numeric(fields["prod-oil"], errors="coerce").round(2),
        location_accuracy=fields["location-accuracy"], source="Global Energy Monitor GOGET (Mar 2026), CC-BY 4.0"),
        geometry=fields.geometry.values, crs=4326)
    # --- OSM wells
    if not os.path.exists(OSM_POI):
        import zipfile, io
        z = zipfile.ZipFile(io.BytesIO(requests.get(OSM_POI_URL, timeout=300).content))
        z.extractall(os.path.dirname(OSM_POI))
    poi = gpd.read_file(OSM_POI)
    wells = poi[poi.man_made.isin(["petroleum_well", "oil_well"])].copy()
    wells["geometry"] = wells.geometry.representative_point()
    wells = gpd.GeoDataFrame(dict(name=wells["name"].fillna("oil well"), type="oil well",
                                  source="OpenStreetMap (HOT export via HDX), ODbL"),
                             geometry=wells.geometry.values, crs=4326)
    pts = assign_county(pd.concat([fields, wells], ignore_index=True).pipe(gpd.GeoDataFrame, crs=4326))
    pts["year"] = 2026
    pts.to_file(os.path.join(DOCS_DATA, "points_oil.geojson"), driver="GeoJSON", COORDINATE_PRECISION=5)
    print(pts["type"].value_counts(), pts[pts["type"].str.startswith("oil field")][["name", "county_id"]])
    # --- pipelines
    goit = gpd.read_file(get_clipped(GOIT, os.path.join(RAW, "goit_ssd_region_2026-06.1.geojson")))
    goit = goit[goit.intersects(near) & (goit["fuel"] == "Oil")]
    goit = gpd.GeoDataFrame(dict(name=goit["name"], status=goit["status"], start_year=goit["start-year"],
                                 source="Global Energy Monitor GOIT (Jun 2026), CC-BY 4.0"),
                            geometry=goit.geometry.values, crs=4326)
    goit["geometry"] = goit.geometry.intersection(near)
    ov = overture_pipelines(os.path.join(RAW, "overture_pipelines_ssd.csv"))
    ov = gpd.GeoDataFrame(dict(name=ov["name"].fillna("pipeline (OSM)"), status="mapped", start_year=None,
                               source="OpenStreetMap via Overture Maps 2026-10-21.0, ODbL"),
                          geometry=gpd.GeoSeries.from_wkt(ov["wkt"]).values, crs=4326)
    ov = ov[ov.intersects(ssd) & ov.geom_type.isin(["LineString", "MultiLineString"])]
    lines = pd.concat([goit, ov], ignore_index=True)
    lines["geometry"] = lines.geometry.simplify(0.0005)
    lines = lines[lines.geom_type.isin(["LineString", "MultiLineString"])]
    lines = gpd.GeoDataFrame(lines, crs=4326)
    lines["length_km"] = (lines.to_crs(32636).length / 1000).round(2)
    lines.to_file(os.path.join(DOCS_DATA, "lines_pipelines.geojson"), driver="GeoJSON", COORDINATE_PRECISION=5)
    with open(os.path.join(RAW, "SOURCE.md"), "w") as f:
        f.write("Oil infrastructure raw sources (global GEM files are NOT kept; only regional bbox extracts 23-41E, 2-20N):\n"
                f"- GEM GOGET extraction areas: {GOGET} -> goget_ssd_region_2026-03.geojson\n"
                f"- GEM GOIT oil pipelines (~200 MB global): {GOIT} -> goit_ssd_region_2026-06.1.geojson\n"
                f"- Overture Maps base/infrastructure class=pipeline: {OVERTURE} -> overture_pipelines_ssd.csv\n"
                "- PRIO PETRODATA v1.2: https://www.prio.org/data/11 (petrodata_v12.zip)\n"
                f"- OSM points of interest (HOT): {OSM_POI_URL}\nLicenses: GEM CC-BY 4.0; OSM/Overture ODbL.\n")
    # --- county vars (static)
    ids = sorted(c.district_id)
    nf = pts[pts["type"].str.startswith("oil field")].groupby("county_id").size().reindex(ids, fill_value=0)
    nw = pts[pts["type"] == "oil well"].groupby("county_id").size().reindex(ids, fill_value=0)
    op = lines[lines.source.str.startswith("OpenStreetMap") | (lines.status == "operating")]
    # merge GEM operating trunk lines with OSM lines (unary_union removes exact duplicates only)
    from shapely.ops import unary_union
    m = op.to_crs(32636)
    osm_l = gpd.GeoDataFrame(geometry=[unary_union(m.geometry)], crs=32636).explode(index_parts=False)
    osm_l = osm_l[osm_l.geom_type.isin(["LineString", "MultiLineString"])]
    inter = gpd.overlay(osm_l[["geometry"]], c[["district_id", "geometry"]].to_crs(32636),
                        how="intersection", keep_geom_type=True)
    km = (inter.length / 1000).groupby(inter.district_id).sum().reindex(ids, fill_value=0)
    rows = []
    for v, s in [("oil_fields_count", nf), ("oil_wells_osm", nw), ("oil_pipeline_km", km)]:
        rows += [(cid, "2018-07-01", v, float(x)) for cid, x in s.items()]
    write_long("oil", pd.DataFrame(rows, columns=["county_id", "date", "variable", "value"]))
    base = {"category": "human", "group": "Oil economy", "temporal": "static", "higher_is": "neutral", "index_ok": False,
            "native_resolution": "point / line"}
    write_meta("oil", [
        dict(base, id="oil_fields_count", label="Oil fields (GEM)", units="fields",
             source="Global Energy Monitor GOGET, Mar 2026 (CC-BY 4.0)",
             source_url="https://globalenergymonitor.org/projects/global-oil-gas-extraction-tracker/",
             aggregation="count of GEM extraction-area points in county",
             notes="Only 5 SSD fields in GEM (Unity, Toma South, Qamari, Tharjath, Palogue): coarse. Block-level fields "
                   "(Munga, Mala, Adar Yale, Moleeta etc.) are not separately listed. Heglig/Panthou is on the Sudan side."),
        dict(base, id="oil_wells_osm", label="Mapped oil wells (OSM)", units="wells", source="OpenStreetMap (HOT/HDX)",
             source_url="https://data.humdata.org/dataset/hotosm_ssd_points_of_interest",
             aggregation="count of man_made=petroleum_well/oil_well", notes="Volunteer mapping - only Rubkona/Guit mapped; absence != no wells."),
        dict(base, id="oil_pipeline_km", label="Mapped pipelines (km)", units="km",
             source="GEM GOIT (operating) + OpenStreetMap via Overture Maps 2026-10-21.0", source_url="https://overturemaps.org/",
             aggregation="length of man_made=pipeline lines within county",
             notes="Operating GEM trunk lines (Greater Nile) + OSM pipelines (Petrodar, flowlines) merged; overlaps may be double counted where geometries differ. Proposed lines excluded."),
    ])
    add_points_meta({"key": "oil", "label": "Oil fields and wells", "category": "human",
                     "source": "Global Energy Monitor GOGET (CC-BY 4.0) + OpenStreetMap wells (ODbL)",
                     "source_url": "https://globalenergymonitor.org/projects/global-oil-gas-extraction-tracker/",
                     "notes": "type = 'oil field (extraction area)' (GEM, with operator/production) or 'oil well' (OSM). Static."})
    add_points_meta({"key": "pipelines", "label": "Oil pipelines (lines)", "category": "human",
                     "source": "GEM GOIT (CC-BY 4.0) + OpenStreetMap via Overture (ODbL)",
                     "source_url": "https://globalenergymonitor.org/projects/global-oil-infrastructure-tracker/",
                     "notes": "Line layer docs/data/lines_pipelines.geojson; includes proposed GEM routes (status field)."})


if __name__ == "__main__":
    main()
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from trend_stats import write_trends
    write_trends("oil")  # Mann-Kendall + Sen's slope (scripts/trend_stats.py)
