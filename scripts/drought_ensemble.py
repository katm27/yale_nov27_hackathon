"""Drought-index ensemble and its uncertainty per county-month (2018-01..2025-12).

Members (each a standardised index, ~N(0,1), negative = dry; all 3-month accumulation):
  dr_spei3_imerg   SPEI-3 from IMERG V07 precipitation - Thornthwaite PET (MERRA-2 T2M)   [drive_climate spei3;
                   baseline = county 2000-2026 history, computed upstream]
  dr_spi3_chirps   SPI-3 from CHIRPS v3.0 monthly rainfall (gauge-blended IR), gamma fit, baseline 1991-2020
  dr_spei3_tc      SPEI-3 from TerraClimate v1.1 ppt - Penman-Monteith PET, log-logistic (L-moments), 1991-2020
  dr_pdsi_tc_z     TerraClimate self-calibrated-style PDSI, re-standardised per county & calendar month against
                   its own 1991-2020 values (raw PDSI is ~-6.6 nationally in 2018-2025, see terraclimate meta)
Outputs (data/processed/drought_ensemble_county_monthly.csv):
  members above, drought_ensemble_mean (mean of available members, >=3 required),
  drought_ensemble_spread (standard deviation across members), drought_ensemble_range (max - min),
  drought_ensemble_agree (share of members agreeing on the sign of the mean, 0..1).
Interpretation: |mean| large with small spread = robust signal; spread > ~1 = the inputs disagree (rain products
disagree strongly over the Sudd and the north-east, where gauges are almost absent).

County precipitation/PET series are area-weighted means of the gridded products (weights from
fetch_terraclimate.weights), then the 3-month accumulation and standardisation are done on the county series.

Usage: python scripts/drought_ensemble.py [--no-download]
Raw TerraClimate subsets (ppt, pet, PDSI 1991-2025) and the CHIRPS 1991-2025 crop are cached in
data/raw/drought_ensemble/_cache/ (not committed).
"""
import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import xarray as xr
from scipy import stats

sys.path.insert(0, str(Path(__file__).parent))
import fetch_terraclimate as tc

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/raw/drought_ensemble/_cache"
OUT = ROOT / "data/processed/drought_ensemble_county_monthly.csv"
META = ROOT / "data/processed/meta/drought_ensemble.json"
YEARS = list(range(1991, 2026))
BASE = (1991, 2020)
CHIRPS = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/africa/tifs/chirps-v3.0.{y}.{m:02d}.tif"
CB = tc.BBOX


# ------------------------------------------------------------------ data
def chirps_month(y, m):
    out = CACHE / "chirps" / f"{y}-{m:02d}.npy"
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(4):
        try:
            with rasterio.open("/vsicurl/" + CHIRPS.format(y=y, m=m)) as s:
                win = rasterio.windows.from_bounds(CB["west"], CB["south"], CB["east"], CB["north"], s.transform)
                win = win.round_offsets().round_lengths()
                a = s.read(1, window=win).astype("float32")
                a[a < -1] = np.nan
                if not (CACHE / "chirps" / "transform.npy").exists():
                    np.save(CACHE / "chirps" / "transform.npy", np.array(tuple(s.window_transform(win))[:6]))
            np.save(out, a)
            return out
        except Exception as e:  # noqa
            print("retry chirps", y, m, e, flush=True)
            time.sleep(5 * (attempt + 1))
    print("FAILED chirps", y, m)
    return None


def download():
    CACHE.mkdir(parents=True, exist_ok=True)
    jobs = [(v, y) for v in ("ppt", "pet", "pdsi") for y in YEARS]
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(lambda j: tc.fetch(j[0], j[1], CACHE), jobs))
    print("terraclimate missing:", [j for j, r in zip(jobs, res) if r is None], flush=True)
    jobs = [(y, m) for y in YEARS for m in range(1, 13)]
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(lambda j: chirps_month(*j), jobs))
    print("chirps missing:", [j for j, r in zip(jobs, res) if r is None], flush=True)


