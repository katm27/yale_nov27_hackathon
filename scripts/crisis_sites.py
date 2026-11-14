"""Crisis / humanitarian sites -> docs/data/points_crisis_sites.geojson

Curated from open sources (coordinates from OpenStreetMap via HOT export on HDX where tagged; otherwise
OSM gazetteer town/village point; a few hub pins read off the Logistics Cluster CONOPS map PDF):
 - UNMISS Protection of Civilians (PoC) sites (Dec 2013-), most redesignated as IDP camps Sept 2020-2021
 - Main IDP camps / settlements
 - UNHCR refugee camps / settlements (Sudanese, Congolese, CAR refugees) and Sudan-crisis transit centre (2023-)
 - Humanitarian logistics hubs (common storage) from Logistics Cluster Concept of Operations, June 2026
   (drive: data/drive_mirror/01_analysis_ready/ssdlcop-new-conopsa3l_04062026.pdf)
"""
import os
import sys
import pandas as pd
import geopandas as gpd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from overlay_utils import DOCS_DATA, write_long, add_points_meta, assign_county, counties

OSM = "OpenStreetMap (HOT export, HDX hotosm_ssd_points_of_interest / populated_places)"
CONOPS = "WFP Logistics Cluster, South Sudan Concept of Operations map, June 2026"

# name, type, lon, lat, period/status, coord_source, coord_quality
SITES = [
    # PoC / former PoC sites
    ("Juba UN House PoC1 (IDP camp since 2020)", "PoC site / IDP camp", 31.538, 4.820, "PoC 2013-2020; IDP camp from Sep 2020", OSM, "site"),
    ("Juba UN House PoC3 (IDP camp since 2020)", "PoC site / IDP camp", 31.528, 4.810, "PoC 2014-2020; IDP camp from Sep 2020", OSM, "site"),
    ("Bentiu PoC (IDP camp since 2020)", "PoC site / IDP camp", 29.795, 9.335, "PoC 2013-2020; IDP camp from Sep 2020; expanded after 2021-22 floods", OSM, "site"),
    ("Malakal PoC site", "PoC site", 31.655, 9.515, "PoC 2013-present (only remaining PoC)", "approx. UNMISS Malakal base, S of town", "approximate"),
    ("Bor PoC (closed/redesignated 2020)", "PoC site / IDP camp", 31.570, 6.185, "PoC 2013-2020", "approx. UNMISS Bor base", "approximate"),
    ("Wau PoC Adjacent Area (closed 2021)", "PoC site / IDP camp", 27.975, 7.690, "PoC AA 2016-2020; IDP camp, closed 2021", "approx. UNMISS Wau base", "approximate"),
    # IDP sites
    ("Mingkaman IDP settlement", "IDP camp", 31.467, 6.188, "2014-present", OSM, "site"),
    ("Mangateen IDP site", "IDP camp", 31.571, 4.887, "2016-present", OSM, "site"),
    ("Don Bosco IDP site (Gumbo)", "IDP camp", 31.632, 4.793, "2016-present", OSM, "site"),
    # Refugee camps / settlements
    ("Doro refugee camp", "refugee camp", 33.751, 9.991, "2011-present (Sudanese refugees, Maban)", OSM, "site"),
    ("Kaya refugee camp", "refugee camp", 33.588, 10.101, "2012-present (Maban)", OSM, "site"),
    ("Yusuf Batil refugee camp", "refugee camp", 33.576, 9.974, "2012-present (Maban)", OSM, "site"),
    ("Gendrassa refugee camp", "refugee camp", 33.609, 9.984, "2012-present (Maban)", OSM, "site"),
    ("Ajuong Thok refugee camp", "refugee camp", 30.285, 9.975, "2013-present (Jamjang)", OSM, "site"),
    ("Pamir refugee camp", "refugee camp", 30.360, 9.905, "2016-present (Jamjang)", OSM, "site"),
    ("Yida refugee settlement", "refugee camp", 30.093, 10.103, "2011-present (relocation ongoing)", OSM, "town"),
    ("Gorom refugee settlement", "refugee camp", 31.443, 4.760, "Ethiopian refugees, 2011-present", "OSM gazetteer (Gorom village)", "village"),
    ("Makpandu refugee settlement", "refugee camp", 28.701, 4.753, "CAR/DRC refugees, 2009-present", "OSM gazetteer (Makpandu village)", "village"),
    ("Lasu refugee settlement", "refugee camp", 30.467, 3.949, "DRC refugees (largely emptied 2016-17)", OSM, "site"),
    ("Renk transit centre (Sudan crisis)", "refugee/returnee transit centre", 32.809, 11.752, "Apr 2023-present (arrivals from Sudan)", "OSM gazetteer (Renk town)", "town"),
]
HUBS = [  # name, lon, lat, storage m2, extra services (coordination c, river j, road n, air a), coord source
    ("Juba", 31.596, 4.846, 1040, "coordination, air, GIS, IM, training, preparedness", "gaz"),
    ("Malakal", 31.658, 9.539, 5040, "coordination, river transport", "gaz"),
    ("Bentiu", 29.798, 9.248, 2186, "coordination", "gaz"),
    ("Bor", 31.561, 6.211, 1440, "coordination, road, river, air", "gaz"),
    ("Akobo", 33.003, 7.793, 800, "", "gaz"), ("Rumbek", 29.677, 6.806, 560, "", "gaz"),
    ("Yida", 30.093, 10.103, 480, "", "gaz"), ("Torit", 32.568, 4.413, 440, "", "gaz"),
    ("Maban (Bunj)", 33.726, 9.963, 320, "", "gaz"), ("Motot", 32.049, 8.165, 320, "", "gaz"),
    ("Ganyiel", 30.48, 7.39, 320, "", "conops"), ("Maridi", 29.465, 4.914, 320, "", "gaz"),
    ("Kapoeta", 33.590, 4.769, 320, "", "gaz"), ("Nyamlel", 26.990, 9.128, 240, "", "gaz"),
    ("Majak Bol", 28.05, 9.07, 240, "", "conops"), ("Wau", 27.991, 7.700, 240, "", "gaz"),
    ("Koch", 29.995, 8.593, 240, "", "gaz"), ("Leer", 30.141, 8.304, 240, "", "gaz"),
    ("Warrap Town", 28.636, 8.090, 240, "", "gaz"), ("Tonj Town", 28.682, 7.275, 240, "", "gaz"),
    ("Ayod", 31.410, 8.124, 240, "to be verified", "gaz"), ("Mabior", 31.404, 7.165, 240, "", "gaz"),
    ("Pochalla", 34.096, 7.184, 240, "", "gaz"), ("Pibor", 33.130, 6.801, 240, "", "gaz"),
    ("Yei", 30.676, 4.094, 240, "to be verified", "gaz"), ("Ulang", 32.719, 8.656, 96, "", "gaz"),
    ("Canal", 31.548, 9.365, 48, "", "gaz"), ("Keew", 30.73, 9.31, 48, "", "conops"),
    ("Manajang", 30.65, 9.28, 48, "", "conops"), ("Pigi", 30.86, 9.39, 48, "", "conops"),
    ("Pajut", 31.692, 7.748, 48, "", "gaz"),
]


