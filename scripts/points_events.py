"""Event layers keep their single `date`; this verifies it and adds valid_from = valid_to = YYYY-MM(date)
plus date_basis, so the app can filter every layer the same way. The ethnic-group polygons are rebuilt by
scripts/ethnic_groups_temporal.py (EPR-2023 status per year). Re-runnable.
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
    import team_dynamic_layers as tdl  # EPR-2023 status per year (scripts/ethnic_groups_temporal.py)
    tdl.ethnic()


if __name__ == "__main__":
    main()
