"""Unit tests on synthetic data, plus integration checks when the raw release is present."""
from __future__ import annotations

import json

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import MultiPolygon, box

from solarde.config import load_yaml, resolve
from solarde.labels.curate import curate
from solarde.splits import blocks as split_blocks
from solarde.splits.blocks import _greedy, balance_score

CFG = {
    "label_version": "test",
    "crs": {"equal_area": 3035},
    "imagery_window": {"start": "2025-04-01", "end": "2025-09-30", "commissioning_buffer_months": 3},
    "labels": {
        "ignore_area_accuracy_2": True,
        "ignore_unlinked": True,
        "keep_outside_germany": True,
        "germany_lat_max": 55.06,
        "large_scale_min_ha": 1.0,
        "size_bins_ha": [0, 0.5, 1, 5, 100000],
    },
}


def _square(lon, lat, d=0.002):
    return MultiPolygon([box(lon, lat, lon + d, lat + d)])


@pytest.fixture
def synthetic():
    polys = gpd.GeoDataFrame(
        {
            "area_id": [1, 2, 3, 4, 5, 6],
            "area_accuracy": [1, 2, 1, 1, 1, 1],
            "area_related": [1, 1, 0, 1, 1, 1],
            "geometry": [_square(10, 50), _square(10.1, 50), _square(10.2, 50), _square(10.3, 50),
                         _square(10.4, 50), _square(11.5, 55.76)],
        },
        crs=4326,
    )
    recs = pd.DataFrame(
        {
            "area_id": [1, 2, 4, 4, 5, 6],
            "installed_capacity": [1000, 500, 300, 300, 800, 9000],
            "commissioning_date": pd.to_datetime(
                ["2020-01-01", "2019-05-01", "2018-01-01", "2025-06-01", "2015-01-01", "2021-01-01"]),
            "decommissioning_date": pd.to_datetime([None, None, None, None, "2025-05-01", None]),
            "location": ["Ground-mounted"] * 6,
            "alignment": ["South"] * 6,
            "inclination": ["21 - 40 degrees"] * 6,
        }
    )
    return polys, recs


def test_status_and_reasons(synthetic):
    out = curate(*synthetic, CFG).set_index("area_id")
    assert out.loc[1, "label_status"] == "positive"
    assert "area_accuracy_2" in out.loc[2, "ignore_reason"]
    assert "unlinked" in out.loc[3, "ignore_reason"]
    assert "built_after_cutoff" in out.loc[4, "ignore_reason"]  # one phase in 2025
    assert bool(out.loc[4, "multi_phase"])
    assert "decommissioned" in out.loc[5, "ignore_reason"]
    # cross-border polygon is kept and only flagged
    assert out.loc[6, "label_status"] == "positive"
    assert bool(out.loc[6, "outside_germany_flag"])


def test_nothing_dropped(synthetic):
    out = curate(*synthetic, CFG)
    assert len(out) == len(synthetic[0])
    assert out.crs.to_epsg() == 3035


def test_greedy_balances_weights():
    rng = np.random.default_rng(0)
    w = rng.lognormal(0, 1, 500)
    targets = np.array([0.7, 0.1, 0.2])
    a = _greedy(w, np.argsort(-w), targets)
    assert balance_score(a, w[:, None], targets) < 0.05


# --- integration (skipped unless data/ outputs exist) -----------------------------------------

def _labels_path():
    d = load_yaml("configs/data.yaml")
    return resolve(d["outputs"]["labels"].format(label_version=d["label_version"]))


@pytest.mark.skipif(not _labels_path().exists(), reason="run `make labels` first")
def test_real_labels_invariants():
    g = gpd.read_file(_labels_path(), layer="labels")
    assert len(g) == 10984
    assert set(g.label_status) <= {"positive", "ignore"}
    assert (g.label_status == "ignore").eq(g.ignore_reason != "").all()
    assert g.area_id.is_unique


def _split_paths():
    s = load_yaml("configs/splits.yaml")
    v = s["split_version"]
    return resolve(s["outputs"]["polygon_assignment"].format(split_version=v)), resolve(
        s["outputs"]["report"].format(split_version=v))


