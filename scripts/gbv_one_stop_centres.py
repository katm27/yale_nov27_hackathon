"""Gender-based violence (GBV) one-stop centres and safe houses, status by month -> docs/data/points_gbv_one_stop_centres.geojson

Replaces the two-period version from the team zip ("operating (documented)" to Q1 2023, then "presumed operating").
Each centre now has a list of dated pieces of evidence, of two kinds:
  * site  - a source names THIS centre as working at that date;
  * count - a UNFPA source reports the nationwide number of centres (13) without naming them; it only applies to the
            centres in UNFPA's network (the nine UNFPA listed by name in March 2020 plus Aweil, Kuajok and Bentiu).
Months are then classified:
  * "operating (this centre named in a source)" - in a month with a site confirmation, or between two site
            confirmations at most 24 months apart;
  * "operating (not named in this period; covered by UNFPA's nationwide count of 13 or by a later mention)" - any
            other month up to the last evidence (the evidence field says which);
  * "status unconfirmed (no source since its last mention)" - after the last evidence, through Dec 2025. The app draws this as a
            hollow marker: it means no source confirms the centre, NOT that it closed.
Rules: a year-only source counts as the end of that year for a first appearance; a report covering a year counts for
every month of that year. Coordinates: host facility (WHO Master Facility List, as in the team zip); safe houses are
shown at town level because their addresses are kept confidential.

Sources checked for this version (Nov 2026; every URL opened):
  UNFPA 4 Jul 2018 (Juba FPC)            https://southsudan.unfpa.org/en/node/33965
  UNFPA 6 Mar 2020 (9 named OSCs)        https://southsudan.unfpa.org/en/node/46297
  UNICEF sitrep May 2020 (Yei, Yambio)   https://reliefweb.int/report/south-sudan/unicef-south-sudan-humanitarian-situation-report-may-2020
  PBF/UNFPA evaluation 26 Nov 2021 (Aweil, Akobo OSCs operational)
      https://mptf.undp.org/sites/default/files/documents/40000/annex_3_pbf_end_of_gbv_project_evaluation_report_2021_final.pdf
  UNFPA annual report 2022 (5,265 survivors served by OSCs; Wau shelter; Juba safe house established)
      https://southsudan.unfpa.org/sites/default/files/pub-pdf/annual_report_2022_-_unfpa_south_sudan_-_final.pdf
  UNMISS 13 Oct 2023 (new Wau OSC building handed over)
      https://www.myjoyonline.com/united-nations-mission-in-south-sudan-unmiss-hands-over-one-stop-centre-facility-to-assist-wau-survivors-of-gender-based-violence/
  South Sudan Medical Journal Nov 2023 (Juba OSC; "13 Centres in all the ten states")
      https://www.southsudanmedicaljournal.com/archive/november-2023/one-stop-centre-for-the-survivors-of-sexual-and-gender-based-violence-at-juba-teaching-hospital.html
  UNFPA annual report 2023 (13 OSCs, 5,148 survivors; safe houses Juba and Wau)
      https://southsudan.unfpa.org/sites/default/files/pub-pdf/annual_report_06_june_7.pdf
  UNFPA newsletter Q1 2024 (Wau OSC and safe shelter)
      https://southsudan.unfpa.org/sites/default/files/pub-pdf/unfpa_south_sudan_newsletter_-_quarter_1_2024.pdf
  UNFPA annual report 2024 (13 OSCs; paragraph repeats the 2023 report word for word; donor visit to Juba OSC)
      https://southsudan.unfpa.org/sites/default/files/pub-pdf/2025-04/UNFPA%20SOUTH%20SUDAN%202024%20ANNUAL%20REPORT%20%20.pdf
  UNFPA situation report #1, 15 Feb - 26 Mar 2025 (Malakal and Bentiu OSCs operating)
      https://www.unfpa.org/resources/south-sudan-situation-report-1-february-2025
  UNFPA newsletter Q1 2025 (Wau OSC visited)
      https://southsudan.unfpa.org/sites/default/files/pub-pdf/2025-04/Newsletter%20quater%201%20for%20final%20review_0.pdf
Carried over from the team compilation without re-checking (no URL recorded there): Juba opened Nov 2017; ELRP GBV
action plan (World Bank/FAO) tables for Dec 2019 and Dec 2021 (Kuajok); UNFPA 2021 annual report (Bentiu OSC and safe
house); UNFPA Q1 2023 newsletter (13 OSCs). Not usable: a 2025 UN Action note said to mention the Juba and Yambio
OSCs (link returns 404). No GBV AoR service map with dated site lists was found in machine-readable form.

Run:  python3 scripts/gbv_one_stop_centres.py   (reads only repo files; no downloads)
"""
from __future__ import annotations

