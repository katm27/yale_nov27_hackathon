"""Build the web app's data bundle from data/processed/.

Reads every long-format CSV in data/processed/ (county_id, date, variable, value)
plus the metadata JSON lists in data/processed/meta/, aligns everything to the
monthly grid 2018-01 .. 2025-12 for the 79 counties, and writes:

  docs/data/counties.geojson      simplified county polygons
  docs/data/variables.json        metadata + coverage for every variable
  docs/data/series/<var>.json     {"county_id": [96 raw values or null], ...}
  docs/data/points.json           list of point layers available

Indexing (value / 2018 baseline) is done in the browser so the user can switch
baseline mode. This script records which year serves as the baseline (2018, or
the first year with data when the source starts later) for transparency.

Usage: python scripts/build_web_data.py
"""
from __future__ import annotations

import glob
import json
import re
import math
import os

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(ROOT, "data", "processed")
OUT = os.path.join(ROOT, "docs", "data")
MONTHS = pd.period_range("2018-01", "2025-12", freq="M")
MONTH_STR = [str(m) for m in MONTHS]
NATIONAL_IDS = {"SS", "SSD", "national"}
# Sparse "round"-type series are carried forward this many months so the slider
# shows the latest known value (flagged in metadata as carried forward).
DEFAULT_CARRY = {"monthly": 0, "periodic": 8, "round": 8, "annual": 0, "static": 95}


def sig(x: float, n: int = 4):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    if x == 0:
        return 0
    return float(f"{x:.{n}g}")


def load_meta() -> dict:
    meta = {}
    for f in sorted(glob.glob(os.path.join(PROC, "meta", "*.json"))):
        if os.path.basename(f) == "points.json":
            continue
        try:
            items = json.load(open(f))
        except Exception as e:  # noqa: BLE001
            print("! bad meta", f, e)
            continue
        if isinstance(items, dict):
            items = items.get("variables", [items])
        for it in items:
            if "id" in it:
                it.setdefault("meta_file", os.path.basename(f))
                meta[it["id"]] = it
    return meta


def load_values(county_ids: list[str]) -> pd.DataFrame:
    frames = []
    for f in sorted(glob.glob(os.path.join(PROC, "*.csv"))):
        try:
            df = pd.read_csv(f, dtype={"county_id": str})
        except Exception as e:  # noqa: BLE001
            print("! unreadable", f, e)
            continue
        if not {"county_id", "date", "variable", "value"} <= set(df.columns):
            print("  (skip, not long format)", os.path.basename(f))
            continue
        df = df[["county_id", "date", "variable", "value"]].copy()
        df["file"] = os.path.basename(f)
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])
    # Broadcast national-only rows to every county.
    nat = df[df["county_id"].isin(NATIONAL_IDS)]
    if len(nat):
        rep = pd.concat([nat.assign(county_id=c) for c in county_ids], ignore_index=True)
        df = pd.concat([df[~df["county_id"].isin(NATIONAL_IDS)], rep], ignore_index=True)
    df["period"] = pd.to_datetime(df["date"], errors="coerce").dt.to_period("M")
    return df.dropna(subset=["period"])


