"""Safety and spatial invariants for raw imports and training-chip preparation."""
from __future__ import annotations

import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import rasterio
from affine import Affine
from shapely.geometry import box

from solarde.config import load_yaml, resolve
from solarde.data.chips import nested_profiles, prepare, safe_footprint
from solarde.data.rasterize import label_mask
from solarde.data.raw import extract_sources, validate_sources
from solarde.splits.verify import verify


def test_import_reuses_identical_sources_and_refuses_conflicts(tmp_path):
    config = {"raw": {"release": "release", "polygons": str(tmp_path / "gpkg" / "solar.gpkg"),
                      "records": str(tmp_path / "csv" / "solar.csv")}}
    archive = tmp_path / "release.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("release/gpkg/solar.gpkg", b"geometry")
        package.writestr("release/csv/solar.csv", b"records")
        package.writestr("release/unrelated.dat", b"do not extract")
    first = extract_sources(archive, config)
    target = tmp_path / "gpkg" / "solar.gpkg"
    original_mtime = target.stat().st_mtime_ns
    assert not any(item["reused"] for item in first["sources"])
    assert all(item["reused"] for item in extract_sources(archive, config)["sources"])
    assert target.stat().st_mtime_ns == original_mtime
    assert archive.exists() and not (tmp_path / "unrelated.dat").exists()
    target.write_bytes(b"existing different data")
    with pytest.raises(ValueError, match="refusing to overwrite"):
        extract_sources(archive, config)
    assert target.read_bytes() == b"existing different data"


def test_archive_path_traversal_is_rejected_before_extraction(tmp_path):
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("../escape", b"unsafe")
    with pytest.raises(ValueError, match="Unsafe archive"):
        extract_sources(archive, {})


def test_border_buffer_is_enforced_over_the_whole_footprint():
    blocks = gpd.GeoDataFrame({"split": ["train", "test"],
                               "geometry": [box(0, 0, 20000, 20000), box(20000, 0, 40000, 20000)]}, crs=3035)
    assert safe_footprint(box(12000, 5000, 14560, 7560), "train", blocks, 2560)
    assert not safe_footprint(box(17000, 5000, 19560, 7560), "train", blocks, 2560)
    assert not safe_footprint(box(19000, 5000, 21560, 7560), "train", blocks, 2560)


def test_masks_prioritize_ignore_and_clip_cross_split_polygons():
    labels = gpd.GeoDataFrame({"area_id": [1, 2], "label_status": ["positive", "ignore"],
                               "geometry": [box(10, 10, 30, 30), box(0, 0, 5, 5)]}, crs=3035)
    blocks = gpd.GeoDataFrame({"block_id": ["owner"], "geometry": [box(0, 0, 20, 40)]}, crs=3035)
    assignments = pd.DataFrame({"area_id": [1, 2], "block_id": ["owner", "owner"],
                                "split": ["train", "train"], "crosses_split_border": [True, False]})
    valid = np.ones((4, 4), dtype=bool)
    valid[0, 3] = False
    mask = label_mask(labels, assignments, blocks, crs=3035,
                      transform=Affine(10, 0, 0, 0, -10, 40), shape=(4, 4), split="train", valid=valid)
    assert mask.dtype == np.uint8
    assert mask[1, 1] == 1  # owned PV remains positive
    assert mask[1, 2] == 255  # cross-split PV must not become background or a positive
    assert mask[3, 0] == 255  # ignored polygon takes priority
    assert mask[0, 3] == 255  # imagery nodata excluded
    assert mask[0, 0] == 0


def test_fractional_mask_uses_subpixel_coverage():
    labels = gpd.GeoDataFrame({"area_id": [1], "label_status": ["positive"],
                               "geometry": [box(0, 0, 5, 10)]}, crs=3035)
    blocks = gpd.GeoDataFrame({"block_id": ["owner"], "geometry": [box(0, 0, 20, 10)]}, crs=3035)
    assignments = pd.DataFrame({"area_id": [1], "block_id": ["owner"], "split": ["train"],
                                "crosses_split_border": [False]})
    mask = label_mask(labels, assignments, blocks, crs=3035,
                      transform=Affine(10, 0, 0, 0, -10, 10), shape=(1, 2), split="train", fractional_factor=10)
    np.testing.assert_array_equal(mask, [[0.5, 0]])


def test_negative_profiles_are_deterministic_and_nested():
    first = nested_profiles(["pv"], ["n1", "n2", "n3"], [1, 3], 0)
    assert first == nested_profiles(["pv"], ["n3", "n1", "n2"], [1, 3], 0)
    assert set(first["draft_1to1"]["negative_ids"]) < set(first["draft_1to3"]["negative_ids"])


@pytest.mark.integration
@pytest.mark.skipif(not resolve(load_yaml("configs/data.yaml")["raw"]["polygons"]).exists(),
                    reason="requires original UFZ/MaStR release")
def test_real_source_release_counts_and_semantics():
    report = validate_sources(load_yaml("configs/data.yaml"))
    assert report["accepted"], report["failures"]
    assert report["label_report"]["n_positive"] == 9219
    assert report["label_report"]["n_ignore"] == 1765
    assert report["year_only_dates_treated_as_missing_by_v1"]["commissioning_date"] == 25
    assert report["n_records"] == 14250


@pytest.mark.integration
@pytest.mark.skipif(not resolve("data/processed/splits_s1_blocks.gpkg").exists(), reason="requires local splits")
def test_real_split_assignments_reproduce_without_replacing_files():
    report = verify(gpd.read_file(resolve("data/interim/labels_v1.gpkg")),
                    gpd.read_file(resolve("data/processed/splits_s1_blocks.gpkg")),
                    pd.read_csv(resolve("data/processed/splits_s1_polygons.csv")),
                    load_yaml("configs/splits.yaml"), rebuild=True)
    assert report["accepted"], report["checks"]


@pytest.mark.integration
@pytest.mark.skipif(not resolve("data/processed/pilot_preparation/manifest.json").exists(),
                    reason="requires local real-label preparation")
def test_real_preparation_grid_metadata_and_buffer():
    config = load_yaml("configs/preparation.yaml")
    result = prepare(config)  # verifies saved checksums and reuses outputs
    blocks = gpd.read_file(resolve("data/processed/splits_s1_blocks.gpkg"))
    assert result["state"] == "draft_awaiting_imagery_and_sampling_approval"
    for chip in result["chips"]:
        with rasterio.open(resolve(config["output_dir"]) / chip["mask_path"]) as source:
            assert source.shape == (256, 256)
            assert source.res == (10, 10)
            assert source.nodata == 255
            assert source.crs.to_string() == chip["crs"]
            assert list(source.transform)[:6] == chip["transform"]
            assert set(np.unique(source.read(1))) <= {0, 1, 255}
            foot = gpd.GeoSeries([box(*source.bounds).segmentize(100)], crs=source.crs).to_crs(3035).iloc[0]
            assert safe_footprint(foot, "train", blocks, 2560)
