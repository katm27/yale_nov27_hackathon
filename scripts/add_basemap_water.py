"""Add rivers and lakes (Natural Earth 1:50m, public domain) to docs/data/basemap_context.json, clipped to the
map's view (South Sudan and its neighbours), so the Nile, the Sobat, Lake Victoria, Lake Turkana, Lake Albert and
Lake Tana show around and inside South Sudan.
Inputs in IN_DIR: ne_50m_rivers_lake_centerlines.geojson, ne_50m_lakes.geojson (natural-earth-vector v5.1.2).
Usage: python scripts/add_basemap_water.py IN_DIR"""
import json, os, sys
from shapely.geometry import shape, mapping, box

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = sys.argv[1]
OUT = os.path.join(ROOT, "docs", "data", "basemap_context.json")
VIEW = box(17.5, -1.5, 42.5, 16.5)
ctx = json.load(open(OUT))
out = {}
for key, fn, tol in (("rivers", "ne_50m_rivers_lake_centerlines.geojson", 0.01), ("lakes", "ne_50m_lakes.geojson", 0.01)):
    feats = []
    for f in json.load(open(os.path.join(IN, fn)))["features"]:
        g = shape(f["geometry"])
        if not g.intersects(VIEW):
            continue
        g = g.intersection(VIEW).simplify(tol)
        if g.is_empty:
            continue
        feats.append({"type": "Feature", "properties": {"name": f["properties"].get("name") or ""}, "geometry": mapping(g)})
    out[key] = {"type": "FeatureCollection", "features": feats}
    print(key, len(feats), sorted({x["properties"]["name"] for x in feats if x["properties"]["name"]})[:40])
ctx.update(out)
ctx["source"] = ctx.get("source", "") + "; rivers and lakes: Natural Earth 1:50m"
json.dump(ctx, open(OUT, "w"), separators=(",", ":"))
print(OUT, os.path.getsize(OUT))
