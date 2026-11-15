"""Pack docs/ into a low-file-count copy for hosting where file counts are limited (e.g. a claude.ai artifact).

Only what docs/data/curated.json lists is packed: the curated variables (plus the national-timeline and
hover-chart series), their raster grids and trend grids, the background layers and the point layers.
Series -> one JSON bundle; raster PNGs -> per-layer-per-year JSON of data URIs.
Usage: python scripts/pack_for_artifact.py OUT_DIR"""
import base64, glob, json, os, re, shutil, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
out = sys.argv[1]
shutil.rmtree(out, ignore_errors=True)
os.makedirs(os.path.join(out, "data"))
cur = json.load(open(os.path.join(DOCS, "data", "curated.json")))

for f in ["index.html", "app.js", "style.css"]:
    shutil.copy(os.path.join(DOCS, f), out)
# Inline Leaflet CSS (hosts with a strict CSP block third-party stylesheets), with its images as data URIs.
LEAFLET_CSS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"
css = urllib.request.urlopen(LEAFLET_CSS).read().decode()
for img in set(re.findall(r"url\((images/[^)]+)\)", css)):
    data = urllib.request.urlopen("https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/" + img).read()
    mime = "image/svg+xml" if img.endswith(".svg") else "image/png"
    css = css.replace("url(%s)" % img, "url(data:%s;base64,%s)" % (mime, base64.b64encode(data).decode()))
own = open(os.path.join(out, "style.css")).read()
open(os.path.join(out, "style.css"), "w").write(css + "\n" + own)
html = open(os.path.join(out, "index.html")).read()
html = html.replace('<link rel="stylesheet" href="%s">\n' % LEAFLET_CSS, "")
open(os.path.join(out, "index.html"), "w").write(html)

# ---- what to keep ----
var_ids = {v["id"] for v in cur["variables"]} | set(cur["national_ids"]) | set(cur["spark_ids"])
var_ids |= {b["county_var"] for b in cur["background"] if b.get("county_var")}
raster_keys = set()
for k in cur["rasters"].values():
    raster_keys |= {k, k + "_trend"}
for b in cur["background"]:
    raster_keys |= set(b.get("rasters", []))
point_keys = set(cur["points"])

copy = ["counties.geojson", "flows.json", "profiles.json", "context_events.json", "context_timeline.json", "basemap_context.json", "curated.json"]
for f in copy:
    p = os.path.join(DOCS, "data", f)
    if os.path.exists(p):
        shutil.copy(p, os.path.join(out, "data"))

# flows: the app shows IOM Event Tracking only
F = json.load(open(os.path.join(out, "data", "flows.json")))
si = next(i for i, s in enumerate(F["sources"]) if s["key"] == "et")
F["months"] = {m: [[0] + r[1:] for r in rows if r[0] == si] for m, rows in F["months"].items()}
F["months"] = {m: rows for m, rows in F["months"].items() if rows}
F["sources"] = [F["sources"][si]]
json.dump(F, open(os.path.join(out, "data", "flows.json"), "w"), separators=(",", ":"))

V = json.load(open(os.path.join(DOCS, "data", "variables.json")))
V["variables"] = [v for v in V["variables"] if v["id"] in var_ids]
V["bundle"] = "data/series_all.json"
json.dump(V, open(os.path.join(out, "data", "variables.json"), "w"), separators=(",", ":"))
series = {i: json.load(open(os.path.join(DOCS, "data", "series", i + ".json"))) for i in sorted(var_ids)
          if os.path.exists(os.path.join(DOCS, "data", "series", i + ".json"))}
json.dump(series, open(os.path.join(out, "data", "series_all.json"), "w"), separators=(",", ":"))
T = json.load(open(os.path.join(DOCS, "data", "trends.json")))
json.dump({k: v for k, v in T.items() if k in var_ids}, open(os.path.join(out, "data", "trends.json"), "w"), separators=(",", ":"))

layers = json.load(open(os.path.join(DOCS, "data", "layers.json")))
layers["points"] = [p for p in layers["points"] if p["key"] in point_keys]
for p in layers["points"]:
    shutil.copy(os.path.join(DOCS, p["file"]), os.path.join(out, "data"))
layers["rasters"] = [r for r in layers["rasters"] if r["key"] in raster_keys]
for r in layers["rasters"]:
    r["packed"] = True
    by_year = {}
    for png in sorted(glob.glob(os.path.join(DOCS, "rasters", r["key"], "*.png"))):
        d = os.path.basename(png)[:-4]
        by_year.setdefault(d[:4], {})[d] = "data:image/png;base64," + base64.b64encode(open(png, "rb").read()).decode()
    os.makedirs(os.path.join(out, "rasters", r["key"]), exist_ok=True)
    for y, m in by_year.items():
        json.dump(m, open(os.path.join(out, "rasters", r["key"], f"{y}.json"), "w"))
json.dump(layers, open(os.path.join(out, "data", "layers.json"), "w"), separators=(",", ":"))
n = sum(len(fs) for _, _, fs in os.walk(out))
size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(out) for f in fs)
print(f"{out}: {n} files, {size / 1e6:.1f} MB, {len(series)} series, {len(layers['rasters'])} rasters, {len(layers['points'])} point layers")
