"""ACLED admin-2 monthly aggregates for South Sudan (public HDX files) -> county-month.

Source: HDX dataset `south-sudan-acled-conflict-data` (ACLED, HRP aggregated files):
  political violence events & fatalities, civilian targeting events & fatalities, demonstrations
Abyei: ACLED codes the Abyei Area under Sudan (Admin1 'Abyei', Admin2 'Abyei', SD19001) -> taken
from `sudan-acled-conflict-data` and mapped to SS0001.

The aggregates list every admin-2 x month (zeros included), so county-months with no events
are true zeros. Output also: data/processed/acled_admin2_crosswalk.csv
"""
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from human_common import (RAW, PROC, MONTHS, download, hdx_resources, load_counties, norm_name,
                          finalize, base_meta)

SRC = "acled"
RAWD = RAW / "acled"
MONTHNUM = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August", "September",
     "October", "November", "December"], 1)}

# ACLED admin2 spelling -> OCHA county name (normalized) where they differ
NAME_FIX = {"kajokeji": "kajokeji", "panriang": "pariang", "longchuk": "longochuk", "anzara": "nzara",
            "luakpinynasir": "luakpinynasir", "nasir": "luakpinynasir", "canalpigi": "canalpigi",
            "pigi": "canalpigi", "kapoetaeast": "kapoetaeast", "abyei": "abyei"}


def fetch():
    files = {}
    for pkg, tag in [("south-sudan-acled-conflict-data", "ssd"), ("sudan-acled-conflict-data", "sdn")]:
        for r in hdx_resources(pkg):
            url = r["url"]
            name = url.split("/")[-1]
            kind = ("political_violence" if "political_violence" in name else
                    "civilian_targeting" if "civilian_targeting" in name else
                    "demonstration" if "demonstration" in name else None)
            if not kind:
                continue
            # stable local name (strip the as-of date) so reruns overwrite
            dest = RAWD / f"{tag}_{kind}.xlsx"
            download(url, dest, overwrite=True)
            files[(tag, kind)] = dest
    return files


def read(path):
    x = pd.read_excel(path, sheet_name="Data")
    x["date"] = pd.to_datetime(dict(year=x.Year, month=x.Month.map(MONTHNUM), day=1))
    return x


def main():
    RAWD.mkdir(parents=True, exist_ok=True)
    files = fetch()
    g = load_counties()
    by_norm = {norm_name(n): pid for n, pid in zip(g.name, g.district_id)}
    pcodes = set(g.district_id)

    frames = []
    xw = {}
    for (tag, kind), path in files.items():
        x = read(path)
        if tag == "sdn":
            x = x[x.Admin1.str.strip().str.lower() == "abyei"].copy()
        for (a1, a2, pc), _ in x.groupby(["Admin1", "Admin2", "Admin2 Pcode"]):
            n = norm_name(a2)
            n2 = NAME_FIX.get(n, n)
            if tag == "sdn":
                cid, how = "SS0001", "manual: ACLED codes Abyei Area under Sudan (SD19001)"
            elif pc in pcodes and norm_name(g.set_index("district_id").name[pc]) == n2:
                cid = pc
                how = "pcode+name" if a2 == g.set_index("district_id").name[pc] else "pcode+name variant"
            elif n2 in by_norm:
                cid, how = by_norm[n2], ("name" if n2 == n else "name variant")
                if pc in pcodes and pc != cid:
                    how += f" (ACLED pcode {pc} disagrees)"
            elif pc in pcodes:
                cid, how = pc, "pcode only (name differs)"
            else:
                cid, how = None, "UNMATCHED"
            xw[(a1, a2, pc)] = (cid, how)
        x["county_id"] = [xw[(a, b, c)][0] for a, b, c in zip(x.Admin1, x.Admin2, x["Admin2 Pcode"])]
        x["kind"] = kind
        frames.append(x)

    cw = pd.DataFrame([dict(acled_admin1=k[0], acled_admin2=k[1], acled_admin2_pcode=k[2], county_id=v[0],
                            county_name=(g.set_index("district_id").name.get(v[0]) if v[0] else None),
                            match_method=v[1]) for k, v in xw.items()])
    cw = cw.drop_duplicates().sort_values("county_id")
    PROC.mkdir(parents=True, exist_ok=True)
    cw.to_csv(PROC / "acled_admin2_crosswalk.csv", index=False)
    print(cw[cw.match_method != "pcode+name"].to_string())
    print("unmatched:", (cw.county_id.isna()).sum(), "| counties covered:", cw.county_id.nunique(), "/", len(g))

    a = pd.concat(frames)
    a = a[a.county_id.notna()]
    out = []
    spec = {"political_violence": [("Events", "acled_pv_events"), ("Fatalities", "acled_pv_fatalities")],
            "civilian_targeting": [("Events", "acled_civ_events"), ("Fatalities", "acled_civ_fatalities")],
            "demonstration": [("Events", "acled_demonstrations")]}
    for kind, cols in spec.items():
        sub = a[a.kind == kind]
        for col, var in cols:
            s = sub.groupby(["county_id", "date"])[col].sum()
            # complete grid: aggregate files list all admin2 x months -> missing = 0
            idx = pd.MultiIndex.from_product([sorted(g.district_id), MONTHS], names=["county_id", "date"])
            s = s.reindex(idx, fill_value=0).reset_index().rename(columns={col: "value"})
            s["variable"] = var
            out.append(s)
    df = pd.concat(out)
    df["value"] = df.value.astype(float)

    url = "https://data.humdata.org/dataset/south-sudan-acled-conflict-data"
    common = dict(source="ACLED via HDX (aggregated admin-2 monthly files)", source_url=url,
                  native_resolution="admin-2 (county)", aggregation="sum of ACLED events/fatalities in county-month",
                  higher_is="worse", group="Conflict")
    note = ("ACLED public aggregate; zero = no ACLED-recorded event. Abyei (SS0001) from Sudan file "
            "(Admin1 'Abyei'). Monthly counts are sparse; consider 12-month rolling sums for indexing.")
    meta = [
        base_meta(id="acled_pv_events", label="Political violence events (ACLED)", units="events/month", notes=note, **common),
        base_meta(id="acled_pv_fatalities", label="Political violence fatalities (ACLED)", units="deaths/month", notes=note, **common),
        base_meta(id="acled_civ_events", label="Civilian targeting events (ACLED)", units="events/month", notes=note, **common),
        base_meta(id="acled_civ_fatalities", label="Civilian targeting fatalities (ACLED)", units="deaths/month", notes=note, **common),
        base_meta(id="acled_demonstrations", label="Demonstrations (ACLED)", units="events/month",
                  notes=note + " Demonstrations = protests + riots.", **common),
    ]
    finalize(df, SRC, meta)


if __name__ == "__main__":
    main()
