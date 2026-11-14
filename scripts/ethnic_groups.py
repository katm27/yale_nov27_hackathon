"""GeoEPR 2021 (ETH Zurich ICR) ethnic group settlement polygons for South Sudan (2011-2021 period)
-> docs/data/polygons_ethnic_groups.geojson; county static vars: ethnic_groups_count, ethnic_dominant_share,
ethnic_excluded_share (area share of politically powerless/discriminated groups per EPR); and lookup CSV
data/processed/ethnic_county_lookup.csv with the dominant group name(s) (categorical, not in the long format).
"""
import os
import sys
import pandas as pd
import geopandas as gpd
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from overlay_utils import ROOT, PROC, DOCS_DATA, counties, write_long, write_meta

RAW = os.path.join(ROOT, "data", "raw", "ethnic")
GEOEPR = "https://icr.ethz.ch/data/epr/geoepr/GeoEPR-2021.geojson"
EPR = "https://icr.ethz.ch/data/epr/core/EPR-2021.csv"


def get(u):
    p = os.path.join(RAW, os.path.basename(u))
    if not os.path.exists(p):
        open(p, "wb").write(requests.get(u, timeout=300).content)
    return p


def main():
    os.makedirs(RAW, exist_ok=True)
    with open(os.path.join(RAW, "SOURCE.md"), "w") as f:
        f.write(f"GeoEPR 2021: {GEOEPR}\nEPR core 2021: {EPR}\n(GREG.zip also downloaded for reference: "
                "https://icr.ethz.ch/data/greg/GREG.zip, 1960s Soviet atlas based)\nVogt et al. 2015 JCR; ICR ETH Zurich.\n")
    g = gpd.read_file(get(GEOEPR))
    g = g[g.statename == "South Sudan"].copy()
    e = pd.read_csv(get(EPR))
    e = e[e.statename == "South Sudan"][["gwgroupid", "from", "to", "size", "status"]]
    g = g.merge(e, on=["gwgroupid", "from", "to"], how="left")
    c = counties()
    country = c.union_all()
    g["geometry"] = g.geometry.intersection(country).simplify(0.005)
    g = g[~g.geometry.is_empty]
    out = g[["group", "from", "to", "status", "size", "type", "geometry"]].rename(
        columns={"from": "year_from", "to": "year_to", "size": "national_pop_share"})
    out["period"] = out.year_from.astype(str) + "-" + out.year_to.astype(str)
    out["source"] = "GeoEPR 2021 / EPR 2021 (ETH Zurich ICR)"
    out.to_file(os.path.join(DOCS_DATA, "polygons_ethnic_groups.geojson"), driver="GeoJSON", COORDINATE_PRECISION=4)
    # county overlay (equal-area)
    ce = c.to_crs(6933)
    ge = out.to_crs(6933)
    ce["carea"] = ce.area
    ov = gpd.overlay(ce[["district_id", "carea", "geometry"]], ge[["group", "status", "geometry"]], how="intersection")
    ov["share"] = ov.area / ov.carea
    ov = ov[ov.share > 0.02]  # ignore slivers (<2% of county area)
    ids = sorted(c.district_id)
    cnt = ov.groupby("district_id").group.nunique().reindex(ids, fill_value=0)
    dom = ov.sort_values("share", ascending=False).groupby("district_id").first()
    excl = ov[ov.status.isin(["POWERLESS", "DISCRIMINATED"])].groupby("district_id").share.sum().clip(upper=1) \
        .reindex(ids, fill_value=0)
    covered = ov.groupby("district_id").share.sum()
    excl = excl.where(cnt > 0)
    rows = []
    for v, s in [("ethnic_groups_count", cnt), ("ethnic_dominant_share", dom.share.reindex(ids)),
                 ("ethnic_excluded_share", excl)]:
        rows += [(cid, "2018-07-01", v, float(x)) for cid, x in s.items() if pd.notna(x)]
    write_long("ethnic", pd.DataFrame(rows, columns=["county_id", "date", "variable", "value"]))
    lk = pd.DataFrame({"county_id": ids})
    lk["dominant_group"] = lk.county_id.map(dom.group)
    lk["dominant_share"] = lk.county_id.map(dom.share).round(3)
    lk["groups"] = lk.county_id.map(ov.sort_values("share", ascending=False).groupby("district_id").group
                                    .apply(lambda s: "; ".join(dict.fromkeys(s))))
    lk["area_share_covered"] = lk.county_id.map(covered).round(3)
    lk.to_csv(os.path.join(PROC, "ethnic_county_lookup.csv"), index=False)
    print(lk.to_string())
    base = {"category": "human", "group": "Ethnic geography", "source": "GeoEPR 2021 + EPR 2021 (ETH Zurich ICR)",
            "source_url": "https://icr.ethz.ch/data/epr/geoepr/", "native_resolution": "polygon (group settlement area)",
            "temporal": "static", "index_ok": False, "higher_is": "neutral"}
    note = ("GeoEPR covers only the 10 politically relevant groups (Dinka, Nuer, Azande, Bari, Murle, Toposa, Shilluk, "
            "Mundari, Didinga, Anyuak); many smaller groups (e.g. Fertit groups in W. Bahr el Ghazal, Acholi, Madi, Lotuko) "
            "are absent, so some counties show 0 groups. Period 2011-2021, treated as static. Polygons may overlap.")
    write_meta("ethnic", [
        dict(base, id="ethnic_groups_count", label="Ethnic groups present (GeoEPR)", units="groups",
             aggregation="number of GeoEPR groups covering >2% of county area", notes=note),
        dict(base, id="ethnic_dominant_share", label="Dominant group area share", units="fraction 0-1",
             aggregation="largest single-group share of county area", notes=note + " Dominant group names in data/processed/ethnic_county_lookup.csv."),
        dict(base, id="ethnic_excluded_share", label="Area of politically excluded groups", units="fraction 0-1",
             aggregation="county area share settled by groups EPR codes as POWERLESS or DISCRIMINATED (2011-2021)",
             notes=note + " EPR status: Dinka senior partner, Nuer junior partner, Murle discriminated, others powerless."),
    ])


if __name__ == "__main__":
    main()
