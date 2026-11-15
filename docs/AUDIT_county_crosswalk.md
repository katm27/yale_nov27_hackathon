# County (admin-2) crosswalk audit

Audited 15 Nov 2026. Gold standard: `data/counties.geojson` = OCHA COD-AB v03, 79 counties incl. Abyei `SS0001`
(`district_id`, `name`, `admin1`). Not modified.

## Deliverables

| File | What |
|---|---|
| `data/crosswalks/county_crosswalk_master.csv` | One row per OCHA county. Columns: IOM P-code, other codes (`SS1101`, `SS0807`, `SD19001`), pre-2015 OCHA numeric code (HNO 2019, e.g. `9202` = Juba), 2020 administrative area, and every name variant seen in IOM DTM (MT/ET/FMR), OCHA (HNO/3W/HAPI), ACLED, IPC, WFP (admin2 label + markets), WHO (immunization 2018, MFL 2025), SSSAMS 2015, UNHCR camps, GADM 4.1 overlap, curated aliases and sub-area notes. Rebuilt from raw files by `scripts/build_county_crosswalk.py`. |
| `data/crosswalks/county_multi_unit_aliases.csv` | Names that cover more than one county (Ruweng AA, Greater Pibor AA, `SS0305/SS0310`). They are never resolved to a single county. |
| `data/crosswalks/gadm41_overlap.csv` | Area overlap between GADM 4.1 SSD level 2 and the OCHA counties. |
| `scripts/county_crosswalk.py` | Helper functions: `to_ocha(code_or_name, source)`, `to_ocha_multi(name)` and `norm(name)`. `human_common.fix_pcode` now uses it. |
| `data/crosswalks/border_crossings.csv` | 23 verified entry points for cross-border arrows, built by `scripts/build_border_crossings.py`. |

## Code systems: findings

* **IOM DTM uses the OCHA admin-2 numbering for all 78 non-Abyei counties.** I checked the name against the code for every
  (code, name) pair in Mobility Tracking R2–R16, Event Tracking 2020–2026 (event, origin and next locations) and FMR. None
  is wrong. The only differences are spellings: `Mayiendit`, `Panyijar` and `Pariang (Ruweng)`. Abyei is `SS1101` in IOM
  files and `SS0001` in COD-AB v03. The IOM ET 2024 export replaces spaces with "Other Admin 2" (for example
  `KapoetaOther Admin 2East`); `norm()` strips this.
* **OCHA HNO 2019 uses the pre-2015 numeric codes.** Examples: `7101` = Renk, `8101` = Abyei (listed under Warrap) and
  `9202` = Juba. These codes are not related to the current `SSxxyy` codes. The pipeline joins HNO 2019 by name, so no
  data was mis-joined. The codes are kept in the `ocha_numeric_code_pre2015` column.
* **`SS0807` = Abyei** in the HNO 2023 PiN/severity files and the 3W 2021–2022 files, where Abyei is listed under Warrap.
  Joining `SS0807` as a Warrap county would be wrong. It is mapped to `SS0001`.
* **ACLED** puts the Abyei Area under Sudan (Admin1/Admin2 "Abyei", `SD19001`). Its SSD admin-2 codes equal OCHA's. Its
  name variants are Kajo Keji, Panriang, Longchuk and Anzara.
* **HDX HAPI** (humanitarian needs, food security, IDPs) leaves `admin2_code` **blank for Abyei**. Only
  `provider_admin2_name` = "Abyei Region" identifies it. This caused one of the bugs below.
* **GADM 4.1 SSD level 2 is not a county layer.** It has 45 units, the pre-2011 Sudan-era provinces (BahrAlJabal,
  NahrYei, AlLeiri, Tonga …), and Abyei is not a separate unit. No pipeline uses GADM. The overlap table is for
  reference only.
* **Drive boundary file**: `data/drive_mirror/02_boundaries/boundaries_south_sudan_counties_79.geojson` matches
  `counties.geojson` exactly (IoU = 1.000 for all 79). No source in the project uses non-COD-AB-v03 county geometry.
  ACLED's own admin-2 polygons are not used.

## 2015–2020 states and 2020 administrative areas

* **28 states (Oct 2015) and 32 states (Jan 2017) were in place until 22 Feb 2020.** They came with many new counties
  (more than 180), and some of their boundaries split the old counties. **No source used here reports at 28/32-state
  units or at the split counties.** ACLED (including the weekly admin-1 export), IOM DTM, OCHA HNO/3W/HAPI, IPC, WFP,
  WHO, SSSAMS 2015 and UNHCR all report at the 10 states plus the 78/79 counties. That includes their 2015–2020 releases,
  because these agencies kept the 10-state/79-county COD for humanitarian work. For this reason the crosswalk does not
  map counties to 28/32-state names.
