"""Trend statistics shared by every data pipeline: Mann-Kendall test and Sen's slope.

Formulas
--------
Mann-Kendall (MK), for a series x_1..x_n ordered in time:
    S      = sum_{i<j} sign(x_j - x_i)
    Var(S) = [n(n-1)(2n+5) - sum_t t(t-1)(2t+5)] / 18        (t = size of each group of tied values)
    Z      = (S - 1)/sqrt(Var S) if S > 0;  0 if S = 0;  (S + 1)/sqrt(Var S) if S < 0   (continuity correction)
    p      = 2 * (1 - Phi(|Z|))                                  (two-sided)
    tau    = S / (n(n-1)/2)                                      (Kendall's tau-a)

Seasonal Kendall (Hirsch, Slack & Smith 1982), used for MONTHLY series so the wet/dry seasonal cycle is not
mistaken for a trend: compute S_g and Var(S_g) separately for each calendar month g (comparing only the same
month across years), then S = sum_g S_g, Var S = sum_g Var S_g, and Z, p as above.

Sen's slope (Sen 1968): median over all pairs i<j of (x_j - x_i) / (t_j - t_i), with t in years.
Seasonal Sen's slope: the same median, taken over pairs within the same calendar month only.

Also reported: lag-1 autocorrelation of the (deseasonalised) series, because positive autocorrelation makes MK
p-values too optimistic, and Benjamini-Hochberg FDR q-values across the 79 counties of each variable.

Usage from a pipeline (after it has written its contract CSV):
    from trend_stats import write_trends
    write_trends("acled")            # reads data/processed/acled_county_monthly.csv + meta, writes trends
"""
from __future__ import annotations

import glob
import json
import math
import os
from typing import Iterable

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(ROOT, "data", "processed")
TREND_DIR = os.path.join(PROC, "trends")
WINDOW = ("2018-01-01", "2025-12-01")
ALPHA = 0.05


# ----------------------------------------------------------------------------- core formulas
def _phi(z: float) -> float:
    """Standard normal CDF."""
    return 0.5 * math.erfc(-z / math.sqrt(2))


def mk_s_var(x: np.ndarray) -> tuple[float, float]:
    """Mann-Kendall S statistic and its tie-corrected variance."""
    x = np.asarray(x, float)
    n = len(x)
    if n < 2:
        return 0.0, 0.0
    d = np.sign(x[None, :] - x[:, None])
    s = float(np.triu(d, 1).sum())
    _, counts = np.unique(x, return_counts=True)
    ties = counts[counts > 1]
    var = (n * (n - 1) * (2 * n + 5) - float(np.sum(ties * (ties - 1) * (2 * ties + 5)))) / 18.0
    return s, var


def mk_z_p(s: float, var: float) -> tuple[float, float]:
    """Z score with continuity correction and two-sided p-value."""
    if var <= 0:
        return 0.0, 1.0
    z = (s - 1) / math.sqrt(var) if s > 0 else (s + 1) / math.sqrt(var) if s < 0 else 0.0
    return z, 2 * (1 - _phi(abs(z)))


def mann_kendall(x: Iterable[float]) -> dict:
    """Classic Mann-Kendall test on a time-ordered series (NaNs dropped)."""
    x = np.asarray([v for v in x if v is not None and np.isfinite(v)], float)
    n = len(x)
    s, var = mk_s_var(x)
    z, p = mk_z_p(s, var)
    tau = s / (n * (n - 1) / 2) if n > 1 else np.nan
    return {"n": n, "S": s, "var_S": var, "Z": z, "p": p, "tau": tau}


def seasonal_kendall(t_years: np.ndarray, x: np.ndarray, season: np.ndarray) -> dict:
    """Seasonal Kendall test: MK within each season (calendar month), summed."""
    s_tot = var_tot = 0.0
    n = pairs = 0
    for g in np.unique(season):
        m = (season == g) & np.isfinite(x)
        xs = x[m][np.argsort(t_years[m])]
        if len(xs) < 2:
            continue
        s, var = mk_s_var(xs)
        s_tot += s
        var_tot += var
        n += len(xs)
        pairs += len(xs) * (len(xs) - 1) / 2
    z, p = mk_z_p(s_tot, var_tot)
    return {"n": n, "S": s_tot, "var_S": var_tot, "Z": z, "p": p, "tau": s_tot / pairs if pairs else np.nan}


def sens_slope(t_years: np.ndarray, x: np.ndarray) -> float:
    """Sen's slope: median of pairwise slopes, in units of x per year."""
    m = np.isfinite(x)
    t, x = np.asarray(t_years, float)[m], np.asarray(x, float)[m]
    if len(x) < 2:
        return np.nan
    i, j = np.triu_indices(len(x), 1)
    dt = t[j] - t[i]
    ok = dt != 0
    return float(np.median((x[j] - x[i])[ok] / dt[ok])) if ok.any() else np.nan