# --------------------------------------------------------------------------- trends (Mann-Kendall / Sen)
def build_trends(variables: list[dict], county_ids: list[str]) -> None:
    """Merge data/processed/trends/*_trends.csv (written by scripts/trend_stats.py) into docs/data/trends.json.

    Per variable and county: [0 p, 1 q_fdr, 2 sen_slope_per_year, 3 sen_slope_pct_per_year, 4 tau, 5 n, 6 significant,
    7 test, 8 sentence, 9 lisa, 10 p_naive, 11 [trend to date 2020..2025], 12 basis, 13 sen_lo, 14 sen_hi (90% range of
    the headline slope), 15 pw_lost (1 = significance does not survive trend-free pre-whitening), 16 Pettitt break
    "YYYY-MM" (p < 0.05, else null), 17 step_like (1 = change looks like a step at that break rather than a drift)]
    National series (county_id "SS") are applied to every county.
    """
    def _flag(v):
        try:
            return None if v is None or not math.isfinite(float(v)) else int(bool(v))
        except (TypeError, ValueError):
            return None

    frames = [pd.read_csv(f, dtype={"county_id": str}) for f in sorted(glob.glob(os.path.join(ROOT, "data", "processed", "trends", "*_trends.csv")))]
    if not frames:
        return
    t = pd.concat(frames, ignore_index=True)
    nat = t[t["county_id"].isin(NATIONAL_IDS)]
    if len(nat):
        t = pd.concat([t[~t["county_id"].isin(NATIONAL_IDS)]] + [nat.assign(county_id=c) for c in county_ids], ignore_index=True)
    shown = {v["id"] for v in variables}
    natonly = {v["id"] for v in variables if v.get("national_only")}
    t = t[t["variable"].isin(shown - natonly) & t["test"].notna()]
    out = {}
    for var, g in t.groupby("variable"):
        out[var] = {r.county_id: [sig(r.p, 3), sig(r.q_fdr, 3), sig(r.sen_slope_per_year), sig(r.sen_slope_pct_per_year, 3),
                                  sig(r.tau, 3), int(r.n), int(bool(r.significant)),
                                  "S" if str(r.test).startswith("seasonal") else "M", r.interpretation,
                                  getattr(r, "lisa", "ns") if isinstance(getattr(r, "lisa", None), str) else "ns",
                                  sig(getattr(r, "p_naive", float("nan")), 3),
                                  [sig(getattr(r, f"todate_{Y}", float("nan")), 3) for Y in range(2020, 2026)],
                                  getattr(r, "basis", "") if isinstance(getattr(r, "basis", None), str) else "",
                                  sig(getattr(r, "sen_lo", float("nan"))), sig(getattr(r, "sen_hi", float("nan"))),
                                  _flag(getattr(r, "pw_lost", float("nan"))),
                                  r.cp_date if isinstance(getattr(r, "cp_date", None), str) and getattr(r, "cp_p", 1) < 0.05 else None,
                                  _flag(getattr(r, "step_like", 0)) or 0]
                    for r in g.drop_duplicates("county_id", keep="last").itertuples()}
    # spatial + regional statistics into variable metadata
    byid = {v["id"]: v for v in variables}
    if "direction" in t:
        for var, g in t.groupby("variable"):
            if var in byid and not byid[var].get("direction"):
                byid[var]["direction"] = str(g["direction"].dropna().iloc[0]) if g["direction"].notna().any() else "more_less"
            if var in byid and "basis" in g and g["basis"].notna().any():
                byid[var]["trend_basis"] = str(g["basis"].dropna().iloc[0])
    for var, g in t.groupby("variable"):
        if var in byid and "moran_I" in g and g["moran_I"].notna().any():
            byid[var]["trend_moran_I"] = sig(float(g["moran_I"].dropna().iloc[0]), 3)
            byid[var]["trend_moran_p"] = sig(float(g["moran_p"].dropna().iloc[0]), 3)
    regf = [f for f in glob.glob(os.path.join(ROOT, "data", "processed", "trends", "*_regional.csv")) if os.path.getsize(f) > 5]
    if regf:
        reg = pd.concat([pd.read_csv(f) for f in regf], ignore_index=True).dropna(subset=["S"])
        reg = reg.sort_values("n_counties").drop_duplicates(["variable", "region"], keep="last")
        for r in reg.itertuples():
            if r.variable in byid:
                byid[r.variable].setdefault("regional", {})[r.region] = {
                    "S": sig(r.S), "p": sig(r.p_boot, 3), "n": int(r.n_counties),
                    "median_pct": sig(r.median_sen_pct_per_year, 3), "median_slope": sig(r.median_sen_per_year, 3)}
    with open(os.path.join(OUT, "trends.json"), "w") as fh:
        json.dump(out, fh, separators=(",", ":"))
    n_sig = int(t["significant"].sum())
    print(f"trends: {len(t)} county-variables for {len(out)} variables, {n_sig} significant (FDR q<0.05)")


