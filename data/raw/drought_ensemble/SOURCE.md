# Drought ensemble inputs
- TerraClimate v1.1 ppt, pet, PDSI 1991-2025, NKN THREDDS NCSS subsets (see scripts/fetch_terraclimate.py URL pattern)
- CHIRPS v3.0 monthly Africa GeoTIFFs 1991-2025, windowed reads via /vsicurl:
  https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/africa/tifs/chirps-v3.0.YYYY.MM.tif
Cached in `_cache/` (gitignored). `member_correlations_2018_2025.csv` = pooled member correlations.
