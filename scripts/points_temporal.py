"""Shared helpers for time-dynamic point layers (docs/data/points_*.geojson).

Temporal standard applied to every feature of every point/line/polygon layer:
  valid_from  "YYYY-MM" or null  (null = already present before 2018-01)
  valid_to    "YYYY-MM" or null  (null = still present at the end of 2025-12)
  date_basis  free text: how the dates are known ("UN map 4456 Rev.62 Jan 2025", "Geo-PKO",
              "WFP first/last price month", "snapshot only", ...)
Event layers keep a single `date` (YYYY-MM-DD) instead and get valid_from = valid_to = YYYY-MM of `date`.
A site whose attributes change over time is emitted as one feature per period.

The app shows a feature in month m when (valid_from is null or valid_from <= m) and (valid_to is null or m <= valid_to).
"""
import json
import os
import re

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DATA = os.path.join(ROOT, "docs", "data")
WINDOW = ("2018-01", "2025-12")
GAZ_XLSX = os.path.join(ROOT, "data", "raw", "gazetteer", "ssd_populatedplaces_tabular.xlsx")
GAZ_URL = "https://data.humdata.org/dataset/south-sudan-settlement-data"


def ym(x):
    """Anything date-like -> 'YYYY-MM' (or None)."""
    if x is None or (isinstance(x, float) and pd.isna(x)) or x == "":
        return None
    if isinstance(x, (int,)) or (isinstance(x, str) and re.fullmatch(r"\d{4}", x)):
        return f"{int(x):04d}-01"
    return pd.Timestamp(x).strftime("%Y-%m")


def ym_add(m, k):
    p = pd.Period(m, "M") + k
    return p.strftime("%Y-%m")


def clip_window(vf, vt):
    """Normalise to the app window: valid_from before 2018-01 -> None, valid_to after 2025-12 -> None.
    Returns (vf, vt) or None when the period lies completely outside the window."""
    if vt is not None and vt < WINDOW[0]:
        return None
    if vf is not None and vf > WINDOW[1]:
        return None
    if vf is not None and vf <= WINDOW[0]:
        vf = None
    if vt is not None and vt >= WINDOW[1]:
        vt = None
    return vf, vt


def read_fc(name):
    with open(os.path.join(DOCS_DATA, name)) as f:
        return json.load(f)


def write_fc(name, feats, precision=5):
    def rnd(c):
        if isinstance(c, (list, tuple)):
            return [rnd(v) for v in c]
        return round(c, precision) if isinstance(c, float) else c
    for f in feats:
        g = f.get("geometry")
        if g and "coordinates" in g:
            g["coordinates"] = rnd(g["coordinates"])
        for k, v in list(f["properties"].items()):
            if isinstance(v, float) and pd.isna(v):
                f["properties"][k] = None
    with open(os.path.join(DOCS_DATA, name), "w") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f, separators=(",", ":"), ensure_ascii=False)


def point(lon, lat, props):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]}, "properties": props}


def set_validity(props, vf, vt, basis):
    """Insert the three temporal fields right after name/type (keeps the files readable)."""
    props["valid_from"] = vf
    props["valid_to"] = vt
    props["date_basis"] = basis
    return props


def tag_meta(key, extra_note=None):
    """Add `temporal` (and optionally a note sentence) to an existing points.json entry."""
    p = os.path.join(ROOT, "data", "processed", "meta", "points.json")
    lst = json.load(open(p))
    for e in lst:
        if e.get("key") == key:
            e["temporal"] = TEMPORAL.get(key, e.get("temporal"))
            if extra_note and extra_note not in e.get("notes", ""):
                e["notes"] = (e.get("notes", "") + " " + extra_note).strip()
    with open(p, "w") as f:
        json.dump(lst, f, indent=1, ensure_ascii=False)


def stamp_events(name, date_field="date", basis=None):
    """Event layer: verify `date`, set valid_from = valid_to = YYYY-MM(date)."""
    fc = read_fc(name)
    bad = 0
    for f in fc["features"]:
        p = f["properties"]
        d = p.get(date_field)
        try:
            m = pd.Timestamp(d).strftime("%Y-%m")
        except Exception:
            m, bad = None, bad + 1
        set_validity(p, m, m, basis or "event date")
    write_fc(name, fc["features"])
    return len(fc["features"]), bad


# ----------------------------------------------------------------------------------------------- gazetteer
_GAZ = None
ALIASES = {"Maban": "Bunj", "Warrap Town": "Warrap", "Tonj Town": "Tonj", "Pibor": "Pibor Town", "Raja": "Raja",
           "Motot": "Mwot Tot", "Pochalla": "Pochala", "Bunj/Maban": "Bunj", "Kuacjok": "Kuajok"}
HINT = {"Keew": "Fangak", "Manajang": "Fangak", "Pigi": "Fangak", "Mboro": "Wau", "Nyamlel": "Aweil West",
        "Mabior": "Twic East", "Nyal": "Panyijiar", "Akobo": "Akobo", "Yida": "Pariang", "Ayod": "Ayod",
        "Malakal": "Malakal", "Wau": "Wau", "Rumbek": "Rumbek Centre", "Bor": "Bor South", "Juba": "Juba",
        "Lankien": "Nyirol", "Leer": "Leer", "Koch": "Koch", "Kapoeta": "Kapoeta South", "Melut": "Melut",
        "Tonj": "Tonj South", "Yambio": "Yambio", "Torit": "Torit"}
