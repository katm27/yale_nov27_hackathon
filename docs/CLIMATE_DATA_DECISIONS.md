# Climate and environment data decisions

South Sudan county map, 79 counties, monthly 2018–2025, indexed to 2018. This document reviews every environmental
variable in the app, explains the flood-product choice and the drought ensemble, and states which contamination and
gender/water indicators can be measured. Reviewed 15 Nov 2026.

Each variable gets a class, which says where its numbers come from:
- **Obs**: a direct observation or a physical retrieval from one instrument (reflectance, backscatter, brightness temperature, gauge).
- **Merged**: a satellite retrieval blended with gauges or with other satellites (IMERG, CHIRPS).
- **Model**: reanalysis or a land-surface or water-balance model forced by other data (MERRA-2, TerraClimate, GLW4).
- **Derived**: an index computed from one of the classes above (SPEI, PDSI, MNDWI water, flood exposure).

It also gets a recommendation:
- **Primary**: the default layer for its topic.
- **Secondary**: keep it for cross-checking.
- **Context**: static or annual background.
- **Drop**: remove it, or hide it from the default view.

## 1. Variable-by-variable review

| Variable(s) | Class | Producer, algorithm, version | Resolution, latency | Known issues in South Sudan | Rec. |
|---|---|---|---|---|---|
| `chirps_precip_mm` | Merged | UCSB CHC, **CHIRPS v3.0** (IR cold-cloud duration + CHPclim + station blend; ERA5 used where IR is weak) | 0.05°, monthly; prelim ~2 days, final ~3 weeks | Very few GTS gauges in SSD, so it falls back to IR climatology. It is **-30 to -48 %** below IMERG in Sudd counties (Rubkona, Guit, Mayendit). Its 2018–2025 trend is **-25 mm/yr per yr**, while IMERG gives **+5** (docs/VALIDATION_rainfall.md). | **Primary** for rainfall level and spatial detail |
| `precip_mm` (drive_climate) | Merged | NASA GPM **IMERG V07 Final** (passive-microwave + IR morphing, monthly GPCC gauge calibration), via NASA POWER | 0.1°, ~3.5 months latency | Passive microwave over wetland or flooded surfaces is noisy. Anomaly r with CHIRPS is only 0.33. Little dry bias. | **Secondary** (independent of CHIRPS; used in SPEI) |
| `power_precip_mm` | Model | MERRA-2 PRECTOTCORR (bias-corrected toward GPCP), NASA POWER | 0.5°×0.625°, ~1 month | Reanalysis convection is too smooth, and at county scale it is near-duplicate information. | **Drop** from the default view (keep in data) |
| `tc_ppt` | Model / interp. | **TerraClimate v1.1** (Abatzoglou et al. 2018). Climatically-aided interpolation: WorldClim normals plus CRU-TS / JRA-55 (ERA5 from 2023+) anomalies | 1/24°, annual release, ~1 year latency | **~40 % drier** than IMERG/CHIRPS. Its 2018–25 values sit far below its own 1991–2020 normals, which looks like an inherited CRU/ERA5 discontinuity, not a real drought. | **Secondary** (relative patterns only) |
| `tair_c`, `tmax_c`, `tmin_c` | Model | MERRA-2 T2M via POWER | ~50 km, ~1 month | It smooths the Sudd-highland contrast. Reanalysis trends are plausible but not station-verified. | **Primary** for temperature trend, because it is homogeneous |
| `tc_tmax`, `tc_tmin` | Model | TerraClimate | ~4 km | Same anomaly source as above, downscaled. | Secondary |
| `modis_lst_day_c`, `modis_lst_night_c` | Obs | MODIS MOD11A2 v061 (split-window), Terra | 1 km, 8-day, ~1 week | Clear-sky only, so wet-season months are biased toward dry days. | Secondary (surface heat) |
| `power_t2m_max`, `power_ws*` | Model | MERRA-2 via POWER | ~50 km | Wind has no clear human link. | Drop from the default view |
| `tc_ws` | Model | TerraClimate | ~4 km | Same as above. | Drop |
| `soilwet_root` | Model | MERRA-2 GWETROOT (Catchment LSM) | ~50 km | It is driven by MERRA-2 precipitation and knows nothing about floodplain inundation. | Secondary |
| `tc_soil` | Model | TerraClimate one-layer bucket | ~4 km | Inherits the tc_ppt dry bias. | Secondary |
| SMAP (other agent) | Obs | SMAP L-band radiometer (L3/L4) | 9–36 km | Starts 2015. Water and flood pixels are flagged. Retrievals over the Sudd are unreliable (open water). | Owned elsewhere |
| `pet_mm` | Derived | Thornthwaite from MERRA-2 T2M | ~50 km | Thornthwaite **underestimates PET in hot semi-arid climates** and ignores VPD and wind. | Secondary; prefer `tc_pet` (Penman-Monteith) for magnitude |
| `tc_pet`, `tc_aet`, `tc_def`, `tc_q` | Model | TerraClimate (Penman-Monteith; Thornthwaite-Mather bucket) | ~4 km | Inherits the tc_ppt dry bias, so def is overstated and q is understated. | Secondary |
| `modis_et_mm` (annual), monthly ET (other agent) | Model / obs | MOD16A3GF v061 (Penman-Monteith with MODIS LAI/albedo + GMAO met) | 500 m | Fill over open water and urban pixels. It misses Sudd wetland ET. | Secondary |
| `spei3` | Derived | SPEI-3: IMERG P minus Thornthwaite PET, log-logistic, county series 2000–2026 | county | Short baseline (≤26 yr), and Thornthwaite PET (see above). | **Member** of the drought ensemble |
| `tc_pdsi` | Derived | TerraClimate PDSI (Palmer) | ~4 km | The raw national mean is **-6.6**, which is meaningless as absolute severity (see tc_ppt). It has 9–12-month memory. | Keep only re-standardised (`dr_pdsi_tc_z`) |
| `tc_extreme_*` | Derived | Percentile flags vs 1991–2020 TerraClimate | ~4 km | `tc_extreme_dry` fires far too often because of the dry bias. | Secondary; use with care |
| **`drought_ensemble_mean`, `_spread`** (new) | Derived | This repo, `scripts/drought_ensemble.py` (see §3) | county | See §3. | **Primary** drought layer + uncertainty |
| `modis_ndvi`, `modis_evi` | Obs | MOD13A1 + MYD13A1 v061 (16-day MVC, pixel reliability) | 500 m | Flooding lowers NDVI (water), so a "greenness drop" in the Sudd can be a flood, not a drought. | **Primary** vegetation |
| `modis_refl_*` | Obs | MOD09A1 v061 | 500 m | Raw bands, with no direct meaning for users. | Drop from the default view |
| `surface_water_*` | Derived | MODIS MOD09A1/MYD09A1 MNDWI(B4,B7) > 0.1 (this repo) | 500 m, 8-day composites | Cloud blocks most of Jun–Oct. It **misses water under vegetation**. Vs UNOSAT it is **~0.5×** in area (state r 0.76; dry-season r 0.82, better than S1). | **Secondary**, all-season (dry-season/receding water) |
| **`flood_s1_*`** (new) | Derived | Sentinel-1 C-band SAR RTC (Catalyst gamma0), this repo: VV−VH change detection (see §2) | 10 m read at 160 m, ~440 m grid, monthly | It under-detects receding dry-season water (F1 0.04), and revisit is thinner in 2022–24. | **Primary** flood layer for Jul–Nov |
| `fire_count`, `burned_area_*`, `viirs_*` | Obs | MODIS MOD14A1/MCD64A1 v061; VIIRS 375 m (FIRMS) | 375 m–1 km | Cloud and smoke cause omission. MCD64A1 has missing months on Planetary Computer. | VIIRS **primary** for counts, MCD64A1 for burned area |
| `s5p_no2`, `s5p_co`, `s5p_aerosol_index` | Obs | Sentinel-5P TROPOMI L2 OFFL/RPRO | 3.5×5.5 km | NO₂ is near the detection limit outside Juba and fires, and only 4 orbits per month are sampled. | Secondary (`s5p_no2` as an oil/flaring signal only near oil fields) |
| `power_aod_*` | Model / obs | CERES SYN1deg (MODIS-assimilated) | 1° | Too coarse for counties. | Drop |
| `lulc_*` | Derived (ML) | Esri / Impact Observatory 10 m LULC v02 (Sentinel-2) | annual, 2017–2023 | Classifier changes between years. "Flooded vegetation" is a useful annual flood-footprint check. | Context |
| Night lights, monthly ET, SMAP (other agents) | Obs | VIIRS DNB VNP46A3; MOD16A2; SMAP | — | Reviewed by their owners. | — |
| `soil_*`, `elevation_*`, `richness_*` | Static | SoilGrids 2.0, Copernicus DEM, BiodiversityMapping | — | Static, so not a trend. | Context |
| `cattle_*` | Model | FAO GLW4 (2015, random-forest disaggregation of old census) | ~10 km, static | No transhumance, and the census inputs are 2008-era. | Context |

