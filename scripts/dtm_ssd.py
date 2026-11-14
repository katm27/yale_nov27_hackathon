"""IOM DTM South Sudan -> county-month.

A) Mobility Tracking baseline assessments (HDX `south-sudan-displacement-data-idps-returnees-baseline-assessment-iom-dtm`,
   rounds 2,4-16 cover 2018-2025): IDPs and returnees present per county per round; each round's stock value
   is placed at its reference month. Variables `dtm_idps`, `dtm_returnees`.
   (The DTM API / HDX HAPI admin-2 IDP figures for SSD are inflated 4x relative to admin-0 -- not used.)
B) Event Tracking (flash displacement events; 2020-2025 xlsx in data/drive_mirror/01_analysis_ready, also on
   HDX `south-sudan-displacement-data-idps-returnees-emergency-event-tracking-iom-dtm`): individuals newly
   displaced / returning per county per month (month of event start). Variables `dtm_et_*`.
   No 2018-2019 Event Tracking dataset is published (HDX series starts Jan 2020).
"""
import re
import sys
import warnings
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from human_common import (RAW, DATA, MONTHS, download, hdx_resources, load_counties, norm_name, fix_pcode,
                          finalize, base_meta)

warnings.filterwarnings("ignore")
SRC = "dtm"
BL = RAW / "dtm" / "baseline"
ET_DIR = DATA / "drive_mirror" / "01_analysis_ready"
ROUND_DATE = {2: "2018-06", 4: "2018-12", 5: "2019-03", 6: "2019-06", 7: "2019-11", 8: "2020-03", 9: "2020-09",
              10: "2020-12", 11: "2021-09", 12: "2021-12", 13: "2022-08", 14: "2023-04", 15: "2024-09",
              16: "2025-02"}


def fetch_baseline():
    BL.mkdir(parents=True, exist_ok=True)
    for r in hdx_resources("south-sudan-displacement-data-idps-returnees-baseline-assessment-iom-dtm"):
        url = r["url"]
        download(url, BL / url.split("/")[-1])


def round_of(fname):
    m = re.search(r"(?:round-|-r)(\d+)[-_.]", fname)
    return int(m.group(1))


def hxl_table(path, sheet):
    """Read a sheet whose 2nd row holds HXL tags; return df with HXL tag columns."""
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    for i in range(4):
        tags = [str(v).strip() for v in raw.iloc[i].tolist()]
        if any(t.startswith("#") or t == "adm2+code" for t in tags):
            df = raw.iloc[i + 1:].copy()
            df.columns = [t if t != "nan" else f"c{j}" for j, t in enumerate(tags)]
            return df
    raise ValueError(f"no HXL row in {path}:{sheet}")


def num(s):
    return pd.to_numeric(s, errors="coerce").fillna(0)


