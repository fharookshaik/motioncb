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
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

from solarde.config import load_yaml, resolve
from solarde.splits.tnew import provenance, sha256

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


def summarise_audit(windows: gpd.GeoDataFrame, labels: gpd.GeoDataFrame, form: pd.DataFrame,
                    excluded: dict[str, int], seed: int, resamples: int) -> dict:
    """Conditional omission, resampling whole windows/blocks, not individual farms."""
    ids = windows["window_id"]
    if not ids.is_unique or not windows["block_id"].is_unique or not form["window_id"].is_unique:
        raise ValueError("Expected one form row per window and one window per block")
    if set(ids) != set(form["window_id"]) or not set(excluded) <= set(ids):
        raise ValueError("Form/exclusion window IDs do not match the retained windows")
    counts = pd.to_numeric(form.set_index("window_id")["missing_pv_count"], errors="raise").reindex(ids)
    if counts.isna().any() or (counts < 0).any() or (counts % 1 != 0).any():
        raise ValueError("Every window needs a non-negative integer missing count")
    outside = np.array([excluded.get(wid, 0) for wid in ids])
    if (outside < 0).any() or (outside % 1 != 0).any() or (outside > counts.to_numpy()).any():
        raise ValueError("Excluded outside-window counts must be integers between zero and the observed count")
    missed = counts.to_numpy(dtype=int) - outside
    positive = labels.loc[labels["label_status"].eq("positive")].to_crs(windows.crs)
    contained = np.array([int(positive.geometry.within(win).sum()) for win in windows.geometry])
    total = int(contained.sum() + missed.sum())
    if not total or not len(windows) or resamples < 1:
        raise ValueError("Need non-empty windows, a positive denominator and resamples >= 1")
    rng = np.random.default_rng(seed)
    rates = []
    for _ in range(resamples):
        index = rng.integers(0, len(windows), len(windows))
        denominator = int(contained[index].sum() + missed[index].sum())
        if denominator == 0:
            raise ValueError("Bootstrap replicate has zero denominator")
        rates.append(float(missed[index].sum() / denominator))
    return {
        "n_windows": len(windows), "labelled_fully_contained": int(contained.sum()),
        "missed_inside": int(missed.sum()), "excluded_outside": excluded,
        "omission_rate": float(missed.sum() / total), "ci95": np.quantile(rates, [0.025, 0.975]).tolist(),
        "bootstrap_seed": seed, "resamples": resamples,
        "scope": "Conditional on label-anchored windows; not landscape-wide omission or current held-out-only coverage",
        "denominator_approval": "pending researcher confirmation",
    }


def print_summary(config_path: Path, cfg: dict) -> None:
    audit = cfg["audit"]
    paths = {key: resolve(audit[key]) for key in ("windows", "form", "labels")}
    summary = summarise_audit(
        gpd.read_file(paths["windows"]), gpd.read_file(paths["labels"], layer="labels"),
        pd.read_csv(paths["form"]), audit["excluded_outside_counts"], audit["seed"], audit["resamples"],
    )
    summary["input_sha256"] = {key: sha256(path) for key, path in paths.items()}
    summary.update(provenance(config_path))
    print(json.dumps(summary, indent=2))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="configs/splits.yaml")
    ap.add_argument("--summary", action="store_true", help="Read the retained audit and print statistics; never write files")
    args = ap.parse_args(argv)
    cfg = load_yaml(args.config)
    if args.summary:
        print_summary(resolve(args.config), cfg)
        return
    out = resolve(cfg.get("audit", {}).get("out_dir", OUT_DIR))
    if any(out.glob("*")):
        raise SystemExit("Refusing to overwrite an existing audit. Choose a new audit.out_dir in the config.")
    v = cfg["split_version"]
    blocks = gpd.read_file(resolve(cfg["outputs"]["blocks"].format(split_version=v)), layer="blocks")
    polys = pd.read_csv(resolve(cfg["outputs"]["polygon_assignment"].format(split_version=v)))
    labels = gpd.read_file(resolve(LABELS_PATH), layer="labels")
    labels = labels.merge(polys[["area_id", "block_id", "crosses_split_border"]], on="area_id",
                          how="left", validate="one_to_one")
    if labels["block_id"].isna().any():
        raise ValueError("labels without a block assignment")
    win = sample_windows(labels, blocks, N_PER_REGION, SEED)
    out.mkdir(parents=True, exist_ok=True)
    win.to_file(out / "windows.gpkg", driver="GPKG", layer="windows")
    pd.DataFrame({"window_id": win["window_id"], "missing_pv_count": "", "notes": ""}).to_csv(
        out / "audit_form.csv", index=False
    )
    print(f"{len(win)} windows written to {out}")


if __name__ == "__main__":
    main()
