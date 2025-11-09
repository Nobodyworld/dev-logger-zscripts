"""Smoke tests for helpers.numpy utilities."""

from __future__ import annotations

import numpy as np

from zscripts.helpers.numpy import batched, normalize_columns, rolling_window


def test_normalize_columns_handles_zero_columns() -> None:
    data = np.array([[3.0, 0.0], [4.0, 0.0]])
    normalized = normalize_columns(data)

    assert np.allclose(np.linalg.norm(normalized[:, 0]), 1.0)
    # Zero column should remain untouched.
    assert np.array_equal(normalized[:, 1], data[:, 1])


def test_rolling_window_produces_expected_slices() -> None:
    sequence = np.arange(6)
    windows = rolling_window(sequence, 3)

    assert windows.shape == (4, 3)
    assert np.array_equal(windows[0], np.array([0, 1, 2]))
    assert np.array_equal(windows[-1], np.array([3, 4, 5]))


def test_batched_groups_arrays_evenly() -> None:
    payload = [np.array([idx]) for idx in range(5)]
    batches = batched(payload, batch_size=2)

    assert len(batches) == 3
    assert batches[0].shape == (2, 1)
    assert batches[-1].shape == (1, 1)


def main() -> None:
    test_normalize_columns_handles_zero_columns()
    test_rolling_window_produces_expected_slices()
    test_batched_groups_arrays_evenly()


if __name__ == "__main__":
    main()
