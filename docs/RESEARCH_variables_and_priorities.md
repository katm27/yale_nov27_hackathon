# Variables and priorities for the South Sudan county map (2018–2025)

Project: NASA Space Apps 2026, "Earth System Trend Detective". South Sudan, 79 counties (OCHA COD admin-2), monthly 2018-01 to 2025-12, every variable indexed to its 2018 level (= 1.0).
Researched: 14 Nov 2026. HDX availability was checked through the HDX CKAN API (`package_show`) on that date. Other sources were checked by web search.

> Challenge page: the official page at <https://www.spaceappschallenge.org/2026/challenges/earth-system-trend-detective/> did not load while this was written (HTTP 503 and a TLS error). This document therefore works from the team's own framing of the challenge: show trends in Earth-system variables next to the drivers and consequences of conflict, as a visual tool for decision-makers, with no causal claims. Re-read the official page before you submit and check this framing against it.

Codes used in the tables:

| Code | Meaning |
|---|---|
| T1 / T2 / T3 | Tier 1 must-have · Tier 2 high value · Tier 3 nice-to-have |
| CM | county-monthly is achievable (native, or by zonal stats on a raster/points) |
| CA | county-annual (or seasonal/irregular rounds) |
| C | coarser than county (state, basin, ≥0.5° grid, or point gauges) |
| N | national only |
| S | static snapshot (one or two epochs), not a time series |
| Open / Login / Restricted | free anonymous download · free registration (e.g. NASA Earthdata, ACLED, Copernicus) · on request or licensed |

---

## 1. Summary: the most useful additions

