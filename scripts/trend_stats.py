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

Persistence (serial correlation) corrections — positive autocorrelation makes the plain MK variance too small and
p-values too optimistic, so the p-value used for significance is corrected:
  * MONTHLY series -> Hirsch & Slack (1984) correlated seasonal Kendall: the 12 monthly S_g statistics are not
    independent (a wet year is wet in Jul, Aug and Sep), so Var(S) adds their covariances:
        Var(S) = sum_g Var(S_g) + 2 * sum_{g<h} Cov(S_g, S_h)
        Cov(S_g, S_h) = [K_gh + 4 * sum_j R_jg R_jh - n(n+1)^2] / 3            (Dietz & Killeen 1981)
        K_gh = sum_{i<j} sign((x_jg - x_ig)(x_jh - x_ih)),  R_jg = rank of year j within month g, n = years
  * ANNUAL / SURVEY-ROUND series (n >= 10) -> Hamed & Rao (1998) variance correction:
        detrend with Sen's slope, take ranks, compute their autocorrelation r_k; keep lags with |r_k| > 1.96/sqrt(n)
        n/n* = 1 + 2/(n(n-1)(n-2)) * sum_k (n-k)(n-k-1)(n-k-2) r_k ;   Var*(S) = Var(S) * n/n*
    (n < 10: too short to estimate autocorrelation; the plain MK p is used and flagged.)
The uncorrected p is kept as p_naive for transparency.

Multiple testing across counties: Benjamini-Hochberg FDR q-values across the 79 counties of each variable. Wilks (2016)
shows BH also controls "field significance" for spatially correlated fields; we use q < 0.05 (conservative).

Spatial structure of the trend map (geospatial statistics, PySAL/esda, Queen contiguity between counties):
  * Global Moran's I of the counties' Sen's slopes (permutation p, 999 draws): are trends spatially clustered?
  * Local Moran's I (LISA; Anselin 1995) per county: High-High = part of a cluster of strongly rising (or least
    falling) counties, Low-Low = cluster of strongly falling counties, High-Low / Low-High = local outliers;
    only reported where the permutation p < 0.05.

Regional trend test (Douglas, Vogel & Kroll 2000 "regional Kendall" with spatially-preserving bootstrap):
    S_R = sum over counties c and months g of S_cg   (pooled seasonal Kendall statistic for a region)
  Null distribution: resample whole YEARS with replacement, applied identically to every county and month, and
  recompute S_R (999 draws). Resampling years jointly keeps the cross-county (spatial) correlation and the
  within-year seasonal correlation, which is what makes the test honest for spatially coherent fields. Reported for
  all counties ("national") and for the 16 Sudd counties, with the median county Sen's slope.

Lag-1 autocorrelation of the (deseasonalised) series is also reported.

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


def _sign0(a):
    """sign() that treats NaN (missing year) as 0 = no information."""
    a = np.sign(a)
    return np.where(np.isnan(a), 0.0, a)


def hirsch_slack(t_years: np.ndarray, x: np.ndarray, season: np.ndarray) -> dict:
    """Correlated seasonal Kendall test (Hirsch & Slack 1984; covariance per Dietz & Killeen 1981).

    Builds a years x seasons matrix (NaN where missing). Variance = sum of per-season tie-corrected variances plus
    twice the sum of between-season covariances.
    """
    yrs = np.floor(t_years).astype(int)
    years, seasons = np.unique(yrs), np.unique(season)
    n = len(years)
    M = np.full((n, len(seasons)), np.nan)
    yi = {y: i for i, y in enumerate(years)}
    si = {g: j for j, g in enumerate(seasons)}
    for y, g, v in zip(yrs, season, x):
        if np.isfinite(v):
            M[yi[y], si[g]] = v
    S, var_diag = 0.0, 0.0
    R = np.zeros_like(M)
    for j in range(M.shape[1]):
        col = M[:, j]
        ok = np.isfinite(col)
        if ok.sum() >= 2:
            s_g, v_g = mk_s_var(col[ok])
            S += s_g
            var_diag += v_g
        # ranks within the season; missing years get the mid rank (n+1)/2
        R[:, j] = (n + 1 + np.nansum(_sign0(col[:, None] - col[None, :]), axis=1)) / 2
        R[~ok, j] = (n + 1) / 2
    cov = 0.0
    for g in range(M.shape[1]):
        for h in range(g + 1, M.shape[1]):
            a, b = M[:, g], M[:, h]
            K = np.triu(_sign0((a[None, :] - a[:, None]) * (b[None, :] - b[:, None])), 1).sum()
            cov += (K + 4 * np.sum(R[:, g] * R[:, h]) - n * (n + 1) ** 2) / 3.0
    var = var_diag + 2 * cov
    if var <= 0:          # can happen with heavy ties / short records; fall back to independent seasons
        var = var_diag
    z, p = mk_z_p(S, var)
    pairs = sum(np.isfinite(M[:, j]).sum() * (np.isfinite(M[:, j]).sum() - 1) / 2 for j in range(M.shape[1]))
    return {"n": int(np.isfinite(M).sum()), "S": S, "var_S": var, "Z": z, "p": p, "tau": S / pairs if pairs else np.nan}


