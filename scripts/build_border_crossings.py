"""Cross-border entry points for flow arrows -> data/crosswalks/border_crossings.csv

Each crossing has a SOURCE coordinate (IOM DTM Flow Monitoring Point coordinates from the team unified dataset
fmr_monitoring_points.csv, or an OpenStreetMap node/way looked up by name) and a MAP coordinate (lat/lon) that is
guaranteed to sit on the South Sudan side of the OCHA COD-AB v03 border used by the app:
  - source point inside South Sudan and <= 3 km from the border -> kept as is;
  - otherwise (outside the COD-AB outline, or deeper inside) -> nearest point on the border line pulled 300 m inside.
`snap_km` = distance moved. Several IOM FMP coordinates sit 4-17 km on the Sudan/Uganda side of the COD-AB line
(Wunthou/Joda, Kiir Adem, Kerwa); the snap puts the arrow origin on the drawn border.
Dropped after checking: Ngomoromo (OSM node is 30 km inside Uganda), Raja/Sopo (85 km from the border),
Panakuach (Unity; no verifiable public coordinate - Jau is used for Unity).
Run: python scripts/build_border_crossings.py
"""
import csv
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point
from shapely.ops import nearest_points

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/crosswalks/border_crossings.csv"
IOM = "IOM DTM FMR monitoring point (data/raw/ssd_unified fmr_monitoring_points.csv)"
FMR_URL = "https://dtm.iom.int/south-sudan"
OSM = "https://www.openstreetmap.org/{}"

# country, name, source lat, lon, coord source, source url, serves (states), notes
CROSSINGS = [
    ("SDN", "Joda / Wunthou (Renk)", 12.36246, 32.79971, IOM + " 'Wunthow (Juda)'", FMR_URL, "Upper Nile",
     "Main entry for Sudan-war arrivals (2023-); Renk transit centre 75 km south. OSM Joda (Sudan side): node 7369223905 12.2479,32.7611"),
    ("SDN", "Kuek (Manyo)", 11.95034, 32.71933, "OSM node 4007862102", OSM.format("node/4007862102"), "Upper Nile",
     "West-bank Nile route into Manyo/Renk"),
    ("SDN", "Yabus - Maban (Blue Nile route)", 9.948038, 34.02907, "OSM relation 5248818 (Yabus, Sudan side)",
     OSM.format("relation/5248818"), "Upper Nile", "Approximate: Blue Nile refugees to Maban camps; snapped to the nearest COD-AB border point"),
    ("SDN", "Jau (Pariang / Ruweng AA)", 10.27375, 29.98546, "OSM node 11276421057", OSM.format("node/11276421057"), "Unity",
     "Refugee entry point to Ajuong Thok/Pamir/Yida (UNHCR: refugees enter via Jau and Liri)"),
    ("SDN", "Diffra / northern Abyei Area", 10.03903, 28.40029, "OSM node 2177423626", OSM.format("node/2177423626"),
     "Abyei Administrative Area", "Muglad-Diffra-Abyei road; IOM FMP Abyei Amieth (9.604,28.438) is 52 km inside, not a border point"),
    ("SDN", "Majok Yinthiou (Aweil East)", 9.687, 27.773, IOM + " 'Majokyinthiou'", FMR_URL, "Northern Bahr el Ghazal; Warrap",
     "IOM FMP coordinate 8 km north of the COD-AB line (14-mile area)"),
    ("SDN", "Kiir Adem (Aweil North)", 9.686756, 26.819653, IOM + " 'Kiir Adem'", FMR_URL, "Northern Bahr el Ghazal",
     "IOM FMP coordinate 17 km north of the COD-AB line; OSM node 2605745298 (9.7322,26.8153) also on Sudan side"),
    ("SDN", "Kafia Kingi - Raja (Darfur route)", 9.107352, 24.11482, "OSM node 7139460319 (Kafia Kingi)", OSM.format("node/7139460319"),
     "Western Bahr el Ghazal", "Approximate: Darfur arrivals to Raja/Boro Medina; Kafia Kingi enclave is Sudanese-administered"),
    ("ETH", "Pagak (Maiwut)", 8.472993, 34.020029, IOM + " 'Pagak'", FMR_URL, "Upper Nile",
     "OSM node 2616039123 (8.4747,34.0246) agrees within 0.5 km"),
    ("ETH", "Jekow (Maiwut/Longochuk)", 8.394, 33.8, IOM + " 'Jekow'", FMR_URL, "Upper Nile", ""),
    ("ETH", "Burbiey (Luakpiny/Nasir)", 8.425, 33.231, IOM + " 'Burebyei'", FMR_URL, "Upper Nile",
     "Sobat/Baro crossing opposite Matar (Ethiopia, OSM node 2519103796)"),
    ("ETH", "Akobo (Akobo river)", 7.792933, 33.00293, "OSM node 227880231 (Akobo town)", OSM.format("node/227880231"), "Jonglei",
     "Akobo town lies on the Akobo river border with Gambella; largest ET arrivals from Ethiopia"),
    ("ETH", "Pochalla (Akobo river)", 7.183552, 34.09558, "OSM node 241778447 (Pochalla town)", OSM.format("node/241778447"),
     "Jonglei (Greater Pibor AA)", ""),
    ("KEN", "Nadapal (Kapoeta East)", 4.405048, 34.28407, "OSM way 198653244 (Nadapal, Turkana West)", OSM.format("way/198653244"),
     "Eastern Equatoria", "Juba-Kapoeta-Lokichogio road; Wikipedia gives 4.4051,34.2837"),
    ("UGA", "Nimule (Magwi)", 3.571, 32.074, IOM + " 'Nimule Border'", FMR_URL, "Eastern Equatoria; Central Equatoria",
     "Juba-Nimule-Gulu road, main Uganda crossing; OSM Nimule town node 2096234512 (3.5969,32.0601)"),
    ("UGA", "Kerwa (Kajo-Keji)", 3.738, 31.307, IOM + " 'Kerwa'", FMR_URL, "Central Equatoria",
     "IOM FMP coordinate 4.5 km on the Uganda side (Yumbe); OSM Kerwa collection point node 5204416192"),
    ("UGA", "Kaya (Morobo)", 3.54, 30.883, IOM + " 'Kaya'", FMR_URL, "Central Equatoria",
     "Kaya-Oraba crossing (Yei-Arua road); OSM node 2222535628 (3.5470,30.8811)"),
    ("COD", "Bazi (Morobo)", 3.589592, 30.813039, IOM + " 'Bazi'", FMR_URL, "Central Equatoria",
     "Morobo tri-border area facing Aru (DRC); OSM node 1157841250 (3.5993,30.8076)"),
    ("COD", "Gangura (Yambio)", 4.447, 28.486, IOM + " 'Gangura'", FMR_URL, "Western Equatoria", ""),
    ("COD", "Sakure (Nzara)", 4.399194, 28.20958, "OSM node 2604345148", OSM.format("node/2604345148"), "Western Equatoria", ""),
    ("COD", "Nabanga (Ibba/Maridi)", 4.491989, 29.08377, IOM + " 'Nabanga'", FMR_URL, "Western Equatoria", ""),
    ("CAF", "Source Yubu (Tambura)", 5.391, 27.253, IOM + " 'Source Yubu'", FMR_URL, "Western Equatoria",
     "Opposite Bambouti (CAR, OSM node 4419989354, 5.3997,27.2047)"),
    ("CAF", "Ezo (CAR/DRC tri-border)", 5.085704, 27.46671, "OSM node 435516605 (Ezo town)", OSM.format("node/435516605"),
     "Western Equatoria", ""),
]