For rainfall, no product can be taken as the truth, because South Sudan has almost no reporting gauges. Show CHIRPS
by default and show where IMERG and CHIRPS disagree. Do not report a rainfall trend that appears in only one
product: over 2018–2025 CHIRPS falls, IMERG rises and TerraClimate falls.

## 2. Flood product decision

What we needed: county-month flood extent for 2018-01 to 2025-12 that works through wet-season cloud and in the Sudd,
where most flood water stands under grass, papyrus or Typha.

| Option | Coverage | Access from this environment | Sees through cloud | Water under vegetation | Verdict |
|---|---|---|---|---|---|
| Our MODIS MNDWI (`water_county_monthly.csv`) | 2018–2025 | done | no (Jun–Oct gaps, carried forward) | no | Secondary (optical cross-check) |
| UNOSAT VIIRS flood maps (HDX) | event-based, 2019–2025, about 60 dates | open | partly (5-day VIIRS composites) | yes, partly (VIIRS flood algorithm) | **Validation only** (irregular dates) |
| NASA MODIS NRT Global Flood Product (MCDWD) | 2021+ (NRT archive) | needs Earthdata login (urs.earthdata.nasa.gov **not reachable**) | no | no | Not possible; would also miss 2018–2020 |
| Copernicus GFM (Sentinel-1, 3-algorithm ensemble) | 2015+ | EODC STAC **returned HTTP 502**. The API needs a GFM account. | yes | partly (open water only by design; flooded vegetation is excluded) | Best on paper, not accessible. Revisit if an account is available. |
| FloodScan (AER, passive microwave) | 1998+ | the HDX "free" admin-2 file holds **only the last 90 days** (Aug–Nov 2026 checked; 79 SSD pcodes). History is commercial. | yes | yes (fraction of a ~10 km cell) | Not possible for 2018–2025 |
| JRC Global Surface Water monthly history | 1984–**2021** (v1.4) | open tiles | no (Landsat) | no | Context only (ends 2021, cloud-limited) |
| **Sentinel-1 RTC via Planetary Computer, this repo** | 2018–2025 (S1A+B to Dec 2021, then S1A only; S1C from 2025) | **open, done** | **yes** | **yes**, with a VV−VH ratio change rule | **Chosen** (wet-season primary) |

