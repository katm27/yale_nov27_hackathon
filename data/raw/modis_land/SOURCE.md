# MODIS land products (no raw files committed)

Streamed directly from Microsoft Planetary Computer STAC (no login):
https://planetarycomputer.microsoft.com/api/stac/v1 — collections
`modis-13A1-061` (MOD+MYD), `modis-11A2-061` (MOD), `modis-09A1-061` (MOD), `modis-16A3GF-061` (MOD),
tiles h20v07 h20v08 h21v07 h21v08, 2018-01..2025-12. COG assets are read in memory; nothing is stored.

Re-run:
```
MODIS_WORK=/some/scratch python scripts/fetch_modis_land.py ndvi lst et refl   # county CSV + meta + grids
MODIS_WORK=/some/scratch python scripts/make_modis_rasters.py                   # docs/rasters/modis_*
```
Intermediate per-month partial CSVs and 0.01° float32 grids go to `$MODIS_WORK` (default
`data/raw/modis_land/work/`, ~1 GB, do not commit).

Known catalog gaps on Planetary Computer (as of 2026-11): no Terra/Aqua composites for 2025-07..2025-10;
MOD11A2 missing 2022-10 (and MOD09A1 only partly present then). MOD16 8-day ET is not hosted, so ET is annual.
