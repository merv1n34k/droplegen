"""Shared utilities."""

import numpy as np


def bin_arrays(x: np.ndarray, y: np.ndarray, bin_size: float) -> tuple[np.ndarray, np.ndarray]:
    """Average x/y arrays into fixed-width time bins."""
    if bin_size <= 0 or len(x) < 2:
        return x, y
    bin_idx = ((x - x[0]) / bin_size).astype(np.intp)
    counts = np.bincount(bin_idx)
    mask = counts > 0
    x_binned = np.bincount(bin_idx, weights=x)[mask] / counts[mask]
    y_binned = np.bincount(bin_idx, weights=y)[mask] / counts[mask]
    return x_binned, y_binned
