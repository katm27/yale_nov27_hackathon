"""Basemap context for the web app: neighbouring-country outlines + names, a South Sudan outline
(used to clip the terrain layer to South Sudan), and a short list of major towns.
Inputs: Natural Earth 1:50m admin-0 countries and 1:10m populated places (GeoJSON, v5.1.2), downloaded to IN_DIR.
Usage: python scripts/build_basemap_context.py IN_DIR"""
import json, os, sys
from shapely.geometry import shape, mapping, box
from shapely.ops import unary_union

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = sys.argv[1]
OUT = os.path.join(ROOT, "docs", "data", "basemap_context.json")
NEIGH = {"SDN": "Sudan", "ETH": "Ethiopia", "KEN": "Kenya", "UGA": "Uganda", "COD": "DR Congo", "CAF": "Central African Rep."}
VIEW = box(21.0, 1.0, 39.5, 14.5)

ne = json.load(open(os.path.join(IN, "ne50.geojson")))
feats = []
for f in ne["features"]:
    iso = f["properties"].get("ADM0_A3")
    if iso in NEIGH:
        g = shape(f["geometry"]).intersection(VIEW).simplify(0.02)
        feats.append({"type": "Feature", "properties": {"name": NEIGH[iso], "iso": iso}, "geometry": mapping(g)})
counties = json.load(open(os.path.join(ROOT, "docs", "data", "counties.geojson")))
ssd = unary_union([shape(f["geometry"]).buffer(0) for f in counties["features"]]).buffer(0.002).buffer(-0.002).simplify(0.005)
# Major towns: state capitals and main border / river towns (names as used by OCHA).
TOWNS = {"Juba": 1, "Wau": 1, "Malakal": 1, "Bor": 1, "Bentiu": 1, "Rumbek": 1, "Aweil": 1, "Torit": 1, "Yambio": 1,
         "Kuajok": 1, "Renk": 2, "Yei": 2, "Nimule": 2, "Nasir": 2, "Pibor": 2, "Kapoeta": 2, "Abyei": 2, "Raja": 2}
pp = json.load(open(os.path.join(IN, "places.geojson")))
towns = {}
for f in pp["features"]:
    p = f["properties"]
    if p.get("adm0_a3") in ("SDS", "SSD") or p.get("sov_a3") in ("SDS", "SSD"):
        if p["name"] in TOWNS:
            towns[p["name"]] = [round(p["latitude"], 3), round(p["longitude"], 3), p["name"], TOWNS[p["name"]], p["name"] == "Juba"]
missing = set(TOWNS) - set(towns)
# fall back to county centroids for towns not in Natural Earth (county named after its main town)
for f in counties["features"]:
    n = f["properties"]["name"]
    for t in list(missing):
        if n.lower().startswith(t.lower()):
            c = shape(f["geometry"]).representative_point(); towns[t] = [round(c.y, 3), round(c.x, 3), t, TOWNS[t], False]; missing.discard(t)
if "Kuajok" in missing:  # Warrap state capital, not in Natural Earth places
    towns["Kuajok"] = [8.302, 27.98, "Kuajok", 1, False]; missing.discard("Kuajok")
json.dump({"neighbors": {"type": "FeatureCollection", "features": feats},
           "ssd": {"type": "Feature", "properties": {"name": "South Sudan"}, "geometry": mapping(ssd)},
           "towns": sorted(towns.values(), key=lambda t: (t[3], t[2])),
           "source": "Natural Earth 1:50m admin-0 & 1:10m populated places (public domain); OCHA county boundaries"},
          open(OUT, "w"), separators=(",", ":"))
print(OUT, os.path.getsize(OUT), "towns:", len(towns), "missing:", missing)