import json
import os
import sys
import zipfile

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from points_temporal import ROOT, write_fc, assign_county_fc  # noqa: E402

ZIP = os.path.join(ROOT, "data", "raw", "team_dynamic_layers", "south_sudan_dynamic_layers_2018_2025_v2.zip")
END = "2025-12"

U = {
    "unfpa2018": "https://southsudan.unfpa.org/en/node/33965",
    "unfpa2020": "https://southsudan.unfpa.org/en/node/46297",
    "unicef2020": "https://reliefweb.int/report/south-sudan/unicef-south-sudan-humanitarian-situation-report-may-2020",
    "pbf2021": "https://mptf.undp.org/sites/default/files/documents/40000/annex_3_pbf_end_of_gbv_project_evaluation_report_2021_final.pdf",
    "ar2022": "https://southsudan.unfpa.org/sites/default/files/pub-pdf/annual_report_2022_-_unfpa_south_sudan_-_final.pdf",
    "unmiss2023": "https://www.myjoyonline.com/united-nations-mission-in-south-sudan-unmiss-hands-over-one-stop-centre-facility-to-assist-wau-survivors-of-gender-based-violence/",
    "ssmj2023": "https://www.southsudanmedicaljournal.com/archive/november-2023/one-stop-centre-for-the-survivors-of-sexual-and-gender-based-violence-at-juba-teaching-hospital.html",
    "ar2023": "https://southsudan.unfpa.org/sites/default/files/pub-pdf/annual_report_06_june_7.pdf",
    "q1_2024": "https://southsudan.unfpa.org/sites/default/files/pub-pdf/unfpa_south_sudan_newsletter_-_quarter_1_2024.pdf",
    "ar2024": "https://southsudan.unfpa.org/sites/default/files/pub-pdf/2025-04/UNFPA%20SOUTH%20SUDAN%202024%20ANNUAL%20REPORT%20%20.pdf",
    "sitrep2025": "https://www.unfpa.org/resources/south-sudan-situation-report-1-february-2025",
    "q1_2025": "https://southsudan.unfpa.org/sites/default/files/pub-pdf/2025-04/Newsletter%20quater%201%20for%20final%20review_0.pdf",
    "q1_2023": "https://southsudan.unfpa.org/en/publications/south-sudan-newsletter-quarter-1-0",
    "team": "https://southsudan.unfpa.org/",
}

# nationwide counts: (first month, last month covered, text, url) - apply to UNFPA-network centres only
COUNTS = [
    ("2021-12", "2021-12", "UNFPA 2021 annual report (as compiled by the team, not re-checked): Bentiu became the 13th one-stop centre in 2021", "team"),
    ("2022-01", "2022-12", "UNFPA 2022 annual report: 5,265 survivors received medical, psychosocial and legal help through the one-stop centres in 2022 (centres not listed)", "ar2022"),
    ("2023-03", "2023-03", "UNFPA newsletter Q1 2023 (as compiled by the team): 13 one-stop centres in the 10 states and 3 administrative areas", "q1_2023"),
    ("2023-01", "2023-12", "UNFPA 2023 annual report: 13 one-stop centres in hospitals served 5,148 women and girls in 2023; South Sudan Medical Journal (Nov 2023): 13 centres in all ten states", "ar2023"),
    ("2024-01", "2024-12", "UNFPA 2024 annual report: 13 one-stop centres in hospitals (the paragraph repeats the 2023 report word for word, so this is weak evidence for 2024)", "ar2024"),
]
NETWORK = {"Juba", "Rumbek", "Malualkon", "Wau", "Torit", "Bor", "Kapoeta", "Yambio", "Malakal", "Aweil", "Kuajok", "Bentiu"}
L2020 = ("UNFPA (6 Mar 2020) names it among the nine one-stop centres: Juba, Rumbek, Malualkon, Wau, Torit, Bor, Kapoeta, "
         "Yambio and Malakal", "unfpa2020")

