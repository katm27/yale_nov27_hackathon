# South Sudan Trend Explorer (NASA Space Apps 2026, Earth System Trend Detective)

An interactive map of South Sudan's 79 counties. It puts climate and environment trends next to the drivers and
consequences of conflict, month by month from 2018 to 2025, and indexes every variable to its 2018 level (= 1.0).

- App: `docs/` (a static Leaflet site). To run it locally: `cd docs && python3 -m http.server`, then open http://localhost:8000.
- Data: [`data/DATA_CONTRACT.md`](data/DATA_CONTRACT.md). Every pipeline writes long CSVs of county × month × variable.
- Variable research and decision-maker priorities: [`docs/RESEARCH_variables_and_priorities.md`](docs/RESEARCH_variables_and_priorities.md)

## The app
The app opens on a landing page with an executive summary, key findings and a national timeline, and a button leads
into the map. [`docs/data/curated.json`](docs/data/curated.json) decides what the map shows: 18 climate and 10 human
measures, the satellite grids behind the climate measures, background layers (water, soil moisture, soil type,
cattle), 10 point layers, and how the IOM Event Tracking migration arrows are grouped (climate vs conflict). The rest
of the data stays in `docs/data/` but is not shown.

Counties are coloured on a single 7-bin red → white → green scale. The bins are percentiles of each measure; in trend
mode, white means little or no change, and black hatching means no data. The grids keep their own 7 equal-width bins
(`scripts/recolor_rasters_rwg.py`) because the raw grids are not stored. Hovering a county gives Sen's slope in native
units per year (percentage points for percentages and shares).

## How it works
1. `scripts/fetch_*.py`, `scripts/*_ssd.py` and `scripts/*_pipeline.py` download each source and aggregate it to counties →
   `data/processed/<source>_county_monthly.csv` + `data/processed/meta/<source>.json`. Fine-resolution raster overlays go to `docs/rasters/<key>/YYYY-MM.png`.
2. `python scripts/build_web_data.py` merges everything into `docs/data/` (one JSON per variable, raw values).
3. Computes the index in one of three ways: against the same month or season of the baseline year (the
   default, which removes seasonality), against the baseline-year average, or as raw values. Ratios are value ÷ baseline.
   Where a ratio makes no sense (temperatures in °C, SPEI/PDSI, anything that can be ≤ 0), the app shows the difference
   from baseline instead. If a source starts after 2018, its first year becomes the baseline, and the legend says so.
4. `python scripts/pack_for_artifact.py OUT` packs the site into a few files for hosts that limit the file count.

## Repository layout
| Path | Contents |
|---|---|
| `data/drive_mirror/` | Full mirror of the team Google Drive (`scripts/mirror_drive.sh`, manifest in `scripts/drive_manifest.tsv`). Most of `01_analysis_ready` and `Jacksonians_SpaceApps_Data/raw_sources` comes from the team's earlier Sahel (Mali/Burkina/Niger) work. The South Sudan files are `ssd_*`, `IOM_DTM_SSD_*`, the UNMISS PDFs and `boundaries_south_sudan_counties_79.geojson`. |
| `data/raw/ssd_unified/` | The team's unified county-month dataset (Dec 2019–Sep 2026): IOM Event Tracking (`et_*`), Flow Monitoring (`fmr_*`), UNMISS sites, Logistics Cluster hubs, OCHA population, national FTS/HRP, US aid and UNMISS budget/troops. Converted by `scripts/convert_unified_dataset.py`. National series appear on every county with the label suffix "— national"; county-to-county FMR flows are in `data/processed/flows/`. Its `et_*` series replace the earlier `dtm_et_*` series, which are hidden in the app. |
| `data/counties.geojson` | 79 county boundaries (OCHA P-codes, `district_id`) |
| `data/processed/` | County time series (long CSV) + metadata |
| `data/raw/<source>/` | Raw downloads (≤ 50 MB) with `SOURCE.md` (URLs for anything larger) |
| `docs/` | Web app, built data, raster overlays, points layers |

## Things to know before using the data
Geography: the project covers South Sudan, and "district" means county (admin-2) throughout. Abyei is included
wherever a source covers it.

Some indicators are not available at county level for 2018–2025, either because they are national-only or because
they are missing: the Women, Peace & Security index (national, copied to every county), girls' and children's school
enrolment (only the 2015 school census), vaccination (2018 only), infant and under-5 mortality (national only), ACLED.

Several layers are static snapshots that give context rather than trends: health facilities (2025), schools (2015),
oil fields and pipelines, ethnic groups (GeoEPR 2021), livestock (GLW 2015), soil, species richness and elevation.

Data caveats:
- MODIS products are missing Jul–Oct 2025 on Planetary Computer, and MODIS ET is annual only.
- MODIS surface water under-detects flooding (~0.5× UNOSAT, r = 0.76), so read it as a relative signal.
- Sentinel-5P samples a few orbits per month and starts in mid-2018, so its baseline is partial.
- NASA POWER variables are sampled at county centroids.
- WFP prices cover 12–28 market counties. Use the USD prices for trends, since SSP inflation swamps the SSP series.
- IPC has no county analysis in 2021, and the phase class from 2022 on is derived with the IPC 20% rule.
- IOM DTM Event Tracking starts in 2020, so its baseline year is 2020.

