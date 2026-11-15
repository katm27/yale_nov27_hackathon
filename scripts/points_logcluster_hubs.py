"""Logistics Cluster South Sudan hubs / common storage over time -> docs/data/points_logcluster_hubs.geojson

Source: every dated "South Sudan - Concept of Operations Map" (WFP Logistics Cluster GIS unit) published at
https://logcluster.org/en/where-we-work/ssd/documents (document types "Maps - General" 833, "Maps - CONOPS" 1393,
"Concept of Operations" 824). The listing was paged through the site's Drupal views AJAX endpoint (plain query-string
filters are stripped by a redirect); PDFs are in data/raw/logcluster/ with manifest.json (page + file URL + date).

Extraction (per map): hub labels are Arial-Bold text, storage as "= N m2" text next to a storage marker whose colour
gives the manager (red = Logistics-Cluster-managed common storage, olive = common storage managed by partners [MSUs];
temperature-controlled storage has its own glyph); service icons (coordination, river/road/air transport, IM, GIS) are
glyphs of the 'logistics-cluster-icons' font. Two maps (Sep 2019, Aug 2020) are pure graphics and the Jan 2018 map has
graphic icons: these were read visually from page renders (values below in MANUAL_MAPS).

Time: each map is a snapshot at its 'Date Created'. A site/attribute combination is valid from the first map that
shows it until the month before the next map that no longer shows it (or shows other capacity/manager), so one feature
per period. No CONOPS map was published between Sep 2023 and Feb 2026: sites are carried through that gap (flagged in
date_basis); the CONOPS text documents of Nov 2023 and Oct 2024 confirm the five cluster hubs (Bentiu, Bor, Juba,
Malakal, Wau) and "29 partner-managed MSU locations"; the Nov 2025 CONOPS no longer lists Wau (end date set 2025-10,
uncertain). Operation-overview maps of 2023 show delivery destinations, not storage, and are not used.
Coordinates: OCHA COD settlements gazetteer (town point) or read off the map pin (coord_quality='approximate').
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from points_temporal import (ROOT, geocode, point, write_fc, set_validity, ym_add, clip_window, update_points_meta,
                             assign_county_fc)

RAW = os.path.join(ROOT, "data", "raw", "logcluster")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
LISTING = "https://logcluster.org/en/where-we-work/ssd/documents"

# map file -> map date (Date Created printed on the map)
MAPS = {
    "ssdlcopconopsa3l_20180101.pdf": "2018-01",
    "ssdlcopconopsa3l20190111-1_0.pdf": "2019-01",
    "ssdlcopconopsa3l_20190607.pdf": "2019-06",
    "ssdlcopconopsa3l_20190906.pdf": "2019-09",
    "ssdlcopconopsa3l_20200323.pdf": "2020-03",
    "ssdlcopnewconopsa3l_20200414.pdf": "2020-04",
    "logisticsclustersouthsudanconopsmap_2008.pdf": "2020-08",
    "ssdlcop-new-conopsa3l_20210512.pdf": "2021-05",
    "ssdlcop-new-conopsa3l_20211003.pdf": "2021-10",
    "ssdlcop-new-conopsa3l_20220922.pdf": "2022-09",
    "ssdlcop-new-conopsa3l_20230119.pdf": "2023-01",
    "ssdlcop-new-conopsa3l20230404aprilza.pdf": "2023-04",
    "ssdlcop-new-conopsa3l_20230906.pdf": "2023-09",
    "ssdlcop-new-conopsa3l_20260223.pdf": "2026-02",
    "ssdlcop-new-conopsa3l_20260323.pdf": "2026-03",
    "ssdlcop-new-conopsa3l_04062026.pdf": "2026-06",
}
OLD_STYLE = {"2018-01", "2019-01", "2019-06", "2019-09", "2020-03"}  # every site = Logistics Cluster hub (red square)

C, R, N, A, I, G, T, P = ("coordination", "river transport", "road transport", "air transport",
                          "information management", "GIS", "training", "preparedness")
# Visually read maps: name -> (storage m2, managed: 'LC'/'partner', services, temperature-controlled m2)
MANUAL_MAPS = {
    "2018-01": {"Bentiu": (1440, "LC", [C, N, A]), "Malakal": (1920, "LC", [C, R, N, A]), "Melut": (640, "LC", [N, A]),
                "Aweil": (240, "LC", [A]), "Wau": (230, "LC", [C, N, A]), "Koch": (320, "LC", []),
                "Nyal": (240, "LC", [A]), "Akobo": (320, "LC", [A]), "Rumbek": (960, "LC", [C, N, A]),
                "Mingkaman": (240, "LC", [A]), "Bor": (2000, "LC", [C, R, N, A]), "Pibor": (320, "LC", [A]),
                "Juba": (640, "LC", [C, I, G, N, A]), "Kapoeta": (320, "LC", []), "Torit": (640, "LC", [])},
    "2019-09": {"Koch": (320, "LC", []), "Yida": (240, "LC", []), "Ganyiel": (240, "LC", []), "Agok": (240, "LC", []),
                "Bentiu": (1440, "LC", [C, N]), "Malakal": (1920, "LC", [C, R, N]), "Malualkon": (240, "LC", []),
                "New Fangak": (320, "LC", []), "Twic": (240, "LC", []), "Wau": (230, "LC", [C, N, A]),
                "Akobo": (320, "LC", []), "Rumbek": (960, "LC", [C, N, A]), "Bor": (2000, "LC", [C, R, N, A]),
                "Pibor": (320, "LC", []), "Maridi": (320, "LC", []), "Yambio": (104, "LC", []),
                "Juba": (875, "LC", [C, I, G, N, A]), "Kapoeta": (320, "LC", []), "Torit": (640, "LC", []),
                "Yei": (640, "LC", [C]), "Nimule": (320, "LC", [])},
    "2020-08": {"Yida": (640, "partner", []), "Ganyiel": (320, "partner", []), "Bentiu": (1440, "LC", [C, N]),
                "Koch": (320, "partner", []), "Maban": (320, "partner", []), "Malakal": (1920, "LC", [C, R, N]),
                "New Fangak": (320, "partner", []), "Twic": (240, "partner", []), "Motot": (320, "partner", []),
                "Wau": (230, "LC", [C, N]), "Raja": (240, "partner", []), "Gumuruk": (320, "partner", []),
                "Bor": (2000, "LC", [C, N, R, A]), "Rumbek": (960, "LC", [C, N, A]), "Pibor": (640, "partner", []),
                "Mabior": (240, "partner", []), "Juba": (2240, "LC", [C, I, G, N, A, T, P], 870),
                "Maridi": (320, "partner", []), "Yambio": (104, "partner", []), "Kapoeta": (320, "partner", []),
                "Torit": (640, "partner", []), "Yei": (560, "partner", [C]), "Nimule": (320, "partner", [])},
}
NAME_FIX = {"Tonj": "Tonj Town", "Bentiu:": "Bentiu", "Malakal:": "Malakal", "Juba:": "Juba"}
GAP = ("2023-09", "2026-02")  # no map published in between
WAU_END = "2025-10"
STATES = {"Lakes", "Central", "Equatoria", "Eastern", "Upper Nile", "Western", "Bahr el", "Ghazal", "Unity", "Northern",
          "Jonglei", "Warrap", "Region", "Abyei", "Upper", "Nile", "(South)", "(North)"}
ICON = {"m": "storage", "c": C, "n": N, "j": R, "a": A, "g": I, "e": G}


# ------------------------------------------------------------------------------------------ listing & download
def list_documents():
    """Page the country document listing through Drupal views AJAX; returns [{href,title,date,type}]."""
    import requests
    out = []
    for typ in ["833", "1393", "824"]:
        for p in range(0, 80):
            u = (f"https://logcluster.org/en/views/ajax?_wrapper_format=drupal_ajax&view_name=document"
                 f"&view_display_id=country&view_args=210&view_path=%2Fwhere-we-work%2Fssd%2Fdocuments"
                 f"&view_base_path=documents&pager_element=0&page={p}&field_document_type_target_id={typ}"
                 f"&activity_type_target_id=All&field_date_value=")
            d = requests.get(u, headers=UA, timeout=60).json()
            t = "".join(c.get("data", "") for c in d if c.get("command") == "insert" and isinstance(c.get("data"), str))
            arts = re.findall(r'<article class="teaser-document">(.*?)</article>', t, re.S)
            new = 0
            for a in arts:
                href = re.search(r'href="([^"]+)"', a).group(1)
                if any(o["href"] == href for o in out):
                    continue
                new += 1
                ti = re.search(r'teaser-document__title">\s*(.*?)\s*</h3>', a, re.S).group(1)
                dd = re.search(r'datetime="([^"]+)"', a)
                out.append(dict(href=href, title=ti, date=dd.group(1)[:10] if dd else None, type=typ))
            if not arts or not new:
                break
            time.sleep(0.3)
    return out


def download():
    """(Re)download CONOPS maps/documents 2018-2026 listed on logcluster.org into data/raw/logcluster."""
    import requests
    os.makedirs(RAW, exist_ok=True)
    docs = list_documents()
    with open(os.path.join(RAW, "listing_maps_conops.json"), "w") as f:
        json.dump(docs, f, indent=0)
    sel = [x for x in docs if re.search(r"concept of operations|warehouse locations", x["title"], re.I)
           and "DRC" not in x["title"] and x["date"] and x["date"] >= "2017-12"]
    man = []
    for x in sel:
        r = requests.get("https://logcluster.org" + x["href"], headers=UA, timeout=60)
        for fpath in sorted(set(re.findall(r'href="(/sites/default/files/[^"]+\.pdf)"', r.text, re.I))):
            fn = os.path.basename(fpath)
            p = os.path.join(RAW, fn)
            if not os.path.exists(p):
                open(p, "wb").write(requests.get("https://logcluster.org" + fpath, headers=UA, timeout=180).content)
            man.append(dict(date=x["date"], title=x["title"], page="https://logcluster.org" + x["href"],
                            url="https://logcluster.org" + fpath, file=fn, bytes=os.path.getsize(p)))
    with open(os.path.join(RAW, "manifest.json"), "w") as f:
        json.dump(man, f, indent=1)


# ------------------------------------------------------------------------------------------ PDF text extraction
def _ctr(b):
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


def _dist(a, b):
    a, b = _ctr(a["b"]), _ctr(b["b"])
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** .5


def _colour(c):
    r, g, b = (c >> 16) & 255, (c >> 8) & 255, c & 255
    if r > 150 and g < 100:
        return "LC"
    if r > 80 and g > 80 and b < 60:
        return "partner"
    return None


def extract_map(path):
    import pymupdf
    page = pymupdf.open(path)[0]
    spans = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                t = s["text"].strip()
                if t:
                    spans.append(dict(t=t, f=s["font"], sz=round(s["size"], 1), b=s["bbox"], col=s["color"]))
    caps = [s for s in spans if re.match(r"^=\s*[\d,\. ]+\s*m", s["t"])]
    names0 = [s for s in spans if s["f"].startswith("Arial-Bold") and s["sz"] >= 9 and len(s["t"]) > 2
              and not re.search(r"(^|\s)\w(\s|$)", s["t"])
              and s["t"] not in STATES and not re.search(r"Equatoria|Ghazal|Bahr", s["t"])]
    markers = [m for m in spans if m["f"].startswith("ESRIDefaultMarker") and m["sz"] > 15 and m["t"] in "!¬Æ"]

    def pair(names):
        out = {}
        for c in caps:
            best = min(names, key=lambda n: _dist(n, c))
            v = int(re.sub(r"[^\d]", "", c["t"]))
            cc = _ctr(c["b"])
            mk = [m for m in markers if abs(_ctr(m["b"])[1] - cc[1]) < 15 and 0 < cc[0] - _ctr(m["b"])[0] < 45]
            temp = bool(mk) and mk[0]["t"] == "Æ"
            out.setdefault(id(best), [best, []])[1].append((v, _colour(mk[0]["col"]) if mk else None, temp))
        return out

    pr = pair(names0)
    from collections import Counter
    sizes = Counter(n["sz"] for n, _ in pr.values())
    hub_sizes = [s for s, k in sizes.items() if k >= 3]
    names = [n for n in names0 if any(abs(n["sz"] - s) <= 1.0 for s in hub_sizes)]
    pr = pair(names)
    icons = [s for s in spans if s["f"].startswith("logistics-cluster-icons") and s["sz"] < 20]
    res = {}
    for n in names:
        caps_n = pr.get(id(n), [n, []])[1]
        nm = NAME_FIX.get(n["t"], n["t"].rstrip(":"))
        svc = sorted({ICON.get(i["t"], i["t"]) for i in icons if _dist(i, n) < 70} - {"storage"})
        mgr = {c[1] for c in caps_n if c[1]}
        res[nm] = dict(storage_m2=sum(c[0] for c in caps_n) or None,
                       temp_m2=sum(c[0] for c in caps_n if c[2]) or None,
                       managed=("LC" if "LC" in mgr else "partner" if mgr else None), services=svc)
    return res


def snapshots():
    snaps = {}
    for fn, d in MAPS.items():
        if d in MANUAL_MAPS:
            snaps[d] = {k: dict(storage_m2=v[0], managed=v[1], services=sorted(v[2]),
                                temp_m2=(v[3] if len(v) > 3 else None)) for k, v in MANUAL_MAPS[d].items()}
        else:
            snaps[d] = extract_map(os.path.join(RAW, fn))
        for k, v in snaps[d].items():
            if d in OLD_STYLE:
                v["managed"] = "LC"
            v["managed"] = v["managed"] or "LC"
    return snaps


def main():
    if not all(os.path.exists(os.path.join(RAW, f)) for f in MAPS):
        download()
    man = {m["file"]: m for m in json.load(open(os.path.join(RAW, "manifest.json")))}
    url_by_date = {d: man[f]["url"] for f, d in MAPS.items() if f in man}
    page_by_date = {d: man[f]["page"] for f, d in MAPS.items() if f in man}
    snaps = snapshots()
    dates = sorted(snaps)
    names = sorted({n for s in snaps.values() for n in s})
    feats = []
    for name in names:
        g = geocode(name)
        if g is None:
            print("NO COORDS", name)
            continue
        lon, lat, csrc, cq = g
        cur = None
        periods = []
        for i, d in enumerate(dates):
            s = snaps[d].get(name)
            key = (s["storage_m2"], s["managed"]) if s else None
            if cur and key == cur["key"]:
                cur["last"] = d
                continue
            if cur:
                cur["to"] = ym_add(d, -1)
                periods.append(cur)
                cur = None
            if s:
                cur = dict(key=key, frm=d, last=d, to=None, s=s)
        if cur:
            periods.append(cur)
        for p in periods:
            s, frm, to = p["s"], p["frm"], p["to"]
            basis = [f"Logistics Cluster CONOPS map {frm}" + (f" .. {p['last']}" if p["last"] != frm else "")]
            if frm == dates[0]:
                frm_v = None
                basis.append("already on the first map in the window (Jan 2018)")
            else:
                frm_v = frm
            if p["last"] == GAP[0]:
                basis.append("carried Oct 2023-Jan 2026: no CONOPS map published (CONOPS texts Nov 2023/Oct 2024: "
                             "cluster hubs Bentiu, Bor, Juba, Malakal, Wau + 29 partner MSU locations)")
            if name == "Wau" and p["last"] == GAP[0]:
                to = WAU_END
                basis.append("Wau not listed as cluster storage in CONOPS Nov 2025: end date uncertain (2024-10..2025-11)")
            cw = clip_window(frm_v, to)
            if cw is None:
                continue
            vf, vt = cw
            svc = s["services"]
            typ = ("Logistics Cluster hub" if C in svc or (s["managed"] == "LC" and (s["storage_m2"] or 0) >= 800)
                   else "common storage (Logistics Cluster)" if s["managed"] == "LC"
                   else "common storage managed by partners (MSU)")
            props = dict(name=name, type=typ)
            set_validity(props, vf, vt, "; ".join(basis))
            props.update(storage_m2=s["storage_m2"], temp_controlled_m2=s.get("temp_m2"),
                         managed_by="Logistics Cluster" if s["managed"] == "LC" else "partner organisation",
                         services=", ".join(svc) if svc else None,
                         map_date=p["frm"], last_map_date=p["last"],
                         source_url=url_by_date.get(p["frm"]), source_page=page_by_date.get(p["frm"]),
                         coord_source=csrc, coord_quality=cq,
                         source="WFP Logistics Cluster South Sudan Concept of Operations maps (logcluster.org)")
            feats.append(point(lon, lat, props))
    assign_county_fc(feats)
    write_fc("points_logcluster_hubs.geojson", feats)
    n_sites = len({f["properties"]["name"] for f in feats})
    print(f"{len(feats)} features, {n_sites} sites, {len(dates)} map dates: {dates}")
    update_points_meta({
        "key": "logcluster_hubs", "label": "Logistics Cluster hubs & common storage (over time)", "category": "human",
        "source": "WFP Logistics Cluster, South Sudan Concept of Operations maps Jan 2018 - Jun 2026 (16 dated maps)",
        "source_url": LISTING,
        "notes": ("Temporal: one feature per site and period with constant storage capacity/manager; valid_from/valid_to "
                  "from consecutive map dates (2018-01, 2019-01/06/09, 2020-03/04/08, 2021-05/10, 2022-09, 2023-01/04/09, "
                  "2026-02/03/06). No map Oct 2023-Jan 2026: sites carried through (date_basis says so). "
                  "type = Logistics Cluster hub (coordination/transport services) / cluster common storage / "
                  "partner-managed MSU; storage_m2 as printed. Coordinates = town (OCHA gazetteer) or map pin "
                  "(coord_quality='approximate'), not the warehouse itself.")})


if __name__ == "__main__":
    main()