def hamed_rao(t_years: np.ndarray, x: np.ndarray, alpha: float = 0.05) -> dict:
    """Mann-Kendall with Hamed & Rao (1998) variance correction for serial correlation."""
    order = np.argsort(t_years)
    t, x = np.asarray(t_years, float)[order], np.asarray(x, float)[order]
    n = len(x)
    base = mann_kendall(x)
    if n < 10:
        base["n_eff_factor"] = np.nan
        return base
    idx = np.arange(1, n + 1, dtype=float)                    # equally spaced index, as in Hamed & Rao
    slope = sens_slope(idx, x)
    detr = x - slope * idx
    ranks = pd.Series(detr).rank().to_numpy()
    r = ranks - ranks.mean()
    denom = np.sum(r * r)
    acf = np.array([np.sum(r[:-k] * r[k:]) / denom for k in range(1, n)]) if denom > 0 else np.zeros(n - 1)
    crit = 1.959963984540054 / np.sqrt(n) if abs(alpha - 0.05) < 1e-12 else _zcrit(alpha) / np.sqrt(n)
    ks = np.arange(1, n)
    sig = np.abs(acf) > crit
    factor = 1 + 2.0 / (n * (n - 1) * (n - 2)) * np.sum(((n - ks) * (n - ks - 1) * (n - ks - 2) * acf)[sig])
    var = base["var_S"] * factor
    z, p = mk_z_p(base["S"], var)
    return {**base, "var_S": var, "Z": z, "p": p, "n_eff_factor": factor}


def _zcrit(alpha: float) -> float:
    from statistics import NormalDist
    return NormalDist().inv_cdf(1 - alpha / 2)


# ----------------------------------------------------------------------------- robustness checks (added 16 Nov 2026)
CI_LEVEL = 0.90          # two-sided confidence level of the slope range
N_BOOT = 500             # block-bootstrap draws for the anchored (vs-2018) slope
STEP_DBIC = 10.0          # BIC gain needed to call a change "mostly a step" (Kass & Raftery: > 10 = very strong)


def sen_ci_gilbert(t: np.ndarray, x: np.ndarray, var_s: float, level: float = CI_LEVEL) -> tuple[float, float]:
    """Rank-based confidence interval of Sen's slope (Sen 1968; Gilbert 1987 §16.5; Hollander & Wolfe).

    C = z_{(1+level)/2} * sqrt(Var S);  M1 = (N - C)/2,  M2 = (N + C)/2  (N = number of pairwise slopes)
    lower = M1-th, upper = (M2+1)-th smallest pairwise slope. Var S may be the persistence-corrected variance.
    """
    m = np.isfinite(x)
    t, x = np.asarray(t, float)[m], np.asarray(x, float)[m]
    if len(x) < 3 or not np.isfinite(var_s) or var_s <= 0:
        return np.nan, np.nan
    i, j = np.triu_indices(len(x), 1)
    dt = t[j] - t[i]
    ok = dt != 0
    sl = np.sort((x[j] - x[i])[ok] / dt[ok])
    N = len(sl)
    C = _zcrit(1 - level) * math.sqrt(var_s)
    lo, hi = int(round((N - C) / 2)) - 1, int(round((N + C) / 2))
    if lo < 0 or hi > N - 1:
        return np.nan, np.nan            # too few pairs for this confidence level: no finite range
    return float(sl[lo]), float(sl[hi])


def _anchored_matrix(Y: np.ndarray, pos: np.ndarray, bpos: np.ndarray, k: np.ndarray) -> np.ndarray:
    """Vectorised anchored_month_slope for rows of Y (draws x months): median of (Y[pos]-Y[bpos])/k, both-zero skipped."""
    a, b = Y[:, pos], Y[:, bpos]
    s = (a - b) / k
    s[(a == 0) & (b == 0)] = np.nan
    with np.errstate(all="ignore"):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return np.nanmedian(s, axis=1)