def extract_round(path):
    rnd = round_of(path.name)
    xl = pd.ExcelFile(path)
    if rnd == 2:
        d = hxl_table(path, "Baseline")
        return pd.DataFrame({"name": d["#adm2 +name"], "pcode": None, "idps": num(d["#population +idps +ind"]),
                             "returnees": num(d["#population +returnees +ind"])})
    if rnd == 4:
        d = pd.read_excel(path, sheet_name="MT_R4_Dataset_Baseline", header=None).iloc[2:]
        # cols: 3 = County P-Code, 8 = IDP individuals (#affected+idps+ind), 72 = # of Returnees (IND)
        return pd.DataFrame({"pcode": d[3], "idps": num(d[8]), "returnees": num(d[72])})
    if rnd == 5:
        i = hxl_table(path, "IDPs at County Level")
        r = pd.read_excel(path, sheet_name="Returnees at County Level")
        r = r[r["ADM2 PCODE"].astype(str).str.match(r"SS\d{4}$")]
        a = pd.DataFrame({"pcode": i["#adm2+code"], "idps": num(i["#affected+idps+ind"]), "returnees": 0.0})
        b = pd.DataFrame({"pcode": r["ADM2 PCODE"], "idps": 0.0, "returnees": num(r["Total Returnees ind"])})
        return pd.concat([a, b])
    if rnd == 6:
        d = pd.read_excel(path, sheet_name="County_78_dataset", header=2)
        return pd.DataFrame({"pcode": d["county_pcode"], "idps": num(d["IDP_all_ind"]), "returnees": num(d["RET_all_ind"])})
    if rnd == 7:
        d = hxl_table(path, "SS_Baseline_R7")
        return pd.DataFrame({"pcode": d["#adm2+code"], "idps": num(d["#affected+idps+ind"]),
                             "returnees": num(d["#affected+returnees+ind"])})
    if rnd in (8, 9, 10, 11, 12):
        sh = [s for s in xl.sheet_names if "count" in s.lower() and "summar" in s.lower()][0]
        d = pd.read_excel(path, sheet_name=sh)
        d.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in d.columns]
        idc = [c for c in d.columns if re.match(r"(?i)Estimated # of IDP individuals \(total\)", c)][0]
        rtc = [c for c in d.columns if re.match(r"(?i)Estimated # of returnee individuals \(total\)", c)][0]
        return pd.DataFrame({"pcode": d["county_pcode"], "idps": num(d[idc]), "returnees": num(d[rtc])})
    if rnd in (13, 14, 15, 16):
        # location-level datasets; named header row (HXL row in R16 is misaligned, so use names).
        # IDPs = internal IDPs + IDPs previously abroad; returnees = internal + from abroad
        sh = [s for s in xl.sheet_names if "Baseline_Loc" in s][0]
        d = pd.read_excel(path, sheet_name=sh).iloc[1:] if rnd > 13 else pd.read_excel(path, sheet_name=sh)
        return pd.DataFrame({"pcode": d["County_INT_PCode"],
                             "idps": num(d["a_idp_inds_ssd"]) + num(d["c_idp_prev_abroad_ind"]),
                             "returnees": num(d["i_returnees_internal_present_ind"]) + num(d["k_abroad_ret_ind"])})
    raise ValueError(rnd)


def mobility_tracking(g):
    by_norm = {norm_name(n): p for n, p in zip(g.name, g.district_id)}
    by_norm.update({"kajokeji": "SS0102", "panyijar": "SS0607", "panyijiar": "SS0607", "nasir": "SS0704",
                    "luakpiny": "SS0704", "pigi": "SS0304", "canal": "SS0304", "abyei": "SS0001",
                    "abyeiadministrativearea": "SS0001", "longechuk": "SS0703", "mayendit": "SS0605"})
    out = []
    for path in sorted(BL.glob("*.xlsx")):
        rnd = round_of(path.name)
        if rnd not in ROUND_DATE:
            continue
        d = extract_round(path)
        if d["pcode"].notna().any():
            d["county_id"] = d["pcode"].map(fix_pcode)
        else:
            d["county_id"] = d["name"].map(lambda n: by_norm.get(norm_name(n)))
        d = d[d.county_id.isin(set(g.district_id))]
        s = d.groupby("county_id")[["idps", "returnees"]].sum()
        print(f"MT round {rnd:>2} ({ROUND_DATE[rnd]}): counties={len(s)} IDPs={s.idps.sum():,.0f} "
              f"returnees={s.returnees.sum():,.0f}")
        s["date"] = pd.Timestamp(ROUND_DATE[rnd] + "-01")
        out.append(s.reset_index())
    mt = pd.concat(out)
    long = mt.melt(id_vars=["county_id", "date"], value_vars=["idps", "returnees"], var_name="v", value_name="value")
    long["variable"] = "dtm_" + long.v
    return long[["county_id", "date", "variable", "value"]]


