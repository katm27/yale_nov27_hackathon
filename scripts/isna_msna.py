"""Household-survey WASH and protection/GBV-risk indicators per county from the South Sudan Inter-Sector Needs
Assessment (ISNA = South Sudan's MSNA, run by REACH/IMPACT for OCHA and the ICCG), rounds 2022, 2023, 2024.

Source: HDX datasets `south-sudan-inter-sector-needs-assessment-isna-data` (county analysis tables) and
`south-sudan-inter-sectoral-needs-assessment`, files in data/raw/isna/:
  2022  isna_hno_analysis_output_county_final_twg_21oct22.xlsx   (data collection Jul-Aug 2022)
  2023  isna_hno_analysis_2023_final_dataset_hdx.xlsx            (Jul-Aug 2023)
  2024  isna_analysis_dataset_08_10_2024-final-clean-dataset-hdx.xlsx, sheet "Analysis - County" (Jul-Sep 2024)
Values are % of households (county-representative, all population groups). Date = YYYY-07-01, temporal annual.
No REACH MSNA/ISNA county tables exist on HDX for 2018-2021 (pre-2022 REACH SSD used the "Area of Knowledge"
key-informant method, settlement-level, not public as county tables) -> series start 2022.

Variables (output data/processed/isna_county_monthly.csv):
  isna_water_30min_plus_pct      water collection round trip >= 30 min
  isna_unsafe_water_collect_pct  a household member felt unsafe while collecting water
  isna_surface_water_source_pct  main drinking source = river/stream/swamp/unprotected or shallow well
  isna_open_defecation_pct       household practises open defecation (no facility)
  isna_wg_avoid_water_points_pct women & girls avoid water points because they feel unsafe (GBV-risk proxy)
  isna_wg_avoid_latrines_pct     women & girls avoid latrines/bathing facilities because unsafe
  isna_wg_avoid_any_pct          women & girls avoid at least one area (100 - "no areas avoided")
"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from human_common import RAW, load_counties, finalize, base_meta, norm_name

SRC = "isna"
D = RAW / "isna"
ALIASES = {"khorflus": "Canal/Pigi", "lafonlopa": "Lafon", "raga": "Raja"}  # ISNA name -> boundary-file name


def county_lookup():
    g = load_counties()
    lk = {norm_name(n): c for n, c in zip(g.name, g.district_id)}
    for n, c in zip(g.name, g.district_id):
        lk.setdefault(norm_name(n.split("/")[0]), c)
    lk.update({k: lk[norm_name(v)] for k, v in ALIASES.items()})
    return lk


def pct(v):
    if isinstance(v, str):
        v = v.strip()
        if v.endswith("%"):
            return float(v[:-1])
        try:
            v = float(v)
        except ValueError:
            return np.nan
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return np.nan
    return float(v) * 100 if float(v) <= 1.0 else float(v)


def wide(f, sheet):
    h = pd.read_excel(D / f, sheet_name=sheet, header=None)
    q = h.iloc[0].ffill().fillna("").astype(str).str.split("\n").str[0].str.strip().str.lower()
    ch = h.iloc[1].fillna("").astype(str).str.strip().str.lower()
    body = h.iloc[2:].copy()
    county = body.iloc[:, 0].fillna("").astype(str)
    return q, ch, body, county


def pick(q, ch, qpat, cpat):
    idx = [i for i in range(len(q)) if re.search(qpat, q[i]) and re.search(cpat, ch[i])]
    return idx


def year_2022_2023(f, year):
    out = {}
    q, ch, body, county = wide(f, "WASH")
    qd = r"walking distance|how long does it take"
    specs = {
        "isna_water_30min_plus_pct": (qd, r"30 minutes to|one \(1\) hour|half a day"),
        "isna_unsafe_water_collect_pct": (r"safety while collecting|felt unsafe while collecting", r"^1\.\s+yes"),
        "isna_surface_water_source_pct": (r"main source of drinking water", r"shallow well|river|swamp|unprotected"),
        "isna_open_defecation_pct": (r"sanitation facility", r"open defecation"),
    }
    for var, (qp, cp) in specs.items():
        cols = pick(q, ch, qp, cp)
        assert cols, (year, var)
        out[var] = (county, body.iloc[:, cols].map(pct).sum(axis=1, min_count=1))
    q, ch, body, county = wide(f, "Protection")
    qa = r"women.?/?.?(and )?girls.*avoid|areas women and girls avoid"
    for var, cp in {"isna_wg_avoid_water_points_pct": r"water points",
                    "isna_wg_avoid_latrines_pct": r"latrines and bathing",
                    "isna_wg_avoid_any_pct": r"there are no areas"}.items():
        cols = pick(q, ch, qa, cp)
        assert cols, (year, var)
        v = body.iloc[:, cols[:1]].map(pct).sum(axis=1, min_count=1)
        out[var] = (county, 100 - v if var == "isna_wg_avoid_any_pct" else v)
    return out


def year_2024():
    c = pd.read_excel(D / "isna_analysis_dataset_08_10_2024-final-clean-dataset-hdx.xlsx", sheet_name="Analysis - County")
    c["v"] = c.Stats.map(pct)
    c["ch"] = c.Choices.fillna("").astype(str).str.strip().str.lower()
    out = {}

    def s(var, cond, transform=None):
        x = c[cond].groupby("County").v.sum(min_count=1)
        out[var] = (pd.Series(x.index), pd.Series(transform(x.values) if transform else x.values))

    V = c.Variable
    s("isna_water_30min_plus_pct", (V == "E02_Duration_Collect_Water") & c.ch.str.contains("30 minutes to|one \\(1\\) hour|half a day"))
    s("isna_unsafe_water_collect_pct", (V == "E04_Mem_Felt_Unsafe") & (c.ch == "yes"))
    s("isna_surface_water_source_pct", (V == "E01_Drinking_Water_Source") & c.ch.str.contains("river|swamp|unprotected"))
    s("isna_open_defecation_pct", (V == "E05_sanitation_facility") & c.ch.str.contains("open defecation"))
    s("isna_wg_avoid_water_points_pct", V == "women_girls_avoid_they_feel_unsafe/Water_points")
    s("isna_wg_avoid_latrines_pct", V == "women_girls_avoid_they_feel_unsafe/latrines_and_bathing_facilities")
    s("isna_wg_avoid_any_pct", V == "women_girls_avoid_they_feel_unsafe/no_areas_women_and_girls_avoid", lambda a: 100 - a)
    return out


def main():
    lk = county_lookup()
    rows, unmatched = [], set()
    rounds = {2022: year_2022_2023("isna_hno_analysis_output_county_final_twg_21oct22.xlsx", 2022),
              2023: year_2022_2023("isna_hno_analysis_2023_final_dataset_hdx.xlsx", 2023),
              2024: year_2024()}
    for year, d in rounds.items():
        for var, (county, vals) in d.items():
            for cn, v in zip(county.values, vals.values):
                k = norm_name(cn)
                cid = lk.get(k)
                if cid is None:
                    if k not in ("nan", "", "county", "total", "southsudan"):
                        unmatched.add((year, cn))
                    continue
                if np.isfinite(v):
                    rows.append((cid, f"{year}-07-01", var, round(min(max(v, 0), 100), 2)))
    print("unmatched county names:", sorted(unmatched))
    df = pd.DataFrame(rows, columns=["county_id", "date", "variable", "value"]).drop_duplicates(["county_id", "date", "variable"])
    print(df.groupby(["variable", "date"]).value.agg(["count", "mean"]).round(1).to_string())
    src = "South Sudan Inter-Sector Needs Assessment (ISNA, the country's MSNA; REACH/IMPACT for OCHA & ICCG) 2022-2024, county tables on HDX"
    url = "https://data.humdata.org/dataset/south-sudan-inter-sector-needs-assessment-isna-data"
    common = dict(category="human", temporal="annual", source=src, source_url=url, native_resolution="county (household survey)",
                  units="% of households", aggregation="weighted % of surveyed households in county (all population groups)",
                  index_ok=True, higher_is="worse")
    gnote = ("Household survey, Jul-Sep each year (shown at YYYY-07). Rounds 2022-2024 only: no county-level MSNA "
             "tables exist on HDX for 2018-2021, so the baseline is 2022. Questions were reworded between rounds "
             "(e.g. 2022 groups shallow wells with rivers/ponds), so small year-to-year changes are not meaningful; "
             "county samples are ~100-300 households (margin of error ~5-10 points).")
    meta = [
        base_meta(id="isna_water_30min_plus_pct", label="Households >=30 min from drinking water", group="Water access",
                  notes="Round trip to the main drinking-water source takes 30 min or more (Sphere standard). " + gnote, **common),
        base_meta(id="isna_unsafe_water_collect_pct", label="Households feeling unsafe while collecting water", group="Gender & protection",
                  notes="A household member felt unsafe while collecting water (recall 2 weeks in 2023-24). Water collection "
                        "is done mostly by women and girls, so this is a GBV-exposure proxy. " + gnote, **common),
        base_meta(id="isna_surface_water_source_pct", label="Households drinking surface/unprotected water", group="Water access",
                  notes="Main drinking source is a river/stream, swamp/pond or unprotected/hand-dug well (2022 category "
                        "'shallow well/river/stream/pond'). Faecal-contamination and cholera risk. " + gnote, **common),
        base_meta(id="isna_open_defecation_pct", label="Households practising open defecation", group="Sanitation",
                  notes="No sanitation facility. Combined with flooding this drives faecal contamination of surface water. " + gnote, **common),
        base_meta(id="isna_wg_avoid_water_points_pct", label="Women & girls avoid water points (unsafe)", group="Gender & protection",
                  notes="% of households reporting that women and girls avoid water points because they feel unsafe - "
                        "the GBV-risk indicator used by the GBV AoR. Not GBV incidence (GBVIMS data are not public). " + gnote, **common),
        base_meta(id="isna_wg_avoid_latrines_pct", label="Women & girls avoid latrines/bathing areas (unsafe)", group="Gender & protection",
                  notes="% of households reporting women and girls avoid latrines and bathing facilities because they feel unsafe. " + gnote, **common),
        base_meta(id="isna_wg_avoid_any_pct", label="Women & girls avoid some areas (unsafe)", group="Gender & protection",
                  notes="100 minus % of households reporting no area that women and girls avoid. " + gnote, **common),
    ]
    finalize(df, SRC, meta)


if __name__ == "__main__":
    main()
    from trend_stats import write_trends
    write_trends(SRC)  # Mann-Kendall + Sen's slope (scripts/trend_stats.py)
