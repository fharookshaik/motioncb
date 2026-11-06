"""Acquire one real pilot scene for alignment QA, separately from reference training data."""
from __future__ import annotations

import argparse
import json
import time

import matplotlib.pyplot as plt
import numpy as np
import rasterio
from affine import Affine
from rasterio.warp import transform_bounds

from solarde.config import load_yaml, resolve
from solarde.data.raw import sha256
from solarde.imagery.stac import COLLECTION, ENDPOINT, read_grid, reflectance, search, select_assets


def acquire(config: dict) -> dict:
    root = resolve(config["output_dir"])
    plan_path = root / "manifest.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    chip = next(chip for chip in plan["chips"] if chip["id"].endswith("_+0_+0"))
    output = root / "preview"
    output.mkdir(exist_ok=True)
    report_path = output / "manifest.json"
    inputs = {"plan": sha256(plan_path), "code": sha256(__file__),
              "provider_code": sha256(resolve("src/solarde/imagery/stac.py"))}
    if report_path.exists():
        saved = json.loads(report_path.read_text(encoding="utf-8"))
        if saved["inputs_sha256"] != inputs:
            raise ValueError("Preview inputs/code changed; preserve outputs and use a new preparation directory")
        for name, checksum in saved["outputs_sha256"].items():
            if sha256(output / name) != checksum:
                raise ValueError(f"Corrupted preview output: {name}")
        return saved
    started = time.perf_counter()
    transform = Affine(*chip["transform"])
    height, width = chip["shape"]
    bounds = rasterio.transform.array_bounds(height, width, transform)
    bbox = list(transform_bounds(chip["crs"], "EPSG:4326", *bounds, densify_pts=21))
    cache = output / "items.json"
    query = {"bbox": bbox, "window": plan["imagery_request"]["window"],
             "endpoint": ENDPOINT, "collection": COLLECTION, "max_cloud": 20}
    if cache.exists():
        cached = json.loads(cache.read_text(encoding="utf-8"))
        items = cached["items"] if isinstance(cached, dict) and cached.get("query") == query else None
    else:
        items = None
    if items is None:
        items = search(bbox, plan["imagery_request"]["window"], max_cloud=query["max_cloud"])
        cache.write_text(json.dumps({"query": query, "items": items}), encoding="utf-8")
    if not items:
        raise ValueError("No scenes meet the bounded pilot search constraints")
    item = items[0]
    bands = plan["imagery_request"]["bands"]
    assets = select_assets(item, bands)
    image = []
    for band in bands:
        print(f"Reading {band} window from {item['id']}", flush=True)
        image.append(reflectance(read_grid(assets[band], crs=chip["crs"], transform=transform,
                                          shape=(height, width)), assets[band]))
    image = np.stack(image)
    scl = read_grid(item["assets"]["scl"], crs=chip["crs"], transform=transform,
                    shape=(height, width), categorical=True)
    cloud = read_grid(item["assets"]["cloud"], crs=chip["crs"], transform=transform,
                      shape=(height, width), categorical=True, zero_is_valid=True)
    valid = np.isfinite(image).all(axis=0) & np.isin(scl, [4, 5, 6]) & np.isfinite(cloud) & (cloud <= 40)
    image[:, ~valid] = np.nan
    with rasterio.open(root / chip["mask_path"]) as source:
        mask = source.read(1)
    if valid.mean() < 0.5 or not ((mask == 1) & valid).any():
        raise ValueError("Selected scene has inadequate valid coverage over the pilot PV label")
    mask[~valid] = 255
    for name, array, nodata, dtype in (("image.tif", image, np.nan, "float32"),
                                      ("mask.tif", mask[None], 255, "uint8"),
                                      ("valid.tif", valid.astype(np.uint8)[None], None, "uint8")):
        with rasterio.open(output / name, "w", driver="GTiff", width=width, height=height,
                           count=array.shape[0], dtype=dtype, crs=chip["crs"], transform=transform,
                           nodata=nodata, compress="deflate") as dest:
            dest.write(array)
            if name == "image.tif":
                dest.descriptions = tuple(bands)
            dest.update_tags(purpose="exploratory single-scene alignment QA; not reference training data",
                             attribution="Contains modified Copernicus Sentinel data 2025; Manske (2026); BNetzA MaStR")
    rgb = np.moveaxis(image[[bands.index(b) for b in ["B04", "B03", "B02"]]], 0, -1)
    rgb = np.nan_to_num(np.clip(rgb / 0.3, 0, 1))
    figure, axes = plt.subplots(1, 4, figsize=(16, 4))
    axes[0].imshow(rgb); axes[0].set_title("Sentinel-2 RGB")
    axes[1].imshow(mask, vmin=0, vmax=1, cmap="gray"); axes[1].set_title("PV mask (ignore=255)")
    axes[2].imshow(rgb); axes[2].imshow(np.ma.masked_where(mask != 1, mask), cmap="autumn", alpha=0.5)
    axes[2].set_title("Label overlay")
    axes[3].imshow(mask == 255, cmap="gray", vmin=0, vmax=1); axes[3].set_title("Ignore / invalid")
    for axis in axes:
        axis.axis("off")
    figure.suptitle(f"Exploratory single scene • {item['id']} • area_id {plan['pilot']['area_id']}")
    figure.tight_layout()
    figure.savefig(output / "qa.png", dpi=140)
    plt.close(figure)
    report = {"purpose": "exploratory_single_scene_alignment_QA", "reference_compliant": False,
              "limitations": ["Single scene, not Apr–Sep median", "SCL + Sen2Cor cloud probability, not approved s2cloudless fallback"],
              "inputs_sha256": inputs, "source_endpoint": ENDPOINT, "collection": COLLECTION,
              "item_id": item["id"], "datetime": item["properties"]["datetime"], "bands": bands,
              "mask_method": "SCL classes 4/5/6 and Sen2Cor cloud probability <=40 percent",
              "reflectance": {b: assets[b]["raster:bands"] for b in bands},
              "crs": chip["crs"], "transform": chip["transform"], "shape": chip["shape"],
              "valid_fraction": float(valid.mean()), "pv_pixels": int((mask == 1).sum()),
              "elapsed_seconds": time.perf_counter() - started,
              "outputs_sha256": {name: sha256(output / name)
                                  for name in ["image.tif", "mask.tif", "valid.tif", "qa.png", "items.json"]}}
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/preparation.yaml")
    args = parser.parse_args(argv)
    print(json.dumps(acquire(load_yaml(args.config)), indent=2))


if __name__ == "__main__":
    main()
