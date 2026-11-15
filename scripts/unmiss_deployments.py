"""UNMISS deployments -> docs/data/points_unmiss.geojson + county unmiss_presence / unmiss_troops (annual).

2018-2024: Geo-PKO v2.3 (Cil et al., ISDP/Uppsala; coded from UN deployment maps No. 4456), cloned from
           https://github.com/geopko/Geo-PKO-Shiny-Dashboard (data/Geo_PKO_v.2.3_ISO3.csv).
           Troops per location averaged over the year's map timepoints (Geo-PKO estimates from unit sizes).
2025/2026: read off UN Geospatial map 4456 Rev.62 (Jan 2025) and Rev.67 (Jan 2026) PDFs in the Drive
           (data/drive_mirror/01_analysis_ready). Locations shown in blue = deployed. No troop numbers on the
           maps; 2025 troops carried from the last Geo-PKO timepoint (Oct 2024) for locations still deployed.
"""
import os
import subprocess
import sys
import numpy as np
import pandas as pd
import geopandas as gpd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from overlay_utils import ROOT, DOCS_DATA, counties, write_long, write_meta, add_points_meta, assign_county

RAW = os.path.join(ROOT, "data", "raw", "geopko")
GEOPKO_URL = "https://raw.githubusercontent.com/geopko/Geo-PKO-Shiny-Dashboard/master/data/Geo_PKO_v.2.3_ISO3.csv"
REPO = "https://github.com/geopko/Geo-PKO-Shiny-Dashboard"

# Locations deployed per UN map 4456 (blue symbols), with sector HQ roles and units listed on the map
MAP_2025 = {  # Rev.62, January 2025
    "Juba": ("Force HQ / Sector South & Juba HQ", "Rwanda 1, Rwanda 3, China, Ethiopia, Nepal II, Nepal 2 (ARG), Nepal (HRC), Bangladesh, Thailand, India, MP Cambodia, FPU Nepal 1, FPU Rwanda 3"),
    "Bentiu": ("Sector HQ (Unity)", "Ghana, Mongolia, Viet Nam, India, Pakistan, MP Cambodia, FPU Ghana 1"),
    "Malakal": ("Sector HQ (North)", "India 1, Rwanda 2, Rwanda, India, Bangladesh (riverine), MP Cambodia, FPU Rwanda 1"),
    "Wau": ("Sector HQ (West)", "Bangladesh, China, India, MP Cambodia"),
    "Bor": ("Sector HQ (East)", "Ethiopia 2, India 2, Mongolia, Korea (ROK), Sri Lanka, India, MP Cambodia"),
    "Aweil": ("company operating base", "Nepal 1, India"), "Kuacjok": ("company operating base", "Bangladesh, China, India"),
    "Rumbek": ("team site", "Nepal 1, India, Thailand, MP Cambodia"), "Yambio": ("team site", "Ethiopia 3, India, Thailand, India"),
    "Tambura": ("company operating base", "Ethiopia 3"), "Yei": ("company operating base", "Nepal 2 FRB"),
    "Torit": ("team site", "Rwanda 1, India"), "Pibor": ("team site", "India 2, Korea (ROK)"),
    "Akobo": ("company operating base", "India 2"), "Leer": ("company operating base", "Ghana"),
    "Pariang": ("company operating base", "Mongolia"), "Renk": ("company operating base", "India 1"),
    "Kodok": ("company operating base", "India 1"), "Bunji": ("company operating base", "Rwanda 2"),
}
GONE_2026 = {"Aweil", "Tambura", "Yei", "Torit"}  # shown as non-UNMISS (black) on Rev.67, Jan 2026


def load_geopko():
    os.makedirs(RAW, exist_ok=True)
    p = os.path.join(RAW, "Geo_PKO_v.2.3_ISO3_UNMISS.csv")
    if not os.path.exists(p):
        import requests
        full = os.path.join(RAW, "_full.csv")
        r = requests.get(GEOPKO_URL, timeout=300)
        if r.ok:
            open(full, "wb").write(r.content)
        else:  # fall back to git clone
            tmp = os.path.join(RAW, "_repo")
            subprocess.run(["git", "clone", "-q", "--depth", "1", REPO + ".git", tmp], check=True)
            os.replace(os.path.join(tmp, "data", "Geo_PKO_v.2.3_ISO3.csv"), full)
        d = pd.read_csv(full, low_memory=False)
        d[d.mission.astype(str).str.contains("UNMISS")].to_csv(p, index=False)
        os.remove(full)
        with open(os.path.join(RAW, "SOURCE.md"), "w") as f:
            f.write(f"Geo-PKO v2.3 (UNMISS subset). Source repo {REPO} file data/Geo_PKO_v.2.3_ISO3.csv\n"
                    "Cite: Cil, Fjelde, Hultman & Nilsson (2020) Mapping blue helmets, JPR.\n")
    return pd.read_csv(p, low_memory=False)