def tc_county(var, cty):
    da = tc.load(var, YEARS, CACHE)
    W = tc.weights(cty, da.lat, da.lon)
    arr = tc.county_means(da, W)
    return pd.DataFrame(arr, index=pd.DatetimeIndex(da.time.values).to_period("M").to_timestamp(),
                        columns=cty.district_id.tolist())


def chirps_county(cty):
    from affine import Affine
    t = Affine(*np.load(CACHE / "chirps" / "transform.npy"))
    files = sorted((CACHE / "chirps").glob("????-??.npy"))
    a0 = np.load(files[0])
    ny, nx = a0.shape
    lon = xr.DataArray(t.c + (np.arange(nx) + 0.5) * t.a)
    lat = xr.DataArray(t.f + (np.arange(ny) + 0.5) * t.e)
    W = tc.weights(cty, lat, lon)
    stack = np.stack([np.load(f) for f in files])
    v = stack.reshape(len(files), -1)
    valid = np.isfinite(v)
    with np.errstate(invalid="ignore", divide="ignore"):
        arr = (np.where(valid, v, 0) @ W.T) / (valid.astype("float64") @ W.T)
    idx = pd.to_datetime([f.stem + "-01" for f in files])
    return pd.DataFrame(arr, index=idx, columns=cty.district_id.tolist())


# ------------------------------------------------------------------ standardisation
def _base_mask(idx):
    return (idx.year >= BASE[0]) & (idx.year <= BASE[1])


def spi(p3):
    """SPI from 3-month sums (DataFrame time x county), gamma with zero-inflation, per calendar month."""
    out = pd.DataFrame(np.nan, index=p3.index, columns=p3.columns)
    base = _base_mask(p3.index)
    for c in p3.columns:
        for mth in range(1, 13):
            sel = p3.index.month == mth
            x = p3.loc[sel, c]
            xb = x[base[sel]].dropna()
            if len(xb) < 20:
                continue
            q0 = (xb <= 0.1).mean()
            pos = xb[xb > 0.1]
            if len(pos) < 10 or pos.std() == 0:
                continue
            a, loc, scale = stats.gamma.fit(pos, floc=0)
            cdf = q0 + (1 - q0) * stats.gamma.cdf(x.clip(lower=0), a, loc=0, scale=scale)
            cdf = np.clip(cdf, 0.001, 0.999)  # bounded at +-3.09
            out.loc[sel, c] = stats.norm.ppf(cdf)
    return out


def _lmom(x):
    x = np.sort(x); n = len(x); i = np.arange(1, n + 1)
    b0 = x.mean(); b1 = np.sum((i - 1) / (n - 1) * x) / n; b2 = np.sum((i - 1) * (i - 2) / ((n - 1) * (n - 2)) * x) / n
    return b0, b1, b2


def spei(d3):
    """SPEI (Vicente-Serrano et al. 2010): 3-parameter log-logistic fitted by unbiased PWMs, per calendar month."""
    from scipy.special import gamma as G
    out = pd.DataFrame(np.nan, index=d3.index, columns=d3.columns)
    base = _base_mask(d3.index)
    for c in d3.columns:
        for mth in range(1, 13):
            sel = d3.index.month == mth
            x = d3.loc[sel, c]
            xb = x[base[sel]].dropna().values
            if len(xb) < 20 or np.std(xb) == 0:
                continue
            # PWMs w_s = sum (1-F)^s x / n  (Hosking plotting positions)
            xs = np.sort(xb); n = len(xs); F = (np.arange(1, n + 1) - 0.35) / n
            w0 = np.mean(xs); w1 = np.mean((1 - F) * xs); w2 = np.mean((1 - F) ** 2 * xs)
            beta = (2 * w1 - w0) / (6 * w1 - w0 - 6 * w2)
            if not np.isfinite(beta) or beta <= 1:
                beta = 1.0001
            alpha = (w0 - 2 * w1) * beta / (G(1 + 1 / beta) * G(1 - 1 / beta))
            gam = w0 - alpha * G(1 + 1 / beta) * G(1 - 1 / beta)
            with np.errstate(all="ignore"):
                cdf = 1.0 / (1.0 + (alpha / (x.values - gam)) ** beta)
            cdf = np.where(x.values <= gam, 0.001, cdf)
            cdf = np.clip(cdf, 0.001, 0.999)
            out.loc[sel, c] = stats.norm.ppf(cdf)
    return out


