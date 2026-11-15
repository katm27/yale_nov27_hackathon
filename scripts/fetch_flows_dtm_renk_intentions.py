"""IOM DTM South Sudan - Renk Transit Center Intention Survey (7-11 July 2024) -> Renk -> intended county.

Household-level survey (652 sampled households of 10,735 people present at Renk TC 1/2/extension).
Each household's surveyed members are assigned from Renk (SS0711) to its intended destination county in
South Sudan. Counts are SAMPLE individuals (not scaled to the TC population, not a monthly flow):
quality = "intention_survey_sample". Households staying in Renk, going abroad, or with no answer are dropped.

Source page: https://dtm.iom.int/datasets/south-sudan-intention-survey-renk-transit-center-july-2024
(file: https://dtm.iom.int/dtm_download_track/61561?file=1&type=node&id=41946). dtm.iom.int refuses
scripted downloads, so the file was saved manually into data/raw/flows/dtm_renk_intentions/ and this
script only converts it.
Run: python3 scripts/fetch_flows_dtm_renk_intentions.py
"""
import csv
from collections import defaultdict
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/flows/dtm_renk_intentions/renk_tc_intention_survey_2024-07_node41946.xlsx"
OUT = ROOT / "data/processed/flows/dtm_renk_intentions_flows.csv"
LOOKUP = ROOT / "data/raw/ssd_unified/counties_lookup.csv"
RENK = "SS0711"


def norm(s):
    return "".join(ch for ch in str(s).lower() if ch.isalnum())


def main():
    name2pc = {}
    with open(LOOKUP, newline="") as f:
        for r in csv.DictReader(f):
            name2pc[norm(r["county"])] = r["county_pcode"]
    ws = openpyxl.load_workbook(RAW, read_only=True).worksheets[0]
    rows = ws.iter_rows(values_only=True)
    hdr = [str(h) for h in next(rows)]
    i_ind = hdr.index("Total Individuals")
    i_cty = next(i for i, h in enumerate(hdr) if h.startswith("9 a."))
    i_adm2 = next(i for i, h in enumerate(hdr) if h.startswith("9 c."))
    agg, dropped, unmatched = defaultdict(float), 0.0, defaultdict(float)
    for r in rows:
        n = float(r[i_ind] or 0)
        if r[i_cty] != "South Sudan" or not r[i_adm2] or str(r[i_adm2]).upper() == "NA":
            dropped += n
            continue
        pc = name2pc.get(norm(r[i_adm2]))
        if not pc:
            unmatched[r[i_adm2]] += n
            continue
        if pc == RENK:
            dropped += n
            continue
        agg[pc] += n
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["month", "from_pcode", "to_pcode", "reason", "individuals", "source", "quality"])
        for pc, n in sorted(agg.items(), key=lambda x: -x[1]):
            w.writerow(["2024-07", RENK, pc, "return", int(n), "IOM DTM SSD Renk TC Intention Survey Jul 2024",
                        "intention_survey_sample"])
    print(f"{len(agg)} destination counties, {sum(agg.values()):.0f} sample individuals; dropped (staying in Renk/"
          f"abroad/no answer) {dropped:.0f}; unmatched names {dict(unmatched)}")


if __name__ == "__main__":
    main()