# --------------------------------------------------------------------------- migration flows
REASONS = ["conflict", "disaster", "food", "sudan_conflict", "return_relocation", "other", "unknown"]
# Fallback entry points ON the border (used only if data/crosswalks/border_crossings.csv is missing).
FOREIGN_NODES = {
    "SDN": ("Sudan (Joda–Renk crossing, approx.)", 12.15, 32.85), "ETH": ("Ethiopia (Pagak crossing, approx.)", 8.40, 33.95),
    "UGA": ("Uganda (Nimule crossing, approx.)", 3.60, 32.06), "KEN": ("Kenya (Nadapal crossing, approx.)", 4.40, 34.25),
    "CAF": ("Central African Rep. (border, approx.)", 5.05, 27.45), "COD": ("DR Congo (Kaya crossing, approx.)", 3.52, 30.90),
}


def border_crossings():
    """Verified crossing points per country -> list of (node_id, label, lat, lon)."""
    path = os.path.join(ROOT, "data", "crosswalks", "border_crossings.csv")
    out = {}
    if os.path.exists(path):
        bc = pd.read_csv(path)
        iso = next(c for c in bc.columns if "iso" in c.lower() or c.lower() == "country")
        name = next(c for c in bc.columns if "name" in c.lower())
        for r in bc.itertuples():
            c = str(getattr(r, iso)).strip().upper()[:3]
            out.setdefault(c, []).append((f"{c}@{getattr(r, name)}", f"{getattr(r, name)} crossing (from {c})", float(r.lat), float(r.lon)))
    for c, (lab, la, lo) in FOREIGN_NODES.items():
        out.setdefault(c, [(c, lab, la, lo)])
    return out


