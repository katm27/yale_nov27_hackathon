# Sentinel-1 RTC monthly grids (flood_s1)
Source: Microsoft Planetary Computer STAC collection `sentinel-1-rtc` (https://planetarycomputer.microsoft.com/dataset/sentinel-1-rtc),
read remotely (1/16 COG overviews). `scripts/flood_s1_pipeline.py grids` writes monthly mean VV/VH dB grids (0.004 deg)
to `_cache/grids/YYYY-MM.npz` (~0.85 GB, gitignored) and `_cache/reference_ratio.npy` (March VV-VH reference).
Validation polygons: UNOSAT FL20220424SSD_SHP.zip (https://unosat.org/static/unosat_filesystem/3399/FL20220424SSD_SHP.zip),
unzipped in data/raw/unosat_floods/_cache/ (gitignored).
