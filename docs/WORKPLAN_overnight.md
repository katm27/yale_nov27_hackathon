# Overnight work plan (requested 15 Nov 2026)

Status legend: [ ] todo · [~] in progress · [x] done. Updated by Claude as work proceeds; each item lists its owner.

## 1. County reconciliation (gold standard = OCHA COD-AB v03, 79 counties incl. Abyei)
- [x] Master crosswalk `data/crosswalks/county_crosswalk_master.csv` (OCHA P-code ↔ IOM codes ↔ ACLED/IPC/HNO/WFP/UNHCR/GADM names; 2015–2020 32/28-state era and 2020 administrative areas noted) — agent "crosswalk"
- [x] Per-source audit `docs/AUDIT_county_crosswalk.md` (match rates, fixes, residual issues); re-run any pipeline whose join was wrong — agent "crosswalk"
- [x] Verified border-crossing points for cross-border flow arrows `data/crosswalks/border_crossings.csv` — agent "crosswalk"

## 2. Time-dynamic point layers (standard properties `valid_from` / `valid_to`, YYYY-MM)
- [x] Logistics Cluster CONOPS maps (all dated PDFs) → hubs over time — agent "points-time"
- [x] UNMISS deployment maps (map 4456 revisions + Geo-PKO) → sites over time — agent "points-time"
- [x] Other layers: PoC/IDP/refugee sites open/close dates, WFP markets active months, FMR monitoring points active months, oil fields status (incl. 2024 export shutdown), health/schools (snapshot dates) — agent "points-time"
- [x] App: filter every point layer by the time-slider window (valid_from/valid_to, date, year) — lead

## 3. Methods, sources & confidence guide
- [x] `docs/METHODS_AND_DATA_GUIDE.md`: every calculation, every source, confidence rating per dataset — lead (after data agents finish)

## 4. Climate data review
- [x] `docs/CLIMATE_DATA_DECISIONS.md`: raw vs derived products, provenance; flood product choice (MODIS water vs UNOSAT/GFM/FloodScan etc.); water contamination / pollution spread options — agent "climate-review"
- [x] Implement recommended derived flood series + drought-index ensemble & uncertainty + feasible contamination proxies — agent "climate-review"

## 5. UI
- [x] Arrows: one clear source at a time ("best available" per month), explained in UI; fix cross-border origins (verified crossings) and county anchors — lead
- [x] Map mode "Trend": colour by Sen's slope (%/yr of 2018 and ×-change 2018→2025); white outline = Mann-Kendall significant — lead
- [x] Hover card (built; profiles done for all 79 counties; drought ensemble/flood product fill in as climate agent finishes): district profile (history, livelihoods, conflict impact) at top; Sen's slope + MK note; sparklines of forced migration, US humanitarian aid, flood extent, drought (with uncertainty band) — lead + agent "profiles"
- [x] Bottom national timeline: USAID / US aid, total humanitarian funding (FTS), HRP coverage, UNMISS uniformed personnel, key climate series, GBV indicators — lead
- [x] GBV & water: REACH MSNA women's safety / water-collection indicators, water points (WPDx), groundwater options; within-county conflict indicators — agent "gbv-water"

## Already running (started earlier)
- [x] NASA AppEEARS: monthly ET, MOD13A3 NDVI/EVI, Jul–Oct 2025 LST & burned-area fill done; SMAP queued at NASA (>30 h); night lights not available via AppEEARS
- [x] FIRMS VIIRS fires, CHIRPS v3 rainfall cross-check, Insecurity Insight incidents (national only: source censors coordinates)

## Round 2 (15 Nov 2026, afternoon) — user bug list + dynamic layers
Agents: raster trend-to-date layers · reconcile team dynamic-layers zip · plain-language labels/definitions/topics.
Lead (app/build), staged with a republish after each stage:
- [x] S1: close button/layer control (1,6); detail panel docked beside/below map (19); %/yr only where meaningful (3,21); no duplicated trend text (4); best-available flow label (5); national-only series kept off the county map → national timeline (8); funding axes (9); search synonyms + "no results" (10); baseline wording (18); hide developer notes (24); trend mode uses slider year (28)
- [x] S2: charts in real units with 2018 reference + SPEI/flag reading lines (12,13,15); combined comparison chart (16); multi-county compare (26); CSV export + copy link + URL state (17,27)
- [x] S3: seasonal-aware trend basis — wet-season totals for rainfall/water, annual totals for sparse counts (7,25); wetter/drier, warmer/cooler direction words (2); trend-to-date county maps; PDSI caution (23); flood-layer caveat + flooded-vegetation variable (22); plain labels/definitions/topic picks (11,14,20)
- [ ] S4: integrate agents (raster trends, zip layers, labels); republish
