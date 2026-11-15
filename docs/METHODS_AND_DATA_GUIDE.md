# South Sudan Trend Explorer: methods, sources and data-confidence guide

NASA Space Apps 2026 (Earth System Trend Detective). Interactive county map of South Sudan: 79 counties,
monthly 2018-01 to 2025-12, overlaying climate and environment data with conflict, displacement and
humanitarian data.

**Who this is for**
- **The team**: one place that explains every number the app shows and how to rebuild it.
- **Judges**: what was calculated, how, and how far each layer can be trusted.
- **Decision-makers (UN agencies, NGOs, donors)**: which layers can support a county-level decision and which are
  context only.

**How to use this guide**
- Read §1 to learn the map.
- Read §5 (confidence) before quoting any number from the app.
- §2–§3 hold the formulas. §4 is the source catalogue. §6 lists gaps and what would close them. §7 explains how to
  rebuild everything.

Status: written 15 Nov 2026 from the repository state on that date. Work still in progress is marked
**⏳ pending: …**. Update those markers when the owning agent finishes.

Companion documents (more detail on specific topics):
[`data/DATA_CONTRACT.md`](../data/DATA_CONTRACT.md) ·
[`docs/CLIMATE_DATA_DECISIONS.md`](CLIMATE_DATA_DECISIONS.md) ·
[`docs/VALIDATION_rainfall.md`](VALIDATION_rainfall.md) ·
[`docs/RESEARCH_variables_and_priorities.md`](RESEARCH_variables_and_priorities.md) ·
[`docs/district_profiles_sources.md`](district_profiles_sources.md) ·
`docs/AUDIT_county_crosswalk.md` (⏳ pending: county crosswalk audit) ·
every `data/raw/<source>/SOURCE.md`.

