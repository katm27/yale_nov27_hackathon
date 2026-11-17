# What analyses this panel can credibly support

This note asks which causal, predictive and classification analyses the compiled South Sudan county panel can support for an external audience, and which it cannot. It assumes a reader who will check the design, not only the result. Variable ids refer to `docs/data/variables.json`; quality ratings refer to `METHODS_AND_DATA_GUIDE.md` §5.

## 1. Binding constraints

**Sample size.** The panel has 79 counties × 96 months (7,584 county-months), but far fewer independent observations. Rainfall and temperature anomalies are correlated over hundreds of kilometres, so in any season the 79 counties experience perhaps five to ten distinct shocks. Many outcomes are seasonal and persistent: the median lag-1 autocorrelation of temperature is 0.53, and after correcting for persistence the number of significant county trends falls from 4,510 to 1,015 (`STATISTICS_EXPLAINED.md`). The binding count is the number of years. Eight years is eight draws of the rainy season and of national politics, and anything that varies by year (a peace deal, the 2023 Sudan war, the 2025 aid cuts) cannot be separated from any other year-level shock.

**The 2018 start.** 2018 was a dry year, and it began during the civil war and before the R-ARCSS peace deal (September 2018). Indexing to 2018, or estimating trends from it, builds that unusual year into the result. A climatology from a longer record (2001–2017 for satellites, 1991–2020 for CHIRPS) is the right reference.

**Survey variables are rounds, not months.** IPC has 10 county analyses in the processed panel (none between January 2020 and February 2022). DTM Mobility Tracking has 14 rounds. HNO and ISNA have three to six. The app carries these values forward for up to 8 months. Any model that treats carried months as observations overstates the sample size by a factor of about 8 and creates artificial persistence. These series must be analysed at the round level.

**Conflict and displacement data measure recording.** ACLED and UCDP count reported events, and reporting depends on access, media attention, the presence of UNMISS and NGOs, and roads that close in the wet season. A flood can lower recorded conflict by cutting access while raising actual conflict. IOM Event Tracking is flash monitoring of events IOM chose to track, so a zero means "nothing tracked". Flow Monitoring counts people passing fixed points, mostly at Renk after 2023.

**Ecological inference and MAUP.** County aggregates say nothing about individual behaviour, and results can change when the same data are aggregated to states or grid cells. Counties range from a few hundred to more than 20,000 km², so a county mean mixes very different exposures.

**Measurement error.** Rainfall products agree on levels (CHIRPS–IMERG r = 0.89) but poorly on anomalies (r = 0.33) and disagree in trend sign. Classical error in the treatment biases estimates toward zero. Because the anomaly correlation is so low, results that hold only for one product should not be reported. GRACE storage is effectively ~300 km resolution and should only be used at basin or regional scale. MERRA-2 temperature cells are as large as counties. Sentinel-1 flood is reliable only in July–November and lost half its revisit after December 2021. TerraClimate precipitation and the drought ensemble's TerraClimate members drift dry and should not be used for trends or anomalies.

**Endogeneity of the response.** OCHA partner presence (`ops_orgs`), UNMISS sites, logistics hubs and IPC classifications all respond to need and insecurity. Aid goes where crises are, so aid will correlate positively with bad outcomes. Funding series are national only and cannot vary across counties.

**Post-treatment bias and multiple testing.** Conditioning on NDVI, prices or displacement when estimating the effect of rainfall on conflict blocks part of the effect and can open spurious paths. The panel has more than 200 variables. With that many outcomes, lags and subgroups, some results will cross p < 0.05 by chance, and external readers know this.

## 2. How far back the data can go

The most useful extension is to push the climate–conflict core back to 2011–2012. That gives 14–15 years and covers the civil-war period, which helps power but also changes the context. The repo already holds ACLED admin-2 monthly data from 2011 (`data/raw/acled/ssd_*.xlsx`, years 2011–2026; 2011 is partial because South Sudan became independent in July). Start dates checked against the repo and the providers:

