# How the trend statistics work (and why they changed)

All formulas live in one place, `scripts/trend_stats.py`. Every data pipeline calls `write_trends("<source>")`
at the end, and `python scripts/trend_stats.py` recomputes everything (about 90 seconds).
We checked the results against the Python package `pymannkendall`. The Hamed–Rao p-values are identical. For
Hirsch–Slack, S is identical and p agrees to within 0.01 (Juba maximum temperature, for example, gives 0.119 vs 0.115).
The small gap comes from how each implementation estimates the between-month covariance terms; ours follows the
published formula term by term.

## 1. The question each county answers

"Over 2018–2025, did this variable go consistently up or down in this county, more than chance would produce?"

Two numbers answer it. Sen's slope says how fast the variable changed: it is the median of all pairwise yearly
changes, so a few outliers barely move it. It is reported in units/yr and as % of the 2018 level per year. For
monthly data it compares only the same calendar month across years (the seasonal Sen's slope), so the rainy season
is never set against the dry season.

The Mann-Kendall test says whether the change is consistent. Over all pairs of time points it scores +1 when the
later value is higher and −1 when it is lower, and the sum is S. With no trend, S stays near 0, and its variance tells
us how far from 0 counts as "surprising".

## 2. The problem: persistence (serial correlation)

A hot, dry month is usually followed by another hot, dry month. Prices and drought indices drift slowly.
Ninety-six months of such data carry much less independent information than 96 coin flips. The plain test
assumes independence, so it underestimates the variance of S and calls too many trends "significant".

Example from our data, average daily maximum temperature (79 counties):

| | Counties "significant" |
|---|---|
| Plain seasonal Mann-Kendall, p < 0.05 | 66 |
| Corrected for persistence (Hirsch–Slack), p < 0.05 | 15 |
| Corrected, then false-discovery-rate q < 0.05 across 79 counties | 0 |

Median month-to-month (lag-1) autocorrelation was 0.53. Across all 16,173 county–variable series, the number
flagged significant fell from 4,510 to 1,015 after the correction.

## 3. The fix over time (one county at a time)

Monthly series use the Hirsch & Slack (1984) correlated seasonal Kendall test.
It is run separately for each calendar month and the 12 results are added: S = Σ_g S_g. The old version
treated the 12 months as independent. Hirsch–Slack adds the covariance between months (a wet year is wet in July,
August and September alike):

    Var(S) = Σ_g Var(S_g) + 2 Σ_{g<h} Cov(S_g, S_h)
    Cov(S_g, S_h) = [K_gh + 4 Σ_j R_jg R_jh − n(n+1)²] / 3          (Dietz & Killeen 1981)

Here K_gh counts pairs of years that move in the same direction in months g and h, R_jg is the rank of year j
within month g, and n is the number of years.

Annual and survey-round series with n ≥ 10 use the Hamed & Rao (1998) correction:
1. Remove the Sen's-slope trend.
2. Rank the residuals and measure their autocorrelation at each lag k.
3. Keep only lags that are significant (|r_k| > 1.96/√n).
4. Inflate the variance by n/n* = 1 + 2/(n(n−1)(n−2)) Σ_k (n−k)(n−k−1)(n−k−2) r_k.

Series shorter than 10 points (most annual series, since 2018–2025 is 8 years) are too short to estimate
autocorrelation. They use the plain test and are labelled "short series, uncorrected".

The uncorrected p is kept in the data (`p_naive`). When a county looked significant before the correction but
not after, the hover sentence says so.

## 4. The fix across space (the geospatial part)

Counties are not independent either. Neighbours share weather systems, the Nile flood pulse and conflict
dynamics. We deal with this in three ways.

### a) Correcting for testing 79 counties (false discovery rate)
At p < 0.05, about 4 of 79 counties would look "significant" by chance even with no trend. We convert p to
Benjamini–Hochberg q-values and outline a county only when q < 0.05. Wilks (2016) shows this procedure also
controls *field significance* for spatially correlated maps. Wilks allows q < 0.10; we use the stricter 0.05.

### b) Is the trend map clustered? Global and local Moran's I
Global Moran's I measures whether neighbouring counties (Queen contiguity: they share a border or corner) have
similar Sen's slopes, with p taken from 999 random reshufflings of counties. Maximum temperature is strongly
clustered (I = 0.83, p = 0.001); IMERG rainfall less so (I = 0.37).

Local Moran's I (LISA; Anselin 1995) gives each county a label, shown only where the permutation p < 0.05:
- High-High: part of a cluster of the strongest increases (or weakest decreases).
- Low-Low: part of a cluster of the strongest decreases.
- High-Low / Low-High: a local outlier, unlike its neighbours.

The labels describe where trends look alike. They do not test whether the trend itself is significant.

### c) Is there a trend across a region? Regional Kendall test (Douglas, Vogel & Kroll 2000)
When each county is too short or noisy on its own but the whole region moves together, pooling gains power.
We add S over all counties and months in a region: S_R = Σ_c Σ_g S_cg. Significance comes from a bootstrap that
resamples whole years, applied identically to every county and month (999 draws). Because whole years are
resampled, all counties share the same resampled year (keeping the spatial correlation) and all months of a year
move together (keeping the seasonal correlation). Resampling individual county-months would throw both away and
make the pooled p-values too small.

Results for all 79 counties and for the 16 Sudd counties (p < 0.05 in bold):

| Variable | All counties | Sudd |
|---|---|---|
| Daily max temperature (MERRA-2) | +0.18 °C/yr, **p = 0.043** | +0.19 °C/yr, p = 0.061 |
| Water storage (GRACE/GRACE-FO) | +2.7 cm/yr, **p = 0.003** | +2.8 cm/yr, **p = 0.006** |
| Groundwater (G3P, to 2023) | +3.2 cm/yr, **p = 0.010** | +3.5 cm/yr, **p = 0.009** |
| Surface water (MODIS) | **p = 0.001** | +0.48 %-points/yr, **p = 0.001** |
| Rainfall, CHIRPS | −0.17 mm/month per yr, **p = 0.012** | **p = 0.039** |
| Rainfall, IMERG | +0.02, p = 0.11 | +2.0, **p = 0.040** |
| Drought ensemble | drying, **p = 0.020** (TerraClimate-driven; see guide) | p = 0.09 |
| Political violence events (ACLED) | rising, **p = 0.022** | **p = 0.048** |

The two rainfall products disagree in sign, so a regional rainfall trend should not be reported from either one alone.

## 5. How to read the map now

A thick dark outline means the county's own trend survives both the persistence correction and the 79-county
correction. With only 8 years of data, expect few outlines on climate variables.

The legend has two extra lines. "Regional trend" is the pooled national and Sudd test; use it for statements like
"temperatures rose across South Sudan". "Spatial clustering" reports Moran's I; when it is high, describe trends
by region rather than county by county.

The hover card shows the corrected p, the uncorrected p in brackets, the FDR q, and any Local Moran's I cluster label.

## 6. Limits that remain

Eight years is short. Many real climate changes will not reach significance, and a non-significant result does
not show that nothing changed. Hirsch–Slack corrects for correlation between months within a year, but with only 8
years it cannot also estimate correlation between consecutive years in a given month. The regional bootstrap's null
distribution is coarse with 8 years; the smallest p it can give is about 0.001. Finally, trends in carried-forward
survey data (IPC, DTM) partly reflect the carry-forward steps.

## 7. "Trend to date" raster layers (`docs/rasters/<key>_trend/`)

Each gridded layer has a companion map for each end year YYYY = 2020..2025. It shows the per-pixel Sen's slope (the same
formula as `trend_stats.sens_slope`) of one value per year from 2018 through YYYY, needing at least 3 years.
Units are the layer's units per year. The colour scale is fixed per layer (±98th percentile of |slope| across all
end years), so the early maps, built on 3 years, look more extreme than later ones. That is noise from the short record.

