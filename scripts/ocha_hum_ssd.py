"""OCHA humanitarian context for South Sudan counties: people in need (HNO), severity, and operational
presence (3W: number of humanitarian organisations per county per month).

- People in need (intersectoral, by HNO year; placed at YYYY-07-01, temporal annual):
    2019, 2021, 2022, 2023: HDX `south-sudan-humanitarian-needs` county workbooks
    2024, 2025: HDX HAPI humanitarian-needs (Intersectoral, category 'total', status INN) for SSD
    (no county HNO file for 2018 or 2020 on HDX)
- Intersectoral severity (1-5): HNO 2022, 2023, 2024 workbooks
- Operational presence: HDX `south-sudan-operational-presence` monthly 3W (Jan 2019 - Dec 2025;
  Dec 2020 missing) -> distinct organisations reporting activity in county-month (+ national NGOs).
- HAPI funding for SSD is national (appeal-level) only -> not usable at county level.
"""
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from human_common import RAW, download, hdx_resources, load_counties, norm_name, fix_pcode, finalize, base_meta

SRC = "ocha_hum"
HNO = RAW / "ocha_hno"
W3 = RAW / "ocha_3w"
HAPI = RAW / "hdx_hapi"
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
ALIAS = {"abyeiregion": "abyei", "abyeiadministrativearea": "abyei", "abyeiarea": "abyei", "raga": "raja", "kajokeji": "kajokeji",
         "panyijar": "panyijiar", "nasir": "luakpinynasir", "pigi": "canalpigi", "canal": "canalpigi",
         "longechuk": "longochuk", "yeicounty": "yei", "bor": "borsouth", "pibor": "pibor",
         "kapoetaeast": "kapoetaeast", "mayendit": "mayendit"}
W3_FILES = {2019: "ss_20200616_3w_op_jan-dec_2019.xlsx", 2020: "ss_20210119_3w_op_jan-november_2020.xlsx",
            2021: "ss_20220130_3w_op_january-december_2021.xlsx", 2022: "ss_20230216_3w_op_january-december_2022.xlsx",
            2023: "ss_20240104_3w_op_january-to-december_2023.xlsx",
            2024: "ss_20250206_3w_oerational-presence_jan-to-dec_2024.xlsx",
            2025: "ss_20262006_3w_operational-presence_jan-dec_2025.xlsx"}
HNO_FILES = {2019: "ssd_hno_2019.xlsx", 2021: "ssd_peopletargeted_peopleinneed_2021.xlsx",
             2022: "ssd_humanitarian_needs_overview_2022.xlsx", 2023: "ssd_humanitarian_needs_overview_2023.xlsx",
             2024: "south-sudan-humanitarian-needs-and-response-plan-2024.xlsx"}


def fetch():
    for d, pkg, names in [(W3, "south-sudan-operational-presence", W3_FILES.values()),
                          (HNO, "south-sudan-humanitarian-needs", HNO_FILES.values())]:
        res = {r["url"].split("/")[-1]: r["url"] for r in hdx_resources(pkg)}
        for n in names:
            if n in res:
                download(res[n], d / n)
    for r in hdx_resources("hdx-hapi-ssd"):
        n = r["url"].split("/")[-1]
        if n in ("hdx_hapi_humanitarian_needs_ssd.csv", "hdx_hapi_operational_presence_ssd.csv", "hdx_hapi_funding_ssd.csv"):
            download(r["url"], HAPI / n, overwrite=True)


def lookup_factory():
    g = load_counties()
    m = {norm_name(n): p for n, p in zip(g.name, g.district_id)}
    return lambda n: m.get(ALIAS.get(norm_name(n), norm_name(n)))


