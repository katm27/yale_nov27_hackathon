"""Georgetown Women, Peace and Security (WPS) Index - South Sudan, national only, editions 2017/18 .. 2025/26.
Output data/processed/wps_national.csv (contract long format, county_id = 'SS' meaning national; lead broadcasts).
NOTE: methodology changed between editions (indicator set, scaling; 2023 re-based), so scores/ranks are not
strictly comparable across editions. South Sudan had no index score in 2017/18 (missing indicators).
"""
import os
import re
import subprocess
import sys
import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from overlay_utils import ROOT, PROC, write_meta

RAW = os.path.join(ROOT, "data", "raw", "wps")
URLS = {
    2017: "https://giwps.georgetown.edu/wp-content/uploads/2019/11/WPS-Index-Data-2017.xlsx",
    2019: "https://giwps.georgetown.edu/wp-content/uploads/2017/10/WPS-Index-2019-Data-1.pdf",
    2021: "https://giwps.georgetown.edu/wp-content/uploads/2021/10/WPS-Index-2021-Data.csv",
    2023: "https://giwps.georgetown.edu/wp-content/uploads/2023/10/WPS-Index-data-final.xlsx",
    2025: "https://giwps.georgetown.edu/wp-content/uploads/2025/10/WPS-Index-2025-Data.xlsx",
}
VARS = ["wps_index", "wps_rank", "wps_education_years", "wps_employment_pct", "wps_financial_inclusion_pct",
        "wps_cellphone_pct", "wps_parliament_women_pct", "wps_ipv_pct", "wps_community_safety_pct"]
# column positions (0-based) of the South Sudan row, per edition, in the order of VARS (None = not available)
POS = {
    2017: [1, 3, 5, 9, 7, 11, 13, 23, 21],
    2021: [2, 0, 3, 7, 5, 9, 11, 19, 21],
    2023: [2, 0, 3, 5, 7, 9, 11, 21, 23],
    2025: [4, 0, 8, 10, 12, 14, 16, 26, 28],
}


def fetch():
    os.makedirs(RAW, exist_ok=True)
    out = {}
    for y, u in URLS.items():
        p = os.path.join(RAW, os.path.basename(u))
        if not os.path.exists(p):
            r = requests.get(u, timeout=300)
            r.raise_for_status()
            open(p, "wb").write(r.content)
        out[y] = p
    with open(os.path.join(RAW, "SOURCE.md"), "w") as f:
        f.write("Georgetown Institute for Women, Peace and Security - WPS Index data files\n" +
                "\n".join(f"{y}: {u}" for y, u in URLS.items()) + "\nhttps://giwps.georgetown.edu/the-index/\n")
    return out


def num(x):
    try:
        return float(str(x).replace(",", ""))
    except ValueError:
        return None


def row_of(df):
    m = df.apply(lambda r: r.astype(str).str.strip().eq("South Sudan").any(), axis=1)
    return df[m].iloc[0].tolist()


def main():
    files = fetch()
    recs = {}
    for y in (2017, 2023, 2025):
        r = row_of(pd.read_excel(files[y], header=None))
        recs[y] = [num(r[i]) for i in POS[y]]
    import csv
    with open(files[2021], encoding="latin-1") as f:  # file is ~28 MB of mostly empty rows; scan lines
        r = next(row for row in csv.reader(f) if len(row) > 1 and row[1].strip() == "South Sudan")
    recs[2021] = [num(r[i]) for i in POS[2021]]
    # 2019: PDF table row "163 South Sudan 0.479 .. 4.0 4.7 66.6 27.0 26.6 34 1.04 25 47.0 42.6 9.12"
    txt = subprocess.run(["pdftotext", "-layout", files[2019], "-"], capture_output=True, text=True).stdout
    line = [l for l in txt.splitlines() if "South Sudan" in l][0]
    t = line.split("South Sudan")
    rank = num(t[0].split()[-1])
    v = t[1].split()  # idx, gdp-rank-diff, edu, fin, emp, cell, parl, legal, srb, norms, ipv, safety, orgviol
    recs[2019] = [num(v[0]), rank, num(v[2]), num(v[4]), num(v[3]), num(v[5]), num(v[6]), num(v[10]), num(v[11])]
    rows = []
    for y, vals in sorted(recs.items()):
        for var, val in zip(VARS, vals):
            if val is not None:
                rows.append(("SS", f"{y}-07-01", var, val))
    df = pd.DataFrame(rows, columns=["county_id", "date", "variable", "value"])
    df.to_csv(os.path.join(PROC, "wps_national.csv"), index=False)
    print(df.pivot(index="variable", columns="date", values="value"))
    lab = {"wps_index": ("WPS Index score (national)", "index 0-1", "better"),
           "wps_rank": ("WPS Index rank (national)", "rank (1 = best)", "worse"),
           "wps_education_years": ("Women's mean years of schooling (national)", "years", "better"),
           "wps_employment_pct": ("Women's employment (national)", "%", "better"),
           "wps_financial_inclusion_pct": ("Women's financial inclusion (national)", "%", "better"),
           "wps_cellphone_pct": ("Women's cell phone use (national)", "%", "better"),
           "wps_parliament_women_pct": ("Women in parliament (national)", "% seats", "better"),
           "wps_ipv_pct": ("Intimate partner violence (national)", "% women", "worse"),
           "wps_community_safety_pct": ("Women feeling safe in community (national)", "%", "better")}
    write_meta("wps", [dict(id=k, label=l, category="human", group="Women, Peace & Security", units=u,
                            source="Georgetown GIWPS WPS Index editions 2017/18-2025/26",
                            source_url="https://giwps.georgetown.edu/the-index/", native_resolution="national",
                            temporal="annual", aggregation="national value (county_id SS) - broadcast to all counties",
                            higher_is=h, index_ok=False,
                            notes="NATIONAL ONLY - no subnational variation. Dated by edition year (2017, 2019, 2021, 2023, 2025); "
                                  "methodology and indicator definitions differ between editions, so not strictly comparable. "
                                  "No index score for South Sudan in 2017/18.")
                       for k, (l, u, h) in lab.items()])


if __name__ == "__main__":
    main()
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from trend_stats import write_trends
    write_trends("wps_national")  # Mann-Kendall + Sen's slope (scripts/trend_stats.py)
