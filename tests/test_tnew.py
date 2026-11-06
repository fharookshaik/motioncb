import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from solarde.splits.tnew import matched_area_ids, select_tnew


def test_select_tnew_test_split_only_and_not_matched():
    assign = pd.DataFrame({"area_id": [1, 2, 3, 4], "split": ["test", "test", "train", "test"]})
    out = select_tnew(assign, matched_ids={1, 3})
    assert out.area_id.tolist() == [2, 4]


def test_matched_area_ids_uses_iou_threshold():
    # 1: IoU 0.95 -> match. 2: IoU 1/3 -> no match. 3: no overlap -> no match. Metres (EPSG:3035).
    new = gpd.GeoDataFrame(
        {"area_id": [1, 2, 3]},
        geometry=[box(0, 0, 10, 10), box(100, 0, 110, 10), box(200, 0, 210, 10)],
        crs=3035,
    )
    old = gpd.GeoDataFrame(geometry=[box(0.5, 0, 10, 10), box(105, 0, 115, 10)], crs=3035)
    assert matched_area_ids(new, old) == {1}
