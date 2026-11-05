"""Synthetic checks for georeferenced prediction export."""
from __future__ import annotations

import json

import numpy as np
import pytest
import rasterio
from affine import Affine

from solarde.evaluate.vectorize import polygonize_probabilities, write_geojson


def _probability_raster(path, values, *, crs="EPSG:3035", nodata=-9999):
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=values.shape[0],
        width=values.shape[1],
        count=1,
        dtype=values.dtype,
        crs=crs,
        transform=Affine(10, 0, 4000000, 0, -10, 3000000),
        nodata=nodata,
    ) as dst:
        dst.write(values, 1)


def test_polygonize_excludes_nodata_and_exports_wgs84(tmp_path):
    values = np.array(
        [[0.1, 0.9, 0.8], [0.1, 0.2, -9999], [0.1, 0.2, 0.95]],
        dtype=np.float32,
    )
    path = tmp_path / "probability.tif"
    _probability_raster(path, values)

    result = polygonize_probabilities(path, threshold=0.7)

    assert len(result["features"]) == 2
    primary = result["features"][0]
    props = primary["properties"]
    assert props["pixel_count"] == 2
    assert props["confidence_mean"] == pytest.approx(0.85)
    assert props["area_ha"] == pytest.approx(0.02)
    coords = primary["geometry"]["coordinates"][0][0]
    assert -180 <= coords[0] <= 180 and -90 <= coords[1] <= 90

    output = tmp_path / "nested" / "predictions.geojson"
    write_geojson(result, output)
    roundtrip = json.loads(output.read_text(encoding="utf-8"))
    assert roundtrip["type"] == "FeatureCollection"
    assert len(roundtrip["features"]) == 2


def test_polygonize_rejects_geographic_raster(tmp_path):
    path = tmp_path / "geographic.tif"
    _probability_raster(path, np.zeros((2, 2), dtype=np.float32), crs="EPSG:4326")

    with pytest.raises(ValueError, match="projected CRS"):
        polygonize_probabilities(path, threshold=0.5)


def test_polygonize_rejects_non_probability_values(tmp_path):
    path = tmp_path / "bad.tif"
    _probability_raster(path, np.array([[2.0]], dtype=np.float32))

    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        polygonize_probabilities(path, threshold=0.5)
