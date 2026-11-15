# Validation: Sudd MODIS water / inundation index

Product: `scripts/sudd_water_index.py`. Outputs: `data/processed/sudd_water_county_monthly.csv`,
`sudd_water_8day.csv`, `sudd_water_annual.csv`, `meta/sudd_water.json`, and the overlay `docs/rasters/sudd_inundation/`.
Validation code: `scripts/sudd_water_validate.py`, which writes `data/processed/validation/sudd_water_vs_*.csv`.
Reviewed 15 Nov 2026.

## 1. What is measured

- **Area of interest (AOI).** The 16 counties that overlap the Sudd: Panyijiar, Mayendit, Leer, Guit, Fangak, Ayod,
  Canal/Pigi, Duk, Twic East, Bor South, Yirol East, Awerial, Rubkona, Koch, Nyirol and Uror. Together they cover
  103 478 km². No official outline of the Sudd is openly available. The Ramsar site 1622 is published only as a
  centroid on the RSIS geoserver, and WDPA needs an account. So no total is given for an official core wetland.
  Instead, §5 gives a frequency-based zone computed from this product.
- **Input data.** Terra MOD09A1 v061, 8-day composites at 500 m, tiles h20v08 and h21v08, read from Planetary Computer.
- **Cloud screen.** A pixel counts as clear only if all of these hold:
  - the state QA cloud flag is clear or assumed clear;
  - there is no cloud shadow, no internal cloud flag, and cirrus is none or small;
  - every band used is valid;
  - blue reflectance is below 0.2.
- **Open water.** MNDWI(b4, b6) > 0.
  - A per-scene Otsu threshold was tested and rejected. Water covers less than 2 % of the AOI, so the MNDWI
    histogram has one peak. Otsu then gives −0.39 to −0.43, which falls inside the land mode.
- **Inundation.** Open water, or EVI − LSWI ≤ 0.05 (the flooding signal of Xiao et al. 2006 and Sakamoto et al. 2007).
  - Sakamoto's EVI ≤ 0.3 cap is not applied to the total. On 20 Oct 2020 the cap would cut inundation from
    20 500 km² to 12 000 km², and the removed pixels are visibly flooded swamp in SWIR/NIR/red false colour.
  - The pixels with EVI > 0.3 are reported separately as `dense_floodedveg_observed_km2`.
- **Gap filling.** A cloudy pixel takes its last clear state if that state is at most 3 composites (24 days) old.
  Otherwise it takes the 2018–2025 probability of inundation for that composite of the year, pooled over ±1
  composite.
- **Monthly values.** The mean of the 8-day values, weighted by the number of days each composite has in the month.
  A month is written only if at least 14 of its days are covered.

## 2. Coverage and clouds

- **Missing data.** Composites exist for 348 of the 368 slots in 2018–2025.
  - Planetary Computer has **no MODIS reflectance for 4 Jul – 24 Nov 2025** (day 185–321). This affects Terra,
    Aqua, MCD43A4 and MOD13A1. Those 18 composites are listed as `none` in `sudd_water_8day.csv`.
  - So 2025-07 to 2025-11 are not written, and the 2025 peak is based on 25 Nov – Dec only.
  - Two composites are also missing on 3–18 Dec 2022. Dec 2022 is still written because it has 15 days of data.
- **Substituted data.** 12 Terra tile-composites are missing: Sep–Oct 2022, Jan 2023 and Nov 2023. MCD43A4 NBAR
  replaces them, using only pixels with BRDF quality 0.
  - On a test date with both products (1 Nov 2021), they agreed on 99.8 % of pixels for open water and 92 % for
    inundation. NBAR gave 27 % less inundated area.
  - Aqua is unusable: band 6 is 55 % fill over the AOI.
  - Because of NBAR, Oct 2022 is conservative. Its clear share is only 13 %.
- **Clear share of the AOI per composite (mean by month):**

| | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| observed | 0.99 | 0.98 | 0.93 | 0.91 | 0.80 | 0.72 | 0.61 | 0.66 | 0.72 | 0.73 | 0.92 | 0.98 |
| carried (≤24 d) | 0.01 | 0.02 | 0.07 | 0.09 | 0.20 | 0.27 | 0.36 | 0.31 | 0.27 | 0.23 | 0.08 | 0.02 |
| climatology | 0 | 0 | 0 | 0 | 0 | 0.01 | 0.03 | 0.03 | 0.01 | 0.05 | 0 | 0 |

- **Overall gap filling.** Across all composites, 83.4 % of AOI pixels are observed, 15.7 % are carried forward and
  0.9 % come from climatology.
- **Cloudy composites.** In Jun–Oct, 24 % of composites have less than half of the AOI clear. The minimum clear share
  is 0.2 %, in an NBAR-substituted composite in Oct 2022.

## 3. Annual extent (AOI, km²)

- **Peak** is the maximum over Sep–Dec of the 3-composite running median. The raw single-composite maximum is in brackets.
- **Low** is the minimum over Mar–May of the same running median.

| year | peak inundation | peak date | peak open water | low inundation | low open water |
|---|---|---|---|---|---|
| 2018 | 6 886 (8 384) | 22 Sep | 151 | 808 | 76 |
| 2019 | 20 895 (20 895) | 6 Sep | 186 | 836 | 77 |
| 2020 | 24 559 (24 893) | 29 Sep | 257 | 697 | 37 |
| 2021 | 26 495 (27 713) | 22 Sep | 413 | 3 045 | 84 |
| 2022 | 25 811 (27 848) | 6 Sep | 1 271 | 5 945 | 303 |
| 2023 | 16 034 (18 475) | 3 Dec | 1 813 | 6 485 | 895 |
| 2024 | 24 776 (25 490) | 13 Sep | 2 225 | 6 882 | 974 |
| 2025 | 19 183 (19 488), Dec only, incomplete | 3 Dec | 2 522 | 8 294 | 1 540 |

The 2019–2022 high-flow sequence and the 2024 flood both appear. Dry-season water left over from these floods rises
from about 0.7–0.8 thousand km² (2018–2020) to 6–8 thousand km² (2022–2025). Over the same years, persistent open water
grows from about 40–80 km² to about 1 500 km², mostly as the flood lakes around Bentiu, Rubkona and Guit (visible in
`docs/rasters/sudd_inundation/2024-03.png`).

## 4. Comparison with other sources

**UNOSAT VIIRS "maximum flood water extent".** These are county (Admin-2) tables, 40 dates from Sep 2022 to Apr 2025,
summed over the 16 counties. Each date is compared with our 8-day composite that contains the middle of the UNOSAT window.
In the 2023–2025 tables, four counties are spelled differently and were matched by name: Old Fangak, Peji, Wuror and
Payinjar.

| subset | n dates | Pearson r | median MODIS/UNOSAT | median abs. error |
|---|---|---|---|---|
| all | 40 | 0.61 (Spearman 0.62) | **0.99** | 15 % |
| composites ≥ 70 % clear | 30 | 0.58 | 0.99 | 17 % |
| dry season (Dec–Jun) | 21 | 0.78 | 0.87 | — |
| wet season (Jul–Nov) | 19 | 0.14 | 1.05 | — |
| county × date pairs | 640 | 0.81 (Spearman 0.80) | — | — |

- **Size agreement.** The areas agree in magnitude, unlike the national MNDWI layer, which is about 0.5× UNOSAT. The
  median correlation per county over time is 0.54.
  - Within the wet season the totals sit on a plateau of about 17–25 thousand km² in both products, and the
    timing within that plateau does not match (r 0.14).
- **Open water.** Open water alone is only 0.11× UNOSAT. UNOSAT's "water" is mostly vegetated swamp.

**Sentinel-1 flood (`flood_s1_flood_km2`).** S1 measures flooding beyond the March reference state, so it is compared
with our inundation minus each county's mean March inundation over 2018–2025. The comparison uses 16-county monthly
totals over 91 months:

