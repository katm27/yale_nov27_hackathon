"""Build data/crosswalks/county_crosswalk_master.csv: one row per OCHA COD-AB v03 county (79 incl. Abyei SS0001)
with every code / name variant used by the project's sources, harvested from the raw files.

Gold standard: data/counties.geojson (district_id, name, admin1) - never modified here.
Each harvested (code, name) pair is resolved to an OCHA P-code by code where the code's OCHA name agrees with the
name (after normalisation / curated aliases), else by name. Disagreements are printed (there are none for SS codes:
IOM DTM uses the OCHA admin-2 numbering for all 78 counties; only Abyei differs, SS1101).

Run: python scripts/build_county_crosswalk.py   (reads raw files only; no downloads)
"""
import io
import json
import re
import sys
import unicodedata
import zipfile
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw"
OUT = ROOT / "data/crosswalks/county_crosswalk_master.csv"

# curated aliases (normalised name -> OCHA P-code). Each one checked against payam/location data or the
# source's own state/code columns (see docs/AUDIT_county_crosswalk.md).
MANUAL = {
    "kajokeji": "SS0102", "kajokaii": "SS0102", "kajokejicounty": "SS0102",
    "yeicounty": "SS0106", "yeiriver": "SS0106",
    "lopa": "SS0206", "lopalafon": "SS0206",
    "bor": "SS0303", "southbor": "SS0303",
    "canal": "SS0304", "pigi": "SS0304", "piji": "SS0304", "khorflus": "SS0304", "khorfulus": "SS0304",
    "oldfangak": "SS0306", "nyirol diror": "SS0307", "nyiroldiror": "SS0307", "urorwunror": "SS0311",
    "greaterpibor": "SS0308", "boma": "SS0308",  # Boma = payam SS030801 of Pibor (not the 2015-20 Boma State)
    "rumbekcenter": "SS0403", "aweilcentral": "SS0501", "aweilcenter": "SS0501", "awielcentre": "SS0501",
    "aweiltown": "SS0501", "awielsouth": "SS0504",
    "abiemnom": "SS0601", "mayiendit": "SS0605", "mayiandit": "SS0605",
    "panyijar": "SS0607", "panyinjiar": "SS0607", "pariangruweng": "SS0608", "ruweng": "SS0608", "panriang": "SS0608",
    "rubkoana": "SS0609",
    "akoka": "SS0701",  # Akoka = payam SS070103 of Baliet (IPC/WHO/SSSAMS list it separately)
    "longechuk": "SS0703", "longchuk": "SS0703", "longchok": "SS0703",
    "nasir": "SS0704", "luakpiny": "SS0704", "malut": "SS0709",
    "raga": "SS0902", "waururalonly": "SS0903", "anzara": "SS1008",
    "abyeiregion": "SS0001", "abyeiarea": "SS0001", "abyeiadministrativearea": "SS0001",
    "abyeiadministrativeareaadmin2": "SS0001", "abyeiregionadmin3poc": "SS0001",
}
# names that denote MORE than one county -> never resolved to a single county
MULTI = {"ruwengadministrativearea": ["SS0601", "SS0608"],
         "greaterpiboradministrativearea": ["SS0308", "SS0309"], "greatpiboradministrativearea": ["SS0308", "SS0309"],
         "piboradministrativearea": ["SS0308", "SS0309"],
         "duktwiceast": ["SS0305", "SS0310"], "ss0305ss0310": ["SS0305", "SS0310"]}
ADMIN_AREA = {"SS0001": "Abyei Administrative Area (AAA; final status undetermined, also claimed by Sudan)",
              "SS0308": "Greater Pibor Administrative Area (GPAA, Feb 2020; = Pibor + Pochalla)",
              "SS0309": "Greater Pibor Administrative Area (GPAA, Feb 2020; = Pibor + Pochalla)",
              "SS0601": "Ruweng Administrative Area (RAA, Feb 2020; = Pariang + Abiemnhom)",
              "SS0608": "Ruweng Administrative Area (RAA, Feb 2020; = Pariang + Abiemnhom)"}
