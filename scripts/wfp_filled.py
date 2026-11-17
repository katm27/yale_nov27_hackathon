"""Gap-filled versions of the curated WFP market-price measures -> data/processed/wfp_filled_county_monthly.csv.

The original ids (price_sorghum_local_usd, ...; scripts/wfp_prices_ssd.py) stay OBSERVED-only. This script writes
`<id>_filled` series and a per-value flag file (data/processed/wfp_filled_flags.csv) saying where every value came from:

  observed              WFP VAM value for the county-month, identical to the original series
  observed_wfp_variant  WFP value for a renamed variety of the same commodity (local sorghum only: WFP reported
                        'Sorghum (red, local)' / 'Sorghum (brown)' in 2020-2024 while 'Sorghum (local)' was not reported)
  observed_fewsnet      FEWS NET market price for a county-month with no WFP value (local sorghum = Feterita, white
                        maize grain; SSP converted to USD at WFP's own monthly reference rate so that it matches the
                        basis of WFP's usdprice, which is the OFFICIAL rate, not the parallel rate)
  interp_time           gap of <= 2 months inside the county's own observed series, linear interpolation of log price
  nearby_market         county-month with no value: inverse-distance weighted median of up to 3 nearest markets with an
                        observed price that same month, all within a validated radius (<= 150 km) of the county
                        centroid; distance_km = distance to the nearest donor market

No value is extrapolated: interpolation is only between two observed months and spatial donors are observed in the same
month. The spatial radius per measure is chosen by leave-one-county-out validation (largest radius in 150/120/100/75/50 km
with median absolute % error <= 25%); a measure with no radius passing gets no spatial fill.

REACH/IMPACT JMMI was not used: the dataset files on repository.impact-initiatives.org returned HTTP 403 to this
environment (2026-11-17) - the 'observed_jmmi' method is therefore absent.
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from human_common import RAW, PROC, MONTHS, download, load_counties, finalize, base_meta

SRC = "wfp_filled"
WFP_URL = "https://data.humdata.org/dataset/wfp-food-prices-for-south-sudan"
FEWS_PAGE = "https://data.humdata.org/dataset/fewsnet_staple_food_price_data_for_south_sudan_weekly_6857"
FEWS_API = ("https://fdw.fews.net/api/marketpricefacts/?dataset=FEWS_NET_Staple_Food_Price_Data&country=SS"
            "&format=csv&fields=website")
FEWS_CSV = RAW / "fewsnet_prices" / "fewsnet_staple_food_prices_ssd.csv"
UNIT_DIV = {"KG": 1.0, "3.5 KG": 3.5, "50 KG": 50.0, "L": 1.0}  # same as scripts/wfp_prices_ssd.py
RADII = [150, 120, 100, 75, 50]
MAX_APE = 0.25
MIN_VAL_PAIRS = 30
MAX_GAP = 2

# id -> spec. kind: 'price' (per-unit, unit-filtered), 'fx', 'wage'. col: WFP column ('usd' = usdprice, 'ssp' = price).
SPECS = {
    "price_sorghum_local_usd": dict(kind="price", col="usd", wfp=["Sorghum (local)"],
                                    variants=["Sorghum (red, local)", "Sorghum (brown)"],
                                    fews=("Sorghum (Feterita)", "3.5_kg", 3.5),
                                    label="Local sorghum price, gap-filled (US$ per kg)", units="USD per kg",
                                    higher_is="worse"),
    "price_maize_usd": dict(kind="price", col="usd", wfp=["Maize (white)"], variants=[],
                            fews=("Maize Grain (White)", "3.5_kg", 3.5),
                            label="Maize price, gap-filled (US$ per kg)", units="USD per kg", higher_is="worse"),
    "price_diesel_parallel_usd": dict(kind="price", col="usd", wfp=["Fuel (diesel, parallel market)"], variants=[],
                                      fews=None, label="Diesel price, black market, gap-filled (US$ per litre)",
                                      units="USD per L", higher_is="worse"),
    "price_diesel_parallel_ssp": dict(kind="price", col="ssp", wfp=["Fuel (diesel, parallel market)"], variants=[],
                                      fews=None, label="Diesel price, black market, gap-filled (pounds per litre)",
                                      units="SSP per L", higher_is="worse"),
    "fx_ssp_per_usd": dict(kind="fx", col="ssp", wfp=["Exchange rate (unofficial)"], variants=[], fews=None,
                           label="Black-market exchange rate, gap-filled (pounds per US$)", units="SSP per USD",
                           higher_is="worse"),
    "wage_casual_labour_usd": dict(kind="wage", col="usd", wfp=["Wage (non-qualified labour, non-agricultural)"],
                                   variants=[], fews=None,
                                   label="Daily wage for casual labour, gap-filled (US$)", units="USD per day",
                                   higher_is="better"),
}
# FEWS NET products checked but NOT used (definition mismatch vs the WFP series; see notes / report):
#   Diesel vs WFP parallel diesel: MdAPE 24% but matches WFP *official* diesel (8%) -> not the parallel series.
#   Casual Labor (without food) vs WFP wage: MdAPE 36%.


def haversine(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def assign_county(df, g, lat="latitude", lon="longitude"):
    pts = gpd.GeoDataFrame(df.copy(), geometry=gpd.points_from_xy(df[lon], df[lat]), crs="EPSG:4326")
    j = gpd.sjoin(pts, g[["district_id", "geometry"]], how="left", predicate="within").drop(columns="index_right")
    j = j[~j.index.duplicated()]
    miss = j.district_id.isna()
    if miss.any():  # rounded coordinates just outside a polygon -> nearest county (as in wfp_prices_ssd.py)
        near = gpd.sjoin_nearest(j[miss].drop(columns=["district_id"]).to_crs(32636),
                                 g[["district_id", "geometry"]].to_crs(32636), how="left")
        near = near[~near.index.duplicated()]
        j.loc[miss, "district_id"] = near.district_id.values
    return pd.DataFrame(j.drop(columns="geometry"))


def load_wfp(g):
    p = pd.read_csv(RAW / "wfp_prices" / "wfp_food_prices_ssd.csv", low_memory=False)
    mk = pd.read_csv(RAW / "wfp_prices" / "wfp_markets_ssd.csv")
    p = p[~p.date.astype(str).str.startswith("#")]
    mk = mk[~mk.market_id.astype(str).str.startswith("#")]
    for c in ["price", "usdprice", "market_id"]:
        p[c] = pd.to_numeric(p[c], errors="coerce")
    mk["market_id"] = pd.to_numeric(mk.market_id)
    mk["latitude"] = pd.to_numeric(mk.latitude, errors="coerce")
    mk["longitude"] = pd.to_numeric(mk.longitude, errors="coerce")
    mk = mk.dropna(subset=["latitude", "longitude"])
    mk = assign_county(mk, g)
    p = p[p.pricetype == "Retail"].copy()
    p["date"] = pd.to_datetime(p.date).dt.to_period("M").dt.to_timestamp()
    p = p[(p.date >= MONTHS[0]) & (p.date <= MONTHS[-1])]
    p = p.merge(mk[["market_id", "district_id", "latitude", "longitude"]].rename(
        columns={"district_id": "county_id", "latitude": "lat", "longitude": "lon"}), on="market_id", how="left",
        suffixes=("_raw", ""))
    p["market_key"] = "wfp:" + p.market_id.astype("Int64").astype(str)
    # WFP reference (official) SSP/USD per month, i.e. the basis of WFP's usdprice
    ok = (p.usdprice > 0) & (p.price > 0)
    ref = (p[ok].price / p[ok].usdprice).groupby(p[ok].date).median().rename("ref_rate")
    return p, ref


def wfp_values(p, spec, commodities):
    s = p[p.commodity.isin(commodities)].copy()
    if spec["kind"] == "price":
        s = s[s.unit.isin(UNIT_DIV)]
        per = s.unit.map(UNIT_DIV)
        s["value"] = (s.usdprice if spec["col"] == "usd" else s.price) / per
    elif spec["kind"] == "wage":
        s = s[s.unit == "Day"]
        s["value"] = s.usdprice if spec["col"] == "usd" else s.price
    else:  # fx
        s["value"] = s.price
    return s.dropna(subset=["value", "county_id"])


def load_fews(g, ref):
    if not FEWS_CSV.exists():
        download(FEWS_API, FEWS_CSV)
    f = pd.read_csv(FEWS_CSV, encoding="utf-8-sig", low_memory=False)
    f["date"] = pd.to_datetime(f.period_date).dt.to_period("M").dt.to_timestamp()
    f = f[(f.date >= MONTHS[0]) & (f.date <= MONTHS[-1]) & (f.currency == "SSP")]
    mk = f.drop_duplicates("market")[["market", "latitude", "longitude"]]
    mk = assign_county(mk, g).rename(columns={"district_id": "county_id", "latitude": "lat", "longitude": "lon"})
    f = f.drop(columns=["latitude", "longitude"]).merge(mk, on="market")
    f["market_key"] = "fews:" + f.market
    return f.merge(ref, left_on="date", right_index=True, how="left")


def fews_values(f, spec):
    if not spec["fews"]:
        return f.iloc[0:0].assign(value=np.nan)
    prod, unit, per = spec["fews"]
    s = f[(f["product"] == prod) & (f.unit == unit) & (f.price_type == "Retail")].copy()
    s["value"] = s.value / per
    if spec["col"] == "usd":
        s["value"] = s.value / s.ref_rate
    # weekly -> monthly median per market
    return s.dropna(subset=["value"]).groupby(["market_key", "county_id", "lat", "lon", "date"]).value.median().reset_index()


def weighted_median(vals, w):
    o = np.argsort(vals)
    vals, w = np.asarray(vals)[o], np.asarray(w)[o]
    c = np.cumsum(w)
    return float(vals[np.searchsorted(c, 0.5 * c[-1])])


def spatial_pred(cid, date, mkt_by_date, cent, radius):
    """IDW weighted median of up to 3 nearest markets (outside cid) observed at `date` within radius km."""
    m = mkt_by_date.get(date)
    if m is None:
        return None
    m = m[m.county_id != cid]
    if m.empty:
        return None
    d = haversine(cent.loc[cid, "clat"], cent.loc[cid, "clon"], m.lat.values, m.lon.values)
    keep = d <= radius
    if not keep.any():
        return None
    idx = np.argsort(d[keep])[:3]
    dd, vv = d[keep][idx], m.value.values[keep][idx]
    return weighted_median(vv, 1.0 / np.maximum(dd, 10.0)), float(dd.min()), len(dd)


def interp_series(s):
    """s: Series on full monthly index (NaN = missing). Fill interior gaps <= MAX_GAP by log-linear interpolation."""
    obs = s.notna().values
    out = s.copy()
    filled = []
    idx = np.where(obs)[0]
    for a, b in zip(idx[:-1], idx[1:]):
        gap = b - a - 1
        if 1 <= gap <= MAX_GAP and s.iloc[a] > 0 and s.iloc[b] > 0:
            la, lb = np.log(s.iloc[a]), np.log(s.iloc[b])
            for k in range(1, gap + 1):
                out.iloc[a + k] = float(np.exp(la + (lb - la) * k / (gap + 1)))
                filled.append(out.index[a + k])
    return out, filled


def main():
    g = load_counties()
    cen = g.to_crs(6933).geometry.centroid.to_crs(4326)
    cent = pd.DataFrame({"clat": cen.y.values, "clon": cen.x.values}, index=g.district_id.values)
    ids = sorted(g.district_id)
    p, ref = load_wfp(g)
    f = load_fews(g, ref)
    orig = pd.read_csv(PROC / "wfp_prices_county_monthly.csv", parse_dates=["date"])

    out, flags, meta, report = [], [], [], {}
    n_cells = len(ids) * len(MONTHS)
    for vid, spec in SPECS.items():
        # ---------- observed layers (county-month) with priority WFP > WFP variant > FEWS NET
        prim = wfp_values(p, spec, spec["wfp"])
        c_prim = prim.groupby(["county_id", "date"]).value.median()
        # sanity: identical to the original observed series
        o = orig[orig.variable == vid].set_index(["county_id", "date"]).value
        j = pd.concat([c_prim.rename("a"), o.rename("b")], axis=1)
        assert j.a.notna().sum() == j.b.notna().sum() and np.allclose(j.dropna().a, j.dropna().b, rtol=1e-4), vid
        var = wfp_values(p, spec, spec["variants"]) if spec["variants"] else prim.iloc[0:0]
        c_var = var.groupby(["county_id", "date"]).value.median()
        fw = fews_values(f, spec)
        c_fews = fw.groupby(["county_id", "date"]).value.median()
        layers = [("observed", c_prim), ("observed_wfp_variant", c_var), ("observed_fewsnet", c_fews)]
        cm = {}
        for method, ser in layers:
            for k, v in ser.items():
                if k not in cm and np.isfinite(v) and v > 0:
                    cm[k] = (v, method)
        # market-level donors (same priority within a WFP market-month: primary before variant)
        mp = prim.groupby(["market_key", "county_id", "lat", "lon", "date"]).value.median().reset_index()
        mv = var.groupby(["market_key", "county_id", "lat", "lon", "date"]).value.median().reset_index()
        mv = mv[~mv.set_index(["market_key", "date"]).index.isin(mp.set_index(["market_key", "date"]).index)]
        mk = pd.concat([mp, mv, fw], ignore_index=True)
        mk = mk[mk.value > 0]
        mkt_by_date = {d: x for d, x in mk.groupby("date")}

        # ---------- validation: spatial (hold out each observed county-month, predict from markets in other counties)
        val = {}
        tests = [(c, d, v) for (c, d), (v, _m) in cm.items()]
        for r in RADII:
            ape, dist = [], []
            for c, d, v in tests:
                res = spatial_pred(c, d, mkt_by_date, cent, r)
                if res:
                    ape.append(abs(res[0] - v) / v)
                    dist.append(res[1])
            val[r] = dict(n=len(ape), mdape=float(np.median(ape)) if ape else None,
                          p90_ape=float(np.quantile(ape, .9)) if ape else None,
                          median_nearest_km=float(np.median(dist)) if dist else None)
        radius = next((r for r in RADII if val[r]["n"] >= MIN_VAL_PAIRS and val[r]["mdape"] <= MAX_APE), None)
        # ---------- validation: temporal (hold out an observed month whose neighbours leave a gap <= 2)
        series = {}
        for (c, d), (v, _m) in cm.items():
            series.setdefault(c, {})[d] = v
        tape = []
        for c, dv in series.items():
            s = pd.Series(dv).reindex(MONTHS)
            pos = np.where(s.notna().values)[0]
            for i in range(1, len(pos) - 1):
                a, t, b = pos[i - 1], pos[i], pos[i + 1]
                if b - a - 1 <= MAX_GAP:
                    la, lb = np.log(s.iloc[a]), np.log(s.iloc[b])
                    pred = np.exp(la + (lb - la) * (t - a) / (b - a))
                    tape.append(abs(pred - s.iloc[t]) / s.iloc[t])
        # ---------- fill
        vals = {}
        for k, (v, m) in cm.items():
            vals[k] = (v, m, None)
        for c, dv in series.items():
            s = pd.Series(dv).reindex(MONTHS)
            s2, filled = interp_series(s)
            for d in filled:
                vals[(c, d)] = (s2[d], "interp_time", None)
        if radius is not None:
            for c in ids:
                for d in MONTHS:
                    if (c, d) in vals:
                        continue
                    res = spatial_pred(c, d, mkt_by_date, cent, radius)
                    if res:
                        vals[(c, d)] = (res[0], "nearby_market", round(res[1], 1))
        fid = f"{vid}_filled"
        for (c, d), (v, m, dk) in vals.items():
            out.append((c, d, fid, v))
            flags.append((c, d.strftime("%Y-%m-%d"), fid, m, dk))
        cnt = pd.Series([m for (_v, m, _d) in vals.values()]).value_counts().to_dict()
        n_obs = cnt.get("observed", 0)
        n_obs2 = n_obs + cnt.get("observed_wfp_variant", 0) + cnt.get("observed_fewsnet", 0)
        n_int = n_obs2 + cnt.get("interp_time", 0)
        report[vid] = dict(
            filled_id=fid, counts=cnt,
            coverage_pct=dict(observed_wfp=round(100 * n_obs / n_cells, 1),
                              observed_all_sources=round(100 * n_obs2 / n_cells, 1),
                              plus_interp=round(100 * n_int / n_cells, 1),
                              filled_total=round(100 * len(vals) / n_cells, 1)),
            counties_with_value=dict(observed_wfp=int(c_prim.index.get_level_values(0).nunique()),
                                     filled=len({c for c, _ in vals})),
            spatial_validation=val, spatial_radius_km=radius,
            temporal_validation=dict(n=len(tape), mdape=float(np.median(tape)) if tape else None))
        print(vid, json.dumps(report[vid], default=str))

        rad_txt = (f"(ii) nearby_market: county-months still empty take the inverse-distance weighted median of the up "
                   f"to 3 nearest markets (in other counties) with an observed price in the SAME month, all within "
                   f"{radius} km of the county centroid; flag distance_km = nearest donor. Leave-one-county-out "
                   f"validation at {radius} km: median abs error {100 * val[radius]['mdape']:.0f}% "
                   f"(n={val[radius]['n']})." if radius else
                   "(ii) No spatial (nearby-market) fill: leave-one-county-out validation error exceeded 25% at "
                   "every radius tested (150-50 km).")
        src_txt = "WFP VAM market monitoring via HDX" + (" + FEWS NET staple food prices (FDW/HDX)" if spec["fews"] else "")
        meta.append(base_meta(
            id=fid, label=spec["label"], units=spec["units"],
            aggregation="median over county markets, monthly; gaps filled (see notes)",
            notes=(f"ESTIMATES in filled cells - gap-filled version of '{vid}' (which stays observed-only). Each value "
                   "is flagged in data/processed/wfp_filled_flags.csv (observed / observed_wfp_variant / "
                   "observed_fewsnet / interp_time / nearby_market). Observed priority: WFP value; "
                   + ("WFP renamed local-sorghum varieties ('Sorghum (red, local)', 'Sorghum (brown)') where WFP "
                      "'Sorghum (local)' is missing (it was not reported 2021-2023); " if spec["variants"] else "")
                   + ("FEWS NET retail price for counties/months without WFP data (SSP converted to USD at WFP's monthly "
                      "reference rate = median price/usdprice, the same official-rate basis as WFP usdprice); "
                      if spec["fews"] else "")
                   + f"(i) interp_time: interior gaps of <= {MAX_GAP} months in a county's own series, linear in log "
                   f"price (hold-out error {100 * np.median(tape):.0f}%); " + rad_txt
                   + " Nothing is extrapolated beyond observed months."),
            source=src_txt, source_url=WFP_URL, native_resolution="market", group="Prices",
            higher_is=spec["higher_is"]))

    df = pd.DataFrame(out, columns=["county_id", "date", "variable", "value"])
    finalize(df, SRC, meta)
    fl = pd.DataFrame(flags, columns=["county_id", "date", "variable", "method", "distance_km"])
    fl = fl.sort_values(["variable", "county_id", "date"])
    fl.to_csv(PROC / "wfp_filled_flags.csv", index=False)
    (PROC / "validation").mkdir(exist_ok=True)
    (PROC / "validation" / "wfp_filled_validation.json").write_text(json.dumps(report, indent=1, default=str))


if __name__ == "__main__":
    main()
    from trend_stats import write_trends
    write_trends(SRC)