1. Flood-affected people by county (OCHA, 2021–2025, county). This links the MODIS flood layer to its human impact. [HDX](https://data.humdata.org/dataset/south-sudan-flood-data)
2. Humanitarian access incidents and attacks on aid workers (AWSD geocoded 2011–2026; OCHA county access incidents 2022–2024; Insecurity Insight). Humanitarian decision-makers ask for this routinely. [AWSD](https://data.humdata.org/dataset/aid-worker-security-database-ssd) · [OCHA 2022–23](https://data.humdata.org/dataset/south-sudan-humanitarian-access-incidents) · [OCHA 2024](https://data.humdata.org/dataset/south-sudan-access-incidents-jan-dec_2024) · [Insecurity Insight SSD](https://data.humdata.org/dataset/south-sudan-attacks-on-civilians-and-vital-civilian-facilities)
3. Arrivals from the Sudan war, April 2023 onward (UNHCR national daily series; RRC/UNHCR/IOM border monitoring at points of entry such as Joda/Wunthou in Renk). This is the largest new shock of the period. [UNHCR new arrivals](https://data.humdata.org/dataset/new-arrivals-from-sudan) · [OCHA border monitoring 2023](https://data.humdata.org/dataset/population-movement-from-sudan-to-south-sudan) · [Renk working group](https://data.unhcr.org/en/working-group/457)
4. Ready-made admin-2 climate series from WFP: CHIRPS rainfall and its anomaly, and MODIS NDVI, both dekadal, with P-codes, 1981/2002 to present. These are a quick cross-check for the team's own zonal statistics. [Rainfall](https://data.humdata.org/dataset/ssd-rainfall-subnational) · [NDVI](https://data.humdata.org/dataset/ssd-ndvi-subnational)
5. FloodScan daily flood fraction per admin-1 and admin-2, with a 10-year baseline and return period. It is passive-microwave, so cloud does not block it. [HDX](https://data.humdata.org/dataset/floodscan)
6. Night-time lights (VIIRS Black Marble VNP46A3 monthly, or EOG VNL monthly). These proxy urban activity, oil-field gas flaring, and electricity loss. [LAADS VNP46A3](https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/VNP46A3/) · [EOG VNL](https://eogdata.mines.edu/products/vnl/)
7. River discharge and upstream drivers: GloFAS reanalysis at Juba, Bor, Malakal and Bentiu, plus the Lake Victoria level. The 2019–2022 Sudd mega-floods were driven upstream. [GloFAS on EWDS](https://ewds.climate.copernicus.eu/datasets/cems-glofas-historical) · [USDA G-REALM](https://ipad.fas.usda.gov/cropexplorer/global_reservoir/)
8. Disease outbreaks: cholera (WHO; the 2024–25 outbreak was South Sudan's largest), and malaria, measles and hepatitis E from the weekly IDSR bulletins. [WHO cholera on HDX](https://data.humdata.org/dataset/world-health-organization-who-cholera-data) · [IDSR bulletins (WHO AFRO)](https://www.afro.who.int/countries/south-sudan/publications)
9. Settlement change from Google Open Buildings 2.5D Temporal (annual 2016–2023, 4 m effective resolution). It shows growth and abandonment of settlements, for example around Bentiu, Renk and Malakal. [GEE catalog](https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_Research_open-buildings-temporal_v1)
10. A context-event timeline shown as annotations, not a variable: R-ARCSS (Sep 2018), the unity government (Feb 2020), the 2019–2022 floods, the Sudan war (Apr 2023), the oil-export pipeline disruption (Feb 2024), the cholera outbreak (from Oct 2024), and the Nasir clashes and political crisis (Mar 2025). Non-specialists find trend breaks hard to read without these markers.

---

## 2. Additional variables (not in the planned list), verified to exist

### 2a. Environment / Earth system

| Variable | Source and link | Time span | Avail. | Access | Tier | Decision-maker use | Caveats |
|---|---|---|---|---|---|---|---|
| Flood fraction (daily, admin-2, with baseline and return period) | AER FloodScan via HDX, [floodscan](https://data.humdata.org/dataset/floodscan) | 1998→ (zonal-stats file); rasters on HDX cover the last 90 days only | CM | Open (tabular); full rasters licensed | T1 | OCHA/WFP: flood severity against normal, used to pre-position supplies before the Sep–Dec flood peak | ~10 km resolution. Check how far back the xlsx goes and whether its admin-2 units match the COD P-codes |
| Sentinel-1 observed flood extent (radar, sees through cloud) | Copernicus CEMS [Global Flood Monitoring](https://global-flood.emergency.copernicus.eu/) via [EODC STAC/API](https://docs.eodc.eu/tutorials/download_gfm_python.html) | 2015→ | CM | Open (API) | T2 | Fills the cloudy rainy-season gaps in the MODIS flood layer | 6–12-day revisit. Large volumes, so pre-aggregate. Flooded vegetation in the Sudd is under-detected |
| UNOSAT satellite-detected water extents | UNOSAT on HDX, e.g. [Aug 2025](https://data.humdata.org/dataset/satellite-detected-water-extents-between-13-and-17-august-2025-over-south-sudan) (~99 products) | 2019–2025, irregular snapshots | CA (event) | Open | T3 | Validates the flood layer for named events | Not a regular series |
| River discharge (Nile at Juba/Bor/Malakal, Bahr el Ghazal, Sobat) | [GloFAS v4 historical reanalysis](https://ewds.climate.copernicus.eu/datasets/cems-glofas-historical) (CEMS Early Warning Data Store) | 1979→, daily, 0.05° | C (gauge points) | Login (free) | T2 | Upstream driver of Sudd flooding. Shown as a sparkline beside the map | Modelled, not observed. Assign each point to a county or show it as a separate panel |
| Lake Victoria / Lake Albert water level | [USDA G-REALM](https://ipad.fas.usda.gov/cropexplorer/global_reservoir/), [DAHITI](https://dahiti.dgfi.tum.de/), [Hydroweb](https://hydroweb.next.theia-land.fr/) | 1992→, ~10-day | N/C (basin) | Open / Login (DAHITI) | T2 | Explains the 2020–2022 record White Nile flows. Shows the decision-maker that the flood risk comes from outside the country | Shows the upstream driver, not South Sudan itself. DAHITI has Nile virtual stations ([DGFI Nile overview](https://nilebasin.org/sites/default/files/2023-10/DAHITI%20-Monitoring%20Water%20levels%20of%20Nile%20River_Schwatke_0.pdf)); coverage of the Sudd and Lake No was not confirmed. MSF used altimetry in Bentiu ([AVISO case](https://www.aviso.altimetry.fr/en/applications/hydrology-and-land/wetlands/use-of-altimetry-water-level-time-series-by-msf-to-help-displaced-communities-in-south-sudan.html)) |
| Terrestrial water storage anomaly (groundwater + soil + surface) | GRACE/GRACE-FO mascons: [JPL](https://grace.jpl.nasa.gov/data/get-data/jpl_global_mascons/), [GSFC](https://earth.gsfc.nasa.gov/geo/data/grace-mascons) | 2002→, monthly | C (~300 km effective) | Login (Earthdata) | T3 | Basin-scale wetting of the Sudd since 2019 | Far too coarse for counties; show at state or basin level. Mid-2017 to mid-2018 gap (so the 2018 baseline is partial) plus some missing months |
| Night-time lights (radiance) | NASA [Black Marble VNP46A3/A4](https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/VNP46A3/) (also on GEE as `NASA/VIIRS/002/VNP46A2`); EOG [VNL monthly](https://eogdata.mines.edu/products/vnl/) (also GEE `NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG`) | 2012→, monthly | CM | Login (Earthdata, free EOG registration) or open via GEE | T1 | Proxy for economic activity and power in towns, collapse after attacks, growth of IDP sites, and oil-field flaring (Unity, Upper Nile) | Very dark country, so most counties are near zero and ratios to 2018 are unstable: index only counties above a threshold. Dry-season biomass fires add noise (use the fire-masked annual VNL). Gas flares dominate in oil counties |
| Gas flaring volume per flare site | World Bank [Global Gas Flaring Tracker / GGFR](https://www.worldbank.org/en/programs/gasflaringreduction/global-flaring-data) (EOG VIIRS Nightfire) | 2012→, annual by site | CA | Open | T3 | Oil-production activity: rises after 2018 restarts, drops after the Feb 2024 pipeline rupture | Only counties with oil fields |
| Vegetation Health Index (agricultural drought) | FAO GIEWS [ASIS](https://www.fao.org/giews/earthobservation/country/index.jsp?code=SSD&lang=en) | 1984→, dekadal | CM (1 km raster) / admin-1 tables | Open | T2 | Crop and pasture stress, a common FAO/IPC input | Overlaps NDVI and SPEI; choose one for the default view |
| FAPAR anomaly | Copernicus via HDX, [ssd-anomalies-fapar-viirs](https://data.humdata.org/dataset/ssd-anomalies-fapar-viirs) | 2012→, 10-day | CM | Open | T3 | Same use as VHI | Overlaps NDVI |
| Pasture biomass (Dry Matter Productivity) | [Copernicus Land DMP 300 m](https://land.copernicus.eu/en/products/vegetation/dry-matter-productivity-v1-0-300m) | 2014→, 10-day | CM | Open | T2 | Pasture scarcity is the main ecological driver of cattle migration and of clashes between herders and farmers | Mask to grassland and shrubland |
| JRC ASAP agricultural production hotspots | JRC [ASAP](https://agricultural-production-hotspots.ec.europa.eu/), [HDX](https://data.humdata.org/dataset/asap-hotspots-monthly) | 2016→, monthly | C (admin-1) | Open | T3 | Official EU early-warning flag | Admin-1 only |
| IGAD Combined Drought Indicator | ICPAC via HDX, e.g. [CDI 2025](https://data.humdata.org/dataset/igad-region-monthly-combined-drought-indicator-cdi-2025) | 2020→ on HDX | CM (raster) | Open | T3 | The regional drought index used by IGAD | Starts in 2020, so no 2018 baseline on HDX |
| Settlement and building change | Google [Open Buildings 2.5D Temporal](https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_Research_open-buildings-temporal_v1) (annual building presence, count and height, 2016–2023); static footprints [on HDX](https://data.humdata.org/dataset/buildings-google-ssd) | 2016–2023 | CA | Open (GEE/GCS) | T2 | Growth of displacement settlements and towns (Renk, Bentiu, Juba) and abandoned villages after violence | Confidence scores are uncalibrated. Detection of thatched tukuls is weak. Ends in 2023 |
| Built-up surface epochs | [GHSL on HDX](https://data.humdata.org/dataset/ssd-ghsl) | 5-year epochs (2015/2020/2025) | S | Open | T3 | Urbanisation context | Too coarse in time |
| Land cover, monthly | [Dynamic World](https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_DYNAMICWORLD_V1) (Sentinel-2, 10 m) | 2015→, near real time | CM (composites) | Open (GEE) | T3 | Cropland and flooded-vegetation fractions; complements Esri annual land cover | Cloud gaps in the rainy season |
| Land degradation (SDG 15.3.1) | [Trends.Earth](https://trends.earth/) | multi-year periods | S | Open | T3 | Long-term degradation context | Not monthly |
| Aboveground biomass | CTrees via [HDX](https://data.humdata.org/dataset/ssd-ctrees-aboveground-biomass) | annual | CA | Open | T3 | Charcoal, deforestation in the Equatorias | Uncertainty is high |
| Desert locust | FAO [Locust Hub](https://locust-hub-hqfao.hub.arcgis.com/) | 2020 incursion only | S/event | Open | T3 | Marginal for South Sudan; a footnote | One swarm episode (2020); not a recurring driver |
| GHG/air-pollutant emissions | Climate TRACE via [HDX](https://data.humdata.org/dataset/ssd-climate-trace) | 2024→ on HDX | C (admin-1) | Open | T3 | Low relevance | Admin-1, short series |

### 2b. Conflict, security and protection

| Variable | Source and link | Time span | Avail. | Access | Tier | Decision-maker use | Caveats |
|---|---|---|---|---|---|---|---|
| Aid-worker security incidents (killed, injured, kidnapped) | [AWSD](https://www.aidworkersecurity.org/), [HDX SSD extract](https://data.humdata.org/dataset/aid-worker-security-database-ssd) | 1997→ | CM (geocoded points) | Open | T1 | Staff safety, deciding when to resume operations, and negotiating access | Major incidents only. Current year is provisional |
| Humanitarian access incidents (violence, interference, bureaucratic impediments, road attacks) | OCHA South Sudan: [2022](https://data.humdata.org/dataset/south-sudan-access-incidents), [2022–23](https://data.humdata.org/dataset/south-sudan-humanitarian-access-incidents), [2024](https://data.humdata.org/dataset/south-sudan-access-incidents-jan-dec_2024) | 2022–2024 as county tables; 2018–2021 only in the monthly [OCHA access snapshots](https://reliefweb.int/updates?search=south%20sudan%20humanitarian%20access%20snapshot) (PDF) | CM (2022–24) / CA | Open | T1 | OCHA and the HCT: where aid cannot reach and why | No 2018 baseline in tabular form, so show counts, not an index |
| Attacks on aid, health, education, food systems; CRSV; children | Insecurity Insight: [SSD bundle](https://data.humdata.org/dataset/south-sudan-attacks-on-civilians-and-vital-civilian-facilities), [Children in Armed Conflict](https://data.humdata.org/dataset/children-in-armed-conflict-data), [CRSV](https://data.humdata.org/dataset/conflict-related-sexual-violence) | 2016/2017/2020→ depending on theme | CM (geolocated where possible) | Open | T2 | Protection cluster, UNICEF, Health/Education clusters | Built from open sources and agency reports, so under-counted. Some events carry only admin-1 locations |
| Attacks on health care (WHO SSA) | WHO [SSA](https://extranet.who.int/ssa/), [historic on HDX](https://data.humdata.org/dataset/surveillance-system-for-attacks-on-health-care-ssa-historic) | 2017→ | C (admin-1) | Open | T3 | Health cluster | Admin-1 |
| Violence against civilians (HRD verified casualties: killed, injured, abducted, CRSV) | UNMISS Human Rights Division [quarterly briefs](https://unmiss.unmissions.org/en/node/28652?page=0), e.g. [Q4 2024](https://unmiss.unmissions.org/sites/default/files/quarterly_brief_on_violence_affecting_civilians_october_-december_2024.pdf) | 2020→, quarterly | CA/quarterly (state; some counties in text) | Open (PDF) | T2 | UNMISS's own verified figures; a check on ACLED. Shows the Q2 2024 Tambura hotspot, for example | PDF tables; county detail only for hotspots |
| Intercommunal violence and cattle raiding | Derived from [ACLED](https://acleddata.com/) (actor type "Communal militia"; text search of notes for "cattle", "raid") | 2011→ | CM | Login | T1 (as a derived layer) | The main layer for conflict over pasture, water and cattle among pastoralists | No dedicated open cattle-raid dataset was found. Keyword tagging is approximate, so document the rule |
| Landmines / ERW (open hazards, clearance tasks) | UNMAS / NMAA [IMSMA monthly reports](https://unmas.org/sites/default/files/2026-08/IMSMA_Monthly_July2026.pdf); payam-level maps in the [monthly map series](https://unsco.unmissions.org/sites/default/files/2026-06/26-05-Monthly%20Maps.pdf) | 2018→, monthly (national); payam maps | N (tabular) / S (payam map) | Open PDF; county extract Restricted (email UNMAS IM) | T3 | Safe routes for returns and agriculture | Database revised from 2018 with over-estimates removed, so the trend partly reflects reclassification |
| Conflict forecasts | [VIEWS](https://viewsforecasting.org/) via [HDX](https://data.humdata.org/dataset/ssd-views-conflict-forecasts) (PRIO-GRID 0.5°) | Forecasts 2026→ on HDX; historical archive on the VIEWS site | C (0.5° grid) | Open | T3 | Forward-looking risk layer | Prediction, not observation. Keep visually separate |

### 2c. Displacement, mobility and population

| Variable | Source and link | Time span | Avail. | Access | Tier | Decision-maker use | Caveats |
|---|---|---|---|---|---|---|---|
| New arrivals from Sudan (refugees + South Sudanese returnees) | UNHCR [new-arrivals-from-sudan](https://data.humdata.org/dataset/new-arrivals-from-sudan) (daily, national); RRC/UNHCR/IOM [border monitoring](https://data.humdata.org/dataset/population-movement-from-sudan-to-south-sudan); [UNHCR Sudan situation portal](https://data.unhcr.org/en/situations/sudansituation) | Apr 2023→ | N daily; points of entry (Joda/Wunthou in Renk, Panakuach, Amiet in Abyei, Aweil) assignable to counties for periods with POE data | Open | T1 | Renk/Malakal reception capacity, onward transport, cholera risk at transit sites | 2018 = 0, so do not index; show absolute values. Joda monitoring was interrupted intermittently in 2025 |
| Refugees hosted in South Sudan by location | UNHCR [population data](https://data.humdata.org/dataset/unhcr-population-data-for-ssd), [South Sudan portal](https://data.unhcr.org/en/country/ssd) | 2018→ | CA (camp/county) | Open | T2 | Maban, Jamjang/Ajuong Thok (Pariang), Gorom and Makpandu host-community pressure on land, wood and water | Camp-level figures need manual mapping to counties |
| IOM DTM flow monitoring (cross-border and internal movements) | [IOM DTM flow monitoring](https://data.humdata.org/dataset/dtm-south-sudan-flow-monitoring-migration-population-movement-iom), [registry 2025](https://data.humdata.org/dataset/south-sudan-flow-monitoring-registry-jan-aug-2025-iom-dtm) | 2018→ | CM (at flow-monitoring points) | Open | T2 | Seasonal and crisis movement corridors | Point-based, not wall-to-wall |
| IDMC new displacements (conflict vs disaster) | [IDMC GIDD](https://data.humdata.org/dataset/idmc-idp-data-ssd); [IDU events](https://data.humdata.org/dataset/ssd-idmc-idu-events) | Annual 2011–2025 (national); IDU 2025→ | N / events | Open | T3 | Splits displacement into conflict and disaster causes, which is the comparison this project is about | National annual totals |
| Displacement forecasts (AHEAD model, admin-2) | Danish Refugee Council via [HDX](https://data.humdata.org/dataset/south-sudan-subnational-displacement-forecasts) | 2025→ | CM (forecast) | Open | T3 | Forward planning | Outside the 2018–2025 window apart from late 2025 |
| Gridded population adjusted for displacement | GRID3/WorldPop [2019 estimates](https://data.humdata.org/dataset/south-sudan-2019-gridded-population-estimates); WorldPop [2015–2030](https://data.humdata.org/dataset/worldpop-population-counts-2015-2030-ssd) | 2019; 2015–2030 annual | CA | Open | (denominator) | Per-capita normalisation of every count layer | Census is from 2008, so uncertainty is large. Use as a denominator, not a headline layer |

### 2d. Food systems, livelihoods and economy

| Variable | Source and link | Time span | Avail. | Access | Tier | Decision-maker use | Caveats |
|---|---|---|---|---|---|---|---|
| FEWS NET food-insecurity classification (IPC-compatible), current and projected | FEWS NET via HDX, e.g. [Oct 2018–May 2019](https://data.humdata.org/dataset/south-sudan-acute-food-insecurity-classification-october-2018-may-2019) (~100 shapefiles); [FEWS NET Data Warehouse](https://fdw.fews.net/) | 2011→, about every 1–4 months | CM (polygon overlay to counties) | Open | T1 (as an IPC gap-filler) | More frequent than IPC rounds; gives continuity between IPC analyses | Polygons follow livelihood zones and areas, so overlay them onto counties. Not identical to official IPC |
| Net cereal production by county | FAO/WFP [CFSAM special reports](https://www.fao.org/markets-and-trade/publications/detail/en/c/1682438/) (2023 shown; also [2024](https://reliefweb.int/report/south-sudan/special-report-2024-faowfp-crop-and-food-security-assessment-mission-cfsam-republic-south-sudan-may-2025)) | Annual (missions in 2018–2024) | CA | Open (PDF annex tables) | T2 | FAO/WFP response sizing and the cereal deficit by county | Must be extracted from PDF annexes. Some missions report by state; check each year. Traditional sector only |
| Subnational crop statistics (harmonised) | [HarvestStat Africa](https://data.humdata.org/dataset/harveststat-africa) | to 2022 | CA (maybe) | Open | T3 | Cross-check for CFSAM | South Sudan coverage is likely thin; verify before use |
| Household-level shocks and food security (DIEM) | FAO [DIEM monitoring](https://data.humdata.org/dataset/fao-diem-monitoring-system-household-surveys-aggregated-data) | Dec 2022→ | C (admin-1) | Open | T3 | Livelihood shocks reported by farmers and pastoralists | Admin-1, short series |
| Market prices and market functionality (JMMI) | REACH/Cash Working Group [JMMI](https://repository.impact-initiatives.org/) monthly factsheets (e.g. [Dec 2025](https://repository.impact-initiatives.org/document/repository/36af13d8/REACH_SSD_Factsheet_JMMI_December_2025.pdf)); [REACH Resource Centre](https://www.impact-initiatives.org/resource-centre/) | Aug 2019→, monthly | CM (market towns) | Open (factsheets); raw data on request | T2 | Cost of the survival minimum expenditure basket (MSSMEB), supply disruptions; complements WFP prices with more markets | Starts after 2018, so index to 2019 or show absolute values |
| Cross-border trade flows | FEWS NET [daily cross-border trade](https://data.humdata.org/dataset/daily_cross_border_trade_for_south_sudan_6824) | 2010→ | C (border points) | Open | T3 | Import dependence on Uganda/Sudan routes; the Sudan war cut off northern supply | Point data |
| Real-time food, fuel and exchange-rate estimates | World Bank [Real Time Prices](https://data.humdata.org/dataset/south-sudan-real-time-prices) | 2007→, monthly | CM (market) / N (FX) | Open | T2 (exchange rate) | SSP depreciation drives price spikes, especially after the Feb 2024 pipeline disruption | Includes ML-imputed values, so flag them |
| Hard-to-reach settlement monitoring (Area of Knowledge) | REACH [AoK factsheets](https://repository.impact-initiatives.org/document/reach/3f42f9cc/REACH_SSD_Factsheet_Assessment-of-Hard-to-Reach-Areas-FSL_May2023.pdf) | 2016–2023, monthly | CM (counties with ≥5% of settlements assessed) | Factsheets open; data on request | T2 | Hunger, service access and displacement where agencies cannot go, that is, in the access-constrained counties | Coverage varies by county and month. Programme scaled down after 2023 |
| Humanitarian needs, people in need (PiN) by county (longer series than HAPI) | OCHA HPC [south-sudan-humanitarian-needs](https://data.humdata.org/dataset/south-sudan-humanitarian-needs); [JIAF severity](https://data.humdata.org/dataset/ssd-jiaf-humanitarian-needs-pin-and-severity) | 2016–2026, annual | CA | Open | T2 (extends the planned HAPI layer back to 2018) | Response prioritisation | Methods changed between years (JIAF 1 to JIAF 2), so trends need caution |
| Funding received | [OCHA FTS](https://data.humdata.org/dataset/ssd-requirements-and-funding-data); [CBPF allocations](https://data.humdata.org/dataset/south-sudan-cbpf-allocations-and-contributions); [CBPF Data Hub](https://cbpf.data.unocha.org/) (project locations) | 2018→ | N (FTS); CA (CBPF by location) | Open | T2 | For donors: where funding went compared with need | Locations of CBPF projects are partial |

### 2e. Health

| Variable | Source and link | Time span | Avail. | Access | Tier | Decision-maker use | Caveats |
|---|---|---|---|---|---|---|---|
| Cholera cases | WHO [cholera data on HDX](https://data.humdata.org/dataset/world-health-organization-who-cholera-data) (2023→); county figures in MoH/WHO situation reports | 2023→ (outbreak from Oct 2024 into 2025) | CM (from situation reports) | Open | T1 for 2024–25 | WASH and health response, linked to flooding and crowding at transit sites (Renk, Malakal, Bentiu) | Event-based: 2018 = 0, so do not index. County figures need extraction from PDFs |
| Malaria, measles, hepatitis E, acute watery diarrhoea (weekly consultations) | MoH/WHO [IDSR weekly bulletins](https://www.afro.who.int/countries/south-sudan/publications) (e.g. [week 44 2025](https://www.afro.who.int/sites/default/files/2025-12/South%20Sudan%20IDSR%20Weekly%20Bulletin%20Week%2044%2C%2027%20October-02%20November%202025%20.pdf)) | 2018→, weekly | C/CM (county tables appear in some issues; reporting-completeness maps by county) | Open (PDF) | T2 | Malaria peaks follow floods. Hepatitis E in Bentiu is a well-documented flood-and-camp outbreak | Fewer than 50% of facilities report, so counts track reporting effort. Extraction from PDFs is labour-intensive |
| Malaria burden (modelled Pf prevalence and incidence) | [Malaria Atlas Project](https://data.malariaatlas.org/maps) (`malariaAtlas` R package) | 2000–2022, annual | CA (5 km raster) | Open | T3 | Baseline vulnerability | Modelled; years after 2022 missing; check `max_raster_year` |
| Travel time to health care and schools | [HeiGIT accessibility indicators](https://data.humdata.org/dataset/south-sudan-accessibility-indicators); [MAP travel-time/friction surfaces](https://malariaatlas.org/research-project/accessibility-to-cities/); [walking time to Level IV facility](https://data.humdata.org/dataset/south-sudan-walking-travel-time-to-nearest-level-iv-health-centre) | 2019 / 2026 | S | Open | T2 | Which counties are isolated; combine with the flood layer to show isolation in the wet season | Static; ignores seasonal flooding of roads |

### 2f. Infrastructure, access and connectivity

| Variable | Source and link | Time span | Avail. | Access | Tier | Decision-maker use | Caveats |
|---|---|---|---|---|---|---|---|
| Road access constraints (passable, restricted, impassable) | Logistics Cluster [access constraints maps](https://logcluster.org/en/ops/ssd11a), e.g. [2 Jul 2026](https://logcluster.org/en/documents/south-sudan-access-constraints-map-2-july-2026); archive on [ReliefWeb](https://reliefweb.int/map/south-sudan/south-sudan-access-constraints-map-30-may-2025) | 2017→, weekly or bi-weekly | CM (after digitising) | Open PDF; GIS on request | T2 | WFP/Logistics: road deliveries compared with airdrops; shows physical access only, not security | PDF maps only, so digitising takes effort. Fallback: digitise one wet-season map and one dry-season map per year |
| Road surface and passability change | HeiGIT [Planet road surface and Humanitarian Passability Index](https://data.humdata.org/dataset/south-sudan-planet-road-surface-data) | 2020 and 2024 | S (two epochs) | Open | T3 | Infrastructure investment, e.g. newly paved trunk roads | Main roads only |
| Airstrips | OCHA [airstrips](https://data.humdata.org/dataset/south-sudan-airstrips) | static | S | Open | T3 | Points layer for air access | — |
| Mobile internet coverage and speed | [Ookla open data](https://registry.opendata.aws/speedtest-global-performance/) (quarterly tiles); [OpenCellID](https://opencellid.org/) | 2019→ | CA (sparse) | Open (Ookla, CC BY-NC-SA) / Login | T3 | Feasibility of mobile cash and early-warning dissemination | Very sparse tests outside Juba. GSMA coverage maps are commercial (restricted) |
| Water points | [WPdx](https://data.humdata.org/dataset/wpdx_ssd) | to 2019 | S | Open | T3 | WASH baseline | Out of date |

---

## 3. Master priority table: planned and additional variables

Rationale is written for UNMISS (protection, peacekeeping), OCHA (coordination, access), WFP/FAO (food), donors, and the government (RRC, ministries).

### Tier 1: must-have (the core of the story)

| # | Variable | Planned? | Primary user | One-line rationale | Avail. | Access | Key caveat |
|---|---|---|---|---|---|---|---|
| 1 | Conflict events and fatalities (ACLED; UCDP-GED as a cross-check) | Planned | UNMISS, OCHA, donors | The map is built around where and when violence happens | CM | ACLED login; UCDP open | Media-reporting bias in remote counties. 2018 counts of zero cannot be indexed; use a 3-month rolling sum or the difference from 2018 |
| 2 | Intercommunal and cattle-raid violence (ACLED-derived) | New (derived) | UNMISS, government | The most direct link between resources (pasture, water, cattle) and conflict | CM | Login | The keyword rule must be documented |
| 3 | IDPs and returnees by county (IOM DTM mobility tracking and event tracking) | Planned | OCHA, IOM, government RRC | Where people are and where they moved after floods or attacks | CA (rounds) / events CM | Open | Mobility-tracking rounds are irregular; interpolate carefully or step-plot |
| 4 | Arrivals from the Sudan war (UNHCR/IOM) | New | OCHA, UNHCR, WFP, donors | The biggest new shock of the period (more than 1 million arrivals since Apr 2023) | N daily / POE→county | Open | Show absolute values, not an index |
| 5 | IPC acute food insecurity (phase and population in Phase 3+) | Planned | WFP, FAO, donors | Defines priority counties for response | CA (2–3 analyses a year) | Open | Not every county in every round; projection and current periods overlap |
| 6 | FEWS NET classification (gap-filler) | New | WFP, USAID-legacy donors | Monthly-ish continuity between IPC rounds | CM (overlay) | Open | Not official IPC |
| 7 | Acute malnutrition (IPC AMN / GAM) | Planned | UNICEF, WFP, Nutrition cluster | Mortality-risk outcome | CA | Open | SMART surveys cover only some counties |
| 8 | Food prices (WFP: sorghum, maize, wheat flour) and fuel | Planned | WFP (cash vs in-kind), donors | Shows market stress and the cost of response | CM (markets → county) | Open | Market gaps; currency redenomination effects. Pair with the exchange rate |
| 9 | Precipitation and anomaly (IMERG/CHIRPS) | Planned | All | The main climate driver of floods, drought and the planting season | CM | Open | Use anomaly (% of normal) rather than a raw ratio to 2018: 2018 was itself abnormal in places |
| 10 | Flood / surface-water extent (MODIS; FloodScan; Sentinel-1 GFM) | Planned + new sources | OCHA, WFP, UNMISS (dyke protection in Bentiu) | The 2019–2022 floods displaced hundreds of thousands and submerged pasture | CM | Open | Clouds affect MODIS; the Sudd wetland is always wet, so show the anomaly relative to a seasonal baseline |
| 11 | Flood-affected people by county (OCHA) | New | OCHA, government | Turns flood area into people affected | CA/season (2021–2025) | Open | 2019–2020 only in PDF snapshots; definitions vary by year |
| 12 | Drought index (SPEI or PDSI) | Planned | FAO, WFP | Cumulative water stress for crops and pasture | CM | Open | Use the difference from 2018, not a ratio (values are ≤ 0) |
| 13 | NDVI/EVI (vegetation condition) | Planned | FAO, WFP | Crop and pasture condition; the visual "greenness" story | CM | Open | Index the anomaly against a 2003–2017 climatology, otherwise seasonality swamps the trend. WFP's admin-2 NDVI CSV is ready-made |
| 14 | Humanitarian access incidents and aid-worker attacks (OCHA, AWSD, Insecurity Insight) | New | OCHA, HCT, donors | Shows where aid is blocked, which explains gaps in service coverage | CM | Open | Counts, not an index; tabular OCHA data only from 2022 |
| 15 | Population (WorldPop, plus displacement-adjusted GRID3 2019) | Planned | All | Denominator for per-capita rates; without it, large counties look worse than they are | CA | Open | Census from 2008; high uncertainty |
| 16 | Night-time lights | New | Donors, UNMISS, government | The only monthly satellite proxy for economic activity, electricity and settlement change | CM | Login (or GEE) | Low signal in most counties; mask fires |
| 17 | Cholera (2024–25) | New | WHO, WASH cluster, OCHA | The largest outbreak on record; overlaps with floods and transit sites | CM (from situation reports) | Open | Not indexable (zero in 2018) |

### Tier 2: high value

| # | Variable | Planned? | Primary user | One-line rationale | Avail. | Access | Key caveat |
|---|---|---|---|---|---|---|---|
| 18 | Soil moisture (SMAP / ESA CCI / FLDAS) | Planned | FAO | Crop stress, and flood saturation before river peaks | CM | Open/Login | SMAP is ~9–36 km; saturated or flooded pixels are flagged |
| 19 | Temperature (MERRA-2, TerraClimate, MODIS LST) | Planned | FAO, health | Heat stress on livestock and people (e.g. the March 2024 heatwave closed schools) | CM | Open | Show the difference in °C, not a ratio. Pick one product to avoid clutter |
| 20 | Evapotranspiration | Planned | FAO | Crop water use and drought | CM | Open | Overlaps with SPEI and soil moisture |
| 21 | Fires and burned area (MODIS) | Planned | UNMISS, environment | Seasonal burning, plus a possible signal of village burning in conflict | CM | Open | Most fires are agricultural or pastoral; do not label them as attacks |
| 22 | Pasture biomass (Copernicus DMP) | New | FAO, UNMISS (early warning on cattle migration) | Pasture scarcity pushes herds south and increases clashes | CM | Open | Mask to rangeland |
| 23 | Vegetation Health Index (FAO ASIS) | New | FAO, WFP | The standard agricultural-drought index | CM | Open | Overlaps NDVI |
| 24 | River discharge (GloFAS) and Lake Victoria level | New | OCHA, government (Ministry of Water Resources), UNMISS (dykes) | Flood early warning months ahead; explains why floods happen without heavy local rain | C (points/basin) | Login / Open | Modelled discharge. Show as a separate chart |
| 25 | Livestock density (GLW) | Planned | FAO, UNMISS | Exposure to pasture shocks and raiding | S (2010/2015/2020) | Open | Static; not a trend |
| 26 | Health facilities and schools (points) | Planned | Health and Education clusters | Service presence; overlay with attacks | S | Open | Functionality is unknown; IOM DTM village assessments give partial functionality data |
| 27 | Crisis sites, camps, UNMISS bases | Planned | UNMISS, CCCM | Protection hotspots | S/CA | Open | PoC sites were redesignated as IDP camps in 2020–21 |
| 28 | Oil infrastructure | Planned | UNMISS, donors | Resource-conflict geography in Unity and Upper Nile; pollution | S | Open | Pair with gas flaring and night-time lights for the trend |
| 29 | Ethnic group areas (GeoEPR) | Planned | UNMISS | Context for intercommunal violence | S | Open | Politically sensitive; coarse polygons. Present as context, never as blame |
| 30 | Humanitarian needs (HAPI / HPC PiN, JIAF severity) | Planned (+ longer HPC series) | OCHA, donors | Annual response priority | CA | Open | Methodology changes over the period |
| 31 | 3W operational presence | Planned | OCHA, donors | Gaps where need is high and few partners operate | CA (monthly in recent years) | Open | Reporting completeness varies |
| 32 | Arrivals by point of entry, refugee hosting areas | New | UNHCR, government | Pressure on host communities | CA | Open | Manual mapping from camp to county |
| 33 | Violence against civilians, verified by UNMISS HRD | New | UNMISS | The mission's own validated numbers | Quarterly (state) | Open PDF | PDF extraction |
| 34 | Attacks on health, education and food systems; CRSV; children (Insecurity Insight) | New | Protection, UNICEF | Protection monitoring | CM | Open | Under-reported |
| 35 | IDSR disease burden (malaria, measles, hepatitis E, AWD) | New | WHO, Health cluster | Post-flood and camp-related outbreaks | C/CM | Open PDF | Reporting completeness <50% |
| 36 | Net cereal production by county (CFSAM) | New | FAO, WFP, government (Ministry of Agriculture) | Annual production gap per county | CA | Open PDF | PDF extraction; state-level in some years |
| 37 | JMMI market prices and functionality | New | Cash Working Group, WFP | More markets than WFP covers | CM (from 2019) | Open factsheets | Baseline 2019 |
| 38 | Exchange rate and real-time prices (World Bank RTP) | New | Donors, WFP | Currency collapse drives prices | N / CM | Open | ML-imputed values |
| 39 | Settlement change (Open Buildings Temporal) | New | UNMISS, UN-Habitat, government | Abandoned villages, growth of displacement towns | CA (2016–2023) | Open | Ends 2023; uncalibrated confidence |
| 40 | Road access constraints (Logistics Cluster) | New | WFP, Logistics Cluster | Explains seasonal isolation | CM (digitised) | Open PDF | Digitising effort |
| 41 | Travel time to services (HeiGIT, MAP) | New | Health, Education | Structural isolation | S | Open | Static |
| 42 | Hard-to-reach area monitoring (REACH AoK) | New | OCHA, Food Security and Livelihoods cluster | The only monthly signal from inaccessible counties | CM (2018–2023) | Factsheets open; data on request | Ends around 2023; patchy coverage |
| 43 | Funding (FTS, CBPF) | New | Donors | Funding against need | N / CA | Open | Partial location data |

### Tier 3: nice to have

| # | Variable | Planned? | Rationale | Avail. | Access | Caveat |
|---|---|---|---|---|---|---|
| 44 | Wind | Planned | Dust and fire spread; weak link to conflict | CM | Open | Low value for decision-makers |
| 45 | Surface reflectance | Planned | Input to other indices, not a decision variable | CM | Open | Use it to derive indices, not as a map layer |
| 46 | Sentinel-5P NO2, CO, aerosols | Planned | Oil-field and urban emissions, smoke from burning | CM | Open | NO2 signal is weak outside Juba and oil fields; starts mid-2018, so the 2018 baseline is partial |
| 47 | Esri annual land cover | Planned | Cropland expansion or abandonment | CA (2017–2024) | Open | Class noise between years exceeds real change |
| 48 | Soil type | Planned | Static context (cracking clays flood) | S | Open | Not a trend |
| 49 | Species-richness proxies | Planned | Biodiversity context (Sudd, Boma-Badingilo migration) | S | Open | Little operational use |
| 50 | Georgetown WPS index | Planned | National context only | N (biennial) | Open | Cannot be mapped to counties (see Section 4) |
| 51 | GRACE terrestrial water storage | New | Basin-scale wetting since 2019 | C | Login | Too coarse; data gap in 2017–18 |
| 52 | Gas flaring by site | New | Oil-activity trend | CA | Open | Oil counties only |
| 53 | ASAP hotspots, IGAD CDI, FAPAR anomaly | New | Official early-warning flags | C / CM | Open | Overlap with NDVI and SPEI |
| 54 | Dynamic World, Trends.Earth, CTrees biomass, GHSL | New | Land-change context | CA / S | Open | Noisy or static |
| 55 | Landmines and ERW (UNMAS) | New | Return and agriculture safety | N / S | PDF; county data restricted | Database reclassification |
| 56 | VIEWS forecasts, DRC displacement forecasts | New | Forward-looking | C / CM | Open | Predictions; keep them separate |
| 57 | IDMC conflict vs disaster displacement | New | National split of displacement causes | N | Open | National |
| 58 | Mobile coverage (Ookla, OpenCellID) | New | Feasibility of digital cash and early warning | CA (sparse) | Open / Login | Very sparse |
| 59 | Malaria Atlas Project prevalence | New | Baseline vulnerability | CA (to 2022) | Open | Modelled |
| 60 | Cross-border trade, DIEM, HarvestStat | New | Livelihood context | C | Open | Coverage gaps |
| 61 | Airstrips, road surface, water points | New | Logistics points | S | Open | Static or dated |
| 62 | Desert locust, Climate TRACE | New | Footnotes | event / C | Open | Marginal |

---

## 4. What is NOT possible at county level for 2018–2025, and the best fallback

| Desired indicator | Why it is not possible | Best available fallback |
|---|---|---|
| Girls' school enrolment / gender parity | The EMIS and school census are national or state-level and irregular. The OCHA [schools and enrolment](https://data.humdata.org/dataset/south-sudan-schools-and-enrolment-data-2015-sssams) data dates from 2015. No MICS or DHS since 2010 | School locations (planned) plus [Education in Danger incidents](https://data.humdata.org/dataset/south-sudan-attacks-on-civilians-and-vital-civilian-facilities); IHME LBD [educational attainment](https://ghdx.healthdata.org/) gridded estimates (to ~2017, modelled); national [UNESCO UIS](https://data.humdata.org/dataset/unesco-data-for-south-sudan) |
| Vaccination coverage (DTP3, measles) | WUENIC estimates are national; administrative data by county is not published and is unreliable | National [WHO indicators](https://data.humdata.org/dataset/who-data-for-ssd); measles cases from the IDSR bulletins as an outcome proxy; IHME LBD vaccine-coverage grids (to ~2016–2019) |
| Infant / under-5 mortality, maternal mortality | Last household survey was the 2010 South Sudan Household Health Survey. No vital registration | IHME LBD under-5 mortality 5 km grids (to 2017, modelled); IPC malnutrition (GAM) as the closest mortality-risk proxy; crude death rates from SMART surveys for some counties only |
| Women, Peace and Security index | Computed nationally only (Georgetown GIWPS) | Show it as a national context badge. At county level, use CRSV incidents (Insecurity Insight / UNMISS HRD) as a partial proxy for the security dimension |
| GBV prevalence or incidents | GBVIMS data is not public (protection-sensitive) | CRSV incidents (Insecurity Insight, UNMISS HRD), GBV components of the HNO PiN where published |
| Child recruitment | The UN Secretary-General's Children and Armed Conflict report verifies cases nationally; locations are not released | [Insecurity Insight children-in-conflict events](https://data.humdata.org/dataset/children-in-armed-conflict-data) (partial, open-source) |
| Poverty / income | No recent subnational survey (the World Bank High-Frequency Survey ended around 2017). Microdata are restricted | Meta [Relative Wealth Index](https://data.humdata.org/dataset/relative-wealth-index) (static, ~2021); night-time lights; IPC as a welfare proxy |
| Electricity access | No county series | Night-time lights (Tier 1), noting that most rural light is not grid electricity |
| Livestock numbers over time | No livestock census since ~2009; GLW is a modelled snapshot | GLW static plus pasture biomass (DMP) and cattle-raid events as dynamic proxies |
| Groundwater level | No monitoring network | GRACE TWS (basin scale only), soil moisture |
| Monthly crop yields | Only annual CFSAM estimates exist, partly by state | CFSAM annual county or state tables plus NDVI/VHI seasonal anomalies |
| County-level funding disbursed | FTS is national; CBPF has partial project locations | 3W partner counts as a proxy for presence |
| Election data | No national election held in 2018–2025 (repeatedly postponed) | A timeline annotation layer for political events, plus ACLED "strategic developments" and protest events |
| Mobile network coverage (authoritative) | GSMA and operator data are commercial or restricted | Ookla tiles (sparse) |
| Landmine contamination by county (tabular) | The UNMAS IMSMA extract is not public | Payam maps in UNMAS monthly reports (PDF); request from UNMAS IM (unmas.ss.imsma@unops.org per the report footers) |
| Humanitarian access 2018–2021 as data | OCHA published PDF snapshots only | Digitise from the [ReliefWeb snapshots](https://reliefweb.int/updates?search=south%20sudan%20humanitarian%20access%20snapshot), or use AWSD and Insecurity Insight for the whole period |

---

## 5. Implementation notes for the 2018 = 1.0 index

1. Do not ratio-index event counts with zero or near-zero 2018 values (conflict events in quiet counties, cholera, Sudan arrivals, access incidents), or any variable that can be ≤ 0 (SPEI, temperature in °C, anomalies). Use the difference from 2018 or absolute values (`index_ok: false` in `DATA_CONTRACT.md`). For sparse counts, a 3- or 12-month rolling sum before indexing reduces noise.
2. Seasonality: index the monthly value against the same calendar month in 2018 (or a 2003–2017 climatology for satellite variables), not the 2018 annual mean. Otherwise every map lights up each wet season.
3. 2018 was not "normal": the R-ARCSS peace deal was signed in Sep 2018, and conflict was still high in the first half of the year. Note this on the map so users do not read a decline after 2018 as an improvement in the environment.
4. Boundary consistency: during the 2015–2020 period of 28/32 states, some agency datasets used other county lists. Several datasets (WFP admin-2 CSVs, FEWS NET polygons, HarvestStat) are not on the OCHA COD; crosswalk them by P-code or by spatial overlay. The Abyei, Pibor and Ruweng administrative areas need explicit handling.
5. Per-capita normalisation for every count layer (WorldPop), with a toggle, because county populations differ by more than a factor of 20.
6. Ready-made admin-2 series that save processing time: WFP CHIRPS rainfall and MODIS NDVI (dekadal, with P-codes), and FloodScan admin-2 flood fraction (daily). Use them at least as validation of the team's own zonal statistics.
7. Context-event annotations (timeline markers) cost almost nothing to add and make the trends much easier for decision-makers to read. Suggested markers: Sep 2018 R-ARCSS; Feb 2020 unity government and return to 10 states; Jul 2019 to 2022 consecutive record floods; Apr 2023 Sudan war; Feb 2024 rupture of the oil-export pipeline in Sudan; Mar 2024 heatwave closing schools; Oct 2024 cholera declaration; Mar 2025 Nasir clashes and political crisis. Check each date against ReliefWeb or ACLED before publishing.
8. Sensitivity: ethnic-group layers next to violence can be read as attributing blame. Keep GeoEPR as a toggle-only context layer with neutral styling and a disclaimer. Do not publish exact coordinates of aid-worker incidents or CRSV events beyond what the source already publishes; aggregate them to county.

---

## 6. Source index (verified on 14 Nov 2026)

- HDX South Sudan group (573 datasets): <https://data.humdata.org/group/ssd>. All `data.humdata.org/dataset/...` links above were confirmed through the HDX CKAN API.
- ACLED: <https://acleddata.com/> · UCDP: <https://ucdp.uu.se/downloads/>
- NASA LAADS VNP46: <https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/VNP46A3/> · EOG: <https://eogdata.mines.edu/products/vnl/>
- GloFAS / CEMS EWDS: <https://ewds.climate.copernicus.eu/datasets/cems-glofas-historical> · GFM: <https://global-flood.emergency.copernicus.eu/>
- GRACE-FO mascons: <https://grace.jpl.nasa.gov/data/get-data/jpl_global_mascons/>
- DAHITI: <https://dahiti.dgfi.tum.de/> · G-REALM: <https://ipad.fas.usda.gov/cropexplorer/global_reservoir/>
- Open Buildings Temporal: <https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_Research_open-buildings-temporal_v1>
- UNMISS HRD reports: <https://unmiss.unmissions.org/en/node/28652?page=0>
- UNMAS IMSMA monthly: <https://unmas.org/sites/default/files/2026-08/IMSMA_Monthly_July2026.pdf>
- CFSAM 2023: <https://www.fao.org/markets-and-trade/publications/detail/en/c/1682438/>
- REACH / IMPACT repository (JMMI, AoK): <https://repository.impact-initiatives.org/>
- Logistics Cluster South Sudan: <https://logcluster.org/en/ops/ssd11a>
- WHO AFRO IDSR bulletins: <https://www.afro.who.int/countries/south-sudan/publications>
- Malaria Atlas Project: <https://data.malariaatlas.org/maps>
- Ookla open data: <https://registry.opendata.aws/speedtest-global-performance/>
- UNHCR Sudan situation: <https://data.unhcr.org/en/situations/sudansituation>

Not verified (needs checking before use): that the FloodScan xlsx covers 1998 onward; whether each CFSAM year has county-level annex tables; HarvestStat coverage of South Sudan; DAHITI virtual stations in the Sudd and Lake No; whether REACH AoK raw data can be downloaded; the exact final year of each MAP raster.