def anchored_block_ci(d: pd.Series, x: np.ndarray, base_year: int, b_fit: float, theta: float,
                      level: float = CI_LEVEL, n_boot: int = N_BOOT, seed: int = 20181, block: int = 12,
                      inflate: bool = True, small_t: bool = True) -> tuple[float, float]:
    """Moving-block bootstrap range for the anchored (vs same month of the baseline year) slope.

    Model: x[y,m] = c_m + b_fit*(y - base) + e, with b_fit the seasonal Sen's slope and c_m robust month levels.
    The residual series e is resampled in moving blocks of 12 consecutive months (Kuensch 1989), which keeps the
    month-to-month persistence and the within-year correlation, the baseline year's noise included. The anchored slope
    is recomputed on each synthetic series; the basic (pivot) interval is theta - (q_hi - b0), theta - (q_lo - b0),
    where b0 is the anchored slope of the noise-free fit. Non-negative variables are floored at 0.
    """
    if not np.isfinite(b_fit) or not np.isfinite(theta):
        return np.nan, np.nan
    ym = (d.dt.year * 12 + d.dt.month - 1).to_numpy()
    start = int(ym.min())
    L = int(ym.max()) - start + 1
    if L < 24:
        return np.nan, np.nan
    X = np.full(L, np.nan)
    X[ym - start] = x
    idx = start + np.arange(L)
    mon, yr = idx % 12, idx // 12
    k = (yr - base_year).astype(float)
    c = np.full(12, np.nan)
    for g in range(12):
        v = X[mon == g] - b_fit * k[mon == g]
        if np.isfinite(v).any():
            c[g] = np.nanmedian(v)
    fit = c[mon] + b_fit * k
    res = X - fit
    if inflate:                          # residuals from a fitted model are too small: scale by sqrt(n/(n - params))
        n_ok = int(np.isfinite(res).sum())
        n_par = int(np.isfinite(c).sum()) + 1
        if n_ok > n_par + 5:
            res = res * math.sqrt(n_ok / (n_ok - n_par))
    # anchored pairs: every later month with the same calendar month of the baseline year
    bmap = {g: p for p, (g, y) in enumerate(zip(mon, yr)) if y == base_year and np.isfinite(X[p])}
    pos = np.array([p for p in range(L) if yr[p] > base_year and mon[p] in bmap and np.isfinite(X[p])], int)
    if len(pos) < 6:
        return np.nan, np.nan
    bpos = np.array([bmap[mon[p]] for p in pos], int)
    kk = k[pos]
    floor0 = np.nanmin(x) >= 0
    F = fit[None, :].copy()
    if floor0:
        F = np.maximum(F, 0)
    b0 = _anchored_matrix(F, pos, bpos, kk)[0]
    if not np.isfinite(b0):
        b0 = b_fit
    rng = np.random.default_rng(seed)
    nb = int(math.ceil(L / block))
    st = rng.integers(0, L - block + 1, size=(n_boot, nb))
    I = (st[:, :, None] + np.arange(block)).reshape(n_boot, -1)[:, :L]
    Y = fit[None, :] + res[I]
    if floor0:
        Y = np.maximum(Y, 0)
    th = _anchored_matrix(Y, pos, bpos, kk)
    th = th[np.isfinite(th)]
    if len(th) < n_boot // 2:
        return np.nan, np.nan
    q_lo, q_hi = np.quantile(th, [(1 - level) / 2, (1 + level) / 2])
    # small-sample widening: Student t with (years - 1) df instead of the normal quantile (8 years -> x1.15)
    from scipy.stats import t as _t
    ny = len(np.unique(yr[np.isfinite(X)]))
    f = float(_t.ppf((1 + level) / 2, max(ny - 1, 2)) / _zcrit(1 - level)) if small_t else 1.0
    return float(theta - f * (q_hi - b0)), float(theta + f * (b0 - q_lo))


def _acf1(x: np.ndarray) -> float:
    xm = x - x.mean()
    den = np.sum(xm * xm)
    return float(np.sum(xm[:-1] * xm[1:]) / den) if den > 0 else 0.0


def tfpw_mk(x: np.ndarray) -> dict:
    """Trend-free pre-whitening Mann-Kendall test (Yue, Pilon, Phinney & Cavadias 2002; as pymannkendall's
    trend_free_pre_whitening_modification_test). x is equally spaced, NaNs dropped.

    b = Sen's slope (per step); e = x - b*i; r1 = lag-1 autocorrelation of e; y_i = e_i - r1*e_{i-1} + b*i; MK on y.
    """
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 10:
        return {"p": np.nan, "r1": np.nan}
    i = np.arange(1, n + 1, dtype=float)
    b = sens_slope(i, x)
    e = x - b * i
    r1 = _acf1(e)
    y = e[1:] - r1 * e[:-1]
    y = y + np.arange(1, n, dtype=float) * b
    r = mann_kendall(y)
    return {"p": r["p"], "r1": r1}


def pettitt(x: np.ndarray) -> dict:
    """Pettitt (1979) change-point test. U_t = 2*sum_{i<=t} r_i - t(n+1) (ranks r), K = max|U_t|,
    p ~= 2*exp(-6K^2/(n^3+n^2)). Returns the index of the first value after the most likely break."""
    x = np.asarray(x, float)
    n = len(x)
    if n < 10:
        return {"p": np.nan, "cp": None, "K": np.nan}
    r = pd.Series(x).rank().to_numpy()
    U = 2 * np.cumsum(r)[:-1] - np.arange(1, n) * (n + 1)
    t = int(np.argmax(np.abs(U)))
    K = float(abs(U[t]))
    return {"p": float(min(1.0, 2 * math.exp(-6 * K * K / (n ** 3 + n ** 2)))), "cp": t + 1, "K": K}


