# Sudd MODIS water / inundation index — sources

Built by `scripts/sudd_water_index.py` (validation: `scripts/sudd_water_validate.py`, `docs/VALIDATION_sudd_water.md`).

| input | access | notes |
|---|---|---|
| MODIS Terra MOD09A1 v061, 8-day 500 m surface reflectance, tiles h20v08 + h21v08 | https://planetarycomputer.microsoft.com/dataset/modis-09A1-061 (STAC, anonymous SAS signing) | bands b01, b02, b03, b04, b06 + sur_refl_state_500m, read as windows from COGs (nothing stored) |
| MODIS MCD43A4 v061 NBAR (substitute for 12 missing Terra tile-composites: 2022 day 265-297, 2023 day 001 and 305) | https://planetarycomputer.microsoft.com/dataset/modis-43A4-061 | BRDF quality 0 only counts as observed |
| Ramsar site 1622 "Sudd" outline | RSIS geoserver WFS `ramsar_sdi:features_published` | **not available**: only a centroid is published for site 1622 (checked 15 Nov 2026); WDPA requires an account |

Not available on Planetary Computer (checked 15 Nov 2026): any MODIS reflectance (MOD/MYD09A1, MCD43A4, MOD13A1) for
2025 day 185-321 (4 Jul - 24 Nov 2025), and MOD09A1/MCD43A4 for 2022 day 337 and 345 (3-18 Dec 2022).

Files here:
- `sudd_water_county_8day.csv` — per-county 8-day series (open water, inundation, observed / carried / climatology shares)
- `sudd_inundation_frequency_2018_2025.tif` — MODIS sinusoidal 500 m; band 1 = % of clear 8-day observations
  2018-2025 classed inundated, band 2 = % classed open water (255 = outside AOI)
- `_cache/` (gitignored) — STAC item list and one compressed class grid per composite (~15 MB); delete with `--clean-cache`
