"""M1.3 completeness audit: draw 60 random 5x5 km windows inside val+test blocks, stratified by region.

Outputs (runs/audit_m1_3/, not committed):
  windows.gpkg    EPSG:3035 window polygons for the QGIS project (labels v1 + S2 composite + basemap)
  audit_form.csv  window_id, missing_pv_count, notes; filled in by Fharook

No land mask yet (M2). Windows over water or forest are expected; record them in notes.

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
OUT_DIR = "runs/audit_m1_3"


def sample_windows(blocks: gpd.GeoDataFrame, n_per_region: int, seed: int) -> gpd.GeoDataFrame:
    """Pick n_per_region distinct val/test blocks per region; place one 5 km window at a random offset in each."""
    rng = np.random.default_rng(seed)
    pool = blocks[blocks["split"].isin(["val", "test"])]
    rows = []
    for reg in sorted(pool["region"].unique()):
        cand = pool[pool["region"] == reg]
        if len(cand) < n_per_region:
            raise ValueError(f"region {reg}: {len(cand)} val/test blocks, need {n_per_region}")
        for pos in rng.choice(len(cand), size=n_per_region, replace=False):
            blk = cand.iloc[pos]
            minx, miny, maxx, maxy = blk.geometry.bounds
            x0 = minx + rng.uniform(0, (maxx - minx) - WINDOW_M)
            y0 = miny + rng.uniform(0, (maxy - miny) - WINDOW_M)
            rows.append(
                {
                    "block_id": blk["block_id"],
                    "split": blk["split"],
                    "region": reg,
                    "geometry": box(x0, y0, x0 + WINDOW_M, y0 + WINDOW_M),
                }
            )
    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=blocks.crs)
    gdf = gdf.iloc[rng.permutation(len(gdf))].reset_index(drop=True)
    gdf.insert(0, "window_id", [f"W{i + 1:02d}" for i in range(len(gdf))])
    return gdf


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="configs/splits.yaml")
    args = ap.parse_args(argv)
    cfg = load_yaml(args.config)
    blocks_path = resolve(cfg["outputs"]["blocks"].format(split_version=cfg["split_version"]))
    blocks = gpd.read_file(blocks_path, layer="blocks")
    win = sample_windows(blocks, N_PER_REGION, SEED)
    out = resolve(OUT_DIR)
    out.mkdir(parents=True, exist_ok=True)
    win.to_file(out / "windows.gpkg", driver="GPKG", layer="windows")
    pd.DataFrame({"window_id": win["window_id"], "missing_pv_count": "", "notes": ""}).to_csv(
        out / "audit_form.csv", index=False
    )
    print(f"{len(win)} windows written to {out}")


if __name__ == "__main__":
    main()
