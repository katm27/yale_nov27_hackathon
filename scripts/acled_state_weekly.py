"""ACLED aggregated weekly state-level data -> county-month contract rows (state totals shown on every county).

Input : data/raw/acled_aggregated/ACLED_aggregated_SSD_weekly_admin1_*.csv (team export, 15 Nov 2026)
Output: data/processed/acled_state_county_monthly.csv + data/processed/meta/acled_state.json

Adds ACLED sub-event detail that the admin-2 HDX aggregates (acled_county_monthly.csv) do not have:
sexual violence, abduction, looting, territory changes, air/drone strikes, etc.
Each week is assigned to the month in which the week starts. Values are STATE totals repeated on every county
of that state (ACLED's aggregated export is admin-1 only), so they show where in the country, not which county.
"""
import glob
import json
import os
import sys

import geopandas as gpd
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = sorted(glob.glob(os.path.join(ROOT, "data", "raw", "acled_aggregated", "ACLED_aggregated_SSD_weekly_admin1_*.csv")))[-1]
MONTHS = pd.date_range("2018-01-01", "2025-12-01", freq="MS")

# variable id -> (label, filter on (event_type, sub_event_type), measure)
VARS = {
    "acled_st_sexual_violence_events": ("Sexual violence events (ACLED, state)", lambda d: d.sub_event_type == "Sexual violence", "events"),
    "acled_st_sexual_violence_fatalities": ("Sexual violence fatalities (ACLED, state)", lambda d: d.sub_event_type == "Sexual violence", "fatalities"),
    "acled_st_abduction_events": ("Abductions / forced disappearances (ACLED, state)", lambda d: d.sub_event_type == "Abduction/forced disappearance", "events"),
    "acled_st_civilian_attack_events": ("Attacks on civilians (ACLED, state)", lambda d: d.sub_event_type == "Attack", "events"),
    "acled_st_civilian_attack_fatalities": ("Civilian attack fatalities (ACLED, state)", lambda d: d.sub_event_type == "Attack", "fatalities"),
    "acled_st_looting_events": ("Looting / property destruction (ACLED, state)", lambda d: d.sub_event_type == "Looting/property destruction", "events"),
    "acled_st_armed_clash_events": ("Armed clashes (ACLED, state)", lambda d: d.sub_event_type == "Armed clash", "events"),
    "acled_st_armed_clash_fatalities": ("Armed clash fatalities (ACLED, state)", lambda d: d.sub_event_type == "Armed clash", "fatalities"),
    "acled_st_territory_change_events": ("Territory changes hands (ACLED, state)", lambda d: d.sub_event_type.isin(
        ["Government regains territory", "Non-state actor overtakes territory", "Non-violent transfer of territory"]), "events"),
    "acled_st_remote_violence_events": ("Air/drone strikes, shelling, IEDs, grenades (ACLED, state)", lambda d: d.event_type == "Explosions/Remote violence", "events"),
    "acled_st_air_drone_strikes": ("Air / drone strikes (ACLED, state)", lambda d: d.sub_event_type == "Air/drone strike", "events"),
    "acled_st_protest_events": ("Protests (ACLED, state)", lambda d: d.event_type == "Protests", "events"),
    "acled_st_riot_events": ("Riots / mob violence (ACLED, state)", lambda d: d.event_type == "Riots", "events"),
    "acled_st_pv_population_exposure": ("Population exposed to political violence (ACLED, state)",
                                        lambda d: d.disorder_type.str.contains("Political violence", na=False), "population_exposure"),
}


def main():
    d = pd.read_csv(SRC)
    for c in ("events", "fatalities", "population_exposure"):
        d[c] = pd.to_numeric(d[c].astype(str).str.replace(",", ""), errors="coerce").fillna(0)
    d["date"] = pd.to_datetime(d["week"]).dt.to_period("M").dt.to_timestamp()
    g = gpd.read_file(os.path.join(ROOT, "data", "counties.geojson"))
    states = sorted(set(d.admin1))
    rows = []
    for vid, (_, filt, measure) in VARS.items():
        s = d[filt(d)].groupby(["admin1", "date"])[measure].sum()
        full = s.reindex(pd.MultiIndex.from_product([states, MONTHS], names=["admin1", "date"]), fill_value=0).reset_index()
        full = full.merge(g[["district_id", "admin1"]], on="admin1")
        full["variable"] = vid
        rows.append(full.rename(columns={"district_id": "county_id", measure: "value"})[["county_id", "date", "variable", "value"]])
    out = pd.concat(rows)
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    out.to_csv(os.path.join(ROOT, "data", "processed", "acled_state_county_monthly.csv"), index=False)
    meta = [{"id": vid, "label": lab, "category": "human", "group": "Conflict – ACLED event types (state level)",
             "units": "people" if m == "population_exposure" else m, "source": "ACLED aggregated data (weekly, admin-1), team export 15 Nov 2026",
             "source_url": "https://acleddata.com/", "native_resolution": "state (admin-1); STATE total shown on every county of the state",
             "temporal": "monthly", "aggregation": "sum of ACLED weeks starting in the month", "higher_is": "worse", "index_ok": True,
             "notes": "State-level: identical on all counties of a state. Abyei not included (ACLED codes it under Sudan). "
                      + ("Population exposure is summed over weeks (person-exposures), so it double counts people exposed repeatedly. "
                         if m == "population_exposure" else "")
                      + ("Sexual violence is ACLED's sub-event type; the best available proxy for political violence targeting women "
                         "(the full PVTW category needs event-level data). " if "sexual" in vid else "")}
            for vid, (lab, _, m) in VARS.items()]
    json.dump(meta, open(os.path.join(ROOT, "data", "processed", "meta", "acled_state.json"), "w"), indent=1)
    print(len(out), "rows,", len(VARS), "variables,", out.county_id.nunique(), "counties,", len(states), "states")


if __name__ == "__main__":
    main()
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from trend_stats import write_trends
    write_trends("acled_state")
