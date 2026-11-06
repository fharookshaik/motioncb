"""Self-check for the M1.3 window sampler. Uses toy blocks, no imagery or data files needed."""
import sys
from pathlib import Path

import geopandas as gpd
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from make_audit_sample import WINDOW_M, sample_windows


def _toy_blocks() -> gpd.GeoDataFrame:
    rows = []
    n = 0
    for reg in ["NE", "NW", "SE", "SW"]:
        for split, count in [("train", 3), ("val", 6), ("test", 6)]:
            for _ in range(count):
                x0 = 4_000_000 + n * 20_000
                rows.append(
                    {"block_id": f"B{n}", "split": split, "region": reg, "geometry": box(x0, 3_000_000, x0 + 20_000, 3_020_000)}
                )
                n += 1
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=3035)


def test_windows_inside_val_test_blocks_and_stratified():
    blocks = _toy_blocks()
    win = sample_windows(blocks, n_per_region=5, seed=1)
    assert len(win) == 4 * 5
    assert win["window_id"].is_unique
    assert set(win["split"]) <= {"val", "test"}
    assert (win.groupby("region").size() == 5).all()
    for _, w in win.iterrows():
        blk = blocks.loc[blocks["block_id"] == w["block_id"]].geometry.iloc[0]
        assert blk.contains(w.geometry)
        minx, miny, maxx, maxy = w.geometry.bounds
        assert abs((maxx - minx) - WINDOW_M) < 1e-6 and abs((maxy - miny) - WINDOW_M) < 1e-6
