# NASA AppEEARS downloads (scripts/fetch_appeears.py)

API: https://appeears.earthdatacloud.nasa.gov/api/ (Earthdata login; credentials from env vars, never stored).
Area requests clipped to the dissolved South Sudan outline (data/counties.geojson, 0.02 deg buffer), GeoTIFF
(MODIS) / NetCDF4 (SMAP), geographic projection. Raw bundles (~0.2-1 GB per task) are NOT kept: each file is
aggregated to a 0.01 deg grid and county x month, then deleted. Re-run with
`APPEEARS_WORK=<dir> python scripts/fetch_appeears.py all --wait` (task ids are saved in <work>/tasks.json;
bundles stay downloadable from AppEEARS for ~30 days after completion, after which tasks must be resubmitted).

Tasks submitted 2026-11-15:

| name | product | task id |
|---|---|---|
| et_2018 | MOD16A2GF.061 | `ff9d814d-bf66-4c7d-8191-24da8ab248e6` |
| et_2019 | MOD16A2GF.061 | `738640b3-2c96-44c2-b545-487ae2508bdc` |
| et_2020 | MOD16A2GF.061 | `b5284772-8fa9-44fd-9083-4022f7033194` |
| et_2021 | MOD16A2GF.061 | `7c64d4f1-38dc-4301-96be-1a062e588d45` |
| et_2022 | MOD16A2GF.061 | `a37d95b4-a339-4375-8c8c-ff598725e5fe` |
| et_2023 | MOD16A2GF.061 | `3f87c346-9f0c-46fa-98ef-29c007ea8915` |
| et_2024 | MOD16A2GF.061 | `9dabf7d1-d70f-42b8-b5f3-6491782f76e0` |
| et_2025 | MOD16A2GF.061 | `af6bdc7b-0eee-40ab-92ee-4f1da211d471` |
| ndvi13a3 | MOD13A3.061 | `2907ef81-2793-47bf-b94f-8d6b3bad5c94` |
| lst_2022_2025 | MOD11A2.061 | `03cbd4ad-3728-4399-bba7-fd33ab2e67a5` |
| burn_2018 | MCD64A1.061 | `ca394322-ab43-4509-a34b-86e11ba4c6fd` |
| burn_2022 | MCD64A1.061 | `b3541861-b1bb-4865-a69e-c57f6c7f221e` |
| smap_2018 | SPL4SMGP.008 | `007e66fa-df47-4a0f-bd9a-0cc57dbf1676` |
| smap_2019 | SPL4SMGP.008 | `ed0221f6-6eb9-404f-8a96-4c9e0b3501c9` |
| smap_2020 | SPL4SMGP.008 | `21b54d7d-9a2c-44e4-ab62-44234e26b166` |
| smap_2021 | SPL4SMGP.008 | `6fe1c3a5-db81-40ea-964b-a7c1a638fb73` |
| smap_2022 | SPL4SMGP.008 | `841683ed-6e19-4c4d-ae85-8a88ab20b50e` |
| smap_2023 | SPL4SMGP.008 | `820879a0-a9f9-467a-8938-910703e7f1c9` |
| smap_2024 | SPL4SMGP.008 | `59aad903-8efe-4050-b3d4-90093794c5e9` |
| smap_2025 | SPL4SMGP.008 | `aeeb5da0-5517-444b-a232-ba9717149990` |

Not available in AppEEARS (checked /api/product, 2026-11-15): VIIRS Black Marble VNP46A1/A2/A3/A4 night lights,
GRACE / GRACE-FO, GLDAS.
