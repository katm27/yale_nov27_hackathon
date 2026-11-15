"""Local (communal / local-militia) conflict per county-month from UCDP GED v26.1.

"Intra-county" here means violence between or by LOCAL actors (ethnic/clan/section groups, cattle-camp youth,
local militias), as opposed to state-based war (government vs rebels) or foreign groups. UCDP GED has no actor-type
column, so actors are classified by name from data/raw/ucdp/ged261_ssd_2018_2025.csv:
  * communal   = identity groups UCDP codes as non-state "informally organised" actors (Dinka/Nuer sections, Murle,
                 Toposa, Misseriya, Anuak, Azande, Balanda, ...). Every non-state / one-sided actor that is not in
                 the ORGANISED or FOREIGN lists below is treated as communal.
  * local militia = South Sudanese organised non-state groups: NAS, SPLM/A-IO (and its Kitgwang/Olony factions),
                 AAKG and CPC (UCDP actor codes for local armed groups) -- counted when they fight each other (non-state) or kill civilians
                 (one-sided). Their clashes with the government are state-based and excluded.
  * excluded   = governments (state-based or one-sided by government forces) and foreign groups (LRA, OLA, Fano,
                 SLM/A, FPRC, MLCJ, UPC; Ethiopian/CAR/Russian/DRC governments).
Counting rules follow scripts/ucdp_ssd.py: events located by point-in-polygon, only where_prec <= 3; zero = no event.
Caveat: GED only records events with >=1 death that belong to a dyad passing UCDP's 25-deaths/year threshold, so
low-level cattle raiding is under-counted; the actor's home county is NOT known, so an event between two groups
from different counties counts in the county where it happened.
"""
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from human_common import RAW, MONTHS, load_counties, finalize, base_meta

SRC = "intracounty"
ORGANISED_LOCAL = {"NAS", "SPLM/A - IO", "SPLM/A - IO - Kitgwang", "SPLM/A - IO - Olony", "AAKG", "CPC"}
FOREIGN_OR_STATE = {"LRA", "OLA", "Fano", "SLM/A", "FPRC", "MLCJ", "UPC", "Government of South Sudan",
                    "Government of Ethiopia", "Government of Central African Republic",
                    "Government of DR Congo (Zaire)", "Government of Russia (Soviet Union)",
                    "Christians (CAR)", "Muslims (CAR)", "Farmers (CAR)", "Herders (CAR)", "Amhara", "Oromo", "Gumuz",
                    "Agaw, Amhara", "Agaw, Amhara, Shinasha", "Amhara, Oromo, Shinasha", "Mursi", "Dassanetch"}


def actor_class(name):
    if name == "Civilians":
        return "civilians"
    if name in FOREIGN_OR_STATE or name.startswith("Government of"):
        return "excluded"
    if name in ORGANISED_LOCAL:
        return "militia"
    return "communal"


def main():
    d = pd.read_csv(RAW / "ucdp" / "ged261_ssd_2018_2025.csv", low_memory=False)
    d = d[d.type_of_violence.isin([2, 3])].copy()
    d["ca"] = d.side_a.map(actor_class)
    d["cb"] = d.side_b.map(actor_class)
    comm = ((d.ca == "communal") & d.cb.isin(["communal", "civilians"])) | ((d.cb == "communal") & (d.ca == "communal"))
    mil = (~comm) & d.ca.isin(["militia", "communal"]) & d.cb.isin(["militia", "communal", "civilians"])
    d["kind"] = None
    d.loc[comm, "kind"] = "communal"
    d.loc[mil, "kind"] = "militia"
    d = d[d.kind.notna()]
    cty = load_counties()[["district_id", "geometry"]].to_crs(4326)
    pts = gpd.GeoDataFrame(d, geometry=gpd.points_from_xy(d.longitude, d.latitude), crs=4326)
    j = gpd.sjoin(pts, cty, how="inner", predicate="within")
    j = j[j.where_prec <= 3].copy()
    j["date"] = pd.to_datetime(j.date_start).dt.to_period("M").dt.to_timestamp()
    print("events by kind:", j.kind.value_counts().to_dict(), "top dyads:")
    print(j.groupby(["kind", "dyad_name"]).size().sort_values(ascending=False).head(15).to_string())
    idx = pd.MultiIndex.from_product([sorted(cty.district_id), MONTHS], names=["county_id", "date"])
    rows = []
    for var, sub, col in [("intracounty_conflict_events", j, None), ("intracounty_conflict_deaths", j, "best"),
                          ("intracounty_communal_events", j[j.kind == "communal"], None),
                          ("intracounty_communal_deaths", j[j.kind == "communal"], "best")]:
        g = sub.groupby(["district_id", "date"])
        s = g.size() if col is None else g[col].sum()
        s.index.names = ["county_id", "date"]
        s = s.reindex(idx, fill_value=0).rename("value").reset_index()
        s["variable"] = var
        rows.append(s)
    df = pd.concat(rows)
    df["value"] = df.value.astype(float)
    common = dict(source="UCDP Georeferenced Event Dataset (GED) v26.1; actor classification scripts/intracounty_conflict.py",
                  source_url="https://ucdp.uu.se/downloads/", native_resolution="event points (where_prec<=3)",
                  group="Conflict", higher_is="worse", index_ok=False,
                  notes="Local violence: UCDP non-state + one-sided events whose perpetrators are communal identity "
                        "groups (Dinka/Nuer sections, Murle, Toposa, Misseriya, ...) or South Sudanese local militias "
                        "(NAS, SPLA-IO factions, UCDP actors AAKG and CPC) fighting each other or attacking civilians. Government "
                        "and foreign actors excluded. Only deadly events of dyads above UCDP's 25-deaths/year threshold, "
                        "so cattle raiding is under-counted; counted where the event happened (actors' home county "
                        "unknown). Zeros in 2018 make ratio indexing meaningless (index_ok false).")
    meta = [base_meta(id="intracounty_conflict_events", label="Local/communal conflict events (UCDP)",
                      units="events/month", aggregation="count of GED non-state/one-sided events by local actors", **common),
            base_meta(id="intracounty_conflict_deaths", label="Local/communal conflict deaths (UCDP)",
                      units="deaths/month", aggregation="sum of GED best estimate", **common),
            base_meta(id="intracounty_communal_events", label="Inter-communal violence events (UCDP)",
                      units="events/month", aggregation="count of GED events between communal groups (or communal "
                      "group vs civilians)", **common),
            base_meta(id="intracounty_communal_deaths", label="Inter-communal violence deaths (UCDP)",
                      units="deaths/month", aggregation="sum of GED best estimate", **common)]
    finalize(df, SRC, meta)


if __name__ == "__main__":
    main()
    from trend_stats import write_trends
    write_trends(SRC)  # Mann-Kendall + Sen's slope (scripts/trend_stats.py)
