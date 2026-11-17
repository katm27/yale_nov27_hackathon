"""Trend tests for the national series shown in the "National trends" drawer.

Each national series is built from the county series (the value itself when every county carries the same national
number, otherwise the sum for counts or the mean for shares/levels), then tested with the same function used for
counties (trend_stats.trend_for_series: seasonal Mann-Kendall with Hirsch-Slack correction for monthly data,
Mann-Kendall with Hamed-Rao for longer annual series, plain Mann-Kendall for short annual series). One test per
series, so no false-discovery adjustment is applied. Output: docs/data/national_trends.json
Usage: python scripts/national_trends.py
"""
import json, os, sys
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from trend_stats import trend_for_series  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "docs", "data")
# series added to the drawer beyond curated national_ids: id -> how to aggregate the 79 counties
EXTRA = {"gldas_gws_anom_cm": "mean", "sudd_inundation_km2": "sum", "precip_mm": "mean", "et_ind_flooding": "sum",
         "acled_civ_fatalities": "sum", "ipc_phase3plus_pct": "mean"}
YEARLY = ("_year", "_fy_", "wps_", "budget")

def national(s, how):
    cs = list(s)
    A = np.array([[np.nan if v is None else v for v in s[c]] for c in cs], float)
    same = all(np.allclose(np.nan_to_num(A[0]), np.nan_to_num(r)) for r in A[1:]) if len(cs) > 1 else True
    if same or how == "national":
        return A[0]
    with np.errstate(all="ignore"):
        tot = np.nansum(A, 0); tot[np.all(np.isnan(A), 0)] = np.nan
        return tot if how == "sum" else np.nanmean(A, 0)

def main():
    months = json.load(open(os.path.join(D, "variables.json")))["months"]
    cur = json.load(open(os.path.join(D, "curated.json")))
    ids = {i: "national" for i in cur["national_ids"]} | EXTRA
    out = {}
    for vid, how in ids.items():
        p = os.path.join(D, "series", f"{vid}.json")
        if not os.path.exists(p):
            continue
        x = national(json.load(open(p)), how)
        dates = pd.to_datetime(pd.Series(months) + "-01")
        ok = np.isfinite(x)
        yearly = any(k in vid for k in YEARLY)
        if yearly:   # one value per year (the series repeats the yearly figure every month)
            df = pd.DataFrame({"d": dates[ok], "x": x[ok]}); df = df.groupby(df.d.dt.year).last()
            r = trend_for_series(df["d"], df["x"], temporal="annual", var=vid)
        else:
            r = trend_for_series(dates[ok], pd.Series(x[ok]), temporal="monthly", var=vid)
        pv = r.get("p")
        out[vid] = {"how": how, "p": None if pv is None or not np.isfinite(pv) else round(float(pv), 4),
                    "significant": bool(pv is not None and np.isfinite(pv) and pv < 0.05),
                    "slope": None if not np.isfinite(r.get("display_slope", np.nan)) else float(r["display_slope"]),
                    "test": r.get("test", r.get("method", ""))}
        print(f"{vid:34s} {how:8s} p={out[vid]['p']} sig={out[vid]['significant']}")
    json.dump(out, open(os.path.join(D, "national_trends.json"), "w"), indent=1)

if __name__ == "__main__":
    main()
