"""Label curation: turn the raw UFZ/MaStR release into a versioned label file.

Every polygon ends up with ``label_status`` in {"positive", "ignore"} and, when
ignored, a semicolon-separated ``ignore_reason``. "ignore" pixels are excluded
from both the loss and the metrics. Nothing is ever deleted: the two
cross-border polygons are kept and only flagged (decision 2026-11-03).

Usage:
    python -m solarde.labels.curate --config configs/data.yaml
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone

import geopandas as gpd
import numpy as np
import pandas as pd

from solarde.config import load_yaml, resolve

STATUS_POSITIVE = "positive"
STATUS_IGNORE = "ignore"


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_raw(cfg: dict) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    polys = gpd.read_file(resolve(cfg["raw"]["polygons"]))
    recs = pd.read_csv(resolve(cfg["raw"]["records"]), sep=";")
    for col in ("commissioning_date", "decommissioning_date"):
        recs[col] = pd.to_datetime(recs[col], errors="coerce")
    return polys, recs


def aggregate_records(recs: pd.DataFrame) -> pd.DataFrame:
    """One row per area_id with build dates, capacity and dominant mounting type."""

    def mode_or_na(s: pd.Series):
        s = s.dropna()
        return s.mode().iat[0] if len(s) else pd.NA

    g = recs.groupby("area_id")
    out = pd.DataFrame(
        {
            "n_records": g.size(),
            "capacity_kw": g["installed_capacity"].sum(min_count=1),
            "commission_first": g["commissioning_date"].min(),
            "commission_last": g["commissioning_date"].max(),
            "commission_missing": g["commissioning_date"].apply(lambda s: s.isna().any()),
            "decommission_first": g["decommissioning_date"].min(),
            "mounting": g["location"].agg(mode_or_na),
            "alignment": g["alignment"].agg(mode_or_na),
            "inclination": g["inclination"].agg(mode_or_na),
        }
    )
    return out


def curate(polys: gpd.GeoDataFrame, recs: pd.DataFrame, cfg: dict) -> gpd.GeoDataFrame:
    lab = cfg["labels"]
    win = cfg["imagery_window"]
    w_start = pd.Timestamp(win["start"])
    w_end = pd.Timestamp(win["end"])
    cutoff = w_start - pd.DateOffset(months=int(win["commissioning_buffer_months"]))

    gdf = polys.to_crs(cfg["crs"]["equal_area"]).copy()
    gdf = gdf.merge(aggregate_records(recs), left_on="area_id", right_index=True, how="left")

    gdf["ha"] = gdf.geometry.area / 1e4
    bins = lab["size_bins_ha"]
    gdf["size_bin"] = pd.cut(gdf["ha"], bins=bins, right=False).astype(str)
    gdf["large_scale"] = gdf["ha"] >= lab["large_scale_min_ha"]

    centroid_wgs = gdf.geometry.centroid.to_crs(4326)
    gdf["lon"], gdf["lat"] = centroid_wgs.x, centroid_wgs.y
    gdf["outside_germany_flag"] = gdf["lat"] > lab["germany_lat_max"]

    reasons: list[list[str]] = [[] for _ in range(len(gdf))]

    def flag(mask: pd.Series, reason: str) -> None:
        for i in np.flatnonzero(mask.to_numpy()):
            reasons[i].append(reason)

    if lab["ignore_area_accuracy_2"]:
        flag(gdf["area_accuracy"] == 2, "area_accuracy_2")
    if lab["ignore_unlinked"]:
        flag(gdf["area_related"] == 0, "unlinked")
    linked = gdf["n_records"].notna()
    flag(linked & gdf["commission_missing"].fillna(False).astype(bool), "commission_date_missing")
    flag(linked & (gdf["commission_last"] >= cutoff), "built_after_cutoff")
    flag(linked & (gdf["decommission_first"] <= w_end), "decommissioned")
    if not lab["keep_outside_germany"]:
        flag(gdf["outside_germany_flag"], "outside_germany")

    gdf["ignore_reason"] = [";".join(r) for r in reasons]
    gdf["label_status"] = np.where(gdf["ignore_reason"] == "", STATUS_POSITIVE, STATUS_IGNORE)
    gdf["multi_phase"] = (
        gdf["commission_last"].dt.year - gdf["commission_first"].dt.year
    ).fillna(0) >= 1

    for col in ("commission_first", "commission_last", "decommission_first"):
        gdf[col] = gdf[col].dt.strftime("%Y-%m-%d")
    return gdf


def build_report(gdf: gpd.GeoDataFrame, cfg: dict) -> dict:
    reason_counts: dict[str, int] = {}
    for r in gdf["ignore_reason"]:
        for part in filter(None, r.split(";")):
            reason_counts[part] = reason_counts.get(part, 0) + 1
    pos = gdf[gdf.label_status == STATUS_POSITIVE]
    return {
        "label_version": cfg["label_version"],
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "raw_polygons_sha256": _sha256(resolve(cfg["raw"]["polygons"])),
        "raw_records_sha256": _sha256(resolve(cfg["raw"]["records"])),
        "n_polygons": int(len(gdf)),
        "n_positive": int(len(pos)),
        "n_ignore": int((gdf.label_status == STATUS_IGNORE).sum()),
        "positive_ha": round(float(pos.ha.sum()), 1),
        "n_positive_large_scale": int(pos.large_scale.sum()),
        "ignore_reasons": dict(sorted(reason_counts.items())),
        "outside_germany_flagged": int(gdf.outside_germany_flag.sum()),
        "positive_by_size_bin": dict(
            sorted(
                pos.groupby("size_bin", observed=True).size().to_dict().items(),
                key=lambda kv: float(kv[0].split(",")[0].lstrip("[")),
            )
        ),
        "positive_by_mounting": pos["mounting"].fillna("unlinked").value_counts().to_dict(),
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="configs/data.yaml")
    args = ap.parse_args(argv)
    cfg = load_yaml(args.config)

    polys, recs = load_raw(cfg)
    gdf = curate(polys, recs, cfg)
    out = resolve(cfg["outputs"]["labels"].format(label_version=cfg["label_version"]))
    out.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(out, driver="GPKG", layer="labels")

    report = build_report(gdf, cfg)
    rep_path = resolve(cfg["outputs"]["labels_report"].format(label_version=cfg["label_version"]))
    rep_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