def read_et(path):
    xl = pd.ExcelFile(path)
    sh = [s for s in xl.sheet_names if re.search(r"(?i)dataset|ET Jan|ET_Data|Event Tracking_", s)]
    sh = [s for s in sh if "dashboard" not in s.lower()][-1]
    d = pd.read_excel(path, sheet_name=sh)
    d.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in d.columns]
    if "Affected population category" in d.columns:  # 2021+ format: one row per event x category
        date = pd.to_datetime(d["Event Started On (From date)"], errors="coerce")
        date = date.fillna(pd.to_datetime(d["Assessment Date"], errors="coerce"))
        trig = d["Movement Trigger"].astype(str)
        return pd.DataFrame({"county_id": d["Event Location: County PCODE"].map(fix_pcode), "date": date,
                             "event": d["Event SSID"].astype(str), "cat": d["Affected population category"].str.strip(),
                             "ind": num(d["No. of Individuals"]), "trigger": trig})
    # 2020 format: one row per event with IDP / returnee columns
    date = pd.to_datetime(d["Period start"], errors="coerce").fillna(pd.to_datetime(d["Date of assessment"], errors="coerce"))
    pc = d["ADM2_PCODE (Destination)"]
    rows = []
    for cat, col in [("IDPs", "Affected population: IDP (ind)"), ("Returnees", "Affected population: Returnee (ind)"),
                     ("Relocated", "Affected population: Relocated (ind)")]:
        rows.append(pd.DataFrame({"county_id": pc.map(fix_pcode), "name": d["ADM2_Name (Destination)"], "date": date,
                                  "event": d.index.astype(str) + "_2020", "cat": cat, "ind": num(d[col]),
                                  "trigger": d["IDPs_Trigger"].astype(str)}))
    return pd.concat(rows)


def event_tracking(g):
    files = sorted(ET_DIR.glob("*Event*Tracking*.xlsx")) + sorted(ET_DIR.glob("*EventTracking*.xlsx"))
    files = sorted(set(files))
    by_norm = {norm_name(n): p for n, p in zip(g.name, g.district_id)}
    by_norm.update({"kajokeji": "SS0102", "panyijar": "SS0607", "nasir": "SS0704", "pigi": "SS0304",
                    "abyei": "SS0001", "abyeiarea": "SS0001", "longechuk": "SS0703", "mayendit": "SS0605"})
    frames = []
    for f in files:
        e = read_et(f)
        if "name" in e:
            miss = e.county_id.isna() | ~e.county_id.isin(set(g.district_id))
            e.loc[miss, "county_id"] = e.loc[miss, "name"].map(lambda n: by_norm.get(norm_name(n)))
        e["file"] = f.name
        # each annual file also carries a few late-reported events from the previous year that may duplicate
        # the previous file (event ids differ between file formats) -> keep only rows dated in the file's year
        fy = int(re.search(r"(20\d\d)", f.name.replace("20210208", "")).group(1))
        e = e[e.date.dt.year == fy]
        frames.append(e)
    e = pd.concat(frames)
    e = e[e.ind > 0]
    e["date"] = e.date.dt.to_period("M").dt.to_timestamp()
    # files overlap slightly (e.g. 2021 file contains late-2020 events): dedupe on event id + category
    e = e.drop_duplicates(["event", "cat", "county_id", "date", "ind"])
    unk = e.county_id.isna() | ~e.county_id.isin(set(g.district_id))
    print(f"ET rows {len(e)}; unmatched county rows {unk.sum()} ({e[unk].ind.sum():,.0f} ind)")
    e = e[~unk]
    trig = e.trigger.str.lower()
    e["conflict"] = trig.str.contains("conflict|clash|violence|attack|insecur|fighting")
    e["flood"] = trig.str.contains("flood|disaster")
    idp = e[e.cat == "IDPs"]
    ret = e[e.cat == "Returnees"]
    parts = {
        "dtm_et_new_idps": idp.groupby(["county_id", "date"]).ind.sum(),
        "dtm_et_new_idps_conflict": idp[idp.conflict].groupby(["county_id", "date"]).ind.sum(),
        "dtm_et_new_idps_disaster": idp[idp.flood].groupby(["county_id", "date"]).ind.sum(),
        "dtm_et_returnees": ret.groupby(["county_id", "date"]).ind.sum(),
        "dtm_et_events": e.groupby(["county_id", "date"]).event.nunique(),
    }
    print("ET months covered:", e.date.min().date(), "->", e.date.max().date())
    # zero-fill only within the Event Tracking period (Jan 2020 onwards)
    months = [m for m in MONTHS if m >= pd.Timestamp("2020-01-01")]
    out = []
    for var, s in parts.items():
        idx = pd.MultiIndex.from_product([sorted(g.district_id), months], names=["county_id", "date"])
        s.index.names = ["county_id", "date"]
        s = s.reindex(idx, fill_value=0).rename("value").reset_index()
        s["variable"] = var
        out.append(s)
    return pd.concat(out)


