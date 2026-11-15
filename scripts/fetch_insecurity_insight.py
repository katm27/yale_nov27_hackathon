#!/usr/bin/env python3
"""Insecurity Insight (HDX, CC BY-SA) incident data for South Sudan, 2018-01..2025-12.

HDX dataset: https://data.humdata.org/dataset/south-sudan-attacks-on-civilians-and-vital-civilian-facilities
Resources used (found via the CKAN API package_show; file names change as II re-publishes):
  * Aid Worker KIKA (killed, injured, kidnapped, arrested)  -> ii_aid_worker_incidents   (1997-)
  * Attacks on Health Care                                  -> ii_health_attacks         (2016-)
  * Education in Danger                                     -> ii_education_attacks      (2017-)
  * Conflict-Related Sexual Violence (CRSV)                 -> ii_sexual_violence_incidents (2020-)

GEOLOCATION: in every public South Sudan file the coordinates are censored (`Geo Precision` = "censored",
Latitude/Longitude empty); only `Admin 1` (state or administrative area) is published. County-level counts are
therefore NOT possible. This pipeline writes:
  data/processed/insecurity_insight_national.csv   national monthly counts (county_id "SS"; the web build
                                                   broadcasts national rows to every county)
  data/processed/insecurity_insight/ii_state_monthly.csv  state x month x variable counts (admin1 names + the
                                                   counties.geojson admin1 they map to; not loaded by the app)
  docs/data/points_insecurity_insight.geojson     one point per incident placed at the centroid of its
                                                   state / administrative area, flagged geo_precision="admin1
                                                   centroid"; records with Admin 1 "No Information" or outside
                                                   South Sudan are dropped from the points (kept in national counts)
  data/processed/meta/insecurity_insight.json + entry in data/processed/meta/points.json
  data/raw/insecurity_insight/*.xlsx + SOURCE.md

Usage: python scripts/fetch_insecurity_insight.py [--no-download]
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import overlay_utils as ou  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/insecurity_insight"
PROC = ROOT / "data/processed"
OUT = PROC / "insecurity_insight_national.csv"
STATE_OUT = PROC / "insecurity_insight" / "ii_state_monthly.csv"
POINTS = ROOT / "docs/data/points_insecurity_insight.geojson"
PKG = "south-sudan-attacks-on-civilians-and-vital-civilian-facilities"
CKAN = f"https://data.humdata.org/api/3/action/package_show?id={PKG}"
PAGE = f"https://data.humdata.org/dataset/{PKG}"
START, END = "2018-01-01", "2025-12-31"

# variable id, match in resource name, label, incident type, extra cols summed for victims
DATASETS = [
    ("ii_aid_worker_incidents", "Aid Worker KIKA Incident", "Aid worker incidents (killed/injured/kidnapped/arrested)",
     "aid worker KIKA", ["Aid Workers Killed", "Aid Workers Injured", "Aid Workers Kidnapped", "Aid Workers Arrested"]),
    ("ii_health_attacks", "Attacks on Health Care Incident", "Attacks on health care", "attack on health care",
     ["Health Workers Killed", "Health Workers Injured", "Health Workers Kidnapped", "Health Workers Arrested"]),
    ("ii_education_attacks", "Education in Danger Incident", "Attacks on education", "attack on education",
     ["Educators Killed", "Educators Injured", "Students Killed", "Students Injured"]),
    ("ii_sexual_violence_incidents", "Sexual Violence (CRSV) Incident", "Conflict-related sexual violence incidents",
     "conflict-related sexual violence", ["Number of Reported Victims"]),
]

# Insecurity Insight Admin 1 -> (counties.geojson admin1 or None, list of county names for the point centroid)
ADMIN_ALIASES = {
    "Western Bahr el Ghazal State": "Western Bahr el Ghazal",
    "Great Pibor Administrative Area": "Greater Pibor Administrative Area",
}
ADMIN_AREAS = {  # special administrative areas -> member counties (centroid) and parent state in counties.geojson
    "Greater Pibor Administrative Area": ("Jonglei", ["Pibor"]),
    "Ruweng Administrative Area": ("Unity", ["Pariang", "Abiemnhom"]),
    "Abyei": ("Abyei Region", ["Abyei"]),
}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ssd-hackathon-pipeline"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def download():
    pkg = json.loads(get(CKAN))["result"]
    RAW.mkdir(parents=True, exist_ok=True)
    got = {}
    for vid, match, *_ in DATASETS:
        res = [r for r in pkg["resources"] if match.lower() in r["name"].lower()]
        if not res:
            print("no resource for", vid)
            continue
        r = res[0]
        fn = RAW / f"{vid}.xlsx"
        fn.write_bytes(get(r["url"]))
        got[vid] = dict(name=r["name"], url=r["url"], modified=r.get("last_modified"))
        print("downloaded", vid, r["name"], fn.stat().st_size)
    (RAW / "resources.json").write_text(json.dumps(got, indent=1))
    return pkg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-download", action="store_true")
    a = ap.parse_args()
    if not a.no_download:
        download()
    res = json.loads((RAW / "resources.json").read_text())

    cty = gpd.read_file(ROOT / "data/counties.geojson")
    states = set(cty.admin1)
    cty_m = cty.to_crs(32636)

    def centroid(names=None, admin1=None):
        g = cty_m[cty_m.name.isin(names)] if names else cty_m[cty_m.admin1 == admin1]
        if g.empty:
            return None
        p = gpd.GeoSeries([g.union_all().representative_point()], crs=32636).to_crs(4326).iloc[0]
        return round(p.x, 4), round(p.y, 4)

    def resolve(a1):
        a1 = ADMIN_ALIASES.get(str(a1).strip(), str(a1).strip())
        if a1 in states:
            return a1, a1, centroid(admin1=a1), "admin1 centroid (state)"
        if a1 in ADMIN_AREAS:
            parent, names = ADMIN_AREAS[a1]
            return a1, parent, centroid(names=names), "admin1 centroid (administrative area)"
        if a1 in set(cty.name):  # some newer records give a county/town name in the Admin 1 field
            parent = cty.loc[cty.name == a1, "admin1"].iloc[0]
            return a1, parent, centroid(names=[a1]), "county centroid"
        return a1, None, None, "not geolocated (no admin1 / outside South Sudan)"

    months = pd.date_range(START, END, freq="MS").strftime("%Y-%m-%d")
    nat_rows, state_rows, feats, meta, summary = [], [], [], [], {}
    for vid, match, label, itype, victim_cols in DATASETS:
        f = RAW / f"{vid}.xlsx"
        if not f.exists():
            continue
        d = pd.read_excel(f)
        d["Date"] = pd.to_datetime(d["Date"], errors="coerce")
        first = d["Date"].min()
        d = d[(d["Date"] >= START) & (d["Date"] <= END) & (d["Country ISO"].astype(str) == "SSD")].copy()
        d["month"] = d["Date"].dt.to_period("M").dt.to_timestamp().dt.strftime("%Y-%m-%d")
        r = d["Admin 1"].map(resolve)
        d["admin1_ii"] = [x[0] for x in r]
        d["state"] = [x[1] for x in r]
        d["xy"] = [x[2] for x in r]
        d["geo_precision"] = [x[3] for x in r]
        vcols = [c for c in victim_cols if c in d.columns]
        d["victims"] = d[vcols].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1) if vcols else 0
        # coverage start = first year in the resource name ("2017-2025 SSD ...") or the first record
        yr0 = res[vid]["name"][:4]
        src_start = pd.Timestamp(f"{yr0}-01-01") if yr0.isdigit() else first.to_period("M").to_timestamp()
        cov_start = max(pd.Timestamp(START), src_start)
        mm = [m for m in months if m >= cov_start.strftime("%Y-%m-%d")]
        cnt = d.groupby("month").size().reindex(mm, fill_value=0)
        nat_rows += [("SS", m, vid, int(v)) for m, v in cnt.items()]
        st = d.dropna(subset=["state"]).groupby(["admin1_ii", "state", "month"]).size().rename("value").reset_index()
        st["variable"] = vid
        state_rows.append(st)
        idcol = next(c for c in d.columns if c.lower() == "sind event id")
        for rr in d.to_dict("records"):
            if rr["xy"] is None:
                continue
            feats.append(dict(type="Feature", geometry=dict(type="Point", coordinates=list(rr["xy"])), properties=dict(
                name=f"{itype[0].upper() + itype[1:]} ({rr['admin1_ii']}, {rr['Date']:%Y-%m-%d})", type=itype,
                date=rr["Date"].strftime("%Y-%m-%d"), year=int(rr["Date"].year), admin1=rr["admin1_ii"],
                geo_precision=rr["geo_precision"], perpetrator=str(rr.get("Reported Perpetrator", "")),
                victims=int(rr["victims"]), event_id=str(rr.get(idcol, "")),
                source="Insecurity Insight via HDX (CC BY-SA 4.0)")))
        no_geo = int(d["xy"].isna().sum())
        summary[vid] = dict(n=len(d), coverage_from=cov_start.strftime("%Y-%m"), not_geolocated=no_geo,
                            per_year=d.groupby(d["Date"].dt.year).size().to_dict())
        meta.append(dict(
            id=vid, label=label + " (national)", category="human", group="Insecurity Insight",
            units="incidents per month", source="Insecurity Insight (SiND) via HDX, CC BY-SA 4.0 - " + res[vid]["name"],
            source_url=PAGE, native_resolution="national (coordinates censored by source; state in points layer)",
            temporal="monthly", aggregation="count of incidents per month, national (county_id SS) - broadcast to "
            "all counties", higher_is="worse", index_ok=False,
            notes=f"NATIONAL ONLY: Insecurity Insight publishes South Sudan incidents with censored coordinates "
                  f"(Admin 1 only), so no county breakdown is possible. Coverage {cov_start:%Y-%m}..2025-12 "
                  f"({len(d)} incidents; {no_geo} without a usable state). Based on open-source/media and partner "
                  f"reports: counts reflect reporting intensity as much as incidence. State-level counts: "
                  f"data/processed/insecurity_insight/ii_state_monthly.csv; incidents are in the points layer "
                  f"'insecurity_insight' at state centroids."))
        print(vid, summary[vid])

    nat = pd.DataFrame(nat_rows, columns=["county_id", "date", "variable", "value"]).sort_values(["variable", "date"])
    nat.to_csv(OUT, index=False)
    STATE_OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.concat(state_rows).rename(columns={"admin1_ii": "admin1_insecurity_insight", "state": "admin1_counties_geojson",
                                          "month": "date"}) \
        .sort_values(["variable", "admin1_insecurity_insight", "date"]).to_csv(STATE_OUT, index=False)
    (PROC / "meta" / "insecurity_insight.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    POINTS.write_text(json.dumps(dict(type="FeatureCollection", features=feats), ensure_ascii=False))
    ou.add_points_meta(dict(
        key="insecurity_insight", label="Insecurity Insight incidents (aid workers, health, education, CRSV)",
        category="human", source="Insecurity Insight (Security in Numbers Database) via HDX, CC BY-SA 4.0",
        source_url=PAGE,
        notes="One point per incident 2018-2025 with `date`, `type`, `victims`. LOW GEOLOCATION PRECISION: the source "
              "censors coordinates, so points sit at the centroid of the reported state / administrative area "
              "(`geo_precision`), stacked on top of each other - do not read them as incident locations. Records "
              "with no state ('No Information') or outside South Sudan are dropped from the layer."))
    (RAW / "SOURCE.md").write_text(
        "# Insecurity Insight - South Sudan incident data (HDX)\n\n"
        f"Dataset page: {PAGE}\n\nCKAN metadata: {CKAN}\n\nLicence: CC BY-SA 4.0. Files (downloaded by "
        "`scripts/fetch_insecurity_insight.py`, saved here as `<variable>.xlsx`):\n\n"
        + "".join(f"- `{k}.xlsx` <- {v['name']} ({v['url']}), last modified {v['modified']}\n" for k, v in res.items())
        + "\nAll records have `Geo Precision` = censored (no coordinates); only `Admin 1` is published.\n\n"
        f"Summary 2018-2025: {json.dumps(summary, default=str)}\n")
    print("points", len(feats), "national rows", len(nat))


if __name__ == "__main__":
    main()
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from trend_stats import write_trends
    write_trends("insecurity_insight_national")
    import points_events  # valid_from/valid_to/date_basis on event points and ethnic polygons
    points_events.main()
