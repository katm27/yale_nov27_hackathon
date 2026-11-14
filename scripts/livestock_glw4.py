"""FAO Gridded Livestock of the World v4 (GLW4, reference year 2015, 5 arc-min ~9 km, dasymetric 'Da' product)
cattle/goats/sheep -> county head counts + cattle density (static) and raster overlay docs/rasters/cattle_density/2015.png.
Source: Harvard Dataverse (Gilbert et al. 2018, Sci Data; FAO), CC-BY 4.0.
"""
import os
import sys
import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask as rmask
from rasterstats import zonal_stats
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from overlay_utils import ROOT, counties, write_long, write_meta, write_overlay

RAW = os.path.join(ROOT, "data", "raw", "glw4")
FILES = {  # species: (dataverse file id, DOI)
    "cattle": (6769711, "doi:10.7910/DVN/LHBICE"),
    "goats": (6769696, "doi:10.7910/DVN/YYG6ET"),
    "sheep": (6769626, "doi:10.7910/DVN/VZOYHM"),
}
BBOX = (23.5, 3.0, 36.5, 12.8)


def fetch(species):
    out = os.path.join(RAW, f"glw4_{species}_2015_Da_ssd.tif")
    if os.path.exists(out):
        return out
    fid, _ = FILES[species]
    tmp = out + ".global.tmp"
    r = requests.get(f"https://dataverse.harvard.edu/api/access/datafile/{fid}", timeout=600)
    r.raise_for_status()
    open(tmp, "wb").write(r.content)
    from shapely.geometry import box
    with rasterio.open(tmp) as src:
        arr, tr = rmask(src, [box(*BBOX)], crop=True, filled=False)
        prof = src.profile
        prof.update(height=arr.shape[1], width=arr.shape[2], transform=tr, compress="deflate")
        with rasterio.open(out, "w", **prof) as dst:
            dst.write(arr.filled(src.nodata if src.nodata is not None else -1))
    os.remove(tmp)
    return out


def main():
    os.makedirs(RAW, exist_ok=True)
    with open(os.path.join(RAW, "SOURCE.md"), "w") as f:
        f.write("GLW4 2015 dasymetric (Da) heads per pixel, clipped to South Sudan bbox. Global files from Harvard Dataverse:\n" +
                "\n".join(f"{k}: https://dataverse.harvard.edu/api/access/datafile/{v[0]} ({v[1]})" for k, v in FILES.items()) +
                "\nGilbert et al. 2018, Sci Data 5:180227. CC-BY 4.0\n")
    c = counties()
    ids = list(c.district_id)
    area_km2 = c.to_crs(6933).area / 1e6
    rows = []
    for sp in FILES:
        p = fetch(sp)
        zs = zonal_stats(c, p, stats=["sum"], all_touched=False)
        heads = pd.Series([z["sum"] for z in zs], index=ids, dtype=float)
        rows += [(cid, "2018-07-01", f"{sp}_head", float(v)) for cid, v in heads.items() if pd.notna(v)]
        if sp == "cattle":
            dens = heads / area_km2.values
            rows += [(cid, "2018-07-01", "cattle_density", float(v)) for cid, v in dens.items() if pd.notna(v)]
    df = write_long("glw4", pd.DataFrame(rows, columns=["county_id", "date", "variable", "value"]))
    print(df.groupby("variable").value.agg(["sum", "max", "count"]))
    # overlay: cattle per km2
    with rasterio.open(fetch("cattle")) as src:
        a = src.read(1).astype("float32")
        nod = src.nodata
        a[(a == nod) | (a < 0)] = np.nan
        lat = src.transform.f + src.transform.e * (np.arange(a.shape[0]) + 0.5)
        px = (abs(src.transform.a) * 111.32 * np.cos(np.radians(lat)))[:, None] * abs(src.transform.e) * 110.57
        d = a / px
        write_overlay(d, src.transform, src.crs, "cattle_density", "2015", 1, 200, "ylorbr",
                      {"label": "Cattle density (GLW4, 2015)", "units": "head / km²", "native_resolution": "~9 km (5 arc-min)",
                       "dates": ["2015"], "source": "FAO Gridded Livestock of the World v4 (2015), dasymetric"},
                      log=True, nodata_mask=np.isnan(d))
    base = {"category": "human", "group": "Livestock", "source": "FAO GLW4 2015 (Gilbert et al. 2018), Harvard Dataverse",
            "source_url": "https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/LHBICE",
            "native_resolution": "~9 km (5 arc-min)", "temporal": "static", "index_ok": False, "higher_is": "neutral",
            "aggregation": "sum of dasymetric head counts of pixels with centre in county"}
    note = ("Modelled 2015 distribution (static). South Sudan census inputs are old/sparse, so values are model-driven; "
            "seasonal transhumance not represented. Grazing extent: see Esri LULC rangeland share (other pipeline).")
    write_meta("glw4", [
        dict(base, id="cattle_head", label="Cattle (head, 2015)", units="head", notes=note, raster="cattle_density"),
        dict(base, id="cattle_density", label="Cattle density (2015)", units="head / km²", notes=note, raster="cattle_density",
             aggregation="county cattle head / county area"),
        dict(base, id="goats_head", label="Goats (head, 2015)", units="head", notes=note),
        dict(base, id="sheep_head", label="Sheep (head, 2015)", units="head", notes=note),
    ])


if __name__ == "__main__":
    main()
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    from trend_stats import write_trends
    write_trends("glw4")  # Mann-Kendall + Sen's slope (scripts/trend_stats.py)