def main():
    fetch_baseline()
    g = load_counties()
    mt = mobility_tracking(g)
    et = event_tracking(g)
    df = pd.concat([mt, et])
    df["value"] = df.value.astype(float)
    mt_url = "https://data.humdata.org/dataset/south-sudan-displacement-data-idps-returnees-baseline-assessment-iom-dtm"
    et_url = "https://data.humdata.org/dataset/south-sudan-displacement-data-idps-returnees-emergency-event-tracking-iom-dtm"
    mt_c = dict(source="IOM DTM South Sudan Mobility Tracking - Baseline Assessment (rounds 2,4-16)", source_url=mt_url,
                native_resolution="county (from location-level baseline)", temporal="irregular (per round)",
                group="Displacement",
                notes="Stock at round reference month (2018-06, 2018-12, 2019-03, 2019-06, 2019-11, 2020-03, 2020-09, "
                      "2020-12, 2021-09, 2021-12, 2022-08, 2023-04, 2024-09, 2025-02); no values between rounds. "
                      "Round 2 (Jun 2018) has partial coverage; rounds 1 and 3 not published at county level.")
    et_c = dict(source="IOM DTM South Sudan Event Tracking (2020-2025)", source_url=et_url,
                native_resolution="county (event location)", group="Displacement",
                aggregation="sum of individuals over Event Tracking records, by month of event start",
                notes="Flash-displacement monitoring of sudden events; not exhaustive -- zeros (Jan 2020+) mean "
                      "no event tracked. No 2018-2019 data published. 2024-25 includes arrivals fleeing Sudan war.")
    meta = [
        base_meta(id="dtm_idps", label="IDPs present (DTM)", units="persons", higher_is="worse",
                  aggregation="sum over baseline locations in county", **mt_c),
        base_meta(id="dtm_returnees", label="Returnees present (DTM)", units="persons", higher_is="neutral",
                  aggregation="sum over baseline locations in county (internal + from abroad)", **mt_c),
        base_meta(id="dtm_et_new_idps", label="Newly displaced persons (DTM event tracking)", units="persons/month",
                  higher_is="worse", **et_c),
        base_meta(id="dtm_et_new_idps_conflict", label="Newly displaced by conflict (DTM ET)", units="persons/month",
                  higher_is="worse", **et_c),
        base_meta(id="dtm_et_new_idps_disaster", label="Newly displaced by floods/disaster (DTM ET)",
                  units="persons/month", higher_is="worse", **et_c),
        base_meta(id="dtm_et_returnees", label="New returnee arrivals (DTM event tracking)", units="persons/month",
                  higher_is="neutral", **et_c),
        base_meta(id="dtm_et_events", label="Displacement events tracked (DTM)", units="events/month",
                  higher_is="worse", **dict(et_c, aggregation="count of distinct Event Tracking records")),
    ]
    finalize(df, SRC, meta)


if __name__ == "__main__":
    main()
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from trend_stats import write_trends
    write_trends("dtm")  # Mann-Kendall + Sen's slope (scripts/trend_stats.py)