# site: key -> (name, kind, host or None to take from the zip, coords or None, [(month, text, url_key), ...])
SITES = {
    "Juba": ("Juba one-stop centre (Family Protection Centre)", "osc", [
        ("2017-11", "Opened in November 2017 at Juba Teaching Hospital, the first one-stop centre in South Sudan (team compilation; UNFPA 4 Jul 2018 confirms it was the first)", "unfpa2018"),
        ("2018-07", "UNFPA (4 Jul 2018) describes the Family Protection Centre at Juba Teaching Hospital in operation", "unfpa2018"),
        ("2020-03",) + L2020,
        ("2023-11", "South Sudan Medical Journal (Nov 2023) describes the services of the Juba Teaching Hospital centre", "ssmj2023"),
        ("2024-12", "UNFPA 2024 annual report: joint donors' visit to the Juba one-stop centre during 2024", "ar2024")]),
    "Rumbek": ("Rumbek one-stop centre", "osc", [
        ("2019-12", "Listed as an existing centre in December 2019 (World Bank/FAO ELRP GBV action plan, as compiled by the team; UNFPA had planned it in July 2018)", "team"),
        ("2020-03",) + L2020]),
    "Malualkon": ("Malualkon one-stop centre", "osc", [
        ("2019-12", "Listed as an existing centre in December 2019 (ELRP GBV action plan, as compiled by the team)", "team"),
        ("2020-03",) + L2020]),
    "Wau": ("Wau one-stop centre", "osc", [
        ("2019-12", "Listed as an existing centre in December 2019 (ELRP GBV action plan, as compiled by the team)", "team"),
        ("2020-03",) + L2020,
        ("2023-10", "UNMISS handed a new one-stop centre building in Wau over to the state authorities (13 Oct 2023)", "unmiss2023"),
        ("2024-03", "UNFPA newsletter Q1 2024: a survivor's story at the Wau one-stop centre and safe shelter", "q1_2024"),
        ("2025-03", "UNFPA newsletter Q1 2025: donors and UNFPA visited the Wau one-stop centre (January-March 2025)", "q1_2025")]),
    "Bor": ("Bor one-stop centre", "osc", [
        ("2019-12", "Listed as an existing centre in December 2019 (ELRP GBV action plan, as compiled by the team)", "team"),
        ("2020-03",) + L2020]),
    "Malakal": ("Malakal one-stop centre", "osc", [
        ("2019-12", "Listed as an existing centre in December 2019 (ELRP GBV action plan, as compiled by the team)", "team"),
        ("2020-03",) + L2020,
        ("2025-03", "UNFPA situation report (15 Feb - 26 Mar 2025): UNFPA operates one-stop centres in Malakal and Bentiu", "sitrep2025")]),
    "Torit": ("Torit one-stop centre", "osc", [
        ("2019-12", "Listed as an existing centre in December 2019 (ELRP GBV action plan, as compiled by the team)", "team"),
        ("2020-03",) + L2020]),
    "Kapoeta": ("Kapoeta one-stop centre", "osc", [
        ("2019-12", "Opened in 2019, month not given (UNFPA Q1 2023 newsletter, as compiled by the team)", "team"),
        ("2020-03",) + L2020]),
    "Yambio": ("Yambio one-stop centre", "osc", [
        ("2019-12", "Listed as an existing centre in December 2019 (ELRP GBV action plan, as compiled by the team)", "team"),
        ("2020-03",) + L2020,
        ("2020-05", "UNICEF sitrep May 2020: social workers assigned to the one-stop centres in Yei and Yambio", "unicef2020")]),
    "Yei": ("Yei one-stop centre", "osc", [
        ("2020-05", "UNICEF sitrep May 2020: social workers assigned to the one-stop centres in Yei and Yambio primary health care centres", "unicef2020")]),
    "Aweil": ("Aweil one-stop centre", "osc", [
        ("2021-11", "UN Peacebuilding Fund project evaluation (26 Nov 2021): one-stop centres established in Aweil and Akobo during Sep 2019 - Aug 2021 and still providing medical, psychosocial and legal services", "pbf2021")]),
    "Kuajok": ("Kuajok one-stop centre", "osc", [
        ("2021-12", "Listed among current centres in December 2021 (World Bank/FAO ELRP GBV action plan, as compiled by the team; not re-checked)", "team")]),
    "Bentiu": ("Bentiu one-stop centre", "osc", [
        ("2021-12", "Established during 2021, month not given, as the 13th centre (UNFPA 2021 annual report, as compiled by the team)", "team"),
        ("2025-03", "UNFPA situation report (15 Feb - 26 Mar 2025): UNFPA operates one-stop centres in Malakal and Bentiu", "sitrep2025")]),
    "Akobo": ("Akobo one-stop centre", "osc", [
        ("2021-11", "UN Peacebuilding Fund project evaluation (26 Nov 2021): one-stop centres established in Akobo and Aweil (existing buildings renovated) and still providing medical, psychosocial and legal services", "pbf2021")]),
    "Bentiu safe house": ("Bentiu GBV safe house", "safe", [
        ("2021-12", "Newly established in 2021; 158 survivors accommodated that year (UNFPA 2021 annual report, as compiled by the team). UNFPA's 2022-2024 reports mention safe houses only in Juba and Wau", "team")]),
    "Juba safe house": ("Juba GBV safe house", "safe", [
        ("2022-12", "UNFPA 2022 annual report: a safe house was established in Juba in 2022", "ar2022"),
        ("2023-12", "UNFPA 2023 annual report: 197 survivors given safe accommodation in the safe houses in Juba and Wau in 2023", "ar2023"),
        ("2024-12", "UNFPA 2024 annual report repeats: safe houses in Juba and Wau (same wording as 2023)", "ar2024")]),
    "Wau safe house": ("Wau GBV safe shelter", "safe", [
        ("2022-12", "UNFPA 2022 annual report: 177 survivors received safety through the shelter in Wau in 2022", "ar2022"),
        ("2023-12", "UNFPA 2023 annual report: safe houses in Juba and Wau (197 survivors in 2023)", "ar2023"),
        ("2024-03", "UNFPA newsletter Q1 2024: survivor's story at the Wau safe shelter", "q1_2024"),
        ("2024-12", "UNFPA 2024 annual report repeats: safe houses in Juba and Wau", "ar2024")]),
}
ZIP_NAME = {"Juba": "Juba OSC (Family Protection Centre)", "Rumbek": "Rumbek OSC", "Malualkon": "Malualkon OSC",
            "Wau": "Wau OSC", "Bor": "Bor OSC", "Malakal": "Malakal OSC", "Torit": "Torit OSC", "Kapoeta": "Kapoeta OSC",
            "Yambio": "Yambio OSC", "Yei": "Yei OSC", "Aweil": "Aweil OSC", "Kuajok": "Kuajok OSC", "Bentiu": "Bentiu OSC",
            "Bentiu safe house": "Bentiu GBV safe house / shelter"}
