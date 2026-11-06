"""T-new: test-split polygons of V20260203 with no match in the previous release (ROADMAP M1.6).

Area ids are reassigned between releases (shared ids sit a median 288 km apart), so a polygon
counts as carried over when a previous-release polygon overlaps it at IoU >= 0.5 (EPSG:3035).
ponytail: no split/merge handling; a farm redrawn into two parts counts as new.
Upgrade path: count a new polygon as carried over when most of it lies inside the old union.

Usage:
    python -m solarde.splits.tnew --config configs/data.yaml --split-config configs/splits.yaml
"""
from __future__ import annotations

import argparse

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely import STRtree, make_valid

from solarde.config import load_yaml, resolve

IOU_MATCH = 0.5  # same-farm threshold, matching the delineation threshold in M5.2


def select_tnew(assign: pd.DataFrame, matched_ids: set[int]) -> pd.DataFrame:
    """Test-split rows of the polygon assignment whose area_id is not matched in the previous release."""
    test = assign[assign["split"] == "test"]
    return test[~test["area_id"].isin(matched_ids)]


def matched_area_ids(new: gpd.GeoDataFrame, old: gpd.GeoDataFrame, thr: float = IOU_MATCH) -> set[int]:
    """area_ids of `new` polygons that overlap an `old` polygon with IoU >= thr (compared in EPSG:3035)."""
    ng = new.to_crs(3035).geometry.map(make_valid).to_numpy()
    og = old.to_crs(3035).geometry.map(make_valid).to_numpy()
    ni, oi = STRtree(og).query(ng, predicate="intersects")
    inter = shapely.area(shapely.intersection(ng[ni], og[oi]))
    union = shapely.area(shapely.union(ng[ni], og[oi]))
    iou = np.divide(inter, union, out=np.zeros_like(inter), where=union > 0)
    hit = np.zeros(len(ng), dtype=bool)
    hit[ni[iou >= thr]] = True
    return set(new.area_id.to_numpy()[hit].tolist())


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="configs/data.yaml")
    ap.add_argument("--split-config", default="configs/splits.yaml")
    args = ap.parse_args(argv)
    dcfg = load_yaml(args.config)
    scfg = load_yaml(args.split_config)

    prev = resolve(dcfg["raw"]["previous_polygons"])
    if not prev.exists():
        raise SystemExit(f"Missing {prev}. Reference release for T-new: see docs/decisions.md (ROADMAP M1.6).")
    new = gpd.read_file(resolve(dcfg["raw"]["polygons"]), columns=["area_id"])
    old = gpd.read_file(prev, columns=["area_id"])
    matched = matched_area_ids(new, old)
    if not matched:
        raise SystemExit(f"No polygon overlaps {prev.name}: check CRS and paths.")

    v = scfg["split_version"]
    assign = pd.read_csv(resolve(scfg["outputs"]["polygon_assignment"].format(split_version=v)))
    tnew = select_tnew(assign, matched)
    out = resolve(f"data/processed/tnew_{v}_vs_{dcfg['raw']['previous_release']}.csv")
    tnew[["area_id", "block_id"]].to_csv(out, index=False)
    print(f"T-new: {len(tnew)} test polygons with no IoU>={IOU_MATCH} match in {prev.name} -> {out}")


if __name__ == "__main__":
    main()