@pytest.mark.skipif(not _split_paths()[0].exists(), reason="run `make splits` first")
def test_real_splits_invariants():
    assign_csv, report_json = _split_paths()
    a = pd.read_csv(assign_csv)
    assert a.area_id.is_unique, "each polygon must belong to exactly one block/split"
    assert set(a.area_id) == set(gpd.read_file(_labels_path(), columns=["area_id"]).area_id)
    assert not a[["block_id", "split", "cv_fold", "crosses_split_border"]].isna().any().any()
    rep = json.loads(report_json.read_text())
    assert rep["accepted"]


@pytest.mark.parametrize("column,date,ignored", [
    ("commissioning_date", "2024-12-31", False),
    ("commissioning_date", "2025-01-01", True),
    ("decommissioning_date", "2025-09-30", True),
    ("decommissioning_date", "2025-10-01", False),
])
def test_temporal_boundaries(synthetic, column, date, ignored):
    polys, records = synthetic
    records = records.copy()
    records.loc[records.area_id.eq(1), column] = pd.Timestamp(date)
    out = curate(polys, records, CFG).set_index("area_id")
    assert (out.loc[1, "label_status"] == "ignore") == ignored


def _toy_split(monkeypatch, centroid_x=5):
    grid = gpd.GeoDataFrame({"block_id": ["left", "right"]},
                            geometry=[box(0, 0, 10, 10), box(10, 0, 20, 10)], crs=3035)
    labels = gpd.GeoDataFrame({"area_id": [1, 2], "ha": [1.0, 0.5], "large_scale": [True, False],
                              "label_status": ["positive", "positive"]},
                              geometry=[box(centroid_x - 6, 2, centroid_x + 6, 4), box(12, 2, 14, 4)], crs=3035)
    monkeypatch.setattr(split_blocks, "make_grid", lambda *args: grid)
    monkeypatch.setattr(split_blocks, "land_group_of", lambda *args: pd.Series(["North", "North"]))
    monkeypatch.setattr(split_blocks, "assign_blocks", lambda *args: (pd.Series(["train", "test"]), 0.0))
    cfg = {"grid_bbox_wgs84": [], "block_size_m": 10, "region_source": {},
           "fractions": {"train": 0.5, "test": 0.5}, "restarts": 1, "seed": 1, "cv_folds": 2,
           "split_version": "toy", "max_rel_deviation": 0.05}
    return labels, cfg


def test_cross_split_polygon_flag(monkeypatch):
    labels, cfg = _toy_split(monkeypatch)
    _, assignments, _ = split_blocks.build(labels, cfg)
    assert assignments.area_id.tolist() == [1, 2]
    assert assignments.block_id.tolist() == ["left", "right"]
    assert assignments.crosses_split_border.tolist() == [True, False]


@pytest.mark.parametrize("centroid_x", [10, 30])
def test_unassigned_boundary_or_outside_centroid_fails(monkeypatch, centroid_x):
    labels, cfg = _toy_split(monkeypatch, centroid_x)
    with pytest.raises(ValueError, match="exactly one centroid"):
        split_blocks.build(labels, cfg)


def test_split_refuses_existing_files_before_reading_labels(tmp_path, monkeypatch):
    out = tmp_path / "blocks.gpkg"
    out.write_bytes(b"retained split")
    cfg = {"split_version": "toy", "outputs": {"blocks": str(out)}}
    monkeypatch.setattr(split_blocks, "load_yaml", lambda path: cfg)
    with pytest.raises(SystemExit, match="Refusing to replace"):
        split_blocks.main(["--config", "unused", "--data-config", "unused"])
    assert out.read_bytes() == b"retained split"


def test_rejected_split_writes_nothing(tmp_path, monkeypatch):
    cfg = {"split_version": "toy", "outputs": {key: str(tmp_path / key)
           for key in ("blocks", "polygon_assignment", "report")}}
    dcfg = {"outputs": {"labels": "unused"}, "label_version": "test"}
    monkeypatch.setattr(split_blocks, "load_yaml", lambda path: cfg if path == "split" else dcfg)
    monkeypatch.setattr(split_blocks.gpd, "read_file", lambda *a, **kw: None)
    monkeypatch.setattr(split_blocks, "build", lambda *a: (None, None, {"accepted": False}))
    with pytest.raises(SystemExit, match="no outputs written"):
        split_blocks.main(["--config", "split", "--data-config", "data"])
    assert not list(tmp_path.iterdir())
