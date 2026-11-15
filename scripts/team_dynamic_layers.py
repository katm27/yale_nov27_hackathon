"""Team-supplied time-dynamic layers (south_sudan_dynamic_layers_2018_2025_v2.zip) -> app layers + county series.

Input: data/raw/team_dynamic_layers/south_sudan_dynamic_layers_2018_2025_v2.zip (read in place; see SOURCE.md and
the zip's METHODS.md). Every output follows the app's temporal standard (scripts/points_temporal.py):
valid_from / valid_to = "YYYY-MM" (null = open-ended: before 2018-01 / after 2025-12), date_basis, plus
`status` and `evidence` on every feature.

Day-precision status periods in the zip are reduced to months: when a status changes mid-month the NEW status owns
that month (e.g. COVID-19 school closure from 20 Mar 2020 -> closed from 2020-03; Heglig seized 8 Dec 2025 ->
disrupted 2025-12), so a site never shows two statuses in the same month.

Decisions (comparison with the layers this replaces/merges; numbers printed by validate()):
 * points_health.geojson      REPLACED. Zip = MoH 2016 list + IOM DTM 2019-20 + MoH 2023 list + WHO MFL Mar 2024,
                              2,275 mapped facilities (all 1,875 of the old WHO-MFL snapshot points are among them),
                              status periods + documented events (Ulang Apr 2025, Old Fangak May 2025).
 * points_schools.geojson     REPLACED. Zip = SSSAMS 2015 + 2019 enrolment export + IOM DTM 2019-20 + national
                              COVID-19 closure (20 Mar 2020 - 2 May 2021). Kept from the old layer: the 2015
                              `managed` / enrol_female / enrol_male attributes (joined on name + position) and the
                              OpenStreetMap schools that are > 300 m from any zip school (undated, status says so).
 * points_oil.geojson         MERGED. GEM GOGET field points keep their attributes (GEM status -> gem_status);
                              production periods reconciled with the zip's block timeline (Toma South restart
                              25 Aug 2018, Unity 21 Jan 2019, Thar Jath restart 21 Jun 2021, Dar Blend halt
                              6 Feb 2024 - 7 Jan 2025, Heglig hub seized 8 Dec 2025 -> Blocks 1/2/4 and 5A disrupted).
                              The 93 undated OSM wells are replaced by the zip's 102 OSM wells with block-status periods.
 * lines_pipelines.geojson    MERGED. The zip's 169 OSM segments (39 km of field lines) all lie on our Overture/OSM
                              lines, so ours are kept and given the same block-status periods (block assigned by the
                              zip's location rule); GEM Greater Nile follows Blocks 1/2/4; GEM proposed routes stay undated.
 * polygons_ethnic_groups     KEPT (GeoEPR geometry clipped to the country) + zip's ACD2EPR rebel-organisation links;
                              2018-2021 = EPR coding, 2022-2025 carried forward with the status saying so.
 * NEW points_gbv_one_stop_centres, points_oil_pollution (2 geolocated Unity-Heglig pipeline spills + 2 located
   pollution reports; the Feb 2024 Petrodar spill lies in Sudan -> timeline event only), points_oil_wells_flooding
   (Sentinel-1 open water around each OSM well), points_surface_water_quality (HLS/Sentinel-2 monthly turbidity at
   8 river/wetland sites; sediment/algae indices, NOT oil contamination).
 * docs/data/context_events.json  timeline annotations (zip context events + in-window water-pollution events).
 * data/processed/sector_partners_county_monthly.csv + meta/sector_partners.json: Protection (incl. GBV) and
   Nutrition partners per county-month from OCHA 3W (2019-2025, Dec 2020 missing). The wells-flooding table is per
   well, not per county, so it is not turned into a county series.

Re-runnable; also called by points_snapshots / points_oil_status / points_events so older pipelines do not
overwrite these layers with the superseded snapshots.
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import zipfile
from collections import Counter, defaultdict

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from points_temporal import (ROOT, DOCS_DATA, read_fc, write_fc, ym, ym_add, clip_window, assign_county_fc,
                             geocode)

RAW = os.path.join(ROOT, "data", "raw", "team_dynamic_layers")
ZIP = os.path.join(RAW, "south_sudan_dynamic_layers_2018_2025_v2.zip")
POINTS_META = os.path.join(ROOT, "data", "processed", "meta", "points.json")
TEAM = "Team compilation (South Sudan dynamic layers v2, Nov 2026)"
BBOX = (23.3, 3.4, 36.0, 12.3)  # lon/lat bounds of South Sudan incl. Abyei, small margin

_Z = None


def zf():
    global _Z
    if _Z is None:
        _Z = zipfile.ZipFile(ZIP)
    return _Z


def zjson(name):
    return json.loads(zf().read(name))


def zcsv(name, **kw):
    return pd.read_csv(io.BytesIO(zf().read(name)), **kw)


# --------------------------------------------------------------------------------------------- period helpers
def month_periods(items, key, start="valid_from", end="valid_to"):
    """items: list of (props, geometry). Group by props[key]; convert ISO-day periods to months so that the new
    status owns the month of a change; drop periods that vanish; clip to the window (null = open-ended).
    Returns list of (props, geometry) with valid_from / valid_to as YYYY-MM or None."""
    groups = defaultdict(list)
    for p, g in items:
        groups[p[key]].append((p, g))
    out = []
    for _, lst in groups.items():
        lst.sort(key=lambda x: str(x[0][start]))
        for i, (p, g) in enumerate(lst):
            vf, vt = ym(p[start]), ym(p[end])
            if i + 1 < len(lst):
                nf = ym(lst[i + 1][0][start])
                if nf <= vt:
                    vt = ym_add(nf, -1)
            if vt < vf:
                continue
            cw = clip_window(vf, vt)
            if cw is None:
                continue
            q = dict(p)
            q[start], q[end] = cw
            out.append((q, g))
    return out


def feat(geom, props):
    return {"type": "Feature", "geometry": geom, "properties": props}


def ordered(p, first):
    """Put user-facing fields first (the app popup shows the first 12 properties)."""
    return {**{k: p.get(k) for k in first if k in p}, **{k: v for k, v in p.items() if k not in first}}


FIRST = ["name", "type", "status", "valid_from", "valid_to", "evidence", "date_basis", "county_id"]


# ------------------------------------------------------------------------------------------------- health
HEALTH_TYPE = {"Hospital": "hospital", "PHCC": "PHCC", "PHCU": "PHCU", "Other": "other", "Private Clinic": "clinic"}
HEALTH_STATUS = {
    "registered": "registered",
    "registered (new since 2016)": "registered (new since 2016)",
    "unconfirmed: in 2016 list, absent from 2023 and 2024 lists": "unconfirmed (dropped from the registry by 2023)",
    "non-functional in 2016; status unknown until relisted": "non-functional in 2016 (until relisted)",
    "non-functional in 2016; absent from 2023 and 2024 lists": "non-functional in 2016 (dropped from the registry by 2023)",
    "non-functional (IOM DTM)": "non-functional (IOM DTM 2019-20)",
    "non-functional (documented event)": "non-functional (attack, documented)",
    "closed (documented event)": "closed (documented)",
}
HEALTH_ORDER = list(dict.fromkeys(HEALTH_STATUS.values()))


def health():
    src = zjson("health_facilities_status_2018_2025.geojson")["features"]
    items = []
    for f in src:
        p = f["properties"]
        st = HEALTH_STATUS[p["status"]]
        if "IOM DTM" in st:
            basis = "IOM DTM village assessment Aug 2019 - Mar 2020 (month the facility stopped, as reported)"
        elif "documented" in st:
            basis = "dated event (MSF)"
        else:
            basis = "bracketed by registry lists (2016, 2023, 2024); change happened between lists"
        q = {"name": p["name"], "type": HEALTH_TYPE.get(p["type"], "other"), "status": st,
             "valid_from": p["valid_from"], "valid_to": p["valid_to"], "evidence": p["evidence"], "date_basis": basis,
             "state": p["state"], "facility_id": p["facility_id"], "in_moh_2016": p["in_moh_2016"],
             "in_mfl_2023": p["in_mfl_2023"], "in_who_mfl_2024": p["in_who_mfl_2024"],
             "moh_2016_status": p["moh_2016_status"],
             "source": "MoH 2016/2023, IOM DTM 2019-20, WHO MFL 2024"}
        items.append((q, f["geometry"]))
    feats = [feat(g, p) for p, g in month_periods(items, "facility_id")]
    feats = assign_county_fc(feats)
    feats = [feat(f["geometry"], ordered(f["properties"], FIRST)) for f in feats]
    write_fc("points_health.geojson", feats)
    return "points_health.geojson", "facility_id"


# ------------------------------------------------------------------------------------------------ schools
SCHOOL_TYPE = {"PRI": "primary school", "SEC": "secondary school", "PRE": "pre-school"}
SCHOOL_STATUS = {
    "operating (reported 2019 enrolment)": "operating (2019 enrolment)",
    "operating (IOM DTM 2019-20)": "operating (IOM DTM 2019-20)",
    "listed, zero enrolment reported 2019": "listed, no learners reported (2019)",
    "unconfirmed (absent from 2019 SSSAMS export)": "unconfirmed (missing from 2019 enrolment list)",
    "non-operational (IOM DTM)": "non-operational (IOM DTM 2019-20)",
    "closed (SSSAMS)": "closed (SSSAMS)",
    "closed nationally (COVID-19)": "closed nationally (COVID-19)",
}
SCHOOL_CARRIED = {
    "operating (2019 enrolment)": "presumed operating (last observed 2019-20)",
    "operating (IOM DTM 2019-20)": "presumed operating (last observed 2019-20)",
    "listed, no learners reported (2019)": "presumed no learners (last observed 2019)",
    "unconfirmed (missing from 2019 enrolment list)": "unconfirmed (last listed 2015)",
    "non-operational (IOM DTM 2019-20)": "presumed non-operational (last observed 2019-20)",
}
OSM_SCHOOL = "mapped in OpenStreetMap (no dates)"
SCHOOL_ORDER = ["operating (2019 enrolment)", "operating (IOM DTM 2019-20)", "listed, no learners reported (2019)",
                "unconfirmed (missing from 2019 enrolment list)", "non-operational (IOM DTM 2019-20)", "closed (SSSAMS)",
                "closed nationally (COVID-19)", "presumed operating (last observed 2019-20)",
                "presumed no learners (last observed 2019)", "unconfirmed (last listed 2015)",
                "presumed non-operational (last observed 2019-20)", OSM_SCHOOL]


def _key(name, coords):
    return (re.sub(r"[^a-z0-9]", "", str(name).lower()), round(round(coords[0], 5), 3), round(round(coords[1], 5), 3))


def schools():
    import numpy as np
    from scipy.spatial import cKDTree
    old = read_fc("points_schools.geojson")["features"]
    osm = [f for f in old if str(f["properties"].get("source", "")).startswith("OpenStreetMap")]
    extra = {}  # SSSAMS 2015 attributes of the previous layer (management, enrolment by sex)
    for f in old:
        p = f["properties"]
        if not str(p.get("source", "")).startswith("OpenStreetMap") and "managed" in p:
            extra[_key(p["name"], f["geometry"]["coordinates"])] = {k: p.get(k) for k in ("managed", "enrol_female", "enrol_male")}
    src = zjson("schools_status_2018_2025.geojson")["features"]
    items, matched = [], 0
    for f in src:
        p = f["properties"]
        raw = p["status"]
        carried = "[carried forward" in raw
        base = SCHOOL_STATUS[raw.split(" [carried")[0]]
        st = SCHOOL_CARRIED.get(base, base) if carried else base
        ev = p["evidence"].split("; no school-level source after")[0]
        if base == "closed nationally (COVID-19)":
            basis = "national COVID-19 closure"
            ev = "All schools closed 20 Mar 2020 to 2 May 2021 (exam classes back 5 Oct 2020)"
        elif carried:
            basis = "carried forward: no school-level data after 2019-20"
            ev = "Last observed: " + ev
        elif "IOM DTM" in base:
            basis = "IOM DTM village assessment 2019-20"
        else:
            basis = "SSSAMS 2015 list and 2019 enrolment"
        is_dtm = str(p["school_id"]).startswith("DTM")
        q = {"name": p["name"], "type": SCHOOL_TYPE.get(p["type"], "school (IOM DTM)" if is_dtm else "school"),
             "status": st, "valid_from": p["valid_from"], "valid_to": p["valid_to"], "evidence": ev,
             "date_basis": basis, "enrolment_2019": p["enrolment_2019"], "enrolment_2015": p["enrolment_2015"]}
        x = extra.get(_key(p["name"], f["geometry"]["coordinates"]))
        if x:
            q.update({k: (int(v) if isinstance(v, float) and v == v else v) for k, v in x.items()})
            matched += 1
        q.update({"school_id": p["school_id"], "source": "IOM DTM 2019-20" if is_dtm else "SSSAMS 2015/2019 (HDX)"})
        items.append((q, f["geometry"]))
    feats = [feat(g, p) for p, g in month_periods(items, "school_id")]
    # OpenStreetMap schools not already in the team layer (> 300 m from any SSSAMS / DTM school)
    zxy = np.array([f["geometry"]["coordinates"] for f in src])
    d, _ = cKDTree(zxy).query(np.array([f["geometry"]["coordinates"] for f in osm]))
    kept = 0
    for f, dd in zip(osm, d):
        if dd * 111 <= 0.3:
            continue
        p = f["properties"]
        kept += 1
        feats.append(feat(f["geometry"], {
            "name": p.get("name"), "type": p.get("type", "school (OSM)"), "status": OSM_SCHOOL, "valid_from": None,
            "valid_to": None, "evidence": "OpenStreetMap education facility; opening and closing dates not recorded",
            "date_basis": "snapshot only: OpenStreetMap (HOT export Nov 2026), mapping date unknown",
            "school_id": f"OSM-{kept:04d}", "source": p.get("source", "OpenStreetMap (HOT/HDX), ODbL")}))
    feats = assign_county_fc(feats)
    feats = [feat(f["geometry"], ordered(f["properties"], FIRST)) for f in feats]
    write_fc("points_schools.geojson", feats)
    print(f"schools: {len(feats)} features; 2015 management/enrolment joined to {matched} period features; "
          f"OSM schools kept {kept} of {len(osm)}")
    return "points_schools.geojson", "school_id"


# ---------------------------------------------------------------------------------------------------- oil
B37 = "Blocks 3 & 7"
B124 = "Blocks 1, 2 & 4"
B5A = "Block 5A"
OIL_ORDER = ["shut in", "partially operating", "operating", "halted (export pipeline rupture in Sudan)",
             "operating (resumed)", "disrupted (Heglig hub seized)", "proposed route (not built)", "mapped line (no status)"]
# block system -> month periods (vf, vt, status, evidence); new status owns the month of change
BLOCK_PERIODS = {
    B37: [(None, "2024-01", "operating", "Producing and exporting Dar Blend via the Petrodar pipeline through Sudan"),
          ("2024-02", "2024-12", "halted (export pipeline rupture in Sudan)",
           "Exports halted 6 Feb 2024 after the Petrodar pipeline ruptured inside Sudan; force majeure March 2024 (Radio Tamazuj; Argus)"),
          ("2025-01", None, "operating (resumed)",
           "Restarted 8 Jan 2025 after force majeure was lifted; full flows reported by Apr 2025 (Sudan Tribune)")],
    B124: [(None, "2018-07", "shut in", "Shut since the Dec 2013 civil war"),
           ("2018-08", "2018-12", "partially operating", "Toma South restarted 25 Aug 2018 (Reuters/Al Jazeera); other Unity fields still shut"),
           ("2019-01", "2025-11", "operating", "Unity fields restarted at a ceremony on 21 Jan 2019 (VOA)"),
           ("2025-12", None, "disrupted (Heglig hub seized)",
            "RSF seized Heglig, the processing hub for this crude, on 8 Dec 2025; engineers shut it down (AFP via New Arab)")],
    B5A: [(None, "2021-05", "shut in", "Production stopped after 2013-14 fighting"),
          ("2021-06", "2025-11", "operating", "Thar Jath production resumed 21 Jun 2021 after nearly 8 years (Sudan Tribune; Eye Radio)"),
          ("2025-12", None, "disrupted (Heglig hub seized)",
           "Block 5A crude flows to the Heglig control centre, seized and shut by the RSF on 8 Dec 2025")],
}
BLOCK_LABEL = {B37: "Blocks 3 & 7 (Dar Petroleum, Melut Basin) -> Petrodar pipeline to Port Sudan",
               B124: "Blocks 1, 2 & 4 (GPOC: Unity, Toma South, El Toor, Munga, El Nar) -> Heglig -> Greater Nile pipeline",
               B5A: "Block 5A (SPOC, Thar Jath) -> Thar Jath-Heglig line"}
BLOCK_OPERATOR = {B37: "Dar Petroleum Operating Company (DPOC)", B124: "Greater Pioneer Operating Company (GPOC)",
                  B5A: "Sudd Petroleum Operating Company (SPOC)"}
BLOCK_BASIS = "block-level status applied to every well/line in the block (not a well-by-well observation)"
# GEM fields: (period list, date basis). Reconciled with the team block timeline.
FIELD_PERIODS = {
    "Toma South Oil Field": [(None, "2018-07", "shut in", "Shut since the Dec 2013 civil war"),
                             ("2018-08", "2025-11", "operating", "Restarted 25 Aug 2018, ceremony 31 Aug 2018 (Reuters/Bloomberg)"),
                             BLOCK_PERIODS[B124][3]],
    "Unity Oil Field": [(None, "2018-12", "shut in", "Shut since the Dec 2013 civil war"),
                        ("2019-01", "2025-11", "operating", "Unity fields restarted 21 Jan 2019 (VOA; Reuters/Bloomberg)"),
                        BLOCK_PERIODS[B124][3]],
    "Tharjath Oil Field": BLOCK_PERIODS[B5A],
    "Palogue Oil Field": BLOCK_PERIODS[B37],
    "Qamari Oil Field": BLOCK_PERIODS[B37],
}
FIELD_BLOCK = {"Toma South Oil Field": B124, "Unity Oil Field": B124, "Tharjath Oil Field": B5A,
               "Palogue Oil Field": B37, "Qamari Oil Field": B37}
BLOCK5A_COUNTIES = {"SS0602", "SS0603", "SS0604", "SS0605", "SS0607"}  # Guit, Koch, Leer, Mayendit, Panyijiar


def block_of_label(s):
    for b in (B37, B124, B5A):
        if str(s).startswith(b):
            return b
    raise ValueError(s)


def oil():
    cur = read_fc("points_oil.geojson")["features"]
    gem, seen = [], set()
    for f in cur:
        p = f["properties"]
        if not str(p.get("type", "")).startswith("oil field") or p["name"] in seen:
            continue
        seen.add(p["name"])
        base = {k: v for k, v in p.items() if k not in ("valid_from", "valid_to", "date_basis", "production_status",
                                                         "status", "evidence", "block_system")}
        base["gem_status"] = p.get("gem_status", p.get("status"))
        gem.append((f["geometry"], base))
    out = []
    for geom, base in gem:
        name = base["name"]
        periods = FIELD_PERIODS.get(name, [(None, None, base["gem_status"], "GEM GOGET status (Mar 2026), undated")])
        for vf, vt, st, ev in periods:
            q = {"name": name, "type": base["type"], "status": st, "valid_from": vf, "valid_to": vt, "evidence": ev,
                 "date_basis": "documented restart/halt dates (month of change shows the new status)",
                 "production_status": st, "block_system": BLOCK_LABEL.get(FIELD_BLOCK.get(name))}
            q.update({k: v for k, v in base.items() if k not in q})
            out.append(feat(geom, q))
    items = []
    for f in zjson("oil_wells_status_2018_2025.geojson")["features"]:
        p = f["properties"]
        q = {"name": p["name"] or f"Oil well (OSM {p['osm_id']})", "type": "oil well", "status": p["status"],
             "valid_from": p["valid_from"], "valid_to": p["valid_to"], "evidence": p["evidence"],
             "date_basis": BLOCK_BASIS, "block_system": p["block_system"],
             "operator": BLOCK_OPERATOR[block_of_label(p["block_system"])], "osm_id": p["osm_id"],
             "osm_last_edit": p["osm_last_edit"], "source": "OpenStreetMap (HOT Raw Data API, Nov 2026), ODbL; " + TEAM}
        items.append((q, f["geometry"]))
    # re-derive month periods from the block table so wells and fields agree exactly
    wells = {}
    for q, g in items:
        wells.setdefault(q["osm_id"], (q, g))
    for q, g in wells.values():
        for vf, vt, st, ev in BLOCK_PERIODS[block_of_label(q["block_system"])]:
            w = dict(q, status=st, valid_from=vf, valid_to=vt, evidence=ev)
            out.append(feat(g, w))
    out = assign_county_fc(out)
    out = [feat(f["geometry"], ordered(f["properties"], FIRST)) for f in out]
    write_fc("points_oil.geojson", out)
    pipelines()
    return "points_oil.geojson", None


def pipelines():
    import geopandas as gpd
    from shapely.geometry import shape
    cur = read_fc("lines_pipelines.geojson")["features"]
    segs, seen = [], set()
    for f in cur:
        k = json.dumps(f["geometry"]["coordinates"])
        if k in seen:
            continue
        seen.add(k)
        p = {k2: v for k2, v in f["properties"].items()
             if k2 not in ("valid_from", "valid_to", "date_basis", "evidence", "block_system", "operator")}
        p.setdefault("gem_status", p.get("status"))
        segs.append((f["geometry"], p))
    cty = gpd.read_file(os.path.join(ROOT, "data", "counties.geojson"))[["district_id", "geometry"]]
    out = []
    for geom, p in segs:
        g = shape(geom)
        st0 = p["gem_status"]
        if st0 == "proposed":
            q = dict(p, status="proposed route (not built)", valid_from=None, valid_to=None,
                     evidence="Proposed route in GEM GOIT; not built", date_basis="planning snapshot (GEM GOIT)")
            out.append(feat(geom, ordered(q, FIRST)))
            continue
        if "Greater Nile" in str(p.get("name")):
            blk = B124
        else:
            c = g.centroid
            if c.x > 31.0:
                blk = B37
            else:
                hit = cty[cty.contains(c)]
                blk = B5A if (len(hit) and hit.district_id.iloc[0] in BLOCK5A_COUNTIES) else B124
        for vf, vt, st, ev in BLOCK_PERIODS[blk]:
            q = dict(p, status=st, valid_from=vf, valid_to=vt, evidence=ev,
                     date_basis=BLOCK_BASIS + "; block assigned by location", block_system=BLOCK_LABEL[blk])
            out.append(feat(geom, ordered(q, FIRST)))
    write_fc("lines_pipelines.geojson", out)


# ------------------------------------------------------------------------------------------------- ethnic
def ethnic():
    """Rebuilt by scripts/ethnic_groups_temporal.py (EPR-2023 / GeoEPR-2023: status per year, coded to 2023,
    2024-2025 carried forward and labelled; plain-language popup fields)."""
    import ethnic_groups_temporal as egt
    feats, last = egt.build()
    egt.write_meta(feats, last)
    return "polygons_ethnic_groups.geojson", "name"


import ethnic_groups_temporal as _egt  # noqa: E402
ETHNIC_ORDER = _egt.status_order(2023)


# --------------------------------------------------------------------------------------------- new layers
def gbv_centres():
    items = []
    for f in zjson("gbv_one_stop_centres_2018_2025.geojson")["features"]:
        p = f["properties"]
        st = {"operating (documented)": "operating (documented)",
              "presumed operating (last confirmed Q1 2023)": "presumed operating (last confirmed early 2023)"}[p["status"]]
        q = {"name": p["name"], "type": "safe house" if "safe house" in p["name"].lower() else "GBV one-stop centre",
             "status": st, "valid_from": p["valid_from"], "valid_to": p["valid_to"], "evidence": p["evidence"],
             "date_basis": ("first date with evidence the site was operating (not necessarily its opening); "
                            "no site-level confirmation after Q1 2023"),
             "host_facility": p["host_facility"], "service": p["service"], "first_evidence": p["first_evidence"],
             "coord_quality": "host facility location (WHO Master Facility List)",
             "source": "UNFPA, UNICEF and FAO/World Bank ELRP reports 2018-2023; " + TEAM}
        items.append((q, f["geometry"]))
    feats = assign_county_fc([feat(g, p) for p, g in month_periods(items, "name")])
    feats = [feat(f["geometry"], ordered(f["properties"], FIRST)) for f in feats]
    write_fc("points_gbv_one_stop_centres.geojson", feats)
    return "points_gbv_one_stop_centres.geojson", "name"


POLL_ORDER = ["oil spill (active)", "spill site (oil removal not documented)", "contamination reported"]


def oil_pollution():
    items = []
    for f in zjson("oil_spills_2018_2025.geojson")["features"]:
        p = f["properties"]
        lon, lat = f["geometry"]["coordinates"][:2]
        if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
            continue  # Petrodar spill in White Nile State, Sudan -> context_events.json only
        st = "oil spill (active)" if "active" in p["status"] else "spill site (oil removal not documented)"
        q = {"name": p["name"].replace(": ", " - "), "type": "oil spill", "status": st, "valid_from": p["valid_from"],
             "valid_to": p["valid_to"], "evidence": p["evidence"],
             "date_basis": "rupture date from satellite imagery and site visit; repair documented, clean-up not",
             "coord_quality": "GPS of spill (Sign of Hope)", "source": p["source"]}
        items.append((q, f["geometry"]))
    feats = [feat(g, p) for p, g in month_periods(items, "name")]
    ev = zcsv("water_pollution_events.csv")
    reports = [
        ("Nahm and Abuk rivers", "Rotriak", "river sampling report",
         "2024-01", None, "sampling dates not published; shown from the 2024-25 coverage"),
        ("Unity State", "Unity Oil Field", "flooded oil wells report",
         "2021-07", None, "floods from Jul 2021 never fully receded (PAX 2023; New Lines/Placemark 2026)"),
    ]
    for area_kw, place, typ, vf, vt, basis in reports:
        r = ev[ev.area.str.startswith(area_kw)].iloc[0]
        if place == "Unity Oil Field":
            lon, lat, cq = 29.6764, 9.4699, "approximate: Unity oil field (GEM GOGET point); report covers Block 2 wells"
        else:
            lon, lat, how, _ = geocode(place)
            cq = "approximate: " + how
        feats.append(feat({"type": "Point", "coordinates": [lon, lat]}, {
            "name": f"{typ.capitalize()}: {r.area}", "type": typ, "status": "contamination reported",
            "valid_from": vf, "valid_to": vt, "evidence": r.event, "date_basis": basis, "coord_quality": cq,
            "source": r.source_url}))
    feats = assign_county_fc(feats)
    feats = [feat(f["geometry"], ordered(f["properties"], FIRST)) for f in feats]
    write_fc("points_oil_pollution.geojson", feats)
    return "points_oil_pollution.geojson", "name"


FLOOD_ORDER = ["flood water around well (radar)", "no open water detected (radar)"]


def wells_flooding():
    items = []
    for f in zjson("oil_wells_flooding_status_2018_2025.geojson")["features"]:
        p = f["properties"]
        st = FLOOD_ORDER[0] if p["status"].startswith("flood water") else FLOOD_ORDER[1]
        q = {"name": f"Oil well (OSM {p['osm_id']})", "type": "oil well", "status": st,
             "valid_from": p["valid_from"], "valid_to": p["valid_to"],
             "evidence": ("Sentinel-1 radar: at least 25% of the 100-500 m ring around the well was open water (monthly median)"
                          if st == FLOOD_ORDER[0] else
                          "Sentinel-1 radar: less than 25% open water around the well; flooded vegetation is not detected"),
             "date_basis": "monthly median of Sentinel-1 acquisitions (Planetary Computer RTC), 2018-2025",
             "max_open_water_share": round(p["max_open_water_share"], 3), "block_system": p["block_system"],
             "osm_id": p["osm_id"], "source": "Sentinel-1 RTC (Microsoft Planetary Computer); OSM wells; " + TEAM}
        items.append((q, f["geometry"]))
    feats = assign_county_fc([feat(g, p) for p, g in month_periods(items, "osm_id")])
    feats = [feat(f["geometry"], ordered(f["properties"], FIRST)) for f in feats]
    write_fc("points_oil_wells_flooding.geojson", feats)
    return "points_oil_wells_flooding.geojson", "osm_id"


WQ_ORDER = ["more turbid than usual", "near usual for the month", "clearer than usual"]
WQ_NAMES = {"Sobat_Nasir": "Sobat river at Nasir", "TharJath_wetland": "Thar Jath wetland",
            "Unity_Bentiu_wetland": "Bentiu wetland (Unity oil fields)", "WhiteNile_Bor": "White Nile at Bor",
            "WhiteNile_Juba": "White Nile at Juba", "WhiteNile_Malakal": "White Nile at Malakal",
            "WhiteNile_Melut": "White Nile at Melut", "WhiteNile_Renk": "White Nile at Renk"}
WQ_THRESH = 0.04  # |NDTI anomaly| above ~ the 80th percentile of all site-months


def surface_water():
    df = zcsv("surface_water_optical_quality_monthly_2018_2025.csv")
    feats = []
    for r in df.itertuples():
        a = r.ndti_anomaly
        st = WQ_ORDER[0] if a > WQ_THRESH else WQ_ORDER[2] if a < -WQ_THRESH else WQ_ORDER[1]
        feats.append(feat({"type": "Point", "coordinates": [float(r.lon), float(r.lat)]}, {
            "name": WQ_NAMES.get(r.aoi, r.aoi), "type": "water-colour monitoring site", "status": st,
            "valid_from": r.month, "valid_to": r.month,
            "evidence": f"turbidity index {r.ndti:.3f} vs usual {r.ndti_clim:.3f} for this month ({r.scenes} scenes)",
            "date_basis": "monthly composite of up to 3 clearest satellite scenes",
            "turbidity_index": round(r.ndti, 4), "turbidity_anomaly": round(a, 4),
            "chlorophyll_index": round(r.ndci, 4), "chlorophyll_anomaly": round(r.ndci_anomaly, 4),
            "red_reflectance": r.red_reflectance, "scenes": int(r.scenes), "sensors": r.sensors, "role": r.role,
            "site_id": r.aoi, "source": "NASA HLS v2 (2020-25) / Sentinel-2 L2A (2018-19) via Planetary Computer; " + TEAM}))
    feats = assign_county_fc(feats)
    write_fc("points_surface_water_quality.geojson", feats)
    return "points_surface_water_quality.geojson", "site_id"


# ------------------------------------------------------------------------------------------ context events
def context_events():
    import geopandas as gpd
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from county_crosswalk import to_ocha
    cty = gpd.read_file(os.path.join(ROOT, "data", "counties.geojson"))
    adm1 = dict(zip(cty.district_id, cty.admin1))
    states = set(cty.admin1)
    cat = {"schools": "education", "health": "health", "oil": "oil"}
    rows = []
    for r in zcsv("context_events_2018_2025.csv").itertuples():
        cid = to_ocha(r.area) if r.scope == "county" else None
        rows.append({"date": r.date_from, "date_to": min(r.date_to, "2025-12-31"), "scope": r.scope,
                     "county_id": cid, "state": adm1.get(cid) if cid else (r.area if r.area in states else None),
                     "area": r.area, "title": r.event, "category": cat.get(r.layer, r.layer),
                     "number": None if pd.isna(r.number) else int(r.number), "source_url": r.source_url})
    for r in zcsv("water_pollution_events.csv").itertuples():
        if r.date_to < "2018-01-01":
            continue  # pre-2018 baselines (2008-13 groundwater study, 2016 hair samples): outside the window
        scope = "national" if r.area.startswith("South Sudan") or "oil fields" in r.area else "state" if r.area == "Unity State" else "county"
        cid = "SS0609" if "Rubkona" in r.area or "Bentiu" in r.area else None
        rows.append({"date": r.date_from, "date_to": min(r.date_to, "2025-12-31"), "scope": scope, "county_id": cid,
                     "state": "Unity" if (cid or scope == "state") else None, "area": r.area, "title": r.event,
                     "category": "water pollution", "number": None, "source_url": r.source_url})
    rows.append({"date": "2024-02-01", "date_to": "2024-03-31", "scope": "national", "county_id": None, "state": None,
                 "area": "White Nile State (Sudan), Petrodar pipeline", "category": "oil spill", "number": None,
                 "title": "Petrodar export pipeline ruptured and spilled oil in Sudan, stopping Blocks 3 & 7 exports "
                          "(spill outside South Sudan)",
                 "source_url": next(f["properties"]["source"].split("; ")[-1]
                                    for f in zjson("oil_spills_2018_2025.geojson")["features"] if "Sudan" in f["properties"]["status"])})
    for r in rows:
        assert "2018-01-01" <= r["date"] <= r["date_to"] <= "2025-12-31", r
    rows.sort(key=lambda r: (r["date"], r["category"]))
    with open(os.path.join(DOCS_DATA, "context_events.json"), "w") as f:
        json.dump({"source": "Team compilation of dated events with source links (Nov 2026); see "
                             "data/raw/team_dynamic_layers/SOURCE.md", "events": rows}, f, indent=1, ensure_ascii=False)
    print(f"context_events.json: {len(rows)} events")


# -------------------------------------------------------------------------------------------- county series
def county_series():
    from human_common import finalize
    from county_crosswalk import to_ocha
    frames = []
    for fname, col, var in [("protection_gbv_partner_presence_county_month_2019_2025.csv", "protection_partners_active",
                             "protection_partners"),
                            ("nutrition_partner_presence_county_month_2019_2025.csv", "nutrition_partners_active",
                             "nutrition_partners")]:
        d = zcsv(fname, dtype={"adm2_pcode": str})
        d["county_id"] = d.adm2_pcode.map(lambda c: to_ocha(c, "ocha") or to_ocha(c))
        assert d.county_id.notna().all(), d[d.county_id.isna()].adm2_pcode.unique()
        frames.append(pd.DataFrame({"county_id": d.county_id, "date": d.month_start, "variable": var, "value": d[col]}))
    df = pd.concat(frames)
    common = dict(category="human", group="Humanitarian response", units="partners", higher_is="better",
                  temporal="monthly", index_ok=False, native_resolution="county",
                  source="OCHA South Sudan 3W operational presence (HDX), compiled by the team (Nov 2026)",
                  source_url="https://data.humdata.org/dataset/south-sudan-operational-presence",
                  aggregation="distinct organisations reporting activity in this sector in the county that month")
    gap = (" No data for December 2020. The way the 3W is reported changes from year to year (2023-2024 have more "
           "counties at zero), so month-to-month changes within a year are more reliable than comparisons between years.")
    meta = [
        dict(common, id="protection_partners", label="Protection and GBV partners present",
             notes="Number of aid organisations reporting protection work in the county that month; protection here "
                   "includes gender-based violence, child protection and mine action, which the source does not "
                   "separate. A stand-in for crisis and survivor services, not a count of service points." + gap),
        dict(common, id="nutrition_partners", label="Nutrition partners present",
             notes="Number of aid organisations reporting nutrition work in the county that month. A stand-in for "
                   "feeding and treatment sites, whose locations are not published." + gap),
    ]
    finalize(df, "sector_partners", meta)
    print("sector_partners:", df.groupby("variable").value.describe().round(2).to_string())


# ------------------------------------------------------------------------------------------- points meta
PLAIN = {
    "health": dict(label="Health facilities (registry status over time)", order=HEALTH_ORDER,
                   notes="Hospitals and clinics with their registry status in each period, built by comparing the 2016, "
                         "2019-20, 2023 and 2024 facility lists and adding documented closures; being listed does not "
                         "prove a facility was working."),
    "schools": dict(label="Schools (status over time)", order=SCHOOL_ORDER,
                    notes="Schools with their status from the 2015 and 2019 school lists, the 2019-20 village "
                          "assessment and the 2020-21 COVID-19 closure; after May 2021 statuses are carried forward "
                          "because no school-level data exists."),
    "oil": dict(label="Oil fields and wells (production status)", order=OIL_ORDER,
                notes="Oil fields and mapped wells coloured by the documented production status of their oil block, "
                      "including the 2018-19 restarts, the 2024 export halt and the December 2025 Heglig disruption."),
    "pipelines": dict(label="Oil pipelines (flow status)", order=OIL_ORDER,
                      notes="Mapped oil pipelines coloured by the documented status of the oil block they serve; "
                            "proposed routes are shown but were never built."),
    "ethnic_groups": dict(label=_egt.LABEL, order=ETHNIC_ORDER, notes=_egt.NOTES.format(last=2023)),
    "gbv_one_stop_centres": dict(label="GBV one-stop centres", order=["operating (documented)", "presumed operating (last confirmed early 2023)"],
                                 notes="Centres offering medical, psychosocial, legal and police help to survivors of "
                                       "sexual and gender-based violence, shown from the first evidence they were "
                                       "operating; no site was confirmed individually after early 2023."),
    "oil_pollution": dict(label="Oil spills and pollution reports", order=POLL_ORDER,
                          notes="Two documented 2019 oil pipeline spills north of Bentiu and two located reports of "
                                "contaminated water and flooded wells in the Unity oil fields."),
    "oil_wells_flooding": dict(label="Flood water around oil wells (radar)", order=FLOOD_ORDER,
                               notes="Mapped oil wells where satellite radar saw open flood water around the well in "
                                     "each period; this shows flooding, not contamination, and misses water under "
                                     "vegetation."),
    "surface_water_quality": dict(label="River and wetland water colour (satellite)", order=WQ_ORDER,
                                  notes="Monthly satellite readings of muddiness at eight river and wetland sites "
                                        "compared with the usual level for that month; this tracks sediment and algae, "
                                        "not oil or chemical pollution."),
    # existing layers: plain labels and one-sentence notes (technical notes kept in `details`)
    "ucdp_events": dict(label="Conflict events with deaths (UCDP)",
                        notes="Organised violence events with at least one death, sized by the number killed."),
    "insecurity_insight": dict(label="Attacks on aid, health and education (Insecurity Insight)",
                               notes="Reported incidents affecting aid workers, health care, education and sexual "
                                     "violence; locations are only approximate, often the centre of a state."),
    "logcluster_hubs": dict(label="Logistics hubs and common storage",
                            notes="Humanitarian logistics hubs and shared warehouses, shown for the periods they "
                                  "appear on the Logistics Cluster's operations maps."),
    "unmiss": dict(label="UN peacekeeping bases (UNMISS)",
                   notes="UN peacekeeping deployments in each period, with approximate troop numbers from UN "
                         "deployment maps."),
    "markets": dict(label="Monitored food markets (WFP)",
                    notes="Markets where WFP recorded food prices, shown for the months they were monitored."),
    "crisis_sites": dict(label="Protection of civilians sites and camps",
                         notes="UN protection of civilians sites, displacement camps and refugee camps, including "
                               "when sites were handed over or closed."),
    "water_points": dict(label="Water points (last known status)",
                         notes="Boreholes and other water points with their last reported working status, most of "
                               "it reported before 2018 and possibly out of date."),
    "fmr_monitoring": dict(label="Migration monitoring points (IOM)",
                           notes="Places where IOM counted people on the move, shown for the months they reported."),
}
NEW_META = {
    "gbv_one_stop_centres": dict(category="human", temporal="periods",
                                 source="UNFPA, UNICEF and FAO/World Bank ELRP reports 2018-2023; host facility coordinates from the WHO Master Facility List; team compilation (Nov 2026)",
                                 source_url="https://southsudan.unfpa.org/"),
    "oil_pollution": dict(category="environment", temporal="periods",
                          source="Sign of Hope (Feb 2020) spill investigation; PAX (2023); New Lines/Placemark (2026); Kenyatta University sampling as reported; team compilation (Nov 2026)",
                          source_url="https://www.hoffnungszeichen.de/sites/default/files/documents/causing_a_black_tide_of_oil_-_south_sudans_polluting_pipeline_-_sign_of_hope.pdf"),
    "oil_wells_flooding": dict(category="environment", temporal="periods",
                               source="Sentinel-1 RTC radar (Microsoft Planetary Computer) at OpenStreetMap well locations; team analysis (Nov 2026)",
                               source_url="https://planetarycomputer.microsoft.com/dataset/sentinel-1-rtc"),
    "surface_water_quality": dict(category="environment", temporal="monthly",
                                  source="NASA HLS v2 (2020-2025) and Sentinel-2 L2A (2018-2019) via Microsoft Planetary Computer; team analysis (Nov 2026)",
                                  source_url="https://www.earthdata.nasa.gov/data/projects/hls"),
    "ethnic_groups": dict(category="human", temporal="periods", source="EPR-2023 / GeoEPR-2023 (ETH Zurich ICR); ACD2EPR-2021",
                          source_url=_egt.EPR_PAGE),
}
DETAILS = {
    "health": "Status periods from MoH Apr 2016 list, IOM DTM village assessment Aug 2019-Mar 2020 (7 counties), MoH 2023 master list and WHO MFL Mar 2024, matched by name and distance; 'new since 2016' facilities start at the first list that has them (opened between Apr 2016 and that list); facilities dropped by 2023 are 'unconfirmed' to Dec 2023; Ulang (closed 14 Apr 2025) and Old Fangak (bombed 3 May 2025) documented. 461 matched facilities lack coordinates and are not mapped. About 11.5% of 'new since 2016' sit within 300 m of a 2016 facility (likely renamed). Aggregate 2022 and 2025 aid-cut closures are timeline events. Superseded the WHO-MFL snapshot layer (all its points are included).",
    "schools": "SSSAMS 2015 list (coordinates) + SSSAMS 29 Oct 2019 enrolment export (joined on school code) + IOM DTM Aug 2019-Mar 2020 (392 DTM-only points, a few may duplicate SSSAMS); national COVID-19 closure 2020-03..2021-04; base status carried forward from 2021-05 (flagged 'presumed'). 2015 managed/enrolment-by-sex kept from the old layer. OpenStreetMap schools > 300 m from any SSSAMS/DTM school kept as undated. Heatwave closures (Mar 2024, Feb-Mar 2025) and flood closures are timeline events, not per-school periods.",
    "oil": "GEM GOGET field points (attributes kept; GEM status in gem_status) with production periods reconciled to the team block timeline; 102 OSM wells (HOT Raw Data API, Nov 2026) replace the 93 undated OSM wells and get their block's status periods: Blocks 3&7 operating -> halted 2024-02..2024-12 -> resumed 2025-01; Blocks 1,2&4 shut -> partial 2018-08 (Toma South) -> operating 2019-01 -> disrupted 2025-12 (Heglig seized 8 Dec 2025); Block 5A shut -> operating 2021-06 -> disrupted 2025-12. Block assignment by location (east of 31E = 3&7; Guit/Koch/Leer/Mayendit/Panyijiar = 5A). Block-level status, not well-by-well. Gas-flare satellite check (MODIS) was inconclusive and is not used.",
    "pipelines": "Overture/OSM pipeline lines and GEM GOIT routes; status periods follow the oil block of each line (location rule as for wells; Greater Nile follows Blocks 1,2&4). The team's 169 OSM field-line segments all lie on these lines.",
    "ethnic_groups": _egt.DETAILS,
    "gbv_one_stop_centres": "13 one-stop centres + Bentiu safe house; valid_from = first evidence of operation (year-only evidence -> end of that year); documented through Q1 2023 (UNFPA newsletter: 13 OSCs), presumed operating afterwards, a period that includes the 2025 funding cuts. No dated point data exist for women and girls' friendly spaces or protection desks.",
    "oil_pollution": "Spills on the Unity-Heglig export pipeline ~24 Aug 2019 (~2 million L) and ~28 Oct 2019 (~4 million L), GPS from Sign of Hope; after repair shown as spill site (removal not documented). Reports: flooded Block 2 wells (PAX 2023: 159 wells ~41% submerged; New Lines/Placemark 2026: 50+ of ~400 Unity wells underwater) placed at the Unity field; Kenyatta University river samples near Bentiu/Rotriak (lead up to 18 ug/L, hydrocarbons >5x limits; sampling dates unpublished) placed at Rotriak. Feb 2024 Petrodar spill is in Sudan -> timeline only.",
    "oil_wells_flooding": "Share of Sentinel-1 VV pixels below -15 dB in a 100-500 m ring around each of 102 OSM wells, monthly median; flagged when >= 25%. Undercounts flooded vegetation; near-zero 2021 likely an artefact (also Sentinel-1B loss Dec 2021). OSM maps ~100 of ~400 Unity wells.",
    "surface_water_quality": "Eight ~11x11 km sites; water pixels only, up to 3 clearest scenes per month. Status = NDTI (red-green)/(red+green) anomaly vs the site's median for that calendar month: > +0.04 more turbid, < -0.04 clearer (|anomaly| > 0.04 is about the top 20% of site-months). NDCI chlorophyll proxy included. 2018-19 Sentinel-2 L2A may be offset from 2020-25 HLS. Thar Jath wetland has only 15 months.",
}


def write_points_meta(status_values):
    lst = json.load(open(POINTS_META))
    by = {e["key"]: e for e in lst}
    for key, nm in NEW_META.items():
        by.setdefault(key, {"key": key})
        by[key].update(nm)
    for key, pl in PLAIN.items():
        e = by.setdefault(key, {"key": key, "category": "human"})
        old_notes = e.get("notes")
        if old_notes and old_notes != pl["notes"] and not e.get("details"):
            e["details"] = old_notes
        if key in DETAILS:
            e["details"] = DETAILS[key]
        e["label"], e["notes"] = pl["label"], pl["notes"]
        e["plain"] = True  # user-facing label/notes curated: other scripts keep them (points_temporal.update_points_meta)
        if key in status_values:
            e["status_values"] = status_values[key]
    for key in ("health", "schools", "oil", "pipelines"):
        by[key]["temporal"] = "periods"
    by["health"]["source"] = ("MoH health facility lists 2016 and 2023, IOM DTM village assessment 2019-20, WHO Master "
                              "Facility List Mar 2024 (HDX); team compilation (Nov 2026)")
    by["schools"]["source"] = ("SSSAMS 2015 list and 2019 enrolment export (HDX, CC0), IOM DTM village assessment "
                               "2019-20, OpenStreetMap (ODbL); team compilation (Nov 2026)")
    by["oil"]["source"] = ("Global Energy Monitor GOGET (CC-BY 4.0), OpenStreetMap wells (ODbL); block status dates "
                           "from Reuters, VOA, Radio Tamazuj, Sudan Tribune, Argus, AFP")
    for e in by.values():
        for k in ("notes", "label"):
            assert "`" not in e.get(k, ""), (e["key"], k)
    keys = [e["key"] for e in lst] + [k for k in by if k not in {e["key"] for e in lst}]
    with open(POINTS_META, "w") as f:
        json.dump([by[k] for k in keys], f, indent=1, ensure_ascii=False)


def status_values_of(fname, order):
    vals = Counter(f["properties"].get("status") for f in read_fc(fname)["features"])
    vals.pop(None, None)
    if order:
        missing = set(vals) - set(order)
        assert not missing, (fname, missing)
        return [v for v in order if v in vals]
    return [v for v, _ in vals.most_common()]


def refresh_layers_json():
    """Rewrite only the vector-layer list of docs/data/layers.json (same logic as build_web_data.py)."""
    import glob
    p = os.path.join(DOCS_DATA, "layers.json")
    lj = json.load(open(p)) if os.path.exists(p) else {"points": [], "rasters": []}
    meta = {e["key"]: e for e in json.load(open(POINTS_META))}
    pts = []
    for f in sorted(glob.glob(os.path.join(DOCS_DATA, "*.geojson"))):
        name = os.path.basename(f)
        if name == "counties.geojson":
            continue
        key = name.replace(".geojson", "")
        short = next((key[len(pre):] for pre in ("points_", "lines_", "polygons_") if key.startswith(pre)), key)
        info = dict(meta.get(short, meta.get(key, {})))
        info.update({"key": key, "file": f"data/{name}"})
        info.setdefault("label", short.replace("_", " ").title())
        info.setdefault("category", "human")
        pts.append(info)
    lj["points"] = pts
    with open(p, "w") as fh:
        json.dump(lj, fh, indent=1)


# --------------------------------------------------------------------------------------------- validation
def validate(layers):
    """valid_from <= valid_to, dates in 2018-2025, inside the bbox, no duplicate features, no overlapping periods per
    site; counts of features active in each year -> data/processed/validation/team_dynamic_layers_counts.csv."""
    rows, problems, mix = [], [], []
    years = range(2018, 2026)
    os.makedirs(os.path.join(ROOT, "data", "processed", "validation"), exist_ok=True)
    for fname, site_key in layers:
        fs = read_fc(fname)["features"]
        seen, per_site = set(), defaultdict(list)
        for f in fs:
            p = f["properties"]
            vf, vt = p.get("valid_from"), p.get("valid_to")
            for d in (vf, vt):
                if d is not None and not ("2018-01" <= str(d)[:7] <= "2025-12"):
                    problems.append((fname, "date outside window", p.get("name"), d))
            if vf and vt and str(vf)[:7] > str(vt)[:7]:
                problems.append((fname, "valid_from > valid_to", p.get("name"), vf, vt))
            if "date_basis" not in p or "status" not in p:
                problems.append((fname, "missing date_basis/status", p.get("name")))
            g = f["geometry"]
            coords = json.dumps(g["coordinates"])
            nums = [float(x) for x in re.findall(r"-?\d+\.?\d*", coords)]
            lons, lats = nums[0::2], nums[1::2]
            inside = [BBOX[0] <= x <= BBOX[2] and BBOX[1] <= y <= BBOX[3] for x, y in zip(lons, lats)]
            # points/polygons: every vertex inside; lines: start inside (GEM export routes continue into Sudan)
            if not (inside[0] if g["type"].endswith("LineString") else all(inside)):
                problems.append((fname, "outside bbox", p.get("name")))
            k = json.dumps([g, p], sort_keys=True)
            if k in seen:
                problems.append((fname, "duplicate feature", p.get("name")))
            seen.add(k)
            sk = p.get(site_key) if site_key else coords + str(p.get("name"))
            per_site[(sk, coords)].append((str(vf or "0000-00")[:7], str(vt or "9999-99")[:7]))
        for sk, per in per_site.items():
            per.sort()
            for a, b in zip(per, per[1:]):
                if b[0] <= a[1]:
                    problems.append((fname, "overlapping periods", sk[0], a, b))
                    break
        row = {"layer": fname.replace(".geojson", ""), "features": len(fs), "sites": len(per_site)}
        for y in years:  # distinct sites shown at some point in the year
            row[str(y)] = len({sk for sk, per in per_site.items() if any(a[:4] <= str(y) <= b[:4] for a, b in per)})
        rows.append(row)
        for y in years:  # status mix in July of each year
            m = f"{y}-07"
            c = Counter(f["properties"].get("status") for f in fs
                        if str(f["properties"].get("valid_from") or "0000-00")[:7] <= m <= str(f["properties"].get("valid_to") or "9999-99")[:7])
            mix.extend({"layer": fname.replace(".geojson", ""), "month": m, "status": k, "features": v} for k, v in c.items())
    pd.DataFrame(mix).to_csv(os.path.join(ROOT, "data", "processed", "validation", "team_dynamic_layers_status_july.csv"), index=False)
    out = pd.DataFrame(rows)
    vd = os.path.join(ROOT, "data", "processed", "validation")
    os.makedirs(vd, exist_ok=True)
    out.to_csv(os.path.join(vd, "team_dynamic_layers_counts.csv"), index=False)
    print("\nDistinct sites shown in each year:")
    print(out.to_string(index=False))
    for pr in problems[:30]:
        print("PROBLEM", pr)
    print(f"validation problems: {len(problems)}")
    return problems


def main():
    layers = [health(), schools(), oil(), ("lines_pipelines.geojson", None), ethnic(), gbv_centres(),
              oil_pollution(), wells_flooding(), surface_water()]
    sv = {
        "health": status_values_of("points_health.geojson", HEALTH_ORDER),
        "schools": status_values_of("points_schools.geojson", SCHOOL_ORDER),
        "oil": status_values_of("points_oil.geojson", OIL_ORDER),
        "pipelines": status_values_of("lines_pipelines.geojson", OIL_ORDER),
        "ethnic_groups": status_values_of("polygons_ethnic_groups.geojson", ETHNIC_ORDER),
        "gbv_one_stop_centres": status_values_of("points_gbv_one_stop_centres.geojson", PLAIN["gbv_one_stop_centres"]["order"]),
        "oil_pollution": status_values_of("points_oil_pollution.geojson", POLL_ORDER),
        "oil_wells_flooding": status_values_of("points_oil_wells_flooding.geojson", FLOOD_ORDER),
        "surface_water_quality": status_values_of("points_surface_water_quality.geojson", WQ_ORDER),
    }
    if any("status" in f["properties"] for f in read_fc("points_water_points.geojson")["features"]):
        sv["water_points"] = status_values_of("points_water_points.geojson", None)
    write_points_meta(sv)
    refresh_layers_json()
    context_events()
    county_series()
    validate(layers)


if __name__ == "__main__":
    main()
    from trend_stats import write_trends
    write_trends("sector_partners")  # Mann-Kendall + Sen's slope (scripts/trend_stats.py)
