"""IOM DTM South Sudan Mobility Tracking (baseline assessment) -> county-to-county O-D *stock* flows.

Each Mobility Tracking round asks key informants, per payam/location, how many IDPs arrived in each
arrival period and the county of habitual residence of the MAJORITY of that cohort; and how many
internal returnees arrived per period and the county they mostly returned FROM. Attributing each cohort
entirely to its majority origin county gives an origin -> current-county matrix of the IDP (and
returnee) stock at the round date. These are stocks, not monthly flows: `month` is the round's
reference month (end of data collection).

Outputs (data/processed/flows/):
  dtm_mt_idp_od_flows.csv       month,from_pcode,to_pcode,reason,individuals,source,quality  (IDP stock O-D)
  dtm_mt_returnee_od_flows.csv  same columns (internal returnees: county of displacement -> county of return)
  dtm_mt_od_by_arrival_period.csv  detail: round, month, layer, arrival_period, from/to, individuals, self-flows kept

Raw files: data/raw/flows/dtm_mt_od/{hdx,dtm_site}/ (see SOURCE.md). HDX files (R4, R13-R16) are
re-downloaded through the CKAN API. The payam-level "Baseline Area" datasets for R5-R12 exist only on
dtm.iom.int, which refuses scripted downloads; they were saved manually (URLs in ROUNDS / SOURCE.md) and
are read from the local copies.

Run: python3 scripts/fetch_flows_dtm_mt_od.py [--no-download]
"""
import csv
import json
import re
import subprocess
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from county_crosswalk import to_ocha  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/flows/dtm_mt_od"
OUT = ROOT / "data/processed/flows"
LOOKUP = ROOT / "data/raw/ssd_unified/counties_lookup.csv"
HDX_PKG = "south-sudan-displacement-data-idps-returnees-baseline-assessment-iom-dtm"

# round -> (reference month, local file, sheet, download url or HDX resource-name round number)
ROUNDS = {
    4: ("2018-12", "hdx/mt_r04_hdx.xlsx", "MT_R4_Dataset_Baseline", "hdx:Round 4"),
    5: ("2019-03", "dtm_site/mt_r05_area_node5937.xlsx", "MT_R5_Dataset_Baseline_complete",
        "https://dtm.iom.int/dtm_download_track/7999?file=1&type=node&id=5937"),
    6: ("2019-06", "dtm_site/mt_r06_area_node7071.xlsx", "MT_R6_Baseline_Dataset",
        "https://dtm.iom.int/dtm_download_track/9003?file=1&type=node&id=7071"),
    7: ("2019-11", "dtm_site/mt_r07_area_node7810.xlsx", "MT R7 B2 Dataset",
        "https://dtm.iom.int/dtm_download_track/10680?file=1&type=node&id=7810"),
    8: ("2020-03", "dtm_site/mt_r08_area_node10035.xlsx", "MT R8 Baseline Assessment Data",
        "https://dtm.iom.int/dtm_download_track/12923?file=1&type=node&id=10035"),
    9: ("2020-09", "dtm_site/mt_r09_area_node10664.xlsx", "MT R9 Baseline Area Dataset",
        "https://dtm.iom.int/dtm_download_track/13790?file=1&type=node&id=10664"),
    10: ("2020-12", "dtm_site/mt_r10_area_node11951.xlsx", "MT R10 Baseline Area Dataset",
         "https://dtm.iom.int/dtm_download_track/15584?file=1&type=node&id=11951"),
    11: ("2021-09", "dtm_site/mt_r11_area_node13172.xlsx", "MT R11 Baseline Area Dataset",
         "https://dtm.iom.int/dtm_download_track/17292?file=1&type=node&id=13172"),
    12: ("2021-12", "dtm_site/mt_r12_area_node18711.xlsx", "MT R12 Baseline Area Dataset",
         "https://dtm.iom.int/dtm_download_track/27946?file=1&type=node&id=18711"),
    13: ("2022-08", "hdx/mt_r13_hdx.xlsx", "MT R13 Baseline_Loc_Dataset", "hdx:Round 13"),
    14: ("2023-04", "hdx/mt_r14_hdx.xlsx", "MT R14 Baseline_Loc_Dataset", "hdx:Round 14"),
    15: ("2024-09", "hdx/mt_r15_hdx.xlsx", "MT R15 Baseline_Loc_Dataset", "hdx:Round 15"),
    16: ("2025-02", "hdx/mt_r16_hdx.xlsx", "MT R16 Baseline_Loc_Dataset", "hdx:Round 16"),
}