def step_vs_line(a: np.ndarray, cp: int) -> float:
    """BIC(straight line) - BIC(one step at cp) on the series a; > 0 favours the step. Step has 3 parameters
    (two levels + break), line 2. Large positive values mean the change looks like a jump, not a steady drift."""
    a = np.asarray(a, float)
    n = len(a)
    if cp is None or cp < 3 or n - cp < 3:
        return np.nan
    i = np.arange(n, dtype=float)
    sse_line = float(np.sum((a - np.polyval(np.polyfit(i, a, 1), i)) ** 2))
    sse_step = float(np.sum((a[:cp] - a[:cp].mean()) ** 2) + np.sum((a[cp:] - a[cp:].mean()) ** 2))
    if sse_line <= 0 or sse_step <= 0:
        return np.nan
    return float(n * math.log(sse_line / n) + 2 * math.log(n) - (n * math.log(sse_step / n) + 3 * math.log(n)))


def spatial_clusters(slopes: pd.Series, permutations: int = 999, seed: int = 12345) -> tuple[dict, pd.DataFrame]:
    """Global Moran's I and Local Moran's I (LISA) of county trend values (Queen contiguity).

    `slopes` is indexed by county_id. Returns ({"I", "p"}, DataFrame[county_id, lisa, lisa_p]).
    """
    import geopandas as gpd
    from esda.moran import Moran, Moran_Local
    from libpysal.weights import Queen
    global _COUNTIES
    try:
        _COUNTIES
    except NameError:
        _COUNTIES = gpd.read_file(os.path.join(ROOT, "data", "counties.geojson"))[["district_id", "geometry"]]
    s = slopes.dropna()
    g = _COUNTIES[_COUNTIES.district_id.isin(s.index)].reset_index(drop=True)
    if len(g) < 8 or np.nanstd(s.values) == 0:
        return {"I": np.nan, "p": np.nan}, pd.DataFrame(columns=["county_id", "lisa", "lisa_p"])
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        w = Queen.from_dataframe(g, use_index=False)
        w.transform = "r"
        y = s.reindex(g.district_id).to_numpy(float)
        gm = Moran(y, w, permutations=permutations)
        lm = Moran_Local(y, w, permutations=permutations, seed=seed)
    labels = {1: "HH", 2: "LH", 3: "LL", 4: "HL"}
    lisa = [labels[q] if p < ALPHA else "ns" for q, p in zip(lm.q, lm.p_sim)]
    return ({"I": float(gm.I), "p": float(gm.p_sim)},
            pd.DataFrame({"county_id": g.district_id, "lisa": lisa, "lisa_p": lm.p_sim}))


SUDD_NAMES = ["Panyijiar", "Mayendit", "Leer", "Guit", "Fangak", "Ayod", "Canal/Pigi", "Duk", "Twic East", "Bor South",
              "Yirol East", "Awerial", "Rubkona", "Koch", "Nyirol", "Uror"]


def regional_kendall(df: pd.DataFrame, county_ids: list, monthly: bool = True, n_boot: int = 999, seed: int = 7) -> dict:
    """Regional (multi-site) seasonal Kendall test with a year-block bootstrap (Douglas et al. 2000).

    df: long rows (county_id, date, value) for ONE variable. Returns S_R, bootstrap p, counties used.
    """
    d = df[df["county_id"].isin(county_ids)].copy()
    d["date"] = pd.to_datetime(d["date"])
    d["y"], d["m"] = d["date"].dt.year, (d["date"].dt.month if monthly else 1)
    years = np.sort(d["y"].unique())
    cids = np.sort(d["county_id"].unique())
    if len(years) < 4 or len(cids) < 3:
        return {"S": np.nan, "p": np.nan, "n_counties": len(cids)}
    months = np.sort(d["m"].unique())
    X = np.full((len(cids), len(years), len(months)), np.nan)
    ci = {c: i for i, c in enumerate(cids)}; yi = {y: i for i, y in enumerate(years)}; mi = {m: i for i, m in enumerate(months)}
    g = d.groupby(["county_id", "y", "m"])["value"].mean()
    for (c, y, m), v in g.items():
        X[ci[c], yi[y], mi[m]] = v

    def S_of(order):
        Y = X[:, order, :]
        tot = 0.0
        for i in range(len(order) - 1):
            diff = Y[:, i + 1:, :] - Y[:, i:i + 1, :]
            tot += np.nansum(np.sign(diff))
        return tot

    S = S_of(np.arange(len(years)))
    rng = np.random.default_rng(seed)
    null = np.array([S_of(rng.integers(0, len(years), len(years))) for _ in range(n_boot)])
    p = (1 + np.sum(np.abs(null) >= abs(S))) / (n_boot + 1)
    return {"S": float(S), "p": float(p), "n_counties": int(len(cids))}