EXTRA_LOC = {  # (lon, lat, host) for sites not in the team zip
    "Akobo": (33.01014, 7.79903, "Akobo Hospital (WHO Master Facility List position)"),
    "Juba safe house": None, "Wau safe house": None,   # town level: shown at the town's one-stop centre position
}

S_SITE = "operating (this centre named in a source)"
S_COUNT = "operating (not named in this period; covered by UNFPA's nationwide count of 13 or by a later mention)"
MAX_GAP = 24  # months: two mentions further apart than this do not make the months between "named"
S_UNC = "status unconfirmed (no source since its last mention)"


def months(a, b):
    return [p.strftime("%Y-%m") for p in pd.period_range(a, b, freq="M")]


def mon(m):
    return pd.Period(m, "M").strftime("%b %Y")


def classify(key, ev):
    first = ev[0][0]
    site_m = sorted(m for m, *_ in ev)
    counts = [c for c in COUNTS if key in NETWORK]
    last_ev = max(site_m + [c[1] for c in counts if c[1] >= first])
    out = []
    for m in months(max(first, "2018-01"), END):
        lo = max([s for s in site_m if s <= m], default=None)
        hi = min([s for s in site_m if s >= m], default=None)
        if m in site_m or (lo and hi and (pd.Period(hi, "M") - pd.Period(lo, "M")).n <= MAX_GAP):
            st = S_SITE
        elif m <= last_ev:
            st = S_COUNT
        else:
            st = S_UNC
        out.append((m, st))
    # run-length -> periods
    per = []
    for m, st in out:
        if per and per[-1][2] == st:
            per[-1][1] = m
        else:
            per.append([m, m, st])
    return per, last_ev


