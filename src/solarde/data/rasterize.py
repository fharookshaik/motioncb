"""Rasterize versioned PV labels into an explicit imagery grid."""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
from affine import Affine
from rasterio.features import rasterize


def label_mask(labels: gpd.GeoDataFrame, assignments: pd.DataFrame, blocks: gpd.GeoDataFrame,
               *, crs, transform: Affine, shape: tuple[int, int], split: str,
               valid: np.ndarray | None = None, fractional_factor: int = 1) -> np.ndarray:
    """Return hard (0/1/255) or fractional (0..1/255) targets on the exact grid.

    Ignored polygons and foreign-split fragments take priority over positives.
    Cross-split polygons are positive only inside their assigned block. Ignore
    geometries use all-touched rasterization to avoid calling uncertain edge
    pixels background. Caller must reject whole chips within the split buffer.
    """
    if fractional_factor < 1 or int(fractional_factor) != fractional_factor:
        raise ValueError("fractional_factor must be a positive integer")
    if valid is not None and valid.shape != shape:
        raise ValueError("Validity mask must match the target grid")
    if labels.geometry.isna().any() or (~labels.geometry.is_valid).any():
        raise ValueError("Missing or invalid label geometry; no silent repair or removal")
    if not set(labels.label_status) <= {"positive", "ignore"}:
        raise ValueError("Unknown label status")
    labels = labels.to_crs(crs)
    blocks = blocks.to_crs(crs).set_index("block_id")
    linked = labels.merge(assignments, on="area_id", how="left", validate="one_to_one")
    if linked.block_id.isna().any():
        raise ValueError("Every polygon must have a split assignment")
    positive, ignored = [], []
    for row in linked.itertuples():
        geom = row.geometry
        if row.label_status == "ignore" or row.split != split:
            ignored.append(geom)
        elif row.crosses_split_border:
            owned = geom.intersection(blocks.loc[row.block_id].geometry)
            positive.append(owned)
            ignored.append(geom.difference(owned))
        else:
            positive.append(geom)
    positive = [(geom, 1) for geom in positive if not geom.is_empty]
    ignored = [(geom, 1) for geom in ignored if not geom.is_empty]
    factor = int(fractional_factor)
    high_shape = (shape[0] * factor, shape[1] * factor)
    high_transform = transform @ Affine.scale(1 / factor, 1 / factor)
    values = rasterize(positive, out_shape=high_shape, transform=high_transform, dtype="uint8") if positive else (
        np.zeros(high_shape, dtype=np.uint8))
    if factor > 1:
        values = values.reshape(shape[0], factor, shape[1], factor).mean(axis=(1, 3)).astype(np.float32)
    uncertain = rasterize(ignored, out_shape=shape, transform=transform, all_touched=True,
                          dtype="uint8").astype(bool) if ignored else np.zeros(shape, dtype=bool)
    if valid is not None:
        uncertain |= ~valid.astype(bool)
    values[uncertain] = 255
    return values