# (lon, lat, how) for names the gazetteer lacks or places wrongly; positions read off the Logistics Cluster
# CONOPS map pins (georeferenced on the map graticule, +-5 km) or approximate.
MANUAL = {
    "Ganyiel": (30.48, 7.39, "read off CONOPS map pin (Panyijiar county)"),
    "Majak Bol": (28.04, 9.07, "read off CONOPS map pin"),
    "Twic": (28.51, 8.80, "read off CONOPS Sep 2019 map pin (Twic county)"),
    "Agok": (28.60, 9.35, "approximate (Agok, Abyei Administrative Area)"),
    "Mingkaman": (31.4716, 6.194, "OCHA gazetteer (Mingkaman IDP settlement)"),
    "New Fangak": (31.1263, 9.4039, "OCHA gazetteer, verified against CONOPS map pin"),
    "Canal": (31.5502, 9.3638, "OCHA gazetteer (Canal, Canal/Pigi county)"),
}


def geocode(name):
    """Town name -> (lon, lat, coord_source, coord_quality). OCHA COD settlements, best class first."""
    global _GAZ
    if name in MANUAL:
        lon, lat, how = MANUAL[name]
        return lon, lat, how, ("approximate" if "approx" in how or "pin" in how else "town")
    if _GAZ is None:
        _GAZ = pd.read_excel(GAZ_XLSX)
        _GAZ["cls"] = _GAZ.popPlaceCl.map({1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 8: 5, 7: 6, 6: 7, 0: 8})
    q = ALIASES.get(name, name)
    g = _GAZ
    m = g[(g.featureNam.str.lower() == q.lower()) | (g.featureAlt.astype(str).str.lower() == q.lower())]
    if name in HINT and (m.admin2Name == HINT[name]).any():
        m = m[m.admin2Name == HINT[name]]
    if m.empty:
        return None
    r = m.sort_values("cls").iloc[0]
    return float(r.POINT_X), float(r.POINT_Y), f"OCHA COD settlements gazetteer ({r.featureNam}, {r.popPlace_1}, {r.admin2Name})", "town"


def periods_from_snapshots(snap_dates, present, attrs_by_date):
    """Generic run-length: snap_dates sorted 'YYYY-MM'; present[d] bool; attrs_by_date[d] hashable attribute tuple.
    Returns list of (valid_from, valid_to, attrs, first_snapshot, last_snapshot). A period starts at the first snapshot
    where the site appears (or attributes change) and ends the month before the next snapshot where it is absent/changed."""
    out, cur = [], None
    for i, d in enumerate(snap_dates):
        if present.get(d):
            a = attrs_by_date.get(d)
            if cur and cur[2] == a:
                cur[4] = d
                continue
            if cur:
                cur[1] = ym_add(d, -1)
                out.append(tuple(cur))
            cur = [d if i > 0 else None, None, a, d, d]
        else:
            if cur:
                cur[1] = ym_add(d, -1)
                out.append(tuple(cur))
                cur = None
    if cur:
        out.append(tuple(cur))
    return out


# how each layer's valid_from/valid_to were obtained (copied into points.json as `temporal`)
TEMPORAL = {"logcluster_hubs": "periods", "unmiss": "periods", "markets": "periods", "fmr_monitoring": "periods",
            "crisis_sites": "periods", "oil": "periods", "ucdp_events": "events", "insecurity_insight": "events",
            "health": "snapshot", "schools": "snapshot", "pipelines": "snapshot", "water_points": "snapshot"}


def update_points_meta(entry):
    if entry["key"] in TEMPORAL:
        entry.setdefault("temporal", TEMPORAL[entry["key"]])
    p = os.path.join(ROOT, "data", "processed", "meta", "points.json")
    lst = json.load(open(p)) if os.path.exists(p) else []
    lst = [e for e in lst if e.get("key") != entry["key"]] + [entry]
    with open(p, "w") as f:
        json.dump(lst, f, indent=1, ensure_ascii=False)


def assign_county_fc(feats):
    """Add county_id (OCHA P-code) via point-in-polygon for point features lacking it."""
    import geopandas as gpd
    from shapely.geometry import Point
    cty = gpd.read_file(os.path.join(ROOT, "data", "counties.geojson"))[["district_id", "geometry"]]
    pts = gpd.GeoDataFrame({"i": range(len(feats))},
                           geometry=[Point(f["geometry"]["coordinates"]) for f in feats], crs=4326)
    j = gpd.sjoin(pts, cty.to_crs(4326), how="left", predicate="within").drop_duplicates("i").set_index("i")
    for i, f in enumerate(feats):
        if not f["properties"].get("county_id"):
            v = j.district_id.get(i)
            f["properties"]["county_id"] = v if isinstance(v, str) else None
    return feats