def hno(lookup):
    rows = []
    d = pd.read_excel(HNO / HNO_FILES[2019]).iloc[1:]
    rows += [(lookup(a), 2019, "hno_pin", v) for a, v in zip(d["Admin Level 2"], d.iloc[:, -1])]
    d = pd.read_excel(HNO / HNO_FILES[2021], sheet_name="PiN_by_cluster").iloc[1:]
    rows += [(fix_pcode(p), 2021, "hno_pin", v) for p, v in zip(d.ADM2_Pcode, d["People in need"])]
    d = pd.read_excel(HNO / HNO_FILES[2022], sheet_name="PIN").iloc[1:]
    rows += [(fix_pcode(p), 2022, "hno_pin", v) for p, v in zip(d.ADM2_Pcode, d["Total PiN"])]
    rows += [(fix_pcode(p), 2022, "hno_severity", v) for p, v in zip(d.ADM2_Pcode, d.iloc[:, 6])]
    d = pd.read_excel(HNO / HNO_FILES[2023], sheet_name="HNO 2023 PIN", header=2)
    d["pin"] = pd.to_numeric(d["Final PiN (without Abyei)"], errors="coerce").fillna(
        pd.to_numeric(d["Preliminary PiN"], errors="coerce"))
    s = d.groupby("Admin 2 P-Code").pin.sum()
    rows += [(fix_pcode(p), 2023, "hno_pin", v) for p, v in s.items()]
    d = pd.read_excel(HNO / HNO_FILES[2023], sheet_name="HNO 2023 severity", header=1)
    rows += [(fix_pcode(p), 2023, "hno_severity", v) for p, v in zip(d["Admin2 Pcode"], d.iloc[:, -1])]
    d = pd.read_excel(HNO / HNO_FILES[2024], sheet_name="Severity_Prioritization")
    rows += [(lookup(a), 2024, "hno_severity", v) for a, v in zip(d["Admin two"], d["InterSectoral_Severity"])]
    h = pd.read_csv(HAPI / "hdx_hapi_humanitarian_needs_ssd.csv")
    h = h[(h.admin_level == 2) & (h.sector_name == "Intersectoral") & (h.category == "total") & (h.population_status == "INN")]
    rows += [(fix_pcode(p), int(y[:4]), "hno_pin", v) for p, y, v in zip(h.admin2_code, h.reference_period_start, h.population)]
    df = pd.DataFrame(rows, columns=["county_id", "year", "variable", "value"])
    df["value"] = pd.to_numeric(df.value, errors="coerce")
    bad = df[df.county_id.isna()]
    if len(bad):
        print("HNO rows not matched:", len(bad))
    df = df.dropna()
    df = df.groupby(["county_id", "year", "variable"]).value.sum().reset_index()
    df["date"] = pd.to_datetime(df.year.astype(str) + "-07-01")
    print(df.groupby(["variable", "year"]).agg(n=("value", "size"), total=("value", "sum")).to_string())
    return df[["county_id", "date", "variable", "value"]]


def month_num(v, year):
    if isinstance(v, pd.Timestamp) or hasattr(v, "month"):
        return pd.Timestamp(v).month
    s = str(v).strip().lower()
    if re.fullmatch(r"\d+(\.0)?", s):
        return int(float(s))
    return MONTHS.get(s[:3])


