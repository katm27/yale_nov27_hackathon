"""Static county context layers for South Sudan (single value per county, date 2018-07-01).

Soil      : ISRIC SoilGrids 2.0 (250 m, files.isric.org VRTs, read at 1 km by decimation)
            topsoil 0-30 cm depth-weighted means of clay, sand, soil organic carbon, pH(H2O);
            WRB most-probable reference soil group -> dominant group code + Vertisol share.
Biodiversity: BiodiversityMapping.org 10 km species-richness rasters (Jenkins, Pimm et al.; from IUCN
            range maps for amphibians and mammals, BirdLife ranges for birds), county mean richness.
Elevation : Copernicus DEM GLO-90 (Planetary Computer), county mean and std.

Usage: python scripts/static_pipeline.py
"""
import os
os.environ["CPL_VSIL_CURL_ALLOWED_EXTENSIONS"] = ".tif,.TIF,.tiff,.vrt"
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import planetary_computer as pc
from rasterio.enums import Resampling
from rasterio.merge import merge

sys.path.insert(0, str(Path(__file__).parent))
import hazards_common as hc

OUT = hc.PROC / "static_county.csv"
SG = "/vsicurl/https://files.isric.org/soilgrids/latest/data"
BM_ZIP = hc.REPO / "data" / "raw" / "biodiversity" / "bm_tiffs.zip"
BM_URL = "https://biodiversitymapping.org/wp-content/uploads/2020/02/BiodiversityMapping_TIFFs_2019_03d14_revised.zip"
WRB = ["Acrisols", "Albeluvisols", "Alisols", "Andosols", "Arenosols", "Calcisols", "Cambisols", "Chernozems",
       "Cryosols", "Durisols", "Ferralsols", "Fluvisols", "Gleysols", "Gypsisols", "Histosols", "Kastanozems",
       "Leptosols", "Lixisols", "Luvisols", "Nitisols", "Phaeozems", "Planosols", "Plinthosols", "Podzols",
       "Regosols", "Solonchaks", "Solonetz", "Stagnosols", "Umbrisols", "Vertisols"]


CACHE = Path(os.environ.get("STATIC_CACHE", "/tmp/static_pipeline_cache"))


def read_bbox(path, factor=1, resampling=Resampling.nearest):
    """Window read with retries; remote reads are cached as .npz (SoilGrids tiles sometimes truncate)."""
    import pickle, time
    key = CACHE / (str(path).replace("/", "_").replace(":", "") + f"_{factor}.pkl")
    if key.exists():
        return pickle.loads(key.read_bytes())
    for attempt in range(6):
        try:
            res = _read_bbox(path, factor, resampling)
            CACHE.mkdir(parents=True, exist_ok=True)
            key.write_bytes(pickle.dumps(res))
            return res
        except rasterio.errors.RasterioIOError as e:
            print("retry", path, attempt, str(e)[:80], flush=True)
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"failed reading {path}")


