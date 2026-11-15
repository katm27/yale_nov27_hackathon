"""Show NASA SMAP root-zone soil moisture instead of TerraClimate soil moisture in the curated app (idempotent)."""
import json, os
p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "data", "curated.json")
c = json.load(open(p))
for v in c["variables"]:
    if v["id"] == "tc_soil":
        v.update(id="smap_sm_rootzone", label="Soil moisture, top 1 m (NASA SMAP)")
r = c["rasters"]
if "tc_soil" in r:
    del r["tc_soil"]
r["smap_sm_rootzone"] = "smap_sm_rootzone"
for b in c["background"]:
    if b["key"] == "soil_moisture":
        b.update(label="Soil moisture, top 1 m (NASA SMAP, monthly grid)", rasters=["smap_sm_rootzone"])
for k in ("national_ids", "spark_ids"):
    if isinstance(c.get(k), list):
        c[k] = ["smap_sm_rootzone" if x == "tc_soil" else x for x in c[k]]
json.dump(c, open(p, "w"), indent=2, ensure_ascii=False)
print("curated.json: soil moisture -> smap_sm_rootzone")
