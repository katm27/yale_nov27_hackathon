# Surface water (MODIS) — scripts/water_pipeline.py
MOD09A1 + MYD09A1 v061 8-day 500 m surface reflectance (bands 4, 7, state QA) from Microsoft Planetary Computer
(`modis-09A1-061`), streamed with window reads (nothing stored). `part_water.csv` is the resumable checkpoint.
Validation against UNOSAT: scripts/water_validate_unosat.py -> data/raw/unosat_floods/validation_state.csv.
JRC Global Surface Water on PC (`jrc-gsw`) only has the 1984-2020 aggregates (occurrence/seasonality), not monthly history, so it was not used.