def regional_trends(df: pd.DataFrame, meta: dict, trends: pd.DataFrame) -> pd.DataFrame:
    """Regional Kendall results for all counties and for the Sudd, per variable."""
    import geopandas as gpd
    cty = gpd.read_file(os.path.join(ROOT, "data", "counties.geojson"))
    regions = {"national": cty.district_id.tolist(), "sudd": cty[cty.name.isin(SUDD_NAMES)].district_id.tolist()}
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[(df["date"] >= WINDOW[0]) & (df["date"] <= WINDOW[1])].dropna(subset=["value"])
    rows = []
    for var, g in df.groupby("variable"):
        m = meta.get(var, {})
        if m.get("temporal") == "static" or g["county_id"].nunique() < 3:
            continue
        monthly = m.get("temporal", "monthly") == "monthly"
        tv = trends[trends["variable"] == var]
        for reg, ids in regions.items():
            r = regional_kendall(g, ids, monthly=monthly)
            sub = tv[tv["county_id"].isin(ids)]
            rows.append({"variable": var, "region": reg, "S": r["S"], "p_boot": r["p"], "n_counties": r["n_counties"],
                         "median_sen_pct_per_year": sub["sen_slope_pct_per_year"].median(),
                         "median_sen_per_year": sub["sen_slope_per_year"].median()})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- display basis (seasonal-aware slopes)
WATER_SEASON = (6, 7, 8, 9)          # Jun–Sep: main rains (rainfall, ET, soil moisture)
FLOOD_SEASON = (8, 9, 10, 11)        # Aug–Nov: flood peak (surface water, inundation, flooded area)
_RE = __import__("re")
_LAB = None


def _labels():
    global _LAB
    if _LAB is None:
        f = os.path.join(ROOT, "data", "variable_labels.json")
        _LAB = json.load(open(f)) if os.path.exists(f) else {}
    return _LAB


def direction_of(var: str, meta: dict) -> str:
    """Plain direction words for a variable: wetter_drier, warmer_cooler, greener_browner, more_less or better_worse."""
    d = (_labels().get(var) or {}).get("direction") or meta.get("direction")
    if d:
        return d
    v = var.lower()
    if _RE.search(r"precip|ppt|chirps|rain|spei|spi|pdsi|drought|soil|soilwet|smap|surface_water|flood|inundat|sudd_|openwater|grace|gwsa|tws|aet|\bq\b|tc_q|runoff|wet|\bdef\b|tc_def|extreme_dry|extreme_wet", v):
        return "wetter_drier"
    if _RE.search(r"tmax|tmin|tair|lst|t2m|temp|heat|hottest", v):
        return "warmer_cooler"
    if _RE.search(r"ndvi|evi|vegetation", v):
        return "greener_browner"
    return "better_worse" if meta.get("higher_is") in ("better", "worse") else "more_less"


def basis_of(var: str, meta: dict, x: np.ndarray) -> str:
    """Which yearly value the headline slope is based on."""
    v = var.lower()
    if meta.get("temporal", "monthly") != "monthly":
        return "observed"
    if _RE.search(r"surface_water|flood|inundat|openwater|sudd_", v):
        return "flood_season"
    if _RE.search(r"precip|ppt|chirps|rain|_et_|et_mm|aet|soil|smap|runoff|tc_q", v):
        return "wet_season"
    unit = str(meta.get("units", "")).lower()
    zeros = np.mean(x == 0) if len(x) else 0
    if zeros > 0.4 or _RE.search(r"\b(events?|people|deaths|fatalities|incidents|detections|individuals|movements)\b", unit):
        return "annual_total"
    return "seasonal"


def pct_meaningful(var: str, meta: dict, sparse: bool) -> bool:
    txt = f"{meta.get('units', '')} {var}"
    return meta.get("index_ok", True) is not False and not sparse and \
        not _RE.search(r"%|standard|flag|index|\bsd\b|°|deg|class|share|fraction|anomal|spei|spi|pdsi|drought", txt, _RE.I)


def yearly_values(d: pd.Series, x: np.ndarray, basis: str):
    """Collapse a monthly series to one value per year according to the basis (complete seasons/years only)."""
    df = pd.DataFrame({"y": d.dt.year.to_numpy(), "m": d.dt.month.to_numpy(), "x": x})
    if basis == "wet_season":
        g = df[df.m.isin(WATER_SEASON)].groupby("y")
        return g.x.sum()[g.x.count() == len(WATER_SEASON)]
    if basis == "flood_season":
        g = df[df.m.isin(FLOOD_SEASON)].groupby("y")
        return g.x.mean()[g.x.count() >= 3]
    if basis == "annual_total":
        g = df.groupby("y")
        return g.x.sum()[g.x.count() >= 10]
    return None


BASIS_TEXT = {"wet_season": "Jun–Sep wet-season total", "flood_season": "Aug–Nov flood-season average",
              "annual_total": "annual total", "seasonal": "same-month comparisons", "observed": "observed values"}


