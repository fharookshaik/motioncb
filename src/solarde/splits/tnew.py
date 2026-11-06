"""T-new: test-split polygons of V20260203 absent from V20250101 (ROADMAP M1.6).

Matches on `area_id`. ponytail: assumes ids persist across releases (unverified, no V20250101 copy yet);
if they do not, match on geometry overlap instead.

Usage:
    python -m solarde.splits.tnew --config configs/data.yaml --split-config configs/splits.yaml
"""
from __future__ import annotations

import argparse

import geopandas as gpd
import pandas as pd

from solarde.config import load_yaml, resolve


def select_tnew(assign: pd.DataFrame, previous_ids: set[int]) -> pd.DataFrame:
    """Rows of the polygon assignment in the test split whose area_id is not in the previous release."""
    test = assign[assign["split"] == "test"]
    return test[~test["area_id"].isin(previous_ids)]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="configs/data.yaml")
    ap.add_argument("--split-config", default="configs/splits.yaml")
    args = ap.parse_args(argv)
    dcfg = load_yaml(args.config)
    scfg = load_yaml(args.split_config)

    prev = resolve(dcfg["raw"]["previous_polygons"])
    if not prev.exists():
        raise SystemExit(f"Missing {prev}. Request access to Zenodo 16942382 first (ROADMAP M1.6).")
    previous_ids = set(gpd.read_file(prev, columns=["area_id"])["area_id"])

    v = scfg["split_version"]
    assign = pd.read_csv(resolve(scfg["outputs"]["polygon_assignment"].format(split_version=v)))
    if not assign["area_id"].isin(previous_ids).any():
        raise SystemExit("No area_id overlap with previous release: id scheme or dtype differs.")
    tnew = select_tnew(assign, previous_ids)
    out = resolve(f"data/processed/tnew_{v}.csv")
    tnew[["area_id", "block_id"]].to_csv(out, index=False)
    print(f"T-new: {len(tnew)} test polygons not in {prev.name} -> {out}")


if __name__ == "__main__":
    main()
