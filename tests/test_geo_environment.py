"""The project must not load a system PostGIS projection database."""
import os
import subprocess
import sys


def test_geospatial_wheels_ignore_inherited_postgis_settings():
    env = os.environ | {key: "invalid-postgis-data" for key in ("PROJ_LIB", "PROJ_DATA", "GDAL_DATA")}
    subprocess.run(
        [sys.executable, "-B", "-c", """
import solarde
import rasterio
from rasterio.warp import transform
from pyproj import Transformer
assert rasterio.crs.CRS.from_epsg(3035).to_epsg() == 3035
x, y = transform('EPSG:4326', 'EPSG:3035', [10.0], [52.0])
expected = Transformer.from_crs(4326, 3035, always_xy=True).transform(10.0, 52.0)
assert abs(x[0] - expected[0]) < 0.01 and abs(y[0] - expected[1]) < 0.01
"""],
        env=env, check=True, capture_output=True, text=True,
    )
