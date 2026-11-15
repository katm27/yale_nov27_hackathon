# NASA FIRMS VIIRS 375 m active fires

Downloaded with `scripts/fetch_firms_viirs.py` (needs env FIRMS_MAP_KEY; free key from https://firms.modaps.eosdis.nasa.gov/api/map_key/).

Requests (10-day chunks, bbox W,S,E,N = 23.4,3.4,36.0,12.3):

    https://firms.modaps.eosdis.nasa.gov/api/area/csv/<MAP_KEY>/VIIRS_SNPP_SP/23.4,3.4,36.0,12.3/10/<YYYY-MM-DD>
    https://firms.modaps.eosdis.nasa.gov/api/area/csv/<MAP_KEY>/VIIRS_NOAA20_SP/23.4,3.4,36.0,12.3/10/<YYYY-MM-DD>

S-NPP 2018-01-01..2025-12-31, NOAA-20 2020-01-01..2025-12-31 (standard-processing archive, collection 2).

Files here: `viirs_<snpp|noaa20>_<year>.csv.gz` = detections after filtering (confidence n/h, type 0, inside a county) with the county_id they fall in. The unfiltered bbox API responses are cached in `_api_cache/` (not committed).

Filter counts: {"VIIRS_SNPP_SP": {"bbox": 1860663, "conf_nh": 1620097, "type0": 1617187, "in_country": 920097}}

Citation: NASA FIRMS, VIIRS 375 m active fire product VNP14IMGTDL / VJ114IMGTDL (Schroeder et al. 2014). doi:10.5067/FIRMS/VIIRS/VNP14IMGT_NRT.002
