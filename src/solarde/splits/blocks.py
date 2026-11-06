"""Spatial block splits (train/val/test and k-fold) on a 20 km EPSG:3035 grid.

Design (docs/study_design.md, "Spatial splits and evaluation metrics"):
- every polygon belongs to the block holding its centroid;
- blocks are assigned to splits by randomised greedy balancing of PV area,
  stratified by region, keeping the best of N restarts;
- blocks without PV are assigned at random (stratified by region) so the
  wall-to-wall false-positive test (T-wall) has empty land too;
- polygons that touch a block of a different split are flagged; the chip
  sampler must mask them outside their own block and drop chips within one
  chip width of a split border.

Usage:
    python -m solarde.splits.blocks --config configs/splits.yaml --data-config configs/data.yaml
"""
from __future__ import annotations

import argparse
import json

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

from solarde.config import load_yaml, resolve


def make_grid(bbox_wgs84: list[float], size_m: float, crs: int = 3035) -> gpd.GeoDataFrame:
    lo = gpd.GeoSeries([box(*bbox_wgs84)], crs=4326).to_crs(crs).total_bounds
    x0, y0 = np.floor(lo[0] / size_m) * size_m, np.floor(lo[1] / size_m) * size_m
    xs = np.arange(x0, lo[2] + size_m, size_m)
    ys = np.arange(y0, lo[3] + size_m, size_m)
    rows = [
        {"block_id": f"E{int(x / 1000)}N{int(y / 1000)}", "geometry": box(x, y, x + size_m, y + size_m)}
        for x in xs
        for y in ys
    ]
    return gpd.GeoDataFrame(rows, crs=crs)


def region_of(lon: np.ndarray, lat: np.ndarray, lon_split: float, lat_split: float) -> np.ndarray:
    ns = np.where(lat >= lat_split, "N", "S")
    ew = np.where(lon >= lon_split, "E", "W")
    return np.char.add(ns.astype(str), ew.astype(str))


def _greedy(weights: np.ndarray, order: np.ndarray, targets: np.ndarray) -> np.ndarray:
    """Assign items (in `order`) to the split with the largest remaining deficit."""
    total = weights.sum()
    filled = np.zeros(len(targets))
    out = np.empty(len(weights), dtype=int)
    for i in order:
        deficit = targets * total - filled
        k = int(np.argmax(deficit / np.maximum(targets, 1e-9)))
        out[i] = k
        filled[k] += weights[i]
    return out


def balance_score(assign: np.ndarray, metrics: np.ndarray, targets: np.ndarray) -> float:
    """Max relative deviation of any split's share of any metric from its target."""
    worst = 0.0
    for m in metrics.T:
        tot = m.sum()
        if tot <= 0:
            continue
        for k, t in enumerate(targets):
            share = m[assign == k].sum() / tot
            worst = max(worst, abs(share - t) / t)
    return worst


def assign_blocks(
    blocks: pd.DataFrame, names: list[str], fracs: list[float], restarts: int, seed: int
) -> tuple[pd.Series, float]:
    """Assign PV blocks to splits, region by region; returns labels and worst deviation."""
    rng = np.random.default_rng(seed)
    targets = np.asarray(fracs, float)
    labels = pd.Series(index=blocks.index, dtype=object)
    pv = blocks[blocks.pv_ha > 0]
    metrics_all = pv[["pv_ha", "n_large", "n_small"]].to_numpy(float)
    best_assign_full, best_score = None, np.inf
    for _ in range(restarts):
        assign_full = np.empty(len(pv), dtype=int)
        for reg in sorted(pv.region.unique()):
            idx = np.flatnonzero(pv.region.to_numpy() == reg)
            w = pv.pv_ha.to_numpy()[idx]
            noisy = w * rng.lognormal(0.0, 0.35, size=len(w))
            order_local = np.argsort(-noisy)
            local = _greedy(w, order_local, targets)
            assign_full[idx] = local
        score = balance_score(assign_full, metrics_all, targets)
        if score < best_score:
            best_score, best_assign_full = score, assign_full
    labels.loc[pv.index] = [names[k] for k in best_assign_full]

    empty = blocks[blocks.pv_ha <= 0]
    for reg in sorted(empty.region.unique()):
        idx = empty.index[empty.region == reg]
        labels.loc[idx] = rng.choice(names, size=len(idx), p=targets / targets.sum())
    return labels, float(best_score)


