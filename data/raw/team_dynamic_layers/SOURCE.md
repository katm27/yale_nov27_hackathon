# Team-supplied time-dynamic layers (v2)

- File: `south_sudan_dynamic_layers_2018_2025_v2.zip` (~0.95 MB), supplied by the team on 15 Nov 2026 (chat upload).
- Contents: status-period layers 2018-2025 (health facilities, schools, oil wells/pipelines/block timeline, GeoEPR
  ethnic groups, GBV one-stop centres, oil spills, Sentinel-1 flood water around oil wells, HLS/Sentinel-2 surface-water
  optical indices), OCHA 3W county-month partner counts (protection/GBV, nutrition), dated context events with source
  URLs, and the Python scripts that produced them. Full sources and methods: `METHODS.md` inside the zip.
- Upstream sources (as documented in METHODS.md): HDX (MoH 2016 and 2023 facility lists, WHO Master Facility List
  Mar 2024, IOM DTM village assessments 2019-20, SSSAMS 2015 list and 2019 enrolment export, OCHA 3W 2019-2025),
  OpenStreetMap via HOT Raw Data API (ODbL), ETH Zurich GeoEPR/EPR/ACD2EPR 2021, Sentinel-1 RTC, NASA HLS v2 and
  Sentinel-2 L2A via Microsoft Planetary Computer, UNFPA/UNICEF/FAO-World Bank reports, Sign of Hope, PAX, news
  and agency reports (URLs in `context_events_2018_2025.csv`).
- Used by: `scripts/team_dynamic_layers.py` (reads the zip in place; nothing is extracted into the repo).
  Outputs: docs/data/points_health, points_schools, points_oil, lines_pipelines, polygons_ethnic_groups,
  points_gbv_one_stop_centres, points_oil_pollution, points_oil_wells_flooding, points_surface_water_quality,
  docs/data/context_events.json, data/processed/sector_partners_county_monthly.csv (+ meta/sector_partners.json).
- Not used: the MODIS gas-flare test (inconclusive per METHODS.md) and the per-well monthly flooding table as a county
  series (it is per well, ~100 of ~400 Unity wells; used only as the well-status layer).
