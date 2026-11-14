"""IPC acute food insecurity (AFI) + acute malnutrition (AMN) for South Sudan counties.

AFI, current-period figures only (projections ignored), value placed at the first month of the current
analysis period:
  - 2018-2022: HDX `ipc-country-data` "All Countries-2017-2023.xlsx" (area rows incl. Area Phase)
  - 2022-2025: HDX `south-sudan-acute-food-insecurity-country-data` ipc_ssd_area_long.csv (populations by
    phase; area phase not given -> derived with the IPC 20% rule: most severe phase such that >=20% of the
    population is in that phase or worse; rule checked against the 2018-2022 published phases)
  Sub-county areas (e.g. Akoka -> Baliet, 'Wau (Rural Only)' -> Wau) are summed into counties; the
  non-geographic 'Returnees' group is dropped.
AMN: IPC AMN county phase for Jul-Sep 2025 (current) from HDX `south-sudan-acute-malnutrition`
  (projection-update workbook). Earlier county AMN tables are not on HDX in machine-readable form.
"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from human_common import RAW, download, hdx_resources, load_counties, norm_name, finalize, base_meta

SRC = "ipc"
RAWD = RAW / "ipc"
ALIAS = {"raga": "raja", "waururalonly": "wau", "yeicounty": "yei", "abyeiregion": "abyei",
         "akoka": "baliet", "kajokeji": "kajokeji"}


def county_lookup():
    g = load_counties()
    m = {norm_name(n): p for n, p in zip(g.name, g.district_id)}
    return lambda name: m.get(ALIAS.get(norm_name(name), norm_name(name)))


def fetch():
    RAWD.mkdir(parents=True, exist_ok=True)
    for r in hdx_resources("ipc-country-data"):
        download(r["url"], RAWD / "all-countries-2017-2023.xlsx")
    for r in hdx_resources("south-sudan-acute-food-insecurity-country-data"):
        n = r["url"].split("/")[-1]
        if n in ("ipc_ssd_area_long.csv", "ipc_ssd_area_wide.csv"):
            download(r["url"], RAWD / n, overwrite=True)
    for r in hdx_resources("south-sudan-acute-malnutrition"):
        n = r["url"].split("/")[-1]
        if "projectionupdate_amn" in n:
            download(r["url"], RAWD / "ipc_amn_projection_update.xlsx", overwrite=True)


def phase_from_shares(p):  # p: array of fractions phase1..5
    cum = np.cumsum(p[::-1])[::-1]  # share in phase k or worse
    for k in range(5, 0, -1):
        if cum[k - 1] >= 0.2:
            return k
    return 1


def global_xlsx(lookup):
    d = pd.read_excel(RAWD / "all-countries-2017-2023.xlsx", header=None, skiprows=12)
    d = d[d[0].astype(str).str.startswith("South Sudan")].copy()
    # header rows (col2 NaN) carry the analysis name and current period for the block that follows
    d["analysis"] = np.where(d[2].isna(), d[0], np.nan)
    d["analysis"] = d["analysis"].ffill()
    per = d[d[2].isna()].set_index(0)[[10, 5]]
    d = d[d[2].notna()]
    rows = []
    for a, sub in d.groupby("analysis"):
        period, dan = per.loc[a, 10], per.loc[a, 5]
        start = str(period).split(" - ")[0] if isinstance(period, str) else dan
        date = pd.to_datetime(start, format="%b %Y")
        for r in sub.itertuples(index=False):
            r = list(r)
            pop = r[7]
            if pd.isna(pop) or pop == 0:
                continue
            ph = [r[11], r[13], r[15], r[17], r[19]]
            rows.append(dict(area=r[2], date=date, pop=pop, p=[0 if pd.isna(x) else x for x in ph],
                             phase=r[9], analysis=a))
    x = pd.DataFrame(rows)
    x["county_id"] = x.area.map(lookup)
    return x


def hdx_long(lookup):
    d = pd.read_csv(RAWD / "ipc_ssd_area_long.csv")
    d = d[~d.iloc[:, 0].astype(str).str.startswith("#")]
    d = d[d["Validity period"] == "current"]
    d["Number"] = pd.to_numeric(d.Number, errors="coerce")
    w = d.pivot_table(index=["Date of analysis", "From", "Area"], columns="Phase", values="Number", aggfunc="sum").reset_index()
    rows = []
    w.columns = [str(c) for c in w.columns]
    for r in w.to_dict("records"):
        rows.append(dict(area=r["Area"], date=pd.to_datetime(r["From"]).to_period("M").to_timestamp(),
                         pop=r["all"], p=[r[k] if not pd.isna(r[k]) else 0 for k in ["1", "2", "3", "4", "5"]],
                         phase=np.nan, analysis=r["Date of analysis"]))
    x = pd.DataFrame(rows)
    x = x.rename(columns=str)
    x["county_id"] = x.area.map(lookup)
    return x


def main():
    fetch()
    lookup = county_lookup()
    a = global_xlsx(lookup)
    b = hdx_long(lookup)
    # validate 20% rule where published phase exists
    chk = a.dropna(subset=["phase"]).copy()
    chk["derived"] = [phase_from_shares(np.array(p, float) / pop) for p, pop in zip(chk.p, chk["pop"])]
    print(f"20% rule reproduces published area phase in {(chk.derived == chk.phase).mean():.0%} of {len(chk)} areas")
    # prefer HDX country file for dates it covers (2022+)
    a = a[~a.date.isin(set(b.date))]
    x = pd.concat([a, b], ignore_index=True)
    un = x[x.county_id.isna()].area.unique()
    print("areas not mapped to a county (dropped):", list(un))
    x = x.dropna(subset=["county_id"])
    out = []
    for (cid, date), sub in x.groupby(["county_id", "date"]):
        P = np.sum([np.array(p, float) for p in sub.p], axis=0)
        pop = float(np.nansum(sub["pop"].astype(float)))
        if not pop > 0:
            pop = float(P.sum())
        if not pop > 0:
            continue
        p3 = float(P[2:].sum())
        if len(sub) == 1 and not pd.isna(sub.phase.iloc[0]):
            phase = int(sub.phase.iloc[0])
        else:
            pub = sub.phase.dropna()
            phase = int(pub.max()) if len(pub) == len(sub) else phase_from_shares(P / pop)
        out += [dict(county_id=cid, date=date, variable="ipc_phase3plus_pop", value=p3),
                dict(county_id=cid, date=date, variable="ipc_phase3plus_pct", value=100 * p3 / pop),
                dict(county_id=cid, date=date, variable="ipc_phase4plus_pop", value=float(P[3:].sum())),
                dict(county_id=cid, date=date, variable="ipc_phase_class", value=float(phase))]
    df = pd.DataFrame(out)
    print("AFI analyses (current period start):", sorted(df.date.dt.strftime("%Y-%m").unique()))

    # ---- AMN Jul-Sep 2025 current
    v = pd.read_excel(RAWD / "ipc_amn_projection_update.xlsx", sheet_name="Hotspot counties AFI AMN", header=None)
    hdr = [str(c) for c in v.iloc[1]]
    ci = [i for i, c in enumerate(hdr) if c.startswith("AMN Current")][0]
    gi = [i for i, c in enumerate(hdr) if c.startswith("GAM")][0]
    amn = v.iloc[2:, [1, ci, gi]].copy()
    amn.columns = ["county", "phase", "gam"]
    amn["county_id"] = amn.county.map(lookup)
    amn = amn.dropna(subset=["county_id"])
    amn["phase"] = pd.to_numeric(amn.phase, errors="coerce")
    amn["gam"] = pd.to_numeric(amn.gam, errors="coerce") * 100
    am = amn.groupby("county_id").agg(phase=("phase", "max"), gam=("gam", "max")).reset_index()
    am["date"] = pd.Timestamp("2025-07-01")
    df = pd.concat([df,
                    am[["county_id", "date"]].assign(variable="ipc_amn_phase", value=am.phase),
                    am[["county_id", "date"]].assign(variable="gam_prevalence_pct", value=am.gam)])

    url = "https://data.humdata.org/dataset/south-sudan-acute-food-insecurity-country-data"
    note = ("Current-period IPC figures placed at the first month of the analysis period "
            "(2018-01, 2018-09, 2019-01, 2019-08, 2020-01, 2020-10, 2022-02, 2022-10, 2023-09, 2024-09, 2025-09); "
            "no county analysis published for 2021 in these sources. 2018-2020 from IPC global country file.")
    c = dict(source="IPC (Integrated Food Security Phase Classification) via HDX", source_url=url,
             native_resolution="county (IPC analysis area)", temporal="irregular (per IPC analysis)",
             group="Food security", higher_is="worse", notes=note)
    meta = [
        base_meta(id="ipc_phase3plus_pop", label="People in IPC Phase 3+ (Crisis or worse)", units="persons",
                  aggregation="sum over IPC areas in county", **c),
        base_meta(id="ipc_phase3plus_pct", label="Share of population in IPC Phase 3+", units="%",
                  aggregation="phase 3+ / population analysed", **c),
        base_meta(id="ipc_phase4plus_pop", label="People in IPC Phase 4+ (Emergency or worse)", units="persons",
                  aggregation="sum over IPC areas in county", **c),
        base_meta(id="ipc_phase_class", label="IPC area phase classification (1-5)", units="phase 1-5",
                  aggregation="published area phase; 2022+ derived by IPC 20% rule", index_ok=False,
                  **c),
        base_meta(id="ipc_amn_phase", label="IPC Acute Malnutrition phase (1-5)", units="phase 1-5",
                  aggregation="county AMN classification, current Jul-Sep 2025", index_ok=False,
                  **dict(c, source_url="https://data.humdata.org/dataset/south-sudan-acute-malnutrition",
                         notes="Only one machine-readable county AMN period on HDX (Jul-Sep 2025). Earlier county AMN "
                               "maps exist only in PDFs / IPC portal (API key required).")),
        base_meta(id="gam_prevalence_pct", label="Global acute malnutrition prevalence (WHZ)", units="% children 6-59m",
                  aggregation="GAM prevalence used in IPC AMN (Jul-Sep 2025)", index_ok=False,
                  **dict(c, source_url="https://data.humdata.org/dataset/south-sudan-acute-malnutrition",
                         notes="Single snapshot (2025); WHZ-based GAM; some counties use MUAC (blank).")),
    ]
    for m in meta:
        m.setdefault("index_ok", True)
    finalize(df, SRC, meta)


if __name__ == "__main__":
    main()