## Variables (generated from `docs/data/variables.json`)
| Category | Group | id | Label | Units | Time step | Coverage | Counties | Baseline | Source |
|---|---|---|---|---|---|---|---|---|---|
| environment | Air quality | `power_aod_550` | Aerosol optical depth 550 nm (dust/smoke haze) | dimensionless | monthly | 2018-01–2025-12 | 79 | 2018 | CERES SYN1deg via NASA POWER (parameter AOD_55) |
| environment | Air quality | `power_aod_840` | Aerosol optical depth 840 nm | dimensionless | monthly | 2018-01–2025-12 | 79 | 2018 | CERES SYN1deg via NASA POWER (parameter AOD_84) |
| environment | Air quality | `s5p_co` | Carbon monoxide total column | mmol/m2 | monthly | 2018-05–2025-12 | 79 | 2018 | Copernicus Sentinel-5P TROPOMI L2 (OFFL/RPRO) via Microsoft Planetary  |
| environment | Air quality | `s5p_no2` | Tropospheric NO2 | umol/m2 | monthly | 2018-05–2025-12 | 79 | 2018 | Copernicus Sentinel-5P TROPOMI L2 (OFFL/RPRO) via Microsoft Planetary  |
| environment | Air quality | `s5p_aerosol_index` | UV aerosol index (dust/smoke) | unitless | monthly | 2018-06–2025-12 | 79 | 2018 | Copernicus Sentinel-5P TROPOMI L2 (OFFL/RPRO) via Microsoft Planetary  |
| environment | Atmosphere | `tc_srad` | Downward shortwave radiation | W/m² | monthly | 2018-01–2025-12 | 79 | 2018 | TerraClimate v1.1 (Abatzoglou et al. 2018) via NKN THREDDS |
| environment | Atmosphere | `tc_vpd` | Vapour pressure deficit | kPa | monthly | 2018-01–2025-12 | 79 | 2018 | TerraClimate v1.1 (Abatzoglou et al. 2018) via NKN THREDDS |
| environment | Biodiversity | `richness_amphibians` | Amphibian species richness | species (mean per 10 km cell) | static | 2018-01–2018-07 | 79 | 2018 | BiodiversityMapping.org (Jenkins, Pimm & Joppa 2013; IUCN + BirdLife r |
| environment | Biodiversity | `richness_birds` | Bird species richness | species (mean per 10 km cell) | static | 2018-01–2018-07 | 79 | 2018 | BiodiversityMapping.org (Jenkins, Pimm & Joppa 2013; IUCN + BirdLife r |
| environment | Biodiversity | `richness_mammals` | Mammal species richness | species (mean per 10 km cell) | static | 2018-01–2018-07 | 79 | 2018 | BiodiversityMapping.org (Jenkins, Pimm & Joppa 2013; IUCN + BirdLife r |
| environment | Biodiversity | `richness_threatened_birds` | Threatened bird species | species (mean per 10 km cell) | static | 2018-01–2018-07 | 79 | 2018 | BiodiversityMapping.org (Jenkins, Pimm & Joppa 2013; IUCN + BirdLife r |
| environment | Biodiversity | `richness_threatened_mammals` | Threatened mammal species | species (mean per 10 km cell) | static | 2018-01–2018-07 | 79 | 2018 | BiodiversityMapping.org (Jenkins, Pimm & Joppa 2013; IUCN + BirdLife r |
| environment | Biodiversity | `richness_vertebrates` | Vertebrate species richness (amphibians+birds+mammals) | species (mean per 10 km cell) | static | 2018-01–2018-07 | 79 | 2018 | BiodiversityMapping.org (Jenkins, Pimm & Joppa 2013; IUCN + BirdLife r |
| environment | Drought | `tc_pdsi` | Palmer Drought Severity Index | index (-4 dry .. +4 wet) | monthly | 2018-01–2025-12 | 79 | 2018 | TerraClimate v1.1 (Abatzoglou et al. 2018) via NKN THREDDS |
| environment | Drought | `spei3` | SPEI-3 drought index | standard deviations | monthly | 2018-01–2025-12 | 79 | 2018 | Derived: IMERG precipitation minus Thornthwaite PET, 3-month SPEI vs c |
| environment | Extreme weather | `tc_extreme_dry` | Extreme dry month (flag) | flag 0/1 | monthly | 2018-01–2025-12 | 79 | 2018 | TerraClimate v1.1 (Abatzoglou et al. 2018) via NKN THREDDS; percentile |
| environment | Extreme weather | `tc_extreme_heat` | Extreme heat month (flag) | flag 0/1 | monthly | 2018-01–2025-12 | 79 | 2018 | TerraClimate v1.1 (Abatzoglou et al. 2018) via NKN THREDDS; percentile |
| environment | Extreme weather | `tc_extreme_wet` | Extreme wet month (flag) | flag 0/1 | monthly | 2018-01–2025-12 | 79 | 2018 | TerraClimate v1.1 (Abatzoglou et al. 2018) via NKN THREDDS; percentile |
| environment | Extreme weather | `tc_extreme_count` | Extreme-weather flags (count) | count 0..3 | monthly | 2018-01–2025-12 | 79 | 2018 | TerraClimate v1.1 (Abatzoglou et al. 2018) via NKN THREDDS; percentile |
| environment | Fire | `fire_count` | Active fire detections | fire pixel-detections per month | monthly | 2018-01–2025-12 | 79 | 2018 | MODIS MOD14A1/MYD14A1 v061 (Terra+Aqua daily 1 km FireMask) via Micros |
| environment | Fire | `burned_area_km2` | Burned area | km2 | monthly | 2018-01–2025-12 | 79 | 2018 | MODIS MCD64A1 v061 burned area via Microsoft Planetary Computer |
| environment | Fire | `burned_area_pct` | Burned area (% of county) | % of county area | monthly | 2018-01–2025-12 | 79 | 2018 | MODIS MCD64A1 v061 burned area via Microsoft Planetary Computer |
| environment | Land cover | `lulc_bare_pct` | Land cover: Bare ground share | % of county land-cover pixels | annual | 2017-07–2023-07 | 79 | 2018 | Esri / Impact Observatory 10 m Annual Land Use Land Cover (io-lulc-ann |
| environment | Land cover | `lulc_built_pct` | Land cover: Built area share | % of county land-cover pixels | annual | 2017-07–2023-07 | 79 | 2018 | Esri / Impact Observatory 10 m Annual Land Use Land Cover (io-lulc-ann |
| environment | Land cover | `lulc_crop_pct` | Land cover: Cropland share | % of county land-cover pixels | annual | 2017-07–2023-07 | 79 | 2018 | Esri / Impact Observatory 10 m Annual Land Use Land Cover (io-lulc-ann |
| environment | Land cover | `lulc_flooded_veg_pct` | Land cover: Flooded vegetation share | % of county land-cover pixels | annual | 2017-07–2023-07 | 79 | 2018 | Esri / Impact Observatory 10 m Annual Land Use Land Cover (io-lulc-ann |
| environment | Land cover | `lulc_rangeland_pct` | Land cover: Rangeland (grass/shrub) share | % of county land-cover pixels | annual | 2017-07–2023-07 | 79 | 2018 | Esri / Impact Observatory 10 m Annual Land Use Land Cover (io-lulc-ann |
| environment | Land cover | `lulc_trees_pct` | Land cover: Trees share | % of county land-cover pixels | annual | 2017-07–2023-07 | 79 | 2018 | Esri / Impact Observatory 10 m Annual Land Use Land Cover (io-lulc-ann |
| environment | Land cover | `lulc_water_pct` | Land cover: Water share | % of county land-cover pixels | annual | 2017-07–2023-07 | 79 | 2018 | Esri / Impact Observatory 10 m Annual Land Use Land Cover (io-lulc-ann |
| environment | Land surface | `modis_refl_nir` | Surface reflectance, near-infrared (MODIS band 2) | reflectance 0..1 | monthly | 2018-01–2025-12 | 79 | 2018 | MODIS MOD09A1 v061 (Terra) via Microsoft Planetary Computer |
| environment | Land surface | `modis_refl_red` | Surface reflectance, red (MODIS band 1) | reflectance 0..1 | monthly | 2018-01–2025-12 | 79 | 2018 | MODIS MOD09A1 v061 (Terra) via Microsoft Planetary Computer |
| environment | Land surface | `modis_refl_swir1` | Surface reflectance, shortwave infrared (MODIS band 6) | reflectance 0..1 | monthly | 2018-01–2025-12 | 79 | 2018 | MODIS MOD09A1 v061 (Terra) via Microsoft Planetary Computer |
| environment | Precipitation | `precip_mm` | Precipitation (IMERG) | mm/month | monthly | 2018-01–2025-12 | 79 | 2018 | GPM IMERG V07 Final via NASA POWER (IMERG_PRECTOT) |
| environment | Precipitation | `power_precip_mm` | Precipitation (MERRA-2 bias-corrected) | mm/month | monthly | 2018-01–2025-12 | 79 | 2018 | MERRA-2 via NASA POWER (parameter PRECTOTCORR) |
| environment | Precipitation | `tc_ppt` | Precipitation (TerraClimate) | mm/month | monthly | 2018-01–2025-12 | 79 | 2018 | TerraClimate v1.1 (Abatzoglou et al. 2018) via NKN THREDDS |
| environment | Soil | `soil_wrb_dominant` | Dominant soil group (WRB) | class code | static | 2018-01–2018-07 | 79 | 2018 | ISRIC SoilGrids 2.0 |
| environment | Soil | `soil_clay_0_30cm` | Topsoil clay content | % (mass) | static | 2018-01–2018-07 | 79 | 2018 | ISRIC SoilGrids 2.0 |
| environment | Soil | `soil_soc_0_30cm` | Topsoil organic carbon | g/kg | static | 2018-01–2018-07 | 79 | 2018 | ISRIC SoilGrids 2.0 |
| environment | Soil | `soil_phh2o_0_30cm` | Topsoil pH (H2O) | pH | static | 2018-01–2018-07 | 79 | 2018 | ISRIC SoilGrids 2.0 |
| environment | Soil | `soil_sand_0_30cm` | Topsoil sand content | % (mass) | static | 2018-01–2018-07 | 79 | 2018 | ISRIC SoilGrids 2.0 |
| environment | Soil | `soil_vertisol_pct` | Vertisol share | % of county | static | 2018-01–2018-07 | 79 | 2018 | ISRIC SoilGrids 2.0 |
| environment | Soil moisture | `soilwet_root` | Root-zone soil wetness (top 1 m) | fraction 0..1 | monthly | 2018-01–2025-12 | 79 | 2018 | MERRA-2 reanalysis via NASA POWER (GWETROOT) |
| environment | Soil moisture | `tc_soil` | Soil moisture (TerraClimate) | mm (end of month) | monthly | 2018-01–2025-12 | 79 | 2018 | TerraClimate v1.1 (Abatzoglou et al. 2018) via NKN THREDDS |
| environment | Temperature | `tmax_c` | Average daily maximum temperature | °C | monthly | 2018-01–2025-12 | 79 | 2018 | MERRA-2 reanalysis via NASA POWER (T2M_MAX_AVG) |
| environment | Temperature | `tmin_c` | Average daily minimum temperature | °C | monthly | 2018-01–2025-12 | 79 | 2018 | MERRA-2 reanalysis via NASA POWER (T2M_MIN_AVG) |
| environment | Temperature | `power_t2m_max` | Hottest hour of the month (2 m) | °C | monthly | 2018-01–2025-12 | 79 | 2018 | MERRA-2 via NASA POWER (parameter T2M_MAX) |
| environment | Temperature | `modis_lst_day_c` | Land surface temperature, day (MODIS) | °C | monthly | 2018-01–2025-12 | 79 | 2018 | MODIS MOD11A2 v061 (Terra, ~10:30 local) via Microsoft Planetary Compu |
| environment | Temperature | `modis_lst_night_c` | Land surface temperature, night (MODIS) | °C | monthly | 2018-01–2025-12 | 79 | 2018 | MODIS MOD11A2 v061 (Terra, ~22:30 local) via Microsoft Planetary Compu |
| environment | Temperature | `tc_tmax` | Max temperature (TerraClimate) | °C | monthly | 2018-01–2025-12 | 79 | 2018 | TerraClimate v1.1 (Abatzoglou et al. 2018) via NKN THREDDS |
| environment | Temperature | `tair_c` | Mean air temperature (2 m) | °C | monthly | 2018-01–2025-12 | 79 | 2018 | MERRA-2 reanalysis via NASA POWER (T2M) |
| environment | Temperature | `tc_tmin` | Min temperature (TerraClimate) | °C | monthly | 2018-01–2025-12 | 79 | 2018 | TerraClimate v1.1 (Abatzoglou et al. 2018) via NKN THREDDS |
| environment | Terrain | `elevation_mean` | Mean elevation | m | static | 2018-01–2018-07 | 79 | 2018 | Copernicus DEM GLO-90 via Microsoft Planetary Computer |
| environment | Terrain | `elevation_std` | Terrain ruggedness (elevation std) | m | static | 2018-01–2018-07 | 79 | 2018 | Copernicus DEM GLO-90 via Microsoft Planetary Computer |
| environment | Vegetation | `modis_evi` | EVI (MODIS enhanced vegetation index) | index -1..1 | monthly | 2018-01–2025-12 | 79 | 2018 | MODIS MOD13A1 + MYD13A1 v061 via Microsoft Planetary Computer |
| environment | Vegetation | `modis_ndvi` | NDVI (MODIS vegetation greenness) | index -1..1 | monthly | 2018-01–2025-12 | 79 | 2018 | MODIS MOD13A1 + MYD13A1 v061 via Microsoft Planetary Computer |
| environment | Water | `modis_et_mm` | Evapotranspiration, annual (MODIS) | mm/year | annual | 2018-07–2025-07 | 79 | 2018 | MODIS MOD16A3GF v061 (gap-filled annual) via Microsoft Planetary Compu |
| environment | Water & flooding | `surface_water_obs_pct` | Cloud-free observation coverage (water layer) | % of county area | monthly | 2018-01–2025-12 | 79 | 2018 | MODIS MOD09A1 + MYD09A1 v061 8-day surface reflectance via Microsoft P |
| environment | Water & flooding | `surface_water_pct` | Surface water (% of county) | % of county area | monthly | 2018-01–2025-12 | 79 | 2018 | MODIS MOD09A1 + MYD09A1 v061 8-day surface reflectance via Microsoft P |
| environment | Water & flooding | `surface_water_km2` | Surface water extent | km2 | monthly | 2018-01–2025-12 | 79 | 2018 | MODIS MOD09A1 + MYD09A1 v061 8-day surface reflectance via Microsoft P |
| environment | Water balance | `tc_aet` | Actual evapotranspiration | mm/month | monthly | 2018-01–2025-12 | 79 | 2018 | TerraClimate v1.1 (Abatzoglou et al. 2018) via NKN THREDDS |
| environment | Water balance | `tc_def` | Climatic water deficit | mm/month | monthly | 2018-01–2025-12 | 79 | 2018 | TerraClimate v1.1 (Abatzoglou et al. 2018) via NKN THREDDS |
| environment | Water balance | `pet_mm` | Potential evapotranspiration (Thornthwaite) | mm/month | monthly | 2018-01–2025-12 | 79 | 2018 | Derived (Thornthwaite) from MERRA-2 T2M via NASA POWER |
| environment | Water balance | `tc_pet` | Reference evapotranspiration (Penman-Monteith) | mm/month | monthly | 2018-01–2025-12 | 79 | 2018 | TerraClimate v1.1 (Abatzoglou et al. 2018) via NKN THREDDS |
| environment | Water balance | `tc_q` | Runoff | mm/month | monthly | 2018-01–2025-12 | 79 | 2018 | TerraClimate v1.1 (Abatzoglou et al. 2018) via NKN THREDDS |
| environment | Wind | `power_ws10m_max` | Strongest hourly wind at 10 m | m/s | monthly | 2018-01–2025-12 | 79 | 2018 | MERRA-2 via NASA POWER (parameter WS10M_MAX) |
| environment | Wind | `tc_ws` | Wind speed (10 m) | m/s | monthly | 2018-01–2025-12 | 79 | 2018 | TerraClimate v1.1 (Abatzoglou et al. 2018) via NKN THREDDS |
| environment | Wind | `power_ws10m` | Wind speed at 10 m | m/s | monthly | 2018-01–2025-12 | 79 | 2018 | MERRA-2 via NASA POWER (parameter WS10M) |
| environment | Wind | `power_ws2m` | Wind speed at 2 m | m/s | monthly | 2018-01–2025-12 | 79 | 2018 | MERRA-2 via NASA POWER (parameter WS2M) |
| human | Aid funding (national) | `fts_hum_funding_month_usd` | FTS hum funding month (USD) — national | USD (by funding decision month) | monthly | 2018-01–2025-12 | 79 | 2018 | OCHA FTS flows (incoming, paid/committed, South Sudan only, de-duplica |
| human | Aid funding (national) | `fts_hum_funding_year_usd` | FTS hum funding year (USD) — national | USD (calendar year, repeated each month) | monthly | 2018-01–2025-12 | 79 | 2018 | OCHA Financial Tracking Service API |
| human | Aid funding (national) | `fts_us_gov_funding_month_usd` | FTS us gov funding month (USD) — national | USD (by funding decision month) | monthly | 2018-01–2025-12 | 79 | 2018 | OCHA FTS flows (incoming, paid/committed, South Sudan only, de-duplica |
| human | Aid funding (national) | `fts_us_gov_funding_year_usd` | FTS us gov funding year (USD) — national | USD (calendar year, repeated each month) | monthly | 2018-01–2025-12 | 79 | 2018 | OCHA Financial Tracking Service API |
| human | Aid funding (national) | `fts_us_share_year` | FTS us share year — national | share | monthly | 2018-01–2025-12 | 79 | 2018 | OCHA Financial Tracking Service API |
| human | Aid funding (national) | `hrp_coverage_year` | HRP coverage year — national | share | monthly | 2018-01–2025-12 | 79 | 2018 | OCHA Financial Tracking Service API |
| human | Aid funding (national) | `hrp_funding_year_usd` | HRP funding year (USD) — national | USD (calendar year) | monthly | 2018-01–2025-12 | 79 | 2018 | OCHA Financial Tracking Service API |
| human | Aid funding (national) | `hrp_requirement_year_usd` | HRP requirement year (USD) — national | USD (calendar year) | monthly | 2018-01–2025-12 | 79 | 2018 | OCHA Financial Tracking Service API |
| human | Aid funding (national) | `state_dept_disbursed_month_usd` | State Dept disbursed month (USD) — national | USD (transaction month) | monthly | 2018-01–2025-12 | 79 | 2018 | ForeignAssistance.gov complete transaction file (South Sudan) |
| human | Aid funding (national) | `us_aid_disbursed_month_usd` | US aid disbursed month (USD) — national | USD (transaction month) | monthly | 2018-01–2025-12 | 79 | 2018 | ForeignAssistance.gov complete transaction file (South Sudan) |
| human | Aid funding (national) | `us_aid_obligated_month_usd` | US aid obligated month (USD) — national | USD (transaction month) | monthly | 2018-01–2025-12 | 79 | 2018 | ForeignAssistance.gov complete transaction file (South Sudan) |
| human | Aid funding (national) | `usaid_disbursed_month_usd` | USAID disbursed month (USD) — national | USD (transaction month) | monthly | 2018-01–2025-12 | 79 | 2018 | ForeignAssistance.gov complete transaction file (South Sudan) |
| human | Aid funding (national) | `usaid_obligated_month_usd` | USAID obligated month (USD) — national | USD (transaction month) | monthly | 2018-01–2025-12 | 79 | 2018 | ForeignAssistance.gov complete transaction file (South Sudan) |
| human | Conflict | `acled_civ_events` | Civilian targeting events (ACLED) | events/month | monthly | 2018-01–2025-12 | 79 | 2018 | ACLED via HDX (aggregated admin-2 monthly files) |
| human | Conflict | `acled_civ_fatalities` | Civilian targeting fatalities (ACLED) | deaths/month | monthly | 2018-01–2025-12 | 79 | 2018 | ACLED via HDX (aggregated admin-2 monthly files) |
| human | Conflict | `acled_demonstrations` | Demonstrations (ACLED) | events/month | monthly | 2018-01–2025-12 | 79 | 2018 | ACLED via HDX (aggregated admin-2 monthly files) |
| human | Conflict | `acled_pv_events` | Political violence events (ACLED) | events/month | monthly | 2018-01–2025-12 | 79 | 2018 | ACLED via HDX (aggregated admin-2 monthly files) |
| human | Conflict | `acled_pv_fatalities` | Political violence fatalities (ACLED) | deaths/month | monthly | 2018-01–2025-12 | 79 | 2018 | ACLED via HDX (aggregated admin-2 monthly files) |
| human | Conflict | `ucdp_civilian_deaths` | UCDP civilian deaths | deaths/month | monthly | 2018-01–2025-12 | 79 | 2018 | UCDP Georeferenced Event Dataset (GED) v26.1 |
| human | Conflict | `ucdp_deaths_best` | UCDP conflict deaths (best est.) | deaths/month | monthly | 2018-01–2025-12 | 79 | 2018 | UCDP Georeferenced Event Dataset (GED) v26.1 |
| human | Conflict | `ucdp_events` | UCDP conflict events | events/month | monthly | 2018-01–2025-12 | 79 | 2018 | UCDP Georeferenced Event Dataset (GED) v26.1 |
| human | Conflict | `ucdp_non_state_deaths` | UCDP non-state deaths | deaths/month | monthly | 2018-01–2025-12 | 79 | 2018 | UCDP Georeferenced Event Dataset (GED) v26.1 |
| human | Conflict | `ucdp_non_state_events` | UCDP non-state events | events/month | monthly | 2018-01–2025-12 | 79 | 2018 | UCDP Georeferenced Event Dataset (GED) v26.1 |
| human | Conflict | `ucdp_one_sided_deaths` | UCDP one-sided (vs civilians) deaths | deaths/month | monthly | 2018-01–2025-12 | 79 | 2018 | UCDP Georeferenced Event Dataset (GED) v26.1 |
| human | Conflict | `ucdp_one_sided_events` | UCDP one-sided (vs civilians) events | events/month | monthly | 2018-01–2025-12 | 79 | 2018 | UCDP Georeferenced Event Dataset (GED) v26.1 |
| human | Conflict | `ucdp_state_based_deaths` | UCDP state-based deaths | deaths/month | monthly | 2018-01–2025-12 | 79 | 2018 | UCDP Georeferenced Event Dataset (GED) v26.1 |
| human | Conflict | `ucdp_state_based_events` | UCDP state-based events | events/month | monthly | 2018-01–2025-12 | 79 | 2018 | UCDP Georeferenced Event Dataset (GED) v26.1 |
| human | Displacement | `dtm_idps` | IDPs present (DTM) | persons | irregular (per round) | 2018-06–2025-02 | 78 | 2018 | IOM DTM South Sudan Mobility Tracking - Baseline Assessment (rounds 2, |
| human | Displacement | `unhcr_refugees` | Refugees & asylum-seekers hosted (UNHCR) | persons | annual | 2018-07–2025-07 | 18 | 2018 | UNHCR Refugee Data Finder via HDX (end-year stock, REF+ASY) |
| human | Displacement | `dtm_returnees` | Returnees present (DTM) | persons | irregular (per round) | 2018-06–2025-02 | 78 | 2018 | IOM DTM South Sudan Mobility Tracking - Baseline Assessment (rounds 2, |
| human | Displacement – Event Tracking (IOM) | `et_events` | ET events | events | monthly | 2019-12–2025-12 | 79 | 2020 | IOM DTM South Sudan Event Tracking (harmonised 2020-2026 files) |
| human | Displacement – Event Tracking (IOM) | `et_events_food_need_assessed` | ET events food need assessed | events | monthly | 2019-12–2025-12 | 79 | 2020 | IOM DTM South Sudan Event Tracking (harmonised 2020-2026 files) |
| human | Displacement – Event Tracking (IOM) | `et_events_food_need_severe` | ET events food need severe | events | monthly | 2019-12–2025-12 | 79 | 2020 | IOM DTM South Sudan Event Tracking (harmonised 2020-2026 files) |
| human | Displacement – Event Tracking (IOM) | `et_ind_arrived_from_ethiopia` | ET people: arrived from ethiopia | people | monthly | 2019-12–2025-12 | 79 | 2020 | IOM DTM South Sudan Event Tracking (harmonised 2020-2026 files) |
| human | Displacement – Event Tracking (IOM) | `et_ind_arrived_from_sudan` | ET people: arrived from sudan | people | monthly | 2019-12–2025-12 | 79 | 2020 | IOM DTM South Sudan Event Tracking (harmonised 2020-2026 files) |
| human | Displacement – Event Tracking (IOM) | `et_ind_drought_fire_other_disaster` | ET people: drought fire other disaster | people | monthly | 2019-12–2025-12 | 79 | 2020 | IOM DTM South Sudan Event Tracking (harmonised 2020-2026 files) |
| human | Displacement – Event Tracking (IOM) | `et_ind_flooding` | ET people: flooding | people | monthly | 2019-12–2025-12 | 79 | 2020 | IOM DTM South Sudan Event Tracking (harmonised 2020-2026 files) |
| human | Displacement – Event Tracking (IOM) | `et_ind_hardship_food_living` | ET people: hardship food living | people | monthly | 2019-12–2025-12 | 79 | 2020 | IOM DTM South Sudan Event Tracking (harmonised 2020-2026 files) |
| human | Displacement – Event Tracking (IOM) | `et_ind_idps` | ET people: idps | people | monthly | 2019-12–2025-12 | 79 | 2020 | IOM DTM South Sudan Event Tracking (harmonised 2020-2026 files) |
| human | Displacement – Event Tracking (IOM) | `et_ind_local_communal_conflict` | ET people: local communal conflict | people | monthly | 2019-12–2025-12 | 79 | 2020 | IOM DTM South Sudan Event Tracking (harmonised 2020-2026 files) |
| human | Displacement – Event Tracking (IOM) | `et_ind_national_conflict` | ET people: national conflict | people | monthly | 2019-12–2025-12 | 79 | 2020 | IOM DTM South Sudan Event Tracking (harmonised 2020-2026 files) |
| human | Displacement – Event Tracking (IOM) | `et_ind_other` | ET people: other | people | monthly | 2019-12–2025-12 | 79 | 2020 | IOM DTM South Sudan Event Tracking (harmonised 2020-2026 files) |
| human | Displacement – Event Tracking (IOM) | `et_ind_return_relocation` | ET people: return relocation | people | monthly | 2019-12–2025-12 | 79 | 2020 | IOM DTM South Sudan Event Tracking (harmonised 2020-2026 files) |
| human | Displacement – Event Tracking (IOM) | `et_ind_returnees` | ET people: returnees | people | monthly | 2019-12–2025-12 | 79 | 2020 | IOM DTM South Sudan Event Tracking (harmonised 2020-2026 files) |
| human | Displacement – Event Tracking (IOM) | `et_ind_sudan_conflict` | ET people: sudan conflict | people | monthly | 2019-12–2025-12 | 79 | 2020 | IOM DTM South Sudan Event Tracking (harmonised 2020-2026 files) |
| human | Displacement – Event Tracking (IOM) | `et_ind_total` | ET people: total | people-movements | monthly | 2019-12–2025-12 | 79 | 2020 | IOM DTM South Sudan Event Tracking (harmonised 2020-2026 files) |
| human | Displacement – Flow Monitoring (IOM) | `fmr_active_monitoring_points` | FMR active monitoring points — national | monitoring points | monthly | 2020-01–2025-08 | 79 | 2020 | IOM DTM South Sudan Flow Monitoring Registry |
| human | Displacement – Flow Monitoring (IOM) | `fmr_all_movements_observed` | FMR all movements observed — national | people observed (all directions) | monthly | 2022-11–2025-08 | 79 | 2022 | IOM DTM South Sudan Flow Monitoring Registry |
| human | Displacement – Flow Monitoring (IOM) | `fmr_arrived_from_other_county_conflict` | FMR arrived from other county conflict | people observed | monthly | 2020-01–2025-08 | 79 | 2020 | IOM DTM South Sudan Flow Monitoring Registry (internal, forced, non-re |
| human | Displacement – Flow Monitoring (IOM) | `fmr_arrived_from_other_county_disaster` | FMR arrived from other county disaster | people observed | monthly | 2020-01–2025-08 | 79 | 2020 | IOM DTM South Sudan Flow Monitoring Registry (internal, forced, non-re |
| human | Displacement – Flow Monitoring (IOM) | `fmr_arrived_from_other_county_food` | FMR arrived from other county food | people observed | monthly | 2020-01–2025-08 | 79 | 2020 | IOM DTM South Sudan Flow Monitoring Registry (internal, forced, non-re |
| human | Displacement – Flow Monitoring (IOM) | `fmr_arrived_from_other_county_total` | FMR arrived from other county total | people observed | monthly | 2020-01–2025-08 | 79 | 2020 | IOM DTM South Sudan Flow Monitoring Registry (internal, forced, non-re |
| human | Displacement – Flow Monitoring (IOM) | `fmr_conflict_share_all_movements` | FMR conflict share all movements — national | share | monthly | 2022-11–2025-08 | 79 | 2022 | IOM DTM South Sudan Flow Monitoring Registry |
| human | Displacement – Flow Monitoring (IOM) | `fmr_departed_to_other_county_conflict` | FMR departed to other county conflict | people observed | monthly | 2020-01–2025-08 | 79 | 2020 | IOM DTM South Sudan Flow Monitoring Registry (internal, forced, non-re |
| human | Displacement – Flow Monitoring (IOM) | `fmr_departed_to_other_county_disaster` | FMR departed to other county disaster | people observed | monthly | 2020-01–2025-08 | 79 | 2020 | IOM DTM South Sudan Flow Monitoring Registry (internal, forced, non-re |
| human | Displacement – Flow Monitoring (IOM) | `fmr_departed_to_other_county_food` | FMR departed to other county food | people observed | monthly | 2020-01–2025-08 | 79 | 2020 | IOM DTM South Sudan Flow Monitoring Registry (internal, forced, non-re |
| human | Displacement – Flow Monitoring (IOM) | `fmr_departed_to_other_county_total` | FMR departed to other county total | people observed | monthly | 2020-01–2025-08 | 79 | 2020 | IOM DTM South Sudan Flow Monitoring Registry (internal, forced, non-re |
| human | Displacement – Flow Monitoring (IOM) | `fmr_internal_forced_conflict` | FMR internal forced conflict — national | people observed | monthly | 2020-01–2025-08 | 79 | 2020 | IOM DTM South Sudan Flow Monitoring Registry |
| human | Displacement – Flow Monitoring (IOM) | `fmr_internal_forced_disaster` | FMR internal forced disaster — national | people observed | monthly | 2020-01–2025-08 | 79 | 2020 | IOM DTM South Sudan Flow Monitoring Registry |
| human | Displacement – Flow Monitoring (IOM) | `fmr_internal_forced_food` | FMR internal forced food — national | people observed | monthly | 2020-01–2025-08 | 79 | 2020 | IOM DTM South Sudan Flow Monitoring Registry |
| human | Displacement – Flow Monitoring (IOM) | `fmr_internal_forced_total` | FMR internal forced total — national | people observed | monthly | 2020-01–2025-08 | 79 | 2020 | IOM DTM South Sudan Flow Monitoring Registry |
| human | Displacement – Flow Monitoring (IOM) | `fmr_monitoring_points_in_county` | FMR monitoring points in county | monitoring points | monthly | 2020-01–2025-08 | 79 | 2020 | IOM DTM South Sudan Flow Monitoring Registry (internal, forced, non-re |
| human | Displacement – Flow Monitoring (IOM) | `fmr_within_county_conflict` | FMR within county conflict | people observed | monthly | 2020-01–2025-08 | 79 | 2020 | IOM DTM South Sudan Flow Monitoring Registry (internal, forced, non-re |
| human | Displacement – Flow Monitoring (IOM) | `fmr_within_county_disaster` | FMR within county disaster | people observed | monthly | 2020-01–2025-08 | 79 | 2020 | IOM DTM South Sudan Flow Monitoring Registry (internal, forced, non-re |
| human | Displacement – Flow Monitoring (IOM) | `fmr_within_county_food` | FMR within county food | people observed | monthly | 2020-01–2025-08 | 79 | 2020 | IOM DTM South Sudan Flow Monitoring Registry (internal, forced, non-re |
| human | Displacement – Flow Monitoring (IOM) | `fmr_within_county_total` | FMR within county total | people observed | monthly | 2020-01–2025-08 | 79 | 2020 | IOM DTM South Sudan Flow Monitoring Registry (internal, forced, non-re |
| human | Education | `edu_girls_share` | Girls' share of enrolment (2015) | fraction 0-1 | static | 2018-01–2018-07 | 78 | 2018 | SSSAMS 2015 schools & enrolment (HDX, CC0) |
| human | Education | `edu_enrolment` | School enrolment (2015) | pupils | static | 2018-01–2018-07 | 78 | 2018 | SSSAMS 2015 schools & enrolment (HDX, CC0) |
| human | Education | `schools_count` | Schools (open, 2015) | schools | static | 2018-01–2018-07 | 79 | 2018 | SSSAMS 2015 schools & enrolment (HDX, CC0) |
| human | Education | `schools_per100k` | Schools per 100k people | per 100k | static | 2018-01–2018-07 | 79 | 2018 | SSSAMS 2015 schools & enrolment (HDX, CC0) |
| human | Ethnic geography | `ethnic_excluded_share` | Area of politically excluded groups | fraction 0-1 | static | 2018-01–2018-07 | 73 | 2018 | GeoEPR 2021 + EPR 2021 (ETH Zurich ICR) |
| human | Ethnic geography | `ethnic_dominant_share` | Dominant group area share | fraction 0-1 | static | 2018-01–2018-07 | 73 | 2018 | GeoEPR 2021 + EPR 2021 (ETH Zurich ICR) |
| human | Ethnic geography | `ethnic_groups_count` | Ethnic groups present (GeoEPR) | groups | static | 2018-01–2018-07 | 79 | 2018 | GeoEPR 2021 + EPR 2021 (ETH Zurich ICR) |
| human | Food security | `gam_prevalence_pct` | Global acute malnutrition prevalence (WHZ) | % children 6-59m | irregular (per IPC analysis) | 2025-07–2025-07 | 78 | 2025 | IPC (Integrated Food Security Phase Classification) via HDX |
| human | Food security | `ipc_amn_phase` | IPC Acute Malnutrition phase (1-5) | phase 1-5 | irregular (per IPC analysis) | 2025-07–2025-07 | 79 | 2025 | IPC (Integrated Food Security Phase Classification) via HDX |
| human | Food security | `ipc_phase_class` | IPC area phase classification (1-5) | phase 1-5 | irregular (per IPC analysis) | 2018-01–2025-09 | 79 | 2018 | IPC (Integrated Food Security Phase Classification) via HDX |
| human | Food security | `ipc_phase3plus_pop` | People in IPC Phase 3+ (Crisis or worse) | persons | irregular (per IPC analysis) | 2018-01–2025-09 | 79 | 2018 | IPC (Integrated Food Security Phase Classification) via HDX |
| human | Food security | `ipc_phase4plus_pop` | People in IPC Phase 4+ (Emergency or worse) | persons | irregular (per IPC analysis) | 2018-01–2025-09 | 79 | 2018 | IPC (Integrated Food Security Phase Classification) via HDX |
| human | Food security | `ipc_phase3plus_pct` | Share of population in IPC Phase 3+ | % | irregular (per IPC analysis) | 2018-01–2025-09 | 79 | 2018 | IPC (Integrated Food Security Phase Classification) via HDX |
| human | Health access | `health_facilities` | Health facilities (all levels) | facilities | static | 2018-01–2018-07 | 79 | 2018 | WHO / MoH Master Facility List, April 2025 (HDX) |
| human | Health access | `health_facilities_per100k` | Health facilities per 100k people | per 100k | static | 2018-01–2018-07 | 79 | 2018 | WHO / MoH Master Facility List, April 2025 (HDX) |
| human | Health access | `hospitals` | Hospitals | facilities | static | 2018-01–2018-07 | 79 | 2018 | WHO / MoH Master Facility List, April 2025 (HDX) |
| human | Health access | `hospitals_per100k` | Hospitals per 100k people | per 100k | static | 2018-01–2018-07 | 79 | 2018 | WHO / MoH Master Facility List, April 2025 (HDX) |
| human | Humanitarian logistics | `logcluster_hubs_in_county` | logcluster hubs in county | hubs | monthly | 2019-12–2025-12 | 79 | 2019 | Logistics Cluster South Sudan CONOPS maps (user hackathon zip) |
| human | Humanitarian needs | `hno_severity` | Humanitarian severity (HNO intersectoral, 1-5) | severity 1-5 | annual | 2022-07–2024-07 | 79 | 2022 | OCHA South Sudan Humanitarian Needs Overview (HDX; HAPI for 2024-25) |
| human | Humanitarian needs | `hno_pin` | People in need (HNO, intersectoral) | persons | annual | 2019-07–2025-07 | 79 | 2019 | OCHA South Sudan Humanitarian Needs Overview (HDX; HAPI for 2024-25) |
| human | Humanitarian response | `ops_orgs` | Humanitarian organisations present (3W) | organisations | monthly | 2019-01–2025-12 | 79 | 2019 | OCHA South Sudan 3W operational presence (HDX) |
| human | Humanitarian response | `ops_orgs_national_ngo` | National NGOs present (3W) | organisations | monthly | 2019-01–2025-12 | 79 | 2019 | OCHA South Sudan 3W operational presence (HDX) |
| human | Livestock | `cattle_head` | Cattle (head, 2015) | head | static | 2018-01–2018-07 | 79 | 2018 | FAO GLW4 2015 (Gilbert et al. 2018), Harvard Dataverse |
| human | Livestock | `cattle_density` | Cattle density (2015) | head / km² | static | 2018-01–2018-07 | 79 | 2018 | FAO GLW4 2015 (Gilbert et al. 2018), Harvard Dataverse |
| human | Livestock | `goats_head` | Goats (head, 2015) | head | static | 2018-01–2018-07 | 79 | 2018 | FAO GLW4 2015 (Gilbert et al. 2018), Harvard Dataverse |
| human | Livestock | `sheep_head` | Sheep (head, 2015) | head | static | 2018-01–2018-07 | 79 | 2018 | FAO GLW4 2015 (Gilbert et al. 2018), Harvard Dataverse |
| human | Oil economy | `oil_wells_osm` | Mapped oil wells (OSM) | wells | static | 2018-01–2018-07 | 79 | 2018 | OpenStreetMap (HOT/HDX) |
| human | Oil economy | `oil_pipeline_km` | Mapped pipelines (km) | km | static | 2018-01–2018-07 | 79 | 2018 | GEM GOIT (operating) + OpenStreetMap via Overture Maps 2026-10-21.0 |
| human | Oil economy | `oil_fields_count` | Oil fields (GEM) | fields | static | 2018-01–2018-07 | 79 | 2018 | Global Energy Monitor GOGET, Mar 2026 (CC-BY 4.0) |
| human | Peacekeeping | `unmiss_presence` | UNMISS deployment present | 0/1 | annual | 2018-07–2025-07 | 79 | 2018 | Geo-PKO v2.3 (2018-2024); UN map 4456 Rev.62 (2025) |
| human | Peacekeeping | `unmiss_deployment_sites_in_county` | UNMISS deployment sites in county | sites | monthly | 2023-12–2025-12 | 79 | 2023 | UN Geospatial map 4456 (UNMISS deployment), Rev. 58-65 (user hackathon |
| human | Peacekeeping | `unmiss_troops` | UNMISS troops deployed (est.) | troops | annual | 2018-07–2025-07 | 79 | 2018 | Geo-PKO v2.3 (2018-2024); UN map 4456 Rev.62 (2025) |
| human | Peacekeeping (national) | `unmiss_budget_fy_usd` | UNMISS budget fy (USD) — national | USD (UN fiscal year Jul-Jun, value repeated each month) | monthly | 2018-01–2025-12 | 79 | 2018 | UN peacekeeping budgets/expenditure (HDX dpo-pkbudget, dpo-pkexp; A/RE |
| human | Peacekeeping (national) | `unmiss_expenditure_fy_usd` | UNMISS expenditure fy (USD) — national | USD (UN fiscal year Jul-Jun, value repeated each month) | monthly | 2018-01–2025-06 | 79 | 2018 | UN peacekeeping budgets/expenditure (HDX dpo-pkbudget, dpo-pkexp; A/RE |
| human | Peacekeeping (national) | `unmiss_uniformed_personnel` | UNMISS uniformed personnel — national | personnel | monthly | 2018-01–2025-12 | 79 | 2018 | UN DPO uniformed personnel by mission (HDX dpo-uchistorical) |
| human | Population | `pop_total` | Population (WorldPop) | people | annual | 2018-07–2025-07 | 79 | 2018 | WorldPop Global2 R2025A constrained 1 km (UN-adjusted), 2015-2030 seri |
| human | Population | `population_estimate` | population estimate | people | annual | 2022-07–2025-07 | 79 | 2022 | OCHA COD-PS South Sudan 2022 v2 |
| human | Prices | `price_beans_ssp` | Beans (red) price (SSP/kg) | SSP per kg | monthly | 2018-01–2025-12 | 32 | 2018 | WFP VAM market monitoring via HDX |
| human | Prices | `price_beans_usd` | Beans (red) price (USD/kg) | USD per kg | monthly | 2018-01–2025-12 | 32 | 2018 | WFP VAM market monitoring via HDX |
| human | Prices | `price_cooking_oil_ssp` | Cooking oil (vegetable) price (SSP/L) | SSP per L | monthly | 2018-01–2025-12 | 32 | 2018 | WFP VAM market monitoring via HDX |
| human | Prices | `price_cooking_oil_usd` | Cooking oil (vegetable) price (USD/L) | USD per L | monthly | 2018-01–2025-12 | 32 | 2018 | WFP VAM market monitoring via HDX |
| human | Prices | `wage_casual_labour_ssp` | Daily casual labour wage (SSP) | SSP per day | monthly | 2018-03–2025-12 | 32 | 2018 | WFP VAM market monitoring via HDX |
| human | Prices | `wage_casual_labour_usd` | Daily casual labour wage (USD) | USD per day | monthly | 2018-03–2025-12 | 32 | 2018 | WFP VAM market monitoring via HDX |
| human | Prices | `price_diesel_parallel_ssp` | Diesel (parallel market) price (SSP/L) | SSP per L | monthly | 2018-03–2025-12 | 29 | 2018 | WFP VAM market monitoring via HDX |
| human | Prices | `price_diesel_parallel_usd` | Diesel (parallel market) price (USD/L) | USD per L | monthly | 2018-03–2025-12 | 29 | 2018 | WFP VAM market monitoring via HDX |
| human | Prices | `price_diesel_ssp` | Diesel price (SSP/L) | SSP per L | monthly | 2018-01–2025-12 | 28 | 2018 | WFP VAM market monitoring via HDX |
| human | Prices | `price_diesel_usd` | Diesel price (USD/L) | USD per L | monthly | 2018-01–2025-12 | 28 | 2018 | WFP VAM market monitoring via HDX |
| human | Prices | `fx_ssp_per_usd` | Exchange rate, parallel market (SSP per USD) | SSP per USD | monthly | 2018-01–2025-12 | 32 | 2018 | WFP VAM market monitoring via HDX |
| human | Prices | `price_groundnuts_ssp` | Groundnuts (shelled) price (SSP/kg) | SSP per kg | monthly | 2018-01–2024-03 | 26 | 2018 | WFP VAM market monitoring via HDX |
| human | Prices | `price_groundnuts_usd` | Groundnuts (shelled) price (USD/kg) | USD per kg | monthly | 2018-01–2024-03 | 26 | 2018 | WFP VAM market monitoring via HDX |
| human | Prices | `price_maize_ssp` | Maize (white grain) price (SSP/kg) | SSP per kg | monthly | 2018-01–2025-12 | 28 | 2018 | WFP VAM market monitoring via HDX |
| human | Prices | `price_maize_usd` | Maize (white grain) price (USD/kg) | USD per kg | monthly | 2018-01–2025-12 | 28 | 2018 | WFP VAM market monitoring via HDX |
| human | Prices | `price_petrol_ssp` | Petrol (gasoline) price (SSP/L) | SSP per L | monthly | 2018-01–2025-12 | 28 | 2018 | WFP VAM market monitoring via HDX |
| human | Prices | `price_petrol_usd` | Petrol (gasoline) price (USD/L) | USD per L | monthly | 2018-01–2025-12 | 28 | 2018 | WFP VAM market monitoring via HDX |
| human | Prices | `price_petrol_parallel_ssp` | Petrol (parallel market) price (SSP/L) | SSP per L | monthly | 2018-03–2025-12 | 30 | 2018 | WFP VAM market monitoring via HDX |
| human | Prices | `price_petrol_parallel_usd` | Petrol (parallel market) price (USD/L) | USD per L | monthly | 2018-03–2025-12 | 30 | 2018 | WFP VAM market monitoring via HDX |
| human | Prices | `price_sorghum_local_ssp` | Sorghum (local) price (SSP/kg) | SSP per kg | monthly | 2018-04–2025-12 | 31 | 2018 | WFP VAM market monitoring via HDX |
| human | Prices | `price_sorghum_local_usd` | Sorghum (local) price (USD/kg) | USD per kg | monthly | 2018-04–2025-12 | 31 | 2018 | WFP VAM market monitoring via HDX |
| human | Prices | `price_sorghum_ssp` | Sorghum (white, imported) price (SSP/kg) | SSP per kg | monthly | 2018-01–2025-12 | 32 | 2018 | WFP VAM market monitoring via HDX |
| human | Prices | `price_sorghum_usd` | Sorghum (white, imported) price (USD/kg) | USD per kg | monthly | 2018-01–2025-12 | 32 | 2018 | WFP VAM market monitoring via HDX |
| human | Prices | `price_wheat_flour_ssp` | Wheat flour price (SSP/kg) | SSP per kg | monthly | 2018-01–2025-12 | 32 | 2018 | WFP VAM market monitoring via HDX |
| human | Prices | `price_wheat_flour_usd` | Wheat flour price (USD/kg) | USD per kg | monthly | 2018-01–2025-12 | 32 | 2018 | WFP VAM market monitoring via HDX |
| human | Public health | `imr_national` | Infant mortality (national) | deaths per 1,000 live births | annual | 2018-07–2024-07 | 79 | 2018 | UN IGME via UNICEF SDMX |
| human | Public health | `vacc_mcv1_cov` | Measles (MCV1) coverage (admin, 2018) | % | annual | 2018-07–2018-07 | 78 | 2018 | WHO/UNICEF administrative immunization data, 2018 (HDX) |
| human | Public health | `vacc_penta3_cov` | Penta3 / DTP3 coverage (admin, 2018) | % | annual | 2018-07–2018-07 | 78 | 2018 | WHO/UNICEF administrative immunization data, 2018 (HDX) |
| human | Public health | `u5mr_national` | Under-5 mortality (national) | deaths per 1,000 live births | annual | 2018-07–2024-07 | 79 | 2018 | UN IGME via UNICEF SDMX |
| human | Women, Peace & Security | `wps_ipv_pct` | Intimate partner violence (national) | % women | annual | 2019-07–2025-07 | 79 | 2019 | Georgetown GIWPS WPS Index editions 2017/18-2025/26 |
| human | Women, Peace & Security | `wps_rank` | WPS Index rank (national) | rank (1 = best) | annual | 2019-07–2025-07 | 79 | 2019 | Georgetown GIWPS WPS Index editions 2017/18-2025/26 |
| human | Women, Peace & Security | `wps_index` | WPS Index score (national) | index 0-1 | annual | 2019-07–2025-07 | 79 | 2019 | Georgetown GIWPS WPS Index editions 2017/18-2025/26 |
| human | Women, Peace & Security | `wps_community_safety_pct` | Women feeling safe in community (national) | % | annual | 2017-07–2025-07 | 79 | 2019 | Georgetown GIWPS WPS Index editions 2017/18-2025/26 |
| human | Women, Peace & Security | `wps_parliament_women_pct` | Women in parliament (national) | % seats | annual | 2017-07–2025-07 | 79 | 2019 | Georgetown GIWPS WPS Index editions 2017/18-2025/26 |
| human | Women, Peace & Security | `wps_cellphone_pct` | Women's cell phone use (national) | % | annual | 2017-07–2025-07 | 79 | 2019 | Georgetown GIWPS WPS Index editions 2017/18-2025/26 |
| human | Women, Peace & Security | `wps_employment_pct` | Women's employment (national) | % | annual | 2019-07–2025-07 | 79 | 2019 | Georgetown GIWPS WPS Index editions 2017/18-2025/26 |
| human | Women, Peace & Security | `wps_financial_inclusion_pct` | Women's financial inclusion (national) | % | annual | 2019-07–2025-07 | 79 | 2019 | Georgetown GIWPS WPS Index editions 2017/18-2025/26 |
| human | Women, Peace & Security | `wps_education_years` | Women's mean years of schooling (national) | years | annual | 2019-07–2025-07 | 79 | 2019 | Georgetown GIWPS WPS Index editions 2017/18-2025/26 |