| Source | Available from | Note |
|---|---|---|
| CHIRPS v3 rainfall | 1981 | Africa monthly TIFFs; same script, wider year range |
| IMERG V07 Final | mid-2000 | via NASA POWER, GES DISC or Earth Engine |
| MODIS NDVI, LST, reflectance, fire | 2000 (Terra), 2002 (Aqua) | same Planetary Computer collections |
| VIIRS active fire | 2012 | MODIS fire covers 2000–2011 |
| GRACE / GRACE-FO | 2002-04 | 11-month gap Jul 2017–May 2018 between missions; ~300 km |
| Sentinel-1 | late 2014 | dense only 2016–2021 (two satellites) |
| SMAP | 2015 | |
| ACLED (admin-2, in repo) | 2011 | 51 events in 2011, 187 in 2012, ~800–1,000/yr from 2014 |
| UCDP GED | 1989 | the repo extract is 2018–2025; the global file covers earlier years |
| WFP prices (in repo) | 2006 | 3–8 markets until 2014, 12–13 in 2015–2019, 19–34 after 2020 |
| IPC county analyses | ~2013 (South Sudan); 2017–2023 file in repo | FEWS NET IPC-compatible maps from 2009, by livelihood zone and less consistent |
| IOM DTM Mobility Tracking | Jan–Feb 2018 (pilot round, 23 counties) | cannot be extended; earlier DTM is PoC-site headcounts |
| IOM Event Tracking | Dec 2019 | |
| OCHA 3W presence | 2019 | |

County boundaries need care before 2018. States were reorganised in 2015 and 2017, and the ACLED admin-2 codes should be checked against the 79-county P-codes for those years with the existing crosswalk tooling. Climate variables have no such problem: they are re-aggregated to the same polygons.

## 3. Analyses ranked by credibility

### 3.1 Long-baseline anomaly monitoring (descriptive)

Question: in which county-months were vegetation, fire, inundation and rainfall unusual relative to their own history? Design: standardised anomalies against a 2001–2017 climatology for each county and calendar month (`modis_ndvi`, `viirs_fire_count`/`fire_count`, `sudd_inundation_pct`, `chirps_precip_mm`, `precip_mm`), with a compound flag only when independent sensors agree (for example a rainfall deficit in both CHIRPS and IMERG plus a negative NDVI anomaly). The panel needs the 2001–2017 extension for these four layers, which the existing scripts can do with a wider date range. This is the most defensible product in the repo because it makes no causal claim, and it repairs the 2018-baseline problem for every other analysis. Report it as "unusual relative to 2001–2017", list the climatology years and sensors, and note that NDVI drops in the Sudd can mean flooding. Effort: 3–5 days, mostly compute.

### 3.2 Weather shocks and recorded conflict (reduced-form causal)

Question: do rainfall deficits or excesses change recorded political violence in the following months? Rainfall anomalies are plausibly exogenous to local politics once county seasonality and national shocks are absorbed, which makes this the only causal design here that does not rest on strong assumptions about selection. It needs the 2012–2025 extension to have useful power. The estimand is the effect on *recorded* violence, interpreted at the county level. The full specification is in §5. Effort: 1–2 weeks.

### 3.3 Out-of-sample forecasting of conflict (predictive)

Question: can the panel predict which counties will record political violence (any event, or fatalities above a threshold) one to three months ahead, better than simple baselines? Design: gradient-boosted trees or a regularised logistic or count model using lagged ACLED and UCDP counts, neighbours' lagged counts (spatial lag), rainfall and NDVI anomalies, fire, prices where observed, and static covariates (`cattle_density`, `pop_total`, livelihood zone). Validation must be rolling-origin: train on months up to t, predict t+h, and roll forward, never shuffle. Add leave-one-region-out folds to test spatial transfer. Benchmarks: persistence (last month's state), a county-specific seasonal mean, and the same model with only conflict history. Report Brier score, area under the precision–recall curve (events are rare in many counties) and calibration plots, with the gain over persistence and a block-bootstrap interval. Prediction claims are credible in their own terms because they are tested on data the model has not seen. They do not show that any feature causes conflict, and feature importances should not be presented as if they did. Expect most skill to come from conflict history. The useful finding is how much the environmental layers add to that baseline, and the answer could easily be "very little". Effort: 1–2 weeks.

### 3.4 Shocks and market prices

Question: how do rainfall and flood shocks, and the April 2023 outbreak of war in Sudan, move USD sorghum and maize prices (`price_sorghum_usd`, `price_maize_usd`, `wage_casual_labour_usd`)? Design: a market-month panel with market and year-month fixed effects and seasonal rainfall anomalies at lags; for the Sudan shock, an event study by distance to the northern border or position on the Renk–Malakal corridor, with leads as the parallel trends check. Use USD series; SSP prices are dominated by inflation (about 250 to more than 4,000 SSP per USD). Only 26–32 counties have markets, so the results describe market towns, and market entry after 2020 changes the sample, so a balanced panel of long-running markets (2015 onward) should be the primary specification. The exchange-rate collapse is a national shock and is absorbed by year-month effects. Effort: 1 week.

### 3.5 Floods and displacement

