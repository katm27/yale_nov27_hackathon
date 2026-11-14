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
DEFAULT_CARRY = {"monthly": 0, "periodic": 6, "round": 6, "annual": 11, "static": 95}


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
        g = g.groupby(["county_id", "period"])["value"].mean().reset_index()
        first_year = int(g["period"].min().year)
        last = g["period"].max()
        if temporal == "static":
            # One value per county regardless of date.
            g = g.groupby("county_id")["value"].mean().reset_index()
            g["period"] = MONTHS[0]
        mat = (g.pivot(index="county_id", columns="period", values="value")
                 .reindex(index=county_ids, columns=MONTHS))
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
    with open(os.path.join(OUT, "layers.json"), "w") as fh:
        json.dump({"points": points, "rasters": rasters}, fh, indent=1)

    print(f"{len(variables)} variables, {len(points)} vector layers, {len(rasters)} raster layers")
    for v in variables:
        print(f"  {v['id']:<32} {v['category']:<12} {v['first_period']}..{v['last_period']} "
              f"counties={v['counties_with_data']} base={v['baseline_year']}")


if __name__ == "__main__":
    main()
