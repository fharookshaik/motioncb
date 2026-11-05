"""Turn a georeferenced probability raster into GIS-ready PV candidate polygons.

This is post-processing only: it does not run a model or choose a threshold from
evaluation data. Thresholds must come from the frozen experiment configuration.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from pyproj import CRS, Transformer
from rasterio.features import shapes
from scipy import ndimage
from shapely import transform as transform_geometry
from shapely.geometry import shape

from solarde.config import load_yaml, resolve


def polygonize_probabilities(
    raster_path: str | Path,
    *,
    threshold: float,
    min_area_ha: float = 0.0,
    area_crs: str | int = "EPSG:3035",
) -> dict[str, Any]:
    """Return GeoJSON FeatureCollection from a single-band probability GeoTIFF.

    Components use 8-connectivity. Nodata and non-finite values are excluded.
    The raster CRS must be projected; area is computed in ``area_crs`` and
    output geometries are transformed to WGS84 as required by GeoJSON.
    """
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between 0 and 1")
    if min_area_ha < 0:
        raise ValueError("min_area_ha must be non-negative")

    with rasterio.open(raster_path) as src:
        if src.count != 1:
            raise ValueError(f"Expected a single-band probability raster; got {src.count} bands")
        if src.crs is None or not src.crs.is_projected:
            raise ValueError("Probability raster must have a projected CRS")
        probability = src.read(1, masked=True).astype(np.float32).filled(np.nan)
        valid = np.isfinite(probability)
        if valid.any() and (np.nanmin(probability[valid]) < 0 or np.nanmax(probability[valid]) > 1):
            raise ValueError("Probability values must be in [0, 1]; convert logits or byte rasters first")
        foreground = valid & (probability >= threshold)
        labels, count = ndimage.label(foreground, structure=np.ones((3, 3), dtype=np.uint8))
        source_crs = CRS.from_user_input(src.crs)
        measure_crs = CRS.from_user_input(area_crs)
        to_measure = Transformer.from_crs(source_crs, measure_crs, always_xy=True).transform
        to_wgs84 = Transformer.from_crs(source_crs, CRS.from_epsg(4326), always_xy=True).transform
        transform = src.transform

        features: list[dict[str, Any]] = []
        if count:
            for geom_mapping, component_value in shapes(
                labels.astype(np.int32), mask=labels > 0, transform=transform, connectivity=8
            ):
                component_id = int(component_value)
                geom = shape(geom_mapping)
                area_ha = transform_geometry(geom, to_measure, interleaved=False).area / 10_000.0
                if area_ha < min_area_ha:
                    continue
                component_pixels = labels == component_id
                confidence = float(np.mean(probability[component_pixels]))
                wgs84_geom = transform_geometry(geom, to_wgs84, interleaved=False)
                features.append(
                    {
                        "type": "Feature",
                        "geometry": wgs84_geom.__geo_interface__,
                        "properties": {
                            "confidence_mean": confidence,
                            "area_ha": float(area_ha),
                            "pixel_count": int(component_pixels.sum()),
                            "threshold": float(threshold),
                        },
                    }
                )

    features.sort(key=lambda feature: feature["properties"]["area_ha"], reverse=True)
    return {
        "type": "FeatureCollection",
        "name": Path(raster_path).stem,
        "features": features,
    }


def write_geojson(collection: dict[str, Any], output_path: str | Path) -> None:
    """Write a UTF-8 GeoJSON FeatureCollection, creating its parent directory."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(collection, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Single-band georeferenced probability GeoTIFF")
    parser.add_argument("--output", required=True, help="Output GeoJSON path")
    parser.add_argument("--config", default="configs/experiment/reference.yaml")
    parser.add_argument("--threshold", type=float, help="Defaults to the configured postprocess threshold")
    parser.add_argument("--min-area-ha", type=float, help="Defaults to the configured minimum area")
    args = parser.parse_args(argv)
    config = load_yaml(args.config)
    postprocess = config["postprocess"]
    threshold = postprocess["threshold"] if args.threshold is None else args.threshold
    min_area_ha = postprocess["min_area_ha"] if args.min_area_ha is None else args.min_area_ha
    collection = polygonize_probabilities(args.input, threshold=threshold, min_area_ha=min_area_ha)
    write_geojson(collection, resolve(args.output))
    print(f"Wrote {len(collection['features'])} prediction features to {resolve(args.output)}")


if __name__ == "__main__":
    main()