Question: do flood anomalies raise new displacement? Treatment: wet-season Sentinel-1 flood area relative to the county's own 2016–2025 seasonal median (`flood_s1_flood_km2`), cross-checked with `sudd_inundation_pct`. Outcome: IOM Event Tracking arrivals and flood-caused displacement (`et_ind_flooding`, `et_ind_total`, December 2019 onward), with county and year-month fixed effects. The weakness is detection: IOM tracks events more often when floods are already in the news, so the outcome and treatment share a cause. Two partial checks help: use conflict-caused displacement (`et_ind_local_communal_conflict`) as a falsification outcome that floods should affect less, and test whether DTM stock changes between Mobility Tracking rounds (round-level, 14 rounds) agree. Report this as association with plausibly exogenous flood timing, with the detection caveat written out. Effort: 1 week.

### 3.6 Early warning of IPC phase (predictive, round level)

Question: can satellite and conflict data from the months before an IPC analysis predict the county phase, or the change in phase, better than the previous round? The unit is the county-analysis (about 780 rows in the processed panel; about 1,000 with the 2013–2017 rounds). Validation: leave-one-analysis-out in time order. The benchmarks are the previous round's phase and, more demanding, the IPC's own projections published at the previous round. Beating persistence is easy to claim and rarely meaningful; beating the IPC projection would be a real result. IPC classifications already use rainfall, prices and conflict information, so this is partly predicting analysts from their inputs. Phase 5 is rare; report results as ordinal accuracy and errors by phase, not overall accuracy. Effort: 1–2 weeks including the IPC back-extension.

### 3.7 County typology (classification)

Question: which counties share a climate–livelihood–risk profile? Inputs: long-run climatology and variability (rainfall CV, inundation frequency, NDVI seasonality), static exposure (`cattle_density`, `elevation_mean`, `soil_vertisol_pct`, `lulc_flooded_veg_pct`) and long-run means of conflict and IPC. Standardise, reduce correlated inputs, and cluster with two methods (k-means or Ward, and a Gaussian mixture). Report the number of clusters chosen by stability under bootstrap resampling (mean Jaccard above about 0.75), and compare the result with the FEWS NET livelihood zones in `data/raw/fews_lhz/`. A typology is a description and should be presented as one; its main use is to pre-specify heterogeneity in 3.2–3.5. Avoid clustering on outcomes and then "explaining" the clusters with the same outcomes. Effort: 3–5 days.

### 3.8 Staggered event study of the 2019–2022 floods

Question: what happened to conflict, prices, NDVI and food insecurity in counties after their first extreme inundation year? Treatment timing: the first year in which wet-season inundation exceeds the county's 2001–2017 95th percentile (MODIS-based, so the climatology is available). Estimator: Callaway–Sant'Anna or Sun–Abraham with not-yet-treated controls; naive two-way fixed effects with staggered timing gives contaminated weights. The problem is support: most Sudd and Jonglei counties were treated in 2019–2021, the never-treated counties are drier and differ in livelihoods, and with a 2018 start there are one or two pre-periods. Extending conflict and NDVI to 2012 gives enough pre-periods to look at trends, which is the minimum for this to be shown. Results should be framed as "the flood period", since the floods coincided with COVID-19, the 2020 unity government and the 2021 rise in sub-national violence. Effort: 1–2 weeks; credibility medium-low.

### 3.9 Synthetic control for the Sudd (exploratory only)

A synthetic control treats the 16 Sudd counties as one unit and builds a weighted comparison from other counties. It is weak here: there is one treated unit, the donors experienced the same national shocks and many had their own floods, and inference relies on placebo permutations across donors that are themselves spatially correlated. It can be shown as an illustration next to 3.8, not as a separate estimate. Effort: 3–5 days.

Causal discovery algorithms (PC, Granger networks, convergent cross mapping) applied to this panel would mostly recover seasonality, shared trends and spatial correlation. With 8 years they should not be presented to an external audience.

## 4. What not to do

Do not interpret county-level relationships between rainfall and conflict as statements about how individuals or ethnic groups behave. Do not treat aid presence, UNMISS sites, partner counts or funding as exogenous, or read a positive correlation between aid and bad outcomes as aid causing harm. Do not correlate 2018–2025 trends across 79 counties and call the result causal; any two trending series will correlate, and the counties are not independent. Do not run regressions on carried-forward IPC or DTM months. Do not report any rainfall trend or anomaly effect from a single product, or any TerraClimate-based trend. Do not use national or state series copied onto counties (funding, Insecurity Insight, ACLED state sub-events, WPS) as county variation. Do not use ordinary standard errors or county-clustered standard errors alone; they ignore spatial correlation. Do not control for mediators (NDVI, prices, displacement) when estimating the effect of weather. Do not search across many lags and outcomes and report the best. Regression discontinuity is not available: no administrative threshold in the data assigns treatment, and state borders coincide with too many other differences.

