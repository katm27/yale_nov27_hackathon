"""Pack docs/ into a low-file-count copy for hosting where file counts are limited
(e.g. a claude.ai artifact). Series -> one JSON; raster PNGs -> per-layer-per-year JSON of data URIs.
Usage: python scripts/pack_for_artifact.py OUT_DIR"""
import base64, glob, json, os, shutil, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
out = sys.argv[1]
shutil.rmtree(out, ignore_errors=True)
os.makedirs(os.path.join(out, "data"))
for f in ["index.html", "app.js", "style.css"]:
    shutil.copy(os.path.join(DOCS, f), out)
# Inline Leaflet CSS (hosts with a strict CSP block third-party stylesheets).
import urllib.request
LEAFLET_CSS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"
css = urllib.request.urlopen(LEAFLET_CSS).read().decode()
with open(os.path.join(out, "style.css")) as fh:
    own = fh.read()
# Leaflet's CSS references images (layer-control icon etc.); inline them as data URIs.
import re
for img in set(re.findall(r"url\((images/[^)]+)\)", css)):
    data = urllib.request.urlopen("https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/" + img).read()
    mime = "image/svg+xml" if img.endswith(".svg") else "image/png"
    css = css.replace("url(%s)" % img, "url(data:%s;base64,%s)" % (mime, base64.b64encode(data).decode()))
open(os.path.join(out, "style.css"), "w").write(css + "\n" + own)
html = open(os.path.join(out, "index.html")).read()
html = html.replace('<link rel="stylesheet" href="%s">\n' % LEAFLET_CSS, "")
open(os.path.join(out, "index.html"), "w").write(html)
for f in glob.glob(os.path.join(DOCS, "data", "*.*")):
    shutil.copy(f, os.path.join(out, "data"))
series = {os.path.basename(f)[:-5]: json.load(open(f)) for f in glob.glob(os.path.join(DOCS, "data", "series", "*.json"))}
json.dump(series, open(os.path.join(out, "data", "series_all.json"), "w"), separators=(",", ":"))
layers = json.load(open(os.path.join(out, "data", "layers.json")))
for r in layers["rasters"]:
    r["packed"] = True
    by_year = {}
    for png in sorted(glob.glob(os.path.join(DOCS, "rasters", r["key"], "*.png"))):
        d = os.path.basename(png)[:-4]
        by_year.setdefault(d[:4], {})[d] = "data:image/png;base64," + base64.b64encode(open(png, "rb").read()).decode()
    os.makedirs(os.path.join(out, "rasters", r["key"]), exist_ok=True)
    for y, m in by_year.items():
        json.dump(m, open(os.path.join(out, "rasters", r["key"], f"{y}.json"), "w"))
json.dump(layers, open(os.path.join(out, "data", "layers.json"), "w"))
v = json.load(open(os.path.join(out, "data", "variables.json")))
v["bundle"] = "data/series_all.json"
json.dump(v, open(os.path.join(out, "data", "variables.json"), "w"))
