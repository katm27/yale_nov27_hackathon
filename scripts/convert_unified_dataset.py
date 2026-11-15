"""Convert the team's South Sudan unified county-month dataset (data/raw/ssd_unified/ssd_unified_dataset.zip)
into the project contract format.

Outputs:
  data/processed/unified_county_monthly.csv   county rows + national rows (county_id "SS")
  data/processed/meta/unified.json
  docs/data/points_fmr_monitoring.geojson     Flow Monitoring points
  data/processed/flows/fmr_flows_county_to_county.csv  (copied for future flow-arrow layer)
The app grid is 2018-01..2025-12; 2026 rows stay in the raw zip.
"""
import io, json, os, zipfile
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIP = os.path.join(ROOT, "data", "raw", "ssd_unified", "ssd_unified_dataset.zip")
z = zipfile.ZipFile(ZIP)
name = lambda suffix: next(n for n in z.namelist() if n.endswith(suffix))
read = lambda suffix, **kw: pd.read_csv(io.BytesIO(z.read(name(suffix))), **kw)

long = read("ssd_unified_long_2018-01_2026-09.csv", dtype={"county_pcode": str, "month": str})
dic = read("variables_dictionary.csv")

# Dates: monthly -> YYYY-MM-01; annual rows (blank month) -> YYYY-07-01.
long["date"] = long["month"].where(long["month"].notna(), long["year"].astype(str) + "-07")
long["date"] = long["date"].str.slice(0, 7) + "-01"
long = long[(long["date"] >= "2018-01-01") & (long["date"] <= "2025-12-01")]
out = long.rename(columns={"county_pcode": "county_id"})[["county_id", "date", "variable", "value"]].dropna(subset=["value"])
out.to_csv(os.path.join(ROOT, "data", "processed", "unified_county_monthly.csv"), index=False)

def label(v):
    s = v
    for a, b in [("et_ind_", "ET people: "), ("et_events", "ET events"), ("fmr_", "FMR "), ("fts_", "FTS "), ("hrp_", "HRP "),
                 ("us_aid_", "US aid "), ("usaid_", "USAID "), ("state_dept_", "State Dept "), ("unmiss_", "UNMISS ")]:
        if s.startswith(a):
            s = b + s[len(a):]
            break
    return s.replace("_", " ").replace(" usd", " (USD)").strip()

def group(v, level):
    if v.startswith("et_"): return "Displacement – Event Tracking (IOM)"
    if v.startswith("fmr_"): return "Displacement – Flow Monitoring (IOM)"
    if v.startswith(("fts_", "hrp_", "us_aid", "usaid", "state_dept")): return "Aid funding (national)"
    if v.startswith("unmiss"): return "Peacekeeping" + (" (national)" if level == "national" else "")
    if v.startswith("logcluster"): return "Humanitarian logistics"
    if v.startswith("population"): return "Population"
    return "Other"

def higher_is(v):
    if any(k in v for k in ("returnees", "return_relocation")): return "neutral"
    if v.startswith(("et_", "fmr_")) and "monitoring_points" not in v: return "worse"
    if v.startswith(("fts_", "hrp_", "us_aid", "usaid", "state_dept", "logcluster", "unmiss")): return "better"
    return "neutral"

meta = []
for _, r in dic.iterrows():
    v, level = r["variable"], r["spatial_level"]
    if v not in set(out["variable"]):
        continue
    pt = r["period_type"]
    m = {
        "id": v, "label": label(v) + (" — national" if level == "national" else ""),
        "category": "human", "group": group(v, level), "units": r["unit"], "source": r["source"],
        "source_url": "data/raw/ssd_unified/README.md", "native_resolution": "county (admin-2)" if level == "county" else "national",
        "temporal": "annual" if pt == "annual" else "monthly", "aggregation": "as supplied in team unified dataset",
        "higher_is": higher_is(v), "index_ok": True,
        "notes": (f"Team unified dataset (built 14 Nov 2026). Data {r['first_month_with_data']}..{r['last_month_with_data']}; "
                  f"{r['rows_missing']} missing rows.")
                 + (" NATIONAL value shown on every county; it does not vary by county." if level == "national" else "")
                 + (" Blank Nov 2023–Dec 2024 (no public FMR data); counts depend on monitoring-point locations (mostly Renk from 2023)." if v.startswith("fmr_") and level == "county" else "")
                 + (" Calendar/fiscal-year value repeated each month." if pt in ("calendar_year", "un_fiscal_year") else ""),
    }
    if v.startswith("et_"):
        m["baseline_year_override"] = 2020  # Dec 2019 is a single stub month
    if pt in ("calendar_year", "un_fiscal_year"):
        m["temporal"] = "monthly"
    meta.append(m)
json.dump(meta, open(os.path.join(ROOT, "data", "processed", "meta", "unified.json"), "w"), indent=1)

pts = read("fmr/fmr_monitoring_points.csv")
feats = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [float(p["fmp.longitude"]), float(p["fmp.latitude"])]},
          "properties": {"name": p["fmp.name"], "type": "IOM Flow Monitoring point", "county_pcode": p["fmp_county_pcode"],
                         "note": p["location_note"] if isinstance(p["location_note"], str) else "", "source": "IOM DTM FMR (team unified dataset)"}}
         for _, p in pts.dropna(subset=["fmp.latitude", "fmp.longitude"]).iterrows()]
json.dump({"type": "FeatureCollection", "features": feats}, open(os.path.join(ROOT, "docs", "data", "points_fmr_monitoring.geojson"), "w"))
read("fmr/fmr_flows_county_to_county.csv").to_csv(os.path.join(ROOT, "data", "processed", "flows", "fmr_flows_county_to_county.csv"), index=False)

pm = os.path.join(ROOT, "data", "processed", "meta", "points.json")
pl = [p for p in json.load(open(pm)) if p.get("key") != "fmr_monitoring"]
pl.append({"key": "fmr_monitoring", "label": "IOM Flow Monitoring points", "category": "human",
           "source": "IOM DTM South Sudan Flow Monitoring Registry (team unified dataset)", "source_url": "data/raw/ssd_unified/README.md",
           "notes": "Where FMR counts travellers; FMR numbers depend on these locations"})
json.dump(pl, open(pm, "w"), indent=1)
print(len(out), "rows,", out["variable"].nunique(), "variables,", len(meta), "meta,", len(feats), "monitoring points")

if __name__ == "__main__":
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from trend_stats import write_trends
    write_trends("unified")  # Mann-Kendall + Sen's slope (scripts/trend_stats.py)
    # time-dynamic FMR point layer (valid_from/valid_to per active period) overrides the static file written above
    import points_fmr
    points_fmr.main()
