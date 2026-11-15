"""WFP monitored markets over time -> docs/data/points_markets.geojson (one feature per market x active period).

Active months = months with at least one retail price in WFP VAM / HDX food prices (data/raw/wfp_prices).
A market is shown from its first to its last price month; a gap of more than GAP months without prices splits it into
separate periods (reporting stopped and resumed). Only months 2018-01..2025-12 count (earlier prices only decide
whether valid_from is null = already monitored before 2018).
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from points_temporal import ROOT, point, write_fc, set_validity, update_points_meta, assign_county_fc

RAW = os.path.join(ROOT, "data", "raw", "wfp_prices")
GAP = 6  # months


def main():
    p = pd.read_csv(os.path.join(RAW, "wfp_food_prices_ssd.csv"), low_memory=False)
    p = p[p.pricetype.astype(str).str.lower() == "retail"].copy()
    p["m"] = pd.to_datetime(p.date).dt.to_period("M")
    mk = pd.read_csv(os.path.join(RAW, "wfp_markets_ssd.csv")).set_index("market_id")
    feats = []
    for mid, s in p.groupby("market_id"):
        months = sorted(set(s.m))
        pre2018 = any(m < pd.Period("2018-01", "M") for m in months)
        win = [m for m in months if pd.Period("2018-01", "M") <= m <= pd.Period("2025-12", "M")]
        if not win:
            continue
        runs, start, prev = [], win[0], win[0]
        for m in win[1:]:
            if (m - prev).n > GAP:
                runs.append((start, prev))
                start = m
            prev = m
        runs.append((start, prev))
        row = mk.loc[mid] if mid in mk.index else s.iloc[0]
        lat, lon = float(row["latitude"]), float(row["longitude"])
        for a, b in runs:
            n = sum(1 for m in win if a <= m <= b)
            vf = None if (a == pd.Period("2018-01", "M") and pre2018) else a.strftime("%Y-%m")
            vt = None if b == pd.Period("2025-12", "M") else b.strftime("%Y-%m")
            props = dict(name=str(row["market"]), type="market")
            set_validity(props, vf, vt, "WFP first/last retail price month" + (f" (split at gaps > {GAP} months)" if len(runs) > 1 else ""))
            props.update(market_id=int(mid), admin1=row.get("admin1"), admin2=row.get("admin2"),
                         first_price=a.strftime("%Y-%m"), last_price=b.strftime("%Y-%m"), months_with_prices=n,
                         n_commodities=int(s[(s.m >= a) & (s.m <= b)].commodity.nunique()),
                         source="WFP VAM (HDX)")
            feats.append(point(lon, lat, props))
    assign_county_fc(feats)
    write_fc("points_markets.geojson", feats)
    print(len(feats), "features,", len({f['properties']['market_id'] for f in feats}), "markets")
    update_points_meta({
        "key": "markets", "label": "WFP monitored markets (active months)", "category": "human",
        "source": "WFP VAM market monitoring (HDX)",
        "source_url": "https://data.humdata.org/dataset/wfp-food-prices-for-south-sudan",
        "notes": (f"Temporal: valid_from/valid_to = first/last month with retail prices 2018-01..2025-12; gaps longer "
                  f"than {GAP} months split a market into separate periods. valid_from null = already monitored before "
                  "2018. months_with_prices counts reporting months within the period.")})


if __name__ == "__main__":
    main()