def ops(lookup):
    frames = []
    for year, fn in W3_FILES.items():
        path = W3 / fn
        xl = pd.ExcelFile(path)
        if year in (2019, 2020):
            sheets = [s for s in xl.sheet_names if s.lower()[:3] in MONTHS or s.lower().startswith("mac")]
            for s in sheets:
                d = pd.read_excel(path, sheet_name=s)
                d = d[~d.iloc[:, 0].astype(str).str.startswith("#")]
                m = MONTHS.get(s.lower()[:3], 3)
                frames.append(pd.DataFrame({"county": d.County, "org": d.Acronym.fillna(d.Organisation),
                                            "type": d["Org Type"], "year": year, "month": m}))
        elif year in (2021, 2022):
            sh = "January to December" if year == 2021 else "Jan to Dec"
            d = pd.read_excel(path, sheet_name=sh)
            frames.append(pd.DataFrame({"pcode": d["#adm2+code"], "county": d["#adm2+name"], "org": d["#org+reporting"],
                                        "type": d["#org+reporting+type"], "year": year,
                                        "month": [month_num(v, year) for v in d["#date"]]}))
        elif year == 2023:
            d = pd.read_excel(path, sheet_name="3W")
            frames.append(pd.DataFrame({"county": d.County, "org": d.Organization, "type": d["Organization Type"],
                                        "year": year, "month": pd.to_numeric(d["Month Number"], errors="coerce")}))
        else:
            d = pd.read_excel(path, sheet_name=xl.sheet_names[0])
            dt = pd.to_datetime(d["Reporting Month"], errors="coerce")
            frames.append(pd.DataFrame({"county": d.County, "org": d.Acronym.fillna(d["Name of organization"]),
                                        "type": d.Type, "year": year, "month": dt.dt.month}))
    o = pd.concat(frames, ignore_index=True)
    o["county_id"] = o.pcode.map(fix_pcode) if "pcode" in o else None
    o["county_id"] = o.county_id.where(o.county_id.notna(), o.county.map(lambda c: lookup(c) if pd.notna(c) else None))
    un = o[o.county_id.isna()].county.value_counts()
    print("3W rows not matched to county:", len(o[o.county_id.isna()]), dict(list(un.items())[:12]))
    o = o.dropna(subset=["county_id", "month", "org"])
    o["org"] = o.org.astype(str).str.strip().str.upper()
    o["date"] = pd.to_datetime(dict(year=o.year, month=o.month.astype(int), day=1))
    t = o.type.astype(str).str.lower()
    o["nngo"] = t.str.contains("national|nngo") & ~t.str.contains("international")
    a = o.groupby(["county_id", "date"]).org.nunique().rename("value").reset_index().assign(variable="ops_orgs")
    b = o[o.nngo].groupby(["county_id", "date"]).org.nunique().rename("value").reset_index().assign(variable="ops_orgs_national_ngo")
    months = sorted(o.date.unique())
    # zero-fill within reported months: a county absent from a month's 3W had no reported partner
    out = []
    for df in (a, b):
        var = df.variable.iloc[0]
        idx = pd.MultiIndex.from_product([sorted(load_counties().district_id), months], names=["county_id", "date"])
        s = df.set_index(["county_id", "date"]).value.reindex(idx, fill_value=0).reset_index()
        s["variable"] = var
        out.append(s)
    r = pd.concat(out)
    print("3W months:", len(months), pd.Timestamp(months[0]).date(), "->", pd.Timestamp(months[-1]).date())
    return r


def main():
    fetch()
    lookup = lookup_factory()
    df = pd.concat([hno(lookup), ops(lookup)])
    df["value"] = df.value.astype(float)
    hno_c = dict(source="OCHA South Sudan Humanitarian Needs Overview (HDX; HAPI for 2024-25)",
                 source_url="https://data.humdata.org/dataset/south-sudan-humanitarian-needs",
                 native_resolution="county", temporal="annual", group="Humanitarian needs", higher_is="worse")
    ops_c = dict(source="OCHA South Sudan 3W operational presence (HDX)",
                 source_url="https://data.humdata.org/dataset/south-sudan-operational-presence",
                 native_resolution="county", group="Humanitarian response", higher_is="better",
                 aggregation="distinct reporting organisations with activities in county-month")
    meta = [
        base_meta(id="hno_pin", label="People in need (HNO, intersectoral)", units="persons",
                  aggregation="county intersectoral PiN for the HNO year",
                  notes="HNO years 2019, 2021-2025 (none for 2018/2020); value placed at July of the plan year. "
                        "Methodology changed between years (2019 = max of cluster PiN incl. refugees; 2023 summed over "
                        "population groups) - compare levels across years with caution.", **hno_c),
        base_meta(id="hno_severity", label="Humanitarian severity (HNO intersectoral, 1-5)", units="severity 1-5",
                  aggregation="intersectoral severity phase", index_ok=False,
                  notes="Available for HNO 2022, 2023, 2024 only.", **hno_c),
        base_meta(id="ops_orgs", label="Humanitarian organisations present (3W)", units="organisations",
                  notes="Monthly 3W, Jan 2019 - Dec 2025 (Dec 2020 missing; no 2018). 0 = no partner reported in "
                        "county that month. Reporting coverage grew over time - partly a reporting artefact.", **ops_c),
        base_meta(id="ops_orgs_national_ngo", label="National NGOs present (3W)", units="organisations",
                  notes="Subset of ops_orgs with organisation type National NGO.", **ops_c),
    ]
    finalize(df, SRC, meta)


if __name__ == "__main__":
    main()
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from trend_stats import write_trends
    write_trends("ocha_hum")  # Mann-Kendall + Sen's slope (scripts/trend_stats.py)
