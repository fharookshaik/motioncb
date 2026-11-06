"""Self-check for the VG250 region-group lookup in solarde.splits.blocks. Toy Länder, no data files needed."""
import geopandas as gpd
from shapely.geometry import box

from solarde.splits.blocks import land_group_of


def test_land_groups_with_nearest_fallback(tmp_path):
    lan = gpd.GeoDataFrame({"AGS": ["01", "09"], "geometry": [box(0, 0, 10, 10), box(10, 0, 20, 10)]}, crs=3035)
    path = tmp_path / "lan.gpkg"
    lan.to_file(path, layer="lan", driver="GPKG")
    blocks = gpd.GeoDataFrame(
        {"block_id": list("ABCD")},
        geometry=[box(1, 1, 3, 3), box(12, 1, 14, 3), box(-5, 1, -3, 3), box(22, 1, 24, 3)],  # C, D lie outside all Länder
        crs=3035,
    )
    source = {"path": str(path), "layer": "lan", "groups": {"North": ["01"], "South": ["09"]}}
    # A in 01, B in 09, C is nearest 01 (4 m away vs 14 m), D is nearest 09.
    assert land_group_of(blocks, source).tolist() == ["North", "South", "North", "South"]
