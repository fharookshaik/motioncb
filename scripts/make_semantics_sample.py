"""M1.5: export 100 random label-v1 polygons and a blank manual-review form, without a QGIS project."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from solarde.config import load_yaml, resolve

SEED = 20261106
N_POLYGONS = 100
ATTRIBUTION = "Manske (2026); BNetzA MaStR; UFZ/MaStR V20260203; dl-de/by-2-0"


def sample_polygons(labels: gpd.GeoDataFrame, n: int = N_POLYGONS, seed: int = SEED) -> gpd.GeoDataFrame:
    """Uniform sample without replacement from all v1 polygons, including ignore labels."""
    if n < 1 or n > len(labels):
        raise ValueError(f"sample size must be between 1 and {len(labels)}")
    if labels["area_id"].isna().any() or not labels["area_id"].is_unique:
        raise ValueError("area_id must be non-null and unique")
    if labels.crs is None or labels.geometry.isna().any() or labels.geometry.is_empty.any():
        raise ValueError("labels need a CRS and non-empty geometries")
    ordered = labels.sort_values("area_id").reset_index(drop=True)
    indices = np.random.default_rng(seed).choice(len(ordered), size=n, replace=False)
    sample = ordered.iloc[indices].copy().reset_index(drop=True).to_crs(3035)
    sample.insert(0, "audit_id", [f"P{i + 1:03d}" for i in range(n)])
    return sample


def export_sample(labels_path: Path, out: Path) -> None:
    """Create a new audit directory; never overwrite an existing review."""
    sample = sample_polygons(gpd.read_file(labels_path, layer="labels"))
    out.mkdir(parents=True, exist_ok=False)
    sample.to_file(out / "polygons.gpkg", layer="polygons", driver="GPKG", metadata={"attribution": ATTRIBUTION})
    form = pd.DataFrame(sample[["audit_id", "area_id", "label_status", "ha"]])
    for column in ["outline_class", "imagery_date", "imagery_source", "notes"]:
        form[column] = ""
    form.to_csv(out / "review_form.csv", index=False)
    with labels_path.open("rb") as source:
        labels_sha256 = hashlib.file_digest(source, "sha256").hexdigest()
    metadata = {
        "task": "M1.5", "label_version": "v1", "seed": SEED, "n": len(sample),
        "population": "all label-v1 polygons, including ignore and outside-Germany polygons",
        "labels_path": str(labels_path),
        "labels_sha256": labels_sha256,
        "area_ids": sample["area_id"].tolist(), "attribution": ATTRIBUTION,
    }
    (out / "sample_manifest.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    instructions = resolve("docs/semantics_audit.md").read_text(encoding="utf-8")
    (out / "README.md").write_text(instructions, encoding="utf-8")
    print(f"{len(sample)} polygons written to {out}; review instructions: {out / 'README.md'}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/data.yaml")
    parser.add_argument("--output", default="runs/audit_m1_5")
    args = parser.parse_args(argv)
    config = load_yaml(args.config)
    if config["label_version"] != "v1":
        raise ValueError("M1.5 requires frozen label version v1")
    labels_path = resolve(config["outputs"]["labels"].format(label_version="v1"))
    export_sample(labels_path, resolve(args.output))


if __name__ == "__main__":
    main()
