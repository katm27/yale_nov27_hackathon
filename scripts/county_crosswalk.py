"""County (admin-2) crosswalk helper: map any source code / name to the OCHA COD-AB v03 P-code in data/counties.geojson.

    from county_crosswalk import to_ocha, to_ocha_multi, norm
    to_ocha("SS1101")                 -> "SS0001"   (IOM DTM Abyei)
    to_ocha("SS0807", "ocha")         -> "SS0001"   (HNO 2023 / 3W 2021-22 Abyei)
    to_ocha("Pariang (Ruweng)")       -> "SS0608"
    to_ocha("Akoka", "ipc")           -> "SS0701"   (Akoka payam of Baliet)
    to_ocha("9202", "ocha_numeric")   -> "SS0101"   (pre-2015 OCHA numeric code used in HNO 2019)
    to_ocha_multi("Ruweng Administrative Area") -> ["SS0601", "SS0608"]

Lookup order: a gold P-code is returned as is; then source-specific / generic alternative codes; then normalised
names (gold names + every alias column of data/crosswalks/county_crosswalk_master.csv).
Returns None when the value is unknown, blank, foreign or denotes several counties (use to_ocha_multi).
The master CSV is rebuilt from raw files by scripts/build_county_crosswalk.py.
"""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "data/crosswalks/county_crosswalk_master.csv"
MULTI = ROOT / "data/crosswalks/county_multi_unit_aliases.csv"
NAME_COLS = ["county_name", "names_iom_dtm", "names_ocha_hno_3w_hapi", "names_acled", "names_ipc", "names_wfp_admin2",
             "names_who", "names_sssams_2015", "manual_aliases"]
# codes that are valid-looking but refer to another unit than the same code in COD-AB v03
CODE_ALIASES = {"SS1101": "SS0001",   # IOM DTM Abyei Administrative Area
                "SS0807": "SS0001",   # OCHA HNO 2023 + 3W 2021-2022 (Abyei listed under Warrap)
                "SD19001": "SS0001",  # ACLED (Abyei coded under Sudan)
                "SS11": "SS00", "SS0001": "SS0001"}


def norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"other admin ?2", " ", s)
    return re.sub(r"[^a-z0-9]", "", s)


@lru_cache(maxsize=1)
def _tables():
    gold = {f["properties"]["district_id"]: f["properties"]["name"]
            for f in json.load(open(ROOT / "data/counties.geojson"))["features"]}
    names, numeric, multi = {}, {}, {}
    with open(MASTER, newline="") as f:
        for r in csv.DictReader(f):
            pc = r["county_pcode"]
            for col in NAME_COLS:
                for a in filter(None, (x.strip() for x in r[col].split(";"))):
                    k = norm(a)
                    if k in names and names[k] != pc:
                        raise ValueError(f"ambiguous alias {a!r}: {names[k]} vs {pc}")
                    names[k] = pc
            for c in filter(None, (x.strip() for x in r["ocha_numeric_code_pre2015"].split(";"))):
                numeric[c] = pc
            for c in filter(None, (x.strip() for x in (r["iom_pcode"] + ";" + r["other_pcodes"]).split(";"))):
                if c != pc and c not in gold:
                    CODE_ALIASES.setdefault(c, pc)
    if MULTI.exists():
        with open(MULTI, newline="") as f:
            for r in csv.DictReader(f):
                multi[r["alias"]] = r["county_pcodes"].split(";")
    return gold, names, numeric, multi


def to_ocha(value, source: str | None = None) -> str | None:
    """Map a code or name from `source` (free text, used for source-specific code systems) to an OCHA P-code."""
    if value is None or (isinstance(value, float) and value != value):
        return None
    gold, names, numeric, multi = _tables()
    v = str(value).strip()
    if not v or v.lower() in ("nan", "none", "other", "unknown", "na", "n/a"):
        return None
    u = v.upper()
    if u in CODE_ALIASES:
        return CODE_ALIASES[u]
    if u in gold:
        return u
    if source and source.startswith("ocha_numeric") and v.split(".")[0] in numeric:
        return numeric[v.split(".")[0]]
    k = norm(v)
    if k in multi:
        return None
    return names.get(k)


def to_ocha_multi(value) -> list[str]:
    """All OCHA P-codes covered by a value (several for administrative areas / combined units)."""
    _, _, _, multi = _tables()
    k = norm(value)
    if k in multi:
        return multi[k]
    pc = to_ocha(value)
    return [pc] if pc else []


def gold_ids() -> list[str]:
    return sorted(_tables()[0])


if __name__ == "__main__":
    for t in ["SS1101", "SS0807", "Pariang (Ruweng)", "Akoka", "Wau (Rural Only)", "KHORFLUS", "Anzara", "Twic", "Twic East",
              "Abyei Region", "Ruweng Administrative Area", "SS0305/SS0310", "Khartoum"]:
        print(f"{t!r:30} -> {to_ocha(t)}  multi={to_ocha_multi(t)}")