def main():
    rows = [dict(name=n, type=t, status=s, coord_source=cs, coord_quality=q, source=cs if cs == OSM else "curated (see notes)",
                 lon=x, lat=y) for n, t, x, y, s, cs, q in SITES]
    for n, x, y, m2, svc, cs in HUBS:
        rows.append(dict(name=f"{n} humanitarian logistics hub", type="humanitarian logistics hub",
                         status=f"common storage {m2} m2" + (f"; {svc}" if svc else "") + " (June 2026)",
                         coord_source="OSM gazetteer town point" if cs == "gaz" else "read off CONOPS map pin",
                         coord_quality="town" if cs == "gaz" else "approximate (~10 km)", source=CONOPS, lon=x, lat=y))
    df = pd.DataFrame(rows)
    gdf = gpd.GeoDataFrame(df.drop(columns=["lon", "lat"]), geometry=gpd.points_from_xy(df.lon, df.lat), crs=4326)
    gdf = assign_county(gdf)
    gdf.to_file(os.path.join(DOCS_DATA, "points_crisis_sites.geojson"), driver="GeoJSON", COORDINATE_PRECISION=4)
    print(gdf["type"].value_counts(), gdf.county_id.isna().sum())
    add_points_meta({"key": "crisis_sites", "label": "PoC sites, IDP & refugee camps, humanitarian hubs", "category": "human",
                     "source": "Curated: OSM (HOT/HDX) coordinates; UNMISS/UNHCR/IOM public site lists; WFP Logistics Cluster CONOPS (Jun 2026)",
                     "source_url": "https://data.humdata.org/dataset/hotosm_ssd_points_of_interest",
                     "notes": "Static layer with `status` describing active period. `coord_quality` flags approximate positions. "
                              "Not exhaustive: IOM DTM lists hundreds of smaller displacement sites (handled in the DTM layer)."})


if __name__ == "__main__":
    main()
