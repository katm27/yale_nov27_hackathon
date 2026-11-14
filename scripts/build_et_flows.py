"""Origin -> destination displacement flows from IOM DTM South Sudan Event Tracking (ET), 2020-2025.

Every ET record gives the county where the event was assessed (destination) and where people arrived
from (origin county inside South Sudan, or a foreign country for cross-border arrivals).
Output: data/processed/flows/et_flows.csv
  month, from_pcode, to_pcode, reason, population, individuals, source, quality
from_pcode is an OCHA admin-2 P-code, or a country code (SDN, ETH, UGA, KEN, CAF, COD) for cross-border arrivals.

Usage: python scripts/build_et_flows.py
"""
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from human_common import DATA, fix_pcode, load_counties  # noqa: E402

ET_DIR = DATA / "drive_mirror" / "01_analysis_ready"
OUT = DATA / "processed" / "flows" / "et_flows.csv"
FOREIGN = {"SDN", "ETH", "UGA", "KEN", "CAF", "COD", "SD", "ET", "UG", "KE", "CF", "CD"}
ISO2 = {"SD": "SDN", "ET": "ETH", "UG": "UGA", "KE": "KEN", "CF": "CAF", "CD": "COD"}


def crosswalk():
    """IOM county codes -> OCHA COD-AB P-codes (from the team unified dataset lookup)."""
    lk = pd.read_csv(DATA / "raw" / "ssd_unified" / "counties_lookup.csv", dtype=str)
    cw = {r.iom_pcode: r.county_pcode for r in lk.itertuples() if isinstance(r.iom_pcode, str)}
    return cw


def reason_of(trigger: str) -> str:
    t = str(trigger).lower()
    if "sudan" in t:
        return "sudan_conflict"
    if re.search(r"conflict|clash|violence|attack|insecur|fight|raid|cattle", t):
        return "conflict"
    if re.search(r"flood|disaster|fire|drought|rain", t):
        return "disaster"
    if re.search(r"food|hardship|living|econom|livelihood|hunger", t):
        return "food"
    if re.search(r"return|relocat|reloc", t):
        return "return_relocation"
    return "other"


def norm_cols(d):
    d.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in d.columns]
    return d


def read_file(path: Path) -> pd.DataFrame:
    xl = pd.ExcelFile(path)
    sh = [s for s in xl.sheet_names if re.search(r"(?i)dataset|ET Jan|ET_Data|Event Tracking_", s)]
    sh = [s for s in sh if "dashboard" not in s.lower()][-1]
    d = norm_cols(pd.read_excel(path, sheet_name=sh))
    num = lambda s: pd.to_numeric(s, errors="coerce").fillna(0)
    if "ADM2_PCODE (From)" in d.columns:  # 2020 layout: one row per event, IDP/returnee columns
        date = pd.to_datetime(d["Period start"], errors="coerce").fillna(pd.to_datetime(d["Date of assessment"], errors="coerce"))
        rows = []
        for pop, col in [("IDPs", "Affected population: IDP (ind)"), ("Returnees", "Affected population: Returnee (ind)"),
                         ("Relocated", "Affected population: Relocated (ind)")]:
            rows.append(pd.DataFrame({"date": date, "to": d["ADM2_PCODE (Destination)"], "from": d["ADM2_PCODE (From)"],
                                      "from_country": d.get("ADM0_PCODE (From)", pd.Series(index=d.index, dtype=str)),
                                      "trigger": d["IDPs_Trigger"], "population": pop, "ind": num(d[col])}))
        return pd.concat(rows)
    pick = lambda pat: next((c for c in d.columns if re.search(pat, c, re.I)), None)
    origin2 = pick(r"^arrival (from|location).*admin 2 pcode") or pick(r"(from|origin).*admin ?2.*pcode")
    origin0 = pick(r"^arrival (from|location).*admin 0 pcode") or pick(r"(from|origin).*admin ?0.*pcode")
    if origin2 is None:
        raise KeyError(f"{path.name}: no origin admin-2 column; columns: {[c for c in d.columns if 'rriv' in c or 'rigin' in c]}")
    date = pd.to_datetime(d["Event Started On (From date)"], errors="coerce").fillna(
        pd.to_datetime(d.get("Assessment Date"), errors="coerce"))
    return pd.DataFrame({"date": date, "to": d["Event Location: County PCODE"], "from": d[origin2],
                         "from_country": d[origin0] if origin0 else None, "trigger": d.get("Movement Trigger", ""),
                         "population": d["Affected population category"].astype(str).str.strip(),
                         "ind": num(d["No. of Individuals"])})


def main():
    g = load_counties()
    valid = set(g.district_id)
    cw = crosswalk()
    fix = lambda p: (lambda q: cw.get(q, fix_pcode(q)) if q else None)(fix_pcode(p))
    frames = []
    files = sorted(set(ET_DIR.glob("*Event*Tracking*.xlsx")) | set(ET_DIR.glob("*EventTracking*.xlsx")))
    for f in files:
        e = read_file(f)
        fy = int(re.search(r"(20\d\d)", f.name.replace("20210208", "")).group(1))
        e = e[(e.date.dt.year == fy) & (e.ind > 0)]  # each file also repeats late events of the previous year
        e["file"] = f.name
        frames.append(e)
        print(f"{f.name[:60]:<60} {len(e):>6} rows {e.ind.sum():>11,.0f} ind")
    e = pd.concat(frames, ignore_index=True)
    e["to_pcode"] = e["to"].map(fix)
    fc = e["from_country"].astype(str).str.strip().str.upper()
    fc = fc.map(lambda x: ISO2.get(x, x))
    e["from_pcode"] = e["from"].map(fix)
    foreign = fc.isin(FOREIGN - {"SSD"}) & (fc != "SSD")
    e.loc[foreign, "from_pcode"] = fc[foreign]
    # IOM sometimes stores a foreign admin-2 code (e.g. SD02114) without the country column
    pref = e["from_pcode"].astype(str).str[:2]
    e.loc[pref.isin(ISO2) & ~e["from_pcode"].isin(valid), "from_pcode"] = pref.map(ISO2)
    e["reason"] = e.trigger.map(reason_of)
    e["month"] = e.date.dt.strftime("%Y-%m")
    ok = e.to_pcode.isin(valid) & (e.from_pcode.isin(valid) | e.from_pcode.isin(FOREIGN))
    print(f"matched {ok.mean():.1%} of rows ({e[ok].ind.sum():,.0f} of {e.ind.sum():,.0f} individuals)")
    flows = (e[ok].groupby(["month", "from_pcode", "to_pcode", "reason", "population"]).ind.sum()
             .rename("individuals").reset_index())
    flows["source"] = "IOM DTM South Sudan Event Tracking"
    flows["quality"] = "ok"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    flows.to_csv(OUT, index=False)
    inter = flows[flows.from_pcode != flows.to_pcode]
    print(f"wrote {len(flows)} rows ({len(inter)} between different places); months {flows.month.min()}..{flows.month.max()}, "
          f"{flows.month.nunique()} months")


if __name__ == "__main__":
    main()
