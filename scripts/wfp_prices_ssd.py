"""WFP VAM market prices South Sudan (HDX `wfp-food-prices-for-south-sudan`) -> county-month median prices.

Markets (lat/lon) are spatially joined to counties. Retail prices only, converted to SSP per kg / per litre
(3.5 kg 'malwa' units / 3.5). USD variants use WFP's own `usdprice` column. Exchange rate = WFP-reported
unofficial (parallel) SSP per USD at each market. Also exports docs/data/points_markets.geojson.
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from human_common import RAW, DOCS_DATA, download, hdx_resources, load_counties, finalize, base_meta, upsert_points_meta

SRC = "wfp_prices"
RAWD = RAW / "wfp_prices"
URL = "https://data.humdata.org/dataset/wfp-food-prices-for-south-sudan"
# key -> (commodity name, label, unit label)
COMMODITIES = {
    "sorghum": ("Sorghum (white, imported)", "Sorghum (white, imported)", "kg"),
    "sorghum_local": ("Sorghum (local)", "Sorghum (local)", "kg"),
    "maize": ("Maize (white)", "Maize (white grain)", "kg"),
    "wheat_flour": ("Wheat flour", "Wheat flour", "kg"),
    "beans": ("Beans (red)", "Beans (red)", "kg"),
    "groundnuts": ("Groundnuts (shelled)", "Groundnuts (shelled)", "kg"),
    "cooking_oil": ("Oil (vegetable)", "Cooking oil (vegetable)", "L"),
    "diesel": ("Fuel (diesel)", "Diesel", "L"),
    "petrol": ("Fuel (petrol-gasoline)", "Petrol (gasoline)", "L"),
    "diesel_parallel": ("Fuel (diesel, parallel market)", "Diesel (parallel market)", "L"),
    "petrol_parallel": ("Fuel (petrol-gasoline, parallel market)", "Petrol (parallel market)", "L"),
}
UNIT_DIV = {"KG": 1.0, "3.5 KG": 3.5, "50 KG": 50.0, "L": 1.0}


def main():
    RAWD.mkdir(parents=True, exist_ok=True)
    for r in hdx_resources("wfp-food-prices-for-south-sudan"):
        name = "wfp_markets_ssd.csv" if "markets" in r["url"] else "wfp_food_prices_ssd.csv"
        download(r["url"], RAWD / name, overwrite=True)
    p = pd.read_csv(RAWD / "wfp_food_prices_ssd.csv")
    mk = pd.read_csv(RAWD / "wfp_markets_ssd.csv")
    p = p[~p.date.astype(str).str.startswith("#")]  # drop HXL tag row if present
    mk = mk[~mk.market_id.astype(str).str.startswith("#")]
    for c in ["price", "usdprice", "market_id"]:
        p[c] = pd.to_numeric(p[c], errors="coerce")
    mk["market_id"] = pd.to_numeric(mk.market_id)
    mk = mk[pd.to_numeric(mk.latitude, errors="coerce").notna()].copy()
    mk["latitude"] = mk.latitude.astype(float)
    mk["longitude"] = mk.longitude.astype(float)

    g = load_counties()
    gm = gpd.GeoDataFrame(mk, geometry=gpd.points_from_xy(mk.longitude, mk.latitude), crs="EPSG:4326")
    gm = gpd.sjoin(gm, g[["district_id", "name", "geometry"]], how="left", predicate="within").drop(columns="index_right")
    # markets falling just outside polygons (rounded coords) -> nearest county
    miss = gm.district_id.isna()
    if miss.any():
        near = gpd.sjoin_nearest(gm[miss].drop(columns=["district_id", "name"]).to_crs(32636),
                                 g[["district_id", "name", "geometry"]].to_crs(32636), how="left").to_crs(4326)
        gm.loc[miss, "district_id"] = near.district_id.values
        gm.loc[miss, "name"] = near.name.values
        print("markets assigned by nearest county:", gm.loc[miss, "market"].tolist())
    disagree = gm[gm.admin2.str.lower().str.replace("-", " ") != gm.name.str.lower().str.replace("-", " ")]
    print("market admin2 vs polygon disagreements:\n", disagree[["market", "admin2", "name"]].to_string())
    m2c = dict(zip(gm.market_id, gm.district_id))

    p = p[p.pricetype == "Retail"].copy()
    p["county_id"] = p.market_id.map(m2c)
    p["date"] = pd.to_datetime(p.date).dt.to_period("M").dt.to_timestamp()
    p = p[(p.date >= "2018-01-01") & (p.date <= "2025-12-01")]

    out, meta = [], []
    common = dict(source="WFP VAM market monitoring via HDX", source_url=URL, native_resolution="market",
                  group="Prices", higher_is="worse")
    for key, (comm, label, unit) in COMMODITIES.items():
        s = p[p.commodity == comm].copy()
        s = s[s.unit.isin(UNIT_DIV)]
        s["per"] = s.unit.map(UNIT_DIV)
        s["ssp"] = s.price / s.per
        s["usd"] = s.usdprice / s.per
        agg = s.groupby(["county_id", "date"]).agg(ssp=("ssp", "median"), usd=("usd", "median")).reset_index()
        for cur in ["ssp", "usd"]:
            o = agg[["county_id", "date", cur]].rename(columns={cur: "value"})
            o["variable"] = f"price_{key}_{cur}"
            out.append(o)
            meta.append(base_meta(id=f"price_{key}_{cur}", label=f"{label} price ({cur.upper()}/{unit})",
                                  units=f"{cur.upper()} per {unit}", aggregation="median over county markets, monthly",
                                  index_ok=True,
                                  notes=("Nominal SSP; very high inflation/devaluation (SSP/USD ~ 250 in 2018 to "
                                         ">4000 in 2025) - prefer the _usd variant for indexing." if cur == "ssp" else
                                         "WFP usdprice (converted at WFP's exchange rate)."),
                                  **common))
    fx = p[p.commodity == "Exchange rate (unofficial)"]
    fx = fx.groupby(["county_id", "date"]).price.median().rename("value").reset_index()
    fx["variable"] = "fx_ssp_per_usd"
    out.append(fx)
    meta.append(base_meta(id="fx_ssp_per_usd", label="Exchange rate, parallel market (SSP per USD)",
                          units="SSP per USD", aggregation="median over county markets, monthly",
                          notes="WFP 'Exchange rate (unofficial)' recorded at each market; largely national signal.",
                          **dict(common, higher_is="worse")))
    wage = p[p.commodity == "Wage (non-qualified labour, non-agricultural)"]
    wage = wage[wage.unit == "Day"]
    for cur, col in [("ssp", "price"), ("usd", "usdprice")]:
        w = wage.groupby(["county_id", "date"])[col].median().rename("value").reset_index()
        w["variable"] = f"wage_casual_labour_{cur}"
        out.append(w)
        meta.append(base_meta(id=f"wage_casual_labour_{cur}", label=f"Daily casual labour wage ({cur.upper()})",
                              units=f"{cur.upper()} per day", aggregation="median over county markets, monthly",
                              notes="Non-agricultural unskilled labour; with sorghum price gives terms of trade.",
                              **dict(common, higher_is="better")))
    df = pd.concat(out).dropna(subset=["value"])
    finalize(df, SRC, meta)

    # ---- markets point layer
    first_last = p.groupby("market_id").date.agg(["min", "max"])
    feats = []
    for r in gm.itertuples():
        fl = first_last.loc[r.market_id] if r.market_id in first_last.index else None
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [r.longitude, r.latitude]},
                      "properties": {"name": r.market, "type": "market", "source": "WFP VAM (HDX)",
                                     "market_id": int(r.market_id), "county_id": r.district_id,
                                     "first_price": None if fl is None else fl["min"].strftime("%Y-%m"),
                                     "last_price": None if fl is None else fl["max"].strftime("%Y-%m")}})
    DOCS_DATA.mkdir(parents=True, exist_ok=True)
    (DOCS_DATA / "points_markets.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    upsert_points_meta({"key": "markets", "label": "WFP monitored markets", "category": "human",
                        "source": "WFP VAM market monitoring (HDX)", "source_url": URL,
                        "notes": "Markets with retail price monitoring; first_price/last_price = months with data 2018-2025."})


if __name__ == "__main__":
    main()