def zscore_by_month(df):
    base = _base_mask(df.index)
    out = df.copy() * np.nan
    for mth in range(1, 13):
        sel = df.index.month == mth
        b = df[sel & base]
        out[sel] = (df[sel] - b.mean()) / b.std()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-download", action="store_true")
    a = ap.parse_args()
    if not a.no_download:
        download()
    cty = gpd.read_file(tc.COUNTIES)[["district_id", "geometry"]]
    ppt = tc_county("ppt", cty); pet = tc_county("pet", cty); pdsi = tc_county("pdsi", cty)
    chp = chirps_county(cty)
    roll = lambda d: d.rolling(3, min_periods=3).sum()
    members = {
        "dr_spi3_chirps": spi(roll(chp)),
        "dr_spei3_tc": spei(roll(ppt - pet)),
        "dr_pdsi_tc_z": zscore_by_month(pdsi),
    }
    drive = pd.read_csv(ROOT / "data/processed/drive_climate_county_monthly.csv")
    d = drive[drive.variable == "spei3"].pivot(index="date", columns="county_id", values="value")
    d.index = pd.to_datetime(d.index)
    members["dr_spei3_imerg"] = d
    win = pd.date_range("2018-01-01", "2025-12-01", freq="MS")
    ids = cty.district_id.tolist()
    M = {k: v.reindex(index=win, columns=ids) for k, v in members.items()}
    cube = np.stack([M[k].values for k in M])  # member x time x county
    n = np.isfinite(cube).sum(0)
    with np.errstate(all="ignore"):
        import warnings
        warnings.simplefilter("ignore")
        mean = np.nanmean(cube, 0); sd = np.nanstd(cube, 0, ddof=1)
        rng = np.nanmax(cube, 0) - np.nanmin(cube, 0)
        agree = np.nansum(np.sign(cube) == np.sign(mean)[None], 0) / n
    ok = n >= 3
    derived = {"drought_ensemble_mean": np.where(ok, mean, np.nan), "drought_ensemble_spread": np.where(ok, sd, np.nan),
               "drought_ensemble_range": np.where(ok, rng, np.nan), "drought_ensemble_agree": np.where(ok, agree, np.nan)}
    frames = []
    for k, arr in list({k: M[k].values for k in M if k != "dr_spei3_imerg"}.items()) + list(derived.items()):
        df = pd.DataFrame(arr, index=win.strftime("%Y-%m-01"), columns=ids).stack().rename("value").reset_index()
        df.columns = ["date", "county_id", "value"]; df["variable"] = k
        frames.append(df)
    out = pd.concat(frames)[["county_id", "date", "variable", "value"]].dropna()
    out["value"] = out.value.round(4)
    out.sort_values(["variable", "county_id", "date"]).to_csv(OUT, index=False)
    # diagnostics: pairwise correlations of members 2018-2025 (pooled county-months)
    flat = pd.DataFrame({k: M[k].values.ravel() for k in M}).dropna()
    corr = flat.corr().round(2)
    print(corr)
    print("mean spread", np.nanmean(derived["drought_ensemble_spread"]).round(3), "n rows", len(out))
    corr.to_csv(ROOT / "data/raw/drought_ensemble/member_correlations_2018_2025.csv")
    write_meta(corr)