## Contents
1. [Overview and how to read the map](#1-overview-and-how-to-read-the-map)
2. [Geography and time](#2-geography-and-time)
3. [Calculations](#3-calculations)
4. [Data catalogue](#4-data-catalogue)
5. [Confidence assessment](#5-confidence-assessment)
6. [Known gaps and what would fix them](#6-known-gaps-and-what-would-fix-them)
7. [Reproducibility](#7-reproducibility)

**Six things to know before quoting the map**
1. **No rainfall product is "truth" in South Sudan.** CHIRPS and IMERG agree on levels (median county r = 0.92) but
   disagree on the 2018–2025 trend: CHIRPS −25 mm/yr per year, IMERG +5. Quote a rainfall trend only when all
   sources agree.
2. **Conflict and displacement counts are sparse.** In most counties most 2018 months are zero. The app therefore
   shows the *change from the 2018 monthly average* (a difference), not a ratio.
3. **Some layers are national or state values copied onto every county:** funding, WPS index, Insecurity Insight,
   ACLED sub-event types. They show *when* something happened, not *where*. The label says "— national" or
   "state".
4. **Survey-based layers are sparse in time:** IPC (11 analyses), DTM Mobility Tracking (14 rounds), ISNA (3 rounds),
   HNO (6 years). Do not read them as monthly series.
5. **A white county outline means a statistically significant monotonic trend** (Mann-Kendall p < 0.05). It does not
   prove cause, and with 79 counties × 251 variables some outlines are false positives. See §3.7.
6. **Flood extent from optical MODIS under-counts** (≈0.5× UNOSAT) because the Sudd floods under vegetation and
   behind cloud. Read it as a relative signal. A Sentinel-1 radar layer is being finalised (⏳ pending).

---

## 1. Overview and how to read the map

### 1.1 What the app is
- A static web page: `docs/index.html` + `docs/app.js`, using Leaflet and Chart.js.
- It loads a pre-built data bundle from `docs/data/`.
- All indexing and aggregation happen in the browser, from **raw values**, so a user can switch between modes
  without rebuilding anything.
- The build is `scripts/build_web_data.py` (§7).

Current bundle: **251 variables** (`docs/data/variables.json`), **13 point/line/polygon layers**, **21 raster
overlay folders**, **5 flow-arrow sources**, and county profiles for all 79 counties.

### 1.2 Sidebar controls
| Control | Options | Effect |
|---|---|---|
| **Show values as** (`#mode`) | **Trend 2018–2025** (default) · **Index vs same month/season in 2018** · **Index vs 2018 annual average** · **Raw values** | How each county is coloured. Formulas in §3.1–3.2. |
| **Time step** (`#agg`) | **Monthly** · **Seasonal** · **Annual** | Window averaged for the map, charts, arrows and point filter. Seasons: dry **Dec–Mar** (Dec counts with the following year), early rains **Apr–Jun**, main rains **Jul–Sep**, late season **Oct–Nov**. |
| Time slider + ▶ | 2018-01 … 2025-12 | Selects the window. Play advances one window every 0.9 s. In Trend mode the county colours do not change with the slider, but arrows, points and charts do. |
| Variable list | ● button = colour the map; ☑ = add to the county detail charts | Grouped by category and group. The text after each label gives units and coverage years. |
| Raster overlays | Native-resolution PNGs (raw units, fixed colour scale) | When an overlay is on, county fill is made semi-transparent (opacity 0.35). |
| Point layers | 13 layers, filtered by the time window | See §1.7. |
| Migration arrows | Source: best available / a single source. Reason filters. | See §1.6 and §3.8. |

### 1.3 Colours and legend
| Mode | Colour scale | Midpoint | Saturation |
|---|---|---|---|
| Trend | Diverging | "no change" | 90th percentile of \|slope\| across counties (§3.7) |
| Index, ratio variables | Diverging on **log2(ratio)** | 1.0 = baseline | ≤ 0.5× and ≥ 2× (halving or doubling) |
| Index, difference variables | Diverging | 0 = baseline | 95th percentile of \|difference\| across counties and (sampled) months |
| Raw, and every static layer | Sequential blue | — | 2nd to 98th percentile of all values |

- **Colour direction** comes from each variable's `higher_is` field:
  - `better`: blue = better than baseline, red = worse.
  - `worse`: the reverse.
  - `neutral`: purple = higher, orange = lower.
  - Changes within ±5 % of the saturation span are drawn in the neutral mid-grey.
- **The legend** always shows the variable title and colour bar. The **"How to read this"** fold adds:
  - the comparison used;
  - the baseline year, with a ⚠ when it is not 2018;
  - the source time step and carry-forward length;
  - the number of counties with a significant trend;
  - the source and native resolution.

### 1.4 County outlines and hatching
| What you see | Meaning |
|---|---|
| **White, thick outline** (2.6 px) | The colouring variable has a **significant 2018–2025 monotonic trend** in that county: Mann-Kendall or seasonal Mann-Kendall p < 0.05, *not* FDR-adjusted (§3.7). |
| Black outline | Selected county (click). |
| Grey fill, dashed outline | No data for this county in this window (or no trend test in Trend mode). |

### 1.5 Hover card
Hovering a county shows, from top to bottom:
1. **County, state, window.**
2. **District profile** (`data/district_profiles.json`, all 79 counties):
   - dominant FEWS NET 2018 livelihood zone;
   - livelihoods;
   - history;
   - conflict impact, with a numeric sentence computed from the processed data.
   Sources: [`district_profiles_sources.md`](district_profiles_sources.md).
3. **Value** of the colouring variable in the current mode, for example:
   - "1.32× 2018 level"
   - "+4.1 events/month vs 2018"
   - "+2.3% of 2018 level per year (≈1.16× from 2018 to 2025)"
4. **Trend badge:** "◆ Significant trend" or "No significant trend", plus the plain-language sentence written by
   `trend_stats.interpret()`.
5. **Four sparklines** (full 2018–2025, orange line = selected month):
   - forced migration (`et_ind_total`);
   - US humanitarian funding (`fts_us_gov_funding_month_usd`, national);
   - flood extent: the first available of `flood_s1_pct` → `surface_water_pct`;
   - drought: `drought_ensemble_mean`, with a shaded band of ± ½ × `drought_ensemble_spread`; falls back to `spei3`.

### 1.6 Arrows (migration flows)
- Arrows run from the county people left to the county where they were recorded.
- **Colour = reason:**
  - red: conflict
  - blue: flood/disaster
  - amber: food/hardship
  - purple: Sudan war (cross-border)
  - green: return/relocation
  - grey: other
- **Width ∝ √people.**
- **Line style = source:**
  - solid: Event Tracking
  - dashed: Flow Monitoring
  - dotted: Mobility Tracking stock
  - dash-dot: Renk intentions
- **Default "best available":** for each month the app draws *one* source only. It takes Event Tracking; if Event
  Tracking has no rows that month, Flow Monitoring; if neither has rows, the latest Mobility Tracking IDP stock.
- The status line under the controls names the source in use, and for a stock source it names the survey round.
- **White circles on the border** are the verified crossing points where cross-border arrivals enter (§2.2, §3.8).
- The 200 largest arrows are drawn in each window.
- Details are in §3.8.

### 1.7 Point layers (time-filtered)
- A feature is shown when its validity period overlaps the selected window. The rule is
  `valid_from ≤ window end` and `valid_to ≥ window start`, where null means open-ended.
- Event layers (UCDP events, Insecurity Insight incidents) are shown when their `date` falls in the window.
- Snapshot layers (health facilities, schools, water points, pipelines) carry `snapshot=true` and a `date_basis`.

| Layer | Temporal basis |
|---|---|
| UCDP events | Event date |
| Insecurity Insight incidents | Event date. **Points sit at state centroids**: the source censors coordinates. |
| UNMISS deployments | 38 UN map 4456 revisions (Geo-PKO v2.3 + Rev.62/67) |
| Logistics Cluster hubs | 16 dated CONOPS maps 2018–2026. Sites carried through the Oct 2023–Jan 2026 gap (flagged). |
| WFP markets | First/last month with retail prices (gaps > 6 months split periods) |
| FMR monitoring points | Months with recorded forced internal trips. Nov 2023–Dec 2024 bridged. |
| Crisis sites (PoC / IDP / refugee camps) | Curated open/redesignation dates. Some months approximate (flagged). |
| Oil fields | Production-status periods: Toma South restart Sep 2018, Unity Jan 2019, Dar Blend export halt Feb–Dec 2024. |
| Pipelines, health facilities, schools, water points | Snapshot only |
| Ethnic groups (GeoEPR polygons) | 2011–2021 period. Toggle-only, neutral styling. |

⏳ pending: final time-dynamic point-layer QA by agent "points-time".

### 1.8 County detail panel (click a county)
- One chart per ticked variable, one point per window (month, season or year), in the current mode.
- In Trend mode the charts show the same-month index instead.
- Ratio charts use a log axis clamped to 1/8×–8×. A dashed line marks 1.0 (ratio) or 0 (difference).
- Clicking a point moves the time slider to that window.

### 1.9 National timeline (bottom strip)
Up to 15 country-wide series with the selected month marked. Each series is built in one of four ways:

| `how` | Construction | Used for |
|---|---|---|
| `national` | The single national series, read from the first county that has data (national rows are broadcast identically to every county, §3.6) | FTS funding, USAID / US aid, HRP coverage, UNMISS personnel, Insecurity Insight |
| `sum` | Sum over the 79 counties | IOM ET people displaced, ACLED fatalities, local conflict events, flood km² |
| `state_sum` | Sum over **one county per state**, because state totals are repeated on every county of the state | ACLED sexual-violence events |
| `mean` | Unweighted mean of county values | Drought index, IMERG rainfall, NDVI |

The `mean` series are **not area- or population-weighted**: a small county counts as much as a large one.

---

## 2. Geography and time

### 2.1 Gold-standard county boundaries
- **Source:** `data/counties.geojson` holds **79 counties (admin-2) from OCHA COD-AB v03** for South Sudan. It
  includes the **Abyei Administrative Area as `SS0001`**.
- **Origin:** team Drive file `boundaries_south_sudan_counties_79.geojson`.
- **Properties:** `district_id` (OCHA P-code, e.g. `SS0101` = Juba), `name`, `admin1` (state or administrative
  area), `lat`, `lon` (centroid).
- **The file is never modified.** Every pipeline joins to `district_id`. `build_web_data.py` drops any row whose
  `county_id` is not one of the 79 and prints the dropped ids.
- **Web map geometry:** `docs/data/counties.geojson` is simplified with a 0.004° tolerance (topology preserved,
  4-decimal coordinates). All statistics use the full-resolution file.
- **"District" means county** throughout the project. The 2015–2020 period of 28 and then 32 states is *not* used
  as a geography. Sources from that period are crosswalked to the 79 COD-AB counties (§2.2).
- **Abyei:**
  - It is included wherever a source covers it.
  - ACLED, UCDP and WorldPop code Abyei under Sudan. It is taken from the Sudan files: ACLED Admin1 'Abyei' →
    `SS0001`; UCDP events by point-in-polygon; WorldPop from the SDN grid.
  - DTM baseline data and the ACLED state export do **not** cover Abyei. ACLED-state variables therefore have 78
    counties.

### 2.2 Crosswalking source codes and names to OCHA P-codes
**Master table:** `data/crosswalks/county_crosswalk_master.csv`, one row per county (79). Its columns:
- OCHA P-code and state;
- 2020 administrative-area membership;
- IOM P-code, other P-codes, and the pre-2015 OCHA numeric code;
- the names used by IOM DTM, OCHA HNO/3W/HAPI, ACLED, IPC, WFP (admin-2 and market names), WHO, SSSAMS 2015 and
  UNHCR locations;
- GADM 4.1 level-2 overlap shares (`gadm41_overlap.csv`);
- curated aliases.

It is rebuilt from raw files by `scripts/build_county_crosswalk.py`, which needs no downloads. Each harvested
(code, name) pair is resolved in two steps:
1. **By code**, if the OCHA name for that code agrees with the source name after normalisation and aliases.
2. **Otherwise by name.**

**Lookup helper:** `scripts/county_crosswalk.py` provides `to_ocha()` and `to_ocha_multi()`. Lookup order: gold
P-code → source-specific alternative codes → normalised names and aliases.

| Case | Resolution |
|---|---|
| Abyei: IOM DTM uses `SS1101`; HNO 2023 and 3W 2021–22 use `SS0807`; ACLED uses Sudan `SD19001` | All → `SS0001` |
| Pre-2015 OCHA numeric codes (HNO 2019, e.g. `9202`) | → current P-code (`SS0101`) |
| Payam-level or sub-county IPC areas (e.g. "Akoka" → Baliet; "Wau (Rural Only)" → Wau) | Summed into the county |
| Multi-county administrative areas ("Ruweng Administrative Area" → `SS0601;SS0608`, "Greater Pibor AA" → `SS0308;SS0309`) | `to_ocha_multi`, listed in `county_multi_unit_aliases.csv`. Not silently assigned to one county. |
| Foreign origins in flow data (SDN, ETH, UGA, KEN, CAF, COD) | Replaced by a verified border-crossing node (§3.8) |
| Market and camp locations (WFP, UNHCR) | WFP: spatial join of market coordinates. UNHCR: hand mapping of camp → county. |
| Events with coordinates (UCDP, VIIRS, MODIS fire) | Point-in-polygon against the gold boundaries |

- **IOM DTM numbering:** IOM uses the OCHA admin-2 numbering for all 78 non-Abyei counties. `build_county_crosswalk.py`
  reports no code/name disagreements for SS codes.
- ⏳ pending: `docs/AUDIT_county_crosswalk.md`. This will hold the per-source match rates, the fixes made, and
  residual issues; pipelines whose join was wrong will be re-run (agent "crosswalk").

### 2.3 Border crossings
`data/crosswalks/border_crossings.csv` (23 crossings: Sudan 8, Ethiopia 5, DR Congo 4, Uganda 3, CAR 2,
Kenya 1, plus fall-backs) is built by `scripts/build_border_crossings.py`.

- **Source coordinate:** an IOM DTM Flow Monitoring Point, or an OpenStreetMap node or way.
- **Map coordinate:**
  - If the source point is inside South Sudan and ≤ 3 km from the COD-AB border, it is kept as is.
  - Otherwise it is snapped to the nearest border point and pulled 300 m inside. `snap_km` records the distance
    moved, for example 14.6 km for Joda/Wunthou (Renk), whose IOM coordinate lies on the Sudan side of the COD-AB
    line.
- **Dropped after checks:**
  - Ngomoromo: the OSM node is 30 km inside Uganda.
  - Raja/Sopo: 85 km from the border.
  - Panakuach: no verifiable coordinate.
- **Fall-back:** if the CSV is missing, `build_web_data.py` uses one approximate crossing per country.

### 2.4 Time grid
- **Grid:** monthly, **2018-01 … 2025-12 (96 months)**. Each value is dated to the first day of its month.
- **Mapping to the grid:**
  - Several rows in the same county-month are averaged.
  - 2026 rows (e.g. the team unified dataset to Sep 2026) are kept in the raw files but not shown.
- **Annual data** (WorldPop, HNO, UNHCR end-year stocks, ISNA, land cover, UNMISS presence, WPS, MODIS annual ET)
  is dated **YYYY-07-01**, by contract.
- **Survey and analysis rounds** (IPC, DTM Mobility Tracking) are dated at the round's reference month:
  - IPC: the first month of the current analysis period.
  - DTM: the last month of data collection.
- **Static layers** (soil, elevation, biodiversity, GLW 2015 livestock, 2015 schools, 2025 health facilities, oil,
  ethnic groups) have one value per county, shown in every month.

### 2.5 Baseline-year rules
The **baseline year** is the year every index compares against. It is set by
`build_web_data.py` (shown in the legend) and, separately for trends, by `trend_stats.py`:

1. **2018 by default.**
2. **If the variable has no data anywhere in 2018:** the first year with data. Examples:
   - IOM Event Tracking and FMR: 2020
   - FMR all-movements: 2022
   - OCHA 3W and HNO PiN: 2019
   - HNO severity: 2022
   - ISNA: 2022
   - WPS: 2019
   - Insecurity Insight CRSV: 2020
   - UNMISS deployment sites: 2023
   - VIIRS NOAA-20: 2020
   - IPC AMN and GAM: 2025 (a single snapshot)
3. **`baseline_year_override`** in a variable's metadata, if set, wins. It is used for the `et_*` series: 2020,
   because Dec 2019 is a single partial month.
4. **Static variables** keep 2018 nominally; they are never indexed.

Variables whose baseline is not 2018 get a ⚠ line in the legend. **64 of 251 variables** have a non-2018
baseline.

**2018 was not a "normal" year.** The R-ARCSS peace agreement was signed in September 2018, and conflict was still
high in the first half of the year. A decline in conflict after 2018 is partly a return from an unusual baseline,
not necessarily an improvement.

**Partial 2018 baselines:**
- Sentinel-5P starts May–July 2018.
- Annual series dated July have **no values Jan–Jun 2018** (see the caveat in §3.4).

---

## 3. Calculations

All statistics are computed **per county from the gold boundaries** and stored as **raw values** in long CSVs
(`county_id, date, variable, value`; [`DATA_CONTRACT.md`](../data/DATA_CONTRACT.md)). An absent row means missing.
A 0 is written only when the true value is zero: conflict events, fires, and ET individuals in a covered month.

### 3.1 Map index modes (browser, `docs/app.js` → `valueAt()`)
Notation:
- *c* = county, *v* = variable.
- *W* = the months in the selected window (one month, a season, or a calendar year).
- *x̄_W* = mean of the available raw values in *W*; missing months are ignored.
- *B* = baseline year.

**Raw:**
  `value = x̄_W` (original units).

**Index vs same month/season of the baseline year (`index_month`, removes seasonality):**
  - *W_B* = the same calendar month(s) shifted into year *B*. For the annual time step, *W_B* = all of year *B*.
  - `base = mean(x over W_B)`
  - ratio variable: `value = x̄_W / base`
  - difference variable: `value = x̄_W − base`

**Index vs baseline-year average (`index_annual`):**
  - `base = mean(x over all months of B)`, then the ratio or difference as above.

**Trend:**
  - Sen's slope from §3.7.
  - Ratio variables: `value = sen_slope_pct_per_year`, shown with the implied ×-change (below).
  - Difference variables: `value = sen_slope_per_year` in native units.

**Ratio or difference? (`index_ok`)**
- The app uses the **difference** whenever the variable's metadata has `index_ok = false`. That is set in three
  ways:
  1. **By the source pipeline**, for °C temperatures, SPEI/SPI/PDSI, drought ensemble, flags, phases, shares that
     can be 0, fire and burned area, Sentinel-5P NO₂ and aerosol index, and every static layer.
  2. **By `build_web_data.py`**, if any value of the variable is < 0. A ratio is meaningless when values cross zero.
  3. **By the sparse-count rule** (§3.3).
- If the baseline is 0 (|base| < 10⁻⁹) for a ratio variable, the cell is left blank instead of showing ∞.
- **Static layers** always show raw values.
- **Sparse-count variables** (`baseline_mode = "annual"`) always compare with the **baseline-year monthly average**,
  even in `index_month` mode. A same-month baseline would be zero almost everywhere.

**Implied change 2018→2025 (Trend mode, ratio variables)**
- `× change = 1 + 7 · (slope % per year) / 100`, floored at 0. The 7 is the number of years from 2018 to 2025
  (`TREND_YEARS = 7`).
- This is a **linear** extrapolation of the median slope, not compounding. For example, +10 %/yr → 1.7×, and
  −10 %/yr → 0.3×.
- It describes the size of the trend line, not the observed 2025/2018 ratio.

**Worked example (Juba, `SS0101`)**
| Quantity | Value | Calculation |
|---|---|---|
| NDVI raw, Aug 2024 | 0.808 | MODIS monthly max-value composite, county mean |
| NDVI, Aug 2018 | 0.771 | Same month in the baseline year |
| Mean NDVI over all of 2018 | 0.607 | 12-month mean |
| **Index vs same month** | **1.05×** | 0.808 / 0.771 → "about the same greenness as August 2018" |
| **Index vs 2018 average** | **1.33×** | 0.808 / 0.607. Inflated by the wet season, which is why same-month is the default index. |
| ACLED political-violence events, Aug 2024 | 12 | ACLED admin-2 monthly aggregate |
| ACLED 2018 monthly mean | 4.17 | (3+1+2+5+2+2+5+9+3+3+5+10)/12 |
| **Shown (sparse count → difference)** | **+7.8 events/month vs 2018** | 12 − 4.17 |
| Population (WorldPop), Sen's slope | +12 920 people/yr = **+2.96 %/yr** of the 2018 level | Mann-Kendall p < 0.001, n = 8 |
| **Implied change 2018→2025** | **≈1.21×** | 1 + 7 × 0.0296 |
| Mean air temperature (`tair_c`, °C, difference variable) | **+0.23 °C per year** | Seasonal Sen's slope, seasonal MK p < 0.001. Shown in °C/yr, not %. |

### 3.2 Time aggregation windows
- **Monthly:** one month.
- **Seasonal:** South Sudan's agricultural calendar:
  - dry season **Dec–Mar**, with December assigned to the *following* year's dry season;
  - early rains **Apr–Jun**;
  - main rains **Jul–Sep**;
  - late season **Oct–Nov**.
- **Annual:** calendar year.

The window value is the **unweighted mean of the available monthly values**. Every variable is averaged this way,
including counts. A seasonal or annual value of a count variable is therefore the *average month* in that window,
not the total. Missing months are skipped, so a window with only one observed month shows that month's value.

### 3.3 Sparse counts
Rule in `build_web_data.py`. A variable is flagged `sparse_count = true` if it meets all three conditions:
1. it is monthly;
2. all its values are ≥ 0;
3. **more than 40 % of its baseline-year county-months are exactly zero** (unless the metadata sets `force_ratio`).

A flagged variable then gets `index_ok = false` and `baseline_mode = "annual"`.

- **66 variables** are flagged. They are all ACLED, ACLED-state, UCDP, local-conflict, IOM ET and FMR county series,
  plus Insecurity Insight health and education attacks, Logistics Cluster hubs, UNMISS sites, and the TerraClimate
  extreme flags.
- **On the map**, they show the **difference from the baseline-year monthly average**, in events, people or deaths
  per month.
- **In Trend mode**, they show the Sen's slope in units per year. A % of baseline is undefined for them.
- **Many county Sen's slopes for sparse counts are exactly 0** (the median of many zero pairwise differences), even
  where MK is significant. `interpret()` then writes "Significant monotonic trend … but the median slope is ~0".
- **Recommendation:** for county comparisons, use seasonal or annual windows (§3.2), which average the noise.

### 3.4 Carry-forward of survey rounds, annual and static values
`build_web_data.py` forward-fills each county series on the monthly grid for a set number of months, by `temporal`:

| `temporal` | Carry (months) | Effect |
|---|---|---|
| monthly | 0 | none |
| annual (dated July) | **11** | The July value fills Jul–Jun of the next year. |
| static | 95 | Fills all 96 months. |
| `periodic` / `round` | 6 | Intended for survey rounds |
| any other label | 0 | — |

- `variables.json` records `carry_forward_months` for each variable, and the legend says "latest value carried
  forward up to N months".
- Charts and the map do not distinguish carried values from observed ones. `months_observed` in `variables.json`
  gives the true count.

**Two known side-effects. Fix both before the final submission.**
1. **IPC and DTM Mobility Tracking are *not* carried forward.**
   - Their metadata uses `temporal = "irregular (per IPC analysis)"` and `"irregular (per round)"`. These labels
     do not match the `periodic`/`round` keys, so the carry is 0.
   - As a result `ipc_*` shows only in its 11 analysis months, and `dtm_idps` / `dtm_returnees` only in their 14
     round months; all other months are blank.
   - **Fix:** set `carry_forward_months` explicitly in `ipc.json` and `dtm.json` (e.g. 12 for IPC and 6–9 for DTM),
     or map `irregular*` to `round` in `DEFAULT_CARRY`.
2. **Annual series have no value in Jan–Jun 2018.**
   - The first value is July 2018.
   - So the *same-month* index is blank in Jan–Jun of every year for annual variables: their baseline months do not
     exist.
   - **Workaround:** use "Index vs 2018 annual average" or the Annual time step for annual variables.
   - **Fix:** give non-monthly variables `baseline_mode = "annual"` in the build.

**Flows are carried separately:**
- Mobility Tracking O-D stocks are carried until the next round, for up to 24 months (§3.8).
- Trend statistics (§3.7) are always computed on the **observed** values only, never on carried values.

### 3.5 Aggregation from native data to counties
| Method | Formula and rules | Used by |
|---|---|---|
| **Area-weighted raster mean** | County value = Σ wᵢ·xᵢ / Σ wᵢ. The weight is wᵢ = (fraction of cell *i* inside the county, estimated on a 5×5 sub-grid per cell) × cos(latitude). | TerraClimate (1/24°), CHIRPS v3 (0.05°), drought-ensemble inputs |
| **Regrid then mean of cell centres** | Native pixels are quality-masked, area-averaged (`Resampling.average`, NaN-aware) onto a 0.01° (~1.1 km) EPSG:4326 grid. County = mean of valid cells whose centre lies in the county (rasterised label grid). County-months with < 5 % valid cells are dropped. | MODIS NDVI/EVI, LST, reflectance, annual ET (`fetch_modis_land.py`); AppEEARS monthly ET (needs ≥ 75 % of days valid per cell) |
| **Native-grid zonal statistics (equal-area)** | County label raster on the MODIS sinusoidal grid. Count of flagged pixels × pixel area (0.2147 km² at 500 m). | MODIS active fire (count), MCD64A1 burned area, MODIS surface water (`hazards_common.py`) |
| **Sum of pixels** | Σ population or head count of pixels whose centre is in the county | WorldPop 1 km (Abyei from the SDN grid), GLW4 livestock |
| **Class share** | Class pixels / classified pixels × 100, from a 1-in-64 nearest-neighbour systematic sample (COG overview, ~80 m) of the 10 m map. UTM tiles are clipped to their own grid cell to avoid double counting. | Esri/IO land cover |
| **Swath binning** | Quality-filtered L2 pixels (TROPOMI) are binned to a 0.05° grid. County = mean of all valid pixel observations whose centre is in the county, from **4 sampled orbits per month** (6 in 2018). | Sentinel-5P NO₂, CO, aerosol index |
| **Centroid sampling** | Value of the single POWER grid cell (0.5°×0.625° MERRA-2, 1° CERES) containing the county centroid | NASA POWER wind, T2M_MAX, PRECTOTCORR, AOD (`fetch_nasa_power.py`) |
| **POWER cells averaged over the county** | Computed upstream in the team Drive pipeline | `drive_climate`: IMERG precipitation, MERRA-2 T2M/Tmax/Tmin, GWETROOT, Thornthwaite PET, SPEI-3 |
| **Point-in-polygon counts and sums** | Each event or detection is assigned to the county polygon that contains it | UCDP GED (only `where_prec` ≤ 3, i.e. county precision or better; coarser events stay in the points layer only), local-conflict subset, VIIRS FIRMS detections, health facilities, schools, oil wells, WFP markets |
| **Median over markets** | Median of retail prices over the county's markets, monthly. 3.5 kg "malwa" units ÷ 3.5 → per kg. USD from WFP `usdprice`. | WFP prices (12–32 market counties) |
| **Name or code joins** | Source admin-2 code or name → OCHA P-code via the crosswalk (§2.2). Sub-county areas summed. | ACLED admin-2 aggregates, IPC, HNO, 3W, DTM baseline, ISNA, immunisation, ET, FMR |
| **State total repeated on every county** | Admin-1 value copied to every county of the state | ACLED aggregated weekly state export (weeks assigned to the month in which they start), Insecurity Insight state table (not loaded) |
| **National value broadcast** | §3.6 | FTS, US aid, UNMISS budget and personnel, FMR national, WPS, IGME mortality, Insecurity Insight |
| **Line length** | Pipeline length within the county (GEM GOIT operating lines + OSM/Overture; overlaps may double count) | `oil_pipeline_km` |

**Special processing by product**
- **MODIS active fire:** months with incomplete Terra/Aqua daily coverage on Planetary Computer are scaled to a full
  month: count × expected / available sensor-days (e.g. 2022-12 had 38 of 62). Months with < 50 % coverage are
  dropped.
- **MODIS NDVI/EVI:** per-pixel **monthly maximum** of 16-day composites, assigned to the month of their mid-date
  (pixel reliability 0/1 only). LST and reflectance use the **monthly mean** of clear 8-day composites.
- **MODIS surface water:**
  - A pixel-observation is water when MNDWI = (B4 − B7)/(B4 + B7) > 0.1.
  - Monthly water = water in ≥ 50 % of the month's clear observations.
  - Unobserved pixels inherit the previous month's state, for at most 2 months.
  - County-months with < 20 % known area are dropped.
- **TerraClimate extreme flags:** the county-mean value is compared with that county's 1991–2020 empirical
  percentiles for the same calendar month:
  - wet: > P90
  - dry: < P10, only where P10 > 0
  - heat: Tmax > P90
- **Drought ensemble** (`drought_ensemble.py`):
  - Members: IMERG SPEI-3 (upstream, county 2000–2026 baseline); CHIRPS SPI-3 (gamma fit with zero-rain
    probability, 1991–2020, bounded ±3.09); TerraClimate SPEI-3 (log-logistic, probability-weighted moments,
    1991–2020); TerraClimate PDSI z-scored per county and calendar month against 1991–2020.
  - `mean` = mean of members, with ≥ 3 members required.
  - `spread` = sample SD across members.
  - `range` = max − min.
  - `agree` = share of members with the sign of the mean.
- **IPC phase:**
  - 2018–2020 analyses: the published area phase.
  - 2022–2025: the area phase is not given in the HDX file. It is **derived with the IPC 20 % rule**: the most
    severe phase such that ≥ 20 % of the population is in that phase or worse.
  - Re-checked for this guide on the 772 area-analyses with a published phase: the rule reproduces the published
    phase **exactly in 92 %**, and within one phase in 100 %.
  - Phase 3+ / 4+ populations are summed over sub-county areas. `ipc_phase3plus_pct` = Phase 3+ population ÷
    population analysed.
- **Rates per 100 000:**
  - `schools_per100k` uses WorldPop 2018.
  - `health_facilities_per100k` uses WorldPop 2025.

### 3.6 National series broadcast
- Some sources have no subnational value. They are written with `county_id` = `SS` (also accepted: `SSD`,
  `national`).
- `build_web_data.py` **copies every national row to all 79 counties**. `build_trends()` does the same for their
  trend rows, so every county shows the same trend and outline.
- Their labels end in "— national", or the metadata says "NATIONAL ONLY".
- **Affected variables:**
  - OCHA FTS funding (monthly and annual), HRP requirement, funding and coverage
  - ForeignAssistance.gov US/USAID/State Dept obligations and disbursements
  - UNMISS budget, expenditure and uniformed personnel
  - FMR national totals and shares, and active monitoring points
  - Georgetown WPS index and its components
  - UN IGME infant and under-5 mortality
  - Insecurity Insight aid-worker, health, education and CRSV incidents
- **Do not compare counties on these layers.** Every county is identical. They are best read in the **national
  timeline** (§1.9) or as context in the hover sparkline.
- The team's unified-dataset README deliberately kept these rows national. The broadcast is a display convenience
  only.
- **State-level values are a different case** (ACLED aggregated sub-event types). They are repeated on the counties
  of one state, so they vary between states but not within a state.

### 3.7 Trend statistics (`scripts/trend_stats.py`)
Trends are computed for every county × variable on the **observed values in 2018-01…2025-12**: no carry-forward,
and only the months present in the processed CSV. The tests are non-parametric. They suit skewed, zero-heavy and
non-normal series and make no assumption that the trend is linear.

**Mann-Kendall (MK)**, for a time-ordered series *x₁…xₙ*:
```
S       = Σ_{i<j} sign(x_j − x_i)
Var(S)  = [ n(n−1)(2n+5) − Σ_t t(t−1)(2t+5) ] / 18      (t = size of each group of tied values)
Z       = (S − 1)/√Var(S)  if S > 0
        = 0                if S = 0
        = (S + 1)/√Var(S)  if S < 0                       (continuity correction)
p       = 2·[1 − Φ(|Z|)]                                  (two-sided)
τ       = S / [n(n−1)/2]                                  (Kendall's tau-a)
```

**Seasonal Kendall** (Hirsch, Slack & Smith 1982), for **monthly** series with ≥ 3 years of data and ≥ 24
observations:
- Compute S_g and Var(S_g) separately for each calendar month *g*, comparing only the same month across years.
- Then S = Σ_g S_g and Var(S) = Σ_g Var(S_g). Z and p are computed as above.
- τ = S / Σ_g n_g(n_g−1)/2.
- This stops the wet/dry seasonal cycle from being mistaken for a trend.

**Sen's slope** (Sen 1968):
- `β = median_{i<j} (x_j − x_i)/(t_j − t_i)`, with *t* in decimal years (year + (month−1)/12), in units per year.
- **Seasonal Sen's slope** = the same median, taken over pairs **within the same calendar month only**.

**% of baseline:**
- `sen_slope_pct_per_year = 100 · β / |mean of the baseline-year values|`.
- The baseline year is 2018 if the county series has 2018 data, else its first year, unless overridden.
- It is left blank if the baseline mean is ~0.

**Which test is used:**
| Series | Test |
|---|---|
| Monthly, ≥ 3 years and ≥ 24 observations | Seasonal Kendall + seasonal Sen |
| Annual, irregular rounds, or short monthly series (n ≥ 4) | Classic MK + Sen on the observed points |
| Static, or n < 4 | Not tested ("Too few observations for a trend test"). This includes the 3-round ISNA series. |

Of 12 249 county-variable tests, 10 580 are seasonal Kendall and 1 669 are classic MK.

**Multiple testing (Benjamini–Hochberg FDR):**
- Within each variable, the 79 county p-values are ranked p₍₁₎ ≤ … ≤ p₍ₘ₎.
- `q₍ₖ₎ = min_{j ≥ k} [ p₍ⱼ₎ · m / j ]`, capped at 1.
- **The white outline uses the unadjusted p < 0.05.** The FDR q-value is shown in the county detail panel.
- Across all tests, **3 884 of 12 249** county-variables have p < 0.05, but only **2 947** have q < 0.05.
- For a claim about "which counties", prefer q < 0.05. Examples:
  - CHIRPS rainfall: 18 counties p < 0.05 → **3** with q < 0.05
  - IOM ET people: 13 → **2**
  - local conflict events: 8 → **0**

**Lag-1 autocorrelation caveat:**
- `lag1` is the lag-1 autocorrelation of the series, after removing each calendar month's mean for monthly series.
- **It is reported but not corrected for.**
- Positive autocorrelation shrinks the true variance of S, so p-values are **too optimistic**.
- Seasonal Kendall also treats the 12 monthly sub-tests as independent. The Hirsch & Slack (1984) covariance
  correction is not applied.
- Median lag-1 values:
  - population 0.96
  - WFP prices 0.78
  - drought ensemble 0.66
  - MERRA-2 temperature 0.57
  - MODIS NDVI 0.58
  - MODIS surface water 0.56
  - most conflict counts ≈ 0–0.3
- Treat significance for **highly autocorrelated** series as indicative. Examples: temperature (77 of 79 counties
  "significant"), drought ensemble (72 of 79), prices, population.
- **Recommended upgrade:** a Hamed–Rao variance correction or Yue–Pilon pre-whitening.

**Other cautions:**
- **Annual series have n ≤ 8.** The smallest achievable two-sided p for n = 8 is ≈ 0.0008, but most annual tests
  have little power.
- **IPC has n ≤ 11**, unevenly spaced, with a 2021 gap.
- **Methodology breaks look like trends:**
  - HNO PiN methods changed in 2019 and 2023.
  - WPS editions are re-based.
  - TerraClimate inherits a CRU/ERA5 discontinuity: 70 of 79 counties show a "significant" `tc_ppt` decline that
    IMERG does not show.
- **Drought ensemble:** the 72 of 79 "significant drying" results come mostly from the two TerraClimate members'
  dry drift (§5). Do not report them as observed drying.
- **Temperature text bug:** `interpret()` writes a "% of 2018 level" phrase for every variable. For °C variables
  (e.g. "+0.8 % of the 2018 level per year" for `tair_c`) this phrase is meaningless; use the °C/yr value. The map
  itself correctly shows units/yr for difference variables.

**Outputs:**
- `data/processed/trends/<source>_trends.csv`, with columns: county_id, variable, test, n, S, Z, τ, p, q_fdr,
  significant, sen_slope_per_year, sen_slope_pct_per_year, baseline_year, baseline_mean, lag1, interpretation.
- Merged into `docs/data/trends.json` by `build_web_data.py`.

**Trend-mode colour scale:**
- The colour span is the 90th percentile of |trend value| across counties: %/yr for ratio variables, with a
  minimum of 1 %/yr; units/yr for difference variables.
- Colour direction follows `higher_is`.

### 3.8 Migration flows (arrows)
Built by `build_flows()` in `build_web_data.py` → `docs/data/flows.json` (102 nodes).

**Sources** (all `month, from_pcode, to_pcode, reason, individuals` in `data/processed/flows/`):

| Key | What one arrow is | Kind | Months in app | Script |
|---|---|---|---|---|
| `et` | People newly displaced or returning in the month (IOM DTM **Event Tracking**). Origin = county left, or a foreign country for cross-border arrivals. Destination = county where IOM assessed the event. | flow | 70 (2020-01…2025-12) | `build_et_flows.py` |
| `fmr` | Forced internal travellers counted at **Flow Monitoring** points: conflict, disaster, food; non-return; SSD→SSD. Covers only routes passing a monitoring point (mostly Renk from 2023). **Blank Nov 2023–Dec 2024**: no public county-level data. | flow | 54 (2020-01…2025-08) | `convert_unified_dataset.py` |
| `dtm_mt_idp_od` | **IDP stock** at a Mobility Tracking round, drawn from the county of habitual residence of the majority of each arrival cohort to the county where they live now | stock | 13 rounds (R4 Dec 2018 … R16 Feb 2025), carried to 85 months | `fetch_flows_dtm_mt_od.py` |
| `dtm_mt_returnee_od` | **Returnee stock**: county of displacement → county of return | stock | as above | as above |
| `dtm_renk_intentions` | Renk transit-centre intention survey (Jul 2024): Renk → intended county. **652 sampled households; 1 273 sample individuals, not scaled.** | survey | 1 | `fetch_flows_dtm_renk_intentions.py` |

**Processing steps:**
1. **Foreign origins** (SDN, ETH, UGA, KEN, CAF, COD) are replaced by **that country's verified crossing nearest
   to the destination county** (squared-degree distance), so arrows start on the drawn border.
2. **Rows are dropped** when:
   - origin = destination (within-county movement), or
   - an endpoint is unknown, or
   - the count is ≤ 0, or
   - the month is outside 2018-01…2025-12.
3. **Reasons are harmonised** to: conflict, disaster, food, sudan_conflict, return_relocation, other.
4. **Stock carry-forward:** each Mobility Tracking round is copied to the following months until the next round,
   for at most 24 months. The arrow tooltip says "stock at the latest survey round, not monthly movement", and the
   status line names the round.

**Rendering in the app:**
- **Best-available priority:** for each month in the window, the app picks the first source with any rows that
  month, in the order **ET → FMR → MT IDP stock**.
  - Returnee stock and Renk intentions are shown only when selected explicitly.
  - Sources are never mixed within a month. In a seasonal or annual window, different months may use different
    sources, and the status line lists each one.
  - In practice: ET from 2020 onwards, the MT stock in Dec 2018–Dec 2019, and **no arrows Jan–Nov 2018**.
- **Window aggregation:** for seasonal or annual windows, the people on each origin→destination→reason arrow are
  **summed** across months.
  - For a carried stock this repeats the same stock once per month, so in seasonal or annual windows read the
    stock **width as relative only**.
- **Width:** `w = max(1.3, min(14, 11·√(n / max_s)))` px.
  - *n* = people on the arrow in the window.
  - *max_s* = the largest single-month arrow of that source.
  - Widths are comparable only within one source.
- **Count:** only the 200 largest arrows are drawn. Arrows are bent to the right of travel so A→B and B→A do not
  overlap.
- **Node anchors:**
  - Counties: the centroid, or, if the centroid falls outside the polygon, a guaranteed interior point.
  - Crossings: the snapped border point (§2.3).

**Stock vs flow:**
- **ET and FMR arrows are flows:** movement *in that month*.
- **Mobility Tracking arrows are stocks:** everyone displaced from A who lives in B at the round date, accumulated
  over years. The two are not comparable in magnitude.
- **Majority attribution** assigns each arrival cohort entirely to its majority origin county.
- **R13 (Aug 2022) is anomalous:**
  - 99 % of origins equal the current county, so cross-county IDP stock falls to 73 k, against 500–725 k in other
    rounds.
  - It also drops 1.42 M IDP and 1.18 M returnee person-entries that have unknown origin, mostly in R13–R16.
  - With the Mobility Tracking source selected, arrows for Aug 2022–Mar 2023 (the months that carry R13)
    under-represent displacement.

---

## 4. Data catalogue

One row per source or variable group. **Coverage** is what the app actually holds on the 2018–2025 grid, taken
from `docs/data/variables.json`, as months with data / 96 and counties with data / 79. **Raw** = folder under
`data/raw/`. Every processed file is `data/processed/<stem>_county_monthly.csv` with `meta/<stem>.json`.

- **Licence column:** taken from the source's `SOURCE.md` or provider page. "HDX" means: check the licence on
  the HDX dataset page before redistributing. ACLED data **may not be redistributed in raw form**.
- **PC** = Microsoft Planetary Computer STAC: free, no login; data streamed and not stored.

### 4.1 Climate and environment

| # | Dataset → variables | Measures | Producer · product / version | Native res. | Coverage in app | County aggregation | Script | Raw | Access · licence |
|---|---|---|---|---|---|---|---|---|---|
| E1 | **CHIRPS** → `chirps_precip_mm` | Monthly rainfall | UCSB Climate Hazards Center · CHIRPS **v3.0** monthly Africa | 0.05° | 96/96 mo · 79 | Area-weighted mean (coverage × cos lat) | `fetch_chirps.py` | `chirps/` (SSD crop .nc) | Open download; cite Funk et al. 2015 |
| E2 | **IMERG** (via NASA POWER, team Drive table) → `precip_mm` | Monthly rainfall | NASA GPM **IMERG V07 Final** (`IMERG_PRECTOT`) | 0.1° | 96 · 79 | POWER cells averaged over county (upstream) | `convert_drive_climate.py` | `drive_mirror/01_analysis_ready/ssd_county_monthly.csv.gz` | NASA open data |
| E3 | **MERRA-2 via NASA POWER** (Drive table) → `tair_c`, `tmax_c`, `tmin_c`, `soilwet_root`, `pet_mm` (Thornthwaite), `spei3` | Air temperature, root-zone wetness, PET, 3-month SPEI | NASA GMAO MERRA-2 via POWER. SPEI-3 = IMERG P − Thornthwaite PET, county 2000–2026 log-logistic fit. | 0.5°×0.625° | 96 · 79 | POWER cells over county; SPEI on county series | `convert_drive_climate.py` | as E2 | NASA open data |
| E4 | **NASA POWER point API** → `power_ws2m`, `power_ws10m`, `power_ws10m_max`, `power_t2m_max`, `power_precip_mm`, `power_aod_550/840` | Wind, hottest hour, bias-corrected precipitation, aerosol optical depth | MERRA-2 (PRECTOTCORR, WS*, T2M_MAX); CERES SYN1deg (AOD) | 0.5°×0.625°; AOD 1° | 96 · 79 | **Centroid sampling** | `fetch_nasa_power.py` | `nasa_power/` (JSON cache) | NASA open data |
| E5 | **TerraClimate** → `tc_ppt`, `tc_tmax`, `tc_tmin`, `tc_aet`, `tc_pet`, `tc_def`, `tc_soil`, `tc_q`, `tc_ws`, `tc_vpd`, `tc_srad`, `tc_pdsi`, `tc_extreme_wet/dry/heat/count` | Water balance, climate, PDSI; percentile flags vs 1991–2020 | Abatzoglou et al. · **TerraClimate v1.1** (NKN THREDDS) | 1/24° (~4 km) | 96 · 79 | Area-weighted mean; flags on the county series | `fetch_terraclimate.py` | `terraclimate/` (subsets not committed, ~350 MB) | CC0 |
| E6 | **Drought ensemble** → `drought_ensemble_mean/spread/range/agree`, `dr_spi3_chirps`, `dr_spei3_tc`, `dr_pdsi_tc_z` | Standardised 3-month drought index and its uncertainty | This project, from E1, E3, E5 (1991–2025 inputs) | county | 96 · 79 | Mean / SD / range / sign agreement of ≥ 3 members | `drought_ensemble.py` | `drought_ensemble/_cache/` (not committed) | Derived (inherits input licences) |
| E7 | **MODIS vegetation** → `modis_ndvi`, `modis_evi` | Greenness | NASA LP DAAC **MOD13A1 + MYD13A1 v061** (16-day) via PC | 500 m → 0.01° | 93 · 79 (missing 2025-08…10) | Monthly per-pixel max; mean of valid cells | `fetch_modis_land.py`, `make_modis_rasters.py` | `modis_land/` (streamed) | NASA open data |
| E8 | **MODIS LST** → `modis_lst_day_c`, `modis_lst_night_c` | Clear-sky land-surface temperature | **MOD11A2 v061** (Terra, 8-day) via PC | 1 km | 91 · 79 (missing 2022-10, 2025-07…10) | Monthly mean of clear composites (QA good, error ≤ 2 K) | `fetch_modis_land.py` | as E7 | NASA open data |
| E9 | **MODIS reflectance** → `modis_refl_red/nir/swir1` | Surface reflectance | **MOD09A1 v061** (Terra) via PC | 500 m | 92 · 79 | Monthly mean of clear composites | `fetch_modis_land.py` | as E7 | NASA open data |
| E10 | **MODIS ET, annual** → `modis_et_mm` | Actual evapotranspiration | **MOD16A3GF v061** via PC | 500 m | 8 years · 79 | Mean of valid cells (water, urban and barren pixels are fill) | `fetch_modis_land.py` | as E7 | NASA open data |
| E11 | **MODIS ET, monthly (AppEEARS)** → `modis_et_monthly_mm` | Actual ET | **MOD16A2GF v061** via NASA AppEEARS | 500 m → ~1 km | **48/96 (2018–2021 only)** · 79 | 8-day totals prorated to months by day overlap; cells need ≥ 75 % valid days | `fetch_appeears.py` | `$APPEEARS_WORK` cache | NASA open data; Earthdata login. ⏳ pending: 2022–2025 |
| E12 | **AppEEARS other products** → `modis13a3_ndvi/evi`, `appeears_lst_*` (2022–25), `appeears_burned_area_*`, `smap_sm_surface/rootzone` (SMAP L4 SPL4SMGP.008) | MODIS fill of Jul–Oct 2025; soil moisture | NASA AppEEARS | 1 km; SMAP 9 km | ⏳ pending: not yet in `data/processed` | Same as E11 | `fetch_appeears.py` | — | Earthdata login. **Night lights (VNP46A3) are not offered by AppEEARS.** |
| E13 | **MODIS active fire** → `fire_count` | Fire pixel-detections per month (Terra + Aqua daily) | **MOD14A1/MYD14A1 v061** via PC | 1 km | 91 · 79 (missing 2025-07…11) | Native-grid count, all confidence levels; scaled for missing sensor-days | `fire_pipeline.py` | `fire/` (counts) | NASA open data |
| E14 | **VIIRS active fire (FIRMS)** → `viirs_fire_count`, `viirs_frp_sum` (S-NPP 2018–25); `viirs_noaa20_*` (2020–25) | Fire detections, fire radiative power | NASA FIRMS **VIIRS 375 m SP, collection 2** (VNP14IMG / VJ114IMG) | 375 m | 96 · 79 (NOAA-20: 72) | Point-in-polygon; confidence nominal/high; type 0 only (gas flares removed) | `fetch_firms_viirs.py` | `viirs_fire/` (filtered detections) | NASA open data; free MAP_KEY |
| E15 | **MODIS burned area** → `burned_area_km2`, `burned_area_pct` | Burned area per month | **MCD64A1 v061** via PC | 500 m | 90 · 79 (missing 2023-09, 2024-07, 2025-05, 2025-08…10) | Burned pixels × 0.2147 km² | `fire_pipeline.py` | `fire/` | NASA open data |
| E16 | **MODIS surface water** → `surface_water_km2`, `surface_water_pct`, `surface_water_obs_pct` | Open-water / shallow-inundation extent; cloud-free coverage flag | This project: MNDWI(B4, B7) > 0.1 on **MOD09A1 + MYD09A1 v061** | 500 m, 8-day | 92 · 79 (missing 2025-07…10) | Native-grid share of known pixels; 2-month gap fill | `water_pipeline.py`, `water_validate_unosat.py` | `water/` (checkpoint) | NASA open data |
| E17 | **Sentinel-1 SAR flood** → `flood_s1_flood_km2/_pct`, `flood_s1_openwater_km2`, `flood_s1_obs_pct` | Flood beyond the dry-season state, incl. flooded vegetation | This project, on **Sentinel-1 IW GRD RTC** (PC `sentinel-1-rtc`, VV+VH) | 10 m read at 160 m → 0.004° (~440 m) | ⏳ pending: monthly grids exist for 96/96 months (`data/raw/s1_flood/grids/`); `finalize` (county CSV, meta) and validation not yet written | Change detection vs the pixel's March VV−VH reference (> 3 dB) OR open water (VV < −18 and VH < −24 dB) | `flood_s1_pipeline.py`, `flood_s1_validate.py` | `s1_flood/` (grids not committed) | Copernicus open data |
| E18 | **Flood exposure** → `flood_population_exposed(_pct)`, `flood_oilfield_exposure_km2`, `flood_oil_wells_flooded` | People and oil infrastructure in flooded cells (contamination-pathway proxies) | This project: E17 × WorldPop × oil points | ~440 m / 1 km | ⏳ pending: depends on E17 | Flooded fraction × population; flood area within 5 km of wells and fields | `flood_exposure.py` | — | Derived |
| E19 | **Sentinel-5P TROPOMI** → `s5p_no2`, `s5p_co`, `s5p_aerosol_index` | Tropospheric NO₂, CO column, UV aerosol index | Copernicus **S5P L2 OFFL/RPRO** via PC | 5.5×3.5 km (7×3.5 before Aug 2019) | 91–92 · 79 (from 2018-05/06) | Swath binning to 0.05°; **4 sampled orbits/month** | `s5p_pipeline.py` | `s5p/` (grid cache) | Copernicus open data |
| E20 | **Land cover** → `lulc_water/trees/flooded_veg/crop/built/bare/rangeland_pct` | Annual class shares | Esri / Impact Observatory **io-lulc-annual-v02** (Sentinel-2) via PC | 10 m (sampled at 80 m) | 2017–2023 (6 years in window) · 79 | 1-in-64 systematic-sample class share | `landcover_pipeline.py` | — | CC BY 4.0 |
| E21 | **Static environment** → `soil_*` (clay, sand, SOC, pH, WRB, Vertisol %), `elevation_mean/std`, `richness_*` | Soil, terrain, species richness | ISRIC **SoilGrids 2.0**; **Copernicus DEM GLO-90**; **BiodiversityMapping.org** 2019 (IUCN/BirdLife ranges) | 250 m (read 1 km); 90 m; 10 km | static · 79 | County mean / mode / share | `static_pipeline.py` | `soilgrids/`, `biodiversity/` | CC BY 4.0; Copernicus; free with citation |
| E22 | **Livestock** → `cattle_head`, `cattle_density`, `goats_head`, `sheep_head` | Modelled 2015 head counts | FAO **GLW4 2015** (Gilbert et al. 2018), dasymetric | ~9 km | static · 79 | Sum of pixels with centre in county | `livestock_glw4.py` | `glw4/` | CC BY 4.0 |
| — | **UNOSAT flood maps** (validation only) | Satellite-detected water extents (VIIRS-based) | UNITAR/UNOSAT via HDX | event polygons, state tables | 30 exposure tables 2022-10…2025-04; pixel maps 2021–22 | State sums | `water_validate_unosat.py`, `flood_s1_validate.py` | `unosat_floods/` | HDX |
| — | Not used (checked): **FloodScan** (only the last 90 days free), **GFM** (needs an account; STAC returned 502), **MCDWD NRT flood**, **GRACE/GLDAS**, **JRC GSW monthly** (ends 2021) | — | — | — | — | — | — | `floodscan/SOURCE.md` | See §6 |

### 4.2 Conflict, security and protection

| # | Dataset → variables | Measures | Producer · product / version | Native res. | Coverage in app | County aggregation | Script | Raw | Access · licence |
|---|---|---|---|---|---|---|---|---|---|
| H1 | **ACLED admin-2 aggregates** → `acled_pv_events`, `acled_pv_fatalities`, `acled_civ_events`, `acled_civ_fatalities`, `acled_demonstrations` | Political violence, civilian targeting, demonstrations | ACLED public HRP aggregates via HDX (re-published weekly) | admin-2 × month | 96 · 79 (Abyei from the Sudan file) | Name/code join; true zeros | `acled_ssd.py` | `acled/` | ACLED terms of use (no raw redistribution) |
| H2 | **ACLED aggregated weekly, state** → `acled_st_*` (sexual violence, abduction, civilian attacks, looting, armed clashes, territory change, remote violence, air/drone, protests, riots, population exposure) | Sub-event detail | ACLED Data Export Tool, aggregated, admin-1 (team export 15 Nov 2026) | **state** × week | 96 · **78** (no Abyei) | Weeks → month of week start; **state total on every county** | `acled_state_weekly.py` | `acled_aggregated/` | ACLED terms of use |
| H3 | **UCDP GED** → `ucdp_events`, `ucdp_deaths_best`, `ucdp_civilian_deaths`, `ucdp_{state_based, non_state, one_sided}_{events, deaths}` | Lethal organised-violence events | Uppsala Conflict Data Program · **GED v26.1** | event points | 96 · 79 | Point-in-polygon, `where_prec` ≤ 3 only | `ucdp_ssd.py`, `points_events.py` | `ucdp/` (SSD subset) | CC BY 4.0 |
| H4 | **Local (intra-county) conflict** → `intracounty_conflict_events/deaths`, `intracounty_communal_events/deaths` | Violence between or by communal groups and local militias | This project: actor-name classification of H3 non-state and one-sided events | event points | 96 · 79 (198 events 2018–25) | As H3 | `intracounty_conflict.py` | as H3 | Derived |
| H5 | **Insecurity Insight** → `ii_aid_worker_incidents`, `ii_health_attacks`, `ii_education_attacks`, `ii_sexual_violence_incidents` | Reported incidents against aid workers, health care, education; CRSV | Insecurity Insight SiND via HDX | **national** (coordinates censored; state only) | 96 (CRSV 72) · broadcast | National monthly count; points at state centroids | `fetch_insecurity_insight.py` | `insecurity_insight/` | CC BY-SA 4.0 |
| H6 | **ISNA (MSNA) WASH and GBV-risk** → `isna_water_30min_plus_pct`, `isna_unsafe_water_collect_pct`, `isna_surface_water_source_pct`, `isna_open_defecation_pct`, `isna_wg_avoid_water_points/latrines/any_pct` | Household-reported water access, sanitation, women's and girls' safety | REACH/IMPACT for OCHA/ICCG · ISNA **2022, 2023, 2024** county tables (HDX) | county (household survey, ~100–300 HH) | **3 rounds** (Jul 2022–Jul 2024) · 79 | Weighted % of households (as published) | `isna_msna.py` | `isna/` | HDX |
| H7 | **Georgetown WPS Index** → `wps_index`, `wps_rank`, and 7 components | Women's inclusion, justice, security | GIWPS editions 2017/18…2025/26 | **national** | 5 editions · broadcast | National value | `wps_national.py` | `wps/` | Free with citation |

### 4.3 Displacement and mobility

| # | Dataset → variables | Measures | Producer · product / version | Native res. | Coverage in app | County aggregation | Script | Raw | Access · licence |
|---|---|---|---|---|---|---|---|---|---|
| D1 | **IOM DTM Event Tracking** (team unified, harmonised) → `et_ind_*` (by cause and arrival origin), `et_events*` | People newly displaced or returning, per month | IOM DTM South Sudan Event Tracking 2020–2026 | county of arrival | Dec 2019–Dec 2025 (73 mo) · 79; baseline 2020 | As supplied (zero-filled) | `convert_unified_dataset.py`; `dtm_ssd.py` (older `dtm_et_*`, hidden) | `ssd_unified/`; Drive | HDX / IOM terms |
| D2 | **IOM DTM Flow Monitoring** → `fmr_departed_*`, `fmr_arrived_*`, `fmr_within_*`, `fmr_monitoring_points_in_county`; national `fmr_internal_forced_*`, `fmr_all_movements_observed`, `fmr_conflict_share_all_movements`, `fmr_active_monitoring_points` | Forced internal travellers at monitoring points | IOM DTM FMR (team extract + HDX Nov22–Oct23 workbook + monthly reports) | monitoring point → county | Jan 2020–Aug 2025; **blank Nov 2023–Dec 2024** (county) | As supplied | `convert_unified_dataset.py` | `ssd_unified/` | HDX / IOM terms |
| D3 | **IOM DTM Mobility Tracking baseline** → `dtm_idps`, `dtm_returnees` | IDP and returnee stock | IOM DTM Baseline Assessment **R2, R4–R16** (HDX) | location → county | **14 rounds** (2018-06…2025-02) · 78 (no Abyei) | Sum over locations. (The DTM API / HAPI admin-2 figures are 4× the national total, so they are **not used**.) | `dtm_ssd.py` | `dtm/baseline/` | HDX / IOM terms |
| D4 | **Mobility Tracking O-D** → flow arrows `dtm_mt_idp_od`, `dtm_mt_returnee_od` | Stock by county of origin | IOM DTM MT R4–R16 (HDX + dtm.iom.int payam files R5–R12, saved by hand) | payam → county | 13 rounds | Majority-origin attribution | `fetch_flows_dtm_mt_od.py` | `flows/dtm_mt_od/` | IOM terms |
| D5 | **Renk intention survey** → arrows `dtm_renk_intentions` | Intended destinations | IOM DTM, Jul 2024 (652 HH) | household sample | 1 month | Unscaled sample | `fetch_flows_dtm_renk_intentions.py` | `flows/dtm_renk_intentions/` | IOM terms |
| D6 | **UNHCR** → `unhcr_refugees` | Refugees and asylum-seekers hosted (end-year stock) | UNHCR Refugee Data Finder via HDX | camp/settlement | 8 years · **18 counties** | Hand camp → county mapping; dispersed/state rows unallocated | `unhcr_ssd.py` | `unhcr/` | HDX |
| D7 | **Population** → `pop_total` (WorldPop), `population_estimate` (OCHA COD-PS 2022 v2) | Population | WorldPop **Global2 R2025A** constrained 1 km, UN-adjusted; OCHA COD-PS | 1 km; county | 8 years · 79; COD-PS 2022 & 2025 | Pixel sum (Abyei from the SDN grid) | `pop_worldpop.py`; `convert_unified_dataset.py` | `worldpop/` | CC BY 4.0; HDX |

### 4.4 Food security, humanitarian needs and response

| # | Dataset → variables | Measures | Producer · product / version | Native res. | Coverage in app | County aggregation | Script | Raw | Access · licence |
|---|---|---|---|---|---|---|---|---|---|
| F1 | **IPC acute food insecurity** → `ipc_phase3plus_pop/_pct`, `ipc_phase4plus_pop`, `ipc_phase_class` | People in IPC Phase 3+/4+; area phase | IPC via HDX (global country file 2017–2023 + SSD area file 2022+) | IPC analysis area (county or payam) | **11 analyses** (2018-01…2025-09; **none in 2021**) · 79 | Sum of sub-county areas; phase published (2018–20) or **20 %-rule derived (2022+)** | `ipc_ssd.py` | `ipc/` | HDX |
| F2 | **IPC acute malnutrition** → `ipc_amn_phase`, `gam_prevalence_pct` | AMN phase, GAM prevalence | IPC AMN projection update (HDX) | county | **1 snapshot** (Jul–Sep 2025) | As published | `ipc_ssd.py` | `ipc/` | HDX |
| F3 | **WFP market prices** → `price_*_ssp/_usd` (sorghum, maize, wheat flour, beans, groundnuts, cooking oil, diesel, petrol), `wage_casual_labour_*`, `fx_ssp_per_usd` | Retail prices, wages, parallel exchange rate | WFP VAM via HDX | market | 39–92 mo · **26–32 counties** | Median over county markets | `wfp_prices_ssd.py`, `points_markets.py` | `wfp_prices/` | HDX |
| F4 | **OCHA HNO** → `hno_pin`, `hno_severity` | People in need (intersectoral); severity 1–5 | OCHA HNO county workbooks (2019, 2021–23) + HDX HAPI (2024–25) | county | PiN: HNO 2019, 2021–2025 (none for 2018/2020); severity 2022–24 | As published | `ocha_hum_ssd.py` | `ocha_hno/`, `hdx_hapi/` | HDX |
| F5 | **OCHA 3W** → `ops_orgs`, `ops_orgs_national_ngo` | Distinct humanitarian organisations reporting activity | OCHA 3W operational presence (HDX) | county × month | Jan 2019–Dec 2025 (Dec 2020 missing) · 79 | Distinct organisations | `ocha_hum_ssd.py` | `ocha_3w/` | HDX |
| F6 | **Aid funding (national)** → `fts_*`, `hrp_*`, `us_aid_*`, `usaid_*`, `state_dept_*` | Humanitarian funding (FTS, by decision month); HRP requirement and coverage; US obligations and disbursements | OCHA FTS API; ForeignAssistance.gov transaction file | **national** | 96 · broadcast | National value | `convert_unified_dataset.py` | `ssd_unified/` | FTS open; US public domain |
| F7 | **UNMISS** → `unmiss_presence`, `unmiss_troops` (annual, Geo-PKO v2.3 + map 4456 Rev.62); `unmiss_deployment_sites_in_county` (2023-12+); national `unmiss_uniformed_personnel`, `unmiss_budget_fy_usd`, `unmiss_expenditure_fy_usd` | Peacekeeping footprint and resources | Geo-PKO v2.3 (Cil et al. 2020); UN map 4456; UN DPO (HDX); A/RES/79/309 | deployment location; national | 8 years · 79; personnel 96 | Sum of troop estimates at locations, mean over map timepoints | `unmiss_deployments.py`, `points_unmiss.py`, `convert_unified_dataset.py` | `geopko/`, Drive PDFs | Geo-PKO with citation; HDX |
| F8 | **Logistics Cluster hubs** → `logcluster_hubs_in_county`; points layer | Common storage and hubs | WFP Logistics Cluster CONOPS maps (16 dated maps 2018–2026) | site | Dec 2019–Dec 2025 (county series); points 2018–2026 | Count of hubs; PDF extraction | `convert_unified_dataset.py`, `points_logcluster_hubs.py` | `logcluster/` | Public PDFs |

### 4.5 Services, infrastructure and social context (mostly static)

| # | Dataset → variables | Measures | Producer · product / version | Native res. | Coverage in app | County aggregation | Script | Raw | Access · licence |
|---|---|---|---|---|---|---|---|---|---|
| S1 | **Health facilities** → `health_facilities`, `hospitals`, `*_per100k`; points | Listed facilities | WHO/MoH Master Facility List, Apr 2025 (list as of Mar 2024) | point | static · 79 | Count by county code; WorldPop 2025 denominator | `health_facilities.py`, `points_snapshots.py` | `health/` | CC BY |
| S2 | **Schools (2015)** → `schools_count`, `schools_per100k`, `edu_enrolment`, `edu_girls_share`; points (+ OSM) | Open schools, enrolment by sex | SSSAMS 2015 (HDX) + OSM education (HOT) | point | static (2015) · 78–79 | Count; enrolment sums over reporting schools (~3 300 of ~4 900) | `education.py`, `points_snapshots.py` | `education/`, `osm/` | CC0; ODbL |
| S3 | **Immunisation 2018** → `vacc_penta3_cov`, `vacc_mcv1_cov` | Administrative coverage | WHO/UNICEF sub-national admin data (HDX) | county | **2018 only** · 78 | Doses ÷ target × 100 (often > 100 %) | `public_health.py` | `public_health/` | CC BY |
| S4 | **Child mortality** → `u5mr_national`, `imr_national` | U5MR, IMR | UN IGME via UNICEF SDMX | **national** | 2018–2024 · broadcast | National estimate | `public_health.py` | — | Open |
| S5 | **Oil** → `oil_fields_count`, `oil_wells_osm`, `oil_pipeline_km`; points with status periods; pipeline lines | Oil infrastructure | GEM GOGET (Mar 2026), GEM GOIT (Jun 2026), OSM (HOT), Overture 2026-10-21.0, PRIO PETRODATA v1.2 | point/line | static · 79 | Counts; line length | `oil_infrastructure.py`, `points_oil_status.py` | `oil/`, `osm/` | CC BY 4.0; ODbL |
| S6 | **Ethnic geography** → `ethnic_groups_count`, `ethnic_dominant_share`, `ethnic_excluded_share`; polygons | Settlement areas of 10 politically relevant groups; EPR status | ETH Zurich ICR · **GeoEPR 2021 + EPR 2021** | polygon | static · 73–79 | Area shares (> 2 % threshold for count) | `ethnic_groups.py` | `ethnic/` | Free with citation |
| S7 | **Water points** → points only | WPDx water points (status mostly pre-2018) | WPDx-Basic (6 099 SSD points) | point | snapshot | — | `points_water_points.py` | `wpdx/` | CC BY 4.0 |
| S8 | **Crisis sites** → points only | PoC sites, IDP and refugee camps, transit centre | Curated: OSM, UNMISS/UNHCR/IOM lists, UNMISS press releases | point | periods 2018–2025 | — | `crisis_sites.py`, `points_crisis_sites.py` | `osm/`, `gazetteer/` | ODbL / public |
| S9 | **District profiles** → hover card | Livelihood zone, history, conflict narrative, key facts | FEWS NET LHZ 2018; CSRF county profiles; UNMISS HRD reports; computed key facts | county | static text | Area overlay (EPSG:6933) | `build_district_profiles.py` | `fews_lhz/`, `district_profiles_narrative.json` | See `district_profiles_sources.md` |
| S10 | **Team Drive mirror** | All Drive files. Most of `01_analysis_ready` is from earlier Sahel work; the SSD files are `ssd_*`, `IOM_DTM_SSD_*`, UNMISS PDFs, and the boundaries. | Team | — | — | — | `mirror_drive.sh` | `data/drive_mirror/` | Team |