def main():
    d = load_geopko()
    d = d[d.year >= 2018]
    d["troops"] = pd.to_numeric(d["no.troops"], errors="coerce").fillna(0)
    tcc = [f"nameoftcc_{i}" for i in range(1, 18)]
    loc = d.groupby(["year", "timepoint", "location"]).agg(
        lat=("latitude", "first"), lon=("longitude", "first"), troops=("troops", "sum"), hq=("hq", "max"),
        fpu=("fpu", "max"), unpol=("unpol.dummy", "max"),
        tccs=(tcc[0], lambda s: s.dropna().iloc[0] if s.notna().any() else None)).reset_index()
    # all TCCs per location-year
    tccs = d.melt(id_vars=["year", "location"], value_vars=tcc).dropna(subset=["value"]) \
        .groupby(["year", "location"]).value.apply(lambda s: ", ".join(sorted(set(s)))).rename("tcc_list")
    yr = loc.groupby(["year", "location"]).agg(lat=("lat", "mean"), lon=("lon", "mean"), troops=("troops", "mean"),
                                               hq=("hq", "max"), fpu=("fpu", "max"),
                                               n_timepoints=("timepoint", "nunique")).reset_index()
    yr = yr.join(tccs, on=["year", "location"])
    hqmap = {0: "team site / company base", 1: "HQ (sector)", 2: "Sector HQ", 3: "Mission / Force HQ"}
    yr["type"] = yr.hq.map(lambda h: hqmap.get(int(h) if pd.notna(h) else 0, "HQ"))
    yr["source"] = "Geo-PKO v2.3 (UN map 4456)"
    # 2025 + 2026 from the Drive PDFs; coordinates = Geo-PKO coordinates of same location
    last = loc[loc.timepoint == loc[loc.year == loc.year.max()].timepoint.iloc[-1]].set_index("location")
    coords = yr.groupby("location")[["lat", "lon"]].last()
    add = []
    for y, src in [(2025, "UN map 4456 Rev.62, Jan 2025 (Drive PDF)"), (2026, "UN map 4456 Rev.67, Jan 2026 (Drive PDF)")]:
        for name, (typ, units) in MAP_2025.items():
            if y == 2026 and name in GONE_2026:
                continue
            la, lo = coords.loc[name]
            tr = float(last.troops.get(name, np.nan)) if y == 2025 else np.nan
            add.append(dict(year=y, location=name, lat=la, lon=lo, troops=tr, type=typ, tcc_list=units,
                            source=src + ("; troops = Geo-PKO Oct 2024 estimate" if y == 2025 else "")))
    pts = pd.concat([yr, pd.DataFrame(add)], ignore_index=True)
    gdf = gpd.GeoDataFrame(pts.rename(columns={"location": "name", "troops": "troops_est", "tcc_list": "units_tcc"})
                           [["name", "type", "year", "troops_est", "units_tcc", "source"]],
                           geometry=gpd.points_from_xy(pts.lon, pts.lat), crs=4326)
    gdf["troops_est"] = gdf["troops_est"].round(0)
    gdf = assign_county(gdf)
    gdf.to_file(os.path.join(DOCS_DATA, "points_unmiss.geojson"), driver="GeoJSON", COORDINATE_PRECISION=5)
    print(gdf.groupby("year").agg(n=("name", "size"), t=("troops_est", "sum")))
    # county annual vars 2018-2025 (0 = true zero: no UNMISS deployment location in county)
    ids = sorted(counties().district_id)
    rows = []
    for y in range(2018, 2026):
        g = gdf[gdf.year == y]
        tr = g.groupby("county_id").troops_est.sum()
        for cid in ids:
            pres = 1.0 if cid in set(g.county_id) else 0.0
            rows.append((cid, f"{y}-07-01", "unmiss_presence", pres))
            rows.append((cid, f"{y}-07-01", "unmiss_troops", float(tr.get(cid, 0.0))))
    write_long("unmiss", pd.DataFrame(rows, columns=["county_id", "date", "variable", "value"]))
    base = {"category": "human", "group": "Peacekeeping", "source": "Geo-PKO v2.3 (2018-2024); UN map 4456 Rev.62 (2025)",
            "source_url": "https://www.pcr.uu.se/data/geo-pko/", "native_resolution": "deployment location (town)",
            "temporal": "annual", "higher_is": "neutral", "index_ok": False}
    write_meta("unmiss", [
        dict(base, id="unmiss_presence", label="UNMISS deployment present", units="0/1",
             aggregation="1 if any UNMISS deployment location in county during year",
             notes="Base/team-site level, not patrol coverage. 2025 from Jan 2025 deployment map."),
        dict(base, id="unmiss_troops", label="UNMISS troops deployed (est.)", units="troops",
             aggregation="sum of Geo-PKO troop estimates at county locations, mean over the year's map timepoints",
             notes="Geo-PKO estimates troop numbers from unit sizes on UN maps (approximate). 2025 = Oct 2024 values for "
                   "locations still shown on the Jan 2025 map. UNPOL/FPU police strength not fully included."),
    ])
    # time-dynamic point layer (one feature per location x period) + points.json entry: scripts/points_unmiss.py
    import points_unmiss
    points_unmiss.main()


if __name__ == "__main__":
    main()
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from trend_stats import write_trends
    write_trends("unmiss")  # Mann-Kendall + Sen's slope (scripts/trend_stats.py)