### How the Sentinel-1 layer is built

Code and outputs: `scripts/flood_s1_pipeline.py`, `data/processed/flood_s1_county_monthly.csv`, `meta/flood_s1.json`,
overlay `docs/rasters/flood_s1/` (96 months, 79 counties).
- **Inputs.** Every Sentinel-1 IW GRD RTC scene (gamma0, VV and VH) over the country is used, 70–183 per month. Each
  is read at its 1/16 COG overview (160 m). That overview is a block average of the 10 m linear power, so speckle is
  suppressed.
- **Grid.** Scenes are converted to dB and averaged onto a fixed 0.004° (~440 m) grid, giving a monthly mean per pixel.
  The intermediate grids are 0.85 GB in `data/raw/s1_flood/_cache/grids/`, which is gitignored.
- **First attempt: absolute thresholds (rejected).**
  - A classic low-backscatter rule (VV < −18 dB) finds about 0 km² in October 2022, when UNOSAT mapped 48 000 km².
    Sudd flood water stands under grass, papyrus or Typha and is radar-**bright**: double bounce raises VV far more
    than VH. Inside the UNOSAT polygons the median VV−VH is 9.0 dB; outside it is 5.5 dB.
  - An absolute "VH < −17 or VV−VH > 8.5" rule fits October (F1 0.61) but fails in the dry season, where pixel F1
    against the January, March and May 2022 UNOSAT maps is 0.03–0.10. Dry grassland and cracking clay are darker than
    the vegetated swamp UNOSAT counts as water, and about 230 000 km² was flagged as "open water".