* **Administrative areas created in Feb 2020** (recorded in the `admin_area_2020` column):
  * Abyei Administrative Area = `SS0001`.
  * Greater Pibor AA = Pibor `SS0308` + Pochalla `SS0309`. GPAA was set up from these two counties in 2014, absorbed into
    Boma State in 2015 and re-created in 2020.
  * Ruweng AA = Pariang `SS0608` + Abiemnhom `SS0601`.
* **Sources that report at administrative-area level:**
  * Insecurity Insight (Admin 1 only) reports "Greater Pibor Administrative Area", "Ruweng Administrative Area" and
    "Abyei". These rows are kept national/state level and never split to counties. The point centroid for GPAA uses Pibor
    only.
  * DTM labels Pariang "Pariang (Ruweng)", and SSSAMS 2015 calls it "Ruweng". In both cases this is the county, not the
    AA.
* **Sub-county or merged units:**
  * IPC (2023+), WHO immunization 2018 and SSSAMS report **Akoka** separately. Akoka is payam `SS070103` of Baliet
    (checked in the DTM R14 location list), so it is summed into Baliet.
  * IPC analyses "**Wau (Rural Only)**" from Sep 2018. Wau town is not in the county figure.
  * WHO uses "KHORFLUS" (the Canal/Pigi HQ, Khorfulus) and "OLD FANGAK" (Fangak).
  * "Boma" in IOM data is the Pibor payam `SS030801`, not Boma State.
  * ET 2020 has one combined origin, `SS0305/SS0310` (Duk/Twic East).

## Per-source audit

Match rates are for 2018–2025 unless noted. "Gold" means the code is in the 79-county gold set and its name agrees.

