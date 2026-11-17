# Logistics story: the Sudd's dry season has stopped drying

All numbers below were recomputed from the repo data with the scripts in this scratchpad (`allvars.py`, `access.py`, `sudd.py`, `story.py`, `corro.py`, `hubs.py`, `demand.py`, `demand2.py`, `idp.py`, `fuel*.py`, `premium.py`). The trend functions come from `scripts/trend_stats.py`. The repo was only read, never written.

## 1. Survey of all 279 variables (full table in section 5)
- Coverage: 279 variables in total. 195 have county trends in trends.json, and 938 of the 13,441 county-variable trends are FDR-significant. Only 36 variables have any FDR-significant county.
- National series: counts are summed over a balanced panel of counties (those with data in at least 80% of months). Shares and indices use the mean of the counties reporting, and WFP prices use the median across markets. Monthly series are tested with the Hirsch-Slack seasonal MK, with the Sen slope anchored on the same month of 2018. Annual, irregular and survey series are reduced to yearly means and tested with plain MK.
  - 57 of 234 testable national series have p < 0.05.
  - After BH-FDR across those 234 tests, 18 remain:
    - Sudd inundation km² and %, and Sudd open water.
    - MODIS surface water % and km².
    - GRACE total water storage.
    - DTM returnees and population.
    - Ten SSP-denominated prices and wages. These are inflation; none of the US$ prices survives.
- Seasonality, from the national monthly climatology:
  - Water, flood and soil peak in Aug-Oct and reach their minimum in Mar-Apr.
  - Fires and burned area peak in Dec-Jan.
  - Fuel prices in US$ peak in May-Jun and are lowest in Jan-Feb.
- Caveat on the 2018 anchor: 2018 was a low-flood year (Sudd peak 6,886 km² against 20,895 in 2019) and a relatively wet year for CHIRPS. Anchored slopes therefore overstate water increases and the fall in rainfall.
  - Example: CHIRPS is down in all 79 counties and the national p is 0.011, yet 0 counties are significant.
  - For the main story I used Feb-Apr annual means and annual minima, so the anchor plays no role there.

## 2. The story: the problem season moved from the wet season to the dry season

**Summary.** In 13 of the 16 Sudd counties, the water that used to drain away by Feb-Apr now stays. The yearly low-water floor has risen every year since 2020, while the wet-season peak has not trended. The low-water months were the dry-season road window for pre-positioning, and that window has mostly closed. Nine Logistics Cluster storage points (35% of the mapped storage area) sit in these counties. Neither the radar flood layer nor the flood-event records show this water.

### Key numbers (recomputed)
| What | Number | Test |
|---|---|---|
| Sudd counties where Feb-Apr inundation rose | 13 of 16 | annual MK n=8 per county, BH-FDR q<0.05. The other 3 are Canal/Pigi (q=0.20), Nyirol and Uror (eastern clay plains, no change). |
| Feb-Apr inundated area, 13 counties | 906 / 1,046 / 927 km² (2018-20), then 3,642 / 7,437 / 8,439 / 9,059 / 10,013 km² (2021-25) | MK p=0.002, Sen +1,501 km²/yr |
| Annual minimum, 13 counties | 807 / 823 / 819 / 2,756 / 5,662 / 6,734 / 7,685 / 8,865 km² (2018-2025). A new record every year since 2020. | |
| Sep-Oct peak, 13 counties | 4,403 (2018) / 12,568 / 18,245 / 19,218 / 17,975 / 12,908 / 19,012 km² (2024) | MK p=0.23. No trend after 2020. |
| Monthly climatology, 2022-25 vs 2018-20 | Jan-May 8.0-9.1× higher; Sep-Oct only 1.4× | |
| Same check without Rubkona and Guit (the well-known Bentiu flood lakes) | Floor 794 → 6,226 km² (a new record every year 2021-25). Feb-Apr MK p=0.002. Sep-Oct p=0.76. | So the floor is not only Bentiu. |
| "Near-dry" months per county per year (inundation ≤ max(2× own 2018-20 Feb-Apr mean, +1 point)) | 6.9 (2018-20) → 1.3 (2022-24). In 2025, 0 in 12 of 13 counties (1 in Panyijiar; Jul-Nov 2025 have no data). | 12 counties FDR-significant decline |
| Local rainfall, Sudd (CHIRPS, mean county annual) | 940 mm (2018) → 751 (2022) → 813 (2025) | MK p=0.063 (falling). The Feb-Apr floor vs previous-year local rain: Spearman −0.79 (n=7). Local rain does not explain the floor. |
| Independent sensor 1: MODIS MNDWI surface water, Feb-Apr, 16 Sudd counties | 0.34% → 6.64% | MK p=0.009; 12/16 counties p<0.05 |
| Independent sensor 2: SMAP surface soil moisture, Feb-Apr | 0.090 → 0.210 m³/m³ | MK p=0.035. The other 63 counties: p=0.11. |
| Sentinel-1 radar "flooded area", Feb-Apr, Sudd | no trend (0.64% in 2018, 0.69% in 2025) | MK p=0.54. Blind by design: its reference is the March median of 2018-2025, so persistent water counts as "normal". |
| Example: Rubkona, March 2024 | Sudd index 45.4%; MODIS MNDWI 34.3%; S1 radar 0.018% | |
| Flood event records (points_disasters, OCHA/GDACS) in the 13 counties | 59 records. 47 end in Dec and 11 in Jan; only 1 covers any Feb-Apr month (Ayod, from Apr 2021). | The official record treats floods as Jul-Dec events. |
| Logistics Cluster storage active in the 13 counties | 6 points / 4,680 m² (23% of mapped m², Jun 2022) → 9 points / 5,760 m² (35% of 16,356 m², Jun 2024 and Jun 2025) | |
| Points opened, reopened or enlarged after the floor rose | Ayod (2022-09), Ganyiel (2022-09), Nyal 360→640 m² (2023-01), Leer (2023-04), New Fangak (2023-04), Bentiu hub 1,440→1,680 m² (2023-04). Also active: Bor hub 1,760 m², Koch, Mabior (Twic East). | |
| IDPs living in the 13 counties (DTM rounds) | 420,162 (Mar 2019) → 705,950 (Feb 2025), +68%. Share of national IDPs 29.6% → 35.4% (peak 37.8%, Sep 2024), against 17.7% of population. | Share trend MK p=0.14 (not significant). DTM county trends: 5 of 13 FDR-significant up. |

### Why a logistics officer should care
1. **Do not plan Sudd road pre-positioning around the Jan-Apr window.** That window was ~7 near-dry months a year in 2018-20 and is ~1 now, and the floor still rose in 2025. Water in the Sudd dry season is now 8-9× the 2018-20 level, more than the wet-season change (1.4×). Plan for river and air resupply all year to Bentiu, New Fangak, Ayod, Nyal/Ganyiel, Leer, Koch and Mabior.
2. **A dry year will not reopen roads.** The floor kept rising while local rainfall fell, and after the weaker 2023 flood peak (12,908 km² vs 17,975 in 2022). Local rain forecasts, or a "dry-spell" signal, are the wrong trigger for the Sudd. Use the Sudd/MODIS water layers.
3. **Which layer is used matters.** The radar flood layer and the flood-event records both show nothing in Feb-Apr. A dashboard built on either would report "no flooding" over ~10,000 km² of standing water in March 2025.
4. **Storage siting.** 35% of the mapped storage area, and all the storage added in 2022-23, is inside the zone where the floor is rising. The caseload there also grew (+68% IDPs). Year-round non-road access, and dyke and siting checks, should be part of every storage decision in these counties.

### Caveats
- **County level only.** A county can be 25% under water while its trunk road stays dry. This shows where the window is closing, not which road segment is cut.
- **Short record.** n=8 annual points per county, so the plain MK is used (Hamed-Rao needs n≥10). The rise looks like a step (Pettitt breaks 2020-07 to 2021-10 in 12 of 13 counties; trends.json step_like=1 in 7). "Since 2020-21" is a fairer description than "x per year".
- **What MODIS can and cannot see.** Dense papyrus is missed in the dry season, so absolute dry-season areas are a lower bound. Jul-Nov 2025 has no data, so the 2025 peak is unknown.
- **The app's own trend outlines differ slightly.** trends.json (2018-anchored, Hirsch-Slack) marks 12 of 16 Sudd counties significant. Bor South is q=0.054 there but q=0.027 in my Feb-Apr test.
- **Storage-point dates.** They come from CONOPS maps up to 2023-09. Points listed after that are carried forward (last_map_date 2023-09 or 2026-06), not reconfirmed every month.
- **IDPs.** DTM is stock at survey rounds and the Dec 2018 round is missing 3 of these counties. The increase in IDP share is descriptive, not significant. Across 79 counties, the change in dry-season water against the change in IDPs gives Spearman r=0.20, p=0.10. No causal claim is made.
- **Ecological inference.** All of this is at county level, and none of it is causal.
- **Not completely new.** The app already shows Rubkona under water in March, and docs/VALIDATION_sudd_water.md notes the rising lows. What is new here:
  - the ratchet happens in 13 counties and continues without Rubkona and Guit;
  - the change is a dry-season change, not a wet-season one;
  - local rain moved the other way;
  - the radar layer and the event records are blind to it;
  - the storage points sit inside the zone.

### Map walkthrough (4-6 steps)
1. `sudd_inundation_pct`, 2019-03, raw, county SS0306 (Fangak), with `points_logcluster_hubs` on. "In March 2019 about 1% of Fangak was under water. This was the dry-season window when New Fangak storage could be stocked."
2. `sudd_inundation_pct`, 2025-03, raw, SS0306, `points_logcluster_hubs` on. "In March 2025, 23.6% of Fangak is under water, and the same pattern covers Rubkona (49.8%), Guit (24.8%) and Mayendit (11.0%), around Bentiu, New Fangak, Leer and Nyal storage."
3. `sudd_inundation_pct`, 2025-12, trend, SS0605 (Mayendit), `points_logcluster_hubs` on. "12 of 16 Sudd counties have a significant upward trend in the app's trend test. Nine storage points, 35% of mapped storage area, sit inside them."
4. `flood_s1_flood_pct`, 2024-03, raw, SS0609 (Rubkona), with `points_disasters` on. "The radar flood layer shows 0.02% of Rubkona flooded in March 2024 and no flood report is active. The water is there, but the radar layer counts it as normal and the reports stop in December."
5. `surface_water_pct`, 2024-03, raw, SS0609. "A second, independent MODIS water map shows 34% of Rubkona under open water that month, so the persistent water is real."
6. `smap_sm_surface`, 2025-03, raw, SS0602 (Guit), with `points_health` on. "Dry-season soil moisture in Guit went from 0.03 (March 2019) to 0.24 m³/m³. Ground that used to dry out by March no longer does. In these counties a median 22% of 2016-registered health facilities had dropped out of the registry by 2023, against 11% elsewhere."

