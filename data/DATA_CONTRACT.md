# Data contract (all pipelines write to this format)

**Geography:** South Sudan, 79 counties (admin-2), from `data/counties.geojson`
(`district_id` = OCHA P-code, e.g. `SS0101` = Juba). "District" in this project = county.
Abyei (`SS0001`-style special area) is included where the boundary file includes it.

**Time window:** 2018-01 to 2025-12 (monthly). Baseline year for indexing = 2018.

## 1. County time series — `data/processed/<source>_county_monthly.csv`
Long format, one row per county x month x variable:

| column | example | notes |
|---|---|---|
| `county_id` | `SS0101` | must match `district_id` in counties.geojson |
| `date` | `2019-07-01` | first day of month. Annual-only data: use `YYYY-07-01` and set `temporal: annual` in meta. Seasonal: first month of season |
| `variable` | `ndvi_mean` | snake_case, unique across project, prefix by source if ambiguous |
| `value` | `0.43` | float, raw units (NOT indexed — indexing happens in `scripts/build_web_data.py`) |

Missing = row absent (do not write 0 unless the true value is 0, e.g. zero conflict events).

## 2. Variable metadata — `data/processed/meta/<source>.json`
A JSON list, one object per variable:
```json
{"id": "ndvi_mean", "label": "NDVI (vegetation greenness)", "category": "environment",
 "group": "Vegetation", "units": "index -1..1", "source": "MODIS MOD13A1 v061 via Planetary Computer",
 "source_url": "https://...", "native_resolution": "500 m", "temporal": "monthly",
 "aggregation": "mean of valid pixels within county", "higher_is": "better",
 "index_ok": true, "raster": "ndvi", "notes": "..."}
```
`category`: `environment` | `human`. `higher_is`: `better` | `worse` | `neutral` (drives map color direction).
`index_ok`: false for variables where a ratio to 2018 is not meaningful (e.g. SPEI, temperatures in °C, values that can be ≤0); the app then shows the difference from 2018 instead.
`raster`: optional key of a raster overlay folder in `docs/rasters/`.

## 3. Raster overlays (finest resolution) — `docs/rasters/<key>/`
For gridded variables, monthly PNG overlays for the web map:
- `docs/rasters/<key>/YYYY-MM.png` — reprojected to **EPSG:3857 (Web Mercator)**, transparent outside South Sudan,
  fixed color scale across all months, max ~1000 px on the long side, palette-compressed (keep each < ~250 KB).
- `docs/rasters/<key>/meta.json` — `{"key","label","units","bounds":[[south,west],[north,east]] (lat/lon of image corners),
  "vmin","vmax","colormap","native_resolution","dates":["2018-01",...],"source"}`.

## 4. Point layers — `docs/data/points_<key>.geojson`
Facilities/infrastructure/events as GeoJSON points with `name`, `type`, `source`, and `date` / `year` where it applies.
Add a matching entry to `data/processed/meta/points.json` (`{"key","label","category","source","source_url","notes"}`).

## 5. Provenance
Each pipeline is a script in `scripts/` (re-runnable). Raw downloads go in `data/raw/<source>/`
(skip committing raw files > 50 MB; record the URL instead in `data/raw/<source>/SOURCE.md`).
