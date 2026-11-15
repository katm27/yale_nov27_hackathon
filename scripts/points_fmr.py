"""IOM DTM Flow Monitoring points over time -> docs/data/points_fmr_monitoring.geojson

Active months per Flow Monitoring Point (FMP) = months with at least one recorded internal forced trip at that point
in the team unified dataset (data/raw/ssd_unified/ssd_unified_dataset.zip: fmr/fmr_internal_forced_2020_2025_filled.csv,
Jan 2020 - Aug 2025; same records behind data/processed/flows/fmr_flows_county_to_county.csv).
Caveats: (1) a point that operated but logged no *forced internal* trip in a month looks inactive that month;
(2) Nov 2023 - Dec 2024 has no public point-level FMR data: these months are treated as unknown and do not break a
period (a point active on both sides is bridged, flagged in date_basis); (3) FMR starts Jan 2020 in this dataset.
A run of more than GAP observed months without records splits a point into separate periods.
Points listed in fmr_monitoring_points.csv without any record keep valid_from/valid_to null and date_basis
'listed, no records 2020-2025'.
"""
import io
import os
import sys
import zipfile

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from points_temporal import ROOT, point, write_fc, set_validity, update_points_meta

ZIP = os.path.join(ROOT, "data", "raw", "ssd_unified", "ssd_unified_dataset.zip")
GAP = 6
UNKNOWN = {p.strftime("%Y-%m") for p in pd.period_range("2023-11", "2024-12", freq="M")}
LAST = "2025-08"


def main():
    z = zipfile.ZipFile(ZIP)
    pts = pd.read_csv(io.BytesIO(z.read("fmr/fmr_monitoring_points.csv")))
    rec = pd.read_csv(io.BytesIO(z.read("fmr/fmr_internal_forced_2020_2025_filled.csv")), low_memory=False)
    act = rec.groupby("fmp.name").observation_month.agg(lambda s: sorted(set(s)))
    ind = rec.groupby(["fmp.name", "observation_month"])["total.ind"].sum()
    months = [p.strftime("%Y-%m") for p in pd.period_range("2020-01", LAST, freq="M")]
    feats = []
    for r in pts.itertuples(index=False):
        name = r[0]
        lat, lon, cid, note = r[1], r[2], r[3], r[4]
        base = dict(name=name, type="IOM Flow Monitoring point")
        common = dict(county_id=cid, county_pcode=cid, note=note if isinstance(note, str) else "",
                      source="IOM DTM FMR (team unified dataset)")
        if name not in act.index:
            props = set_validity(dict(base), None, None, "listed, no forced-movement records 2020-2025 (dates unknown)")
            props.update(common, active_months=0)
            feats.append(point(lon, lat, props))
            continue
        a = set(act[name])
        runs, cur, miss, bridged = [], None, 0, False
        for m in months:
            if m in a:
                if cur is None:
                    cur = [m, m, False]
                else:
                    cur[1] = m
                    cur[2] = cur[2] or bridged
                miss, bridged = 0, False
            elif m in UNKNOWN:
                bridged = cur is not None
            elif cur is not None:
                miss += 1
                if miss > GAP:
                    runs.append(cur)
                    cur, miss, bridged = None, 0, False
        if cur:
            runs.append(cur)
        for f, t, br in runs:
            n = sum(1 for m in a if f <= m <= t)
            basis = "IOM FMR months with recorded forced trips (first..last)"
            if br:
                basis += "; bridged over Nov 2023-Dec 2024 (no public FMR data)"
            vt = None if t == LAST else t
            if t == LAST:
                basis += "; open-ended: data end Aug 2025"
            props = set_validity(dict(base), f, vt, basis)
            props.update(common, first_month=f, last_month=t, active_months=n,
                         travellers=int(sum(ind.get((name, m), 0) for m in a if f <= m <= t)))
            feats.append(point(lon, lat, props))
    write_fc("points_fmr_monitoring.geojson", feats)
    print(len(feats), "features for", len(pts), "points")
    update_points_meta({
        "key": "fmr_monitoring", "label": "IOM Flow Monitoring points (active months)", "category": "human",
        "source": "IOM DTM South Sudan Flow Monitoring Registry (team unified dataset)",
        "source_url": "data/raw/ssd_unified/README.md",
        "notes": ("Where FMR counts travellers; FMR numbers depend on these locations. Temporal: valid_from/valid_to = "
                  "first/last month with recorded internal forced trips (Jan 2020-Aug 2025); >6 empty months split a "
                  "point into periods; Nov 2023-Dec 2024 (no public data) is bridged. Points still active in Aug 2025 "
                  "are open-ended. active_months / travellers summarise each period.")})


if __name__ == "__main__":
    main()