## 3. Runner-up stories
1. **Buy fuel in Jan-Mar.** US$ parallel-market diesel is a median 10.6% dearer in May-Aug than in Jan-Mar of the same year. Correction, 17 Nov 2026: this used WFP's official-rate dollar prices. At the parallel rate the dollar premium disappears after April 2023; see section 4.1.
   - Evidence: 71 market-years (Wilcoxon p=5e-6); 20 of 21 markets have a median ratio above 1 (sign test p=2e-5); 5 of 6 years have a yearly median above 1 (2023: 0.97; 2024: 1.79 during the currency crisis).
   - Petrol (parallel) shows +14.8% (p=3e-6), and official diesel in US$ shows +8.7% (p=7.5e-5).
   - Caveats: market coverage is patchy (14-21 markets); this is ecological; part of the effect is SSP devaluation, since fx is also 21% higher in May-Aug.
   - It is actionable for fuel procurement timing.
2. **Health-registry attrition where the floor rose.** Of the facilities in the 2016 MoH list, a median 22.2% per county were dropped from the registry by 2023 in the 13 counties, against 11.1% in the other 63.
   - Evidence: Mann-Whitney p=0.013. Across 79 counties, the attrition correlates with the rise in Feb-Apr water (Spearman 0.23, p=0.042).
   - Caveat: "dropped" means unconfirmed, not proven closed.
   - Relevance: last-mile medical supply points in these counties may no longer exist.

**Tested and not supported** (reported so they are not reused):
- The change in fuel premium against the change in dry-season water across markets: r=0.39, p=0.11 (n=18).
- The fall in aid-organisation presence in the 13 counties is no different from elsewhere: −23% vs −17%, p=0.27. It fell in 12 of 13 counties, but none is FDR-significant.
- The Sudd share of dry-season fires: 18.6% → 10.1%, MK p=0.23. The fire story already exists in stories.json.
- The S1 radar dry-season trend: none, by construction.
- Sudan arrivals: event-tracking counts, dominated by Renk, Juba and Rubkona in 2023 (409,645), then 195,010 in 2024 and 46,873 in 2025. They are too irregular for a corridor test.

## 4. Findings that have nothing to do with flooding

Added 17 Nov 2026. Each number below was recomputed by the scratchpad scripts `road.py`, `prices_panel.py`, `did.py`, `did2.py`, `seas.py`, `seas2.py` and `f345.py`. Outside data were downloaded on 17 Nov 2026 (sources listed at the end of this section). Four findings were tested; two hold up and two do not.

### 4.1 Since the Sudan war, fuel is no cheaper in US dollars early in the year. In pounds it is much cheaper.

Section 3 suggested buying fuel in Jan-Mar. That result used WFP's `usdprice`, which converts at the official exchange rate. In 2018, for example, Konyokonyo diesel was 200 SSP = US$1.55, an implied rate of 129, while the unofficial rate that month was 211.

I rebuilt the market panel from the raw WFP file (`data/raw/wfp_prices/wfp_food_prices_ssd.csv`):
- Retail prices were converted at each market's own unofficial exchange rate for that month, or the national median unofficial rate where the market had none.
- The seasonal gap was estimated as the May-Aug vs Jan-Mar difference in log price, within market-year (market x year fixed effects).
- 95% intervals come from a market-cluster bootstrap with 300 draws.

| Series (30-35 markets) | Before Apr 2023 | Apr 2023 onward |
|---|---|---|
| Parallel diesel, US$ at parallel rate | +32.7% [+25.7, +41.4] | +5.5% [-1.5, +12.8] |
| Parallel petrol, US$ at parallel rate | +33.4% [+26.1, +41.2] | +0.8% [-4.9, +7.3] |
| Official-market diesel, US$ at parallel rate | +29.4% [+23.1, +36.2] | +1.3% [-3.5, +6.6] |
| Official-market petrol, US$ at parallel rate | +24.2% [+17.1, +31.1] | +4.3% [+0.7, +8.4] |
| Parallel diesel, SSP | +26.2% [+18.6, +33.7] | +70.0% [+56.7, +85.2] |
| Parallel petrol, SSP | +23.9% [+17.7, +30.0] | +54.1% [+39.1, +68.9] |
| Unofficial exchange rate, SSP per US$ | -5.3% [-7.9, -1.9] | +53.1% [+45.1, +60.9] |

Year by year, the median market ratio of May-Aug to Jan-Mar for parallel diesel at the parallel rate was:
- 2021: 1.58
- 2022: 1.18
- 2023: 0.99
- 2024: 1.03
- 2025: 1.03

The pre-war premium therefore rests mostly on 2021-22.

World oil prices do not explain either period. Brent crude's May-Aug / Jan-Mar ratio (FRED) was:
- 2021: 1.18
- 2022: 1.12
- 2023: 0.98
- 2024: 0.99
- 2025: 0.91

Brent was flat or falling in exactly the months when pound fuel prices rose 54-70%. Since 2023 the seasonal swing in pound prices is a currency effect: the pound lost a median 53% of its value between Jan-Mar and May-Aug. The largest jump came in 2024, the year the export pipeline through Sudan was cut (exchange-rate ratio 2.46). Al Jazeera, 26 Mar 2024, cited in the app's context timeline, describes the rupture in Feb 2024.

What to do with this:
- Fuel bought or contracted in pounds should be bought, or fixed in price, in Jan-Mar.
- Fuel bought in dollars at the parallel rate costs about the same all year since 2023.
- The usual advice to buy fuel before the rains is now advice about currency exposure, not about the fuel market.

Caveats:
- Only 30-35 markets, with gaps.
- The post-war window has three years, and 2024 dominates it.
- Seven related tests, so treat p-values near 0.05 with care. The SSP and exchange-rate results are far below any correction threshold. The post-war US$ results are nulls.

### 4.2 Road travel is where aid workers get kidnapped, and 2025 was the worst year in both incident databases

There are two independent incident datasets for 2018-2025:
- Insecurity Insight's aid-worker KIKA file (in the repo).
- The Aid Worker Security Database (AWSD), downloaded from HDX.

They agree on the main points.

| | AWSD | Insecurity Insight |
|---|---|---|
| Incidents 2018-2025 | 498 | 464 |
| Incidents on roads (II: road or checkpoint) | 202 (41%) | 180 (39%) |
| Kidnapped aid workers taken on roads | 114 of 184 (62%) | 91 of 141 (65%) |
| Aid workers killed on roads | 58 of 162 (36%) | 57 of 176 (32%) |
| Road incidents in 2025 vs 2018-24 mean | 41 vs 23.0 (previous high 31); Poisson P(X≥41) = 0.0005 | 37 vs 20.4 (previous high 29); P = 0.0006 |
| All incidents in 2025 vs 2018-24 mean | 99 vs 57.0; P = 3e-7 | 99 vs 52.1; P = 5e-9 |
| States with most road incidents | Jonglei 52, Central Equatoria 49, Eastern Equatoria 28, Unity 20 | Central Equatoria 50, Jonglei 33, Eastern Equatoria 26 |

AWSD codes 196 of its 498 South Sudan incidents as ambushes. South Sudan had the second-highest incident count in AWSD worldwide for 2018-2025 (498), after the occupied Palestinian territories (590).

There is no safe season:
- Road incidents fall in Dec-May about as often as in Jun-Nov: 54% in AWSD (binomial p = 0.23), 51% in Insecurity Insight (p = 0.82).
- The monthly distribution is not significantly uneven (II chi-square p = 0.076).
- December is the quietest month in both sources, with 9 and 7 incidents.

For a logistics officer:
- Road convoys carry most of the kidnapping risk.
- 2025 was a step up in both datasets, after the funding cuts.
- The concentration in Central Equatoria and Jonglei puts the Juba hub's southern corridors and the Bor routes most at risk.

Caveats:
- These are counts of reported incidents, so changes in reporting effort are possible. Both sources rely partly on the same media and agency reports, so they are not fully independent.
- Neither source gives road segments: AWSD publishes coordinates for some incidents, and II's are censored. So no corridor-level test was possible.
- Traffic volume is unknown. A rise in incidents could partly reflect more movement, although funding fell in 2025 (see 4.3).

### 4.3 The 2025 funding cut did not shrink the partner map; national NGOs filled more of it

OCHA FTS (outside, via the public API) puts funding to the South Sudan response plan at US$1,289.3 million in 2024 (plan 1157) and US$787.2 million in 2025 (plan 1223), a fall of 39%. The repo's FTS series match, and add that the US share of humanitarian funding fell from 50% to 31%.

The OCHA 3W counts did not move with the money:
- Organisations reported per county averaged 8.00 in 2024 and 7.97 in 2025. The sum of county means went from 632 to 630. 34 counties rose and 45 fell; Wilcoxon p = 0.57.
- South Sudanese NGOs per county rose from 2.50 to 3.14 (sum 198 to 248). They rose in 54 counties and fell in 21; Wilcoxon p = 4e-6.

For logistics, the partners that common storage, the MSU network and last-mile delivery now depend on are more often national NGOs, at a time when total money is down by more than a third.

Caveat: the 3W counts record presence as reported, not activity or capacity. A partner can stay on the 3W with a much smaller budget.

### 4.4 What did not hold up

Sudan-war supply-corridor effect on northern market prices. I ran a difference-in-differences on the WFP market panel:
- Design: market and month fixed effects; markets north of 9°N vs the rest; May 2021-Apr 2025, with Apr 2023 excluded; market-cluster bootstrap.
- The headline estimates are positive for all six commodities: parallel diesel +11.7% [+0.6, +24.5], sorghum +13.7% [+0.5, +29.0], wheat flour +13.7% [+1.8, +27.6]. Defining "north" by state (Upper Nile, Unity, Northern Bahr el Ghazal, Abyei) gives similar results.
- They do not survive the checks:
  - An event study against Jan-Mar 2023 shows the north-south fuel gap moving by -17% to +4% in the pre-war half-years, which is as much as after the war.
  - A placebo break in May 2022, using pre-war data only, gives -19.0% for parallel petrol (p ≈ 0.05).
  - None of the six estimates passes a Bonferroni threshold (0.05/6).
- My conclusion is that the market data cannot separate a war-corridor effect from the normal instability of these northern markets.
- The arrivals themselves are large: UNHCR's Sudan situation portal lists 1,394,320 refugees and returnees from Sudan in South Sudan (figure dated 9 Nov 2026). But that is a caseload fact, not a price effect.
- I could not test the supply side. WFP's Sudan price file on HDX has no fuel series.

