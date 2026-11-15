# GRACE / GRACE-FO water storage (GFZ GravIS, open access, no login)

- TWSA: https://isdc-data.gfz.de/grace-fo/GravIS/COST-G/Level-3/TWS/GRAVIS-3_COSTG_0200_TWS_GRID_GFZ_0001.nc
  COST-G combined GRACE/GRACE-FO Level-3, 1°, monthly 2002-04..2026-07 (file dated 2026-10-04), cm EWH.
- GWSA: https://isdc-data.gfz.de/grace-fo/GravIS/G3P/v1.12/G3P_v1.12.zip
  G3P v1.12, 0.5°, monthly 2002-04..2023-09, mm (converted to cm).
- Downloaded files are cached in `_cache/` (gitignored, ~0.9 GB); `python scripts/fetch_grace.py` re-downloads.
- Cite: Boergens, Dobslaw, Dill (GFZ) COST-G GravIS L3 TWS; Güntner et al. (2024) G3P v1.12, GFZ Data Services.
