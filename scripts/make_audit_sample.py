"""M1.3 completeness audit: draw 60 windows centred on positive labelled farms in val+test blocks, stratified by region.

Windows are anchored on labelled polygons, so the omission rate is conditional on a labelled farm being in the
window. Only German polygons are used (outside_germany_flag excluded). Polygons crossing a split border are excluded
so every window lies fully inside its own block.

Outputs (runs/audit_m1_3/, not committed):
  windows.gpkg    EPSG:3035 window polygons for the QGIS project (labels v1 + basemap)
  audit_form.csv  window_id, missing_pv_count, notes; filled in by Fharook

Usage:
    uv run python scripts/make_audit_sample.py --config configs/splits.yaml
"""
from __future__ import annotations

import argparse

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

from solarde.config import load_yaml, resolve

WINDOW_M = 5000
N_PER_REGION = 15
SEED = 20261106
LABELS_PATH = "data/interim/labels_v1.gpkg"
OUT_DIR = "runs/audit_m1_3"


def _window_around(poly, blk, size: float, rng: np.random.Generator):
    """Random size x size window inside blk that fully contains poly. None if no such window fits."""
    pminx, pminy, pmaxx, pmaxy = poly.bounds
    bminx, bminy, bmaxx, bmaxy = blk.bounds
    xlo, xhi = max(bminx, pmaxx - size), min(bmaxx - size, pminx)
    ylo, yhi = max(bminy, pmaxy - size), min(bmaxy - size, pminy)
    if xlo > xhi or ylo > yhi:
        return None
    x0, y0 = rng.uniform(xlo, xhi), rng.uniform(ylo, yhi)
    return box(x0, y0, x0 + size, y0 + size)


def sample_windows(labels: gpd.GeoDataFrame, blocks: gpd.GeoDataFrame, n_per_region: int, seed: int,
                   size: float = WINDOW_M) -> gpd.GeoDataFrame:
    """One window per sampled block, containing a positive German label from a val/test block of that region."""
    rng = np.random.default_rng(seed)
    bidx = blocks.set_index("block_id")
    ok = labels["label_status"].eq("positive") & ~labels["outside_germany_flag"] & ~labels["crosses_split_border"]
    pool = labels[ok].copy()
    pool["split"] = pool["block_id"].map(bidx["split"])
    pool["region"] = pool["block_id"].map(bidx["region"])
    pool = pool[pool["split"].isin(["val", "test"])]
    regions = sorted(blocks.loc[blocks["split"].isin(["val", "test"]), "region"].unique())
    rows = []
    for reg in regions:
        cand = pool[pool["region"] == reg]
        picked = 0
        for bid in rng.permutation(cand["block_id"].unique()):
            if picked == n_per_region:
                break
            polys = cand[cand["block_id"] == bid]
            for pos in rng.permutation(len(polys)):
                row = polys.iloc[pos]
                win = _window_around(row.geometry, bidx.geometry.loc[bid], size, rng)
                if win is not None:
                    rows.append({"block_id": bid, "area_id": row["area_id"], "split": row["split"],
                                 "region": reg, "geometry": win})
                    picked += 1
                    break
        if picked < n_per_region:
            raise ValueError(f"region {reg}: only {picked} usable blocks, need {n_per_region}")
    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=blocks.crs)
    gdf = gdf.iloc[rng.permutation(len(gdf))].reset_index(drop=True)
    gdf.insert(0, "window_id", [f"W{i + 1:02d}" for i in range(len(gdf))])
    return gdf


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="configs/splits.yaml")
    args = ap.parse_args(argv)
    cfg = load_yaml(args.config)
    v = cfg["split_version"]
    blocks = gpd.read_file(resolve(cfg["outputs"]["blocks"].format(split_version=v)), layer="blocks")
    polys = pd.read_csv(resolve(cfg["outputs"]["polygon_assignment"].format(split_version=v)))
    labels = gpd.read_file(resolve(LABELS_PATH), layer="labels")
    labels = labels.merge(polys[["area_id", "block_id", "crosses_split_border"]], on="area_id",
                          how="left", validate="one_to_one")
    if labels["block_id"].isna().any():
        raise ValueError("labels without a block assignment")
    win = sample_windows(labels, blocks, N_PER_REGION, SEED)
    out = resolve(OUT_DIR)
    out.mkdir(parents=True, exist_ok=True)
    win.to_file(out / "windows.gpkg", driver="GPKG", layer="windows")
    pd.DataFrame({"window_id": win["window_id"], "missing_pv_count": "", "notes": ""}).to_csv(
        out / "audit_form.csv", index=False
    )
    print(f"{len(win)} windows written to {out}")


if __name__ == "__main__":
    main()
