"""T-new: label-v1 positives added in the current release, held out in split s1 test blocks.

T-new = current polygons with no comparator polygon at IoU >= match_iou and no comparator polygon within
revised_within_m (those are revisions of an existing farm, not additions). area_id is not a stable key
across releases: shared ids have median centroid shifts of 288 km. Restricted to label-v1 positives,
to test blocks, and to polygons that do not cross a split border (their extent would reach another
split). The comparator is V20240104, substituting for V20250101 (access denied).

Usage:
    python -m solarde.splits.tnew --config configs/testsets.yaml
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import shapely
from shapely.strtree import STRtree

from solarde.config import REPO_ROOT, load_yaml, resolve


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def provenance(config_path: Path) -> dict:
    """Git commit, dirty flag and config hash, so a report traces back to the code that wrote it."""

    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False).stdout.strip()

    return {
        "git_hash": git("rev-parse", "HEAD") or None,
        "git_dirty": bool(git("status", "--porcelain")),
        "config_sha256": sha256(config_path),
    }


def best_iou(current: gpd.GeoSeries, comparator: gpd.GeoSeries) -> pd.Series:
    """Highest IoU between each current polygon and any comparator polygon. Both must share a CRS."""
    cur = shapely.make_valid(current.to_numpy())
    ref = shapely.make_valid(comparator.to_numpy())
    best = np.zeros(len(cur))
    i, j = STRtree(ref).query(cur)  # candidate pairs whose envelopes overlap
    inter = shapely.area(shapely.intersection(cur[i], ref[j]))
    union = shapely.area(shapely.union(cur[i], ref[j]))
    iou = np.divide(inter, union, out=np.zeros_like(inter), where=union > 0)
    np.maximum.at(best, i, iou)
    return pd.Series(best, index=current.index)


def nearest_distance(current: gpd.GeoSeries, comparator: gpd.GeoSeries) -> pd.Series:
    """Distance (CRS units, metres for EPSG:3035) from each current polygon to the nearest comparator polygon."""
    cur = shapely.make_valid(current.to_numpy())
    ref = shapely.make_valid(comparator.to_numpy())
    idx, dist = STRtree(ref).query_nearest(cur, return_distance=True, all_matches=False)
    out = np.full(len(cur), np.inf)
    out[idx[0]] = dist
    return pd.Series(out, index=current.index)


def new_polygon_ids(best: pd.Series, dist: pd.Series, match_iou: float, revised_within_m: float) -> set[int]:
    """Current polygons with no comparator match and no comparator polygon nearby (added farms)."""
    is_new = (best < match_iou) & (dist >= revised_within_m)
    return set(best.index[is_new].astype(int))


def select_tnew(labels: pd.DataFrame, splits: pd.DataFrame, new_ids: set[int]) -> tuple[pd.DataFrame, dict]:
    """Return the T-new rows and the count remaining after each filter."""
    pos = labels.loc[labels["label_status"].eq("positive") & labels["area_id"].isin(sorted(new_ids)), ["area_id"]]
    m = pos.merge(splits[["area_id", "block_id", "split", "crosses_split_border"]], on="area_id", how="inner")
    in_test = m.loc[m["split"].eq("test")]
    tnew = in_test.loc[~in_test["crosses_split_border"].astype(bool), ["area_id", "block_id"]]
    counts = {
        "new_ids": len(new_ids),
        "new_label_v1_positive": len(pos),
        "in_test_blocks": len(in_test),
        "tnew": len(tnew),
    }
    return tnew.sort_values("area_id").reset_index(drop=True), counts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = load_yaml(args.config)["tnew"]

    current_path, comparator_path = resolve(cfg["current"]), resolve(cfg["comparator"])
    cur = gpd.read_file(current_path).to_crs(3035).set_index("area_id")
    ref = gpd.read_file(comparator_path).to_crs(3035)
    best = best_iou(cur.geometry, ref.geometry)
    dist = nearest_distance(cur.geometry, ref.geometry)
    new_ids = new_polygon_ids(best, dist, cfg["match_iou"], cfg["revised_within_m"])
    n_revised = int(((best < cfg["match_iou"]) & (dist < cfg["revised_within_m"])).sum())
    labels = pyogrio.read_dataframe(resolve(cfg["labels"]), columns=["area_id", "label_status"], read_geometry=False)
    splits = pd.read_csv(resolve(cfg["polygon_split"]))

    tnew, counts = select_tnew(labels, splits, new_ids)

    out_csv = resolve(cfg["out_csv"])
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    tnew.to_csv(out_csv, index=False)
    report = {
        "test_set": "T-new",
        "labels": "v1",
        "split_version": "s1",
        "match_iou": cfg["match_iou"],
        "revised_within_m": cfg["revised_within_m"],
        "unmatched_but_revised_excluded": n_revised,
        "current_release": {"path": cfg["current"], "sha256": sha256(current_path)},
        "comparator_release": {"path": cfg["comparator"], "sha256": sha256(comparator_path)},
        "counts": counts,
        "tnew_csv_sha256": sha256(out_csv),
        "polygon_split_sha256": sha256(resolve(cfg["polygon_split"])),
        **provenance(resolve(args.config)),
    }
    resolve(cfg["out_report"]).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