def build(labels_gdf: gpd.GeoDataFrame, cfg: dict) -> tuple[gpd.GeoDataFrame, pd.DataFrame, dict]:
    grid = make_grid(cfg["grid_bbox_wgs84"], cfg["block_size_m"], labels_gdf.crs.to_epsg())
    cent = labels_gdf.copy()
    cent["geometry"] = labels_gdf.geometry.centroid
    j = gpd.sjoin(cent[["area_id", "ha", "large_scale", "label_status", "geometry"]], grid, predicate="within")
    j = j.drop(columns="index_right")

    pos = j[j.label_status == "positive"]
    stats = pos.groupby("block_id").agg(
        pv_ha=("ha", "sum"),
        n_large=("large_scale", "sum"),
        n_small=("large_scale", lambda s: int((~s.astype(bool)).sum())),
    )
    blocks = grid.merge(stats, left_on="block_id", right_index=True, how="left").fillna(
        {"pv_ha": 0.0, "n_large": 0, "n_small": 0}
    )
    # keep blocks with any polygon (positive or ignore) plus all blocks overlapping the polygon extent;
    # land/Germany masking of empty blocks happens in the imagery pipeline.
    bc = blocks.geometry.centroid.to_crs(4326)
    blocks["region"] = region_of(bc.x.to_numpy(), bc.y.to_numpy(), cfg["region_split_lon"], cfg["region_split_lat"])
    blocks["n_polygons_any"] = blocks.block_id.map(j.groupby("block_id").size()).fillna(0).astype(int)

    names, fracs = list(cfg["fractions"].keys()), list(cfg["fractions"].values())
    blocks["split"], worst = assign_blocks(blocks, names, fracs, cfg["restarts"], cfg["seed"])

    k = int(cfg["cv_folds"])
    folds, worst_cv = assign_blocks(
        blocks, [f"fold{i}" for i in range(k)], [1 / k] * k, cfg["restarts"], cfg["seed"] + 1
    )
    blocks["cv_fold"] = folds

    # polygon -> block assignment and cross-split flag
    poly = j[["area_id", "block_id"]].merge(blocks[["block_id", "split", "cv_fold"]], on="block_id")
    touch = gpd.sjoin(labels_gdf[["area_id", "geometry"]], blocks[["block_id", "split", "geometry"]], predicate="intersects")
    n_splits_touched = touch.groupby("area_id")["split"].nunique()
    poly["crosses_split_border"] = poly.area_id.map(n_splits_touched).fillna(1).astype(int) > 1

    report = {
        "split_version": cfg["split_version"],
        "seed": cfg["seed"],
        "n_blocks_total": len(blocks),
        "n_blocks_with_positive_pv": int((blocks.pv_ha > 0).sum()),
        "worst_relative_deviation_train_val_test": round(worst, 4),
        "worst_relative_deviation_cv": round(worst_cv, 4),
        "accepted": bool(worst <= cfg["max_rel_deviation"]),
        "polygons_crossing_split_border": int(poly.crosses_split_border.sum()),
        "by_split": {},
    }
    pv_tot = blocks.pv_ha.sum()
    for s in names:
        b = blocks[blocks.split == s]
        report["by_split"][s] = {
            "blocks_with_pv": int((b.pv_ha > 0).sum()),
            "pv_ha_share": round(float(b.pv_ha.sum() / pv_tot), 4),
            "large_share": round(float(b.n_large.sum() / blocks.n_large.sum()), 4),
            "small_share": round(float(b.n_small.sum() / blocks.n_small.sum()), 4),
            "pv_ha_share_by_region": {
                r: round(float(b[b.region == r].pv_ha.sum() / max(blocks[blocks.region == r].pv_ha.sum(), 1e-9)), 4)
                for r in sorted(blocks.region.unique())
            },
        }
    return blocks, poly, report


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="configs/splits.yaml")
    ap.add_argument("--data-config", default="configs/data.yaml")
    args = ap.parse_args(argv)
    cfg = load_yaml(args.config)
    dcfg = load_yaml(args.data_config)

    # Put protection in the CLI itself, not only in a platform-specific Makefile.
    # Verify existing artifacts without regenerating even before training starts.
    sv = cfg["split_version"]
    output_paths = [resolve(value.format(split_version=sv)) for value in cfg["outputs"].values()]
    if any(path.exists() for path in output_paths):
        raise SystemExit("Split artifacts already exist; preserved. Run solarde.splits.verify instead.")

    labels_path = resolve(dcfg["outputs"]["labels"].format(label_version=dcfg["label_version"]))
    labels_gdf = gpd.read_file(labels_path, layer="labels")
    blocks, poly, report = build(labels_gdf, cfg)
    report["label_version"] = dcfg["label_version"]
    if not report["accepted"]:
        raise SystemExit("Split balance outside tolerance; no artifacts written. Review the configured protocol.")

    out_b = resolve(cfg["outputs"]["blocks"].format(split_version=sv))
    out_b.parent.mkdir(parents=True, exist_ok=True)
    blocks.to_file(out_b, driver="GPKG", layer="blocks")
    poly.to_csv(resolve(cfg["outputs"]["polygon_assignment"].format(split_version=sv)), index=False)
    resolve(cfg["outputs"]["report"].format(split_version=sv)).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
