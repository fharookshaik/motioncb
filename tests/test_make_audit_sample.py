"""Self-check for the M1.3 window sampler. Toy blocks and labels, no data files needed."""
import sys
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from make_audit_sample import WINDOW_M, sample_windows

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
