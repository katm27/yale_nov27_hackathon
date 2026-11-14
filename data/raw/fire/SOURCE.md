# Fire (MODIS) — scripts/fire_pipeline.py
- Active fire: MOD14A1 / MYD14A1 v061 daily FireMask (1 km), Microsoft Planetary Computer STAC
  collection `modis-14A1-061` (https://planetarycomputer.microsoft.com/dataset/modis-14A1-061). Tiles h20v07, h20v08, h21v07, h21v08.
- Burned area: MCD64A1 v061 Burn_Date (500 m), PC collection `modis-64A1-061`.
- Nothing downloaded to disk (COGs streamed with window reads). `part_active.csv` = raw (un-normalised) monthly counts,
  `active_fire_sensor_days.csv` = number of Terra/Aqua daily layers available per month (used for normalisation),
  `part_burned.csv` = burned-area rows.
- PC catalogue gaps (as of 2026-11): 8-day/daily MODIS fire 2025-07..2025-11 partially/fully missing; MCD64A1 missing 2023-09, 2024-07, 2025-05, 2025-08..10.
- NASA FIRMS (firms.modaps.eosdis.nasa.gov) was not reachable from the build environment (connection reset).