def write_meta(corr):
    import json
    common = dict(category="environment", group="Drought", temporal="monthly", index_ok=False, raster=None,
                  native_resolution="county (from 4-10 km grids)")
    c = lambda a, b: corr.loc[a, b] if a in corr.index and b in corr.columns else float("nan")
    corr_txt = (f"Pooled 2018-2025 county-month correlations between members: CHIRPS SPI vs IMERG SPEI r={c('dr_spi3_chirps','dr_spei3_imerg')}, "
                f"CHIRPS SPI vs TC SPEI r={c('dr_spi3_chirps','dr_spei3_tc')}, IMERG SPEI vs TC SPEI r={c('dr_spei3_imerg','dr_spei3_tc')}, "
                f"TC SPEI vs TC PDSI-z r={c('dr_spei3_tc','dr_pdsi_tc_z')}.")
    ens_src = ("Ensemble of 4 drought indices: SPEI-3 IMERG/MERRA-2 (drive_climate spei3), SPI-3 CHIRPS v3.0, SPEI-3 "
               "TerraClimate, TerraClimate PDSI standardised (scripts/drought_ensemble.py)")
    meta = [
        dict(id="drought_ensemble_mean", label="Drought index, ensemble mean", units="standardised (SD units; <0 dry)",
             source=ens_src, source_url="https://spei.csic.es/", aggregation="mean of >=3 available member indices",
             higher_is="better", notes="Mean of standardised 3-month drought indices from independent rainfall inputs "
             "(satellite IMERG, gauge-blended CHIRPS, reanalysis-driven TerraClimate). <-1 moderate, <-1.5 severe drought. "
             "Members use different baselines (TerraClimate/CHIRPS 1991-2020; IMERG SPEI 2000-2026). " + corr_txt, **common),
        dict(id="drought_ensemble_spread", label="Drought uncertainty (ensemble spread)", units="SD across members",
             source=ens_src, source_url="https://spei.csic.es/", aggregation="sample standard deviation across members",
             higher_is="worse", notes="How much the drought indices disagree. <0.5: inputs agree; >1: the sign or "
             "severity of the anomaly depends on which rainfall product you trust (typical in the Sudd and Upper Nile, "
             "where there are almost no rain gauges). " + corr_txt, **common),
        dict(id="drought_ensemble_range", label="Drought index range (max - min of members)", units="SD units",
             source=ens_src, source_url="https://spei.csic.es/", aggregation="max - min across members",
             higher_is="worse", notes="Alternative uncertainty measure to the spread.", **common),
        dict(id="drought_ensemble_agree", label="Drought index sign agreement", units="share of members (0-1)",
             source=ens_src, source_url="https://spei.csic.es/", aggregation="share of members with same sign as mean",
             higher_is="neutral", notes="1 = all members agree whether the county is drier or wetter than normal.", **common),
        dict(id="dr_spi3_chirps", label="SPI-3 (CHIRPS rainfall)", units="standardised", source="CHIRPS v3.0 monthly, UCSB CHC",
             source_url="https://data.chc.ucsb.edu/products/CHIRPS/v3.0/", aggregation="county-mean rainfall, 3-month sum, gamma SPI vs 1991-2020",
             higher_is="better", notes="Gamma distribution with zero-rain probability per county and calendar month; "
             "dry-season months with near-zero rain give unstable SPI (bounded to +-3.09).", **common),
        dict(id="dr_spei3_tc", label="SPEI-3 (TerraClimate)", units="standardised", source="TerraClimate v1.1 ppt and PET (Penman-Monteith)",
             source_url="https://www.climatologylab.org/terraclimate.html",
             aggregation="county-mean P-PET, 3-month sum, log-logistic SPEI vs 1991-2020", higher_is="better",
             notes="TerraClimate precipitation is ~40% below IMERG in 2018-2025 and its recent years are anomalously dry "
             "relative to 1991-2020 (it inherits ERA5/CRU trends), so this member is biased toward drought.", **common),
        dict(id="dr_pdsi_tc_z", label="PDSI, re-standardised (TerraClimate)", units="standardised", source="TerraClimate v1.1 PDSI",
             source_url="https://www.climatologylab.org/terraclimate.html",
             aggregation="county-mean PDSI, z-score vs the county's 1991-2020 values for the same calendar month",
             higher_is="better", notes="PDSI has long memory (~9-12 months) so it lags SPI/SPEI-3; it shares the "
             "TerraClimate precipitation with dr_spei3_tc, so these two members are not independent.", **common),
    ]
    META.write_text(json.dumps(meta, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
    from trend_stats import write_trends
    write_trends("drought_ensemble")  # Mann-Kendall + Sen's slope (scripts/trend_stats.py)
