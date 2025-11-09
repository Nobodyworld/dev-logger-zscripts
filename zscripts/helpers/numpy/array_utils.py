"""NumPy utility helpers for common data-preparation tasks."""

from __future__ import annotations

from typing import Iterable

import numpy as np
import numpy.typing as npt

__all__ = ["normalize_columns", "rolling_window", "batched"]


def normalize_columns(array: npt.ArrayLike, *, eps: float = 1e-12) -> np.ndarray:
    """Return a copy of ``array`` with each column scaled to unit length.

    Args:
        array: Any object that can be coerced to a :class:`numpy.ndarray`.
        eps: Minimum norm allowed per column to avoid division by zero.

    Returns:
        A floating-point array with columns normalized to length 1 (within ``eps``).
    """
    data = np.asarray(array, dtype=float)
    if data.ndim != 2:
        raise ValueError("normalize_columns expects a 2D array")

    norms = np.linalg.norm(data, axis=0, keepdims=True)
    safe_norms = np.maximum(norms, eps)
    normalized = data / safe_norms
    # Preserve zero columns exactly when their norm is below ``eps``.
    normalized[:, norms.flatten() < eps] = data[:, norms.flatten() < eps]
    return normalized


def rolling_window(
    array: npt.ArrayLike,
    window: int,
    *,
    axis: int = -1,
) -> np.ndarray:
    """Return a view that iterates over ``array`` with an overlapping window.

    This helper wraps :func:`numpy.lib.stride_tricks.sliding_window_view` and adds
    a validation layer so helpers can depend on consistent error messages in older
    NumPy releases.
    """
    if window <= 0:
        raise ValueError("window must be a positive integer")

    data = np.asarray(array)
    try:
        return np.lib.stride_tricks.sliding_window_view(data, window_shape=window, axis=axis)
    except AttributeError as exc:  # pragma: no cover - older numpy releases
        raise RuntimeError("sliding_window_view is unavailable in this NumPy version") from exc


def batched(iterable: Iterable[npt.ArrayLike], batch_size: int) -> list[np.ndarray]:
    """Group an iterable of arrays into batches of ``batch_size``.

    The helper coerces every element to an ``ndarray``. The final batch may be
    smaller than ``batch_size`` when the number of elements is not evenly
    divisible. Returning a list keeps the API ergonomic for quick scripts while
    still enabling deterministic iteration order.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    batches: list[np.ndarray] = []
    current: list[np.ndarray] = []
    for item in iterable:
        current.append(np.asarray(item))
        if len(current) == batch_size:
            batches.append(np.stack(current))
            current.clear()

    if current:
        batches.append(np.stack(current))

    return batches