ALIASES = {
    "luakpinynasir": "Luakpiny/Nasir", "nasir": "Luakpiny/Nasir", "luakpiny": "Luakpiny/Nasir",
    "canalpigi": "Canal/Pigi", "pigi": "Canal/Pigi", "canal": "Canal/Pigi",
    "panyijar": "Panyijiar", "raga": "Raja", "kajokeji": "Kajo-keji",
    "abyeiregion": "Abyei", "mayiendit": "Mayendit", "pariangruweng": "Pariang",
    "abyeiadministrativearea": "Abyei", "abyeiarea": "Abyei", "ruweng": "Pariang",
    "panyikang": "Panyikang", "rumbekcenter": "Rumbek Centre", "bor": "Bor South", "borsouth": "Bor South",
    "pochalla": "Pochalla", "longechuk": "Longochuk", "maiwut": "Maiwut", "mayendit": "Mayendit",
    "kapoetasouth": "Kapoeta South", "lopalafon": "Lafon", "lopa": "Lafon", "awielcentre": "Aweil Centre",
    "awielsouth": "Aweil South", "aweilcenter": "Aweil Centre", "tonjeast": "Tonj East",
    "jurriver": "Jur River", "wulu": "Wulu", "nagero": "Nagero", "akoka": "Baliet", "baliet": "Baliet",
    "yirolwest": "Yirol West", "yiroleast": "Yirol East", "magwi": "Magwi", "pibor": "Pibor",
    "greaterpibor": "Pibor", "gpaa": "Pibor", "fangak": "Fangak", "mundrieast": "Mundri East",
    "mundriwest": "Mundri West", "manyo": "Manyo", "melut": "Melut", "fashoda": "Fashoda",
}
NULLS = {"", "na", "n/a", "none", "unknown", "0", "nan", "-", "dont know", "don't know", "other", "abroad"}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def load_lookup():
    name2pc, valid, iom2ocha = {}, set(), {}
    with open(LOOKUP, newline="") as f:
        for r in csv.DictReader(f):
            valid.add(r["county_pcode"])
            name2pc[norm(r["county"])] = r["county_pcode"]
            if r["iom_pcode"] and r["iom_pcode"] != r["county_pcode"]:
                iom2ocha[r["iom_pcode"]] = r["county_pcode"]
    for k, v in ALIASES.items():
        name2pc.setdefault(k, name2pc[norm(v)])
    return name2pc, valid, iom2ocha


def download(no_download):
    if no_download:
        return
    (RAW / "hdx").mkdir(parents=True, exist_ok=True)
    try:
        url = f"https://data.humdata.org/api/3/action/package_show?id={HDX_PKG}"
        pkg = json.load(urllib.request.urlopen(url, timeout=60))["result"]
        res = {r["name"].replace("DTM South Sudan Baseline Assessment ", ""): r["url"] for r in pkg["resources"]}
    except Exception as e:  # noqa: BLE001
        print("HDX metadata failed, using local copies:", e)
        res = {}
    for rnd, (_, local, _, src) in ROUNDS.items():
        dest = RAW / local
        if not src.startswith("hdx:"):
            if not dest.exists():
                print(f"R{rnd}: missing {dest}; save it manually from {src}")
            continue
        url = res.get(src[4:])
        if not url:
            continue
        tmp = dest.with_suffix(".part")
        rc = subprocess.run(["curl", "-sfL", "-m", "180", "-o", str(tmp), url]).returncode
        if rc == 0 and tmp.exists() and tmp.read_bytes()[:2] == b"PK":
            tmp.replace(dest)
            print(f"R{rnd}: downloaded {url}")
        else:
            if tmp.exists():
                tmp.unlink()
            print(f"R{rnd}: download failed ({url}); using local copy {dest.name}" if dest.exists()
                  else f"R{rnd}: download failed and no local copy!")


def hnorm(h):
    h = re.sub(r"[\s_\-\.]+", " ", str(h)).strip().lower()
    return h


DROP = {"returnee", "internal", "ret", "period", "habitual", "residence", "displ", "previously"}


def key_of(h):
    return " ".join(w for w in h.split() if w not in DROP)


def cohort_of(h):
    m = re.search(r"arrival (.*?)(?: county| ind| individuals| household| hh|$)", h)
    c = m.group(1) if m else h
    c = " ".join(w for w in c.split() if w not in DROP)
    return c.replace(" ", "_")


def to_num(v):
    try:
        x = float(v)
        return x if x == x else 0.0
    except (TypeError, ValueError):
        return 0.0


