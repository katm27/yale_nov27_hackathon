# How the trend statistics work (and why they changed)

All formulas live in one place, `scripts/trend_stats.py`. Every data pipeline calls `write_trends("<source>")`
at the end, and `python scripts/trend_stats.py` recomputes everything (about 90 seconds).
Validated against the reference Python package `pymannkendall`:
- **Hamed–Rao:** identical p-values.
- **Hirsch–Slack:** S identical, p within 0.01 (e.g. Juba maximum temperature 0.119 vs 0.115). The small gap comes
  from how each implementation estimates the between-month covariance terms; ours follows the published formula
  term by term.

## 1. The question each county answers

"Over 2018–2025, did this variable go consistently up or down in this county, more than chance would produce?"

- **Sen's slope** = how fast it changed: the median of all pairwise yearly changes. It is robust to outliers and
  reported in units/yr and as % of the 2018 level per year. For monthly data it only compares the same calendar
  month across years (seasonal Sen's slope), so the rainy season is never compared with the dry season.
- **Mann-Kendall test** = whether the change is consistent. It counts, over all pairs of time points, how often the
  later value is higher (+1) or lower (−1). That sum is S. If there is no trend, S hovers around 0, and its
  variance tells us how far from 0 is "surprising".

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

**Monthly series → Hirsch & Slack (1984) correlated seasonal Kendall.**
The test is run separately for each calendar month and the 12 results are added: S = Σ_g S_g. The old version
treated the 12 months as independent. Hirsch–Slack adds the covariance between months (a wet year is wet in July,
August and September alike):

    Var(S) = Σ_g Var(S_g) + 2 Σ_{g<h} Cov(S_g, S_h)
    Cov(S_g, S_h) = [K_gh + 4 Σ_j R_jg R_jh − n(n+1)²] / 3          (Dietz & Killeen 1981)

Here K_gh counts pairs of years that move in the same direction in months g and h, R_jg is the rank of year j
within month g, and n is the number of years.

**Annual and survey-round series (n ≥ 10) → Hamed & Rao (1998).**
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
dynamics. We use three complementary tools.

**a) Correcting for testing 79 counties (false discovery rate).**
At p < 0.05, about 4 of 79 counties would look "significant" by chance even with no trend. We convert p to
Benjamini–Hochberg q-values and outline a county only when q < 0.05. Wilks (2016) shows this procedure also
controls *field significance* for spatially correlated maps. Using q < 0.05, rather than the 0.10 Wilks permits,
keeps us conservative.

**b) Is the trend map clustered? Global and local Moran's I.**
- Global Moran's I measures whether neighbouring counties (Queen contiguity: they share a border or corner) have
  similar Sen's slopes. p comes from 999 random reshufflings of counties.
  - Maximum temperature: I = 0.83, p = 0.001 (strongly clustered).
  - Rainfall (IMERG): I = 0.37.
- Local Moran's I (LISA; Anselin 1995) labels each county:
  - **High-High:** part of a cluster of the strongest increases (or weakest decreases).
  - **Low-Low:** part of a cluster of the strongest decreases.
  - **High-Low / Low-High:** a local outlier, unlike its neighbours.
- A label is shown only where the permutation p < 0.05.
- These labels describe where trends are similar; they are not significance tests of the trend itself.

**c) Is there a trend across a region? Regional Kendall test (Douglas, Vogel & Kroll 2000).**
When each county is too short or noisy on its own but the whole region moves together, pooling gains power.
We add S over all counties and months in a region: S_R = Σ_c Σ_g S_cg. Significance comes from a bootstrap that
resamples whole years, applied identically to every county and month (999 draws). Shuffling whole years, not
individual county-months, preserves spatial correlation (all counties share the same resampled year) and seasonal
correlation (all months of a year move together). That is what makes the pooled test honest.

Reported for all 79 counties and for the 16 Sudd counties:

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

Note that the two rainfall products disagree in sign. A regional rainfall trend should not be reported from one
product alone.

## 5. How to read the map now

- **White outline:** that county's own trend survives the persistence correction *and* the 79-county correction.
  Expect few outlines for climate variables over only 8 years. That is the honest answer, not a bug.
- **Legend, "Regional trend":** the pooled national and Sudd test. Use it for statements like "temperatures rose
  across South Sudan".
- **Legend, "Spatial clustering":** if Moran's I is high, describe trends regionally rather than county by county.
- **Hover:** the corrected p, the uncorrected p in brackets, the FDR q, and any Local Moran's I cluster label.

## 6. Limits that remain

- Eight years is short. Many real climate changes will not reach significance, and absence of significance is not
  evidence of no change.
- Hirsch–Slack corrects for correlation *between months within a year*. With only 8 years it cannot also estimate
  correlation *between consecutive years* in a given month.
- The regional bootstrap with 8 years has a coarse null distribution: its smallest possible p is about 0.001.
- Trends in carried-forward survey data (IPC, DTM) partly reflect the carry-forward steps.

## 7. "Trend to date" raster layers (`docs/rasters/<key>_trend/`)

Each gridded layer has a companion map per end year YYYY = 2020..2025: the per-pixel **Sen's slope** (the same
formula as `trend_stats.sens_slope`) of one value per year from 2018 through YYYY, needing at least 3 years.
Units are the layer's units per year. The colour scale is fixed per layer (±98th percentile of |slope| across all
end years), so early maps built on 3 years look more extreme than later ones; that is the noise of a short record.

- **One value per year:** annual mean for state variables (NDVI, temperature, deficit, PDSI, wind, GRACE, S5P);
  wet-season (Jun–Sep) mean for rainfall, ET, soil water and Sentinel-1 flooding, so dry-season zeros do not
  flatten the slope; Sep–Dec for Sudd inundation (its high-water season; Jun–Sep is mostly cloud); annual totals
  for VIIRS fire detections and MODIS burned area. Missing months are filled with the pixel's monthly
  climatology plus the mean anomaly of the observed months. Each `meta.json` states its `basis`.
- **No per-pixel significance test.** With 3–8 points a pixel slope describes change; it does not prove a trend.
  Use the county trends (sections 3–5) for significance.
- Built by `scripts/raster_trends.py`.

## 8. Headline trend: each month vs the same month of 2018 (seasonality-controlled)

Since 15 Nov 2026 the headline slope for every monthly series compares each month with the **same calendar month of
the baseline year** (2018, or a source's first full year):

    change_ym = (x[y, m] − x[2018, m]) / (y − 2018)              e.g. (Jan 2024 − Jan 2018) / 6, (Feb 2022 − Feb 2018) / 4
    % change_ym = 100 · (x[y, m] − x[2018, m]) / |x[2018, m]| / (y − 2018)

The headline value is the median over all months after 2018 (a Sen-type estimator anchored on 2018), so January is only
ever compared with January. Pairs where both months are 0 (dry-season rain, months without events) carry no information
and are skipped. The "trend to date" for slider year Y uses only months up to Y. Significance still comes from the
seasonal Mann-Kendall test (Hirsch–Slack corrected), which likewise compares like months only. Annual or survey-round
series (no months) keep the ordinary Sen's slope.
