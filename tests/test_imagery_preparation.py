"""Synthetic radiometry/grid tests and optional actual pilot-artifact checks."""
from __future__ import annotations

import json

import numpy as np
import pytest
import rasterio
from affine import Affine

from solarde.config import load_yaml, resolve
from solarde.data.raw import sha256
from solarde.imagery.stac import read_grid, reflectance, select_assets


def test_band_selection_excludes_visual_assets():
    reflectance_asset = {"href": "B02.tif", "eo:bands": [{"name": "B02"}], "roles": ["data", "reflectance"]}
    item = {"assets": {"blue": reflectance_asset,
                        "visual": {"href": "visual.tif", "eo:bands": [{"name": "B02"}], "roles": ["visual"]}}}
    assert select_assets(item, ["B02"])["B02"]["href"] == "B02.tif"
    with pytest.raises(ValueError, match="Missing required"):
        select_assets(item, ["B03"])


def test_window_resampling_nodata_and_zero_cloud_probability(tmp_path):
    path = tmp_path / "source.tif"
    with rasterio.open(path, "w", driver="GTiff", width=2, height=2, count=1, dtype="uint16",
                       crs=32632, transform=Affine(20, 0, 600000, 0, -20, 5400000), nodata=0) as source:
        source.write(np.array([[0, 2000], [3000, 4000]], dtype=np.uint16), 1)
    asset = {"href": str(path), "raster:bands": [{"nodata": 0, "scale": 0.0001, "offset": -0.1}]}
    grid = {"crs": 32632, "transform": Affine(10, 0, 600000, 0, -10, 5400000), "shape": (4, 4)}
    values = read_grid(asset, **grid, categorical=True)
    assert values.shape == (4, 4) and np.isnan(values[:2, :2]).all()
    assert reflectance(values, asset)[0, 3] == pytest.approx(0.1)
    clouds = read_grid(asset, **grid, categorical=True, zero_is_valid=True)
    assert (clouds[:2, :2] == 0).all()  # metadata nodata=0 must not discard clear sky
    resampled = read_grid(asset, **grid)
    assert np.isfinite(resampled[2:, 2:]).all()


def test_missing_radiometric_metadata_is_not_guessed():
    with pytest.raises(ValueError, match="explicit radiometric"):
        reflectance(np.ones((2, 2)), {})


def test_interrupted_metadata_cache_is_not_reused_for_a_different_request(tmp_path, monkeypatch):
    monkeypatch.setenv("MPLCONFIGDIR", str(tmp_path / "matplotlib"))
    from solarde.imagery import preview

    plan = {"chips": [{"id": "pilot_+0_+0", "transform": [10, 0, 600000, 0, -10, 5400000],
                       "shape": [256, 256], "crs": "EPSG:32632"}],
            "imagery_request": {"window": ["2025-04-01", "2025-09-30"]}}
    (tmp_path / "manifest.json").write_text(json.dumps(plan))
    directory = tmp_path / "preview"
    directory.mkdir()
    (directory / "items.json").write_text(json.dumps({"query": {"window": ["2020-01-01", "2020-12-31"]},
                                                     "items": [{"id": "stale"}]}))
    calls = []

    def search(bbox, window, max_cloud):
        calls.append(window)
        return []

    monkeypatch.setattr(preview, "search", search)
    with pytest.raises(ValueError, match="No scenes"):
        preview.acquire({"output_dir": str(tmp_path)})
    assert calls == [["2025-04-01", "2025-09-30"]]


@pytest.mark.integration
@pytest.mark.skipif(not resolve("data/processed/pilot_preparation/preview/manifest.json").exists(),
                    reason="requires actual satellite preview artifacts")
def test_real_imagery_and_label_alignment():
    root = resolve("data/processed/pilot_preparation/preview")
    report = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert report["reference_compliant"] is False
    for name, checksum in report["outputs_sha256"].items():
        assert sha256(root / name) == checksum
    with (rasterio.open(root / "image.tif") as image, rasterio.open(root / "mask.tif") as mask,
          rasterio.open(root / "valid.tif") as validity):
        assert image.crs == mask.crs == validity.crs
        assert image.transform == mask.transform == validity.transform
        assert image.shape == mask.shape == validity.shape == (256, 256)
        assert image.res == (10, 10) and image.count == 10
        assert list(image.descriptions) == load_yaml("configs/experiment/reference.yaml")["imagery"]["bands"]
        valid = validity.read(1).astype(bool)
        assert valid.mean() > 0.5
        assert np.isfinite(image.read()[:, valid]).all()
        assert (mask.read(1)[~valid] == 255).all()
        assert (mask.read(1) == 1).any()