def evidence_for(key, ev, a, b, st, last_ev):
    inside = [e for e in ev if a <= e[0] <= b]
    before = [e for e in ev if e[0] < a][-1:]
    after = [e for e in ev if e[0] > b][:1]
    cnt = [c for c in COUNTS if key in NETWORK and c[1] >= a and c[0] <= b]
    parts = [f"{mon(e[0])}: {e[1]}" for e in before + inside + after]
    if st == S_COUNT:
        parts += [c[2] for c in cnt]
    if st.startswith("status unconfirmed"):
        tail = ("No later source names this centre or gives a nationwide count" if key in NETWORK
                else "No later source names this centre")
        parts = [f"Last evidence {mon(last_ev)}. {tail}; for 2025 this includes the period of the aid cuts. "
                 "Status unknown - not known to be closed."]
        if key in ("Juba", "Yambio"):
            parts.append("A 2025 UN Action project note reportedly mentions the Juba and Yambio centres, but the document "
                         "could not be opened (404), so it is not used.")
        if key in ("Yei", "Akobo"):
            parts.append("It may be one of the 13 centres UNFPA counts each year, but no source says so.")
    urls = [U[e[2]] for e in inside + after + before if e[2] != "team"] + [U[c[3]] for c in cnt if c[3] != "team"]
    return " | ".join(parts), (urls[0] if urls else U["team"])


def build():
    z = zipfile.ZipFile(ZIP)
    zf = {f["properties"]["name"]: f for f in json.loads(z.read("gbv_one_stop_centres_2018_2025.geojson"))["features"]}
    feats, summary = [], []
    for key, (name, kind, ev) in SITES.items():
        ev = sorted(ev)
        if key in ZIP_NAME:
            src = zf[ZIP_NAME[key]]
            lon, lat = src["geometry"]["coordinates"][:2]
            host = src["properties"]["host_facility"]
        elif EXTRA_LOC.get(key):
            lon, lat, host = EXTRA_LOC[key]
        else:  # safe houses: town only
            town = key.split()[0]
            src = zf[ZIP_NAME[town]]
            lon, lat = src["geometry"]["coordinates"][:2]
            host = None
        where = ("Host hospital or health centre" if kind == "osc" else
                 "Town only: shelter addresses are kept confidential for survivors' safety")
        per, last_ev = classify(key, ev)
        named = [e[0] for e in ev]
        for a, b, st in per:
            text, url = evidence_for(key, ev, a, b, st, last_ev)
            vf = None if a <= "2018-01" else a
            vt = None if b >= END else b
            props = {
                "Centre": name,
                "What it offers": ("Medical care including clinical management of rape, counselling, legal aid and police help "
                                   "in one place" if kind == "osc" else "Temporary safe accommodation for survivors"),
                "Hosted at": host,
                "Where the dot is": where,
                "First evidence it was working": mon(ev[0][0]),
                "Last time a source named it": mon(max(named)),
                "source_url": url,
                "name": name, "status": st, "valid_from": vf, "valid_to": vt, "evidence": text,
                "date_basis": ("month-by-month: named in a dated source / covered by UNFPA's nationwide count of 13 / "
                               "not confirmed after the last evidence; year-only sources = end of that year"),
            }
            feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
                          "properties": {k: v for k, v in props.items() if v is not None or k in ("valid_from", "valid_to")}})
        summary.append((name, mon(ev[0][0]), mon(max(named)), mon(last_ev), len(per)))
    feats = assign_county_fc(feats)
    write_fc("points_gbv_one_stop_centres.geojson", feats)
    return feats, summary