def anchored_month_slope(d: pd.Series, x: np.ndarray, base_year: int, upto: int | None = None):
    """Seasonality-controlled slope anchored on the baseline year (default 2018).

    For every month (y, m) after the baseline year, compare it with the SAME calendar month of the baseline year:
        slope_ym = (x[y,m] - x[base,m]) / (y - base)            (units per year)
        pct_ym   = 100 * (x[y,m] - x[base,m]) / |x[base,m]| / (y - base)   (% of that month's baseline value per year)
    Headline = median over all (y, m). Pairs where both values are 0 (e.g. dry-season rain, months with no events)
    carry no information and are skipped, so they cannot drag the median to zero.
    """
    yy, mm = d.dt.year.to_numpy(), d.dt.month.to_numpy()
    base = {m: v for y, m, v in zip(yy, mm, x) if y == base_year and np.isfinite(v)}
    sl, pc = [], []
    for y, m, v in zip(yy, mm, x):
        if y <= base_year or (upto is not None and y > upto) or m not in base or not np.isfinite(v):
            continue
        b = base[m]
        if v == 0 and b == 0:
            continue
        k = y - base_year
        sl.append((v - b) / k)
        if abs(b) > 1e-9:
            pc.append(100 * (v - b) / abs(b) / k)
    return (float(np.median(sl)) if sl else np.nan), (float(np.median(pc)) if pc else np.nan), len(sl)


def display_slope(d: pd.Series, x: np.ndarray, basis: str, t: np.ndarray, season: np.ndarray):
    """Headline Sen's slope per year on the chosen basis, and the baseline (first-year) value for a % figure."""
    if basis in ("wet_season", "flood_season", "annual_total"):
        yv = yearly_values(d, x, basis)
        if len(yv) >= 3:
            return sens_slope(yv.index.to_numpy(float), yv.to_numpy(float)), float(yv.iloc[0]), int(yv.index[0])
        return np.nan, np.nan, None
    if basis == "seasonal":
        return seasonal_sens_slope(t, x, season), np.nan, None
    return sens_slope(t, x), np.nan, None


# ----------------------------------------------------------------------------- per-series wrapper
def trend_for_series(dates: pd.Series, values: pd.Series, temporal: str = "monthly", baseline_year: int | None = None,
                     var: str = "", meta: dict | None = None) -> dict:
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
           "sen_slope_per_year": np.nan, "lag1": np.nan, "baseline_mean": np.nan, "p_naive": np.nan}
    if temporal == "static" or len(x) < 4:
        return res
    t = (d.dt.year + (d.dt.month - 1) / 12.0).to_numpy(float)
    years = d.dt.year.nunique()
    if temporal == "monthly" and years >= 3 and len(x) >= 24:
        season = d.dt.month.to_numpy()
        naive = seasonal_kendall(t, x, season)
        r = hirsch_slack(t, x, season)
        res["p_naive"] = naive["p"]
        res.update(test="seasonal Mann-Kendall (Hirsch-Slack)", sen_slope_per_year=seasonal_sens_slope(t, x, season))
        clim = pd.Series(x).groupby(season).transform("mean").to_numpy()
        res["lag1"] = lag1_autocorr(x - clim)
    else:
        if years < 3 and len(x) < 4:
            return res
        naive = mann_kendall(x[np.argsort(t)])
        r = hamed_rao(t, x)
        res["p_naive"] = naive["p"]
        res.update(test="Mann-Kendall (Hamed-Rao)" if len(x) >= 10 else "Mann-Kendall (short series, uncorrected)",
                   sen_slope_per_year=sens_slope(t, x))
        res["lag1"] = lag1_autocorr(x[np.argsort(t)])
    res.update({k: r[k] for k in ("n", "S", "Z", "p", "tau")})
    # robustness checks on the time-ordered series (calendar-month means removed for monthly data)
    order = np.argsort(t, kind="stable")
    a = x - pd.Series(x).groupby(d.dt.month.to_numpy()).transform("mean").to_numpy() if temporal == "monthly" else x
    a = a[order]
    res["p_pw"] = tfpw_mk(a)["p"]
    pt = pettitt(a)
    res["cp_p"] = pt["p"]
    if pt["cp"] is not None:
        c_ = pt["cp"]
        res["cp_date"] = d.iloc[order[c_]].strftime("%Y-%m")
        res["cp_shift"] = float(a[c_:].mean() - a[:c_].mean())
        res["cp_dbic"] = step_vs_line(a, c_)
    by = baseline_year or int(d.dt.year.min())
    base = x[(d.dt.year == by).to_numpy()]
    res["baseline_mean"] = float(np.mean(base)) if len(base) else np.nan
    # headline slope on a seasonal-aware basis (+ trend-to-date for the slider)
    meta = meta or {}
    season_ = d.dt.month.to_numpy()
    res["sparse"] = bool(len(x) and np.mean(x == 0) > 0.4)
    if temporal == "monthly" and (d.dt.year == by).any():
        # seasonality-controlled: each month vs the same month of the baseline year
        res["basis"] = "vs_base_month"
        sl, pc, npairs = anchored_month_slope(d, x, by)
        res["display_slope"], res["display_pct"] = sl, pc
        res["sen_lo"], res["sen_hi"] = anchored_block_ci(d, x, by, seasonal_sens_slope(t, x, season_), sl)
        res["display_base"] = res["baseline_mean"]
        for Y in range(2020, 2026):
            s2, p2, n2 = anchored_month_slope(d, x, by, upto=Y)
            res[f"todate_{Y}"], res[f"todate_pct_{Y}"] = (s2, p2) if Y - by >= 2 and n2 else (np.nan, np.nan)
        return res
    basis = basis_of(var, {**meta, "temporal": temporal}, x)
    sl, b0, _ = display_slope(d, x, basis, t, season_)
    res["basis"] = basis
    res["display_slope"] = sl
    if basis == "observed":
        res["sen_lo"], res["sen_hi"] = sen_ci_gilbert(t, x, r["var_S"])
    res["display_base"] = b0 if np.isfinite(b0) else res["baseline_mean"]
    for Y in range(2020, 2026):
        m_ = (d.dt.year <= Y).to_numpy()
        if m_.sum() >= 3 and d[m_].dt.year.nunique() >= 3:
            s2, _, _ = display_slope(d[m_].reset_index(drop=True), x[m_], basis, t[m_], season_[m_])
            res[f"todate_{Y}"] = s2
        else:
            res[f"todate_{Y}"] = np.nan
    return res


