#!/usr/bin/env jupyter
"""Find indices corresponding to the largest and smallest values."""

import cupy as cp
import numpy as np


def get_bottom_top_indices(
    mat: cp.array, n: int, skip_first: bool = False
) -> tuple[cp.array]:
    """
    Get the top n and bottom n indices from a matrix for each row.

    Parameters
    ----------
    mat : cp.array
        The input matrix.
    n : int
        The number of top and bottom indices to get.
    skip_first : bool, optional
        Whether to skip the first column. Defaults to False.

    Returns
    -------
    xs : np.ndarray
        The row indices of the top and bottom indices.
    ys : np.ndarray
        The column indices of the top and bottom indices.

    """
    mask = cp.ones(mat.shape[1], dtype=bool)
    mask[n + skip_first - 1 : -n - 1] = False
    if skip_first:
        mask[0] = False

    indices = mat.argsort(axis=1)[:, mask]

    xs = cp.indices(indices.shape)[0].flatten().get()
    ys = indices.flatten().get()
    return xs, ys


def get_ranks(mat: cp.array, n_vals_used: int = 20) -> tuple[np.array, list[cp.array]]:
    """Get a binary mask of the edges and ranks in every dimension."""
    ranks = [mat.argsort(i) for i in range(mat.ndim)]

    mask = cp.zeros_like(mat, dtype=bool)

    # Get the location of the largest/smallest values in every dimension
    for rank in ranks:
        mask |= rank < n_vals_used

    return ([x.get() for x in cp.where(mask)], [rank[mask].get() for rank in ranks])
