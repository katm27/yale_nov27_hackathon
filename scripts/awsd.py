"""Aid Worker Security Database (Humanitarian Outcomes) for South Sudan: yearly national counts of incidents
against aid workers, split into incidents on roads and elsewhere, and aid workers kidnapped.

Input : data/raw/awsd/awsd_south_sudan.csv (South Sudan rows of the global AWSD file on HDX,
        https://data.humdata.org/dataset/aid-worker-security-data-global, accessed 17 Nov 2026).
Output: data/processed/awsd_county_monthly.csv (national rows, county_id "SS", yearly value repeated each month)
        and data/processed/meta/awsd.json. Usage: python scripts/awsd.py
"""
import json, os
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = pd.read_csv(os.path.join(ROOT, "data", "raw", "awsd", "awsd_south_sudan.csv"))
d = d[(d.Year >= 2018) & (d.Year <= 2025)]
road = d["Location"].astype(str).str.strip().eq("Road")
yr = pd.DataFrame({
    "awsd_road_incidents_year": d[road].groupby("Year").size(),
    "awsd_other_incidents_year": d[~road].groupby("Year").size(),
    "awsd_kidnapped_year": d.groupby("Year")["Total kidnapped"].sum(),
}).reindex(range(2018, 2026)).fillna(0)
rows = []
for y, r in yr.iterrows():
    for m in range(1, 13):
        for vid, val in r.items():
            rows.append(("SS", f"{y}-{m:02d}-01", vid, float(val)))
pd.DataFrame(rows, columns=["county_id", "date", "variable", "value"]).to_csv(os.path.join(ROOT, "data", "processed", "awsd_county_monthly.csv"), index=False)
common = dict(category="human", group="Aid worker security (national)", source="Aid Worker Security Database (Humanitarian Outcomes) via HDX",
              source_url="https://data.humdata.org/dataset/aid-worker-security-data-global", native_resolution="national",
              temporal="monthly", aggregation="count of incidents per calendar year", higher_is="worse", index_ok=False,
              notes="Reported major attacks on aid workers (killings, kidnappings, serious injuries). National yearly count repeated each month; it does not vary by county.")
meta = [dict(id="awsd_road_incidents_year", label="Attacks on aid workers on roads (per year)", units="incidents per year", **common),
        dict(id="awsd_other_incidents_year", label="Attacks on aid workers elsewhere (per year)", units="incidents per year", **common),
        dict(id="awsd_kidnapped_year", label="Aid workers kidnapped (per year)", units="people per year", **common)]
json.dump(meta, open(os.path.join(ROOT, "data", "processed", "meta", "awsd.json"), "w"), indent=1)
print(yr.astype(int).to_string())
