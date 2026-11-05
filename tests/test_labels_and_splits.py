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
    rep = json.loads(report_json.read_text())
    assert rep["accepted"]
