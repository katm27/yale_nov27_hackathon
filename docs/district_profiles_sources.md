# District profile sources

`data/district_profiles.json` holds the county hover-card profiles (79 counties). It is built by
`python scripts/build_district_profiles.py`, which merges:

- **`data/district_profiles_narrative.json`**: hand-written `history` and `conflict_narrative` text with per-county `sources`. Edit text here.
- **Livelihood zones**: an area overlay of `data/counties.geojson` on the FEWS NET 2018 zones (`data/raw/fews_lhz/SS_LHZ_2018.zip`, EPSG:6933 equal-area). The dominant zone is reported. A secondary zone is added when it covers more than 25% of the county. All shares of 5% or more are kept in `key_facts.lhz_shares`. Zone text is condensed from the FEWS NET zone descriptions and is in `ZONES` in the script.
- **`key_facts`**: recomputed from the processed county-month tables every time the script runs. `conflict_impact` is a hand-written, number-free narrative (`conflict_impact` in `data/district_profiles_narrative.json`) that describes these values in words (e.g. "among the deadliest counties", "floods displaced tens of thousands") alongside the sourced events in `conflict_narrative`. All numbers stay in `key_facts`; a numeric sentence is generated only as a fallback for a county with no narrative.

## Livelihoods
- FEWS NET South Sudan livelihood zones 2018 (shapefile): https://shapefiles.fews.net/LHZ/SS_LHZ_2018.zip
- FEWS NET, *Livelihoods Zone Map and Descriptions for the Republic of South Sudan (updated)*, Aug 2018: https://fews.net/sites/default/files/documents/reports/Livelihoods%20Zone%20Map%20and%20Descriptions%20for%20South%20Sudan.pdf

## History and conflict narrative
- CSRF (Conflict Sensitivity Resource Facility) county profiles, 2023-24 editions. This is the main source for communities, county headquarters, 2013-2018 history and post-2018 dynamics. The URL pattern is `https://archive.csrf-southsudan.org/county_profile/<county>/`, and each profile cites its own primary sources (UNSC, UN Panel of Experts, Radio Tamazuj, Small Arms Survey and others).
- UNMISS HRD, *Conflict-related violations and abuses in Central Equatoria, Sept 2018-Apr 2019*: https://www.ecoi.net/en/file/local/2012167/final_-_human_rights_division_report_on_central_equatoria_-_3_july_2019.pdf
- UNMISS annual briefs on violence affecting civilians:
  - 2020: https://www.ecoi.net/en/file/local/2048257/unmiss_annual_brief_violence_against_civilians_2020_final_for_publication.pdf
  - 2022: https://www.developmentaid.org/api/frontend/cms/file/2023/03/2022_annual_brief_on_violence_affecting_civilians_in_south_sudan_0.pdf
  - 2023: https://unmiss.unmissions.org/sites/default/files/annual_brief_on_violence_affecting_civilians_2023.pdf
  - 2024: https://unmiss.unmissions.org/sites/default/files/2025-10/annual_brief_on_violence_affecting_civilians_in_south_sudan_january_-_december_2024.pdf
- UNMISS quarterly briefs:
  - Q3 2024: https://unmiss.unmissions.org/sites/default/files/human_rights_brief_violence_affecting_civilians_july-september_2024.pdf
  - Q2 2025: https://unoau.unmissions.org/sites/default/files/2026-01/UNMISS%20HRD%20Q2%20Brief%20on%20Violence%20Affecting%20Civilians%20%209%20Sept%20%202025.pdf
- UNMISS/OHCHR, *Armed violence involving community-based militias in Greater Jonglei, Jan-Aug 2020*: https://docs.southsudanngoforum.org/sites/default/files/2021-04/21-03-11%20Jonglei%20report%20FINAL.pdf
- UNMISS/OHCHR, *Attacks against civilians in southern Unity State, Feb-May 2022*: https://unmiss.unmissions.org/sites/default/files/report_on_attacks_on_civilians_in_southern_unity_state_-_06_september_2022.pdf
- UNMISS/OHCHR, *Attacks against civilians in Greater Upper Nile, Aug-Dec 2022*: https://unmiss.unmissions.org/sites/default/files/greater_upper_nile_report.pdf
- CSRF, *Tambura: violence, displacement and response* (Dec 2021): https://www.csrf-southsudan.org/wp-content/uploads/2021/12/CSRF-Analysis-Tambura-Violence-Displacement-and-Response-20-Dec-2021.pdf
- Fangak flooding 2021 (OCHA data via 211check): https://www.211check.org/post/data-story-south-sudan-floods-database-2021
- Bentiu floods (MSF): https://www.msf.ie/article/catastrophic-floods-cause-mass-displacement-and-escalating-humanitarian-crisis-south-sudan
- Renk / Sudan-war arrivals: REACH (Jul 2025) https://repository.impact-initiatives.org/document/repository/8d39fa52/REACH_SSD_Brief_Renk-Emergency-Assessment_July-2025.pdf and MSF https://www.msf.org/war-sudan-exacerbates-humanitarian-needs-south-sudan
- UNISFA (Abyei): https://unisfa.unmissions.org/
- Wikipedia county articles, used for some towns and history facts and cited per county.
- GeoEPR 2021 (`data/processed/ethnic_county_lookup.csv`), used only to cross-check the groups named. It covers just 10 groups, so the CSRF lists take precedence.

## Numbers (`key_facts`)
| key | source file | origin |
|---|---|---|
| `acled_*` (political-violence events/fatalities, civilian-targeting fatalities, peak year) | `acled_county_monthly.csv` | ACLED public aggregates via HDX, https://data.humdata.org/dataset/south-sudan-acled-conflict-data |
| `ucdp_*` | `ucdp_county_monthly.csv` | UCDP GED, https://ucdp.uu.se/downloads/ |
| `dtm_idps_*` (peak/latest IDP stock) | `dtm_county_monthly.csv` | IOM DTM baseline rounds (2018-06 to 2025-02) |
| `dtm_et_*` (displaced by flooding / communal / national conflict, arrivals from Sudan) | `unified_county_monthly.csv` (`et_ind_*`) | IOM DTM Event Tracking 2019-12 to 2025-12 |
| `ipc_phase3plus_*` | `ipc_county_monthly.csv` | IPC county analyses (no 2021 county analysis) |
| `surface_water_*` | `water_county_monthly.csv` | project surface-water series (max monthly % of county area) |
| `lhz_shares` | FEWS NET shapefile overlay | see above |

Caveats: ACLED records no political-violence events for Nzara (SS1008) or Longochuk (SS0703) in 2018-2025, which may reflect sparse reporting or location coding. DTM baseline data do not cover Abyei (no IDP stock). Flood-displacement totals come from event tracking only and are not exhaustive.
