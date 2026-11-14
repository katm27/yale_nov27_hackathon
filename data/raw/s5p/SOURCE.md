# Sentinel-5P — scripts/s5p_pipeline.py
Copernicus Sentinel-5P TROPOMI L2 NetCDF (OFFL/RPRO) via Microsoft Planetary Computer `sentinel-5p-l2-netcdf`
(L2__AER_AI, L2__NO2___, L2__CO____). Only the scanlines over South Sudan are fetched with HTTP range reads (h5py+fsspec).
`monthly_grids/<product>_<YYYY-MM>.npz` = per-month 0.05 deg sum/count grids (cache, git-ignored, ~75 MB total; re-creatable).
`orbits_used.csv` = number of orbits used per product-month.
