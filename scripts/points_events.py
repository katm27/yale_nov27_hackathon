"""Event layers keep their single `date`; this verifies it and adds valid_from = valid_to = YYYY-MM(date)
plus date_basis, so the app can filter every layer the same way. Also stamps the GeoEPR ethnic-group polygons
(year_from / year_to -> valid_from / valid_to). Re-runnable.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from points_temporal import read_fc, write_fc, set_validity, stamp_events, clip_window, tag_meta


def check(name):
    fc = read_fc(name)
    ds = [f["properties"].get("date") for f in fc["features"]]
    bad = [d for d in ds if not d or not ("2018-01-01" <= d[:10] <= "2025-12-31")]
    yr = sum(1 for f in fc["features"] if f["properties"].get("year") and str(f["properties"]["year"]) != f["properties"]["date"][:4])
    return len(ds), len(bad), yr, min(ds), max(ds)


def main():
    for name, basis in [("points_ucdp_events.geojson", "event date (UCDP GED date_start)"),
                        ("points_insecurity_insight.geojson", "event date (Insecurity Insight incident date)")]:
        n, bad = stamp_events(name, basis=basis)
        tag_meta(name.replace("points_", "").replace(".geojson", ""),
                 "Temporal: event layer - single `date`; valid_from = valid_to = its month (date verified 2018-01..2025-12).")
        print(name, "events", n, "unparseable", bad, "check (n, outside 2018-2025, year!=date, min, max):", check(name))
    fc = read_fc("polygons_ethnic_groups.geojson")
    for f in fc["features"]:
        p = f["properties"]
        vf, vt = f"{int(p['year_from'])}-01", f"{int(p['year_to'])}-12"
        cw = clip_window(vf, vt) or (vf, vt)
        end = cw[1]
        note = f"GeoEPR period {p.get('period')} (annual)"
        if p["year_to"] == max(int(g["properties"]["year_to"]) for g in fc["features"]):
            end, note = None, note + "; dataset ends 2021, settlement areas carried to 2025"
        set_validity(p, cw[0], end, note)
    write_fc("polygons_ethnic_groups.geojson", fc["features"])
    print("ethnic polygons", len(fc["features"]))


if __name__ == "__main__":
    main()
