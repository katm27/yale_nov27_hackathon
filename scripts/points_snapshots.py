"""Snapshot point layers (health facilities, schools): add valid_from / valid_to / date_basis + snapshot flag.

These lists are one-off inventories, not time series, so they cannot show openings/closures:
 * Health (points_health.geojson, WHO/MoH master facility list published Apr 2025, sheet
   'hsf_master_facility_list_202403' = list as of Mar 2024): valid_from = 2024-03; facilities whose name + county also
   appear in the MoH 'SS master HF codes 2023' list (data/raw/health/ss_master_hf_codes_2023.xlsx) get 2023-01
   (year-only list). valid_to = null (no closure information; functionality not reported).
 * Schools (points_schools.geojson): SSSAMS 2015 survey -> valid_from null (listed before 2018; continued operation
   after 2015 not verified); OSM education facilities (HOT export Nov 2026, mapping dates not in the extract) ->
   null/null 'snapshot only'.
All features get snapshot=true so the app can choose to keep them visible regardless of the slider.
Re-runnable (overwrites the fields it sets).

SUPERSEDED (Nov 2026): health() and schools() now finish by rebuilding the layers from the team's time-dynamic
compilation (scripts/team_dynamic_layers.py: registry/survey status periods), so re-running the older pipelines
does not bring back the static snapshots.
"""
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from points_temporal import ROOT, read_fc, write_fc, set_validity, update_points_meta


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def health():
    fc = read_fc("points_health.geojson")
    old = pd.read_excel(os.path.join(ROOT, "data", "raw", "health", "ss_master_hf_codes_2023.xlsx"),
                        sheet_name="Health Facilities & Codes")
    keys = set(zip(old.County_Code, old.Facility_Name.map(norm)))
    n23 = 0
    for f in fc["features"]:
        p = f["properties"]
        if (p.get("county_id"), norm(p.get("name"))) in keys:
            n23 += 1
            set_validity(p, "2023-01", None, "snapshot: in MoH master HF code list 2023 (year only) and WHO MFL (Mar 2024 list, published Apr 2025); no closure data")
        else:
            set_validity(p, "2024-03", None, "snapshot: WHO/MoH master facility list as of Mar 2024 (published Apr 2025); no opening/closure data")
        p["snapshot"] = True
    write_fc("points_health.geojson", fc["features"])
    print("health", len(fc["features"]), "of which in 2023 list:", n23)
    import team_dynamic_layers as tdl  # superseding status-period layer
    tdl.health()
    tdl.write_points_meta({"health": tdl.status_values_of("points_health.geojson", tdl.HEALTH_ORDER)})
    return
    update_points_meta({
        "key": "health", "label": "Health facilities (hospital / PHCC / PHCU)", "category": "human",
        "source": "WHO / MoH Master Facility List, April 2025 (HDX); MoH HF code list 2023",
        "source_url": "https://data.humdata.org/dataset/south-sudan-health-facilities",
        "notes": ("Point per facility with type; functionality not reported. Some listed facilities lack coordinates "
                  "(counted in county totals only). Temporal: SNAPSHOT (snapshot=true) - valid_from = list date "
                  "(2023-01 if already in the 2023 MoH code list, else 2024-03), valid_to null; no opening/closure dates exist.")})


def schools():
    fc = read_fc("points_schools.geojson")
    for f in fc["features"]:
        p = f["properties"]
        if str(p.get("source", "")).startswith("SSSAMS"):
            set_validity(p, None, None, "snapshot: SSSAMS 2015 school survey (listed before 2018; later operation not verified)")
        else:
            set_validity(p, None, None, "snapshot only: OpenStreetMap (HOT export Nov 2026), mapping date unknown")
        p["snapshot"] = True
    write_fc("points_schools.geojson", fc["features"])
    print("schools", len(fc["features"]))
    import team_dynamic_layers as tdl  # superseding status-period layer
    tdl.schools()
    tdl.write_points_meta({"schools": tdl.status_values_of("points_schools.geojson", tdl.SCHOOL_ORDER)})
    return
    update_points_meta({
        "key": "schools", "label": "Schools", "category": "human",
        "source": "SSSAMS 2015 (HDX, CC0) + OpenStreetMap education facilities (HOT/HDX, ODbL)",
        "source_url": "https://data.humdata.org/dataset/south-sudan-schools-and-enrolment-data-2015-sssams",
        "notes": ("SSSAMS points carry type and 2015 enrolment by sex (year=2015); OSM points year=2026. The two sources "
                  "overlap (duplicates possible). Temporal: SNAPSHOT (snapshot=true, valid_from/valid_to null) - no "
                  "opening/closure dates in either source.")})


def main():
    health()
    schools()


if __name__ == "__main__":
    main()
