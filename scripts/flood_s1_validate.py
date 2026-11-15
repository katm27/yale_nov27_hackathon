"""Validate the Sentinel-1 flood layer (flood_s1_pipeline.py) against UNOSAT VIIRS flood maps.

1. Pixel level (~440 m grid): UNOSAT 5-day flood-extent + permanent-water polygons, 2021-09..2022-10
   (FL20220424SSD_SHP.zip from https://unosat.org/static/unosat_filesystem/3399/FL20220424SSD_SHP.zip, unzipped in
   data/raw/unosat_floods/_cache/), UNOSAT cloud-obstruction areas excluded. Metrics: F1, IoU, area ratio S1/UNOSAT.
   NOTE: 2022-10-04..08 was used to choose the S1 thresholds -> reported separately (not independent).
2. State level: UNOSAT exposure XLSX tables (30 dates 2022-10..2025-04, data/raw/unosat_floods/*.xlsx) vs
   flood_s1_water_km2 and MODIS surface_water_km2 summed by state, same months.
Writes data/processed/validation/flood_s1_vs_unosat_pixel.csv and flood_s1_vs_unosat_state.csv.
"""
import glob
import re
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from rasterio import features

sys.path.insert(0, str(Path(__file__).parent))
import hazards_common as hc
import flood_s1_pipeline as f

SHP = hc.REPO / "data/raw/unosat_floods/_cache/FL20220424SSD_SHP"
VAL = hc.PROC / "validation"
CAL = "20221004_20221008"


def rast(path, gtr, gs):
    g = gpd.read_file(path).to_crs(4326)
    geoms = [(geom, 1) for geom in g.geometry if geom is not None and not geom.is_empty]
    if not geoms:
        return np.zeros(gs, bool)
    return features.rasterize(geoms, out_shape=gs, transform=gtr, fill=0, dtype="uint8").astype(bool)


def pixel_level():
    gtr, gs, gc = f.grid()
    lab = hc.labels_for(gc, gtr, gs)
    area = f.pixel_area_km2(gtr, gs)
    water = {m: w for m, w, _ in f.water_series()}
    rows = []
    for fe in sorted(glob.glob(str(SHP / "VIIRS_*_*_*Flood*Extent*_SouthSudan.shp")) + sorted(glob.glob(str(SHP / "VIIRS_*_MaximumFloodWater_SouthSudan.shp")))):
        m = re.search(r"VIIRS_(\d{8})_(\d{8})_", fe)
        d0, d1 = m.group(1), m.group(2)
        if (pd.Timestamp(d1) - pd.Timestamp(d0)).days > 7:  # skip 30-day cumulative maps
            continue
        mid = pd.Timestamp(d0) + (pd.Timestamp(d1) - pd.Timestamp(d0)) / 2
        mon = mid.strftime("%Y-%m")
        if mon not in water:
            continue
        pw_f = SHP / f"VIIRS_{d0}_{d1}_PermanentWater_SouthSudan.shp"
        cl_f = SHP / f"VIIRS_{d0}_{d1}_CloudObstruction_SouthSudan.shp"
        U = rast(fe, gtr, gs)
        if pw_f.exists():
            U |= rast(pw_f, gtr, gs)
        cloud = rast(cl_f, gtr, gs) if cl_f.exists() else np.zeros(gs, bool)
        w = water[mon]
        ok = (lab > 0) & (w >= 0) & ~cloud
        P = (w == 1) & ok; T = U & ok
        tp = (area * (P & T)).sum(); fp = (area * (P & ~T)).sum(); fn = (area * (~P & T)).sum()
        rows.append(dict(unosat=f"{d0}_{d1}", month=mon, calibration=(f"{d0}_{d1}" == CAL),
                         unosat_km2=round(float((area * T).sum())), s1_km2=round(float((area * P).sum())),
                         f1=round(2 * tp / (2 * tp + fp + fn), 3), iou=round(tp / (tp + fp + fn), 3),
                         precision=round(tp / (tp + fp), 3), recall=round(tp / (tp + fn), 3),
                         compared_km2=round(float((area * ok).sum()))))
        print(rows[-1], flush=True)
    df = pd.DataFrame(rows)
    VAL.mkdir(parents=True, exist_ok=True)
    df.to_csv(VAL / "flood_s1_vs_unosat_pixel.csv", index=False)
    ind = df[~df.calibration]
    print("independent dates:", len(ind), "median F1", ind.f1.median(), "median IoU", ind.iou.median(),
          "median area ratio", round((ind.s1_km2 / ind.unosat_km2).median(), 2))
    return df


def state_level():
    g = gpd.read_file(hc.COUNTIES)[["district_id", "admin1"]]
    s1 = pd.read_csv(hc.PROC / "flood_s1_county_monthly.csv")
    s1 = s1[s1.variable == "flood_s1_water_km2"].merge(g, left_on="county_id", right_on="district_id")
    mo = pd.read_csv(hc.PROC / "water_county_monthly.csv")
    mo = mo[mo.variable == "surface_water_km2"].merge(g, left_on="county_id", right_on="district_id")
    rows = []
    for fx in sorted(glob.glob(str(hc.REPO / "data/raw/unosat_floods/*.xlsx"))):
        x = pd.read_excel(fx, sheet_name=0, header=None)
        hdr = x.index[x[0].astype(str).str.strip() == "Province"][0]
        t = x.iloc[hdr + 1:hdr + 12, [0, 4]]
        t.columns = ["state", "unosat_km2"]
        t = t[pd.to_numeric(t.unosat_km2, errors="coerce").notna() & (t.state.astype(str).str.strip() != "Total")]
        m = re.search(r"_(\d\d)([A-Z][a-z]{2})_(\d\d)([A-Z][a-z]{2})(\d{4})", fx)
        month = pd.Timestamp(f"{m.group(3)} {m.group(4)} {m.group(5)}").strftime("%Y-%m-01")
        a = s1[s1.date == month].groupby("admin1").value.sum()
        b = mo[mo.date == month].groupby("admin1").value.sum()
        for _, r in t.iterrows():
            st = str(r.state).strip()
            if st in a.index:
                rows.append((Path(fx).name, month, st, float(r.unosat_km2), float(a[st]), float(b.get(st, np.nan))))
    df = pd.DataFrame(rows, columns=["unosat_file", "month", "state", "unosat_km2", "s1_km2", "modis_km2"])
    df.to_csv(VAL / "flood_s1_vs_unosat_state.csv", index=False)
    if len(df):
        d = df.dropna()
        tot = d.groupby(["unosat_file", "month"])[["unosat_km2", "s1_km2", "modis_km2"]].sum()
        print(tot.round())
        print("state-level r: S1", round(np.corrcoef(d.unosat_km2, d.s1_km2)[0, 1], 3),
              "MODIS", round(np.corrcoef(d.unosat_km2, d.modis_km2)[0, 1], 3), "n", len(d))
        print("national-total r over dates: S1", round(np.corrcoef(tot.unosat_km2, tot.s1_km2)[0, 1], 3),
              "MODIS", round(np.corrcoef(tot.unosat_km2, tot.modis_km2)[0, 1], 3),
              "| median ratio S1/UNOSAT", round((tot.s1_km2 / tot.unosat_km2).median(), 2),
              "MODIS/UNOSAT", round((tot.modis_km2 / tot.unosat_km2).median(), 2))
    return df


if __name__ == "__main__":
    pixel_level()
    state_level()