def seasonal_sens_slope(t_years: np.ndarray, x: np.ndarray, season: np.ndarray) -> float:
    """Seasonal Sen's slope: median of pairwise slopes taken within each season only."""
    slopes = []
    for g in np.unique(season):
        m = (season == g) & np.isfinite(x)
        t, xs = t_years[m], x[m]
        if len(xs) < 2:
            continue
        i, j = np.triu_indices(len(xs), 1)
        dt = t[j] - t[i]
        ok = dt != 0
        slopes.append((xs[j] - xs[i])[ok] / dt[ok])
    return float(np.median(np.concatenate(slopes))) if slopes else np.nan


def lag1_autocorr(x: np.ndarray) -> float:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) < 4 or np.std(x[:-1]) == 0 or np.std(x[1:]) == 0:
        return np.nan
    return float(np.corrcoef(x[:-1], x[1:])[0, 1])


def bh_fdr(p: Iterable[float]) -> np.ndarray:
    """Benjamini-Hochberg false-discovery-rate adjusted q-values (NaNs preserved)."""
    p = np.asarray(list(p), float)
    q = np.full_like(p, np.nan)
    ok = np.isfinite(p)
    if not ok.any():
        return q
    pv = p[ok]
    order = np.argsort(pv)
    ranked = pv[order] * len(pv) / (np.arange(len(pv)) + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty_like(pv)
    out[order] = np.minimum(ranked, 1.0)
    q[ok] = out
    return q


# ----------------------------------------------------------------------------- per-series wrapper
def trend_for_series(dates: pd.Series, values: pd.Series, temporal: str = "monthly", baseline_year: int | None = None) -> dict:
    """Run the appropriate test for one county-variable series.

    monthly  -> Seasonal Kendall + seasonal Sen's slope (needs >= 3 years with data)
    annual / periodic / round -> Mann-Kendall + Sen's slope on the observed points
    static   -> not tested
    """
    d = pd.to_datetime(pd.Series(dates).reset_index(drop=True))
    x = pd.to_numeric(pd.Series(values).reset_index(drop=True), errors="coerce").to_numpy(float)
    keep = np.isfinite(x)
    d, x = d[keep].reset_index(drop=True), x[keep]
    res = {"test": None, "n": int(len(x)), "S": np.nan, "Z": np.nan, "p": np.nan, "tau": np.nan,
           "sen_slope_per_year": np.nan, "lag1": np.nan, "baseline_mean": np.nan}
    if temporal == "static" or len(x) < 4:
        return res
    t = (d.dt.year + (d.dt.month - 1) / 12.0).to_numpy(float)
    years = d.dt.year.nunique()
    if temporal == "monthly" and years >= 3 and len(x) >= 24:
        season = d.dt.month.to_numpy()
        r = seasonal_kendall(t, x, season)
        res.update(test="seasonal Mann-Kendall", sen_slope_per_year=seasonal_sens_slope(t, x, season))
        clim = pd.Series(x).groupby(season).transform("mean").to_numpy()
        res["lag1"] = lag1_autocorr(x - clim)
    else:
        if years < 3 and len(x) < 4:
            return res
        r = mann_kendall(x[np.argsort(t)])
        res.update(test="Mann-Kendall", sen_slope_per_year=sens_slope(t, x))
        res["lag1"] = lag1_autocorr(x[np.argsort(t)])
    res.update({k: r[k] for k in ("n", "S", "Z", "p", "tau")})
    by = baseline_year or int(d.dt.year.min())
    base = x[(d.dt.year == by).to_numpy()]
    res["baseline_mean"] = float(np.mean(base)) if len(base) else np.nan
    return res


def interpret(row: dict, meta: dict) -> str:
    """One plain-language sentence for the map hover."""
    p, slope, q = row.get("p"), row.get("sen_slope_per_year"), row.get("q_fdr")
    if row.get("test") is None or p is None or not np.isfinite(p):
        return "Too few observations for a trend test."
    units = meta.get("units") or ""
    pct = row.get("sen_slope_pct_per_year")
    ratio_ok = meta.get("index_ok", True) is not False and not str(meta.get("units", "")).strip().startswith(("°", "deg"))
    pct_txt = f" ({pct:+.1f}% of the {meta.get('baseline_year', 'baseline')} level per year)" if ratio_ok and pct is not None and np.isfinite(pct) else ""
    fmt = lambda v: f"{v:+.3g}"
    ptxt = ("p < 0.001" if p < 0.001 else f"p = {p:.3f}") + (f", FDR q = {q:.3f}" if q is not None and np.isfinite(q) else "")
    sig = q is not None and np.isfinite(q) and q < ALPHA      # significance = FDR-adjusted across the 79 counties
    lag = row.get("lag1")
    ac = " Strong month-to-month persistence (lag-1 r > 0.5) may still overstate significance." if lag is not None and np.isfinite(lag) and lag > 0.5 else ""
    if sig and np.isfinite(slope) and slope != 0:
        direction = "rising" if slope > 0 else "falling"
        hi = meta.get("higher_is", "neutral")
        judge = "" if hi == "neutral" else (" — improving" if (slope > 0) == (hi == "better") else " — worsening")
        return (f"Significant {direction} trend over 2018–2025 ({row['test']}, {ptxt}): "
                f"about {fmt(slope)} {units} per year{pct_txt}{judge}.{ac}")
    if sig:
        return f"Significant monotonic trend ({row['test']}, {ptxt}), but the median slope is ~0 (many tied values).{ac}"
    weak = " (nominal p < 0.05, but not significant after correcting for testing 79 counties)" if p < ALPHA else ""
    return f"No significant monotonic trend over 2018–2025 ({row['test']}, {ptxt}){weak}; Sen's slope {fmt(slope) if np.isfinite(slope) else 'n/a'} {units}/yr."


# ----------------------------------------------------------------------------- pipeline hook
def _load_meta() -> dict:
    meta = {}
    for f in glob.glob(os.path.join(PROC, "meta", "*.json")):
        if f.endswith("points.json"):
            continue
        try:
            items = json.load(open(f))
        except Exception:  # noqa: BLE001
            continue
        for it in items if isinstance(items, list) else items.get("variables", [items]):
            if "id" in it:
                meta[it["id"]] = it
    return meta


def compute_trends(df: pd.DataFrame, meta: dict | None = None, window: tuple[str, str] = WINDOW) -> pd.DataFrame:
    """Trend table for a long contract DataFrame (county_id, date, variable, value)."""
    meta = meta if meta is not None else _load_meta()
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[(df["date"] >= window[0]) & (df["date"] <= window[1])].dropna(subset=["value"])
    rows = []
    for (var, cid), g in df.groupby(["variable", "county_id"], sort=False):
        m = meta.get(var, {})
        temporal = m.get("temporal", "monthly")
        g = g.groupby("date", as_index=False)["value"].mean().sort_values("date")
        by = m.get("baseline_year_override") or (2018 if (g["date"].dt.year == 2018).any() else int(g["date"].dt.year.min()))
        r = trend_for_series(g["date"], g["value"], temporal, by)
        r.update(variable=var, county_id=cid, baseline_year=by)
        b = r["baseline_mean"]
        r["sen_slope_pct_per_year"] = 100 * r["sen_slope_per_year"] / abs(b) if np.isfinite(b) and abs(b) > 1e-9 else np.nan
        rows.append(r)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["q_fdr"] = out.groupby("variable")["p"].transform(lambda s: pd.Series(bh_fdr(s), index=s.index))
    # significance uses Benjamini-Hochberg FDR-adjusted q (controls false positives across the 79 counties)
    out["significant"] = out["q_fdr"] < ALPHA
    out["interpretation"] = [interpret(r, {**meta.get(r["variable"], {}), "baseline_year": r["baseline_year"]})
                             for r in out.to_dict("records")]
    cols = ["county_id", "variable", "test", "n", "S", "Z", "tau", "p", "q_fdr", "significant", "sen_slope_per_year",
            "sen_slope_pct_per_year", "baseline_year", "baseline_mean", "lag1", "interpretation"]
    return out[cols]


def write_trends(source: str) -> str | None:
    """Compute and save trends for one processed source.

    `source` is a file stem in data/processed ("acled" -> acled_county_monthly.csv, or a full stem such as
    "landcover_county_annual"). Writes data/processed/trends/<stem>_trends.csv and returns its path.
    """
    cands = [os.path.join(PROC, f"{source}.csv"), os.path.join(PROC, f"{source}_county_monthly.csv")]
    path = next((c for c in cands if os.path.exists(c)), None)
    if path is None:
        print(f"[trend_stats] no processed file for '{source}'")
        return None
    df = pd.read_csv(path, dtype={"county_id": str})
    if not {"county_id", "date", "variable", "value"} <= set(df.columns):
        print(f"[trend_stats] {os.path.basename(path)} is not in long contract format; skipped")
        return None
    tr = compute_trends(df)
    os.makedirs(TREND_DIR, exist_ok=True)
    out = os.path.join(TREND_DIR, os.path.basename(path).replace(".csv", "_trends.csv"))
    tr.to_csv(out, index=False, float_format="%.6g")
    n_sig = int(tr["significant"].sum()) if len(tr) else 0
    print(f"[trend_stats] {os.path.basename(out)}: {len(tr)} county-variables, {n_sig} significant at FDR q<{ALPHA}")
    return out


if __name__ == "__main__":
    # Recompute trends for every processed source (python scripts/trend_stats.py)
    for f in sorted(glob.glob(os.path.join(PROC, "*.csv"))):
        write_trends(os.path.basename(f)[:-4])
