# TerraClimate raw subsets (not committed, ~350 MB)

Re-create with `python scripts/fetch_terraclimate.py --workdir <dir>`.

Per variable-year NCSS subset (bbox N12.4 S3.3 W23.3 E36.1, all months):

    https://thredds.northwestknowledge.net/thredds/ncss/TERRACLIMATE_ALL/data/TerraClimate_{f}_{y}.nc?var=<var>&north=12.4&south=3.3&west=23.3&east=36.1&temporal=all&accept=netcdf

Variables ppt, tmax, tmin, aet, pet, def, soil, ws, PDSI, vpd, srad, q for 2018-2025; ppt and tmax also 1991-2020 (climatology baseline for extreme flags).

Catalog: https://thredds.northwestknowledge.net/thredds/catalog/TERRACLIMATE_ALL/data/catalog.html
Citation: Abatzoglou, J.T. et al. (2018) Sci. Data 5:170191. License CC0.
