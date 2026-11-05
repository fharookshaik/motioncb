"""Hand-computed checks for accumulated, ignore-aware pixel metrics."""
from __future__ import annotations

import numpy as np
import pytest

from solarde.evaluate.pixel_metrics import PixelMetricAccumulator


def test_accumulates_counts_and_excludes_ignore_pixels():
    metrics = PixelMetricAccumulator()
    metrics.update(
        probabilities=np.array([[0.9, 0.8], [0.2, 0.99]]),
        target=np.array([[1, 0], [1, 255]]),
        threshold=0.5,
    )
    metrics.update(
        probabilities=np.array([[0.7, 0.1]]),
        target=np.array([[1, 0]]),
        threshold=0.5,
    )

    assert metrics.compute() == {
        "true_positive": 2,
        "false_positive": 1,
        "false_negative": 1,
        "true_negative": 1,
        "ignored_pixels": 1,
        "precision": pytest.approx(2 / 3),
        "recall": pytest.approx(2 / 3),
        "f1": pytest.approx(2 / 3),
        "iou": pytest.approx(0.5),
    }


def test_invalid_target_or_probability_is_rejected():
    metrics = PixelMetricAccumulator()
    with pytest.raises(ValueError, match="target values"):
        metrics.update([0.4], [2], threshold=0.5)
    with pytest.raises(ValueError, match="finite"):
        metrics.update([np.nan], [1], threshold=0.5)