SUBAREAS = {"SS0701": "Akoka payam (SS070103) reported separately by IPC (2023+), WHO immunization 2018, SSSAMS 2015 -> summed into Baliet",
            "SS0903": "IPC 2018-09+ analyses 'Wau (Rural Only)' (Wau town not analysed as part of the county)",
            "SS0304": "HQ Khorfulus (WHO 'KHORFLUS')", "SS0306": "'Old Fangak' (WHO, SSSAMS)",
            "SS0308": "Boma payam (SS030801); 2015-20 Boma State (Pibor+Pochalla) is NOT the payam",
            "SS0305": "ET 2020 origin 'SS0305/SS0310 Duk/Twic East' (combined) split 50/50 in et_flows",
            "SS0310": "ET 2020 origin 'SS0305/SS0310 Duk/Twic East' (combined) split 50/50 in et_flows",
            "SS0711": "IOM FMR 'Renk River Port' (11.761,32.780) falls on the Manyo side of the COD-AB river line; assigned to Renk"}


def nn(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"other admin ?2", " ", s)
    return re.sub(r"[^a-z0-9]", "", s)


def main():
    gj = json.load(open(ROOT / "data/counties.geojson"))
    gold = {f["properties"]["district_id"]: f["properties"] for f in gj["features"]}
    by_name = {nn(p["name"]): c for c, p in gold.items()}
    look = dict(by_name, **MANUAL)

    names = defaultdict(lambda: defaultdict(set))  # pcode -> source -> names
    codes = defaultdict(lambda: defaultdict(set))  # pcode -> source -> codes
    problems = []

    def add(src, code, name, state=""):
        code = "" if code is None or str(code) in ("nan", "None") else str(code).strip()
        name = "" if name is None or str(name) in ("nan", "None") else str(name).strip()
        if not name and not code:
            return
        k = nn(name)
        by_nm = look.get(k) if k else None
        if k in MULTI:
            return
        pc = None
        if code in gold:
            pc = code
            if by_nm and by_nm != code:
                problems.append((src, code, name, f"code->{gold[code]['name']} but name->{by_nm}"))
        elif by_nm:
            pc = by_nm
            if code:
                codes[pc][src].add(code)
        else:
            if re.fullmatch(r"SS\d{4}", code) or (name and not code):
                problems.append((src, code, name, "unresolved"))
            return
        if name:
            names[pc][src].add(name)

    # ---- IOM DTM Mobility Tracking (county summary / location datasets)
    mt = pd.read_csv(ROOT / "data/raw/ssd_unified/counties_lookup.csv", dtype=str)
    for r in mt.itertuples():
        codes[r.county_pcode]["iom"].add(r.iom_pcode)
    sys.path.insert(0, str(ROOT / "scripts"))
    for p in sorted((RAW / "dtm/baseline").glob("*.xlsx")):
        xl = pd.ExcelFile(p)
        for sh in xl.sheet_names:
            raw = pd.read_excel(p, sheet_name=sh, header=None, nrows=4000)
            for i in range(3):
                hdr = [str(x).strip() for x in raw.iloc[i]]
                ci = [j for j, h in enumerate(hdr) if re.fullmatch(r"(?i)(county[ _]?(int_)?p-?code|adm2 ?pcode|#?adm2\+code)", h)]
                ni = [j for j, h in enumerate(hdr) if re.fullmatch(r"(?i)(county([ _]name)?|adm2[ _]?en|#adm2 ?\+name)", h)]
                if ni:
                    d = raw.iloc[i + 1:]
                    for c, n in zip(d[ci[0]] if ci else [None] * len(d), d[ni[0]]):
                        if str(n).startswith("#") or str(n).lower() in ("total", "county_name"):
                            continue
                        add("iom_dtm", c, n)
                    break
    # ---- IOM DTM Event Tracking (event location + SSD origins)
    for p in sorted(set((ROOT / "data/drive_mirror/01_analysis_ready").glob("*Event*Tracking*.xlsx")) |
                    set((ROOT / "data/drive_mirror/01_analysis_ready").glob("*EventTracking*.xlsx"))):
        xl = pd.ExcelFile(p)
        sh = [s for s in xl.sheet_names if re.search(r"(?i)dataset|ET Jan|ET_Data|Event Tracking_", s)]
        d = pd.read_excel(p, sheet_name=[s for s in sh if "dashboard" not in s.lower()][-1])
        d.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in d.columns]
        for cc, nc in [("Event Location: County PCODE", "Event Location: County (Admin 2)"),
                       ("ADM2_PCODE (Destination)", "ADM2_Name (Destination)"),
                       ("Arrival from: Admin 2 PCODE", "Arrival from: County (Admin 2)"),
                       ("ADM2_PCODE (From)", "Admin 2 Name (From)")]:
            if cc in d and nc in d:
                for c, n in d[[cc, nc]].drop_duplicates().itertuples(index=False):
                    if str(c).startswith("SS"):
                        add("iom_dtm", c, n)
    # ---- FMR (team unified dataset)
    z = zipfile.ZipFile(RAW / "ssd_unified/ssd_unified_dataset.zip")
    f = pd.read_csv(io.BytesIO(z.read("fmr/fmr_internal_forced_2020_2025_filled.csv")), low_memory=False)
    for a, b in [("dep.adm2.pcode", "dep.adm2"), ("dest.adm2.pcode", "dest.adm2")]:
        for c, n in f[[a, b]].drop_duplicates().itertuples(index=False):
            add("iom_dtm", c, n)
    # ---- OCHA HNO / 3W / HAPI
    H = RAW / "ocha_hno"
    old = pd.read_excel(H / "ssd_hno_2019.xlsx").iloc[1:]
    for c, n in zip(old.Pcode2, old["Admin Level 2"]):
        add("ocha", None, n)
        pc = look.get(nn(n))
        if pc:
            codes[pc]["ocha_numeric_pre2015"].add(str(c))
    for fn, sh, hdr, c, n in [("ssd_peopletargeted_peopleinneed_2021.xlsx", "PiN_by_cluster", 0, "ADM2_Pcode", "ADM2_COUNTY"),
                              ("ssd_humanitarian_needs_overview_2022.xlsx", "PIN", 0, "ADM2_Pcode", "ADM2_COUNTY"),
                              ("ssd_humanitarian_needs_overview_2023.xlsx", "HNO 2023 PIN", 2, "Admin 2 P-Code", "Admin 2"),
                              ("ssd_humanitarian_needs_overview_2023.xlsx", "HNO 2023 severity", 1, "Admin2 Pcode", "Admin2"),
                              ("south-sudan-humanitarian-needs-and-response-plan-2024.xlsx", "Severity_Prioritization", 0, None, "Admin two")]:
        d = pd.read_excel(H / fn, sheet_name=sh, header=hdr)
        for cc, n_ in zip(d[c] if c else [None] * len(d), d[n]):
            if not str(n_).startswith("#"):
                add("ocha", cc, n_)
    for fn in ["humanitarian_needs", "operational_presence", "food_security", "idps"]:
        d = pd.read_csv(RAW / f"hdx_hapi/hdx_hapi_{fn}_ssd.csv", low_memory=False)
        d = d[d.admin_level == 2][["admin2_code", "admin2_name", "provider_admin2_name"]].drop_duplicates()
        for c, n, pn in d.itertuples(index=False):
            add("ocha", c, n)
            add("ocha", c if str(c).startswith("SS") else None, pn)
    W = RAW / "ocha_3w"
    for fn in sorted(W.glob("*.xlsx")):
        xl = pd.ExcelFile(fn)
        for sh in xl.sheet_names:
            d = pd.read_excel(fn, sheet_name=sh)
            if "#adm2+code" in d:
                for c, n in d[["#adm2+code", "#adm2+name"]].drop_duplicates().itertuples(index=False):
                    add("ocha", c, n)
            elif "County" in d:
                for n in d.County.dropna().unique():
                    add("ocha", None, n)
    # ---- ACLED
    for fn in sorted((RAW / "acled").glob("ssd_*.xlsx")):
        d = pd.read_excel(fn, sheet_name="Data")[["Admin2", "Admin2 Pcode"]].drop_duplicates()
        for n, c in d.itertuples(index=False):
            add("acled", c, n)
    codes["SS0001"]["acled"].add("SD19001")
    names["SS0001"]["acled"].add("Abyei (ACLED Sudan file, Admin1 Abyei)")
    # ---- IPC
    d = pd.read_csv(RAW / "ipc/ipc_ssd_area_long.csv")
    for n in d.Area.dropna().unique():
        if not str(n).startswith("#") and n != "Returnees":
            add("ipc", None, n)
    g = pd.read_excel(RAW / "ipc/all-countries-2017-2023.xlsx", header=None, skiprows=12)
    g = g[g[0].astype(str).str.startswith("South Sudan") & g[2].notna()]
    for n in g[2].unique():
        add("ipc", None, n)
    # ---- WFP markets (admin2 label + market names; the pipeline joins markets spatially)
    import geopandas as gpd
    cg = gpd.read_file(ROOT / "data/counties.geojson")
    m = pd.read_csv(RAW / "wfp_prices/wfp_markets_ssd.csv")
    m = m[pd.to_numeric(m.latitude, errors="coerce").notna()]
    gm = gpd.GeoDataFrame(m, geometry=gpd.points_from_xy(m.longitude.astype(float), m.latitude.astype(float)), crs=4326)
    gm = gpd.sjoin(gm, cg[["district_id", "geometry"]], how="left")
    wfp_markets = defaultdict(set)
    for r in gm.itertuples():
        if isinstance(r.district_id, str):
            wfp_markets[r.district_id].add(r.market)
            if look.get(nn(r.admin2)) != r.district_id:
                problems.append(("wfp", r.market, r.admin2, f"admin2 label -> {look.get(nn(r.admin2))}, coords -> {r.district_id}"))
        add("wfp", None, r.admin2)
    # ---- WHO immunization 2018, WHO MFL 2025, SSSAMS 2015
    v = pd.read_excel(RAW / "public_health/who_subnational_immunization_2020.xlsx", sheet_name="Data")
    for n in v[v.iso == "SSD"].Admin2.unique():
        add("who", None, n)
    h = pd.read_excel(RAW / "health/who_mfl_apr2025.xlsx")[["county_code", "county"]].drop_duplicates()
    for c, n in h.itertuples(index=False):
        add("who", c, n)
    s = pd.read_excel(RAW / "education/sssams_2015.xlsx", sheet_name=0)
    for n in s.County.dropna().unique():
        add("sssams", None, n)
    # ---- UNHCR camps (curated, scripts/unhcr_ssd.py)
    from unhcr_ssd import CAMP_COUNTY
    unhcr = defaultdict(set)
    for k, pc in CAMP_COUNTY.items():
        unhcr[pc].add(k.title())
    # ---- GADM 4.1 level-2 (45 pre-2011 provinces, NOT counties): area overlap precomputed from
    # https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_SSD_2.json.zip (units covering >5% of the county)
    gadm = {}
    gp = ROOT / "data/crosswalks/gadm41_overlap.csv"
    if gp.exists():
        o = pd.read_csv(gp)
        for pc, sub in o.groupby("district_id"):
            sub = sub.sort_values("share_of_ocha", ascending=False)
            gadm[pc] = "; ".join(f"{r.NAME_2} ({r.share_of_ocha:.0%})" for r in sub.itertuples())

    rows = []
    for pc, p in sorted(gold.items()):
        j = lambda src: "; ".join(sorted(names[pc][src] - {p["name"]}))
        rows.append(dict(
            county_pcode=pc, county_name=p["name"], admin1_name=p["admin1"], admin1_pcode=pc[:4],
            admin_area_2020=ADMIN_AREA.get(pc, ""),
            iom_pcode="; ".join(sorted(codes[pc]["iom"])),
            other_pcodes="; ".join(sorted({c for s in ("iom_dtm", "ocha", "acled", "who", "wfp") for c in codes[pc][s]} - {pc})),
            ocha_numeric_code_pre2015="; ".join(sorted(codes[pc]["ocha_numeric_pre2015"])),
            names_iom_dtm=j("iom_dtm"), names_ocha_hno_3w_hapi=j("ocha"), names_acled=j("acled"), names_ipc=j("ipc"),
            names_wfp_admin2=j("wfp"), wfp_markets="; ".join(sorted(wfp_markets[pc])), names_who=j("who"),
            names_sssams_2015=j("sssams"), unhcr_locations="; ".join(sorted(unhcr[pc])),
            gadm41_level2_overlap=gadm.get(pc, ""),
            manual_aliases="; ".join(sorted(k for k, v in MANUAL.items() if v == pc)),
            sub_areas_and_notes=SUBAREAS.get(pc, ""),
        ))
    out = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    multi = pd.DataFrame([dict(alias=k, county_pcodes=";".join(v)) for k, v in MULTI.items()])
    multi.to_csv(OUT.with_name("county_multi_unit_aliases.csv"), index=False)
    print(f"wrote {OUT} ({len(out)} rows)")
    print("problems / notes:")
    for p_ in sorted(set(problems)):
        print("  ", p_)


if __name__ == "__main__":
    main()