- **Final rule: change detection.**
  - The reference is the per-pixel median of the **March** VV−VH ratio over 2018–2025.
  - **Flooded** = monthly VV−VH more than **3 dB above the reference**.
  - **Open water** = VV < −18 and VH < −24 dB.
  - Permanent swamp is part of the reference, so it is not counted as flood.
  - The 3 dB threshold was chosen on one date: UNOSAT 4–8 Oct 2022, new water vs 10–14 Mar 2022 (F1 0.59, area ratio
    0.95).
- **Gap filling.** Pixels with no acquisition inherit the previous month (max 2 months). County-months with less than
  50 % of the area known are dropped.
- Variables: `flood_s1_flood_km2` and `flood_s1_flood_pct` (index_ok false), `flood_s1_openwater_km2`, and
  `flood_s1_obs_pct` (a quality flag).

National flood peaks (Sep–Oct):

| Year | Peak flood area |
|---|---|
| 2018 | low |
| 2019 | 15 500 km² |
| 2020 | 28 000 km² |
| 2021 | 30 000 km² |
| 2022 | 33 000 km² |
| 2023 | 14 000 km² |
| 2024 | 24 000 km² |
| 2025 | 26 000 km² |

The layer picks up the 2020–2022 Sudd mega-flood and the 2024 flood. The dry-season minimum is 200–1 500 km².

### Validation against UNOSAT

Code and outputs: `scripts/flood_s1_validate.py`, `data/processed/validation/flood_s1_vs_unosat_*.csv`.

*Pixel level.* New flood (UNOSAT water on the date minus the UNOSAT 10–14 Mar 2022 water) vs the S1 flood class, with
cloud-obstructed areas excluded. 19 independent dates, Sep 2021–Sep 2022:

| Season | Dates | Median F1 | Range | Precision | Recall | Area ratio S1/UNOSAT |
|---|---|---|---|---|---|---|
| **Wet season (Jul–Nov)** | 10 | **0.51** | 0.43–0.61 | 0.64 | 0.52 | 0.80 |
| **Dry season (Jan–Jun)** | 9 | **0.04** | — | — | — | 0.12 |

In the dry season S1 does not see the receding flood UNOSAT still maps. That water is shallow or standing under
drying vegetation, and it is close to the reference state.

*State level.* 30 UNOSAT exposure tables, Oct 2022–Apr 2025, 250 state-dates. UNOSAT totals include permanent swamp,
while the S1 flood class does not.

| Comparison | Wet-season months, r | Dry-season months, r | Overall, r | Median area ratio vs UNOSAT |
|---|---|---|---|---|
| S1 flood | **0.88** | 0.41 | 0.62 | 0.38 |
| MODIS MNDWI | 0.82 | **0.82** | 0.76 | 0.48 |

### Recommendation
- Use `flood_s1_flood_km2` as the primary flood layer for the flood season (Jul–Nov) and for annual flood peaks.
  Cloud does not block it, and it sees water under vegetation.
- Keep MODIS `surface_water_km2` as the secondary, all-season layer, which is better for receding and dry-season water.
- Use UNOSAT for validation only.
- Copernicus GFM would be the natural upgrade if an account becomes available. Note that GFM also excludes flooded
  vegetation, so in the Sudd it would behave more like our open-water class.

### Caveats
- Wind-roughened open lakes are missed.
- Woody wetland, rice and built-up double bounce can raise VV−VH.
- Sentinel-1 revisit fell from 6–12 days to 12–24 days after the Sentinel-1B failure (23 Dec 2021). Some areas in
  2022–24 have no acquisition in a month: 61 % coverage of the bounding box in Feb 2022.
- `flood_s1_openwater_km2` jumps about 10× in 2025, probably from Sentinel-1C acquisitions and processing changes, so it
  is not trend-safe. The flood class, being relative to each pixel's reference, is less affected.
- The monthly mean smooths floods that last less than about 10 days.

## 3. Drought index ensemble and uncertainty

`scripts/drought_ensemble.py` → `data/processed/drought_ensemble_county_monthly.csv`, `meta/drought_ensemble.json`
(all `index_ok: false`).

| Member | Input | Method | Baseline |
|---|---|---|---|
| `spei3` (existing) | IMERG V07 P − Thornthwaite PET (MERRA-2) | log-logistic SPEI-3 | county 2000–2026 |
| `dr_spi3_chirps` | CHIRPS v3.0 (1991–2025 crop via /vsicurl) | gamma SPI-3 with zero-rain probability | 1991–2020 |
| `dr_spei3_tc` | TerraClimate ppt − Penman-Monteith PET (1991–2025) | log-logistic SPEI-3 (PWM fit) | 1991–2020 |
| `dr_pdsi_tc_z` | TerraClimate PDSI (1991–2025) | z-score per county and calendar month | 1991–2020 |

