"""M1.5 sampling and export checks, using synthetic labels only."""
import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from make_semantics_sample import export_sample, sample_polygons


def toy_labels(n: int = 120) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame({
        "area_id": range(n), "label_status": ["ignore"] * n, "ha": [1.0] * n,
        "outside_germany_flag": [True] * n,
        "geometry": [box(4_000_000 + i * 100, 3_000_000, 4_000_050 + i * 100, 3_000_050) for i in range(n)],
    }, crs=3035)


def test_sample_is_unique_reproducible_and_does_not_filter_ignore_or_foreign_labels():
    labels = toy_labels()
    sample = sample_polygons(labels)
    assert len(sample) == 100
    assert sample["area_id"].is_unique
    assert sample["audit_id"].tolist() == [f"P{i:03d}" for i in range(1, 101)]
    assert sample["area_id"].tolist() == sample_polygons(labels.iloc[::-1])["area_id"].tolist()
    assert sample["area_id"].tolist() != sample_polygons(labels, seed=1)["area_id"].tolist()
    assert sample.crs.to_epsg() == 3035
    original = labels.set_index("area_id").geometry
    assert all(row.geometry.equals(original.loc[row.area_id]) for row in sample.itertuples())
    assert "audit_id" not in labels


@pytest.mark.parametrize("n", [0, 121])
def test_invalid_sample_size(n):
    with pytest.raises(ValueError, match="sample size"):
        sample_polygons(toy_labels(), n=n)


def test_duplicate_ids_rejected():
    labels = toy_labels()
    labels.loc[1, "area_id"] = 0
    with pytest.raises(ValueError, match="unique"):
        sample_polygons(labels)


def test_export_has_matching_blank_form_and_protects_existing_review(tmp_path):
    labels_path = tmp_path / "labels.gpkg"
    toy_labels().to_file(labels_path, layer="labels", driver="GPKG")
    source_bytes = labels_path.read_bytes()
    out = tmp_path / "audit"
    export_sample(labels_path, out)
    polygons = gpd.read_file(out / "polygons.gpkg", layer="polygons")
    form = pd.read_csv(out / "review_form.csv", keep_default_na=False)
    assert len(polygons) == len(form) == 100
    assert form["area_id"].tolist() == polygons["area_id"].tolist()
    assert form["audit_id"].tolist() == polygons["audit_id"].tolist()
    assert (form[["outline_class", "imagery_date", "imagery_source", "notes"]] == "").all().all()
    manifest = json.loads((out / "sample_manifest.json").read_text(encoding="utf-8"))
    assert manifest["area_ids"] == form["area_id"].tolist()
    assert "dl-de/by-2-0" in manifest["attribution"]
    assert (out / "README.md").is_file()
    assert not list(out.glob("*.qgs"))
    form.loc[0, "outline_class"] = "panel_rows"
    form.to_csv(out / "review_form.csv", index=False)
    completed_form = (out / "review_form.csv").read_bytes()
    with pytest.raises(FileExistsError):
        export_sample(labels_path, out)
    assert (out / "review_form.csv").read_bytes() == completed_form
    assert labels_path.read_bytes() == source_bytes