def interpret(row: dict, meta: dict) -> str:
    """One plain-language sentence for the map hover (wraps _interpret)."""
    txt = _interpret(row, meta)
    if row.get("basis") == "vs_base_month":
        by = meta.get("baseline_year", 2018)
        txt = txt.replace("Sen's slope ", f"median change vs the same month of {by}: ").replace("about ", f"median change vs the same month of {by} ≈ ")
    return txt


def _interpret(row: dict, meta: dict) -> str:
    p, slope, q = row.get("p"), row.get("sen_slope_per_year"), row.get("q_fdr")
    if row.get("test") is None or p is None or not np.isfinite(p):
        return "Too few observations for a trend test."
    units = meta.get("units") or ""
    pct = row.get("sen_slope_pct_per_year")
    pct_txt = f" ({pct:+.1f}% of the {meta.get('baseline_year', 'baseline')} level per year)" if row.get("pct_ok") and pct is not None and np.isfinite(pct) else ""
    basis = row.get("basis")
    if basis == "vs_base_month":
        pct_txt = pct_txt.replace(" level per year", " same-month level per year")
    if basis in ("wet_season", "flood_season", "annual_total"):
        u0 = _RE.sub(r"\s*(/\s*month|per month)", "", units) if basis in ("wet_season", "annual_total") else units
        units = {"wet_season": f"{u0} (Jun–Sep total)", "flood_season": f"{units} (Aug–Nov average)", "annual_total": f"{u0} (annual total)"}[basis]
    fmt = lambda v: f"{v:+.3g}"
    ptxt = ("p < 0.001" if p < 0.001 else f"p = {p:.3f}") + (f", FDR q = {q:.3f}" if q is not None and np.isfinite(q) else "")
    sig = q is not None and np.isfinite(q) and q < ALPHA      # significance = FDR-adjusted across the 79 counties
    ac = ""
    pn = row.get("p_naive")
    if pn is not None and np.isfinite(pn) and pn < ALPHA <= p:
        ac = " (Looked significant before correcting for persistence; it is not.)"
    lisa = row.get("lisa")
    ac += {"HH": " Part of a spatial cluster of counties with similarly high trends (Local Moran's I).",
           "LL": " Part of a spatial cluster of counties with similarly low trends (Local Moran's I).",
           "HL": " Local outlier: a higher trend than its neighbours (Local Moran's I).",
           "LH": " Local outlier: a lower trend than its neighbours (Local Moran's I)."}.get(lisa, "")
    if sig and np.isfinite(slope) and slope != 0:
        direction = "rising" if slope > 0 else "falling"
        hi = meta.get("higher_is", "neutral")
        dw = row.get("direction", "more_less")
        words = {"wetter_drier": ("wetter", "drier"), "warmer_cooler": ("warmer", "cooler"), "greener_browner": ("greener", "browner")}
        if dw in words:
            judge = f" — {words[dw][0] if slope > 0 else words[dw][1]}"
        else:
            judge = "" if hi == "neutral" else (" — improving" if (slope > 0) == (hi == "better") else " — worsening")
        return (f"Significant {direction} trend over 2018–2025 ({row['test']}, {ptxt}): "
                f"about {fmt(slope)} {units} per year{pct_txt}{judge}.{ac}")
    if sig:
        return (f"Significant monotonic trend ({row['test']}, {ptxt}): values tend to be higher in later years even though the "
                f"typical change is small; slope ≈ {fmt(slope) if np.isfinite(slope) else 'n/a'} {units} per year.{ac}")
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
        r = trend_for_series(g["date"], g["value"], temporal, by, var, m)
        r.update(variable=var, county_id=cid, baseline_year=by)
        # headline slope = seasonal-aware display slope; % only where a % of the baseline is meaningful
        pct_ok = pct_meaningful(var, m, r.get("sparse", False))
        r["sen_slope_seasonal"] = r["sen_slope_per_year"]
        if np.isfinite(r.get("display_slope", np.nan)):
            r["sen_slope_per_year"] = r["display_slope"]
        b = r.get("display_base", r["baseline_mean"])
        r["pct_ok"] = pct_ok
        if r.get("basis") == "vs_base_month":
            r["sen_slope_pct_per_year"] = r.get("display_pct", np.nan) if pct_ok else np.nan
            for Y in range(2020, 2026):
                if pct_ok:
                    r[f"todate_{Y}"] = r.get(f"todate_pct_{Y}", np.nan)
        else:
            r["sen_slope_pct_per_year"] = 100 * r["sen_slope_per_year"] / abs(b) if pct_ok and b is not None and np.isfinite(b) and abs(b) > 1e-9 else np.nan
            for Y in range(2020, 2026):
                k = f"todate_{Y}"
                if pct_ok and b is not None and np.isfinite(b) and abs(b) > 1e-9 and np.isfinite(r.get(k, np.nan)):
                    r[k] = 100 * r[k] / abs(b)
        r["direction"] = direction_of(var, m)
        rows.append(r)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["q_fdr"] = out.groupby("variable")["p"].transform(lambda s: pd.Series(bh_fdr(s), index=s.index))
    # significance uses Benjamini-Hochberg FDR-adjusted q (controls false positives across the 79 counties)
    out["significant"] = out["q_fdr"] < ALPHA
    # sensitivity checks: (1) does significance survive trend-free pre-whitening (also FDR-adjusted)?
    # (2) is the change better described as one step (Pettitt break) than as a steady drift?
    for c_ in ("p_pw", "cp_p", "cp_dbic", "cp_shift", "sen_lo", "sen_hi"):
        if c_ not in out:
            out[c_] = np.nan
    out["q_pw"] = out.groupby("variable")["p_pw"].transform(lambda s: pd.Series(bh_fdr(s), index=s.index))
    out["pw_lost"] = np.where(out["q_pw"].notna(), (out["significant"] & ~(out["q_pw"] < ALPHA)).astype(float), np.nan)
    out["step_like"] = ((out["p"] < ALPHA) & (out["cp_p"] < ALPHA) & (out["cp_dbic"] >= STEP_DBIC)
                        & (np.sign(out["cp_shift"]) == np.sign(out["S"]))).astype(int)
    # spatial structure of each variable's trend map (skip national series repeated on every county)
    out["lisa"], out["lisa_p"], out["moran_I"], out["moran_p"] = "ns", np.nan, np.nan, np.nan
    for var, g in out.groupby("variable"):
        vals = g.set_index("county_id")["sen_slope_pct_per_year"]
        if vals.notna().sum() < 8 or vals.nunique() < 3:
            vals = g.set_index("county_id")["sen_slope_per_year"]
        if vals.notna().sum() < 8 or vals.nunique() < 3:
            continue
        glob_, loc = spatial_clusters(vals)
        out.loc[g.index, "moran_I"], out.loc[g.index, "moran_p"] = glob_["I"], glob_["p"]
        if len(loc):
            m_ = g[["county_id"]].reset_index().merge(loc, on="county_id", how="left").set_index("index")
            out.loc[m_.index, "lisa"] = m_["lisa"].fillna("ns")
            out.loc[m_.index, "lisa_p"] = m_["lisa_p"]
    out["interpretation"] = [interpret(r, {**meta.get(r["variable"], {}), "baseline_year": r["baseline_year"]})
                             for r in out.to_dict("records")]
    cols = ["county_id", "variable", "test", "n", "S", "Z", "tau", "p", "p_naive", "q_fdr", "significant", "sen_slope_per_year",
            "sen_slope_pct_per_year", "sen_slope_seasonal", "basis", "pct_ok", "direction", "baseline_year", "baseline_mean", "lag1",
            "lisa", "lisa_p", "moran_I", "moran_p", "sen_lo", "sen_hi", "p_pw", "q_pw", "pw_lost", "cp_date", "cp_p",
            "cp_shift", "cp_dbic", "step_like"] + [f"todate_{Y}" for Y in range(2020, 2026)] + ["interpretation"]
    return out.reindex(columns=cols)   # static-only sources have no basis/to-date columns


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
    if len(tr) and not df["county_id"].isin(["SS", "SSD", "national"]).all():
        reg = regional_trends(df, _load_meta(), tr)
        reg.to_csv(os.path.join(TREND_DIR, os.path.basename(path).replace(".csv", "_regional.csv")), index=False, float_format="%.6g")
    n_sig = int(tr["significant"].sum()) if len(tr) else 0
    print(f"[trend_stats] {os.path.basename(out)}: {len(tr)} county-variables, {n_sig} significant at FDR q<{ALPHA}")
    return out


if __name__ == "__main__":
    # Recompute trends for every processed source (python scripts/trend_stats.py)
    for f in sorted(glob.glob(os.path.join(PROC, "*.csv"))):
        write_trends(os.path.basename(f)[:-4])