def build_flows(counties) -> None:
    """Combine origin->destination flow tables into docs/data/flows.json for the arrow layer."""
    fdir = os.path.join(ROOT, "data", "processed", "flows")
    src_files = {
        "et": ("IOM DTM Event Tracking (people displaced/returning, by origin county)", os.path.join(fdir, "et_flows.csv")),
        "fmr": ("IOM DTM Flow Monitoring (internal forced travel observed at monitoring points)", os.path.join(fdir, "fmr_flows_county_to_county.csv")),
        "dtm_mt_idp_od": ("IOM DTM Mobility Tracking: IDP stock by county of origin (survey round, carried to next round)", os.path.join(fdir, "dtm_mt_idp_od_flows.csv")),
        "dtm_mt_returnee_od": ("IOM DTM Mobility Tracking: returnee stock by county returned from (survey round, carried to next round)", os.path.join(fdir, "dtm_mt_returnee_od_flows.csv")),
        "dtm_renk_intentions": ("IOM DTM Renk transit-centre intention survey (intended destination, sample)", os.path.join(fdir, "dtm_renk_intentions_flows.csv")),
    }
    # Stock-type sources (survey rounds) are carried forward until the next round (max 24 months), flagged in the app.
    CARRY = {"dtm_mt_idp_od": 24, "dtm_mt_returnee_od": 24}
    for f in sorted(glob.glob(os.path.join(fdir, "*_flows.csv"))):
        key = os.path.basename(f)[:-10]
        if key not in src_files:
            src_files[key] = (key.replace("_", " "), f)
    # County anchors: centroid if it lies inside the polygon, otherwise a guaranteed interior point.
    nodes = {}
    for r in counties.itertuples():
        from shapely.geometry import Point
        pt = Point(r.lon, r.lat)
        if not r.geometry.contains(pt):
            pt = r.geometry.representative_point()
        nodes[r.district_id] = [round(pt.y, 3), round(pt.x, 3), r.name]
    crossings = border_crossings()
    for c, lst in crossings.items():
        for nid, lab, la, lo in lst:
            nodes[nid] = [round(la, 3), round(lo, 3), lab]
    # foreign origin -> nearest crossing of that country to the destination county
    def nearest_crossing(country, to):
        lst = crossings.get(country)
        if not lst or to not in nodes:
            return country
        la, lo = nodes[to][0], nodes[to][1]
        return min(lst, key=lambda x: (x[2] - la) ** 2 + (x[3] - lo) ** 2)[0]
    node_ids = list(nodes)
    nidx = {k: i for i, k in enumerate(node_ids)}
    sources, months = [], {}
    for key, (label, path) in src_files.items():
        if not os.path.exists(path):
            continue
        d = pd.read_csv(path, dtype=str)
        d["individuals"] = pd.to_numeric(d["individuals"], errors="coerce")
        foreign = d["from_pcode"].isin(list(crossings))
        d.loc[foreign, "from_pcode"] = [nearest_crossing(c, t) for c, t in zip(d.loc[foreign, "from_pcode"], d.loc[foreign, "to_pcode"])]
        d = d[(d["from_pcode"] != d["to_pcode"]) & d["from_pcode"].isin(nidx) & d["to_pcode"].isin(nidx) & (d["individuals"] > 0)]
        d = d[(d["month"] >= MONTH_STR[0]) & (d["month"] <= MONTH_STR[-1])]
        d["reason"] = d["reason"].replace({"return": "return_relocation", "returnee": "return_relocation", "unknown": "other"})
        d["reason"] = d["reason"].where(d["reason"].isin(REASONS), "other")
        observed = sorted(d["month"].unique().tolist())
        if key in CARRY and observed:
            # copy each round to the following months until the next round (or CARRY months)
            grid = [m for m in MONTH_STR if m >= observed[0]]
            src_of = {}
            for m in grid:
                latest = max(o for o in observed if o <= m)
                ago = (int(m[:4]) - int(latest[:4])) * 12 + int(m[5:]) - int(latest[5:])
                if ago <= CARRY[key]:
                    src_of[m] = latest
            parts = [d[d["month"] == r].assign(month=m) for m, r in src_of.items()]
            d = pd.concat(parts, ignore_index=True) if parts else d
        g = d.groupby(["month", "from_pcode", "to_pcode", "reason"])["individuals"].sum().reset_index()
        si = len(sources)
        sources.append({"key": key, "label": label, "months": sorted(g["month"].unique().tolist()), "observed": observed,
                        "kind": "stock" if key in CARRY else ("survey" if "intention" in key else "flow"),
                        "max": float(g["individuals"].max()) if len(g) else 1})
        for r in g.itertuples():
            months.setdefault(r.month, []).append([si, nidx[r.from_pcode], nidx[r.to_pcode], REASONS.index(r.reason), int(round(r.individuals))])
    with open(os.path.join(OUT, "flows.json"), "w") as fh:
        json.dump({"nodes": [nodes[k] + [k] for k in node_ids], "reasons": REASONS, "sources": sources, "months": months},
                  fh, separators=(",", ":"))
    print("flows:", ", ".join(f"{s['key']} {len(s['months'])} months" for s in sources))


LABELS = {}
_lp = os.path.join(ROOT, "data", "variable_labels.json")
if os.path.exists(_lp):
    LABELS = json.load(open(_lp))
POINT_LABELS = {}
_pp = os.path.join(ROOT, "data", "points_labels.json")
if os.path.exists(_pp):
    POINT_LABELS = json.load(open(_pp))