- r = **0.82** (Spearman 0.75). The r against raw inundation is 0.77. For county × month pairs, r = 0.66 (n = 1 456).
- **Sep–Dec maxima, our anomaly vs S1:**
  - 2018: 2.9 vs 4.1 thousand km²
  - 2019: 16.6 vs 6.4
  - 2020: 17.2 vs 16.5
  - 2021: 18.9 vs 15.2
  - 2022: 18.0 vs 19.0
  - 2023: 9.8 vs 9.3
  - 2024: 17.1 vs 13.4
  - The correlation across years is r = 0.70. 2025 is excluded because our Sep–Nov is missing.
- **2019 is the main disagreement.** MODIS shows large wet-season inundation in Uror (6 800 km²) and Ayod. The
  national MNDWI layer agrees: 8 200 km² in Uror in Aug 2019. These are rain-fed sheet floods on the eastern clay
  plains, which the S1 VV−VH change rule picks up only weakly.

**National MODIS MNDWI (`surface_water_km2`, same 16 counties).**
- r with our inundation is 0.84; r with our open water is 0.44.
- National MNDWI (B7, threshold > 0.1) sits between our open-water class and our inundation class. Its mean
  September value is 8 000 km², against 588 km² of open water and 18 100 km² of inundation in our product.

## 5. Comparison with published Sudd extents

- **Peaks.** Published estimates for the whole Sudd in high-flow years such as 2020–2022 are about 30 000–40 000 km²
  at peak. This is the reference range from the project brief, citing Sosnowski et al. 2016 and Di Vittorio &
  Georgakakos 2018. We did not re-extract numbers from those papers.
  - Our 16-county AOI peaks at 24 600–26 500 km² in 2020–2022, which is 0.65–0.85 of that range.
  - The AOI leaves out swamp in Panyikang, Malakal, Mayom, Abiemnhom and the Bahr el Ghazal/Zeraf fringes.
  - MODIS 500 m also misses narrow channels and dense papyrus.
  - So the shortfall is expected, and the inter-annual ranking matches: 2018 ≪ 2019 < 2020–2022, a 2023 dip, and
    2024 high.
- **Frequency zones** (share of clear 8-day observations 2018–2025 classed inundated, from
  `data/raw/sudd_water/sudd_inundation_frequency_2018_2025.tif`):

| zone | area |
|---|---|
| inundated in ≥ 10 % of clear observations | 27 717 km² |
| inundated in ≥ 25 % | 12 804 km² |
| inundated in ≥ 50 % | 3 118 km² |
| inundated in ≥ 75 % | 792 km² |
| open water in ≥ 50 % | 90 km² |

  The ≥ 25 % zone (12 800 km²) is the closest internal stand-in for a "core wetland". Published permanent-swamp
  figures are larger, around 10 000–16 000 km² (the commonly cited 1980s Landsat-era range). Our ≥ 50 % zone is far
  smaller than that.

## 6. Caveats

- **Dense papyrus or Typha in the dry season is not flagged.** Under a closed green canopy, EVI exceeds LSWI by more
  than 0.05. So dry-season "low" values (0.7–8 thousand km²) measure the surface-water signal MODIS can detect, not
  the full permanent swamp.
- **Wet-season composites are 30–40 % gap-filled.** Most of this is carry-forward. Climatology fill is at most 5 %
  of a month on average, but 27 % in Oct 2022.
- **Single 8-day values are noisy.** The swing is ±20–30 % because of view-angle and best-pixel compositing.
  Use the monthly values or the running-median peaks.
- **Missing periods:**
  - 2025-07 to 2025-11 are missing. The 2025 peak is Dec only (`peak_complete = False`).
  - Sep–Oct 2022 is partly NBAR, which has a −27 % bias on the test date.
- **Wet green grassland can trigger the rule.** In heavy-rain years (2019 Uror) the EVI−LSWI rule also flags
  rain-fed sheet water and saturated clay plains. This is real surface water, but it is not river-fed Sudd flooding.