def column_pairs(hdr):
    """Return list of (layer, cohort, ind_idx, county_idx)."""
    H = [hnorm(h) for h in hdr]
    pairs = []
    # R4 layout
    for i, h in enumerate(H):
        m = re.match(r"residence before displacement \(county\) for majority of arrivals (.*)", h)
        if m and "(ind)" in H[i - 2]:
            pairs.append(("idp", m.group(1).replace(" ", "_").replace("/", "-"), i - 2, i))
        m = re.match(r"among (.*) arrival, majority returned from \(county\)", h)
        if m and "(ind)" in H[i - 4] and "(country)" in H[i - 3]:
            pairs.append(("returnee", m.group(1).replace(" ", "_"), i - 4, i, i - 3))
    if pairs:
        return pairs
    county_cols, ind_cols = {}, {}
    for i, h in enumerate(H):
        if not re.match(r"^(b|d|j|h2) ", h):
            continue
        if "arrival" not in h or "reason" in h:
            continue
        k = key_of(h)
        if k.endswith(" county"):
            county_cols[k[: -len(" county")].strip()] = i
        elif k.endswith(" ind") or k.endswith(" individuals"):
            ind_cols[re.sub(r" (ind|individuals)$", "", k).strip()] = i
    for k, ci in county_cols.items():
        if k in ind_cols:
            layer = "returnee" if re.match(r"^(j|h2) ", k) else "idp"
            grp = "prev_abroad" if (k.startswith("d ") and "abroad" in k) else ""
            pairs.append((layer if not grp else "idp_prev_abroad", cohort_of(H[ci]), ind_cols[k], ci))
        else:
            print("   unpaired county column:", H[ci])
    return pairs


def main():
    no_dl = "--no-download" in sys.argv
    download(no_dl)
    name2pc, valid, iom2ocha = load_lookup()
    detail = []
    unmatched = defaultdict(float)
    stats = {}
    for rnd, (month, local, sheet, _) in ROUNDS.items():
        wb = openpyxl.load_workbook(RAW / local, read_only=True, data_only=True)
        ws = wb[sheet]
        rows = ws.iter_rows(values_only=True)
        hdr = next(rows)
        H = [hnorm(h) for h in hdr]
        pc_idx = next(i for i, h in enumerate(H) if re.fullmatch(r"(0 )?county ?(int )?p ?code", h))
        pairs = column_pairs(hdr)
        n_in = n_ok = 0.0
        for r in rows:
            to = str(r[pc_idx] or "").strip()
            if not re.fullmatch(r"SS\d{4}", to):
                continue
            to = to_ocha(to) or to
            if to not in valid:
                unmatched[f"R{rnd} dest code {to}"] += 1
                continue
            for p in pairs:
                layer, cohort, ii, ci = p[:4]
                ind = to_num(r[ii])
                if ind <= 0:
                    continue
                n_in += ind
                if len(p) == 5 and norm(r[p[4]]) != "southsudan":
                    continue  # R4 returnees from abroad
                oname = str(r[ci] or "").strip()
                if oname.lower() in NULLS:
                    unmatched[f"{layer}: origin blank/unknown"] += ind
                    continue
                frm = to_ocha(oname, "iom_dtm")  # master crosswalk (scripts/county_crosswalk.py)
                if not frm:
                    unmatched[f"{layer}: origin name '{oname}'"] += ind
                    continue
                n_ok += ind
                detail.append((rnd, month, layer, cohort, frm, to, ind))
        stats[rnd] = (len(pairs), n_in, n_ok)
        print(f"R{rnd} {month}: {len(pairs)} cohort columns, individuals in cohorts {n_in:,.0f}, "
              f"with matched origin county {n_ok:,.0f}")

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "dtm_mt_od_by_arrival_period.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["round", "month", "layer", "arrival_period", "from_pcode", "to_pcode", "individuals", "self_flow"])
        agg = defaultdict(float)
        for rnd, month, layer, cohort, frm, to, ind in detail:
            agg[(rnd, month, layer, cohort, frm, to)] += ind
        for (rnd, month, layer, cohort, frm, to), ind in sorted(agg.items()):
            w.writerow([rnd, month, layer, cohort, frm, to, int(round(ind)), int(frm == to)])

    for layer_set, fname, reason, quality in [
        ({"idp"}, "dtm_mt_idp_od_flows.csv", "unknown", "mt_stock_majority_origin"),
        ({"returnee"}, "dtm_mt_returnee_od_flows.csv", "return", "mt_stock_majority_origin"),
    ]:
        agg = defaultdict(float)
        self_drop = 0.0
        for rnd, month, layer, cohort, frm, to, ind in detail:
            if layer not in layer_set:
                continue
            if frm == to:
                self_drop += ind
                continue
            agg[(month, frm, to)] += ind
        with open(OUT / fname, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["month", "from_pcode", "to_pcode", "reason", "individuals", "source", "quality"])
            for (month, frm, to), ind in sorted(agg.items()):
                w.writerow([month, frm, to, reason, int(round(ind)), "IOM DTM SSD Mobility Tracking", quality])
        print(f"{fname}: {len(agg)} rows, {sum(agg.values()):,.0f} individuals; "
              f"within-county (self) dropped {self_drop:,.0f}")

    print("\nUnmatched / dropped (individuals; dest-code rows):")
    for k, v in sorted(unmatched.items(), key=lambda x: -x[1])[:40]:
        print(f"  {v:>12,.0f}  {k}")


if __name__ == "__main__":
    main()
