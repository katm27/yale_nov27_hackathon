"""UNHCR refugees & asylum-seekers hosted in South Sudan by county (end-year stocks, 2018-2025).

Source: HDX `unhcr-population-data-for-ssd` -> demographics_residing_ssd.csv (UNHCR Refugee Data Finder),
population types REF + ASY, by camp/settlement 'location'. Locations are mapped to counties by hand
(camp -> county), state-level / 'dispersed' rows are not allocated (reported in the log).
Annual value placed at YYYY-07-01 (temporal: annual) per the data contract.
"""
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from human_common import RAW, download, hdx_resources, finalize, base_meta

SRC = "unhcr"
RAWD = RAW / "unhcr"
CAMP_COUNTY = {
    "ajuong thok": "SS0608", "yida": "SS0608", "pamir": "SS0608",               # Pariang (Unity)
    "doro": "SS0705", "kaya": "SS0705", "gendrassa": "SS0705", "yusuf batil": "SS0705",  # Maban
    "andari": "SS1001", "ezo": "SS1001", "naandi": "SS1001",                     # Ezo
    "makpandu": "SS1010",                                                        # Yambio
    "source yubu": "SS1009", "tambura": "SS1009",                                # Tambura
    "gorom": "SS0101", "juba": "SS0101",                                         # Juba
    "lasu": "SS0106", "yei": "SS0106",                                           # Yei
    "kodok": "SS0702", "kuajok": "SS0802", "maridi": "SS1003", "morobo": "SS0104",
    "pochalla": "SS0309", "raga town": "SS0902", "boro medina": "SS0902",
    "renk": "SS0711", "renk centre": "SS0711", "turalei": "SS0806", "wunrok": "SS0806",
    "wau": "SS0903", "wedwil": "SS0505", "abyei region": "SS0001",
}


def loc_key(s):
    s = str(s).lower()
    s = re.sub(r"\(within.*?\)", "", s)
    s = re.sub(r"\[.*?\]|:.*$|,.*$", "", s)
    return s.strip()


def main():
    RAWD.mkdir(parents=True, exist_ok=True)
    for r in hdx_resources("unhcr-population-data-for-ssd"):
        if "demographics_residing" in r["url"]:
            path = download(r["url"], RAWD / "demographics_residing_ssd.csv", overwrite=True)
    d = pd.read_csv(path).iloc[1:]  # row 1 = HXL tags
    d["Year"] = d.Year.astype(int)
    d["Total"] = pd.to_numeric(d.Total, errors="coerce")
    d = d[(d.Year.between(2018, 2025)) & d["Population Type"].isin(["REF", "ASY"])]
    d["county_id"] = d.location.map(lambda s: CAMP_COUNTY.get(loc_key(s)))
    un = d[d.county_id.isna()].groupby(["location", "Year"]).Total.sum().unstack(fill_value=0)
    print("Unallocated (state-level/dispersed) REF+ASY:\n", un.to_string())
    s = d.dropna(subset=["county_id"]).groupby(["county_id", "Year"]).Total.sum().reset_index()
    s["date"] = pd.to_datetime(s.Year.astype(str) + "-07-01")
    s["variable"] = "unhcr_refugees"
    s = s.rename(columns={"Total": "value"})
    print("allocated per year:", s.groupby("Year").value.sum().to_dict())
    meta = [base_meta(id="unhcr_refugees", label="Refugees & asylum-seekers hosted (UNHCR)", units="persons",
                      group="Displacement", temporal="annual", higher_is="neutral",
                      source="UNHCR Refugee Data Finder via HDX (end-year stock, REF+ASY)",
                      source_url="https://data.humdata.org/dataset/unhcr-population-data-for-ssd",
                      native_resolution="camp/settlement location", aggregation="sum of camp/settlement stocks in county",
                      notes="End-of-year stock placed at July. Only counties hosting camps/settlements have values "
                            "(Maban, Pariang, Juba, Yei, Ezo, Yambio, Tambura, Renk ...); refugees reported only at "
                            "state level or 'dispersed' are not allocated. Renk/Wedwil/Boro Medina jump in 2023-25 = "
                            "Sudan war arrivals.")]
    finalize(s, SRC, meta)


if __name__ == "__main__":
    main()
