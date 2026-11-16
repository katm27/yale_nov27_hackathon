"""Ground-subsidence rates measured with Sentinel-1 InSAR at oil fields near South Sudan (literature values).

No open InSAR velocity product covers South Sudan for 2018-2025 (checked: EGMS, OPERA, LiCSAR/COMET, GEE catalog,
global ML subsidence maps, NISAR (from mid-2026 only), GNSS stations). The only measured rates are from
Gido et al. 2020, Remote Sensing 12(11):1792, doi:10.3390/rs12111792: Sentinel-1 persistent-scatterer InSAR,
Nov 2015 - Apr 2019. Neem (-23.8 mm/yr) is not mapped because its location could not be verified.
Locations: Heglig and Diffra from OpenStreetMap place nodes; Unity from the repo's oil-field layer (points_oil).
Usage: python scripts/subsidence_literature.py
"""
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = "https://doi.org/10.3390/rs12111792"
SITES = [  # name, lon, lat, rate mm/yr, +-, country, location basis
    ("Heglig oil field", 29.3856, 10.0256, -24.5, 0.85, "Sudan (West Kordofan, on the border)", "Heglig town, OpenStreetMap"),
    ("Diffra oil field", 28.4003, 10.0390, -14.2, 0.85, "Abyei Area (disputed between Sudan and South Sudan)", "Diffra, OpenStreetMap"),
    ("Unity oil field area", 29.6764, 9.4699, -6.0, 0.88, "South Sudan (Unity State)", "Unity Oil Field, points_oil layer"),
]
feats = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
          "properties": {"name": n, "Ground sinking (mm per year)": f"{r} ± {e}", "Measured": "November 2015 to April 2019",
                         "Method": "Sentinel-1 radar interferometry (persistent scatterers)", "Where": c,
                         "Location": f"approximate field centre ({basis})",
                         "Source": "Gido et al. 2020, Remote Sensing 12(11):1792", "source_url": SRC}}
         for n, lon, lat, r, e, c, basis in SITES]
json.dump({"type": "FeatureCollection", "features": feats}, open(os.path.join(ROOT, "docs", "data", "points_subsidence_insar.geojson"), "w"), indent=1, ensure_ascii=False)
p = os.path.join(ROOT, "data", "points_labels.json")
L = json.load(open(p))
L["points_subsidence_insar"] = {
    "label": "Ground sinking at oil fields (radar study, 2015–2019)",
    "plain": "Ground at three oil fields sank by 6 to 25 mm a year between 2015 and 2019, measured from Sentinel-1 radar by Gido et al. (2020), a likely sign of oil and water being pumped out of the ground; no open radar measurements of this kind exist for 2018–2025 or for Juba.",
    "topic": "Context (static)"}
json.dump(L, open(p, "w"), indent=1, ensure_ascii=False)
print("wrote", len(feats), "sites")
