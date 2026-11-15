#!/usr/bin/env bash
# Build the SMAP soil-moisture layers from the processed AppEEARS SMAP tasks and put SMAP in place of
# TerraClimate soil moisture on the map. Re-runnable.
#   APPEEARS_WORK  = AppEEARS state dir (tasks.json, partials/, grids/)
#   SWAP=1         = also switch docs/data/curated.json from tc_soil to SMAP (do this once all years are in)
set -euo pipefail
cd "$(dirname "$0")/.."
K="smap_sm_rootzone smap_sm_surface"
APPEEARS_RENDER=smap_sm_rootzone,smap_sm_surface python scripts/fetch_appeears.py assemble
APPEEARS_GRIDS="$APPEEARS_WORK/grids" python scripts/raster_trends.py $K
L=""; for k in $K ${K// /_trend }_trend; do [ -f docs/rasters/$k/meta.json ] && L="$L $k"; done
for k in $L; do
  python - "$k" <<'PY'
import json, sys
p = f"docs/rasters/{sys.argv[1]}/meta.json"; m = json.load(open(p))
for f in ("recolored", "palette"): m.pop(f, None)       # freshly rendered -> recolour again
json.dump(m, open(p, "w"), indent=1)
PY
done
python scripts/recolor_rasters.py $L
python scripts/recolor_rasters_rwg.py $L
if [ "${SWAP:-0}" = 1 ]; then python scripts/swap_soil_to_smap.py; fi
python scripts/build_web_data.py
