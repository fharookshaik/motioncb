"""Inspect/import the configured solar sources and validate the real label release."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

import pandas as pd

from solarde.config import load_yaml, resolve
from solarde.labels.curate import build_report, curate, load_raw


def sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_sources(archive: str | Path, cfg: dict) -> dict:
    """Selectively extract the configured GPKG/CSV, refusing conflicting files.

    Preflight the complete ZIP and both destinations before writing anything.
    The original archive stays at its existing location. Identical sources are
    reused without rewriting them; raw records are never modified.
    """
    archive = Path(archive).resolve(strict=True)
    extracted = []
    with zipfile.ZipFile(archive) as package:
        names = package.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Archive has duplicate member paths")
        for name in names:
            member = PurePosixPath(name)
            if member.is_absolute() or ".." in member.parts or "\\" in name:
                raise ValueError(f"Unsafe archive member: {name}")
        if bad := package.testzip():
            raise ValueError(f"Archive CRC failure: {bad}")
        pending = []
        for key, directory in (("polygons", "gpkg"), ("records", "csv")):
            target = resolve(cfg["raw"][key])
            member = f"{cfg['raw']['release']}/{directory}/{target.name}"
            data = package.read(member)
            digest = hashlib.sha256(data).hexdigest()
            if target.is_symlink() or any(parent.is_symlink() for parent in target.parents):
                raise ValueError(f"Refusing symlink destination: {target}")
            if target.exists() and sha256(target) != digest:
                raise ValueError(f"Existing raw source differs; refusing to overwrite: {target}")
            pending.append((target, member, data, digest))
        for target, member, data, digest in pending:
            reused = target.exists()
            if not reused:
                target.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as temp:
                    temp.write(data)
                    temp_path = Path(temp.name)
                try:
                    os.replace(temp_path, target)
                finally:
                    temp_path.unlink(missing_ok=True)
            extracted.append({"path": str(target), "member": member, "sha256": digest,
                              "bytes": len(data), "reused": reused})
    return {"archive": str(archive), "archive_sha256": sha256(archive), "crc_valid": True,
            "sources": extracted}


def validate_sources(cfg: dict) -> dict:
    """Measure geometry, linkage, date, and label invariants from actual files."""
    polygons, records = load_raw(cfg)
    raw_records = pd.read_csv(resolve(cfg["raw"]["records"]), sep=";")
    date_errors, partial_dates = {}, {}
    for name in ("commissioning_date", "decommissioning_date"):
        unparsed = raw_records[name].notna() & records[name].isna()
        year_only = raw_records[name].astype("string").str.fullmatch(r"\d{4}", na=False)
        partial_dates[name] = int((unparsed & year_only).sum())
        date_errors[name] = int((unparsed & ~year_only).sum())
    labels = curate(polygons, records, cfg)
    measured = {
        "source_crs": str(polygons.crs),
        "geometry_types": polygons.geom_type.value_counts().to_dict(),
        "missing_geometry": int(polygons.geometry.isna().sum()),
        "empty_geometry": int(polygons.geometry.is_empty.sum()),
        "invalid_geometry": int((~polygons.geometry.is_valid).sum()),
        "duplicate_area_ids": int(polygons.area_id.duplicated().sum()),
        "missing_area_ids": int(polygons.area_id.isna().sum()),
        "n_records": len(records),
        "records_without_polygon": int((~records.area_id.isin(polygons.area_id)).sum()),
        "polygons_without_records": int((~polygons.area_id.isin(records.area_id)).sum()),
        "record_date_parse_errors": date_errors,
        "year_only_dates_treated_as_missing_by_v1": partial_dates,
        "commissioning_date_missing": int(records.commissioning_date.isna().sum()),
        "commissioning_date_range": [str(records.commissioning_date.min()), str(records.commissioning_date.max())],
        "area_accuracy_counts": {str(k): int(v) for k, v in polygons.area_accuracy.value_counts().items()},
        "label_report": build_report(labels, cfg),
    }
    failures = [name for name in ("missing_geometry", "empty_geometry", "invalid_geometry",
                                 "duplicate_area_ids", "missing_area_ids", "records_without_polygon")
                if measured[name]]
    if any(date_errors.values()):
        failures.append("record_date_parse_errors")
    if cfg["raw"]["release"] == "V20260203" and cfg["label_version"] == "v1":
        expected = {"n_polygons": 10984, "n_positive": 9219, "n_ignore": 1765}
        measured["expected_counts_match"] = all(measured["label_report"][k] == v for k, v in expected.items())
        if not measured["expected_counts_match"]:
            failures.append("expected_label_counts")
    measured["failures"] = failures
    measured["accepted"] = not failures
    return measured


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/data.yaml")
    parser.add_argument("--archive", type=Path, help="Original local ZIP; remains at this path")
    parser.add_argument("--output", default="data/interim/raw_validation.json")
    args = parser.parse_args(argv)
    cfg = load_yaml(args.config)
    archive_report = extract_sources(args.archive, cfg) if args.archive else None
    report = validate_sources(cfg)
    if archive_report:
        report["import"] = archive_report
    output = resolve(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not report["accepted"]:
        raise SystemExit("Source validation failed; see report")


if __name__ == "__main__":
    main()
