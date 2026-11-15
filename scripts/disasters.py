"""Natural disasters / extreme weather events in South Sudan 2018-2025 -> docs/data/points_disasters.geojson.

One feature per event (flood season, drought alert, heatwave) per affected county, placed at the county centre
(data/counties.geojson lat/lon), or per state / nationwide when the source gives no county. Every feature has
valid_from / valid_to (YYYY-MM) so it stays visible on the time slider while the event lasted; there is no `date`
property on purpose (the app would then show the feature in a single month only). Epidemics (cholera, measles,
Ebola readiness ...) are NOT weather disasters and are excluded.

Sources (all downloaded files are read from a cache directory, see CACHE below):
 * OCHA South Sudan "Flood Data" on HDX - county tables of people affected (and displaced, 2025):
   https://data.humdata.org/dataset/south-sudan-flood-data
     2021 season: ss_floodsaffected_people_20211213.xlsx (as of 13 Dec 2021; per-county month of flooding)
     2022 season: ssd_flood_response_301122.xlsx (as of end Nov 2022)
     2024 season: ssd_flood_response_20122024.xlsx (as of 20 Dec 2024)
     2025 season: ss_people_affected_and_displaced_by_floods_20251130.xlsx (as of 30 Nov 2025)
 * 2019 season: OCHA Seasonal Flooding Update #3 (5 Nov 2019) map - the 32 named flood-affected counties (OCHA text:
   908,000 affected in 32 counties); people displaced per county from IOM DTM / IRNA / RRC location list of
   29 Oct 2019 (HDX south-sudan-flood-locations). June 2019 Northern Bahr el Ghazal flood: IFRC DREF MDRSS008.
 * 2020 season: OCHA Flooding Snapshot (21 Oct 2020) map - the 39 named flood-affected counties; state totals from
   the OCHA/ICCG Flooding Situation Report of 31 Jan 2021 (period 1 Jul 2020 - 31 Jan 2021).
 * GDACS (EC JRC) event API: agricultural drought alerts (polygons -> counties covering >= 25 % of the county) and
   the May 2018 flood alert near Bor (no OCHA flood data exist for 2018).
 * Heatwaves: national school closures 18 Mar - early Apr 2024 and from 21 Feb 2025 (Radio Tamazuj, AP).
No OCHA county flood table was found for 2023 (no GLIDE flood event for 2023 either), so 2023 has no flood features.

Run (downloads are untrusted data -> isolated interpreter):
    python3 -I scripts/disasters.py [--cache DIR]
Writes docs/data/points_disasters.geojson, data/processed/disasters_events.csv, and the layer entries in
data/points_labels.json and data/processed/meta/points.json (picked up by build_web_data.py -> layers.json).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from collections import Counter

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from points_temporal import ROOT, write_fc  # noqa: E402

HDX = "https://data.humdata.org/dataset/south-sudan-flood-data"
HDX_RES = "https://data.humdata.org/dataset/70cefa0a-e4bd-481e-b773-20c2a462ea2e/resource/"
FILES = {
    "2021": HDX_RES + "1f91a97c-5c60-4375-8e5d-8967f764cbac/download/ss_floodsaffected_people_20211213.xlsx",
    "2022": HDX_RES + "918b0b51-30d3-4d46-b0c5-1688bdf27b8e/download/ssd_flood_response_301122.xlsx",
    "2024": HDX_RES + "eed79fad-e7d2-4890-881d-de8e0ec88a41/download/ssd_flood_response_20122024.xlsx",
    "2025": HDX_RES + "eb064156-f948-4520-8e2c-3b271badbd5c/download/ss_people_affected_and_displaced_by_floods_20251130.xlsx",
    "2019dtm": "https://data.humdata.org/dataset/a0a190d5-09af-49a8-87ba-83d91bfdab30/resource/"
               "7c454f75-ea6e-4361-98ab-e12baa31cb20/download/20191029_dtm_floods_locations.xlsx",
}
GDACS_LIST = ("https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH?eventlist=FL;DR;TC;EQ;WF;VO"
              "&country=South%20Sudan&fromdate={y}-01-01&todate={y}-12-31&alertlevel=green;orange;red&pagesize=100")
GDACS_GEOM = "https://www.gdacs.org/gdacsapi/api/polygons/getgeometry?eventtype={t}&eventid={i}&episodeid={e}"
GDACS_REPORT = "https://www.gdacs.org/report.aspx?eventid={i}&episodeid={e}&eventtype={t}"

STATES = {"SS00": "Abyei Administrative Area", "SS01": "Central Equatoria", "SS02": "Eastern Equatoria",
          "SS03": "Jonglei (incl. Greater Pibor)", "SS04": "Lakes", "SS05": "Northern Bahr el Ghazal",
          "SS06": "Unity", "SS07": "Upper Nile", "SS08": "Warrap", "SS09": "Western Bahr el Ghazal",
          "SS10": "Western Equatoria"}
ALIAS = {"pigi / canal": "Canal/Pigi", "panyijar": "Panyijiar", "nasir": "Luakpiny/Nasir", "jur": "Jur River",
         "bor": "Bor South", "manyom": "Mayom", "abyei administrative area": "Abyei", "kajo-keji": "Kajo-keji",
         "rumbek center": "Rumbek Centre"}

# ---- 2019: counties named on the OCHA Seasonal Flooding Update #3 map (5 Nov 2019); OCHA: 908,000 affected in 32
U2019 = "https://reliefweb.int/report/south-sudan/south-sudan-seasonal-flooding-update-3-05-november-2019"
C2019 = ["Maban", "Abiemnhom", "Aweil North", "Twic", "Mayom", "Longochuk", "Luakpiny/Nasir", "Gogrial East",
         "Maiwut", "Gogrial West", "Ulang", "Nyirol", "Aweil Centre", "Ayod", "Tonj North", "Mayendit", "Tonj East",
         "Rumbek North", "Duk", "Uror", "Akobo", "Pochalla", "Twic East", "Bor South", "Pibor", "Lafon",
         "Kapoeta North", "Kapoeta East", "Juba", "Kapoeta South", "Torit", "Budi"]
# ---- 2020: counties named on the OCHA Flooding Snapshot map (21 Oct 2020; "Thirty-nine counties have been affected")
U2020 = "https://reliefweb.int/report/south-sudan/south-sudan-flooding-snapshot-21-october-2020"
U2020_SITREP = ("https://docs.southsudanngoforum.org/sites/default/files/2021-02/"
                "south_sudan_flooding_situation_report_31jan2021_1.pdf")
C2020 = ["Renk", "Fashoda", "Pariang", "Panyikang", "Longochuk", "Mayom", "Aweil West", "Fangak", "Canal/Pigi",
         "Gogrial East", "Luakpiny/Nasir", "Koch", "Maiwut", "Nyirol", "Leer", "Ayod", "Mayendit", "Tonj East", "Duk",
         "Panyijiar", "Rumbek Centre", "Pochalla", "Cueibet", "Twic East", "Yirol East", "Tonj South", "Rumbek East",
         "Yirol West", "Bor South", "Pibor", "Awerial", "Wulu", "Terekeka", "Ibba", "Maridi", "Mundri East",
         "Mundri West", "Juba", "Uror"]
# state totals, OCHA/ICCG Flooding Situation Report 31 Jan 2021 (1 Jul 2020 - 31 Jan 2021); Jonglei incl. GPAA
S2020 = {"SS03": 495000, "SS04": 147000, "SS06": 126000, "SS07": 100000, "SS08": 60000, "SS10": 53000,
         "SS01": 40000, "SS05": 15000}

SEASONS = {  # season: (valid_from, valid_to, GLIDE, reliefweb disaster page, what the end month means)
    "2019": ("2019-07", "2019-12", "FL-2019-000062-SSD", "https://reliefweb.int/disaster/fl-2019-000062-ssd",
             "severe flooding from July 2019 (OCHA); end set to December 2019 when OCHA's flood updates stop"),
    "2020": ("2020-07", "2021-01", "FL-2020-000193-SSD", "https://reliefweb.int/disaster/fl-2020-000193-ssd",
             "OCHA/ICCG situation report period 1 Jul 2020 - 31 Jan 2021"),
    "2021": ("2021-05", "2021-12", "FL-2021-000108-SSD", "https://reliefweb.int/disaster/fl-2021-000108-ssd",
             "OCHA: flooding since May 2021; county month of flooding where OCHA's table gives one; data as of "
             "13 Dec 2021 (in parts of Unity and Jonglei the water did not recede for years)"),
    "2022": ("2022-07", "2022-12", "FL-2021-000108-SSD", "https://reliefweb.int/disaster/fl-2021-000108-ssd",
             "OCHA/WHO: severe flooding since July 2022; data as of end November 2022"),
    "2024": ("2024-07", "2024-12", "FL-2024-000145-SSD", "https://reliefweb.int/disaster/fl-2024-000145-ssd",
             "GLIDE event July 2024 (OCHA: heavy rains since May, first affected count end Aug); data as of 20 Dec 2024"),
    "2025": ("2025-07", "2025-12", "FL-2025-000158-SSD", "https://reliefweb.int/disaster/fl-2025-000158-ssd",
             "GLIDE event July 2025 (OCHA first report 31 Jul 2025); data as of 30 Nov 2025, end not yet reported"),
}

END_LABEL = {"2019": "2019-12 (approximate: last OCHA flood update)", "2020": "2021-01 (end of OCHA reporting period)",
             "2021": "2021-12 (last OCHA table, 13 Dec 2021; water stayed for years in parts of Unity and Jonglei)",
             "2022": "2022-12 (approximate: last OCHA table, end Nov 2022)",
             "2024": "2024-12 (approximate: last OCHA table, 20 Dec 2024)",
             "2025": "still ongoing at the last OCHA table (30 Nov 2025)"}

CACHE = os.environ.get("DISASTER_CACHE", os.path.join(ROOT, "data", "raw", "disasters", "_cache"))


def fetch(url, name):
    p = os.path.join(CACHE, name)
    if not os.path.exists(p):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research map)"})
        with urllib.request.urlopen(req, timeout=180) as r, open(p, "wb") as f:
            f.write(r.read())
    return p


def counties():
    d = json.load(open(os.path.join(ROOT, "data", "counties.geojson")))
    return {f["properties"]["district_id"]: f for f in d["features"]}


CTY = None
BY_NAME = None


def cid(name):
    n = str(name).strip()
    n = ALIAS.get(n.lower(), n)
    hit = BY_NAME.get(n.lower())
    assert hit, f"unknown county {name!r}"
    return hit


def num(x):
    try:
        v = float(x)
        return None if pd.isna(v) else int(round(v))
    except (TypeError, ValueError):
        return None


def county_feature(code, props):
    p = CTY[code]["properties"]
    props.setdefault("County", p["name"])
    props["State"] = STATES[code[:4]]
    props.setdefault("Where the dot is", "County centre (the source reports whole counties, not exact places)")
    props["county_id"] = code
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(p["lon"], 4), round(p["lat"], 4)]},
            "properties": props}


def state_centre(code):
    import geopandas as gpd
    g = gpd.read_file(os.path.join(ROOT, "data", "counties.geojson"))
    g = g[g.district_id.str[:4] == code].to_crs(6933).union_all().representative_point()
    pt = gpd.GeoSeries([g], crs=6933).to_crs(4326).iloc[0]
    return [round(pt.x, 4), round(pt.y, 4)]


def flood(season, code, affected=None, displaced=None, vf=None, evidence="", src_url=HDX, source="", extra=None):
    s0, s1, glide, rw, basis = SEASONS[season]
    vf = vf or s0
    yr = season
    props = {"name": f"Floods {yr} - {CTY[code]['properties']['name']}",
             "status": "flood-affected (reported)",
             "valid_from": vf, "valid_to": s1,
             "evidence": evidence, "date_basis": basis,
             "Type": "flood", "Started": vf, "Ended": END_LABEL[season],
             "People affected": affected, "People displaced": displaced}
    if extra:
        props.update(extra)
    props.update({"Disaster ID (GLIDE)": glide, "Source": source, "source_url": src_url, "Disaster page": rw})
    return county_feature(code, props)


# --------------------------------------------------------------------------------------------- OCHA tables
def season_2019():
    out = []
    d = pd.read_excel(fetch(FILES["2019dtm"], "20191029_dtm_floods_locations.xlsx"), sheet_name=0)
    d = d[d.source.notna()].copy()
    d["code"] = d["_county"].map(cid)  # the file's own P-codes are partly outdated (e.g. Nyirol)
    rep = d.groupby("code").agg(ppl=("idp_inds", "sum"), src=("source", lambda s: ", ".join(sorted(set(s)))),
                                when=("date_reported", "max"))
    for n in C2019:
        c = cid(n)
        r = rep.loc[c] if c in rep.index else None
        ppl = num(r.ppl) if r is not None else None
        ev = "Named as flood-affected on OCHA's Seasonal Flooding Update #3 map (5 Nov 2019; 908,000 people affected in 32 counties)."
        extra = {}
        if r is not None and ppl:
            when = r.when.strftime("%d %b %Y") if pd.notna(r.when) else "Oct 2019"
            if n == "Maban":  # ICWG figure = refugees + hosts affected (UNHCR 18 Oct 2019: nearly 200,000 affected)
                extra["People affected"] = ppl
                ev += f" About {ppl:,} refugees and hosts affected (ICWG Malakal, {when})."
                ppl = None
            else:
                ev += f" {ppl:,} people displaced by floods reported by {r.src} ({when}; IOM DTM flood location list)."
        f = flood("2019", c, displaced=ppl, evidence=ev, src_url=U2019,
                  source="OCHA Seasonal Flooding Update #3 (5 Nov 2019); IOM DTM / IRNA / RRC flood location list (HDX, 29 Oct 2019)",
                  extra=extra)
        if extra.get("People affected"):
            f["properties"]["People affected"] = extra["People affected"]
        out.append(f)
    # Tonj South: OCHA (cited on ReliefWeb FL-2019-000062-SSD) 13,000 displaced, with 33,000 in Maiwut, by July 2019
    out.append(flood("2019", cid("Tonj South"), displaced=13000,
                     evidence="OCHA (summarised on ReliefWeb disaster page FL-2019-000062-SSD): an estimated 46,000 people "
                              "displaced in Maiwut (33,000) and Tonj South (13,000) in mid-2019.",
                     src_url="https://reliefweb.int/disaster/fl-2019-000062-ssd", source="OCHA via ReliefWeb"))
    # June 2019 Northern Bahr el Ghazal flash flood (IFRC DREF): three unnamed counties -> state point
    out.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": state_centre("SS05")}, "properties": {
        "name": "Floods June 2019 - Northern Bahr el Ghazal", "status": "flood-affected (reported)",
        "valid_from": "2019-06", "valid_to": "2019-06",
        "evidence": "Flooding on 5-7 June 2019 displaced some 7,780 households (about 46,680 people) in three counties of "
                    "former Northern Bahr el Ghazal state (IFRC DREF MDRSS008, South Sudan Red Cross rapid assessment).",
        "date_basis": "flood dates 5-7 June 2019 (IFRC)", "Type": "flood", "Started": "2019-06-05", "Ended": "2019-06-07",
        "People affected": None, "People displaced": 46680, "State": STATES["SS05"],
        "Where the dot is": "Centre of the state (the source does not name the three counties)",
        "Disaster ID (GLIDE)": "FL-2019-000062-SSD", "Source": "IFRC GO emergency 3611 / DREF MDRSS008",
        "source_url": "https://go.ifrc.org/emergencies/3611", "Disaster page": "https://reliefweb.int/disaster/fl-2019-000062-ssd"}})
    return out


def season_2020():
    out = []
    for n in C2020:
        c = cid(n)
        st = c[:4]
        out.append(flood("2020", c, evidence=(
            "Named as flood-affected on OCHA's Flooding Snapshot map (21 Oct 2020: 39 counties affected). OCHA gives only "
            f"state totals: about {S2020[st]:,} people affected in {STATES[st]} between July 2020 and January 2021."),
            src_url=U2020, source="OCHA Flooding Snapshot (21 Oct 2020); OCHA/ICCG Flooding Situation Report (31 Jan 2021)",
            extra={"People affected in the state": S2020[st]}))
    return out


def month_of(v, default):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return default
    if isinstance(v, (pd.Timestamp,)) or hasattr(v, "month"):
        return f"2021-{v.month:02d}"  # 'Aug-21' cells were parsed as 21 Aug: only the month is meaningful
    s = str(v).lower()
    for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]):
        if m in s:
            return f"2021-{i + 1:02d}"
    m = re.search(r"\d{1,2}/(\d{1,2})/2021", s)
    return f"2021-{int(m.group(1)):02d}" if m else default


def season_2021():
    p = fetch(FILES["2021"], "ss_floodsaffected_people_20211213.xlsx")
    s2 = pd.read_excel(p, sheet_name="Sheet2", header=None).iloc[1:, 6:10]
    s2.columns = ["st", "county", "pop", "aff"]
    s2 = s2[s2.county.notna() & (s2.st != "Total")]
    s1 = pd.read_excel(p, sheet_name="Sheet1").iloc[:, :6]
    s1.columns = ["state", "county", "where", "month", "pop", "aff"]
    months = {}
    for r in s1[s1.county.notna()].itertuples():
        if r.county.strip() == "Ayod Islands":
            continue
        c = cid(r.county)
        m = month_of(r.month, "")  # "" = a row of this county without a month -> season start
        if c not in months or m < months[c]:
            months[c] = m
    months = {c: m for c, m in months.items() if m}
    out = []
    for r in s2.itertuples():
        c = cid(r.county)
        vf = months.get(c, SEASONS["2021"][0])
        aff = num(r.aff)
        out.append(flood("2021", c, affected=aff, vf=vf, evidence=(
            f"OCHA county table as of 13 Dec 2021: {aff:,} people affected"
            + (f"; flooding reported from {pd.Period(vf, 'M').strftime('%B %Y')}" if c in months else "")
            + ". OCHA national total 835,693 in 33 counties."),
            source="OCHA South Sudan flood data, HDX (13 Dec 2021)"))
    return out


def season_2022():
    d = pd.read_excel(fetch(FILES["2022"], "ssd_flood_response_301122.xlsx"), header=None).iloc[2:]
    out = []
    for r in d.itertuples(index=False):
        aff = num(r[4])
        if not aff:
            continue
        out.append(flood("2022", cid(r[2]), affected=aff, evidence=(
            f"OCHA county table as of end November 2022: {aff:,} people assessed as flood-affected (verified figures; the "
            "government reported higher numbers)."), source="OCHA South Sudan flood data, HDX (30 Nov 2022)"))
    return out


def season_2024():
    d = pd.read_excel(fetch(FILES["2024"], "ssd_flood_response_20122024.xlsx"), header=None).iloc[1:]
    out = []
    for r in d.itertuples(index=False):
        aff = num(r[4])
        if not aff or not isinstance(r[3], str):
            continue
        out.append(flood("2024", r[3] if r[3] in CTY else cid(r[2]), affected=aff, evidence=(
            f"OCHA county table as of 20 Dec 2024: {aff:,} people affected (national total 1,416,678)."),
            source="OCHA South Sudan flood data, HDX (20 Dec 2024)"))
    return out


def season_2025():
    d = pd.read_excel(fetch(FILES["2025"], "ss_people_affected_and_displaced_by_floods_20251130.xlsx"), header=None).iloc[1:]
    out = []
    for r in d.itertuples(index=False):
        aff = num(r[4])
        if not aff:
            continue
        dis = num(r[5])
        out.append(flood("2025", r[3], affected=aff, displaced=dis, evidence=(
            f"OCHA county table as of 30 Nov 2025: {aff:,} people affected"
            + (f", {dis:,} displaced" if dis else "") + "."),
            source="OCHA South Sudan flood data, HDX (30 Nov 2025)"))
    return out


# ------------------------------------------------------------------------------------------------- GDACS
def gdacs():
    import geopandas as gpd
    from shapely.geometry import shape
    cty = gpd.read_file(os.path.join(ROOT, "data", "counties.geojson")).to_crs(6933)
    cty["a"] = cty.area
    out = []
    for y in range(2018, 2026):
        p = fetch(GDACS_LIST.format(y=y), f"gdacs_{y}.json")
        if os.path.getsize(p) == 0:
            continue
        for ev in json.load(open(p))["features"]:
            q = ev["properties"]
            t, i, e = q["eventtype"], q["eventid"], q["episodeid"]
            if t == "FL" and y != 2018:
                continue  # 2019-2025 floods come from OCHA county tables (GDACS has one point per season)
            vf, vt = q["fromdate"][:7], q["todate"][:7]
            sev = (q.get("severitydata") or {}).get("severitytext", "").strip()
            alert = q.get("alertlevel", "").capitalize()
            rep = GDACS_REPORT.format(t=t, i=i, e=e)
            if t == "FL":
                code = gpd.sjoin(gpd.GeoDataFrame(geometry=[shape(ev["geometry"])], crs=4326).to_crs(6933),
                                 cty, predicate="within").district_id.iloc[0]
                out.append(county_feature(code, {
                    "name": f"Flood alert {q['fromdate'][:7]} - {CTY[code]['properties']['name']}",
                    "status": f"flood alert ({alert.lower()})", "valid_from": vf, "valid_to": vt,
                    "evidence": f"GDACS {alert} flood alert {q['fromdate'][:10]} to {q['todate'][:10]} (source {q.get('source')}). "
                                "Green = minor; no people-affected figures were published. No OCHA flood figures exist for 2018.",
                    "date_basis": "GDACS event dates", "Type": "flood", "Started": q["fromdate"][:10],
                    "Ended": q["todate"][:10], "Disaster ID (GLIDE)": q.get("glide") or None,
                    "Source": "GDACS (European Commission JRC / UN)", "source_url": rep}))
                continue
            g = gpd.read_file(fetch(GDACS_GEOM.format(t=t, i=i, e=e), f"gdacs_geom_{t}_{i}_{e}.json"))
            poly = g[g.geometry.geom_type.str.contains("Polygon")].to_crs(6933).union_all()
            hit = cty[cty.intersects(poly)].copy()
            hit["share"] = hit.geometry.intersection(poly).area / hit.a
            hit = hit[hit.share >= 0.25]
            for r in hit.itertuples():
                out.append(county_feature(r.district_id, {
                    "name": f"Drought {vf[:4]} - {r.name}",
                    "status": f"agricultural drought alert ({alert.lower()})", "valid_from": vf, "valid_to": vt,
                    "evidence": (f"GDACS {alert} agricultural drought alert {q['fromdate'][:10]} to {q['todate'][:10]} "
                                 f"({sev}; European Drought Observatory). The alert area covers {r.share:.0%} of this county."),
                    "date_basis": "GDACS event dates (satellite/model drought indicators, not ground reports)",
                    "Type": "drought (crop and pasture stress)", "Started": q["fromdate"][:10], "Ended": q["todate"][:10],
                    "Share of county in alert area": f"{r.share:.0%}",
                    "Disaster ID (GLIDE)": q.get("glide") or None,
                    "Source": "GDACS (European Commission JRC / UN), drought data from the Global Drought Observatory",
                    "source_url": rep}))
    return out


def heatwaves():
    juba = CTY["SS0101"]["properties"]
    pt = {"type": "Point", "coordinates": [round(juba["lon"], 4), round(juba["lat"], 4)]}
    base = {"Type": "heatwave", "Where the dot is": "Juba, where the national decision was announced; the heatwave and "
                                                    "school closures were nationwide", "State": "nationwide"}
    return [
        {"type": "Feature", "geometry": pt, "properties": dict(
            name="Heatwave March 2024 - nationwide school closure", status="extreme heat (schools closed)",
            valid_from="2024-03", valid_to="2024-04",
            evidence=("Ministries of Health and Education closed all schools from 18 March 2024 for a heatwave forecast at "
                      "41-45 C lasting at least two weeks (Radio Tamazuj, 17 Mar 2024); on 26 March the government said "
                      "schools would reopen the following week (AP, 26 Mar 2024)."),
            date_basis="closure 18 Mar 2024 to reopening early April 2024", Started="2024-03-18", Ended="2024-04 (reopening)",
            **base, Source="Radio Tamazuj; Associated Press",
            source_url="https://radiotamazuj.org/en/news/article/south-sudan-suspends-schools-due-to-extreme-heatwave")},
        {"type": "Feature", "geometry": pt, "properties": dict(
            name="Heatwave February-March 2025 - nationwide school closure", status="extreme heat (schools closed)",
            valid_from="2025-02", valid_to="2025-03",
            evidence=("All schools closed for two weeks from 21 February 2025 after about 12 pupils a day collapsed in Juba; "
                      "39-42 C or higher forecast; reopening possibly delayed to the second week of March (Radio Tamazuj, "
                      "21 Feb 2025)."),
            date_basis="closure 21 Feb 2025 to about mid-March 2025", Started="2025-02-21", Ended="2025-03 (approx.)",
            **base, Source="Radio Tamazuj",
            source_url="https://www.radiotamazuj.org/en/news/article/south-sudan-closes-schools-as-heatwave-intensifies")},
    ]


# --------------------------------------------------------------------------------------------- outputs
LABEL = "Natural disasters (floods, droughts, storms)"
PLAIN = ("Floods, drought alerts and heatwaves reported in 2018-2025, one dot per affected county (or one for the whole "
         "country) shown for as long as the event lasted; flood numbers are people affected as counted by the UN, and "
         "a dot sits at the county centre, not at the flooded place.")
DETAILS = ("Floods: OCHA county tables on HDX for 2021 (13 Dec), 2022 (30 Nov), 2024 (20 Dec) and 2025 (30 Nov); 2019 "
           "and 2020 counties are those named on OCHA's flood maps (5 Nov 2019: 32 counties, 908,000 affected; 21 Oct "
           "2020: 39 counties, state totals from the 31 Jan 2021 situation report) with IOM DTM/IRNA displacement figures "
           "for 2019. Each flood season runs from OCHA's reported start month to its last report (2021: month per county "
           "where given). No OCHA flood table or GLIDE flood event exists for 2023. Droughts: GDACS agricultural-drought "
           "alerts (European Drought Observatory), counties with >= 25% of their area in the alert polygon. Heatwaves: "
           "national school closures in March 2024 and February 2025, placed at Juba. No storm events were found in "
           "GDACS, IFRC GO or ReliefWeb for South Sudan 2018-2025. Epidemics are excluded.")


def write_meta(feats):
    lab_p = os.path.join(ROOT, "data", "points_labels.json")
    labels = json.load(open(lab_p))
    labels["points_disasters"] = {"label": LABEL, "plain": PLAIN, "topic": "Water & floods"}
    with open(lab_p, "w") as f:
        json.dump(labels, f, indent=1, ensure_ascii=False)
    meta_p = os.path.join(ROOT, "data", "processed", "meta", "points.json")
    meta = [e for e in json.load(open(meta_p)) if e.get("key") != "disasters"]
    order = ["flood-affected (reported)", "flood alert (green)", "agricultural drought alert (orange)",
             "agricultural drought alert (green)", "extreme heat (schools closed)"]
    vals = Counter(f["properties"]["status"] for f in feats)
    meta.append({"key": "disasters", "category": "environment", "temporal": "periods", "label": LABEL, "notes": PLAIN,
                 "plain": True, "details": DETAILS,
                 "source": "OCHA South Sudan flood data (HDX) and flood snapshots; IOM DTM; IFRC GO; GDACS; Radio Tamazuj / AP",
                 "source_url": HDX,
                 "status_values": [v for v in order if v in vals] + [v for v in vals if v not in order]})
    with open(meta_p, "w") as f:
        json.dump(meta, f, indent=1, ensure_ascii=False)


def main():
    global CACHE, CTY, BY_NAME
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=CACHE)
    CACHE = ap.parse_args().cache
    os.makedirs(CACHE, exist_ok=True)
    CTY = counties()
    BY_NAME = {f["properties"]["name"].lower(): k for k, f in CTY.items()}
    feats = (season_2019() + season_2020() + season_2021() + season_2022() + season_2024() + season_2025()
             + gdacs() + heatwaves())
    first = ["Type", "County", "State", "Started", "Ended", "People affected", "People displaced",
             "People affected in the state", "Share of county in alert area", "Where the dot is", "Source", "source_url",
             "Disaster ID (GLIDE)", "Disaster page"]
    for f in feats:  # drop empty fields; readable fields first (the app's "All fields" table shows the first 12)
        q = {k: v for k, v in f["properties"].items() if v is not None and v != ""}
        f["properties"] = {**{k: q[k] for k in first if k in q}, **{k: v for k, v in q.items() if k not in first}}
        p = f["properties"]
        assert "date" not in p and p["valid_from"] <= p["valid_to"], p
        assert "2018-01" <= p["valid_from"] and p["valid_to"] <= "2025-12" or p["valid_to"] == "2021-01", p
    feats.sort(key=lambda f: (f["properties"]["valid_from"], f["properties"]["name"]))
    write_fc("points_disasters.geojson", feats, precision=4)
    rows = [{"name": f["properties"]["name"], "type": f["properties"]["Type"], "valid_from": f["properties"]["valid_from"],
             "valid_to": f["properties"]["valid_to"], "county_id": f["properties"].get("county_id"),
             "people_affected": f["properties"].get("People affected"),
             "people_displaced": f["properties"].get("People displaced"),
             "source_url": f["properties"]["source_url"]} for f in feats]
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(ROOT, "data", "processed", "disasters_events.csv"), index=False)
    write_meta(feats)
    df["year"] = df.valid_from.str[:4]
    print(f"{len(feats)} features")
    print(df.groupby(["year", "type"]).agg(features=("name", "size"), affected=("people_affected", "sum")).to_string())


if __name__ == "__main__":
    main()