def main():
    g = gpd.read_file(ROOT / "data/counties.geojson")
    gm = g.to_crs(32636)
    U = gm.union_all()
    inner = U.buffer(-300)
    rows = []
    for iso, name, la, lo, src, url, serves, notes in CROSSINGS:
        p = gpd.GeoSeries([Point(lo, la)], crs=4326).to_crs(32636).iloc[0]
        d = p.distance(U.boundary) / 1000
        if U.contains(p) and d <= 3:
            q, method = p, "source point (inside, <=3 km from border)"
        else:
            q = nearest_points(inner.boundary, p)[0]
            method = ("snapped: source outside COD-AB outline" if not U.contains(p) else "snapped: source >3 km inside")
        snap = p.distance(q) / 1000
        ql = gpd.GeoSeries([q], crs=32636).to_crs(4326).iloc[0]
        cty = gm[gm.contains(q)]
        rows.append(dict(country_iso3=iso, crossing_name=name, lat=round(ql.y, 5), lon=round(ql.x, 5),
                         serves_states=serves, county_pcode=cty.district_id.iloc[0] if len(cty) else "",
                         county_name=cty.name.iloc[0] if len(cty) else "", source_lat=la, source_lon=lo,
                         source_dist_to_border_km=round(d, 1), snap_km=round(snap, 1), method=method,
                         coord_source=src, source_url=url, notes=notes))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(f"{r['country_iso3']} {r['crossing_name']:38} {r['lat']:9} {r['lon']:9} {r['county_name']:15} snap {r['snap_km']} km")


if __name__ == "__main__":
    main()
