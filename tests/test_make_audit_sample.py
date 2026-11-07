"""Self-check for the M1.3 window sampler. Toy blocks and labels, no data files needed."""
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from make_audit_sample import WINDOW_M, main, sample_windows, summarise_audit

EXCLUDED_AREAS = {9997, 9998, 9999}


def _toy_inputs() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    blocks, labels = [], []
    n = 0
    for reg in ["NE", "NW", "SE", "SW"]:
        for split, count in [("train", 3), ("val", 6), ("test", 6)]:
            for _ in range(count):
                x0 = 4_000_000 + n * 20_000
                bid = f"B{n}"
                blocks.append({"block_id": bid, "split": split, "region": reg,
                               "geometry": box(x0, 3_000_000, x0 + 20_000, 3_020_000)})
                labels.append({"area_id": n, "block_id": bid, "label_status": "positive",
                               "outside_germany_flag": False, "crosses_split_border": False,
                               "geometry": box(x0 + 1000, 3_001_000, x0 + 1500, 3_001_500)})
                n += 1
    # Excluded decoys, each placed inside its named block (B3 and B4 are val, B5 is val, all NE).
    labels.append({"area_id": 9999, "block_id": "B3", "label_status": "positive", "outside_germany_flag": True,
                   "crosses_split_border": False, "geometry": box(4_065_000, 3_005_000, 4_065_500, 3_005_500)})
    labels.append({"area_id": 9998, "block_id": "B4", "label_status": "ignore", "outside_germany_flag": False,
                   "crosses_split_border": False, "geometry": box(4_085_000, 3_005_000, 4_085_500, 3_005_500)})
    # Straddles the B5/B6 border at x=4_120_000.
    labels.append({"area_id": 9997, "block_id": "B5", "label_status": "positive", "outside_germany_flag": False,
                   "crosses_split_border": True, "geometry": box(4_119_000, 3_005_000, 4_121_000, 3_005_500)})
    blocks = gpd.GeoDataFrame(blocks, geometry="geometry", crs=3035)
    labels = gpd.GeoDataFrame(labels, geometry="geometry", crs=3035)
    return labels, blocks


def test_windows_contain_german_positive_labels_inside_val_test_blocks():
    labels, blocks = _toy_inputs()
    win = sample_windows(labels, blocks, n_per_region=5, seed=1)
    assert len(win) == 4 * 5
    assert win["window_id"].is_unique
    assert win["block_id"].is_unique
    assert set(win["split"]) <= {"val", "test"}
    assert (win.groupby("region").size() == 5).all()
    assert not set(win["area_id"]) & EXCLUDED_AREAS
    bidx = blocks.set_index("block_id").geometry
    lidx = labels.set_index("area_id").geometry
    for _, w in win.iterrows():
        assert bidx.loc[w["block_id"]].contains(w.geometry)
        assert w.geometry.contains(lidx.loc[w["area_id"]])
        minx, miny, maxx, maxy = w.geometry.bounds
        assert abs((maxx - minx) - WINDOW_M) < 1e-6 and abs((maxy - miny) - WINDOW_M) < 1e-6


def test_raises_when_region_has_too_few_usable_blocks():
    labels, blocks = _toy_inputs()
    # 12 val+test blocks per toy region, so 13 cannot be met.
    with pytest.raises(ValueError):
        sample_windows(labels, blocks, n_per_region=13, seed=1)


def test_completed_audit_is_never_overwritten(tmp_path):
    form = tmp_path / "audit_form.csv"
    form.write_text("completed observations", encoding="utf-8")
    config = tmp_path / "audit.yaml"
    config.write_text(f"audit:\n  out_dir: '{tmp_path.as_posix()}'\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="Refusing to overwrite"):
        main(["--config", str(config)])
    assert form.read_text(encoding="utf-8") == "completed observations"


def test_audit_summary_and_validation():
    windows = gpd.GeoDataFrame({"window_id": ["W01", "W02"], "block_id": ["B1", "B2"]},
                               geometry=[box(0, 0, 10, 10), box(20, 0, 30, 10)], crs=3035)
    labels = gpd.GeoDataFrame({"label_status": ["positive", "positive", "ignore", "positive"]},
                              geometry=[box(1, 1, 2, 2), box(9, 1, 11, 2), box(3, 3, 4, 4), box(21, 1, 22, 2)],
                              crs=3035)
    form = pd.DataFrame({"window_id": ["W02", "W01"], "missing_pv_count": [2, 1]})
    result = summarise_audit(windows, labels, form, {"W02": 2}, seed=1, resamples=100)
    assert result["labelled_fully_contained"] == 2
    assert result["missed_inside"] == 1
    assert result["omission_rate"] == 1 / 3
    assert result == summarise_audit(windows, labels, form, {"W02": 2}, seed=1, resamples=100)


def test_audit_rejects_incomplete_form():
    labels, blocks = _toy_inputs()
    windows = sample_windows(labels, blocks, n_per_region=1, seed=1)
    form = pd.DataFrame({"window_id": windows.window_id, "missing_pv_count": [0, 0, None, 0]})
    with pytest.raises(ValueError, match="non-negative integer"):
        summarise_audit(windows, labels, form, {}, seed=1, resamples=10)
