"""PoC sites, IDP & refugee camps with open / redesignation / close dates -> docs/data/points_crisis_sites.geojson

Site list and coordinates: scripts/crisis_sites.py (SITES; OSM/HOT coordinates, coord_quality flags).
The June 2026 Logistics Cluster hubs that crisis_sites.py used to add are now in their own time-dynamic layer
(points_logcluster_hubs.geojson, built from all CONOPS maps 2018-2026) and are left out here.

Dates (one feature per status period):
 * PoC -> IDP camp redesignation: UNMISS began withdrawing from the Bor and Wau PoC sites in September 2020
   (UNMISS press releases, 4 Sep 2020); the Juba PoC sites 1 and 3 and Bentiu were redesignated afterwards
   (UNMISS: "redesignated Juba, Wau, Bor and Bentiu sites into IDP camps since 2020"; Juba late 2020, Bentiu
   early 2021 -> month approximate, flagged). Malakal remains the only PoC site.
 * Camps opened before 2018 get valid_from = null; the Renk transit centre opened with the Sudan war arrivals
   (Apr 2023). Camps with no documented closure stay open (valid_to = null).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from points_temporal import point, write_fc, set_validity, update_points_meta, assign_county_fc
from crisis_sites import SITES, OSM

UN = "UNMISS press releases (Sep 2020-Mar 2021) / UN Peacekeeping: PoC redesignation"
# name -> list of (valid_from, valid_to, type, status, date_basis)
PERIODS = {
    "Juba UN House PoC1 (IDP camp since 2020)": [
        (None, "2020-10", "PoC site", "UNMISS Protection of Civilians site (Dec 2013-)", UN),
        ("2020-11", None, "IDP camp (former PoC)", "redesignated IDP camp under government control",
         UN + "; month approximate (late 2020)")],
    "Juba UN House PoC3 (IDP camp since 2020)": [
        (None, "2020-10", "PoC site", "UNMISS Protection of Civilians site (2014-)", UN),
        ("2020-11", None, "IDP camp (former PoC)", "redesignated IDP camp under government control",
         UN + "; month approximate (late 2020)")],
    "Bentiu PoC (IDP camp since 2020)": [
        (None, "2021-02", "PoC site", "UNMISS Protection of Civilians site (Dec 2013-)", UN),
        ("2021-03", None, "IDP camp (former PoC)", "redesignated IDP camp; expanded after 2021-22 floods",
         UN + "; month approximate (early 2021)")],
    "Malakal PoC site": [(None, None, "PoC site", "only remaining UNMISS PoC site", UN + "; still a PoC site in 2025")],
    "Bor PoC (closed/redesignated 2020)": [
        (None, "2020-08", "PoC site", "UNMISS Protection of Civilians site (Dec 2013-)", UN),
        ("2020-09", None, "IDP camp (former PoC)", "redesignated Sep 2020 (UNMISS withdrawal began 4 Sep 2020)",
         UN + " (Bor, Sep 2020)")],
    "Wau PoC Adjacent Area (closed 2021)": [
        (None, "2020-08", "PoC site", "UNMISS PoC Adjacent Area (2016-)", UN),
        ("2020-09", "2021-12", "IDP camp (former PoC)", "redesignated Sep 2020; closed during 2021",
         UN + " (Wau, Sep 2020); closure month unknown - set to end-2021")],
    "Renk transit centre (Sudan crisis)": [
        ("2023-04", None, "refugee/returnee transit centre", "opened with arrivals from Sudan after 15 Apr 2023",
         "start of Sudan war (15 Apr 2023); UNHCR/IOM Renk transit centre")],
}


def main():
    feats = []
    for n, t, x, y, s, cs, q in SITES:
        per = PERIODS.get(n) or [(None, None, t, s, "opened before 2018 (status text); no closure documented 2018-2025")]
        for vf, vt, typ, status, basis in per:
            props = dict(name=n, type=typ)
            set_validity(props, vf, vt, basis)
            props.update(status=status, site_history=s, coord_source=cs, coord_quality=q,
                         source=cs if cs == OSM else "curated (see notes)")
            feats.append(point(x, y, props))
    assign_county_fc(feats)
    write_fc("points_crisis_sites.geojson", feats, precision=4)
    print(len(feats), "features for", len(SITES), "sites")
    update_points_meta({
        "key": "crisis_sites", "label": "PoC sites, IDP & refugee camps (status over time)", "category": "human",
        "source": "Curated: OSM (HOT/HDX) coordinates; UNMISS / UNHCR / IOM public site lists; UNMISS press releases "
                  "on PoC redesignation (2020-21)",
        "source_url": "https://data.humdata.org/dataset/hotosm_ssd_points_of_interest",
        "notes": ("Temporal: one feature per site and status period. PoC -> IDP camp redesignation: Bor & Wau Sep 2020 "
                  "(documented), Juba PoC1/3 Nov 2020 and Bentiu Mar 2021 (month approximate); Wau former PoC closed "
                  "2021 (month unknown); Malakal stays a PoC site; Renk transit centre from Apr 2023. Other camps "
                  "opened before 2018 and are open-ended. Logistics hubs moved to the logcluster_hubs layer. "
                  "`coord_quality` flags approximate positions. Not exhaustive (see DTM layer).")})


if __name__ == "__main__":
    main()