The script writes four outputs:
- `drought_ensemble_mean`: the mean of the members (at least 3 required).
- `drought_ensemble_spread`: the standard deviation across members. This is the "drought uncertainty" in the hover card.
- `drought_ensemble_range`: maximum minus minimum across members.
- `drought_ensemble_agree`: the share of members with the same sign as the mean.

### Results, 2018–2025
- The members agree only weakly. Pooled county-month correlations are r = 0.27–0.45:
  - CHIRPS-SPI vs IMERG-SPEI: 0.39
  - IMERG-SPEI vs TC-SPEI: 0.31
  - TC-SPEI vs TC-PDSI: 0.45
- The mean spread is **1.2 SD**. Spread is lowest in Mar–Jul (~1.0) and highest in Sep–Jan (1.3–1.4).
- TerraClimate members are systematically dry: their 2018–25 means are −0.9 to −2.0 SD, against about 0 for CHIRPS
  and IMERG. As a result, the ensemble mean leans dry, about −0.5 to −0.9.

### Reading the ensemble
- Treat a drought claim as solid only when `drought_ensemble_mean < −1`, `drought_ensemble_agree = 1` and the spread is
  below about 0.7.
- Otherwise the hover card should say "inputs disagree".
- PDSI and TC-SPEI share TerraClimate precipitation, so the four members are effectively three independent rainfall
  sources.

## 4. Water contamination and pollution spread with floods: what is measurable

| Candidate | Measurable? | Decision |
|---|---|---|
| Faecal contamination exposure: S1 flood × population (WorldPop R2025A 1 km, year-matched), with open defecation (ISNA ~50 %) | **Yes, as exposure** | **Implemented**: `flood_population_exposed`, `flood_population_exposed_pct` (`scripts/flood_exposure.py`, 79 counties, 2018–2025). Peaks are ~75 k (Oct 2019), ~215 k (2020), ~225 k (2021), ~200 k (2022) and ~120 k (2024). This is far below OCHA's "people affected" (~0.8–1 M in 2021) because WorldPop puts people on dry settlement mounds and dyke-protected towns, while OCHA counts livelihoods and access lost. |
| Oil-field pollution exposure: S1 flood within 5 km of the 104 oil well and field points in `docs/data/points_oil.geojson` (OSM wells + GEM GOGET; 848 km² zone) | **Yes, as exposure** | **Implemented**: `flood_oilfield_exposure_km2` (7 counties) and `flood_oil_wells_flooded` (5 counties). Peaks are ~120 km² in the oil zones in Sep 2021 and Sep 2022, with the maximum in Guit (SS0602, Thar Jath area, 101 km²). |
| Turbidity or suspended sediment (NDTI = (red − green)/(red + green), or MODIS red reflectance over water) | Technically yes for the open Nile/Sobat channels. It is **not a contamination measure**: sediment is natural, and the Sudd swamp is vegetated, so it has no clean water pixels at 500 m. Sentinel-2 at 10–20 m is feasible on Planetary Computer but heavy, and is cloud-limited in the wet season, exactly when floods happen. | Not implemented. Possible next step: dry-season Sentinel-2 NDTI on the Bahr el Jebel/White Nile at Juba, Bor and Malakal. |
| Produced-water / hydrocarbon contamination (Thar Jath, Unity, Paloich) | Field studies only (e.g. Sign of Hope hair and water samples, 2014–2019). Satellites cannot see dissolved hydrocarbons or salinity. Oil slicks on water are too small for Sentinel-1 at this scale. | Exposure proxy only |
| Water-quality monitoring (E. coli, residual chlorine) | WASH-cluster water-quality data are not public at county level | Not possible |
| Cholera / AWD outcome | WHO cholera on HDX is **national, 2026 only** (15 058 cases, Jan–Oct 2026). County line lists exist only in MoH/WHO sitrep PDFs (2024–25 outbreak). IDSR weekly bulletins are PDFs with <50 % completeness. | Not implemented (needs manual PDF extraction) |

## 5. Gender, water access and groundwater

### ISNA (South Sudan's MSNA)
- The ISNA is run by REACH/IMPACT for OCHA and the ICCG. County tables are on HDX for **2022, 2023 and 2024**.
- No county MSNA tables exist on HDX for 2018–2021. REACH's earlier "Area of Knowledge" data are settlement-level and
  shared on request.