def _read_bbox(path, factor=1, resampling=Resampling.nearest):
    with rasterio.open(path) as src:
        win = hc.window_for_bbox(src)
        shape = (max(1, int(win.height // factor)), max(1, int(win.width // factor)))
        a = src.read(1, window=win, out_shape=shape, resampling=resampling, masked=True)
        tr = src.window_transform(win) * rasterio.Affine.scale(win.width / shape[1], win.height / shape[0])
        return a, tr, src.crs


def zonal_mean(a, tr, crs, scale=1.0):
    lab = hc.labels_for(crs, tr, a.shape, all_touched=True)
    valid = ~np.ma.getmaskarray(a)
    s = hc.bincount(lab, np.where(valid, a.filled(0), 0).astype("float64"))
    n = hc.bincount(lab, valid)
    return np.where(n > 0, s / np.maximum(n, 1) * scale, np.nan), n


def main():
    ids = hc.county_ids()
    vals = {}
    # ---------------- soil
    weights = {"0-5cm": 5, "5-15cm": 10, "15-30cm": 15}
    for prop, scale in [("clay", 0.1), ("sand", 0.1), ("soc", 0.1), ("phh2o", 0.1)]:
        acc = 0
        for d, w in weights.items():
            a, tr, crs = read_bbox(f"{SG}/{prop}/{prop}_{d}_mean.vrt", factor=4)
            a = np.ma.masked_where(np.ma.getmaskarray(a) | (a.filled(0) <= 0), a)
            m, n = zonal_mean(a, tr, crs, scale)
            acc = acc + w * m
            print(prop, d, "done", flush=True)
        vals[f"soil_{prop}_0_30cm"] = acc / sum(weights.values())
    a, tr, crs = read_bbox(f"{SG}/wrb/MostProbable.vrt", factor=4)
    lab = hc.labels_for(crs, tr, a.shape, all_touched=True)
    valid = ~np.ma.getmaskarray(a) & (a.filled(255) < len(WRB))
    counts = np.zeros((len(ids) + 1, len(WRB)))
    for c in range(len(WRB)):
        counts[:, c] = hc.bincount(lab, valid & (a.filled(255) == c))
    tot = counts.sum(1)
    vals["soil_wrb_dominant"] = np.where(tot > 0, counts.argmax(1), np.nan)
    vals["soil_vertisol_pct"] = np.where(tot > 0, 100 * counts[:, WRB.index("Vertisols")] / np.maximum(tot, 1), np.nan)
    print("wrb done", flush=True)
    # ---------------- biodiversity
    bm_dir = BM_ZIP.parent / "extracted"
    if not bm_dir.exists():
        if not BM_ZIP.exists():
            import urllib.request
            req = urllib.request.Request(BM_URL, headers={"User-Agent": "Mozilla/5.0"})
            BM_ZIP.write_bytes(urllib.request.urlopen(req).read())
        with zipfile.ZipFile(BM_ZIP) as z:
            z.extractall(bm_dir)
    base = next(bm_dir.glob("BiodiversityMapping_TIFFs_*"))
    layers = {
        "richness_amphibians": base / "Amphibians/Richness_10km_AMPHIBIANS_dec2017_EckertIV.tif",
        "richness_birds": base / "Birds/Richness_10km_Birds_v7_EckertIV_no_seabirds.tif",
        "richness_mammals": base / "Mammals/Richness_10km_MAMMALS_mar2018_EckertIV.tif",
        "richness_threatened_birds": base / "Birds/Richness_10km_Birds_v7_EckertIV_threatened_no_seabirds.tif",
        "richness_threatened_mammals": base / "Mammals/Richness_10km_MAMMALS_mar2018_EckertIV_threatened.tif",
    }
    for k, p in layers.items():
        a, tr, crs = read_bbox(p)
        a = a.astype("float32")
        a = np.ma.masked_where(np.ma.getmaskarray(a) | (a.filled(-1) < 0), a)
        vals[k], _ = zonal_mean(a, tr, crs)
        print(k, "done", flush=True)
    vals["richness_vertebrates"] = vals["richness_amphibians"] + vals["richness_birds"] + vals["richness_mammals"]
    # ---------------- elevation (Copernicus DEM 90 m, read at ~360 m)
    items = hc.search("cop-dem-glo-90", None)
    srcs = [rasterio.open(pc.sign(it.assets["data"].href.split("?")[0])) for it in items]
    b = hc.counties().total_bounds
    dem, tr = merge(srcs, bounds=(b[0] - .05, b[1] - .05, b[2] + .05, b[3] + .05), res=1 / 300, nodata=-32767,
                    resampling=Resampling.average)
    crs = srcs[0].crs
    dem = np.ma.masked_equal(dem[0], -32767)
    m, n = zonal_mean(dem, tr, crs)
    lab = hc.labels_for(crs, tr, dem.shape, all_touched=True)
    sq = hc.bincount(lab, np.where(~np.ma.getmaskarray(dem), dem.filled(0).astype("float64") ** 2, 0))
    vals["elevation_mean"] = m
    vals["elevation_std"] = np.sqrt(np.maximum(sq / np.maximum(n, 1) - m ** 2, 0))
    print("dem done", len(items), "tiles", flush=True)

    rows = []
    for k, v in vals.items():
        for i, cid in enumerate(ids, start=1):
            if np.isfinite(v[i]):
                rows.append((cid, "2018-07-01", k, round(float(v[i]), 3)))
    df = pd.DataFrame(rows, columns=["county_id", "date", "variable", "value"]).sort_values(["variable", "county_id"])
    df.to_csv(OUT, index=False)

    sg = dict(category="environment", group="Soil", source="ISRIC SoilGrids 2.0", temporal="static", index_ok=False,
              source_url="https://files.isric.org/soilgrids/latest/data/", raster=None,
              native_resolution="250 m (read at 1 km by nearest-neighbour decimation)")
    wrb_codes = ", ".join(f"{i}={n}" for i, n in enumerate(WRB))
    bm = dict(category="environment", group="Biodiversity", temporal="static", index_ok=False, raster=None,
              source="BiodiversityMapping.org (Jenkins, Pimm & Joppa 2013; IUCN + BirdLife range maps, 2017-2019 versions)",
              source_url="https://biodiversitymapping.org/index.php/download/", native_resolution="10 km",
              higher_is="better")
    meta = [
        dict(id="soil_clay_0_30cm", label="Topsoil clay content", units="% (mass)", aggregation="county mean of 0-30 cm depth-weighted clay", higher_is="neutral",
             notes="High clay (Vertisols, 'black cotton' soils) = waterlogging/flood-prone plains.", **sg),
        dict(id="soil_sand_0_30cm", label="Topsoil sand content", units="% (mass)", aggregation="county mean, 0-30 cm depth-weighted", higher_is="neutral", notes="", **sg),
        dict(id="soil_soc_0_30cm", label="Topsoil organic carbon", units="g/kg", aggregation="county mean, 0-30 cm depth-weighted", higher_is="better", notes="", **sg),
        dict(id="soil_phh2o_0_30cm", label="Topsoil pH (H2O)", units="pH", aggregation="county mean, 0-30 cm depth-weighted", higher_is="neutral", notes="", **sg),
        dict(id="soil_wrb_dominant", label="Dominant soil group (WRB)", units="class code", aggregation="most frequent SoilGrids WRB most-probable class in county",
             higher_is="neutral", notes="Categorical code: " + wrb_codes, **sg),
        dict(id="soil_vertisol_pct", label="Vertisol share", units="% of county", aggregation="share of 1 km cells whose most probable WRB group is Vertisols",
             higher_is="neutral", notes="Cracking clay soils, seasonally flooded; agriculturally productive but hard to work.", **sg),
        dict(id="richness_amphibians", label="Amphibian species richness", units="species (mean per 10 km cell)", aggregation="county mean of 10 km richness cells", notes="IUCN range-map based (Dec 2017).", **bm),
        dict(id="richness_birds", label="Bird species richness", units="species (mean per 10 km cell)", aggregation="county mean of 10 km richness cells", notes="BirdLife range maps v7, excl. seabirds.", **bm),
        dict(id="richness_mammals", label="Mammal species richness", units="species (mean per 10 km cell)", aggregation="county mean of 10 km richness cells", notes="IUCN range maps (Mar 2018).", **bm),
        dict(id="richness_threatened_birds", label="Threatened bird species", units="species (mean per 10 km cell)", aggregation="county mean", notes="IUCN threatened categories.", **bm),
        dict(id="richness_threatened_mammals", label="Threatened mammal species", units="species (mean per 10 km cell)", aggregation="county mean", notes="IUCN threatened categories.", **bm),
        dict(id="richness_vertebrates", label="Vertebrate species richness (amphibians+birds+mammals)", units="species (mean per 10 km cell)", aggregation="sum of the three county means",
             notes="Reptiles not included (not in the downloadable package). Range-map richness = potential, not observed, species.", **bm),
        dict(id="elevation_mean", label="Mean elevation", units="m", category="environment", group="Terrain", source="Copernicus DEM GLO-90 via Microsoft Planetary Computer",
             source_url="https://planetarycomputer.microsoft.com/dataset/cop-dem-glo-90", native_resolution="90 m (read at ~370 m, average)", temporal="static",
             aggregation="county mean", higher_is="neutral", index_ok=False, raster=None, notes=""),
        dict(id="elevation_std", label="Terrain ruggedness (elevation std)", units="m", category="environment", group="Terrain", source="Copernicus DEM GLO-90 via Microsoft Planetary Computer",
             source_url="https://planetarycomputer.microsoft.com/dataset/cop-dem-glo-90", native_resolution="90 m (read at ~370 m, average)", temporal="static",
             aggregation="standard deviation of elevation within county", higher_is="neutral", index_ok=False, raster=None, notes=""),
    ]
    hc.write_meta("static", meta)
    print("wrote", OUT, len(df))


if __name__ == "__main__":
    main()
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from trend_stats import write_trends
    write_trends("static_county")  # Mann-Kendall + Sen's slope (scripts/trend_stats.py)
