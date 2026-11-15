"""Ethnic group areas with their national political power status per year -> docs/data/polygons_ethnic_groups.geojson.

Basis: ETH Zurich ICR Ethnic Power Relations core dataset EPR-2023 (status per group and period, coded to 2023) and
GeoEPR-2023 settlement polygons; ACD2EPR-2021 rebel-organisation links (from the team zip,
data/raw/team_dynamic_layers/..._v2.zip). EPR-2023 is published at https://icr.ethz.ch/data/epr/core/EPR-2023.csv
(the core page still lists 2021 as the current release; the 2023 file is the same format, extended to 2023).

For South Sudan EPR-2023 has a single period 2011-2023 for all ten groups, so each group gets
  * one feature for its EPR period clipped to the map window (2018-01 .. 2023-12, "coded by EPR"), and
  * one feature 2024-01 .. 2025-12 carrying the last coded status forward, labelled as not yet coded.
The code handles several EPR periods per group if a later EPR release adds them.

Popup fields use plain-language keys (the app prints keys as row labels); only `name`, `status`, `valid_from`,
`valid_to`, `evidence` and `date_basis` keep machine keys because the app reads them. Internal ids are folded into one
"Dataset ids" string.

Run (downloaded files are untrusted data -> isolated interpreter):
    python3 -I scripts/ethnic_groups_temporal.py [--cache DIR]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import urllib.request
import zipfile

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from points_temporal import ROOT, write_fc  # noqa: E402

EPR_URL = "https://icr.ethz.ch/data/epr/core/EPR-2023.csv"
GEOEPR_URL = "https://icr.ethz.ch/data/epr/geoepr/GeoEPR-2023.geojson"
EPR_PAGE = "https://icr.ethz.ch/data/epr/core/"
CODEBOOK = "https://icr.ethz.ch/data/epr/core/EPR_2021_Codebook_EPR.pdf"
ZIP = os.path.join(ROOT, "data", "raw", "team_dynamic_layers", "south_sudan_dynamic_layers_2018_2025_v2.zip")
CACHE = os.environ.get("ETHNIC_CACHE", os.path.join(ROOT, "data", "raw", "ethnic", "_cache"))
WINDOW = (2018, 2025)

# plain-language explanations, paraphrasing the EPR codebook definitions (EPR 2021 codebook, section on power access)
STATUS = {
    "MONOPOLY": ("Monopoly", "Leaders from this group hold all executive power and exclude every other group."),
    "DOMINANT": ("Dominant", "Leaders from this group hold executive power; other groups have only token posts without real influence."),
    "SENIOR PARTNER": ("Senior partner in government",
                       "Shares national power with other groups and holds the stronger position in the power-sharing arrangement."),
    "JUNIOR PARTNER": ("Junior partner in government",
                       "Represented in the national government, but as a junior partner to a stronger group."),
    "POWERLESS": ("Powerless",
                  "Its leaders have no real influence on national government decisions, though the state does not "
                  "deliberately exclude the group."),
    "DISCRIMINATED": ("Discriminated against",
                      "The state deliberately and actively excludes members of this group from political power."),
    "SELF-EXCLUSION": ("Self-excluded",
                       "The group has excluded itself from national power by controlling territory it has declared independent."),
    "IRRELEVANT": ("Not politically relevant", "EPR does not consider the group politically relevant at the national level."),
}
SETTLEMENT = {"Regionally based": "Lives mainly in its own home region", "Urban": "Lives mainly in cities",
              "Aggregate": "Lives in several regions", "Statewide": "Lives throughout the country",
              "Regional & urban": "Lives in its home region and in cities", "Migrant": "Migrant group",
              "Dispersed": "Dispersed across the country"}


def fetch(url):
    p = os.path.join(CACHE, os.path.basename(url))
    if not os.path.exists(p):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research map)"})
        with urllib.request.urlopen(req, timeout=300) as r, open(p, "wb") as f:
            f.write(r.read())
    return p


def rebel_links():
    """ACD2EPR-2021 links from the team zip: group -> 'SSLM/A; SPLM/A - IO' (claim/recruitment codes dropped:
    every listed organisation has claim >= 1 and recruitment = 1)."""
    z = zipfile.ZipFile(ZIP)
    out = {}
    for f in json.loads(z.read("ethnic_groups_geoepr_2018_2021.geojson"))["features"]:
        p = f["properties"]
        if p.get("linked_rebel_orgs"):
            out[p["group"]] = "; ".join(x.split(" (")[0].strip() for x in p["linked_rebel_orgs"].split(";"))
    return out


def pct(x):
    x = float(x) * 100
    return f"{x:.1f}%".replace(".0%", "%") if x < 10 else f"{x:.0f}%"


def build():
    import geopandas as gpd
    os.makedirs(CACHE, exist_ok=True)
    epr = pd.read_csv(fetch(EPR_URL))
    epr = epr[epr.statename == "South Sudan"].rename(columns={"from": "yfrom", "to": "yto"})
    geo = gpd.read_file(fetch(GEOEPR_URL))
    geo = geo[geo.statename == "South Sudan"].copy()
    assert len(epr) and len(geo), "South Sudan missing from EPR/GeoEPR"
    country = gpd.read_file(os.path.join(ROOT, "data", "counties.geojson")).union_all()
    links = rebel_links()
    last_coded = int(epr["yto"].max())
    feats = []
    for r in epr.sort_values(["size", "group"], ascending=[False, True]).itertuples():
        y0, y1 = max(int(r.yfrom), WINDOW[0]), min(int(r.yto), WINDOW[1])
        if y0 > y1:
            continue
        g = geo[(geo.gwgroupid == r.gwgroupid) & (geo["from"] <= y1) & (geo["to"] >= y0)]
        assert len(g) == 1, (r.group, len(g))
        geom = g.geometry.iloc[0].intersection(country).simplify(0.005)
        label, plain = STATUS[r.status]
        reg = {True: "Yes", False: "No"}.get(str(r.reg_aut).lower() == "true", "Not coded")
        if pd.isna(r.reg_aut) or str(r.reg_aut) == "":
            reg = "Not coded (not applicable for monopoly or dominant groups)"
        common = {
            "Group": r.group,
            "Share of national population": f"{pct(r.size)} (EPR estimate)",
            "Regional autonomy": reg if reg.startswith("Not") else
            (reg + (" - runs its own regional government" if reg == "Yes" else " - no own regional government")),
            "Where the group lives": SETTLEMENT.get(g["type"].iloc[0], g["type"].iloc[0]),
            "Armed groups linked to the group": (links.get(r.group, "None recorded")
                                                 + " (organisations that recruited from or claimed to fight for the group; ACD2EPR, coded to 2021)"),
            "Source": f"Ethnic Power Relations (EPR-2023) and GeoEPR-2023, ETH Zurich; status coded for {int(r.yfrom)}-{int(r.yto)}",
            "source_url": EPR_PAGE,
            "Dataset ids": f"EPR gwgroupid {r.gwgroupid}; country code (gwid) {r.gwid}; EPR group id {r.groupid}",
        }
        periods = [(y0, y1, False)]
        if int(r.yto) == last_coded and last_coded < WINDOW[1]:
            periods.append((last_coded + 1, WINDOW[1], True))
        for a, b, carried in periods:
            q = {"Group": r.group,
                 "Political power status": label + (f" (last coded {last_coded}, shown unchanged)" if carried else ""),
                 "What this means": plain,
                 "Period": f"{a}-{b}" + (" (not yet coded: EPR ends in %d)" % last_coded if carried else " (coded by EPR)")}
            q.update({k: v for k, v in common.items() if k not in q})
            q.update({
                "name": r.group,
                "status": label.lower() + (f" (carried forward, not coded after {last_coded})" if carried else ""),
                "valid_from": f"{a}-01", "valid_to": f"{b}-12",
                "evidence": (f"EPR codes the {r.group} as '{r.status.lower()}' for {int(r.yfrom)}-{int(r.yto)}"
                             + (f"; no EPR coding exists after {last_coded}, so the {last_coded} status is carried forward"
                                if carried else "")),
                "date_basis": (f"carried forward: EPR-2023 ends in {last_coded}" if carried
                               else f"EPR-2023 period {int(r.yfrom)}-{int(r.yto)}, clipped to the 2018-2025 map window"),
            })
            feats.append({"type": "Feature", "geometry": json.loads(gpd.GeoSeries([geom]).to_json())["features"][0]["geometry"],
                          "properties": q})
    write_fc("polygons_ethnic_groups.geojson", feats, precision=4)
    return feats, last_coded


def status_order(last_coded):
    base = [STATUS[k][0].lower() for k in STATUS]
    return base + [f"{s} (carried forward, not coded after {last_coded})" for s in base]


LABEL = "Ethnic group areas and political power (EPR)"
NOTES = ("Where ten major ethnic groups live and how much national political power each held in each year, as coded "
         "by the Ethnic Power Relations dataset to {last}; the {last} status is shown unchanged for later years.")
DETAILS = ("GeoEPR-2023 settlement polygons clipped to South Sudan; EPR-2023 power status (one period, 2011-2023, for "
           "all ten groups: Dinka senior partner, Nuer junior partner, Murle discriminated, the other seven powerless; "
           "no group has regional autonomy). Features 2018-01..2023-12 are coded; 2024-01..2025-12 carry the 2023 status "
           "forward and say so. Group shares of national population are EPR estimates. Armed-group links from ACD2EPR-2021.")


def write_meta(feats, last):
    from collections import Counter
    meta_p = os.path.join(ROOT, "data", "processed", "meta", "points.json")
    meta = json.load(open(meta_p))
    vals = Counter(f["properties"]["status"] for f in feats)
    for e in meta:
        if e.get("key") == "ethnic_groups":
            e.update({"label": LABEL, "notes": NOTES.format(last=last), "details": DETAILS, "plain": True,
                      "temporal": "periods", "source": "EPR-2023 / GeoEPR-2023 (ETH Zurich ICR); ACD2EPR-2021",
                      "source_url": EPR_PAGE,
                      "status_values": [v for v in status_order(last) if v in vals]})
    with open(meta_p, "w") as f:
        json.dump(meta, f, indent=1, ensure_ascii=False)
    lab_p = os.path.join(ROOT, "data", "points_labels.json")
    labels = json.load(open(lab_p))
    labels.setdefault("polygons_ethnic_groups", {}).update(
        {"label": LABEL, "plain": NOTES.format(last=last), "topic": "Population & society"})
    with open(lab_p, "w") as f:
        json.dump(labels, f, indent=1, ensure_ascii=False)


def main():
    global CACHE
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=CACHE)
    CACHE = ap.parse_args().cache
    feats, last = build()
    write_meta(feats, last)
    for f in feats:
        p = f["properties"]
        print(f"{p['name']:<8} {p['valid_from']}..{p['valid_to']}  {p['status']}")
    print(len(feats), "features; EPR coded to", last)


if __name__ == "__main__":
    main()
