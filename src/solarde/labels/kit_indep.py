"""T-indep: KIT RADAR manual PV labels, mapped to the ground-mounted task.

KIT tiles (data/raw/kit_radar_pv_labels): 1 km, 0.2 m, EPSG:25832. Pixel values: 0 background,
1 rooftop PV, 2 ground-mounted PV (dataset.desc_md.xml). The task is ground-mounted only and label v1
does not label rooftops, so rooftop pixels map to background, as they do in v1.

A tile is usable only when every split-s1 block it touches is a test block, so no training block overlaps T-indep.
The manifest also counts label-v1 positive polygons that touch each tile and were commissioned after
the tile's reference year. The KIT tile may not show them, so the scorer must mask them.

Usage:
    python -m solarde.labels.kit_indep --config configs/testsets.yaml
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import rasterio
from pyproj import Transformer
from shapely.geometry import box

from solarde.config import load_yaml, resolve
from solarde.splits.tnew import provenance, sha256

TILE_RE = re.compile(r"^label_manual_(?P<region>[a-z]+)_\d{4}_\d{4}_(?P<year>\d{4})\.tif$")
KIT_CRS = "EPSG:25832"
TASK_CRS = "EPSG:3035"
ALLOWED_VALUES = (0, 1, 2)  # 0 background, 1 rooftop PV, 2 ground-mounted PV
GROUND_PV = 2


def to_task_mask(values: np.ndarray) -> np.ndarray:
    """1 where ground-mounted PV, else 0. Unknown KIT values raise instead of passing silently."""
    unknown = np.setdiff1d(np.unique(values), ALLOWED_VALUES)
    if unknown.size:
        raise ValueError(f"unexpected KIT pixel values: {unknown.tolist()}")
    return (values == GROUND_PV).astype(np.uint8)


def describe_tile(path: Path, blocks: gpd.GeoDataFrame, labels: gpd.GeoDataFrame, to_task: Transformer) -> dict:
    m = TILE_RE.match(path.name)
    if m is None:
        raise ValueError(f"unexpected KIT tile name: {path.name}")
    year = int(m["year"])
    with rasterio.open(path) as src:
        values = src.read(1)
        left, bottom, right, top = src.bounds
    tile_kit = box(left, bottom, right, top)
    xs, ys = to_task.transform([left, right, left, right], [bottom, bottom, top, top])
    tile_task = box(min(xs), min(ys), max(xs), max(ys))

    splits_hit = sorted(set(blocks.loc[blocks.intersects(tile_task), "split"]))
    touching = labels[labels.intersects(tile_kit)]
    # Label v1 ignores a polygon when any record was commissioned on or after 2025-01-01, so use the latest date.
    commissioned = pd.to_datetime(touching["commission_last"], errors="coerce").dt.year
    return {
        "tile": path.name,
        "source_sha256": sha256(path),
        "region": m["region"],
        "year": year,
        "n_px": int(values.size),
        "n_background_px": int((values == 0).sum()),
        "n_rooftop_px": int((values == 1).sum()),
        "n_ground_px": int(to_task_mask(values).sum()),
        "splits": "+".join(splits_hit),
        "usable": splits_hit == ["test"],
        "n_v1_positive_polygons_after_year": int(((touching["label_status"] == "positive") & (commissioned > year)).sum()),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = load_yaml(args.config)["tindep"]

    blocks = gpd.read_file(resolve(cfg["blocks"]))
    labels = pyogrio.read_dataframe(resolve(cfg["labels"]), columns=["label_status", "commission_last"]).to_crs(KIT_CRS)
    to_task = Transformer.from_crs(KIT_CRS, TASK_CRS, always_xy=True)

    tiles = sorted(resolve(cfg["tiles_dir"]).glob("label_manual_*.tif"))
    manifest = pd.DataFrame([describe_tile(p, blocks, labels, to_task) for p in tiles])
    out = resolve(cfg["out_manifest"])
    out.parent.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(out, index=False)

    usable = manifest[manifest["usable"]]
    report = {
        "test_set": "T-indep",
        "source": "KIT RADAR PV reference labels, Hesse and NRW (CC BY-SA 4.0)",
        "mapping": {"0": "background", "1": "rooftop PV -> background", "2": "ground-mounted PV -> positive"},
        "n_tiles": len(manifest),
        "n_usable_tiles": len(usable),
        "usable_by_region": usable["region"].value_counts().to_dict(),
        "usable_by_year": {str(k): int(v) for k, v in usable["year"].value_counts().sort_index().items()},
        "usable_ground_px": int(usable["n_ground_px"].sum()),
        "usable_v1_positive_polygons_after_year": int(usable["n_v1_positive_polygons_after_year"].sum()),
        "manifest_sha256": sha256(out),
        "blocks_sha256": sha256(resolve(cfg["blocks"])),
        "labels_sha256": sha256(resolve(cfg["labels"])),
        **provenance(resolve(args.config)),
    }
    resolve(cfg["out_report"]).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