def main() -> None:
    os.makedirs(os.path.join(OUT, "series"), exist_ok=True)
    counties = gpd.read_file(os.path.join(ROOT, "data", "counties.geojson"))
    county_ids = counties["district_id"].tolist()

    simp = counties.copy()
    simp["geometry"] = simp.geometry.simplify(0.004, preserve_topology=True)
    simp[["lat", "lon"]] = simp[["lat", "lon"]].round(4)
    simp.to_file(os.path.join(OUT, "counties.geojson"), driver="GeoJSON", COORDINATE_PRECISION=4)

    meta = load_meta()
    df = load_values(county_ids)
    known = set(county_ids)
    unknown = sorted(set(df["county_id"]) - known)
    if unknown:
        print("! county ids not in boundary file (dropped):", unknown[:20])
    df = df[df["county_id"].isin(known)]

    for old in glob.glob(os.path.join(OUT, "series", "*.json")):
        os.remove(old)

    variables = []
    for var, g in df.groupby("variable"):
        if meta.get(var, {}).get("hidden"):
            continue  # superseded by another source; kept in data/processed for provenance
        m = dict(meta.get(var, {"id": var, "label": var, "category": "other"}))
        m["id"] = var
        if var not in meta:
            print("! no metadata for", var, "from", g["file"].iloc[0])
        temporal = m.get("temporal", "monthly")
        if str(temporal).lower().startswith(("irregular", "round", "periodic")):
            temporal = "periodic"   # survey rounds / analyses (IPC, DTM): carry the latest value forward
        g = g.groupby(["county_id", "period"])["value"].mean().reset_index()
        first_year = int(g["period"].min().year)
        last = g["period"].max()
        if temporal == "static":
            # One value per county regardless of date.
            g = g.groupby("county_id")["value"].mean().reset_index()
            g["period"] = MONTHS[0]
        mat = (g.pivot(index="county_id", columns="period", values="value")
                 .reindex(index=county_ids, columns=MONTHS))
        if temporal == "annual":
            # an annual value describes the whole calendar year: fill every month of that year
            yrs = np.array([p.year for p in MONTHS])
            for y in np.unique(yrs):
                cols = mat.columns[yrs == y]
                mat.loc[:, cols] = np.repeat(mat[cols].mean(axis=1).values[:, None], len(cols), axis=1)
            m["baseline_mode"] = "annual"
        observed = mat.notna().values.copy()
        carry = int(m.get("carry_forward_months", DEFAULT_CARRY.get(temporal, 0)))
        if carry:
            mat = mat.T.ffill(limit=carry).T
        if temporal == "static":
            mat = mat.T.ffill().T

        arr = mat.values.astype(float)
        if np.isnan(arr).all():
            continue
        # Baseline year: 2018, unless the source has no 2018 data -> first year with data.
        years = np.array([p.year for p in MONTHS])
        base_year = 2018
        if temporal != "static" and np.isnan(arr[:, years == 2018]).all():
            have = [y for y in range(2018, 2026) if not np.isnan(arr[:, years == y]).all()]
            base_year = have[0] if have else 2018
        if m.get("baseline_year_override"):
            base_year = int(m["baseline_year_override"])

        series = {cid: [sig(v) for v in row] for cid, row in zip(county_ids, arr)}
        with open(os.path.join(OUT, "series", f"{var}.json"), "w") as fh:
            json.dump(series, fh, separators=(",", ":"))

        finite = arr[np.isfinite(arr)]
        m.update({
            "baseline_year": base_year,
            "first_period": str(g["period"].min()),
            "last_period": str(last),
            "counties_with_data": int(np.isfinite(arr).any(axis=1).sum()),
            "months_observed": int(observed.any(axis=0).sum()),
            "carry_forward_months": carry,
            "p02": sig(float(np.percentile(finite, 2))),
            "p98": sig(float(np.percentile(finite, 98))),
            "min": sig(float(finite.min())),
            "max": sig(float(finite.max())),
        })
        u = str(m.get("units", "")).lower()
        if temporal == "monthly" and re.search(r"\b(events?|people|persons|individuals|deaths|fatalities|incidents|count|movements|travellers|detections|fires)\b", u) and "per" not in u and "%" not in u:
            m["aggregate"] = "sum"
        m.setdefault("index_ok", True)
        m.setdefault("higher_is", "neutral")
        m.setdefault("category", "other")
        m.setdefault("group", "Other")
        # Sparse counts (e.g. conflict events, displacement): most baseline-year county-months are zero, so a
        # ratio is undefined almost everywhere. Show the change from the baseline-year monthly average instead.
        base_vals = arr[:, years == base_year]
        base_vals = base_vals[np.isfinite(base_vals)]
        if (temporal == "monthly" and base_vals.size and (finite >= 0).all()
                and (base_vals == 0).mean() > 0.4 and not m.get("force_ratio")):
            m["index_ok"] = False
            m["baseline_mode"] = "annual"
            m["sparse_count"] = True
        if m["min"] is not None and m["min"] < 0:
            m["index_ok"] = False  # ratio index is meaningless for values that cross zero
        # national-only series (identical in every county) are kept off the county map
        rows_ok = [r for r in arr if np.isfinite(r).any()]
        same = len(rows_ok) > 1 and all(np.array_equal(np.nan_to_num(r, nan=-9e9), np.nan_to_num(rows_ok[0], nan=-9e9)) for r in rows_ok[1:])
        if same and (np.nanstd(rows_ok[0]) > 0 or str(m.get("native_resolution", "")).lower().startswith("national")):
            m["national_only"] = True
        # plain-language labels / definitions / topics (data/variable_labels.json, written by hand + review)
        lab = LABELS.get(var, {})
        for k in ("label", "plain", "method", "how_to_read", "direction", "topic", "caution", "synonyms"):
            if lab.get(k):
                if k == "label":
                    m.setdefault("label_original", m.get("label"))
                m[k] = lab[k]
        variables.append(m)

    order = {"environment": 0, "human": 1, "other": 2}
    variables.sort(key=lambda v: (order.get(v["category"], 3), v.get("group", ""), v.get("label", v["id"])))
    with open(os.path.join(OUT, "variables.json"), "w") as fh:
        json.dump({"months": MONTH_STR, "variables": variables}, fh, indent=1)

    # Point layers + raster overlays
    pts_meta = {}
    pm = os.path.join(PROC, "meta", "points.json")
    if os.path.exists(pm):
        for p in json.load(open(pm)):
            pts_meta[p["key"]] = p
    points = []
    for f in sorted(glob.glob(os.path.join(OUT, "*.geojson"))):
        name = os.path.basename(f)
        if name == "counties.geojson":
            continue
        key = name.replace(".geojson", "")
        for pre in ("points_", "lines_", "polygons_"):
            if key.startswith(pre):
                key_short = key[len(pre):]
                break
        else:
            key_short = key
        info = dict(pts_meta.get(key_short, pts_meta.get(key, {})))
        pl = POINT_LABELS.get(key, POINT_LABELS.get(key_short, {}))
        info.update({k: v for k, v in pl.items() if k in ("label", "plain", "topic") and v})
        info.update({"key": key, "file": f"data/{name}"})
        info.setdefault("label", key_short.replace("_", " ").title())
        info.setdefault("category", "human")
        points.append(info)
    rasters = []
    for f in sorted(glob.glob(os.path.join(ROOT, "docs", "rasters", "*", "meta.json"))):
        try:
            r = json.load(open(f))
            r["key"] = os.path.basename(os.path.dirname(f))
            rasters.append(r)
        except Exception as e:  # noqa: BLE001
            print("! bad raster meta", f, e)
    prof = os.path.join(ROOT, "data", "district_profiles.json")
    if os.path.exists(prof):
        import shutil
        shutil.copy(prof, os.path.join(OUT, "profiles.json"))
    build_trends(variables, county_ids)
    with open(os.path.join(OUT, "variables.json"), "w") as fh:   # rewrite with spatial/regional trend metadata
        json.dump({"months": MONTH_STR, "variables": variables}, fh, indent=1)
    build_flows(counties)
    tp = os.path.join(ROOT, "data", "topic_picks.json")
    if os.path.exists(tp):
        import shutil
        shutil.copy(tp, os.path.join(OUT, "topic_picks.json"))
    with open(os.path.join(OUT, "layers.json"), "w") as fh:
        json.dump({"points": points, "rasters": rasters}, fh, indent=1)

    print(f"{len(variables)} variables, {len(points)} vector layers, {len(rasters)} raster layers")
    for v in variables:
        print(f"  {v['id']:<32} {v['category']:<12} {v['first_period']}..{v['last_period']} "
              f"counties={v['counties_with_data']} base={v['baseline_year']}")


if __name__ == "__main__":
    main()
