"""UNMISS deployment locations over time -> docs/data/points_unmiss.geojson (one feature per location x period).

Sources
 * Geo-PKO v2.3 (Cil et al. 2020; data/raw/geopko, see scripts/unmiss_deployments.py): coded from every UN map
   No. 4456 revision; timepoints Nov 2017 (Rev.30) .. Oct 2024 (Rev.61) - 36 maps inside the window.
   Per timepoint and location: troops (sum of Geo-PKO unit-size estimates), HQ level, formed police unit (FPU)
   presence, contributing countries.
 * UN Geospatial map 4456 Rev.62 (January 2025) and Rev.67 (January 2026), Drive PDFs in
   data/drive_mirror/01_analysis_ready (locations, unit labels; no troop numbers printed). Other 2025 revisions
   (Rev.63 Mar 2025 ...) are catalogued by the UN Digital Library but could not be downloaded (bot wall); the UN
   Geospatial page only serves the current revision (Rev.69, Oct 2026, outside the window).

Periods: a location's period starts at the first map showing it (or showing a different troop estimate / role) and
ends the month before the next map that drops it or changes it. Locations already on the Nov 2017 map have
valid_from = null. Locations on Rev.62 but not on Rev.67 (Aweil, Tambura, Yei, Torit; base closures during the 2025
UNMISS liquidity cuts) get valid_to = 2025-12 with an explicit 'closed between Jan 2025 and Jan 2026' basis.
PoC sites are in the crisis-sites layer (points_crisis_sites.geojson); temporary operating bases (TOBs) are not on
the 4456 maps and are not included.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from points_temporal import point, write_fc, set_validity, ym_add, update_points_meta, assign_county_fc
from unmiss_deployments import load_geopko, MAP_2025, GONE_2026

# Closures of locations on Rev.62 (Jan 2025) but not on Rev.67 (Jan 2026). Rev.63 (Mar 2025), Rev.64 (May 2025) and
# Rev.65 (Jul 2025) still show all of them (team unified dataset, variable unmiss_deployment_sites_in_county, built
# from the hackathon zip of 4456 revisions + news reports of closures; data/raw/ssd_unified).
CLOSURE = {
    "Aweil": ("2025-11", "documented closure Nov 2025 (news reports; team unified dataset)"),
    "Tambura": (None, "documented closure Jan 2026 (news reports; team unified dataset) - present through 2025"),
    "Yei": ("2025-12", "on Rev.65 (Jul 2025), not on Rev.67 (Jan 2026): closed Aug 2025-Jan 2026, month unknown"),
    "Torit": ("2025-12", "on Rev.65 (Jul 2025), not on Rev.67 (Jan 2026): closed Aug 2025-Jan 2026, month unknown"),
}
HQ = {0: "team site / company operating base", 1: "HQ", 2: "Sector HQ", 3: "Mission / Force HQ"}
TYPE_2025 = {"Force HQ / Sector South & Juba HQ": "Mission / Force HQ", "company operating base":
             "team site / company operating base", "team site": "team site / company operating base"}


def main():
    d = load_geopko()
    d["date"] = pd.to_datetime(dict(year=d.year, month=d.month, day=1))
    d = d[d.date >= "2017-11-01"].copy()
    d["troops"] = pd.to_numeric(d["no.troops"], errors="coerce").fillna(0)
    d["fpu_no"] = pd.to_numeric(d["fpu.no"], errors="coerce")
    tcc = [f"nameoftcc_{i}" for i in range(1, 18)]
    d["tccs"] = d[tcc].apply(lambda r: sorted({v for v in r if isinstance(v, str)}), axis=1)
    g = d.groupby(["date", "location"]).agg(
        rev=("source", "first"), lat=("latitude", "first"), lon=("longitude", "first"), troops=("troops", "sum"),
        hq=("hq", "max"), fpu=("fpu", "max"), fpu_no=("fpu_no", "sum"), unpol=("unpol.dummy", "max"),
        tccs=("tccs", lambda s: ", ".join(sorted({c for l in s for c in l})))).reset_index()
    g["ym"] = g.date.dt.strftime("%Y-%m")
    g["rev"] = g.rev.str.replace("Map no.", "Map No.", regex=False)
    g["type"] = g.hq.fillna(0).astype(int).map(HQ)
    # add the two Drive maps as snapshots
    last = g[g.ym == g.ym.max()].set_index("location")
    coords = g.groupby("location")[["lat", "lon"]].last()
    add = []
    for ym, rev, gone in [("2025-01", "Map No. 4456 Rev.62 (Jan 2025)", set()),
                          ("2026-01", "Map No. 4456 Rev.67 (Jan 2026)", GONE_2026)]:
        for name, (role, units) in MAP_2025.items():
            if name in gone:
                continue
            typ = TYPE_2025.get(role, "Sector HQ" if "Sector HQ" in role else role)
            add.append(dict(ym=ym, location=name, rev=rev, lat=coords.lat[name], lon=coords.lon[name],
                            troops=np.nan, type=typ, fpu=int("FPU" in units), fpu_no=np.nan, tccs=units, role=role))
    g = pd.concat([g, pd.DataFrame(add)], ignore_index=True)
    dates = sorted(g.ym.unique())
    feats = []
    for loc, s in g.groupby("location"):
        s = s.set_index("ym")
        cur = None
        periods = []
        for i, ym in enumerate(dates):
            if ym in s.index:
                r = s.loc[ym]
                key = (r["type"], None if pd.isna(r["troops"]) else round(float(r["troops"]), -1), int(r["fpu"] or 0),
                       ym >= "2025-01")
                if cur and cur["key"] == key:
                    cur["last"] = ym
                    cur["revs"].append(r["rev"])
                    continue
                if cur:
                    cur["to"] = ym_add(ym, -1)
                    periods.append(cur)
                cur = dict(key=key, frm=ym, last=ym, to=None, r=r, revs=[r["rev"]])
            elif cur:
                cur["to"] = ym_add(ym, -1)
                periods.append(cur)
                cur = None
        if cur:
            periods.append(cur)
        for p in periods:
            r = p["r"]
            vf = None if p["frm"] <= "2018-01" else p["frm"]
            vt = p["to"]
            if vt is not None and vt < "2018-01":
                continue
            src = "Geo-PKO v2.3" if p["frm"] < "2025-01" else "UN Geospatial map 4456 (Drive PDF)"
            basis = f"{src}: {p['revs'][0]}" + (f" .. {p['revs'][-1]}" if len(p["revs"]) > 1 else "")
            if p["frm"] >= "2025-01":
                basis += "; presence also on Rev.63/64/65 (Mar/May/Jul 2025) per team unified dataset"
            if vt == "2025-12" and loc in CLOSURE:
                vt, why = CLOSURE[loc]
                basis += "; " + why
            elif vt is not None and vt >= "2026-01":
                vt = None
            elif vt == "2024-12" and loc not in MAP_2025:
                basis += "; not on Rev.62 (Jan 2025)"
            props = dict(name=loc, type=r["type"])
            set_validity(props, vf, vt, basis)
            props.update(
                troops_est=None if pd.isna(r["troops"]) else round(float(r["troops"])),
                fpu_present=bool(r["fpu"]) if not pd.isna(r["fpu"]) else None,
                fpu_police_est=None if pd.isna(r.get("fpu_no")) or not r.get("fpu_no") else round(float(r["fpu_no"])),
                units_tcc=r["tccs"] or None,
                role_on_map=r.get("role") if isinstance(r.get("role"), str) else None,
                first_map=p["frm"], last_map=p["last"], n_maps=len(p["revs"]),
                year=int((vf or "2018-01")[:4]),
                source="Geo-PKO v2.3 (UN map 4456)" if p["frm"] < "2025-01" else "UN map 4456 Rev.62/67 (Drive PDF)")
            if p["frm"] >= "2025-01":
                props["note"] = "troop numbers not printed on the 2025/2026 maps (last Geo-PKO estimate in earlier period)"
            feats.append(point(r["lon"], r["lat"], props))
    assign_county_fc(feats)
    write_fc("points_unmiss.geojson", feats)
    print(len(feats), "features,", len({f['properties']['name'] for f in feats}), "locations,", len(dates), "map dates")
    update_points_meta({
        "key": "unmiss", "label": "UNMISS peacekeeping deployments (over time)", "category": "human",
        "source": "Geo-PKO v2.3 (UN maps 4456 Rev.30 Nov 2017 .. Rev.61 Oct 2024) + UN Geospatial map 4456 Rev.62 "
                  "(Jan 2025) and Rev.67 (Jan 2026)",
        "source_url": "https://www.pcr.uu.se/data/geo-pko/",
        "notes": ("One feature per location and period with constant role / troop estimate (rounded to 10) / FPU "
                  "presence; valid_from/valid_to from consecutive 4456 map revisions (38 maps). troops_est = Geo-PKO "
                  "estimate from unit sizes (approximate); fpu_present = formed police unit at location. 2025 periods "
                  "from Rev.62 have no troop numbers. Closures: Aweil Nov 2025 (documented), Yei & Torit between Jul 2025 "
                  "(Rev.65) and Jan 2026 (Rev.67) -> valid_to 2025-12; Tambura closed Jan 2026 (open through 2025). PoC sites: see crisis-sites layer.")})


if __name__ == "__main__":
    main()
