"""Shared helpers for the human/conflict pipelines (ACLED, UCDP, DTM, WFP, IPC, HAPI).

All outputs follow data/DATA_CONTRACT.md:
  data/processed/<source>_county_monthly.csv  (county_id,date,variable,value)
  data/processed/meta/<source>.json
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
PROC = DATA / "processed"
META = PROC / "meta"
DOCS_DATA = ROOT / "docs" / "data"
COUNTIES = DATA / "counties.geojson"

START, END = "2018-01-01", "2025-12-01"
MONTHS = pd.date_range(START, END, freq="MS")

# DTM / some OCHA products code the Abyei Administrative Area as SS1101; our boundary file uses SS0001
PCODE_ALIASES = {"SS1101": "SS0001", "SS11": "SS00", "SS0807": "SS0001"}  # SS0807 = Abyei in HNO 2023


def load_counties():
    import geopandas as gpd
    g = gpd.read_file(COUNTIES)
    return g


def county_ids() -> list[str]:
    return sorted(load_counties()["district_id"].tolist())


def norm_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def fix_pcode(p):
    if p is None or (isinstance(p, float) and pd.isna(p)):
        return None
    p = str(p).strip().upper()
    return PCODE_ALIASES.get(p, p)


def download(url: str, dest: Path, overwrite: bool = False, timeout: int = 300) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0 and not overwrite:
        return dest
    r = requests.get(url, timeout=timeout, stream=True)
    r.raise_for_status()
    tmp = dest.with_suffix(dest.suffix + ".part")
    with open(tmp, "wb") as f:
        for chunk in r.iter_content(1 << 20):
            f.write(chunk)
    os.replace(tmp, dest)
    return dest


def hdx_resources(package: str) -> list[dict]:
    r = requests.get("https://data.humdata.org/api/3/action/package_show", params={"id": package}, timeout=60)
    r.raise_for_status()
    return r.json()["result"]["resources"]


def month_start(s) -> pd.Series:
    d = pd.to_datetime(s, errors="coerce")
    return d.dt.to_period("M").dt.to_timestamp()


def finalize(df: pd.DataFrame, source: str, meta: list[dict], valid_ids=None) -> pd.DataFrame:
    """Validate + write long CSV and meta JSON. df: county_id,date,variable,value."""
    valid_ids = set(valid_ids or county_ids())
    df = df[["county_id", "date", "variable", "value"]].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df[(df.date >= START) & (df.date <= END)]
    bad = set(df.county_id) - valid_ids
    if bad:
        print(f"[{source}] dropping unknown county ids: {sorted(bad)}")
        df = df[df.county_id.isin(valid_ids)]
    df = df.dropna(subset=["value"])
    dup = df.duplicated(["county_id", "date", "variable"])
    assert not dup.any(), f"duplicate rows in {source}: {df[dup].head()}"
    ids = {m["id"] for m in meta}
    missing = set(df.variable) - ids
    assert not missing, f"variables without meta: {missing}"
    meta = [m for m in meta if m["id"] in set(df.variable)]
    df = df.sort_values(["variable", "county_id", "date"])
    df["date"] = df.date.dt.strftime("%Y-%m-%d")
    PROC.mkdir(parents=True, exist_ok=True)
    META.mkdir(parents=True, exist_ok=True)
    df.to_csv(PROC / f"{source}_county_monthly.csv", index=False, float_format="%.6g")
    with open(META / f"{source}.json", "w") as f:
        json.dump(meta, f, indent=1, ensure_ascii=False)
    # coverage summary
    cov = df.groupby("variable").agg(n=("value", "size"), counties=("county_id", "nunique"),
                                     first=("date", "min"), last=("date", "max"),
                                     months=("date", "nunique"))
    print(f"[{source}] wrote {len(df)} rows")
    print(cov.to_string())
    return df


def zero_fill(df: pd.DataFrame, variables: list[str], ids: list[str], months=MONTHS) -> pd.DataFrame:
    """Complete county x month grid for count variables with true zeros."""
    idx = pd.MultiIndex.from_product([ids, months, variables], names=["county_id", "date", "variable"])
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    s = df.groupby(["county_id", "date", "variable"])["value"].sum()
    s = s.reindex(idx, fill_value=0.0)
    return s.reset_index()


def upsert_points_meta(entry: dict):
    p = META / "points.json"
    items = []
    if p.exists():
        try:
            items = json.loads(p.read_text())
        except Exception:
            items = []
    items = [i for i in items if i.get("key") != entry["key"]] + [entry]
    p.write_text(json.dumps(items, indent=1, ensure_ascii=False))


def base_meta(**kw) -> dict:
    m = {"category": "human", "temporal": "monthly", "index_ok": True}
    m.update(kw)
    return m
