# South Sudan unified county-month dataset, Jan 2018 to Sep 2026

Built 14 Nov 2026. Keyed for geospatial joins on **OCHA COD-AB v03 admin2 p-codes** (79 counties incl. Abyei `SS0001`) and **calendar month (`YYYY-MM`)**, so climate rasters aggregated to county-month (rainfall, NDVI, LST, soil moisture, etc.) can be joined directly on `county_pcode` + `month`.

## Files

| File | What it is |
|---|---|
| `ssd_unified_long_2018-01_2026-09.csv` | **Main file.** One row per county (or national) x month x variable. 185,221 rows, 55 variables. |
| `ssd_county_month_wide.csv` | Same county-level monthly variables, one row per county-month (6,478 rows, Dec 2019-Sep 2026). |
| `ssd_national_month_wide.csv` | National variables, one row per month (105 rows, Jan 2018-Sep 2026). |
| `variables_dictionary.csv` | Each variable: level, unit, source, first/last month with data, rows missing. |
| `counties_lookup.csv` | p-codes (OCHA and IOM), names, state, area, centroid, population 2022 and 2025. |
| `fmr/fmr_internal_forced_2020_2025_filled.csv` | Row-level Flow Monitoring records (your extract + recovered months), with `origin_file`. |
| `fmr/fmr_flows_county_to_county.csv` | Monthly county-to-county flows by reason (for flow arrows). |
| `fmr/fmr_monitoring_points.csv` | Monitoring points with coordinates and county. |
| `fmr/fmr_national_monthly.csv` | National FMR series incl. 2024 report-level totals and quality flags. |

## Long-file columns

`county_pcode` (`SS` = national), `county`, `state`, `spatial_level` (county / national), `year`, `month` (`YYYY-MM`; blank for annual population rows), `period_type` (month / calendar_year / un_fiscal_year / annual), `variable`, `value`, `unit`, `source`, `quality_flag`.

National rows are kept national on purpose: funding and troop strength do not vary by county, so broadcasting them to 79 counties would imply spatial detail that does not exist. Join them on `month` when needed.

## Variable groups

| Prefix | Level | Coverage | Source |
|---|---|---|---|
| `et_*` (16) | county | Dec 2019-Sep 2026, zero-filled | IOM DTM Event Tracking (people displaced or returning, by cause, by county of arrival) |
| `fmr_departed_*`, `fmr_arrived_*`, `fmr_within_*`, `fmr_monitoring_points_in_county` (13) | county | Jan 2020-Aug 2025; **blank** Nov 2023-Dec 2024 | IOM DTM Flow Monitoring Registry, internal forced non-return trips |
| `logcluster_hubs_in_county` | county | Dec 2019-Sep 2026 | Logistics Cluster CONOPS maps (your hackathon zip) |
| `unmiss_deployment_sites_in_county` | county | Dec 2023-Sep 2026 | UN map 4456 Rev. 58-65 (your zip) + documented closures |
| `population_estimate` | county | 2022, 2025 | OCHA COD-PS |
| `unmiss_uniformed_personnel`, `unmiss_budget_fy_usd`, `unmiss_expenditure_fy_usd` | national | 2018-2026 | UN DPO (HDX), A/RES/79/309, A/80/621 |
| `fts_*`, `hrp_*` | national | 2018-2026 | OCHA Financial Tracking Service API |
| `us_aid_*`, `usaid_*`, `state_dept_*` | national | Jan 2018-Jun 2026 | ForeignAssistance.gov transaction file |
| `fmr_internal_forced_*`, `fmr_all_movements_observed`, `fmr_conflict_share_all_movements`, `fmr_active_monitoring_points` | national | Jan 2020-Aug 2025 | IOM DTM FMR workbooks and monthly reports |

## Flow Monitoring gaps: what was filled and what cannot be

| Months | Status | How |
|---|---|---|
| Nov-Dec 2022, Jul-Oct 2023 | **Filled** (13,633 records, 86,268 travellers) | HDX `fmr_db_clean_nov2022_oct2023_public_nov21.xlsx`, filtered exactly as your extract (Internal, forced, non-return, SSD to SSD, conflict/disaster/food). The filter reproduces your Jan-Jun 2023 values to the person, except 6 people in Mar 2023 (one row revised in IOM's consolidated file). |
| Jun-Dec 2024 | **National totals only** | IOM FMR Cross Border Movement Reports #59-#65 publish all-direction totals and reason shares, not county flows. Reason shares for Sep and Oct 2024 are identical to Aug 2024 and are flagged as a likely template carry-over. |
| Nov 2023-May 2024 | **Not published** | No dataset or report found on HDX or the IOM DTM site. Rows are present with blank values and `quality_flag` = "no public FMR data for this month". |

## Quality checks run

- Event Tracking: 5,389,113 people-movements; causes sum to the total in every row; identical to the earlier files.
- FMR: for every month, departures + within-county + missing-endpoint = national total (difference 0); departures = arrivals. Grand total 191,317 = sum of source rows.
- Duplicates: no month is drawn from more than one workbook. Repeated identical rows inside a workbook are kept: the 2025 HDX file carries a unique ID per record and its monthly totals match IOM's published reports exactly (e.g. Feb 2025 45,369; Apr 2025 41,432), which shows these are separate traveller groups with the same attributes, not copies.
- Your 2025 extract matches the HDX 2025 workbook to within 6 people (2 rows) out of 38,098.
- No duplicate (county, month, variable) keys in the long file.

## Cautions

- Event Tracking and Flow Monitoring measure different things; do not add them.
- FMR counts depend on where monitoring points sit (from 2023 mostly Renk River Port). The Jun-Jul 2025 drop (994 to 72) follows IOM's suspension of onward transport on 1 Jun 2025.
- UNMISS sites after Oct 2025 apply only documented closures (Aweil Nov 2025, Tambura Jan 2026, Akobo end-Jun 2026); other closures were reported in aggregate but not by site.
- Before Dec 2019 there is no county-level displacement data in this set; national series start Jan 2018.