| Source / pipeline | Join method | Match rate | Issues found → fix | Residual caveats |
|---|---|---|---|---|
| ACLED admin-2 (`acled_ssd.py`) | ACLED pcode, accepted only when the name agrees (crosswalk); Abyei from the Sudan file | 79/79 admin-2 rows; 100% of events. PV 10,313 = 9,984 SSD + 329 Abyei; civ 5,751; fatalities 22,794 / 9,899 | None. NAME_FIX replaced by `to_ocha` (identical output) | ACLED event geolocation is ACLED's own. Abyei is Sudan-coded |
| ACLED weekly admin-1 (`acled_state_weekly.py`) | 10 state names exact | 100% | None | Abyei not in SSD export; values are state totals |
| DTM Mobility Tracking (`dtm_ssd.py`) | IOM county P-code (R4–R16); names for R2 | 100% of county rows; only "Total" rows dropped; R2 46/46 names | Valid-but-wrong codes: **none**. Inline alias dicts replaced by crosswalk (identical output) | MT covers 78 counties (no Abyei); R4 covers 68 counties, R2 covers 46 |
| DTM Event Tracking (`dtm_ssd.py`, `dtm_et_*`) | Event-location P-code (SS1101→SS0001); names for 2020 rows | 4,976 rows, 0 unmatched | None | The year filter drops late-reported prior-year events (e.g. 2021 file: Fangak Oct-2020 32,286; Tonj N Dec-2020 19,757; Juba Dec-2020 11,555). This is a dedupe choice, not a join error. The team `et_*` series keeps some of them |
| ET O-D flows (`build_et_flows.py` → `flows/et_flows.csv`) | Destination + origin P-code; foreign origin → ISO3 | **Before: 98.67%** (5,253,989 / 5,324,800 people). **After: 99.38%** (5,291,661) | (1) 2020 file foreign codes with ISO3 prefixes `COD5306`, `COD5307`, `CAF632` were dropped (5,012 people). Fix: `foreign_of()` handles ISO2 and ISO3 prefixes. COD now 11,548 (incl. Morobo 6,473); CAF now 2,308 (incl. Tambura 1,688). (2) Combined origin `SS0305/SS0310` (Duk/Twic East → Awerial, Aug 2020, 32,660) was dropped. Fix: split 50/50, `quality=split_combined_origin` | 33,139 people with blank or "other" origin are still dropped (mainly Juba Sep 2020, 22,445). Destination totals still equal the team `et_ind_total` |
| DTM MT O-D stocks (`fetch_flows_dtm_mt_od.py`) | Destination IOM P-code; origin county names | All SS origin names matched (233 distinct). Dropped: blank/unknown origin 1.42 M IDP + 1.18 M returnee cohort-individuals (all rounds); foreign origins (Khartoum, Gambella, Arua …) are not output | ALIASES replaced by `to_ocha` (identical output) | Majority-origin attribution (see script docstring) |
| Renk intentions (`fetch_flows_dtm_renk_intentions.py`) | Destination county name | 37 counties, 0 unmatched | → `to_ocha` (identical) | Sample survey |
| FMR (team unified, `convert_unified_dataset.py`) | `dep/dest.adm2.pcode` (names agree) | 152,970 of 153,020 between-county travellers (50 lack codes) | **FMR point "Renk River Port (Renk Mina Port)" (11.761, 32.780) was assigned to Manyo `SS0708`** because it sits a few hundred metres west of the COD-AB river line. Fix: moved to Renk `SS0711` in `fmr_monitoring_points_in_county` (13 months, `convert_unified_dataset.py`) and in the time-dynamic `docs/data/points_fmr_monitoring.geojson` (`scripts/points_fmr.py`) | Wau bus-station points fall in Jur River and Aweil Bus Park in Aweil West. The COD-AB lines cut through these towns, and the points were left as is |
| OCHA HNO PiN / severity (`ocha_hum_ssd.py`) | 2019 and 2024 by name; 2021–2023 by P-code (`SS0807`→`SS0001`); 2024–25 HAPI code | 2019/21/22: 78 counties (no Abyei value in source); 2023: 79; **2024/25: was 78, now 79** | **HAPI Abyei row has a blank `admin2_code` and was dropped (PiN 100,873 in 2024 and 100,728 in 2025).** Fix: fall back to `provider_admin2_name`. National 2024 sum 8,446,111 → 8,546,984 (= HAPI admin-0 8,546,986) | HNO methods differ between years |
| OCHA 3W (`ocha_hum_ssd.py`) | 2021–22 P-code; other years county name | 0 unmatched rows | None | Reporting coverage grows over time |
| IPC (`ipc_ssd.py`) | Area name → crosswalk | All areas except the non-geographic "Returnees" group (280,000 Sep 2023; 629,606 Sep 2024) | Akoka→Baliet checked (payam of Baliet). ALIAS replaced by `to_ocha` (identical) | Wau = rural only from Sep 2018. Abyei not in the IPC global file 2017–2022 or the Sep 2025 analysis. Some analyses miss 1–5 counties |
| UNHCR (`unhcr_ssd.py`) | Curated camp → county | 100% of REF+ASY except 6,170 reported at NBeG state level in 2023 | Checked against camp, market and health points: Maban camps, Ajuong Thok/Pamir/Yida (Pariang), Gorom (Juba), Makpandu (Yambio), Wedwil (Aweil West, 27.19 E 9.00 N). OK | 2023 NBeG state-level rows unallocated |
| WFP prices (`wfp_prices_ssd.py`) | Spatial (market lat/lon) | All markets | 1 disagreement: WFP labels the "Abyei" market admin2 = Twic, but its coordinates are in the Abyei Area. Spatial result (SS0001) kept | 12–32 market counties |
| WHO immunization 2018 (`public_health.py`) | Name → crosswalk | 80 admin-2 → 79 (Akoka+Baliet) | FIX dict replaced by `to_ocha` (identical) | Panyikang has negative numerators in the source, so it is missing |
| WHO MFL 2025 (`health_facilities.py`) | Source `county_code` | 1,988/1,988 codes are gold; name agrees for all | None. 94.5% of 1,875 geolocated facilities fall inside their coded county | Code-based counts kept |
| SSSAMS 2015 (`education.py`) | Spatial first, name fallback | 0 of 4,881 unassigned | NAME_FIX replaced by `to_ocha` (identical) | 2015 snapshot |
| Point layers (UCDP, UNMISS, crisis sites, oil, ethnic, health/schools points) | Spatial (`sjoin`, nearest within 20 km) | Spot-checked: UNMISS 21 sites and 30 crisis sites all in the expected county (Bentiu→Rubkona, Kodok→Fashoda, Mingkaman→Awerial …) | None | — |
| Team unified dataset `et_*` / `fmr_*` (`convert_unified_dataset.py`) | Supplied OCHA P-codes | 79/79 + national "SS" | Renk River Port fix (see FMR above) | 2026 rows not in app window |