## 5. Recommended first analysis: rainfall anomalies and recorded political violence, 2012–2025

**Data.** Outcome: `acled_pv_events` from the raw ACLED admin-2 file, monthly, 2012-01 to 2025-12 (79 × 168 = 13,272 county-months). Secondary outcomes: `acled_pv_fatalities`, and `ucdp_events` from the full UCDP GED file (independent coding). Falsification outcome: `acled_demonstrations`, which are mostly urban and should not respond to rural rainfall in the way violence might. Exposure: SPI-3 computed from CHIRPS against its 1991–2020 county climatology; replication with IMERG (2001–2020 climatology). Expressed as two indicators, D = SPI-3 < −1 (dry) and W = SPI-3 > +1 (wet), because drought and flood may act differently.

**Model.** Poisson pseudo-maximum likelihood, which handles zeros and does not need a log transformation:

    log E[y_ct] = a_{c,m(t)} + d_t + sum_{k=1..12} (b_k D_{c,t−k} + g_k W_{c,t−k}) + sum_{j=1..3} (l_j D_{c,t+j} + h_j W_{c,t+j})

Here a_{c,m(t)} is a county × calendar-month fixed effect (each county's own seasonality), d_t is a year-month fixed effect (national politics, peace deals, the Sudan war, national reporting intensity), b_k and g_k are the lagged effects, and l_j, h_j are leads that should be zero. The pre-registered summary statistics are the cumulative effects B = sum b_k and G = sum g_k, reported as a percentage change in recorded events (exp(B) − 1). Standard errors: Conley with a 300 km distance cutoff and 12-month serial correlation, and a randomisation test that reassigns whole years of the rainfall anomaly field to the outcome years (all counties moved together), which keeps the spatial structure of the shocks. One pre-specified heterogeneity split: pastoral versus agrarian livelihood zones (FEWS NET 2018), plus pre-2018 versus post-2018 to check whether the civil-war years drive the result.

**Robustness checks**, written down before estimation: CHIRPS vs IMERG; ACLED vs UCDP; leave-one-year-out; leave-one-state-out; counts aggregated to states (MAUP); an any-event binary outcome (linear probability with the same fixed effects); and dropping the wettest months (July–October), when access-driven under-reporting is most likely.

**What would be convincing.** Leads near zero; a cumulative dry or wet effect whose sign agrees across both rainfall products and both conflict datasets; a confidence interval excluding zero under both Conley errors and year-permutation inference; no single year or state driving the result; a null for demonstrations; and timing that fits a mechanism stated in advance (for example, effects concentrated in the dry season after a failed rainy season, when cattle move). A result of roughly 10% or more per dry episode with those properties would be a credible, modest finding about recorded violence.

**What would not be convincing.** Significance under county-clustered errors only; agreement in one rainfall product but not the other; non-zero leads; a negative wet-season effect that appears only in the wet months (more likely reporting than peace); results that disappear when one year (2021, for example) is dropped; or a significant effect found only after trying several lag windows or subgroups. A precise null is also a reportable result and should be presented with its confidence interval.

**Power.** About 14 seasons and perhaps five to ten spatially distinct anomaly patterns per season give on the order of 70–140 effective shocks. That should detect effects of about 10–15% per dry episode but not smaller ones. Before estimating, the power should be checked by simulation: add a known effect to the observed outcomes using the real rainfall fields and see how often the full procedure, including Conley errors, recovers it.

**Effort.** Extending CHIRPS and IMERG to 1991/2001 and loading ACLED 2012–2017: 2–3 days. Checking the pre-2018 admin-2 codes: 1 day. Estimation, robustness and the permutation test: 3–4 days. A written pre-analysis plan should be committed to the repo, with a timestamp, before the outcome data are merged with the extended rainfall.

Sources for start dates: repo files (`data/raw/acled/`, `data/raw/wfp_prices/`, IPC files), the [DTM Mobility Tracking Report 1](https://displacement.iom.int/reports/south-sudan-%E2%80%94-mobility-tracking-report-1-16-april-2018), [CHC CHIRPS](https://www.chc.ucsb.edu/node/497) and [NASA GES DISC IMERG V07](https://www.earthdata.nasa.gov/data/catalog/ges-disc-gpm-3imergm-07). Other start dates (MODIS, VIIRS, Sentinel-1, SMAP, UCDP) are standard mission dates and should be confirmed before publication.
