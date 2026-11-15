"""Oil fields / wells / pipelines with production-status periods.

Post-processes docs/data/points_oil.geojson and docs/data/lines_pipelines.geojson (written by
scripts/oil_infrastructure.py; re-runnable: it collapses its own period features back to one per field first).

Field status periods (sourced, months approximate where flagged):
 * Unity & Toma South (GPOC Blocks 1/2/4, Unity state) and Tharjath (SPOC Block 5A): shut in since the Dec 2013
   war. Toma South restart: ceremony 31 Aug 2018 (Bloomberg / Reuters, "South Sudan resumes output in key oil area
   after five-year halt") -> producing from 2018-09. Unity field restart: Jan 2019 (Reuters/Bloomberg, Jan 2019).
   Tharjath: restart month not documented in the sources consulted -> one 'shut in Dec 2013; restart undated' period.
 * Palogue & Qamari (DPOC Blocks 3/7, Upper Nile, Dar Blend via the Petrodar pipeline through Sudan): producing
   through Jan 2024; Dar Blend exports halted 6 Feb 2024 after the pipeline rupture in Sudan (force majeure
   declared by Sudan 16 Mar 2024; Argus / Radio Tamazuj) -> 'export disruption' 2024-02..2024-12; government
   announced resumption of production/exports in Jan 2025 -> from 2025-01 (volumes not verified).
 * OSM wells and OSM pipeline segments carry no dates: snapshot (valid_from/valid_to null, date_basis says so).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from points_temporal import read_fc, write_fc, set_validity, update_points_meta

SHUT = "shut in (war damage since Dec 2013)"
FIELD_PERIODS = {
    "Toma South Oil Field": [
        (None, "2018-08", SHUT, "shut Dec 2013 (civil war)"),
        ("2018-09", None, "producing (restarted)", "restart ceremony 31 Aug 2018 (Bloomberg/Reuters)")],
    "Unity Oil Field": [
        (None, "2018-12", SHUT, "shut Dec 2013 (civil war)"),
        ("2019-01", None, "producing (restarted)", "Unity field restart Jan 2019 (Reuters/Bloomberg)")],
    "Tharjath Oil Field": [
        (None, None, "shut in Dec 2013; restart month undocumented",
         "shut Dec 2013 (civil war); no sourced restart date - status not time-resolved")],
    "Palogue Oil Field": [
        (None, "2024-01", "producing (Dar Blend exports)", "DPOC Blocks 3/7 producing through the war"),
        ("2024-02", "2024-12", "export disruption (Petrodar pipeline rupture in Sudan)",
         "exports halted 6 Feb 2024, force majeure 16 Mar 2024 (Argus, Radio Tamazuj)"),
        ("2025-01", None, "producing (exports resumed)", "resumption announced Jan 2025 (Radio Tamazuj); volumes unverified")],
}
FIELD_PERIODS["Qamari Oil Field"] = FIELD_PERIODS["Palogue Oil Field"]


def main():
    fc = read_fc("points_oil.geojson")
    out, seen = [], set()
    for f in fc["features"]:
        p = f["properties"]
        if p.get("type", "").startswith("oil field"):
            if p["name"] in seen:
                continue
            seen.add(p["name"])
            for k in ("valid_from", "valid_to", "date_basis", "production_status"):
                p.pop(k, None)
            for vf, vt, st, basis in FIELD_PERIODS.get(p["name"], [(None, None, p.get("status"), "snapshot only (GEM GOGET Mar 2026)")]):
                q = dict(name=p["name"], type=p["type"])
                set_validity(q, vf, vt, basis)
                q["production_status"] = st
                q.update({k: v for k, v in p.items() if k not in q})
                out.append({"type": "Feature", "geometry": f["geometry"], "properties": q})
        else:
            set_validity(p, None, None, "snapshot only (OpenStreetMap mapping, no dates; mapped wells may predate 2018)")
            out.append(f)
    write_fc("points_oil.geojson", out)
    pl = read_fc("lines_pipelines.geojson")
    for f in pl["features"]:
        p = f["properties"]
        st = str(p.get("status"))
        if st == "proposed":
            set_validity(p, None, None, "proposed route (GEM GOIT): not built - shown as planning snapshot")
        elif "Greater Nile" in str(p.get("name")) and st == "operating":
            set_validity(p, None, None, "operating since 1999 (GEM GOIT start_year); carried Nile Blend from Unity "
                                        "fields, flows interrupted 2013-2018 while fields were shut")
        else:
            set_validity(p, None, None, "snapshot only (OpenStreetMap / GEM, no dates)")
    write_fc("lines_pipelines.geojson", pl["features"])
    print(len(out), "oil points;", sum(1 for f in out if f["properties"]["type"].startswith("oil field")), "field periods;",
          len(pl["features"]), "pipeline lines")
    update_points_meta({
        "key": "oil", "label": "Oil fields (production status over time) and wells", "category": "human",
        "source": "Global Energy Monitor GOGET (CC-BY 4.0) + OpenStreetMap wells (ODbL); status dates from Reuters/"
                  "Bloomberg (2018-19 restarts) and Argus/Radio Tamazuj (2024 Dar Blend export halt, 2025 resumption)",
        "source_url": "https://globalenergymonitor.org/projects/global-oil-gas-extraction-tracker/",
        "notes": ("Temporal: oil fields get one feature per production_status period - Toma South shut in until Aug 2018, "
                  "Unity until Dec 2018 (Dec 2013 war); Palogue/Qamari (Dar Blend) export disruption Feb-Dec 2024 after "
                  "the pipeline rupture in Sudan, resumed Jan 2025; Tharjath shut 2013, restart undated (static). "
                  "OSM wells: snapshot only (no dates).")})
    update_points_meta({
        "key": "pipelines", "label": "Oil pipelines (lines)", "category": "human",
        "source": "GEM GOIT (CC-BY 4.0) + OpenStreetMap via Overture (ODbL)",
        "source_url": "https://globalenergymonitor.org/projects/global-oil-infrastructure-tracker/",
        "notes": ("Line layer docs/data/lines_pipelines.geojson; includes proposed GEM routes (status field). Temporal: "
                  "snapshot (valid_from/valid_to null) - routes exist through the window; flow interruptions are "
                  "recorded on the oil-field periods (points_oil).")})
    # Superseded by the reconciled block-status periods (Heglig Dec 2025, Thar Jath Jun 2021, OSM wells with periods)
    import team_dynamic_layers as tdl
    tdl.oil()
    tdl.write_points_meta({"oil": tdl.status_values_of("points_oil.geojson", tdl.OIL_ORDER),
                           "pipelines": tdl.status_values_of("lines_pipelines.geojson", tdl.OIL_ORDER)})


if __name__ == "__main__":
    main()