Health-registry drop-out. I tested this as a possible non-flood finding (runner-up 2 in section 3):
- Method: across 75 counties with at least 3 facilities registered in 2016, a rank regression of the drop-out share on four predictors (HC3 errors):
  - change in dry-season water;
  - ACLED political-violence events per 100k, 2018-23;
  - distance from Juba;
  - distance to the nearest Logistics Cluster hub.
- Result: no predictor is significant. Water is the closest (p = 0.085), conflict p = 0.89, distance from Juba p = 0.25, distance to hub p = 0.49.
- A quasi-binomial model on facility counts makes everything significant. It treats facilities as independent and its estimated dispersion was implausibly low (0.14), so I do not rely on it.
- I would drop this finding.

Heat, fire smoke and air operations. I did not test this. The repo has no flight, visibility or airstrip-closure records to link to MODIS land temperature or fire counts, so any claim would be a guess.

### Sources used in this section (all accessed 17 Nov 2026)
- WFP VAM market prices, South Sudan (in repo): https://data.humdata.org/dataset/wfp-food-prices-for-south-sudan
- WFP VAM market prices, Sudan (checked; no fuel series): https://data.humdata.org/dataset/wfp-food-prices-for-sudan
- Aid Worker Security Database, global incidents via HDX: https://data.humdata.org/dataset/aid-worker-security-data-global (file `global-security-incidents`, South Sudan rows, 2018-2025)
- Insecurity Insight, South Sudan aid-worker KIKA incidents (in repo, `data/raw/insecurity_insight/ii_aid_worker_incidents.xlsx`): https://data.humdata.org/dataset/south-sudan-attacks-on-civilians-and-vital-civilian-facilities
- Brent crude, monthly mean of daily prices, FRED series DCOILBRENTEU: https://fred.stlouisfed.org/series/DCOILBRENTEU
- OCHA FTS public API, incoming funding to plans 1157 (2024) and 1223 (2025): https://api.hpc.tools/v1/public/fts/flow?planid=1157 and https://api.hpc.tools/v1/public/fts/flow?planid=1223
- UNHCR operational data portal, Sudan situation: https://data.unhcr.org/en/situations/sudansituation
- Pipeline rupture, Feb 2024 (cited in the app's context timeline): https://www.aljazeera.com/features/2024/3/26/south-sudan-on-the-brink-after-oil-exports-derailed-by-sudans-civil-war

## 5. All-variable table (279 variables)
National aggregation: sum for count variables (aggregate=sum), mean for shares and indices, median for WFP prices. A * after p means the national test has p<0.05. The q column is BH-FDR across the 234 national tests. 'Notable counties' lists the top 2 FDR-significant counties up and down. Peak and trough are months of the national monthly climatology.

| id | label | temporal | nat. agg | counties | months (span) | nat. dir | nat. slope/yr | nat. p | nat. q (BH, 234 tests) | counties rising/falling (of trended) | counties FDR-sig up/down | peak/trough month | notable counties (FDR-sig) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| s5p_co | Carbon monoxide in the air (smoke) | monthly | mean | 79 | 92 (2018-05..2025-12) | up | 0.318 | 0.442 | 0.595 | 71/6 of 79 | 0/0 | Mar/Sep |  |
| s5p_aerosol_index | Dust and smoke index (UV aerosol index) | monthly | mean | 79 | 91 (2018-06..2025-12) | up | 0.0494 | 0.135 | 0.272 | 79/0 of 79 | 0/0 | Feb/Oct |  |
| maiac_aod_055 | Haze (aerosol optical depth) | monthly | mean | 79 | 96 (2018-01..2025-12) | down | -0.00066 | 0.39 | 0.547 | 42/36 of 79 | 0/0 | Mar/Oct |  |
| power_aod_840 | Haze from coarse dust (aerosols, 840 nm) | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.00557 | 0.0131 * | 0.099 | 79/0 of 79 | 77/0 | Jul/Dec | up: Cueibet(2.96%),Rumbek Centre(2.96%) |
| power_aod_550 | Haze from dust and smoke (aerosols) | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.007 | 0.00995 * | 0.0842 | 79/0 of 79 | 76/0 | Jul/Dec | up: Cueibet(3.23%),Rumbek Centre(3.23%) |
| s5p_no2 | Nitrogen dioxide in the air (NO2) | monthly | mean | 79 | 92 (2018-05..2025-12) | down | -0.109 | 0.641 | 0.761 | 49/28 of 79 | 0/0 | Dec/Sep |  |
| tc_vpd | Dryness of the air (vapour pressure deficit) | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.00567 | 0.17 | 0.31 | 79/0 of 79 | 0/0 | Mar/Aug |  |
| tc_srad | Sunshine (incoming solar radiation) | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.165 | 0.0771 | 0.228 | 69/9 of 79 | 0/0 | Feb/Jul |  |
| richness_amphibians | Amphibian species (frogs, toads) | static | mean | 79 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| richness_vertebrates | Animal species (amphibians, birds, mammals) | static | mean | 79 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| richness_birds | Bird species | static | mean | 79 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| richness_mammals | Mammal species | static | mean | 79 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| richness_threatened_birds | Threatened bird species | static | mean | 79 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| richness_threatened_mammals | Threatened mammal species | static | mean | 79 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| spei3 | 3-month drought index (SPEI, satellite rain) | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.00448 | 0.124 | 0.266 | 12/67 of 79 | 0/0 | Jan/Apr |  |
| dr_spei3_tc | 3-month drought index (TerraClimate) | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.131 | 0.126 | 0.266 | 0/79 of 79 | 0/0 | Sep/May |  |
| dr_spi3_chirps | 3-month rainfall index (CHIRPS) | monthly | mean | 79 | 96 (2018-01..2025-12) | down | -0.149 | 0.0101 * | 0.0842 | 1/78 of 79 | 0/0 | Jan/Jun |  |
| drought_ensemble_mean | Drought index (combined, best estimate) | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.0196 | 0.0287 * | 0.154 | 0/78 of 79 | 0/0 | Sep/Jun |  |
| drought_ensemble_agree | Drought sources in agreement (share) | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.00844 | 0.296 | 0.449 | 58/20 of 79 | 0/0 | May/Feb |  |
| drought_ensemble_spread | Drought uncertainty (how much sources disagree) | monthly | mean | 79 | 96 (2018-01..2025-12) | down | -0.00711 | 0.308 | 0.453 | 57/20 of 79 | 0/0 | Sep/Mar |  |
| drought_ensemble_range | Drought uncertainty (range between sources) | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.00705 | 0.288 | 0.44 | 61/18 of 79 | 0/0 | Sep/Jul |  |
| dr_pdsi_tc_z | Long-term drought (Palmer index, adjusted) | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.0336 | 0.19 | 0.342 | 0/79 of 79 | 0/0 | Dec/Jun |  |
| tc_pdsi | Palmer drought index (raw) | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.0816 | 0.205 | 0.352 | 0/79 of 79 | 0/0 | Mar/Nov |  |
| tc_extreme_count | Number of extreme-weather flags | monthly | sum | 79 | 96 (2018-01..2025-12) | up | 1.17 | 0.11 | 0.246 | 76/2 of 79 | 0/0 | Jun/Jan |  |
| tc_extreme_dry | Unusually dry month (flag) | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.0116 | 0.0166 * | 0.117 | 79/0 of 79 | 0/0 | May/Jan |  |
| tc_extreme_heat | Unusually hot month (flag) | monthly | mean | 79 | 96 (2018-01..2025-12) | down | -0.000844 | 0.246 | 0.389 | 69/7 of 79 | 0/0 | Jun/Aug |  |
| tc_extreme_wet | Unusually wet month (flag) | monthly | mean | 79 | 96 (2018-01..2025-12) | down | -0.00211 | 0.102 | 0.246 | 24/50 of 79 | 0/0 | Aug/May |  |
| fire_count | Active fires detected (MODIS) | monthly | mean | 79 | 91 (2018-01..2025-12) | down | -2.83 | 0.912 | 0.957 | 39/38 of 79 | 0/0 | Jan/Jul |  |
| viirs_fire_count | Active fires detected (VIIRS) | monthly | mean | 79 | 96 (2018-01..2025-12) | down | -2.13 | 0.315 | 0.456 | 57/22 of 79 | 0/0 | Dec/Jul |  |
| viirs_noaa20_fire_count | Active fires detected (VIIRS, NOAA-20) | monthly | mean | 79 | 72 (2020-01..2025-12) | up | 0.0775 | 0.414 | 0.57 | 57/20 of 79 | 0/0 | Jan/Sep |  |
| burned_area_km2 | Burned area | monthly | mean | 79 | 96 (2018-01..2025-12) | down | -1.48 | 0.756 | 0.834 | 44/35 of 79 | 0/0 | Dec/Jul |  |
| burned_area_pct | Burned area (% of county) | monthly | mean | 79 | 96 (2018-01..2025-12) | down | -0.0436 | 0.688 | 0.805 | 44/35 of 79 | 0/0 | Dec/Jul |  |
| viirs_frp_sum | Fire intensity (VIIRS) | monthly | sum | 79 | 96 (2018-01..2025-12) | down | -2.36e+03 | 0.615 | 0.746 | 53/26 of 79 | 0/0 | Dec/Jul |  |
| viirs_noaa20_frp_sum | Fire intensity (VIIRS, NOAA-20) | monthly | sum | 79 | 72 (2020-01..2025-12) | down | -133 | 0.582 | 0.717 | 52/27 of 79 | 0/0 | Jan/Sep |  |
| lulc_bare_pct | Bare ground (% of county) | annual | mean | 79 | 72 (2018-01..2023-12) | down | -0.00343 | 0.26 | 0.405 | 16/43 of 79 | 0/0 | – |  |
| lulc_built_pct | Built-up area (% of county) | annual | mean | 79 | 72 (2018-01..2023-12) | up | 0.00891 | 0.00853 * | 0.0799 | 70/9 of 79 | 0/0 | – |  |
| lulc_crop_pct | Cropland (% of county) | annual | mean | 79 | 72 (2018-01..2023-12) | down | -0.00406 | 1 | 1 | 37/41 of 79 | 0/0 | – |  |
| lulc_flooded_veg_pct | Flooded vegetation / swamp (% of county) | annual | mean | 79 | 72 (2018-01..2023-12) | up | 0.966 | 0.0242 * | 0.138 | 63/11 of 79 | 0/0 | – |  |
| lulc_rangeland_pct | Grassland and shrubland (% of county) | annual | mean | 79 | 72 (2018-01..2023-12) | down | -1.6 | 0.133 | 0.271 | 6/73 of 79 | 0/0 | – |  |
| lulc_trees_pct | Tree cover (% of county) | annual | mean | 79 | 72 (2018-01..2023-12) | up | 0.713 | 1 | 1 | 61/18 of 79 | 0/0 | – |  |
| lulc_water_pct | Water (% of county, land-cover map) | annual | mean | 79 | 72 (2018-01..2023-12) | up | 0.0421 | 0.0242 * | 0.138 | 71/7 of 79 | 0/0 | – |  |
| modis_refl_nir | Satellite brightness: near-infrared | monthly | mean | 79 | 92 (2018-01..2025-12) | up | 0.000157 | 0.718 | 0.824 | 54/24 of 79 | 0/0 | Aug/Jan |  |
| modis_refl_red | Satellite brightness: red light | monthly | mean | 79 | 92 (2018-01..2025-12) | down | -0.00176 | 0.0892 | 0.235 | 9/69 of 79 | 0/0 | Mar/Aug |  |
| modis_refl_swir1 | Satellite brightness: shortwave infrared | monthly | mean | 79 | 92 (2018-01..2025-12) | down | -0.00268 | 0.00605 * | 0.0709 | 4/75 of 79 | 0/0 | Apr/Aug |  |
| chirps_precip_mm | Rainfall (CHIRPS) | monthly | mean | 79 | 96 (2018-01..2025-12) | down | -1.46 | 0.0107 * | 0.0861 | 0/79 of 79 | 0/0 | Aug/Jan |  |
| power_precip_mm | Rainfall (MERRA-2 model) | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 1.77 | 0.448 | 0.599 | 23/55 of 79 | 0/0 | Jul/Jan |  |
| precip_mm | Rainfall (NASA IMERG satellite) | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.904 | 0.234 | 0.381 | 42/35 of 79 | 0/0 | Aug/Jan |  |
| tc_ppt | Rainfall (TerraClimate) | monthly | mean | 79 | 96 (2018-01..2025-12) | down | -0.401 | 0.0215 * | 0.129 | 0/79 of 79 | 0/0 | Aug/Jan |  |
| soil_clay_0_30cm | Clay in topsoil | static | mean | 79 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| soil_vertisol_pct | Cracking clay soils (% of county) | static | mean | 79 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| soil_wrb_dominant | Main soil type | static | mean | 79 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| soil_soc_0_30cm | Organic carbon in topsoil | static | mean | 79 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| soil_sand_0_30cm | Sand in topsoil | static | mean | 79 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| soil_phh2o_0_30cm | Topsoil acidity (pH) | static | mean | 79 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| soilwet_root | Root-zone soil wetness | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.00127 | 0.207 | 0.353 | 4/75 of 79 | 0/0 | Oct/Mar |  |
| tc_soil | Soil moisture (TerraClimate) | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 1.59 | 0.732 | 0.824 | 51/28 of 79 | 0/0 | Aug/May |  |
| tair_c | Average air temperature | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.0563 | 0.0715 | 0.228 | 79/0 of 79 | 0/0 | Mar/Aug |  |
| modis_lst_day_c | Daytime ground surface temperature | monthly | mean | 79 | 96 (2018-01..2025-12) | down | -0.393 | 0.00843 * | 0.0799 | 0/79 of 79 | 0/63 | Mar/Aug | down: Melut(-1.057),Mayom(-0.9452) |
| tmax_c | Daytime high temperature | monthly | mean | 79 | 96 (2018-01..2025-12) | down | -0.041 | 0.0635 | 0.218 | 79/0 of 79 | 0/0 | Mar/Aug |  |
| tc_tmax | Daytime high temperature (TerraClimate) | monthly | mean | 79 | 96 (2018-01..2025-12) | down | -0.0185 | 0.283 | 0.436 | 78/1 of 79 | 0/0 | Mar/Aug |  |
| power_t2m_max | Hottest hour of the month | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.0318 | 0.0754 | 0.228 | 78/1 of 79 | 0/0 | Mar/Aug |  |
| modis_lst_night_c | Night-time ground surface temperature | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.127 | 0.0406 * | 0.179 | 78/0 of 79 | 0/0 | Apr/Jan |  |
| tmin_c | Night-time low temperature | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.104 | 0.0684 | 0.227 | 79/0 of 79 | 0/0 | Apr/Dec |  |
| tc_tmin | Night-time low temperature (TerraClimate) | monthly | mean | 79 | 96 (2018-01..2025-12) | down | -0.0372 | 0.955 | 0.993 | 49/29 of 79 | 0/0 | Apr/Jan |  |
| elevation_mean | Average elevation | static | mean | 79 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| elevation_std | Hilliness (terrain ruggedness) | static | mean | 79 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| modis_evi | Vegetation greenness (EVI) | monthly | mean | 79 | 93 (2018-01..2025-12) | up | 0.00277 | 0.506 | 0.654 | 72/7 of 79 | 0/0 | Aug/Feb |  |
| modis13a3_evi | Vegetation greenness (EVI, 1 km monthly) | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.00272 | 0.198 | 0.348 | 71/6 of 79 | 0/0 | Aug/Feb |  |
| modis_ndvi | Vegetation greenness (NDVI) | monthly | mean | 79 | 93 (2018-01..2025-12) | up | 0.00569 | 0.203 | 0.352 | 73/5 of 79 | 0/0 | Aug/Feb |  |
| modis13a3_ndvi | Vegetation greenness (NDVI, 1 km monthly) | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.00654 | 0.13 | 0.27 | 76/3 of 79 | 0/0 | Aug/Feb |  |
| smap_sm_rootzone | Soil moisture, top 1 m (NASA SMAP) | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.00564 | 0.123 | 0.266 | 47/31 of 79 | 0/0 | Sep/Mar |  |
| smap_sm_surface | Surface soil moisture, top 5 cm (NASA SMAP) | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.00831 | 0.0766 | 0.228 | 49/30 of 79 | 0/0 | Sep/Feb |  |
| modis_et_monthly_mm | Water evaporated by land and plants (monthly) | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.844 | 0.0883 | 0.235 | 11/68 of 79 | 0/0 | Aug/Feb |  |
| modis_et_mm | Water evaporated by land and plants (yearly) | annual | mean | 79 | 96 (2018-01..2025-12) | down | -17.4 | 0.174 | 0.315 | 6/69 of 79 | 0/0 | – |  |
| flood_s1_flood_pct | Flooded area (% of county, radar) | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.209 | 0.0138 * | 0.101 | 54/17 of 79 | 0/0 | Sep/Mar |  |
| flood_s1_flood_km2 | Flooded area (radar) | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 10.7 | 0.0263 * | 0.147 | 55/17 of 79 | 0/0 | Sep/Mar |  |
| flood_oilfield_exposure_km2 | Flooded land near oil wells and fields | monthly | mean | 7 | 96 (2018-01..2025-12) | up | 0.0979 | 0.0189 * | 0.12 | 5/1 of 7 | 1/0 | Sep/Mar | up: Rubkona(0.1233) |
| flood_oil_wells_flooded | Oil wells/fields reached by flood water | monthly | sum | 5 | 96 (2018-01..2025-12) | up | 0.5 | 0.0523 | 0.201 | 4/0 of 5 | 0/0 | Sep/Feb |  |
| flood_s1_openwater_km2 | Open water (radar) | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.0281 | 0.029 * | 0.154 | 24/27 of 79 | 0/0 | Dec/Mar |  |
| flood_population_exposed | People living in flooded areas | monthly | sum | 79 | 96 (2018-01..2025-12) | up | 3.72e+03 | 0.49 | 0.637 | 46/18 of 79 | 0/0 | Oct/Mar |  |
| flood_s1_obs_pct | Radar flood map: coverage in month | monthly | mean | 79 | 96 (2018-01..2025-12) | down | -1.59 | 0.0535 | 0.202 | 2/67 of 79 | 0/0 | Sep/Jun |  |
| flood_population_exposed_pct | Share of people living in flooded areas | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.0432 | 0.756 | 0.834 | 46/21 of 79 | 0/0 | Sep/Mar |  |
| sudd_inundation_km2 | Sudd flooded area incl. swamp | monthly | mean | 16 | 91 (2018-01..2025-12) | up | 112 | 0.00314 * | 0.0432 | 14/2 of 16 | 12/0 | Sep/Apr | up: Rubkona(2780.0%),Mayendit(240.0%) |
| sudd_inundation_pct | Sudd flooded area incl. swamp (% of county) | monthly | mean | 16 | 91 (2018-01..2025-12) | up | 2.1 | 0.0019 * | 0.04 | 14/2 of 16 | 12/0 | Sep/Apr | up: Rubkona(7.618),Guit(3.329) |
| sudd_openwater_km2 | Sudd open water (no vegetation) | monthly | mean | 16 | 91 (2018-01..2025-12) | up | 8.81 | 0.00222 * | 0.04 | 14/2 of 16 | 11/0 | Dec/Sep | up: Rubkona(108.1),Guit(32.45) |
| sudd_clear_pct | Sudd water map: directly observed share | monthly | mean | 16 | 91 (2018-01..2025-12) | down | -0.136 | 0.151 | 0.287 | 7/9 of 16 | 0/0 | Jan/Jul |  |
| sudd_climfill_pct | Sudd water map: share estimated from typical years | monthly | mean | 16 | 91 (2018-01..2025-12) | up | 0.00695 | 0.482 | 0.63 | 8/8 of 16 | 0/0 | Oct/Apr |  |
| surface_water_pct | Surface water (% of county) | monthly | mean | 79 | 92 (2018-01..2025-12) | up | 0.265 | 0.0021 * | 0.04 | 66/11 of 79 | 11/0 | Aug/Mar | up: Rubkona(5.433),Guit(1.481) |
| surface_water_km2 | Surface water area | monthly | mean | 79 | 92 (2018-01..2025-12) | up | 14.7 | 0.00249 * | 0.0416 | 66/11 of 79 | 11/0 | Aug/Mar | up: Rubkona(1920.0%),Guit(963.0%) |
| surface_water_obs_pct | Surface-water map: cloud-free coverage | monthly | mean | 79 | 92 (2018-01..2025-12) | flat | 0 | 0.312 | 0.453 | 53/23 of 79 | 0/0 | Jan/Jul |  |
| sudd_floodedveg_pct | Flooded vegetation, Sudd (% of county) | monthly | mean | 16 | 91 (2018-01..2025-12) | up | 1.76 | 0.0083 * | 0.0799 | 14/2 of 16 | 10/0 | Sep/Apr | up: Fangak(2.98),Ayod(2.866) |
| sudd_floodedveg_km2 | Flooded vegetation, Sudd (km²) | monthly | mean | 16 | 91 (2018-01..2025-12) | up | 98.8 | 0.00636 * | 0.0709 | 14/2 of 16 | 10/0 | Sep/Apr | up: Mayendit(241.0%),Guit(171.0%) |
| tc_pet | Evaporation demand (TerraClimate) | monthly | mean | 79 | 96 (2018-01..2025-12) | down | -0.98 | 0.169 | 0.31 | 73/5 of 79 | 0/0 | Mar/Aug |  |
| pet_mm | Evaporation demand (simple estimate) | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.618 | 0.0514 | 0.2 | 79/0 of 79 | 0/0 | Mar/Aug |  |
| tc_q | Runoff (TerraClimate) | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.0357 | 0.109 | 0.246 | 6/73 of 79 | 0/0 | Aug/Feb |  |
| tc_def | Water shortfall for plants (climatic water deficit) | monthly | mean | 79 | 96 (2018-01..2025-12) | down | -1.3 | 0.12 | 0.265 | 75/3 of 79 | 0/0 | Mar/Aug |  |
| tc_aet | Water used by plants and soil (TerraClimate) | monthly | mean | 79 | 96 (2018-01..2025-12) | down | -0.292 | 0.0172 * | 0.117 | 8/71 of 79 | 0/0 | Aug/Feb |  |
| g3p_gwsa_cm | Groundwater | monthly | mean | 79 | 62 (2018-06..2023-09) | up | 3.69 | 0.0175 * | 0.117 | 79/0 of 79 | 54/0 | Feb/Jun | up: Pochalla(4.72),Akobo(4.58) |
| gldas_gws_anom_cm | Groundwater | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 2.04 | 0.0085 * | 0.0799 | 79/0 of 79 | 60/0 | Nov/May | up: Longochuk(3.519),Duk(3.297) |
| gracedm_gws_pctl | Groundwater | monthly | mean | 79 | 95 (2018-01..2025-12) | up | 4.05 | 0.01 * | 0.0842 | 74/5 of 79 | 45/0 | Apr/Oct | up: Renk(12.47),Manyo(9.562) |
| g3p_gwsa_unc_cm | Groundwater estimate: uncertainty | monthly | mean | 79 | 62 (2018-06..2023-09) | down | -0.0336 | 0.404 | 0.559 | 12/62 of 79 | 0/0 | Feb/Nov |  |
| grace_tws_cm | Total water stored in the land (satellite gravity) | monthly | mean | 79 | 89 (2018-06..2025-12) | up | 3.54 | 0.00287 * | 0.042 | 79/0 of 79 | 76/0 | Oct/Apr | up: Longochuk(4.285),Maiwut(4.263) |
| grace_tws_unc_cm | Water storage estimate: uncertainty | monthly | national | 79 | 89 (2018-06..2025-12) | down | -0.0559 | 0.0501 | 0.199 | 0/0 of 0 | 0/0 | Apr/Aug |  |
| power_ws10m_max | Strongest wind of the month | monthly | mean | 79 | 96 (2018-01..2025-12) | down | -0.0156 | 0.587 | 0.719 | 52/26 of 79 | 0/0 | Feb/Sep |  |
| tc_ws | Wind speed (TerraClimate) | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.00885 | 0.358 | 0.505 | 66/9 of 79 | 0/0 | May/Sep |  |
| power_ws10m | Wind speed at 10 m | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.00339 | 0.3 | 0.449 | 64/15 of 79 | 0/0 | Feb/Sep |  |
| power_ws2m | Wind speed near the ground (2 m) | monthly | mean | 79 | 96 (2018-01..2025-12) | up | 0.00176 | 0.204 | 0.352 | 65/14 of 79 | 0/0 | Feb/Sep |  |
| hrp_coverage_year | Aid appeal funded (share, national) | monthly | national | 79 | 96 (2018-01..2025-12) | up | 0.003 | 0.327 | 0.467 | 0/0 of 0 | 0/0 | – |  |
| hrp_funding_year_usd | Aid appeal: money received (national) | monthly | national | 79 | 96 (2018-01..2025-12) | up | 4.33e+06 | 0.813 | 0.884 | 0/0 of 0 | 0/0 | – |  |
| hrp_requirement_year_usd | Aid appeal: money requested (national) | monthly | national | 79 | 96 (2018-01..2025-12) | down | -3.29e+06 | 0.628 | 0.75 | 0/0 of 0 | 0/0 | – |  |
| fts_hum_funding_month_usd | Humanitarian funding received, monthly (national) | monthly | national | 79 | 96 (2018-01..2025-12) | down | -1e+07 | 0.0441 * | 0.191 | 0/0 of 0 | 0/0 | May/Oct |  |
| fts_hum_funding_year_usd | Humanitarian funding received, yearly (national) | monthly | national | 79 | 96 (2018-01..2025-12) | down | -3.67e+06 | 0.0489 * | 0.199 | 0/0 of 0 | 0/0 | – |  |
| state_dept_disbursed_month_usd | US State Department aid paid out (national) | monthly | national | 79 | 96 (2018-01..2025-12) | up | 2.69e+05 | 0.105 | 0.246 | 0/0 of 0 | 0/0 | Aug/Apr |  |
| us_aid_obligated_month_usd | US foreign aid committed (national) | monthly | national | 79 | 96 (2018-01..2025-12) | down | -8.93e+05 | 0.0895 | 0.235 | 0/0 of 0 | 0/0 | Sep/Oct |  |
| us_aid_disbursed_month_usd | US foreign aid paid out (national) | monthly | national | 79 | 96 (2018-01..2025-12) | up | 9.99e+05 | 0.515 | 0.658 | 0/0 of 0 | 0/0 | Nov/Dec |  |
| fts_us_gov_funding_month_usd | US government humanitarian funding, monthly (national) | monthly | national | 79 | 96 (2018-01..2025-12) | down | -4.62e+06 | 0.0763 | 0.228 | 0/0 of 0 | 0/0 | Jul/Oct |  |
| fts_us_gov_funding_year_usd | US government humanitarian funding, yearly (national) | monthly | national | 79 | 96 (2018-01..2025-12) | up | 3.85e+07 | 0.628 | 0.75 | 0/0 of 0 | 0/0 | – |  |
| fts_us_share_year | US share of humanitarian funding (national) | monthly | national | 79 | 96 (2018-01..2025-12) | up | 0.023 | 0.464 | 0.617 | 0/0 of 0 | 0/0 | – |  |
| usaid_obligated_month_usd | USAID aid committed (national) | monthly | national | 79 | 96 (2018-01..2025-12) | down | -3.97e+05 | 0.156 | 0.292 | 0/0 of 0 | 0/0 | Nov/Oct |  |
| usaid_disbursed_month_usd | USAID aid paid out (national) | monthly | national | 79 | 96 (2018-01..2025-12) | up | 5.36e+05 | 0.393 | 0.548 | 0/0 of 0 | 0/0 | Nov/Dec |  |
| acled_civ_events | Attacks on civilians (events) | monthly | sum | 79 | 96 (2018-01..2025-12) | up | 8.38 | 0.0687 | 0.227 | 57/16 of 79 | 0/0 | Mar/Sep |  |
| ucdp_civilian_deaths | Civilians killed (UCDP) | monthly | sum | 79 | 96 (2018-01..2025-12) | down | -4.73 | 0.0837 | 0.233 | 15/26 of 79 | 0/0 | May/Mar |  |
| ucdp_one_sided_deaths | Civilians killed by armed groups or forces (UCDP) | monthly | sum | 79 | 96 (2018-01..2025-12) | - | – | 1 | 1 | 0/0 of 79 | 0/0 | – |  |
| acled_civ_fatalities | Civilians killed in attacks | monthly | sum | 79 | 96 (2018-01..2025-12) | up | 10 | 0.133 | 0.271 | 56/16 of 79 | 0/0 | Jan/Sep |  |
| ucdp_deaths_best | Conflict deaths (UCDP) | monthly | sum | 79 | 96 (2018-01..2025-12) | down | -10.4 | 0.107 | 0.246 | 18/38 of 79 | 0/0 | May/Nov |  |
| ucdp_one_sided_events | Deadly attacks on civilians (UCDP events) | monthly | sum | 79 | 96 (2018-01..2025-12) | - | – | 1 | 1 | 0/0 of 79 | 0/0 | – |  |
| ucdp_events | Deadly conflict events (UCDP) | monthly | sum | 79 | 96 (2018-01..2025-12) | down | -2 | 0.05 | 0.199 | 17/43 of 79 | 0/0 | Apr/Nov |  |
| acled_pv_fatalities | Deaths from political violence | monthly | sum | 79 | 96 (2018-01..2025-12) | up | 22.8 | 0.0955 | 0.24 | 59/18 of 79 | 0/0 | Jan/Sep |  |
| ucdp_non_state_deaths | Deaths in fighting between armed groups (UCDP) | monthly | sum | 79 | 96 (2018-01..2025-12) | - | – | 1 | 1 | 0/0 of 79 | 0/0 | – |  |
| ucdp_state_based_deaths | Deaths in government-involved fighting (UCDP) | monthly | sum | 79 | 96 (2018-01..2025-12) | - | – | 1 | 1 | 0/0 of 79 | 0/0 | – |  |
| intracounty_communal_deaths | Deaths in inter-communal violence | monthly | sum | 79 | 96 (2018-01..2025-12) | down | -1 | 0.153 | 0.289 | 12/16 of 79 | 0/0 | Feb/Aug |  |
| intracounty_conflict_deaths | Deaths in local conflict (communities and militias) | monthly | sum | 79 | 96 (2018-01..2025-12) | down | -1.37 | 0.146 | 0.285 | 15/25 of 79 | 0/0 | Feb/Aug |  |
| ucdp_non_state_events | Fighting between armed groups (UCDP events) | monthly | sum | 79 | 96 (2018-01..2025-12) | - | – | 1 | 1 | 0/0 of 79 | 0/0 | – |  |
| ucdp_state_based_events | Government-involved fighting (UCDP events) | monthly | sum | 79 | 96 (2018-01..2025-12) | - | – | 1 | 1 | 0/0 of 79 | 0/0 | – |  |
| intracounty_communal_events | Inter-communal violence (events) | monthly | sum | 79 | 96 (2018-01..2025-12) | down | -0.2 | 0.0826 | 0.233 | 9/20 of 79 | 0/0 | Mar/Aug |  |
| intracounty_conflict_events | Local conflict events (communities and militias) | monthly | sum | 79 | 96 (2018-01..2025-12) | down | -0.367 | 0.0325 * | 0.165 | 11/30 of 79 | 0/0 | Jan/Aug |  |
| acled_pv_events | Political violence (events) | monthly | sum | 79 | 96 (2018-01..2025-12) | up | 10.1 | 0.0679 | 0.227 | 62/15 of 79 | 0/0 | May/Sep |  |
| acled_demonstrations | Protests and riots | monthly | sum | 79 | 96 (2018-01..2025-12) | up | 0.667 | 0.0799 | 0.233 | 36/7 of 79 | 0/0 | Jan/Apr |  |
| acled_st_abduction_events | Abductions and disappearances (state) | monthly | sum | 78 | 96 (2018-01..2025-12) | up | 3.83 | 0.0203 * | 0.125 | 70/8 of 78 | 0/0 | Aug/Mar |  |
| acled_st_air_drone_strikes | Air and drone strikes (state) | monthly | sum | 78 | 96 (2018-01..2025-12) | up | 12.9 | 0.0847 | 0.233 | 73/0 of 78 | 0/0 | May/Jan |  |
| acled_st_armed_clash_events | Armed clashes (state) | monthly | sum | 78 | 96 (2018-01..2025-12) | up | 28.4 | 0.0591 | 0.217 | 69/9 of 78 | 0/0 | Apr/Aug |  |
| acled_st_civilian_attack_events | Attacks on civilians (state) | monthly | sum | 78 | 96 (2018-01..2025-12) | up | 64.9 | 0.0493 * | 0.199 | 78/0 of 78 | 0/0 | Mar/Sep |  |
| acled_st_civilian_attack_fatalities | Civilians killed in attacks (state) | monthly | sum | 78 | 96 (2018-01..2025-12) | up | 78.2 | 0.0927 | 0.24 | 69/9 of 78 | 0/0 | Jan/Sep |  |
| acled_st_armed_clash_fatalities | Deaths in armed clashes (state) | monthly | sum | 78 | 96 (2018-01..2025-12) | up | 79.1 | 0.11 | 0.246 | 70/3 of 78 | 0/0 | May/Oct |  |
| acled_st_sexual_violence_fatalities | Deaths in sexual violence incidents (state) | monthly | sum | 78 | 96 (2018-01..2025-12) | down | -4.76 | 0.108 | 0.246 | 17/48 of 78 | 0/0 | Apr/Jan |  |
| acled_st_looting_events | Looting and property destruction (state) | monthly | sum | 78 | 96 (2018-01..2025-12) | up | 17.2 | 0.0478 * | 0.199 | 78/0 of 78 | 0/0 | Jan/Aug |  |
| acled_st_pv_population_exposure | People exposed to political violence (state) | monthly | sum | 78 | 96 (2018-01..2025-12) | down | -1.25e+05 | 0.146 | 0.285 | 52/26 of 78 | 0/0 | Jan/Jun |  |
| acled_st_protest_events | Protests (state) | monthly | sum | 78 | 96 (2018-01..2025-12) | up | 4 | 0.0698 | 0.227 | 72/6 of 78 | 0/0 | Feb/Mar |  |
| acled_st_riot_events | Riots and mob violence (state) | monthly | sum | 78 | 96 (2018-01..2025-12) | up | 3.4 | 0.75 | 0.834 | 55/23 of 78 | 0/0 | May/Nov |  |
| acled_st_sexual_violence_events | Sexual violence in conflict (state) | monthly | sum | 78 | 96 (2018-01..2025-12) | down | -1 | 0.0943 | 0.24 | 25/53 of 78 | 0/0 | Nov/Jul |  |
| acled_st_remote_violence_events | Strikes, shelling and explosives (state) | monthly | sum | 78 | 96 (2018-01..2025-12) | up | 0.5 | 0.256 | 0.403 | 72/6 of 78 | 0/0 | May/Feb |  |
| acled_st_territory_change_events | Territory changing hands (state) | monthly | sum | 78 | 96 (2018-01..2025-12) | down | -3 | 0.859 | 0.918 | 40/9 of 78 | 0/0 | Dec/Jul |  |
| dtm_idps | Displaced people living in county (IOM) | irregular (per round) | mean | 78 | 81 (2018-06..2025-10) | up | 1.13e+03 | 0.0354 * | 0.169 | 41/37 of 78 | 16/10 | – | up: Pochalla(1398.0),Leer(767.0%) ; down: Raja(-25.2%),Mundri West(-17.4%) |
| unhcr_refugees | Refugees hosted (UNHCR) | annual | mean | 18 | 96 (2018-01..2025-12) | up | 1.02e+03 | 0.0354 * | 0.169 | 6/4 of 11 | 3/3 | – | up: Juba(49.1%),Yambio(29.5%) ; down: Maridi(-4.89%),Tambura(-4.04%) |
| dtm_returnees | Returnees living in county (IOM) | irregular (per round) | mean | 78 | 81 (2018-06..2025-10) | up | 3.46e+03 | 0.000837 * | 0.0373 | 59/19 of 78 | 44/3 | – | up: Twic(16290.0),Raja(9460.0%) ; down: Kapoeta East(-14.7%),Guit(-12.6%) |
| et_ind_arrived_from_ethiopia | Arrivals from Ethiopia | monthly | sum | 79 | 73 (2019-12..2025-12) | - | – | 0.602 | 0.734 | 4/1 of 79 | 0/0 | Aug/Jan |  |
| et_ind_arrived_from_sudan | Arrivals from Sudan | monthly | sum | 79 | 73 (2019-12..2025-12) | up | 252 | 0.143 | 0.285 | 48/2 of 79 | 0/0 | Jul/Nov |  |
| et_ind_drought_fire_other_disaster | Displaced by drought, fire or other disasters | monthly | sum | 79 | 73 (2019-12..2025-12) | - | – | 0.429 | 0.587 | 4/3 of 79 | 0/0 | Jan/Jun |  |
| et_ind_flooding | Displaced by flooding | monthly | sum | 79 | 73 (2019-12..2025-12) | up | 557 | 0.163 | 0.303 | 20/30 of 79 | 0/0 | Aug/Apr |  |
| et_ind_local_communal_conflict | Displaced by local / communal conflict | monthly | sum | 79 | 73 (2019-12..2025-12) | up | 4.83e+03 | 0.0724 | 0.228 | 18/42 of 79 | 0/0 | Feb/Oct |  |
| et_ind_national_conflict | Displaced by national-level conflict | monthly | sum | 79 | 73 (2019-12..2025-12) | up | 3.32e+03 | 0.081 | 0.233 | 34/6 of 79 | 0/0 | Apr/Jan |  |
| et_events | Displacement events recorded (IOM) | monthly | sum | 79 | 73 (2019-12..2025-12) | up | 5.42 | 0.0965 | 0.24 | 55/22 of 79 | 0/0 | Aug/Dec |  |
| et_events_food_need_assessed | Displacement events with food needs assessed (IOM) | monthly | sum | 79 | 73 (2019-12..2025-12) | up | 5.42 | 0.0983 | 0.24 | 55/22 of 79 | 0/0 | Aug/Dec |  |
| et_events_food_need_severe | Displacement events with severe food needs (IOM) | monthly | sum | 79 | 73 (2019-12..2025-12) | up | 2.98 | 0.127 | 0.266 | 61/13 of 79 | 0/0 | Aug/Dec |  |
| et_ind_sudan_conflict | Fled the war in Sudan | monthly | sum | 79 | 73 (2019-12..2025-12) | up | 1.47e+03 | 0.127 | 0.266 | 52/0 of 79 | 0/0 | Jan/Nov |  |
| et_ind_hardship_food_living | Moved because of hunger or hardship | monthly | sum | 79 | 73 (2019-12..2025-12) | up | 93.7 | 0.512 | 0.658 | 18/12 of 79 | 0/0 | Jan/Sep |  |
| et_ind_other | Moved for other reasons | monthly | sum | 79 | 73 (2019-12..2025-12) | - | – | 0.0975 | 0.24 | 4/10 of 79 | 0/0 | Aug/Dec |  |
| et_ind_idps | Newly displaced people (IOM) | monthly | sum | 79 | 73 (2019-12..2025-12) | up | 5.39e+03 | 0.725 | 0.824 | 42/34 of 79 | 0/0 | Aug/Mar |  |
| et_ind_total | People displaced or returning (IOM, all causes) | monthly | sum | 79 | 73 (2019-12..2025-12) | up | 7.05e+03 | 0.436 | 0.593 | 54/24 of 79 | 0/0 | Aug/Mar |  |
| et_ind_return_relocation | Returned or relocated | monthly | sum | 79 | 73 (2019-12..2025-12) | up | 2.43e+03 | 0.62 | 0.748 | 15/19 of 79 | 0/0 | Aug/Sep |  |
| et_ind_returnees | Returnees (people coming back) | monthly | sum | 79 | 73 (2019-12..2025-12) | up | 1.81e+03 | 0.196 | 0.348 | 47/9 of 79 | 0/0 | Jan/Mar |  |
| fmr_arrived_from_other_county_total | Forced arrivals from other counties (IOM) | monthly | sum | 79 | 54 (2020-01..2025-08) | up | 233 | 0.0332 * | 0.165 | 70/3 of 79 | 0/0 | Aug/Dec |  |
| fmr_arrived_from_other_county_conflict | Forced arrivals from other counties: conflict (IOM) | monthly | sum | 79 | 54 (2020-01..2025-08) | up | 77.7 | 0.0613 | 0.217 | 70/1 of 79 | 0/0 | Aug/Dec |  |
| fmr_arrived_from_other_county_disaster | Forced arrivals from other counties: disaster (IOM) | monthly | sum | 79 | 54 (2020-01..2025-08) | up | 25.3 | 0.679 | 0.798 | 12/15 of 79 | 0/0 | Oct/Jul |  |
| fmr_arrived_from_other_county_food | Forced arrivals from other counties: food (IOM) | monthly | sum | 79 | 54 (2020-01..2025-08) | up | 55 | 0.213 | 0.354 | 20/12 of 79 | 0/0 | Aug/Mar |  |
| fmr_departed_to_other_county_total | Forced departures to other counties (IOM) | monthly | sum | 79 | 54 (2020-01..2025-08) | up | 233 | 0.0332 * | 0.165 | 38/29 of 79 | 0/0 | Aug/Dec |  |
| fmr_departed_to_other_county_conflict | Forced departures to other counties: conflict (IOM) | monthly | sum | 79 | 54 (2020-01..2025-08) | up | 77.7 | 0.0613 | 0.217 | 46/15 of 79 | 0/0 | Aug/Dec |  |
| fmr_departed_to_other_county_disaster | Forced departures to other counties: disaster (IOM) | monthly | sum | 79 | 54 (2020-01..2025-08) | up | 25.3 | 0.679 | 0.798 | 15/34 of 79 | 0/0 | Oct/Jul |  |
| fmr_departed_to_other_county_food | Forced departures to other counties: food (IOM) | monthly | sum | 79 | 54 (2020-01..2025-08) | up | 55 | 0.213 | 0.354 | 24/17 of 79 | 0/0 | Aug/Mar |  |
| fmr_within_county_total | Forced moves within county (IOM) | monthly | sum | 79 | 54 (2020-01..2025-08) | up | 66.2 | 0.243 | 0.389 | 36/6 of 79 | 0/0 | Sep/Mar |  |
| fmr_within_county_conflict | Forced moves within county: conflict (IOM) | monthly | sum | 79 | 54 (2020-01..2025-08) | up | 22.8 | 0.106 | 0.246 | 33/5 of 79 | 0/0 | Jan/May |  |
| fmr_within_county_disaster | Forced moves within county: disaster (IOM) | monthly | sum | 79 | 54 (2020-01..2025-08) | up | 12.5 | 0.831 | 0.9 | 11/6 of 79 | 0/0 | Sep/Mar |  |
| fmr_within_county_food | Forced moves within county: food (IOM) | monthly | sum | 79 | 54 (2020-01..2025-08) | down | -1.6 | 0.71 | 0.822 | 14/5 of 79 | 0/0 | Sep/Feb |  |
| fmr_internal_forced_total | Forced travellers counted (national) | monthly | national | 79 | 54 (2020-01..2025-08) | up | 516 | 0.0392 * | 0.179 | 0/0 of 0 | 0/0 | Sep/Dec |  |
| fmr_internal_forced_conflict | Forced travellers counted: conflict (national) | monthly | national | 79 | 54 (2020-01..2025-08) | up | 138 | 0.0758 | 0.228 | 0/0 of 0 | 0/0 | Aug/Nov |  |
| fmr_internal_forced_disaster | Forced travellers counted: disaster (national) | monthly | national | 79 | 54 (2020-01..2025-08) | up | 78 | 0.834 | 0.9 | 0/0 of 0 | 0/0 | Sep/Jul |  |
| fmr_internal_forced_food | Forced travellers counted: food (national) | monthly | national | 79 | 54 (2020-01..2025-08) | up | 79 | 0.323 | 0.464 | 0/0 of 0 | 0/0 | Sep/Mar |  |
| fmr_active_monitoring_points | IOM flow-monitoring points active (national) | monthly | national | 79 | 54 (2020-01..2025-08) | up | 0.1 | 0.554 | 0.69 | 0/0 of 0 | 0/0 | Sep/Dec |  |
| fmr_monitoring_points_in_county | IOM flow-monitoring points in county | monthly | mean | 79 | 54 (2020-01..2025-08) | up | 0.00127 | 0.554 | 0.69 | 11/9 of 79 | 0/0 | Sep/Dec |  |
| fmr_conflict_share_all_movements | Share of travellers fleeing conflict (national) | monthly | national | 79 | 27 (2022-11..2025-08) | up | 0.0948 | 0.695 | 0.809 | 0/0 of 0 | 0/0 | Oct/Jan |  |
| fmr_all_movements_observed | Travellers counted at IOM points (national) | monthly | national | 79 | 27 (2022-11..2025-08) | down | -1.54e+04 | 0.341 | 0.483 | 0/0 of 0 | 0/0 | Apr/Jul |  |
| edu_girls_share | Girls' share of pupils (2015) | static | mean | 78 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| edu_enrolment | Pupils enrolled in school (2015) | static | mean | 78 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| schools_count | Schools (2015) | static | mean | 79 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| schools_per100k | Schools per 100,000 people | static | mean | 79 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| ethnic_excluded_share | Area settled by politically excluded groups | static | mean | 73 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| ethnic_dominant_share | Area share of the largest ethnic group | static | mean | 73 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| ethnic_groups_count | Number of ethnic groups present | static | mean | 79 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| gam_prevalence_pct | Child acute malnutrition rate (2025) | irregular (per IPC analysis) | mean | 78 | 6 (2025-07..2025-12) | - | – | – | – | 0/0 of 0 | 0/0 | – |  |
| ipc_amn_phase | Child malnutrition severity phase (2025) | irregular (per IPC analysis) | mean | 79 | 6 (2025-07..2025-12) | - | – | – | – | 0/0 of 0 | 0/0 | – |  |
| ipc_phase_class | Food insecurity phase (IPC, 1-5) | irregular (per IPC analysis) | mean | 79 | 72 (2018-01..2025-12) | down | -0.0123 | 0.23 | 0.376 | 24/42 of 78 | 0/0 | – |  |
| ipc_phase3plus_pop | People facing crisis-level hunger or worse | irregular (per IPC analysis) | mean | 79 | 72 (2018-01..2025-12) | up | 484 | 0.764 | 0.839 | 39/39 of 78 | 0/0 | – |  |
| ipc_phase4plus_pop | People facing emergency-level hunger or worse | irregular (per IPC analysis) | mean | 79 | 72 (2018-01..2025-12) | up | 577 | 0.548 | 0.689 | 52/26 of 78 | 2/1 | – | up: Fangak(21.0%),Lainya(2.67%) ; down: Koch(-8.26%) |
| ipc_phase3plus_pct | Share of people facing crisis-level hunger | irregular (per IPC analysis) | mean | 79 | 72 (2018-01..2025-12) | down | -0.712 | 0.548 | 0.689 | 16/61 of 78 | 0/0 | – |  |
| isna_unsafe_water_collect_pct | Households feeling unsafe fetching water | annual | mean | 79 | 36 (2022-01..2024-12) | - | – | – | – | 0/0 of 0 | 0/0 | – |  |
| isna_wg_avoid_latrines_pct | Women and girls avoiding latrines (unsafe) | annual | mean | 79 | 36 (2022-01..2024-12) | - | – | – | – | 0/0 of 0 | 0/0 | – |  |
| isna_wg_avoid_any_pct | Women and girls avoiding unsafe places | annual | mean | 79 | 36 (2022-01..2024-12) | - | – | – | – | 0/0 of 0 | 0/0 | – |  |
| isna_wg_avoid_water_points_pct | Women and girls avoiding water points (unsafe) | annual | mean | 79 | 36 (2022-01..2024-12) | - | – | – | – | 0/0 of 0 | 0/0 | – |  |
| health_facilities | Health facilities | static | mean | 79 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| health_facilities_per100k | Health facilities per 100,000 people | static | mean | 79 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| hospitals | Hospitals | static | mean | 79 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| hospitals_per100k | Hospitals per 100,000 people | static | mean | 79 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| logcluster_hubs_in_county | Aid logistics hubs and warehouses | monthly | mean | 79 | 73 (2019-12..2025-12) | up | 0.0171 | 0.0126 * | 0.0984 | 10/5 of 79 | 0/0 | Sep/Jan |  |
| hno_pin | People in need of aid (UN estimate) | annual | mean | 79 | 72 (2019-01..2025-12) | up | 3.76e+03 | 0.0603 | 0.217 | 51/27 of 78 | 0/0 | – |  |
| hno_severity | Severity of humanitarian needs (1-5) | annual | mean | 79 | 36 (2022-01..2024-12) | - | – | – | – | 0/0 of 0 | 0/0 | – |  |
| ops_orgs | Aid organisations working in county | monthly | mean | 79 | 83 (2019-01..2025-12) | down | -0.0734 | 0.0399 * | 0.179 | 19/59 of 79 | 0/0 | Jun/Jan |  |
| nutrition_partners | Nutrition aid partners in county | monthly | mean | 79 | 83 (2019-01..2025-12) | down | -0.122 | 0.0382 * | 0.179 | 20/58 of 79 | 0/0 | Jul/Jan |  |
| protection_partners | Protection and GBV aid partners in county | monthly | mean | 79 | 83 (2019-01..2025-12) | down | -0.0696 | 0.0885 | 0.235 | 61/18 of 79 | 0/0 | Mar/Oct |  |
| ops_orgs_national_ngo | South Sudanese NGOs working in county | monthly | mean | 79 | 83 (2019-01..2025-12) | up | 0.0253 | 0.858 | 0.918 | 37/41 of 79 | 0/0 | Jun/Jan |  |
| ii_aid_worker_incidents | Aid workers killed, hurt, kidnapped or arrested (national) | monthly | national | 79 | 96 (2018-01..2025-12) | up | 0.714 | 0.108 | 0.246 | 0/0 of 0 | 0/0 | Sep/Dec |  |
| ii_education_attacks | Attacks on education (national) | monthly | national | 79 | 96 (2018-01..2025-12) | up | 0.25 | 0.301 | 0.449 | 0/0 of 0 | 0/0 | Jun/Apr |  |
| ii_health_attacks | Attacks on health care (national) | monthly | national | 79 | 96 (2018-01..2025-12) | up | 0.25 | 0.221 | 0.363 | 0/0 of 0 | 0/0 | Feb/Nov |  |
| ii_sexual_violence_incidents | Conflict-related sexual violence (national) | monthly | national | 79 | 72 (2020-01..2025-12) | down | -0.5 | 0.0842 | 0.233 | 0/0 of 0 | 0/0 | Feb/Aug |  |
| cattle_head | Cattle (2015 estimate) | static | mean | 79 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| cattle_density | Cattle per square km (2015 estimate) | static | mean | 79 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| goats_head | Goats (2015 estimate) | static | mean | 79 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| sheep_head | Sheep (2015 estimate) | static | mean | 79 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| oil_wells_osm | Mapped oil wells | static | mean | 79 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| oil_fields_count | Oil fields | static | mean | 79 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| oil_pipeline_km | Oil pipelines (km) | static | mean | 79 | 96 (2018-01..2025-12) | - | – | static | – | 0/0 of 0 | 0/0 | – |  |
| unmiss_presence | UN peacekeepers present (yes/no) | annual | mean | 79 | 96 (2018-01..2025-12) | flat | 0 | 0.194 | 0.346 | 3/2 of 79 | 0/0 | – |  |
| unmiss_deployment_sites_in_county | UN peacekeeping sites in county | monthly | mean | 79 | 25 (2023-12..2025-12) | down | -0.00316 | 0.54 | 0.687 | 0/1 of 79 | 0/0 | Jan/Dec |  |
| unmiss_troops | UN peacekeeping troops (estimate) | annual | mean | 79 | 96 (2018-01..2025-12) | down | -1.36 | 0.902 | 0.95 | 5/8 of 79 | 0/0 | – |  |
| unmiss_budget_fy_usd | UNMISS budget (national) | monthly | national | 79 | 96 (2018-01..2025-12) | up | 9.5e+06 | 0.31 | 0.453 | 0/0 of 0 | 0/0 | Jul/Jan |  |
| unmiss_expenditure_fy_usd | UNMISS spending (national) | monthly | national | 79 | 90 (2018-01..2025-06) | up | 8.17e+06 | 0.263 | 0.408 | 0/0 of 0 | 0/0 | Jul/Jan |  |
| unmiss_uniformed_personnel | UNMISS troops and police (national) | monthly | national | 79 | 96 (2018-01..2025-12) | down | -11 | 0.127 | 0.266 | 0/0 of 0 | 0/0 | Jul/Dec |  |
| pop_total | Population (WorldPop estimate) | annual | mean | 79 | 96 (2018-01..2025-12) | up | 3.76e+03 | 0.000837 * | 0.0373 | 79/0 of 79 | 79/0 | – | up: Abyei(4.46%),Tambura(3.02%) |
| population_estimate | Population (official OCHA estimate) | annual | mean | 79 | 24 (2022-01..2025-12) | - | – | – | – | 0/0 of 0 | 0/0 | – |  |
| price_beans_ssp | Beans price (South Sudanese pounds) | monthly | median | 32 | 91 (2018-01..2025-12) | up | 204 | 0.000766 * | 0.0373 | 29/0 of 29 | 26/0 | Nov/Jan | up: Budi(6115.0),Aweil South(3591.0) |
| price_beans_usd | Beans price (US$) | monthly | median | 32 | 91 (2018-01..2025-12) | up | 0.0186 | 0.867 | 0.922 | 15/13 of 29 | 0/0 | May/Dec |  |
| fx_ssp_per_usd | Black-market exchange rate (pounds per US$) | monthly | median | 32 | 82 (2018-01..2025-12) | up | 161 | 0.0186 * | 0.12 | 28/1 of 29 | 18/0 | Sep/Jan | up: Aweil South(1000.0),Twic(276.0%) |
| price_cooking_oil_ssp | Cooking oil price (South Sudanese pounds) | monthly | median | 32 | 92 (2018-01..2025-12) | up | 309 | 0.000542 * | 0.0373 | 29/0 of 29 | 21/0 | Nov/Jan | up: Aweil South(4541.0),Pibor(198.0%) |
| price_cooking_oil_usd | Cooking oil price (US$) | monthly | median | 32 | 92 (2018-01..2025-12) | up | 0.111 | 1 | 1 | 13/16 of 29 | 0/0 | May/Dec |  |
| wage_casual_labour_ssp | Daily wage for casual labour (South Sudanese pounds) | monthly | median | 32 | 88 (2018-03..2025-12) | up | 452 | 0.000755 * | 0.0373 | 28/1 of 29 | 21/0 | Nov/Mar | up: Twic(4905.0),Abyei(560.0%) |
| wage_casual_labour_usd | Daily wage for casual labour (US$) | monthly | median | 32 | 88 (2018-03..2025-12) | up | 0.156 | 0.0975 | 0.24 | 3/26 of 29 | 0/0 | Oct/Dec |  |
| price_diesel_parallel_ssp | Diesel (black-market) price (South Sudanese pounds) | monthly | median | 29 | 88 (2018-03..2025-12) | up | 189 | 0.00197 * | 0.04 | 29/0 of 29 | 20/0 | Dec/Mar | up: Bor South(749.1),Twic(730.0) |
| price_diesel_parallel_usd | Diesel (black-market) price (US$) | monthly | median | 29 | 88 (2018-03..2025-12) | up | 0.00768 | 0.786 | 0.859 | 18/10 of 29 | 0/0 | Aug/Feb |  |
| price_diesel_ssp | Diesel price (South Sudanese pounds) | monthly | median | 28 | 89 (2018-01..2025-12) | up | 161 | 0.00108 * | 0.0373 | 27/0 of 27 | 21/0 | Dec/Jan | up: Pibor(6640.0),Aweil South(3086.0) |
| price_diesel_usd | Diesel price (US$) | monthly | median | 28 | 89 (2018-01..2025-12) | down | -0.036 | 0.734 | 0.824 | 16/11 of 27 | 0/0 | May/Jan |  |
| price_groundnuts_ssp | Groundnuts price (South Sudanese pounds) | monthly | median | 26 | 69 (2018-01..2024-03) | up | 169 | 0.00607 * | 0.0709 | 21/2 of 24 | 8/0 | Feb/Apr | up: Aweil East(176.0%),Gogrial West(156.0%) |
| price_groundnuts_usd | Groundnuts price (US$) | monthly | median | 26 | 69 (2018-01..2024-03) | up | 0.113 | 0.883 | 0.935 | 5/18 of 24 | 0/0 | May/Nov |  |
| price_sorghum_ssp | Imported white sorghum price (South Sudanese pounds) | monthly | median | 32 | 89 (2018-01..2025-12) | up | 102 | 0.00278 * | 0.042 | 27/2 of 29 | 22/0 | Aug/Jan | up: Aweil South(540.5),Aweil East(471.0%) |
| price_sorghum_usd | Imported white sorghum price (US$) | monthly | median | 32 | 89 (2018-01..2025-12) | up | 0.0194 | 0.3 | 0.449 | 13/14 of 29 | 0/0 | Jul/Dec |  |
| price_sorghum_local_ssp | Local sorghum price (South Sudanese pounds) | monthly | median | 31 | 39 (2018-04..2025-12) | up | 399 | 0.0627 | 0.218 | 23/2 of 25 | 8/0 | Dec/Mar | up: Fashoda(400.0%),Fangak(200.0%) |
| price_sorghum_local_usd | Local sorghum price (US$) | monthly | median | 31 | 39 (2018-04..2025-12) | up | 0.04 | 0.47 | 0.618 | 11/14 of 25 | 1/1 | Jan/Nov | up: Torit(16.4%) ; down: Akobo(-31.9%) |
| price_maize_ssp | Maize price (South Sudanese pounds) | monthly | median | 28 | 89 (2018-01..2025-12) | up | 87 | 0.00146 * | 0.0381 | 24/0 of 24 | 16/0 | Sep/Jan | up: Renk(1119.0),Aweil North(325.0%) |
| price_maize_usd | Maize price (US$) | monthly | median | 28 | 89 (2018-01..2025-12) | up | 0.0194 | 0.736 | 0.824 | 8/14 of 24 | 0/0 | Aug/Jan |  |
| price_petrol_parallel_ssp | Petrol (black-market) price (South Sudanese pounds) | monthly | median | 30 | 88 (2018-03..2025-12) | up | 193 | 0.00339 * | 0.0441 | 29/0 of 29 | 21/0 | Dec/Feb | up: Aweil South(3876.0),Twic(757.2) |
| price_petrol_parallel_usd | Petrol (black-market) price (US$) | monthly | median | 30 | 88 (2018-03..2025-12) | down | -0.0777 | 0.442 | 0.595 | 15/13 of 29 | 1/0 | Aug/Feb | up: Fashoda(51.3%) |
| price_petrol_ssp | Petrol price (South Sudanese pounds) | monthly | median | 28 | 89 (2018-01..2025-12) | up | 129 | 0.00111 * | 0.0373 | 26/0 of 26 | 18/0 | Dec/Jan | up: Aweil South(3103.0),Rubkona(888.9) |
| price_petrol_usd | Petrol price (US$) | monthly | median | 28 | 89 (2018-01..2025-12) | down | -0.059 | 0.944 | 0.986 | 13/13 of 26 | 2/0 | May/Feb | up: Renk(61.6%),Akobo(16.9%) |
| price_wheat_flour_ssp | Wheat flour price (South Sudanese pounds) | monthly | median | 32 | 89 (2018-01..2025-12) | up | 133 | 0.00139 * | 0.0381 | 28/1 of 29 | 22/1 | Dec/Mar | up: Aweil South(1614.0),Twic(1111.0) ; down: Maban(-4.46%) |
| price_wheat_flour_usd | Wheat flour price (US$) | monthly | median | 32 | 89 (2018-01..2025-12) | down | -0.000714 | 0.572 | 0.709 | 8/21 of 29 | 0/0 | May/Dec |  |
| u5mr_national | Child deaths under age 5 per 1,000 births (national) | annual | national | 79 | 84 (2018-01..2024-12) | flat | 0 | 0.211 | 0.354 | 0/0 of 0 | 0/0 | – |  |
| vacc_penta3_cov | Childhood vaccine coverage, 3 doses (2018) | annual | mean | 78 | 12 (2018-01..2018-12) | - | – | – | – | 0/0 of 0 | 0/0 | – |  |
| imr_national | Infant deaths per 1,000 births (national) | annual | national | 79 | 84 (2018-01..2024-12) | flat | 0 | 0.211 | 0.354 | 0/0 of 0 | 0/0 | – |  |
| vacc_mcv1_cov | Measles vaccination coverage (2018) | annual | mean | 78 | 12 (2018-01..2018-12) | - | – | – | – | 0/0 of 0 | 0/0 | – |  |
| isna_open_defecation_pct | Households with no toilet (open defecation) | annual | mean | 79 | 36 (2022-01..2024-12) | - | – | – | – | 0/0 of 0 | 0/0 | – |  |
| isna_water_30min_plus_pct | Households 30+ minutes from drinking water | annual | mean | 79 | 36 (2022-01..2024-12) | - | – | – | – | 0/0 of 0 | 0/0 | – |  |
| isna_surface_water_source_pct | Households drinking untreated surface water | annual | mean | 79 | 36 (2022-01..2024-12) | - | – | – | – | 0/0 of 0 | 0/0 | – |  |
| wps_ipv_pct | Women facing partner violence (national) | annual | national | 79 | 48 (2019-01..2025-12) | down | -1.77 | 0.149 | 0.285 | 0/0 of 0 | 0/0 | – |  |
| wps_community_safety_pct | Women feeling safe in their community (national) | annual | national | 79 | 48 (2019-01..2025-12) | up | 0.0833 | 0.47 | 0.618 | 0/0 of 0 | 0/0 | – |  |
| wps_employment_pct | Women in paid work (national) | annual | national | 79 | 48 (2019-01..2025-12) | down | -1.5 | 0.308 | 0.453 | 0/0 of 0 | 0/0 | – |  |
| wps_parliament_women_pct | Women in parliament (national) | annual | national | 79 | 48 (2019-01..2025-12) | up | 1.19 | 0.245 | 0.389 | 0/0 of 0 | 0/0 | – |  |
| wps_cellphone_pct | Women using a mobile phone (national) | annual | national | 79 | 48 (2019-01..2025-12) | up | 6.54 | 0.149 | 0.285 | 0/0 of 0 | 0/0 | – |  |
| wps_financial_inclusion_pct | Women with a bank or mobile-money account (national) | annual | national | 79 | 48 (2019-01..2025-12) | down | -0.106 | 0.245 | 0.389 | 0/0 of 0 | 0/0 | – |  |
| wps_education_years | Women's years of schooling (national) | annual | national | 79 | 48 (2019-01..2025-12) | up | 0.159 | 0.734 | 0.824 | 0/0 of 0 | 0/0 | – |  |
| wps_rank | Women, Peace & Security rank (national) | annual | national | 79 | 48 (2019-01..2025-12) | up | 1.83 | 0.149 | 0.285 | 0/0 of 0 | 0/0 | – |  |
| wps_index | Women, Peace & Security score (national) | annual | national | 79 | 48 (2019-01..2025-12) | down | -0.017 | 0.734 | 0.824 | 0/0 of 0 | 0/0 | – |  |