"""Public health: county-level routine immunization coverage, 2018 (WHO/UNICEF administrative data,
'World Vaccination at sub-national level', HDX world-sub-national-immunization-coverage, CC-BY).
Only 2018 is available for South Sudan at county level in open data. Penta3 proxy = HepB3 (pentavalent DTP-HepB-Hib),
measles = MCV1. Admin coverage = doses / target population (often >100% due to poor denominators and cross-border use).

Not available openly at county level (checked): IHME geospatial U5MR/DTP3 rasters (GHDx login required),
DHS (none since 2010 SHHS), MICS (none since 2010). National U5MR available from UN IGME (unicef-cme on HDX).
"""
import os
import sys
import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from overlay_utils import ROOT, counties, write_long, write_meta
from county_crosswalk import to_ocha

RAW = os.path.join(ROOT, "data", "raw", "public_health")
URL = ("https://docs.google.com/spreadsheets/d/e/2PACX-1vRfjaIXE1hvEIXD66g6cuCbPrGdZkx6vLIgXO_znVbjQ-OgwfaI1kJPhxhgjw2Yg08"
       "CmtBuMLAZkTnu/pub?output=xlsx")
PAGE = "https://data.humdata.org/dataset/world-sub-national-immunization-coverage"
IGME = ("https://sdmx.data.unicef.org/ws/public/sdmxapi/rest/data/UNICEF,CME,1.0/SSD.CME_MRY0T4+CME_MRY0.._T"
        "?format=csv&startPeriod=2018")

def main():
    os.makedirs(RAW, exist_ok=True)
    p = os.path.join(RAW, "who_subnational_immunization_2020.xlsx")
    if not os.path.exists(p):
        open(p, "wb").write(requests.get(URL, timeout=300).content)
    with open(os.path.join(RAW, "SOURCE.md"), "w") as f:
        f.write(f"WHO/UNICEF sub-national immunization coverage (HDX {PAGE}): {URL}\n")
    v = pd.read_excel(p, sheet_name="Data")
    s = v[(v.iso == "SSD") & v.Vaccine.isin(["HepB3", "MCV1"]) & (v.Numerator >= 0) & (v.Denominator > 0)].copy()
    s["county_id"] = s.Admin2.map(lambda n: to_ocha(n, "who"))  # crosswalk: AKOKA->Baliet, KHORFLUS->Canal/Pigi ...
    assert s.county_id.notna().all(), s[s.county_id.isna()].Admin2.unique()
    # Admin2 rows can share a denominator (e.g. Akoka + Baliet): sum numerators and denominators per county
    a = s.groupby(["county_id", "Year", "Vaccine"])[["Numerator", "Denominator"]].sum().reset_index()
    a["value"] = 100 * a.Numerator / a.Denominator
    a["variable"] = a.Vaccine.map({"HepB3": "vacc_penta3_cov", "MCV1": "vacc_mcv1_cov"})
    a["date"] = a.Year.astype(int).astype(str) + "-07-01"
    write_long("public_health", a.rename(columns={})[["county_id", "date", "variable", "value"]])
    print(a.groupby("variable").value.describe())
    # national under-5 and infant mortality (UN IGME) -> county_id 'SS' (national, lead broadcasts)
    from overlay_utils import PROC
    import io
    r = requests.get(IGME, timeout=120)
    r.raise_for_status()
    open(os.path.join(RAW, "unicef_cme_ssd.csv"), "w").write(r.text)
    m = pd.read_csv(io.StringIO(r.text))
    m = m[(m.SEX == "_T") & (m.WEALTH_QUINTILE == "_T") & (m.DATA_SOURCE == "UN_IGME")]
    m["variable"] = m.INDICATOR.map({"CME_MRY0T4": "u5mr_national", "CME_MRY0": "imr_national"})
    m["date"] = m.TIME_PERIOD.astype(int).astype(str) + "-07-01"
    m = m[m.TIME_PERIOD.astype(int).between(2018, 2025)]
    nat = m.assign(county_id="SS", value=m.OBS_VALUE)[["county_id", "date", "variable", "value"]]
    nat.to_csv(os.path.join(PROC, "public_health_national.csv"), index=False)
    print(nat)
    base = {"category": "human", "group": "Public health", "source": "WHO/UNICEF administrative immunization data, 2018 (HDX)",
            "source_url": PAGE, "native_resolution": "county", "temporal": "annual", "index_ok": False, "higher_is": "better",
            "aggregation": "doses administered / target population x 100 (county)"}
    note = ("ONLY 2018 available at county level (single year). Administrative coverage: unreliable denominators, "
            "values >100% common (cross-county/border service use); near-0 values often indicate non-reporting. "
            "No open county-level infant/under-5 mortality for South Sudan (no DHS/MICS since 2010; IHME rasters need login).")
    write_meta("public_health", [
        dict(base, id="vacc_penta3_cov", label="Penta3 / DTP3 coverage (admin, 2018)", units="%",
             notes="HepB3 dose of pentavalent (DTP-HepB-Hib) used as DTP3 proxy. " + note),
        dict(base, id="vacc_mcv1_cov", label="Measles (MCV1) coverage (admin, 2018)", units="%", notes=note),
        dict(base, id="u5mr_national", label="Under-5 mortality (national)", units="deaths per 1,000 live births",
             higher_is="worse", source="UN IGME via UNICEF SDMX", source_url="https://childmortality.org/",
             native_resolution="national", aggregation="national estimate (county_id SS, file public_health_national.csv)",
             notes="NATIONAL ONLY; modelled with very wide uncertainty bounds (no survey since 2010)."),
        dict(base, id="imr_national", label="Infant mortality (national)", units="deaths per 1,000 live births",
             higher_is="worse", source="UN IGME via UNICEF SDMX", source_url="https://childmortality.org/",
             native_resolution="national", aggregation="national estimate (county_id SS, file public_health_national.csv)",
             notes="NATIONAL ONLY; modelled with very wide uncertainty bounds."),
    ])


if __name__ == "__main__":
    main()
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from trend_stats import write_trends
    write_trends("public_health")  # Mann-Kendall + Sen's slope (scripts/trend_stats.py)
