"""Self-checks for T-new selection and the KIT label mapping. Toy data only, no release files needed."""
import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

from solarde.labels.kit_indep import TILE_RE, describe_tile, to_task_mask
from solarde.splits.tnew import best_iou, nearest_distance, new_polygon_ids, select_tnew


def test_new_polygon_ids_drops_matched_and_revised():
    best = pd.Series([1.0, 0.1, 0.1, 0.0], index=[1, 2, 3, 4])
    dist = pd.Series([0.0, 10.0, 500.0, 900.0], index=[1, 2, 3, 4])
    assert new_polygon_ids(best, dist, 0.5, 50) == {3, 4}  # 1 matched, 2 revised within 50 m


def test_select_tnew_filters_each_step():
    labels = pd.DataFrame(
        {"area_id": [1, 2, 3, 4, 5, 6], "label_status": ["positive", "positive", "ignore", "positive", "positive", "positive"]}
    )
    splits = pd.DataFrame(
        {
            "area_id": [1, 2, 3, 4, 5, 6],
            "block_id": ["A", "B", "C", "D", "E", "F"],
            "split": ["test", "test", "test", "train", "test", "test"],
            "crosses_split_border": [False, False, False, False, True, False],
        }
    )
    new_ids = {1, 2, 3, 4, 5}  # 6 is already in the comparator, so it is not new
    out, counts = select_tnew(labels, splits, new_ids)
    assert out["area_id"].tolist() == [1, 2]
    assert counts == {"new_ids": 5, "new_label_v1_positive": 4, "in_test_blocks": 3, "tnew": 2}


def test_to_task_mask_keeps_only_ground_pv():
    values = np.array([[0, 1], [2, 2]], dtype=np.int8)  # background, rooftop, ground, ground
    assert to_task_mask(values).tolist() == [[0, 0], [1, 1]]


def test_to_task_mask_rejects_unknown_values():
    with pytest.raises(ValueError):
        to_task_mask(np.array([0, 3], dtype=np.int8))


def test_best_iou_exact_partial_and_disjoint():
    cur = gpd.GeoSeries([box(0, 0, 10, 10), box(2.5, 0, 12.5, 10), box(50, 50, 60, 60)], index=[1, 2, 3])
    ref = gpd.GeoSeries([box(0, 0, 10, 10), box(5, 0, 15, 10)])
    out = best_iou(cur, ref)
    assert out.loc[1] == pytest.approx(1.0)  # identical to ref 0
    assert out.loc[2] == pytest.approx(0.6)  # 75 / 125 against both refs
    assert out.loc[3] == pytest.approx(0.0)  # no overlap


def test_nearest_distance_zero_on_overlap_and_gap_otherwise():
    cur = gpd.GeoSeries([box(0, 0, 10, 10), box(30, 0, 40, 10)], index=[1, 2])
    ref = gpd.GeoSeries([box(5, 0, 15, 10)])
    out = nearest_distance(cur, ref)
    assert out.loc[1] == pytest.approx(0.0)
    assert out.loc[2] == pytest.approx(15.0)  # gap from x=15 to x=30


def test_tile_name_pattern():
    m = TILE_RE.match("label_manual_nrw_0292_5600_2023.tif")
    assert (m["region"], m["year"]) == ("nrw", "2023")


def test_kit_source_hash_detects_rearranged_pixels(tmp_path):
    import rasterio
    from pyproj import Transformer

    path = tmp_path / "label_manual_nrw_0292_5600_2023.tif"
    bounds = box(300000, 5600000, 300002, 5600002)
    blocks = gpd.GeoDataFrame({"split": ["test"]}, geometry=[bounds], crs=25832).to_crs(3035)
    labels = gpd.GeoDataFrame({"label_status": ["positive"], "commission_last": ["2020-01-01"]},
                              geometry=[bounds], crs=25832)
    transformer = Transformer.from_crs(25832, 3035, always_xy=True)
    results = []
    for values in (np.array([[0, 1], [2, 2]], dtype="uint8"), np.array([[2, 2], [0, 1]], dtype="uint8")):
        with rasterio.open(path, "w", driver="GTiff", height=2, width=2, count=1, dtype="uint8",
                           crs="EPSG:25832", transform=rasterio.Affine(1, 0, 300000, 0, -1, 5600002)) as dst:
            dst.write(values, 1)
        results.append(describe_tile(path, blocks, labels, transformer))
    assert results[0]["n_ground_px"] == results[1]["n_ground_px"] == 2
    assert results[0]["source_sha256"] != results[1]["source_sha256"]
