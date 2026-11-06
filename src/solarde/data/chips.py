"""Prepare a bounded native-UTM pilot chip plan and aligned real-label masks.

Outputs remain draft and await satellite imagery and sampling-protocol approval.
No image chip or normalization statistic is fabricated by this command.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from affine import Affine
from pyproj import Transformer
from shapely import transform as transform_geometry
from shapely.geometry import box, mapping

from solarde.config import load_yaml, resolve
from solarde.data.rasterize import label_mask
from solarde.data.raw import sha256
from solarde.splits.verify import verify


def project(transformer, geometry):
    return transform_geometry(geometry, transformer, interleaved=False)


def safe_footprint(footprint, split: str, blocks: gpd.GeoDataFrame, buffer_m: float) -> bool:
    """Enforce full split coverage and configured distance to any other split."""
    if blocks.crs.to_epsg() != 3035:
        raise ValueError("Split buffers require EPSG:3035")
    nearby = blocks.iloc[blocks.sindex.query(footprint.buffer(buffer_m), predicate="intersects")]
    same = nearby[nearby.split == split]
    other = nearby[nearby.split != split]
    return bool(len(same) and same.geometry.union_all().covers(footprint)
                and (other.empty or other.geometry.distance(footprint).min() >= buffer_m))


def nested_profiles(positive_ids: list[str], negative_ids: list[str], ratios: list[int], seed: int) -> dict:
    """Deterministic nested candidate subsets; no protocol is selected or frozen."""
    order = sorted(negative_ids, key=lambda value: hashlib.sha256(f"{seed}:{value}".encode()).hexdigest())
    return {f"draft_1to{ratio}": {"positive_ids": sorted(positive_ids),
                                "negative_ids": order[:len(positive_ids) * ratio],
                                "requested_negatives": len(positive_ids) * ratio,
                                "available_negatives": min(len(order), len(positive_ids) * ratio)}
            for ratio in ratios}


def prepare(cfg: dict) -> dict:
    data = load_yaml(cfg["data_config"])
    split_cfg = load_yaml(cfg["split_config"])
    reference = load_yaml(cfg["reference_config"])
    labels_path = resolve(data["outputs"]["labels"].format(label_version=data["label_version"]))
    paths = {key: resolve(value.format(split_version=split_cfg["split_version"]))
             for key, value in split_cfg["outputs"].items()}
    inputs = {"labels": sha256(labels_path), **{key: sha256(path) for key, path in paths.items()},
              "data_config": sha256(resolve(cfg["data_config"])),
              "split_config": sha256(resolve(cfg["split_config"])),
              "reference_config": sha256(resolve(cfg["reference_config"])),
              "preparation_code": sha256(__file__),
              "rasterization_code": sha256(Path(__file__).with_name("rasterize.py"))}
    signature = hashlib.sha256(json.dumps({"config": cfg, "inputs": inputs}, sort_keys=True).encode()).hexdigest()
    output = resolve(cfg["output_dir"])
    manifest_path = output / "manifest.json"
    if manifest_path.exists():
        saved = json.loads(manifest_path.read_text(encoding="utf-8"))
        if saved["signature"] != signature:
            raise ValueError("Existing preparation has different inputs/config; use a new output directory")
        for chip in saved["chips"]:
            if sha256(output / chip["mask_path"]) != chip["mask_sha256"]:
                raise ValueError("Existing mask checksum failed; inspect interrupted/corrupted output")
        if sha256(output / "footprints.geojson") != saved["footprints_sha256"]:
            raise ValueError("Footprint checksum failed")
        return saved
    labels = gpd.read_file(labels_path, layer="labels")
    assignments = pd.read_csv(paths["polygon_assignment"])
    blocks = gpd.read_file(paths["blocks"])
    labels = labels.to_crs(3035)
    verification = verify(labels, blocks, assignments, split_cfg)
    if not json.loads(paths["report"].read_text(encoding="utf-8"))["accepted"] or not verification["accepted"]:
        raise ValueError("Preparation requires accepted, verified spatial splits")
    split = cfg["pilot_split"]
    if split != "train":
        raise ValueError("Pilot preparation must use training blocks")
    size = int(reference["chips"]["size_px"])
    resolution = float(reference["imagery"]["gsd_m"])
    width_m = size * resolution
    buffer_m = float(reference["chips"]["border_buffer_m"])
    if buffer_m != float(split_cfg["chip_size_m"]):
        raise ValueError("Split and reference border buffer definitions disagree")
    eligible = labels[(labels.label_status == "positive") & (labels.ha >= 1)].merge(
        assignments[["area_id", "split"]], on="area_id")
    eligible = eligible[eligible.split == split].copy()
    eligible["target_distance"] = abs(eligible.ha - cfg["target_farm_ha"])
    eligible = eligible.sort_values(["target_distance", "area_id"])
    pilot = None
    for row in eligible.itertuples():
        epsg = 32600 + int((row.lon + 180) // 6) + 1
        native = Transformer.from_crs(4326, epsg, always_xy=True)
        x, y = native.transform(row.lon, row.lat)
        origin = Affine(resolution, 0, np.floor(x / resolution) * resolution - width_m / 2,
                        0, -resolution, np.ceil(y / resolution) * resolution + width_m / 2)
        to_3035 = Transformer.from_crs(epsg, 3035, always_xy=True).transform
        foot = project(to_3035, box(origin.c, origin.f - width_m, origin.c + width_m, origin.f).segmentize(100))
        if safe_footprint(foot, split, blocks, buffer_m):
            pilot = (row, epsg, origin, to_3035)
            break
    if pilot is None:
        raise ValueError("No safe positive pilot found under the configured border buffer")
    row, epsg, origin, to_3035 = pilot
    output.mkdir(parents=True, exist_ok=True)
    positives, negatives, features = [], [], []
    radius = int(cfg["grid_radius_chips"])
    offsets = sorted(((x, y) for x in range(-radius, radius + 1) for y in range(-radius, radius + 1)),
                     key=lambda p: (abs(p[0]) + abs(p[1]), p))
    for dx, dy in offsets:
        transform = origin @ Affine.translation(dx * size, dy * size)
        native_foot = box(transform.c, transform.f - width_m, transform.c + width_m, transform.f)
        footprint = project(to_3035, native_foot.segmentize(100))
        if not safe_footprint(footprint, split, blocks, buffer_m):
            continue
        local = labels.iloc[labels.sindex.query(footprint, predicate="intersects")]
        mask = label_mask(local, assignments[assignments.area_id.isin(local.area_id)], blocks,
                          crs=epsg, transform=transform, shape=(size, size), split=split)
        positive = bool((mask == 1).any())
        group = positives if positive else negatives
        maximum = cfg["max_positive_chips"] if positive else cfg["max_positive_chips"] * cfg["candidate_negative_ratio"]
        if len(group) >= maximum or (not positive and (mask == 255).any()):
            continue
        chip_id = f"pv{int(row.area_id)}_{dx:+d}_{dy:+d}"
        path = output / f"{chip_id}_mask.tif"
        temporary = path.with_suffix(".tmp.tif")
        with rasterio.open(temporary, "w", driver="GTiff", height=size, width=size, count=1,
                           dtype="uint8", crs=epsg, transform=transform, nodata=255, compress="deflate") as dest:
            dest.write(mask, 1)
            dest.update_tags(label_version=data["label_version"], split=split,
                             attribution="Manske (2026); BNetzA MaStR; dl-de/by-2-0")
        os.replace(temporary, path)
        chip = {"id": chip_id, "kind": "positive" if positive else "candidate_negative", "split": split,
                "crs": f"EPSG:{epsg}", "transform": list(transform)[:6], "shape": [size, size],
                "mask_path": path.name, "mask_sha256": sha256(path),
                "pv_pixels": int((mask == 1).sum()), "ignore_pixels": int((mask == 255).sum()),
                "image_path": None, "land_cover_stratum": None}
        group.append(chip)
        wgs84 = project(Transformer.from_crs(epsg, 4326, always_xy=True).transform, native_foot)
        features.append({"type": "Feature", "geometry": mapping(wgs84), "properties": chip})
    chips = positives + negatives
    manifest = {"schema_version": 1, "state": "draft_awaiting_imagery_and_sampling_approval",
                "signature": signature, "inputs_sha256": inputs, "label_version": data["label_version"],
                "split_version": split_cfg["split_version"], "seed": cfg["seed"],
                "pilot": {"area_id": int(row.area_id), "ha": float(row.ha), "lon": float(row.lon), "lat": float(row.lat)},
                "imagery_request": reference["imagery"], "border_buffer_m": buffer_m,
                "normalization": None, "chips": chips,
                "profiles": nested_profiles([c["id"] for c in positives], [c["id"] for c in negatives],
                                            [1, int(cfg["candidate_negative_ratio"])], cfg["seed"]),
                "limitations": ["No satellite imagery acquired; masks are label-only preparation artifacts",
                                "Land-cover stratification unavailable", "No reference sampling profile approved"]}
    (output / "footprints.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": features}),
                                               encoding="utf-8")
    manifest["footprints_sha256"] = sha256(output / "footprints.geojson")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/preparation.yaml")
    args = parser.parse_args(argv)
    result = prepare(load_yaml(args.config))
    print(json.dumps({"state": result["state"], "pilot": result["pilot"], "n_masks": len(result["chips"]),
                      "profiles": result["profiles"]}, indent=2))


if __name__ == "__main__":
    main()
