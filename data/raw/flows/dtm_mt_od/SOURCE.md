# IOM DTM South Sudan Mobility Tracking: origin-destination (IDP and returnee stock)

Converter: `scripts/fetch_flows_dtm_mt_od.py`. It re-downloads the HDX files and reads the dtm.iom.int files from the local copies saved here.
Outputs: `data/processed/flows/dtm_mt_idp_od_flows.csv`, `dtm_mt_returnee_od_flows.csv`, `dtm_mt_od_by_arrival_period.csv`.

**Method.** Key informants report, for each payam or location, how many IDPs arrived in each arrival period and the county of habitual residence of the *majority* of that group. For returnees they report the county the majority returned *from*. The whole group is assigned to that majority county. This gives the IDP or returnee stock at the round date, not a monthly flow. `month` is the last month of data collection. Within-county pairs are dropped from the main files and kept, flagged, in the detail file. IDPs previously abroad (`d_` columns) record their origin as a place abroad, so they appear only in the detail file.

| Round | month | Data collection | File | URL |
|---|---|---|---|---|
| 4 | 2018-12 | Nov-Dec 2018 | hdx/mt_r04_hdx.xlsx | HDX `south-sudan-displacement-data-idps-returnees-baseline-assessment-iom-dtm` (Round 4) |
| 5 | 2019-03 | Mar 2019 | dtm_site/mt_r05_area_node5937.xlsx | https://dtm.iom.int/dtm_download_track/7999?file=1&type=node&id=5937 |
| 6 | 2019-06 | Jun 2019 | dtm_site/mt_r06_area_node7071.xlsx | https://dtm.iom.int/dtm_download_track/9003?file=1&type=node&id=7071 |
| 7 | 2019-11 | Oct-Nov 2019 | dtm_site/mt_r07_area_node7810.xlsx | https://dtm.iom.int/dtm_download_track/10680?file=1&type=node&id=7810 |
| 8 | 2020-03 | Feb-Mar 2020 | dtm_site/mt_r08_area_node10035.xlsx | https://dtm.iom.int/dtm_download_track/12923?file=1&type=node&id=10035 |
| 9 | 2020-09 | Jul-Sep 2020 | dtm_site/mt_r09_area_node10664.xlsx | https://dtm.iom.int/dtm_download_track/13790?file=1&type=node&id=10664 |
| 10 | 2020-12 | Nov-Dec 2020 | dtm_site/mt_r10_area_node11951.xlsx | https://dtm.iom.int/dtm_download_track/15584?file=1&type=node&id=11951 |
| 11 | 2021-09 | Jul-Sep 2021 | dtm_site/mt_r11_area_node13172.xlsx | https://dtm.iom.int/dtm_download_track/17292?file=1&type=node&id=13172 |
| 12 | 2021-12 | Nov-Dec 2021 | dtm_site/mt_r12_area_node18711.xlsx | https://dtm.iom.int/dtm_download_track/27946?file=1&type=node&id=18711 |
| 13 | 2022-08 | Jul-Aug 2022 | hdx/mt_r13_hdx.xlsx | HDX (Round 13) |
| 14 | 2023-04 | Mar-Apr 2023 | hdx/mt_r14_hdx.xlsx | HDX (Round 14) |
| 15 | 2024-09 | Jul-Sep 2024 | hdx/mt_r15_hdx.xlsx | HDX (Round 15) |
| 16 | 2025-02 | Dec 2024-Feb 2025 | hdx/mt_r16_hdx.xlsx | HDX (Round 16) |

The HDX location datasets for R5-R12 have no origin fields. The payam-level "Baseline Area / Analysis and Tabulation" datasets above, listed at https://dtm.iom.int/data-product-series/baseline-assessment-7, do. dtm.iom.int returns HTTP 403 to scripted clients, so these files were saved manually. Round 2 (2018) gives origin by state only, and no Round 3 dataset was found.

**Caveats.**
- Majority attribution pushes counts towards same-county origins.
- Cross-county IDP stock by round: R4 594k, R5 692k, R6 725k, R7 660k, R8 533k, R9 538k, R10 536k, R11 678k, R12 716k, R13 **73k**, R14 207k, R15 524k, R16 510k.
- In the published R13 file, 99% of origin counties equal the current county; this looks like a coding artefact, so treat R13 with caution.
- Individuals with blank or unknown origin are dropped: 1.42M IDP and 1.18M returnee person-entries across all rounds, mostly in R13-R16, where "unknown period" groups have no origin.