- `scripts/isna_msna.py` → `data/processed/isna_county_monthly.csv` (annual, dated YYYY-07-01, 75–79 counties per round).

| Variable | Description | Mean 2022 → 2024 |
|---|---|---|
| `isna_water_30min_plus_pct` | Round trip to the main drinking-water source ≥30 min | 41 → 49 % |
| `isna_unsafe_water_collect_pct` | A household member felt unsafe while collecting water | 19 → 22 % |
| `isna_surface_water_source_pct` | Main drinking source is surface water or an unprotected well | 30 → 39 % |
| `isna_open_defecation_pct` | Household practises open defecation | 49 → 53 % |
| `isna_wg_avoid_water_points_pct` | Women and girls avoid water points because they feel unsafe | 8 → 12 % |
| `isna_wg_avoid_latrines_pct` | Women and girls avoid latrines and bathing areas because they feel unsafe | 3 → 9 % |
| `isna_wg_avoid_any_pct` | Women and girls avoid at least one area because they feel unsafe | 33 → 30 % |

### Caveats on the ISNA indicators
- These measure GBV **risk perception and exposure**, not incidence. GBVIMS incident data are confidential.
- Question wording changed between rounds (e.g. the 2022 water-source categories). The 2024 multi-select rows are
  missing for some counties.
- With only 3 rounds, Mann-Kendall trends cannot be significant.
- Who collects water (sex and age of the collector) is not in the published county tables for these rounds.

### Other water and GBV sources
- Insecurity Insight CRSV (`ii_sexual_violence_incidents`) is owned by another agent.
- IOM DTM mobility-tracking rounds hold WASH fields at site/settlement level only.
- WPdx water points stop around 2019 and are static.

### Groundwater
- GRACE/GRACE-FO terrestrial water storage needs an Earthdata login (urs.earthdata.nasa.gov not reachable). At about
  300 km resolution it would be basin-scale only.
- Open alternatives are **static**:
  - BGS **Africa Groundwater Atlas** / MacDonald et al. (2012) aquifer productivity and depth-to-groundwater maps (5 km)
  - UNICEF/UNOPS groundwater potential mapping for South Sudan (PDF maps)
- Use them as context layers only. There is no groundwater time series.

### Local (within-county) conflict
- `scripts/intracounty_conflict.py` → `intracounty_county_monthly.csv`, built from UCDP GED v26.1 non-state and
  one-sided events whose actors are communal groups or South Sudanese local militias. Government and foreign actors
  are excluded.
- Over 2018–2025 there are 198 county-precision events: 171 communal and 27 militia.
- Variables: `intracounty_conflict_events`, `intracounty_conflict_deaths`, `intracounty_communal_events` and
  `intracounty_communal_deaths`.
- UCDP's 25-deaths/year dyad threshold means cattle raiding is under-counted, and the actors' home county is unknown.


## Addendum (15 Nov 2026): Sudd MODIS water / inundation index

`scripts/sudd_water_index.py` applies the team's Inner Niger Delta method to the Sudd (16 counties, 103,478 km²):
Terra MOD09A1 8-day 500 m; open water = MNDWI > 0; inundation incl. flooded vegetation = open water or EVI − LSWI ≤ 0.05
(Xiao et al. 2006 / Sakamoto et al. 2007); cloudy pixels carried from the last clear view ≤ 24 days, else climatology
(83 % observed, 16 % carried, 1 % climatology; Jul–Aug only ~61–66 % observed).
Annual peak (Sep–Dec) ≈ 6.9k km² (2018) → 21–26k km² (2019–2022, 2024), 16k (2023); dry-season low rose from ~0.8k (2018–20)
to 6–8k km² (2022–25); the water no longer drains. Validation: UNOSAT median ratio 0.99 (r 0.61; county r 0.81); Sentinel-1 r 0.82;
national MODIS layer r 0.84; ~0.65–0.85 of published 30–40k km² peaks (smaller AOI; dense papyrus missed).
Recommendation: use it as the primary Sudd-wide flood-extent series for 2018–2025 (consistent all-season record); Sentinel-1 for
Jul–Nov detail; UNOSAT for validation. Planetary Computer lacks MODIS for 4 Jul–24 Nov 2025 → 2025 peak is Dec-only.
Details: `docs/VALIDATION_sudd_water.md`.