- One value per year: the annual mean for state variables (NDVI, temperature, deficit, PDSI, wind, GRACE, S5P);
  wet-season (Jun–Sep) mean for rainfall, ET, soil water and Sentinel-1 flooding, so dry-season zeros do not
  flatten the slope; Sep–Dec for Sudd inundation (its high-water season; Jun–Sep is mostly cloud); annual totals
  for VIIRS fire detections and MODIS burned area. Missing months are filled with the pixel's monthly
  climatology plus the mean anomaly of the observed months. Each `meta.json` states its `basis`.
- There is no per-pixel significance test. With 3–8 points, a pixel slope describes the change but cannot establish
  a trend. Use the county trends (sections 3–5) for significance.
- Built by `scripts/raster_trends.py`.

## 8. Headline trend: each month vs the same month of 2018 (seasonality-controlled)

Since 15 Nov 2026 the headline slope for every monthly series compares each month with the same calendar month of
the baseline year (2018, or a source's first full year):

    change_ym = (x[y, m] − x[2018, m]) / (y − 2018)              e.g. (Jan 2024 − Jan 2018) / 6, (Feb 2022 − Feb 2018) / 4
    % change_ym = 100 · (x[y, m] − x[2018, m]) / |x[2018, m]| / (y − 2018)

The headline value is the median over all months after 2018 (a Sen-type estimator anchored on 2018), so January is only
ever compared with January. Pairs where both months are 0 (dry-season rain, months without events) carry no information
and are skipped. The "trend to date" for slider year Y uses only months up to Y. Significance still comes from the
seasonal Mann-Kendall test (Hirsch–Slack corrected), which likewise compares like months only. Annual or survey-round
series (no months) keep the ordinary Sen's slope.