**Re-run:** `ocha_hum`, `ipc`, `acled`, `dtm`, `public_health`, `education`, `unified`, the three DTM flow builders and
`et_flows` were all re-run (each ends with `write_trends`). Apart from the fixes listed above, every county-month value is
unchanged after the move to the shared crosswalk.

## Cross-border entry points (`data/crosswalks/border_crossings.csv`)

**Source coordinates** come from two places:
* IOM DTM FMR monitoring points in the team unified dataset: Wunthou/Joda, Kiir Adem, Majok Yinthiou, Pagak, Jekow,
  Burbiey, Nimule, Kerwa, Kaya, Bazi, Gangura, Nabanga, Source Yubu.
* OpenStreetMap nodes found by name (node ids are in `coord_source`/`source_url`): Kuek, Yabus, Jau, Diffra, Kafia Kingi,
  Akobo, Pochalla, Nadapal, Sakure, Ezo.

**Map coordinates (`lat`/`lon`)** follow one rule:
* A point inside South Sudan and within 3 km of the COD-AB border is kept.
* Any other point is moved to the nearest COD-AB border point, 300 m inside. `snap_km` gives the distance moved.

Several IOM FMP coordinates lie 4–18 km on the far side of the drawn border because the COD-AB line differs from the
ground border: Wunthou 14.6 km, Kiir Adem 17.6 km and Majok Yinthiou 8.5 km (the 14-mile area), and Kerwa 4.8 km.

**Points that are approximate:**
* Yabus–Maban and Kafia Kingi–Raja are snapped from Sudan-side or enclave towns (route markers, not named border posts).
* Diffra marks the north edge of the Abyei Area. The IOM point "Abyei Amieth" is 52 km inside, so it was not used.

**Rejected points:**
* Abaya (30 km inside Uganda).
* Ngomoromo (the OSM node is 30 km from the border).
* Sopo (85 km inside).
* Panakuach: no public coordinate could be verified. Unity arrivals use Jau.

**Foreign origins in `flows/*.csv`:** only `et_flows.csv` has them. FMR, MT and Renk flows are SSD-to-SSD only.

| Origin | People (ET 2020-01..2026-09) | Main destinations | Crossings to use |
|---|---|---|---|
| SDN | 667,274 | Juba 136k, Renk 98k, Rubkona 69k, Malakal 52k, Wau 45k, Raja 27k, Maban 26k, Abyei 20k, Fangak 19k, Aweil E/W/N 17k each | Joda/Wunthou (Upper Nile, and onward to Juba/Malakal/Fangak), Jau (Unity), Diffra (Abyei), Majok Yinthiou / Kiir Adem (NBeG, Warrap), Kafia Kingi (Raja), Yabus (Maban) |
| ETH | 156,387 | Akobo 119k, Nasir 17k, Ulang 10k, Maiwut 9k | Akobo, Burbiey, Jekow, Pagak |
| UGA | 69,170 | Magwi 26k, Morobo 25k, Kajo-Keji 11k, Ikotos/Torit/Lafon | Nimule, Kaya, Kerwa |
| COD | 11,548 | Morobo 6.5k, Yei 4.5k, Ibba 0.6k | Bazi, Nabanga |
| KEN | 5,108 | Torit, Ikotos, Lafon, Budi, Kapoeta S | Nadapal |
| CAF | 2,308 | Tambura 1.7k, Raja 0.6k | Source Yubu (Tambura); none verified for Raja, so use Kafia Kingi/Raja with a note |

Sudan arrivals that reach Juba, Wau or Malakal are recorded at the county of assessment. The ET data does not give the
crossing used. Joda/Wunthou → Renk is the dominant corridor (IOM/UNHCR), which makes it the sensible default origin for
SDN arrows into counties with no nearer crossing.

## Residual issues / not fixed

* The ET year-filter dedupe (see the table) under-counts some late-reported 2020 events compared with the team series.
* Abyei has no IPC data for 2017–2022, no HNO PiN for 2019/2021/2022, and no DTM MT data. These gaps are in the source
  data, not join errors.
* Some foreign origin codes in IOM ET carry no country column. They are classified by code prefix.
* `convert_unified_dataset.py` still writes a plain `points_fmr_monitoring.geojson` and `points.json` entry. Run `scripts/points_fmr.py` after it, or the time-dynamic layer is replaced.
* The app's `docs/data/*` needs `scripts/build_web_data.py` to be re-run to pick up the changed processed files.
