"""Ignore-aware pixel metrics accumulated across an evaluation area."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike


@dataclass
class PixelMetricAccumulator:
    """Accumulate pixel confusion counts without averaging per-chip scores.

    ``target`` uses 1 for PV, 0 for background, and 255 for ignored pixels.
    Probabilities at ignored pixels are not inspected. A non-finite probability
    at any evaluated pixel is an error rather than an implicit exclusion.
    """

    ignore_index: int = 255
    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0
    true_negative: int = 0
    ignored_pixels: int = 0

    def update(self, probabilities: ArrayLike, target: ArrayLike, *, threshold: float) -> None:
        """Add one aligned probability/label window to the accumulated counts."""
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")
        probability = np.asarray(probabilities)
        truth = np.asarray(target)
        if probability.shape != truth.shape:
            raise ValueError("probabilities and target must have identical shapes")
        allowed = (truth == 0) | (truth == 1) | (truth == self.ignore_index)
        if not np.all(allowed):
            raise ValueError("target values must be 0, 1, or the configured ignore index")
        valid = truth != self.ignore_index
        evaluated_probability = probability[valid]
        if not np.isfinite(evaluated_probability).all():
            raise ValueError("probabilities must be finite at every non-ignored target pixel")
        if evaluated_probability.size and (
            np.min(evaluated_probability) < 0 or np.max(evaluated_probability) > 1
        ):
            raise ValueError("probabilities must be in [0, 1]")

        predicted_positive = probability >= threshold
        self.true_positive += int(np.count_nonzero(valid & (truth == 1) & predicted_positive))
        self.false_positive += int(np.count_nonzero(valid & (truth == 0) & predicted_positive))
        self.false_negative += int(np.count_nonzero(valid & (truth == 1) & ~predicted_positive))
        self.true_negative += int(np.count_nonzero(valid & (truth == 0) & ~predicted_positive))
        self.ignored_pixels += int(np.count_nonzero(~valid))

    def compute(self) -> dict[str, int | float | None]:
        """Return accumulated counts and metrics; undefined denominators return ``None``."""
        tp, fp = self.true_positive, self.false_positive
        fn, tn = self.false_negative, self.true_negative
        precision_denominator = tp + fp
        recall_denominator = tp + fn
        f1_denominator = 2 * tp + fp + fn
        iou_denominator = tp + fp + fn
        return {
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "true_negative": tn,
            "ignored_pixels": self.ignored_pixels,
            "precision": tp / precision_denominator if precision_denominator else None,
            "recall": tp / recall_denominator if recall_denominator else None,
            "f1": 2 * tp / f1_denominator if f1_denominator else None,
            "iou": tp / iou_denominator if iou_denominator else None,
        }
