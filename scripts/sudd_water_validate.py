"""Validation of the Sudd MODIS water / inundation index (scripts/sudd_water_index.py).

Compares, for the 16 Sudd counties:
  1. UNOSAT VIIRS "maximum flood water extent" county (Admin_2) tables, 2022-2025 (data/raw/unosat_floods/*.xlsx),
     against our 8-day composite that contains the middle day of each 5-day UNOSAT window;
  2. the Sentinel-1 flood series (flood_s1_county_monthly.csv; flooded = above the March reference, so it is
     compared with our inundation ANOMALY = inundation minus the county's mean March inundation 2018-2025);
  3. the national MODIS MNDWI series (water_county_monthly.csv, surface_water_km2) against our open water and
     inundation.
Writes data/processed/validation/sudd_water_vs_*.csv and prints the numbers used in docs/VALIDATION_sudd_water.md.
"""
import glob
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import hazards_common as hc
import sudd_water_index as sw

VAL = hc.PROC / "validation"
MON = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def r(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    ok = np.isfinite(a) & np.isfinite(b)
    return float(np.corrcoef(a[ok], b[ok])[0, 1]) if ok.sum() > 2 else np.nan


def spearman(a, b):
    return r(pd.Series(a).rank(), pd.Series(b).rank())


def counties():
    g = sw.grid()["counties"]
    return g[["district_id", "name", "admin1"]]


def unosat():
    cty = counties()
    names = {n.lower().replace("/", "-"): cid for n, cid in zip(cty.name, cty.district_id)}
    # spellings used in the 2023-2025 UNOSAT tables
    alias = {"old fangak": "fangak", "peji": "canal-pigi", "wuror": "uror", "payinjar": "panyijiar"}
    names.update({k: names[v] for k, v in alias.items()})
    rows = []
    for f in sorted(glob.glob(str(hc.REPO / "data/raw/unosat_floods/*.xlsx"))):
        x = pd.ExcelFile(f)
        for sh in [s for s in x.sheet_names if s.lower().startswith("admin_2")]:
            m = re.search(r"(\d{1,2})([A-Za-z]{3})?-(\d{1,2})([A-Za-z]{3})(\d{4})", sh)
            if not m:
                continue
            end = pd.Timestamp(int(m.group(5)), MON[m.group(4).lower()], int(m.group(3)))
            mid = end - pd.Timedelta(days=2)
            t = pd.read_excel(f, sheet_name=sh, header=None)
            hdr = t.index[t[0].astype(str).str.strip().str.startswith("Province")][0]
            heads = t.iloc[hdr].astype(str).str.replace(r"\s+", " ", regex=True)
            c_ext = [i for i, h in enumerate(heads) if "maximum flood water extent" in h.lower() and "km2" in h.lower()
                     and "population" not in h.lower()][0]
            c_cf = ([i for i, h in enumerate(heads) if "cloud free" in h.lower() and "area" in h.lower()] or [None])[0]
            for _, rr in t.iloc[hdr + 1:].iterrows():
                key = str(rr[0]).strip().lower().replace("/", "-")
                if key in names:
                    rows.append(dict(window_end=end.date().isoformat(), mid=mid, sheet=sh, county_id=names[key],
                                     unosat_km2=pd.to_numeric(rr[c_ext], errors="coerce"),
                                     unosat_cloudfree_km2=pd.to_numeric(rr[c_cf], errors="coerce") if c_cf is not None else np.nan))
    u = pd.DataFrame(rows).drop_duplicates(["window_end", "county_id"])
    c8 = pd.read_csv(sw.COUNTY_8DAY)
    c8["start"] = pd.to_datetime(c8.composite_start)
    c8["end"] = c8.start + pd.to_timedelta(c8.ndays - 1, unit="D")
    out = []
    for _, rr in u.iterrows():
        m = c8[(c8.county_id == rr.county_id) & (c8.start <= rr.mid) & (c8.end >= rr.mid)]
        if len(m):
            m = m.iloc[0]
            out.append({**rr.to_dict(), "composite_start": m.composite_start, "modis_inundation_km2": m.inundation_km2,
                        "modis_openwater_km2": m.openwater_km2, "modis_observed_share": m.observed_share,
                        "county_km2": m.county_km2})
    v = pd.DataFrame(out)
    v.to_csv(VAL / "sudd_water_vs_unosat_county.csv", index=False, float_format="%.3f")
    tot = v.groupby(["window_end", "composite_start"]).agg(unosat_km2=("unosat_km2", "sum"),
                                                          modis_inundation_km2=("modis_inundation_km2", "sum"),
                                                          modis_openwater_km2=("modis_openwater_km2", "sum"),
                                                          observed=("modis_observed_share", "mean"),
                                                          n=("county_id", "size")).reset_index()
    tot = tot[tot.n == 16]
    tot.to_csv(VAL / "sudd_water_vs_unosat_total.csv", index=False, float_format="%.3f")
    print("\n== UNOSAT (VIIRS max flood water extent) vs MODIS, 16 Sudd counties")
    print(tot.round(2).to_string(index=False))
    print(f"dates={len(tot)}  r(total inund)={r(tot.unosat_km2, tot.modis_inundation_km2):.2f}  "
          f"rho={spearman(tot.unosat_km2, tot.modis_inundation_km2):.2f}  "
          f"r(total openwater)={r(tot.unosat_km2, tot.modis_openwater_km2):.2f}  "
          f"median ratio inund/UNOSAT={np.median(tot.modis_inundation_km2 / tot.unosat_km2):.2f}  "
          f"median ratio ow/UNOSAT={np.median(tot.modis_openwater_km2 / tot.unosat_km2):.2f}")
    print(f"county-date pairs={len(v)}  r(county inund)={r(v.unosat_km2, v.modis_inundation_km2):.2f}  "
          f"rho={spearman(v.unosat_km2, v.modis_inundation_km2):.2f}  r(county ow)={r(v.unosat_km2, v.modis_openwater_km2):.2f}")
    cc = v.groupby("county_id").apply(lambda d: pd.Series({"r": r(d.unosat_km2, d.modis_inundation_km2),
                                                            "mean_unosat": d.unosat_km2.mean(),
                                                            "mean_modis": d.modis_inundation_km2.mean()}),
                                      include_groups=False)
    print("per-county r (median):", round(cc.r.median(), 2))
    print(cc.merge(counties().set_index("district_id")[["name"]], left_index=True, right_index=True).round(2).to_string())
    return tot, v


def s1_and_national():
    cty = counties()
    ids = set(cty.district_id)
    ours = pd.read_csv(sw.OUT_MONTHLY)
    ours = ours[ours.variable.isin(["sudd_inundation_km2", "sudd_openwater_km2"])].pivot_table(
        index=["county_id", "date"], columns="variable", values="value").reset_index()
    ours["month"] = ours.date.str[5:7]
    march = ours[ours.month == "03"].groupby("county_id").sudd_inundation_km2.mean().rename("march_ref")
    ours = ours.merge(march, on="county_id")
    ours["inund_anom_km2"] = (ours.sudd_inundation_km2 - ours.march_ref).clip(lower=0)
    s1 = pd.read_csv(hc.PROC / "flood_s1_county_monthly.csv")
    s1 = s1[s1.county_id.isin(ids) & s1.variable.isin(["flood_s1_flood_km2", "flood_s1_openwater_km2"])].pivot_table(
        index=["county_id", "date"], columns="variable", values="value").reset_index()
    nat = pd.read_csv(hc.PROC / "water_county_monthly.csv")
    nat = nat[nat.county_id.isin(ids) & (nat.variable == "surface_water_km2")].rename(columns={"value": "national_mndwi_km2"})[
        ["county_id", "date", "national_mndwi_km2"]]
    m = ours.merge(s1, on=["county_id", "date"], how="left").merge(nat, on=["county_id", "date"], how="left")
    m.to_csv(VAL / "sudd_water_vs_s1_national_county_monthly.csv", index=False, float_format="%.3f")
    full = m.dropna(subset=["flood_s1_flood_km2", "national_mndwi_km2"])
    cnt = full.groupby("date").county_id.nunique()
    tot = full[full.date.isin(cnt[cnt == 16].index)].groupby("date")[
        ["sudd_inundation_km2", "inund_anom_km2", "sudd_openwater_km2", "flood_s1_flood_km2", "flood_s1_openwater_km2",
         "national_mndwi_km2"]].sum().reset_index()
    tot.to_csv(VAL / "sudd_water_vs_s1_national_total.csv", index=False, float_format="%.1f")
    print("\n== Sentinel-1 and national MODIS vs Sudd MODIS (16-county totals, months with all 16 counties)")
    print("months:", len(tot))
    print(f"r(inundation anomaly, S1 flood) = {r(tot.inund_anom_km2, tot.flood_s1_flood_km2):.2f}; "
          f"r(inundation, S1 flood) = {r(tot.sudd_inundation_km2, tot.flood_s1_flood_km2):.2f}; "
          f"rho = {spearman(tot.inund_anom_km2, tot.flood_s1_flood_km2):.2f}")
    print(f"r(openwater, national MNDWI) = {r(tot.sudd_openwater_km2, tot.national_mndwi_km2):.2f}; "
          f"r(inundation, national MNDWI) = {r(tot.sudd_inundation_km2, tot.national_mndwi_km2):.2f}; "
          f"r(openwater, S1 openwater) = {r(tot.sudd_openwater_km2, tot.flood_s1_openwater_km2):.2f}")
    print(f"county-month r(anom, S1 flood) = {r(full.inund_anom_km2, full.flood_s1_flood_km2):.2f} (n={len(full)})")
    tot["year"] = tot.date.str[:4]; tot["mm"] = tot.date.str[5:7].astype(int)
    pk = tot[tot.mm >= 9].groupby("year")[["sudd_inundation_km2", "inund_anom_km2", "flood_s1_flood_km2",
                                           "national_mndwi_km2", "sudd_openwater_km2"]].max()
    print("Sep-Dec monthly maxima by year:\n", pk.round(0).to_string())
    print("year-to-year r of Sep-Dec maxima (anom vs S1):", round(r(pk.inund_anom_km2, pk.flood_s1_flood_km2), 2))
    clim = tot.groupby("mm")[["sudd_inundation_km2", "inund_anom_km2", "flood_s1_flood_km2", "national_mndwi_km2",
                              "sudd_openwater_km2"]].mean()
    print("mean seasonal cycle:\n", clim.round(0).to_string())
    return tot, pk


def frequency_zone():
    import rasterio
    with rasterio.open(sw.FREQ_TIF) as s:
        f = s.read(1).astype(float); o = s.read(2).astype(float)
    f[f == 255] = np.nan; o[o == 255] = np.nan
    print("\n== inundation frequency zones (share of clear 8-day obs 2018-2025)")
    for th in (10, 25, 50, 75):
        print(f"  inundated in >= {th}% of clear obs: {(f >= th).sum() * sw.PIX_KM2:,.0f} km2")
    print(f"  open water in >= 50% of clear obs: {(o >= 50).sum() * sw.PIX_KM2:,.0f} km2")


if __name__ == "__main__":
    VAL.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 200)
    unosat()
    s1_and_national()
    frequency_zone()
    ann = pd.read_csv(sw.OUT_ANNUAL)
    print("\n== AOI annual peak / low")
    print(ann[ann.district_id == "SUDD_AOI"].round(0).to_string(index=False))