ORDER = [S_SITE, S_COUNT, S_UNC]
LABEL = "Gender-based violence (GBV) one-stop centres"
NOTES = ("Hospital centres where survivors of sexual and gender-based violence get medical care, counselling, legal "
         "and police help in one place, plus three safe houses, each shown from the first report that it was working; "
         "UNFPA reported 13 centres every year up to 2024 but named only a few of them after 2020 (Juba in 2023, Wau "
         "up to early 2025, Malakal and Bentiu in early 2025), so a hollow marker means no source has confirmed that "
         "centre since its last mention, not that it closed.")
DETAILS = ("Month-by-month status from dated evidence: 'named in a source' between two dated mentions of the centre "
           "(UNFPA 2018/2020 lists, UNICEF May 2020, UN Peacebuilding Fund evaluation Nov 2021, UNMISS Oct 2023, "
           "South Sudan Medical Journal Nov 2023, UNFPA newsletters Q1 2024 and Q1 2025, UNFPA situation report "
           "Feb-Mar 2025); 'UNFPA reports 13 centres' where only UNFPA's yearly nationwide count (annual reports "
           "2021-2024; the 2024 paragraph repeats 2023) covers it - this applies only to the 12 UNFPA-network centres; "
           "'status unconfirmed' after the last evidence (hollow marker). Akobo one-stop centre (UN Peacebuilding Fund, "
           "2021) and the Juba and Wau safe houses (UNFPA 2022-2024) were added; Yei is UNICEF-supported. Some first "
           "dates (Dec 2019 and Dec 2021 ELRP tables, UNFPA 2021 annual report) come from the team compilation and "
           "were not re-checked. No dated, machine-readable GBV service map exists for women and girls' friendly "
           "spaces or protection desks.")


def order_with(feats):
    vals = sorted({f["properties"]["status"] for f in feats})
    return ORDER + [v for v in vals if v not in ORDER]


def write_meta(feats):
    meta_p = os.path.join(ROOT, "data", "processed", "meta", "points.json")
    meta = json.load(open(meta_p))
    for e in meta:
        if e.get("key") == "gbv_one_stop_centres":
            e.update({"label": LABEL, "notes": NOTES, "details": DETAILS, "plain": True, "temporal": "periods",
                      "source": ("UNFPA South Sudan annual reports 2022-2024, newsletters and situation reports; UNICEF; "
                                 "UN Peacebuilding Fund evaluation; UNMISS; South Sudan Medical Journal; host facility "
                                 "coordinates from the WHO Master Facility List"),
                      "source_url": "https://southsudan.unfpa.org/",
                      "status_values": order_with(feats)})
    with open(meta_p, "w") as f:
        json.dump(meta, f, indent=1, ensure_ascii=False)
    lab_p = os.path.join(ROOT, "data", "points_labels.json")
    labels = json.load(open(lab_p))
    labels.setdefault("points_gbv_one_stop_centres", {}).update(
        {"label": LABEL, "plain": NOTES, "topic": "Gender & protection"})
    with open(lab_p, "w") as f:
        json.dump(labels, f, indent=1, ensure_ascii=False)


def main():
    feats, summary = build()
    write_meta(feats)
    print(f"{len(feats)} features")
    print(pd.DataFrame(summary, columns=["site", "first", "last named", "last evidence", "periods"]).to_string(index=False))
    for y in range(2018, 2026):
        m = f"{y}-07"
        from collections import Counter
        c = Counter(f["properties"]["status"][:28] for f in feats
                    if (f["properties"]["valid_from"] or "0000") <= m <= (f["properties"]["valid_to"] or "9999"))
        print(m, dict(c))


if __name__ == "__main__":
    main()
