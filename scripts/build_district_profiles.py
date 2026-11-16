"""Build data/district_profiles.json (county hover-card profiles).

Merges
  * hand-written, sourced narrative text  -> data/district_profiles_narrative.json
  * FEWS NET 2018 livelihood zones        -> data/raw/fews_lhz/SS_LHZ_2018.zip (area overlay)
  * key_facts recomputed from processed county-month data (ACLED, UCDP, DTM, IPC, water)

Usage:  python scripts/build_district_profiles.py
Sources are listed in docs/district_profiles_sources.md.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROC = DATA / "processed"
NARRATIVE = DATA / "district_profiles_narrative.json"
OUT = DATA / "district_profiles.json"
LHZ_ZIP = DATA / "raw" / "fews_lhz" / "SS_LHZ_2018.zip"
LHZ_URL = "https://shapefiles.fews.net/LHZ/SS_LHZ_2018.zip"
LHZ_DOC = ("https://fews.net/sites/default/files/documents/reports/"
           "Livelihoods%20Zone%20Map%20and%20Descriptions%20for%20South%20Sudan.pdf")
MAX_CHARS = 300
MAX_CONFLICT_CHARS = 900  # conflict_impact is a 3-5 sentence narrative
SECONDARY_MIN = 0.25

# Zone summaries condensed from FEWS NET, "Livelihoods Zone Map and Descriptions for the
# Republic of South Sudan (updated)", Aug 2018 (LHZ_DOC). Names follow the 2018 shapefile.
ZONES = {
    "SS01": ("Equatorial maize and cassava",
             "Rain-fed farming in the Greenbelt, which has two rainy seasons and normally produces a "
             "surplus of maize, sorghum, groundnuts, cassava and beans. Small livestock, fishing, hunting, "
             "wild foods and cross-border trade add to this."),
    "SS02": ("Ironstone Plateau agro-pastoral",
             "An agro-pastoral zone where households grow sorghum, groundnuts and other crops and keep "
             "cattle, goats and sheep. Output is moderate, water runs very short in the dry season, and "
             "cattle raids come with the seasons."),
    "SS03": ("Highland forest and sorghum",
             "Mostly crop farming, mainly sorghum, with a few livestock. There is one rainy season and "
             "not enough cereal, so people turn to forest and wild foods and sell bush products."),
    "SS04": ("Western plains groundnuts sesame and sorghum",
             "Subsistence rain-fed farming of groundnuts, sesame and sorghum. Forest products, seasonal "
             "river fishing and sales of poultry, goats and sheep add to it. The area used to produce a "
             "surplus."),
    "SS05": ("South-Eastern semi-arid pastoral",
             "Herding of cattle, goats and sheep with very little cropping in a semi-arid zone. Wild foods "
             "and market purchases, including grain from Kenya and Ethiopia, fill the food gap."),
    "SS06": ("Eastern plains sorghum and cattle",
             "Rain-fed sorghum and cattle herding on the floodplains, with fishing, hunting and wild "
             "foods. The area grows too little cereal but has plenty of fish and livestock products."),
    "SS07": ("Greater Bahr el Ghazal sorghum and cattle",
             "Farming of sorghum (the staple), maize and groundnuts alongside cattle, goats and sheep, "
             "plus fishing and wild foods. Most households own cattle, and since the zone grows too little "
             "cereal, people trade livestock for grain."),
    "SS08": ("Nile basin fishing and agro-pastoral",
             "Riverine livelihoods along the Nile and the Sudd. People fish, grow sorghum and maize, keep "
             "cattle, goats and sheep, and gather water lilies and other wild foods. Floods return every "
             "few years."),
    "SS09": ("North-Western Nile basin cattle and maize",
             "Agro-pastoral, with more weight on cattle than on crops. Maize is the main staple, fishing "
             "and wild foods add to it, and the zone relies on grain imported from Sudan."),
    "SS10": ("North-Eastern maize cattle and fishing",
             "Livelihoods on the Sobat River floodplain, where maize growing, cattle and fishing are "
             "equally important. The zone imports cereal and is fairly isolated near the Ethiopian border."),
    "SS11": ("Northern sorghum and livestock",
             "Semi-arid agro-pastoralism based on sorghum and livestock, with Nile fishing, labour "
             "migration and petty trade. Near the Nile there is mechanised farming. Elsewhere farming is "
             "for subsistence, and the zone grows too little cereal."),
    "SS12": ("Maize Sorghum Fishing and Natural Resources",
             "Farming of maize and sorghum with two harvests a year, plus livestock, fishing and natural "
             "resources such as honey and shea from the Boma/Badingilo area."),
}


def lhz_overlay(counties_path: Path) -> pd.DataFrame:
    """Area share of each FEWS NET 2018 zone within each county (equal-area CRS)."""
    import geopandas as gpd

    src = f"zip://{LHZ_ZIP}" if LHZ_ZIP.exists() else LHZ_URL
    c = gpd.read_file(counties_path).to_crs(6933)
    z = gpd.read_file(src).to_crs(6933)
    c["A"] = c.area
    o = gpd.overlay(c[["district_id", "A", "geometry"]], z[["LZCODE", "geometry"]],
                    how="intersection", keep_geom_type=True)
    o["share"] = o.area / o["A"]
    return (o.groupby(["district_id", "LZCODE"]).share.sum().reset_index()
             .sort_values(["district_id", "share"], ascending=[True, False]))


def load_long(name: str) -> pd.DataFrame:
    d = pd.read_csv(PROC / name)
    d["year"] = d.date.str[:4].astype(int)
    return d


def _num(x, nd=0):
    if pd.isna(x):
        return None
    return int(round(float(x))) if nd == 0 else round(float(x), nd)


def compute_key_facts(ids: list[str]) -> dict[str, dict]:
    acled = load_long("acled_county_monthly.csv")
    ucdp = load_long("ucdp_county_monthly.csv")
    dtm = load_long("dtm_county_monthly.csv")
    ipc = load_long("ipc_county_monthly.csv")
    water = load_long("water_county_monthly.csv")
    uni = load_long("unified_county_monthly.csv")
    uni = uni[uni.variable.isin(["et_ind_flooding", "et_ind_local_communal_conflict",
                                 "et_ind_national_conflict", "et_ind_arrived_from_sudan"])]

    def yearly(df, var):
        s = df[df.variable == var].groupby(["county_id", "year"]).value.sum()
        return s

    a_ev, a_fat = yearly(acled, "acled_pv_events"), yearly(acled, "acled_pv_fatalities")
    a_civ = yearly(acled, "acled_civ_fatalities")
    u_d, u_ev = yearly(ucdp, "ucdp_deaths_best"), yearly(ucdp, "ucdp_events")
    ipc3 = ipc[ipc.variable == "ipc_phase3plus_pct"]
    ipc3pop = ipc[ipc.variable == "ipc_phase3plus_pop"]
    idp = dtm[dtm.variable == "dtm_idps"]
    sw = water[water.variable == "surface_water_pct"]
    et = uni.groupby(["county_id", "variable"]).value.sum()

    def tot(s, cid):
        return _num(s.loc[cid].sum()) if cid in s.index.get_level_values(0) else 0

    def peak_year(s, cid):
        if cid not in s.index.get_level_values(0):
            return None
        sc = s.loc[cid]
        return int(sc.idxmax()) if sc.max() > 0 else None

    out = {}
    for cid in ids:
        kf = {
            "acled_pv_events_2018_2025": tot(a_ev, cid),
            "acled_pv_fatalities_2018_2025": tot(a_fat, cid),
            "acled_civilian_targeting_fatalities_2018_2025": tot(a_civ, cid),
            "acled_peak_year_fatalities": peak_year(a_fat, cid),
            "acled_peak_year_fatalities_value": (_num(a_fat.loc[cid].max())
                                                 if peak_year(a_fat, cid) else 0),
            "ucdp_events_2018_2025": tot(u_ev, cid),
            "ucdp_deaths_best_2018_2025": tot(u_d, cid),
            "ucdp_peak_year": peak_year(u_d, cid),
        }
        i = idp[idp.county_id == cid]
        if len(i):
            r = i.loc[i.value.idxmax()]
            last = i.sort_values("date").iloc[-1]
            kf.update(dtm_idps_peak=_num(r.value), dtm_idps_peak_date=r.date[:7],
                      dtm_idps_latest=_num(last.value), dtm_idps_latest_date=last.date[:7])
        for var, key in [("et_ind_flooding", "dtm_et_displaced_by_flooding_2020_2025"),
                         ("et_ind_local_communal_conflict", "dtm_et_displaced_by_communal_conflict_2020_2025"),
                         ("et_ind_national_conflict", "dtm_et_displaced_by_national_conflict_2020_2025"),
                         ("et_ind_arrived_from_sudan", "dtm_et_arrivals_from_sudan_2023_2025")]:
            kf[key] = _num(et.get((cid, var), 0))
        p = ipc3[ipc3.county_id == cid]
        if len(p):
            r = p.loc[p.value.idxmax()]
            kf.update(ipc_phase3plus_pct_peak=_num(r.value), ipc_phase3plus_peak_date=r.date[:7])
            last = p.sort_values("date").iloc[-1]
            kf.update(ipc_phase3plus_pct_latest=_num(last.value),
                      ipc_phase3plus_latest_date=last.date[:7])
        pp = ipc3pop[ipc3pop.county_id == cid]
        if len(pp):
            kf["ipc_phase3plus_pop_peak"] = _num(pp.value.max())
        w = sw[sw.county_id == cid]
        if len(w) and w.value.notna().any():
            r = w.loc[w.value.idxmax()]
            kf.update(surface_water_pct_max=_num(r.value, 1), surface_water_max_month=r.date[:7],
                      surface_water_pct_median=_num(w.value.median(), 1))
        out[cid] = kf
    return out


def facts_sentence(kf: dict, short: bool = False) -> str:
    """Compact numeric summary; `short` keeps only ACLED and the IDP peak."""
    parts = []
    if kf["acled_pv_events_2018_2025"]:
        s = (f"ACLED 2018-25: {kf['acled_pv_events_2018_2025']} political-violence events, "
             f"{kf['acled_pv_fatalities_2018_2025']} deaths")
        if kf["acled_peak_year_fatalities"]:
            s += f" (peak {kf['acled_peak_year_fatalities']})"
        parts.append(s)
    else:
        parts.append("ACLED 2018-25: no political-violence events recorded")
    if kf.get("dtm_idps_peak"):
        parts.append(f"IDPs peak {kf['dtm_idps_peak']:,} ({kf['dtm_idps_peak_date']})")
    if short:
        return "; ".join(parts) + "."
    if kf.get("ipc_phase3plus_pct_peak"):
        parts.append(f"IPC3+ peak {kf['ipc_phase3plus_pct_peak']}%")
    if kf.get("dtm_et_displaced_by_flooding_2020_2025"):
        parts.append(f"flood-displaced {kf['dtm_et_displaced_by_flooding_2020_2025']:,}")
    return "; ".join(parts) + "."


def livelihood_text(zones: list[tuple[str, float]]) -> str:
    code, share = zones[0]
    text = ZONES[code][1]
    sec = [(c, s) for c, s in zones[1:] if s > SECONDARY_MIN]
    if sec:
        names = [ZONES[c][0] for c, _ in sec]  # no area percentages in prose; shares stay in key_facts
        add = " Also partly in the " + " and ".join(names) + (" zones." if len(names) > 1 else " zone.")
        if len(text) + len(add) > MAX_CHARS:
            text = text.split(". ")[0].rstrip(".") + "."  # keep the first sentence
        text += add
    return text


def main() -> int:
    counties = json.loads((DATA / "counties.geojson").read_text())
    props = [f["properties"] for f in counties["features"]]
    ids = [p["district_id"] for p in props]
    narrative = json.loads(NARRATIVE.read_text()) if NARRATIVE.exists() else {}
    ov = lhz_overlay(DATA / "counties.geojson")
    facts = compute_key_facts(ids)

    out, warnings = {}, []
    for p in props:
        cid = p["district_id"]
        n = narrative.get(cid, {})
        z = ov[ov.district_id == cid]
        zones = [(r.LZCODE, float(r.share)) for r in z.itertuples() if r.share > 0.01]
        kf = facts[cid]
        kf["lhz_shares"] = {c: round(s, 2) for c, s in zones if s >= 0.05}
        lz = {"code": zones[0][0], "name": ZONES[zones[0][0]][0], "share": round(zones[0][1], 2)}
        sec = [(c, s) for c, s in zones[1:] if s > SECONDARY_MIN]
        if sec:
            lz["secondary"] = {"code": sec[0][0], "name": ZONES[sec[0][0]][0],
                               "share": round(sec[0][1], 2)}
        # conflict_impact is a hand-written, number-free narrative (district_profiles_narrative.json
        # "conflict_impact") built from conflict_narrative, the sources and key_facts in words.
        # All statistics stay in key_facts; facts_sentence() is only a fallback for new counties.
        conflict = n.get("conflict_narrative", "").strip()
        conflict_full = n.get("conflict_impact", "").strip()
        if not conflict_full:
            conflict_full = f"{conflict} {facts_sentence(kf, True)}".strip()
        rec = {
            "name": p["name"],
            "state": p["admin1"],
            "livelihood_zone": lz,
            "livelihoods": n.get("livelihoods") or livelihood_text(zones),
            "history": n.get("history", ""),
            "conflict_impact": conflict_full,
            "key_facts": kf,
            "sources": list(dict.fromkeys([LHZ_DOC, LHZ_URL] + n.get("sources", []) + [
                "https://data.humdata.org/dataset/south-sudan-acled-conflict-data",
                "https://ucdp.uu.se/downloads/",
                "https://data.humdata.org/dataset/south-sudan-displacement-data-idps-returnees-baseline-assessment-iom-dtm",
                "https://data.humdata.org/dataset/south-sudan-displacement-data-idps-returnees-emergency-event-tracking-iom-dtm",
                "https://www.ipcinfo.org/ipc-country-analysis/en/?country=SSD",
            ])),
        }
        for k in ("livelihoods", "history", "conflict_impact"):
            if len(rec[k]) > (MAX_CONFLICT_CHARS if k == "conflict_impact" else MAX_CHARS):
                warnings.append(f"{cid} {k} is {len(rec[k])} chars")
            if not rec[k]:
                warnings.append(f"{cid} {k} empty")
        out[cid] = rec

    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"wrote {OUT} ({len(out)} counties)")
    for w in warnings:
        print("WARN", w, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
