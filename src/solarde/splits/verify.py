"""Verify existing geographic splits without overwriting their artifacts."""
from __future__ import annotations

import argparse
import json

import geopandas as gpd
import pandas as pd

from solarde.config import load_yaml, resolve
from solarde.data.raw import sha256
from solarde.splits.blocks import build, make_grid


def verify(labels: gpd.GeoDataFrame, blocks: gpd.GeoDataFrame, assignments: pd.DataFrame,
           cfg: dict, *, rebuild: bool = False) -> dict:
    """Check geometry, identifiers, linkage, and optionally deterministic reproduction."""
    checks = {
        "equal_area_crs": labels.crs.to_epsg() == blocks.crs.to_epsg() == 3035,
        "unique_block_ids": bool(blocks.block_id.is_unique),
        "unique_polygon_ids": bool(assignments.area_id.is_unique and labels.area_id.is_unique),
        "all_polygons_assigned": set(assignments.area_id) == set(labels.area_id),
        "known_splits": set(blocks.split) == set(cfg["fractions"]),
    }
    expected = make_grid(cfg["grid_bbox_wgs84"], cfg["block_size_m"], 3035).set_index("block_id")
    actual = blocks.set_index("block_id")
    checks["stable_grid_ids_and_geometry"] = set(expected.index) == set(actual.index) and bool(
        expected.geometry.sort_index().geom_equals_exact(actual.geometry.sort_index(), tolerance=1e-6).all()
    )
    linked = assignments.merge(blocks[["block_id", "split", "cv_fold"]], on="block_id", how="left",
                               suffixes=("", "_block"), validate="many_to_one")
    checks["assignment_split_matches_block"] = bool(
        linked.split.eq(linked.split_block).all() & linked.cv_fold.eq(linked.cv_fold_block).all()
    )
    locations = labels[["area_id", "geometry"]].merge(assignments[["area_id", "block_id"]], on="area_id")
    owner = blocks.set_index("block_id").geometry
    checks["centroids_in_owned_blocks"] = all(
        owner.loc[row.block_id].covers(row.geometry.centroid) for row in locations.itertuples()
    )
    intersections = gpd.sjoin(labels[["area_id", "geometry"]], blocks[["split", "geometry"]],
                              predicate="intersects")
    crossing = set(intersections.groupby("area_id").split.nunique().loc[lambda n: n > 1].index)
    checks["crossing_flags_match_geometry"] = crossing == set(
        assignments.loc[assignments.crosses_split_border, "area_id"]
    )
    if rebuild:
        rebuilt_blocks, rebuilt_assignments, _ = build(labels, cfg)

        def same_values(left, right):
            left, right = left.sort_index(), right.sort_index()
            return left.index.equals(right.index) and left.columns.equals(right.columns) and bool(
                left.eq(right).all().all())

        checks["deterministic_rebuild"] = same_values(
            rebuilt_blocks.set_index("block_id")[["split", "cv_fold"]],
            blocks.set_index("block_id")[["split", "cv_fold"]]) and same_values(
            rebuilt_assignments.set_index("area_id"), assignments.set_index("area_id"))
    return {"checks": checks, "accepted": all(checks.values()), "n_polygons": len(labels),
            "n_blocks": len(blocks), "polygons_crossing_split_border": len(crossing),
            "pv_area_share": {s: float(blocks.loc[blocks.split == s, "pv_ha"].sum() / blocks.pv_ha.sum())
                              for s in cfg["fractions"]},
            "region_pv_area_share": {
                str(region): {s: float(group.loc[group.split == s, "pv_ha"].sum() / group.pv_ha.sum())
                              for s in cfg["fractions"]}
                for region, group in blocks.groupby("region")},
            "region_method": "provisional longitude/latitude proxy; no reassignment performed",
            "regenerated_on_disk": False}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/splits.yaml")
    parser.add_argument("--data-config", default="configs/data.yaml")
    parser.add_argument("--rebuild-check", action="store_true", help="Rebuild in memory only and compare assignments")
    parser.add_argument("--output", default="data/processed/split_verification.json")
    parser.add_argument("--germany-boundary", help="Optional authoritative boundary GeoJSON/GPKG")
    parser.add_argument("--denmark-boundary", help="Optional authoritative boundary GeoJSON/GPKG")
    args = parser.parse_args(argv)
    cfg, data = load_yaml(args.config), load_yaml(args.data_config)
    label_path = resolve(data["outputs"]["labels"].format(label_version=data["label_version"]))
    paths = {key: resolve(value.format(split_version=cfg["split_version"]))
             for key, value in cfg["outputs"].items()}
    labels = gpd.read_file(label_path, layer="labels")
    report = verify(labels, gpd.read_file(paths["blocks"]), pd.read_csv(paths["polygon_assignment"]),
                    cfg, rebuild=args.rebuild_check)
    report["artifact_sha256"] = {key: sha256(path) for key, path in paths.items()}
    report["label_sha256"] = sha256(label_path)
    if args.germany_boundary:
        centroids = labels.geometry.centroid.to_crs(4326)
        germany = gpd.read_file(resolve(args.germany_boundary)).to_crs(4326).geometry.union_all()
        report["country_boundary_check"] = {
            "germany_boundary_sha256": sha256(resolve(args.germany_boundary)),
            "centroid_outside_germany_ids": labels.loc[~centroids.covered_by(germany), "area_id"].tolist(),
            "v1_latitude_flagged_ids": labels.loc[labels.outside_germany_flag, "area_id"].tolist(),
            "interpretation": "Centroid coverage at the supplied boundary scale; v1 labels unchanged",
        }
        if args.denmark_boundary:
            denmark = gpd.read_file(resolve(args.denmark_boundary)).to_crs(4326).geometry.union_all()
            report["country_boundary_check"]["denmark_boundary_sha256"] = sha256(resolve(args.denmark_boundary))
            report["country_boundary_check"]["centroid_in_denmark_ids"] = labels.loc[
                centroids.covered_by(denmark), "area_id"].tolist()
    output = resolve(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not report["accepted"]:
        raise SystemExit("Split verification failed")


if __name__ == "__main__":
    main()
