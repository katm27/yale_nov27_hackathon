"""Compare MODIS monthly surface water (water_county_monthly.csv) with UNOSAT VIIRS-based
'satellite detected water extents' state tables (HDX exposure XLSX in data/raw/unosat_floods/).
Writes data/raw/unosat_floods/validation_state.csv and prints summary stats."""
import glob
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd

sys.path.insert(0, str(Path(__file__).parent))
import hazards_common as hc

g = gpd.read_file(hc.COUNTIES)[["district_id", "admin1"]]
w = pd.read_csv(hc.PROC / "water_county_monthly.csv")
w = w[w.variable == "surface_water_km2"].merge(g, left_on="county_id", right_on="district_id")
rows = []
for f in sorted(glob.glob(str(hc.REPO / "data/raw/unosat_floods/*.xlsx"))):
    x = pd.read_excel(f, sheet_name=0, header=None)
    hdr = x.index[x[0].astype(str).str.strip() == "Province"][0]
    t = x.iloc[hdr + 1:hdr + 12, [0, 4]]
    t.columns = ["state", "unosat_km2"]
    t = t[pd.to_numeric(t.unosat_km2, errors="coerce").notna() & (t.state.astype(str).str.strip() != "Total")]
    m = re.search(r"_(\d\d)([A-Z][a-z]{2})_(\d\d)([A-Z][a-z]{2})(\d{4})", f)
    month = pd.Timestamp(f"{m.group(3)} {m.group(4)} {m.group(5)}").strftime("%Y-%m-01")
    ours = w[w.date == month].groupby("admin1").value.sum()
    for _, r in t.iterrows():
        s = str(r.state).strip()
        if s in ours.index:
            rows.append((Path(f).name, month, s, float(r.unosat_km2), float(ours[s])))
df = pd.DataFrame(rows, columns=["unosat_file", "month", "state", "unosat_km2", "modis_km2"])
df.to_csv(hc.REPO / "data/raw/unosat_floods/validation_state.csv", index=False)
if len(df):
    tot = df.groupby(["unosat_file", "month"])[["unosat_km2", "modis_km2"]].sum()
    print(tot.round())
    print("state-level Pearson r (all dates):", round(np.corrcoef(df.unosat_km2, df.modis_km2)[0, 1], 3),
          " median MODIS/UNOSAT total ratio:", round((tot.modis_km2 / tot.unosat_km2).median(), 2), "n dates", len(tot))
