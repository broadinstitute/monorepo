#!/usr/bin/env jupyter
"""Find indices corresponding to the largest and smallest values."""

import cupy as cp
import dask.array as da
import numpy as np


def get_bottom_top_indices(
    mat: cp.array, n: int, skip_first: bool = False
) -> tuple[np.array]:
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
    top = da.argtopk(mat, n + skip_first)[:, skip_first:]
    bottom = da.argtopk(mat, -n)
    xs = (
        da.matmul(da.arange(len(mat))[:, da.newaxis], da.ones((1, n * 2), dtype=int))
        .flatten()
        .compute()
    )
    ys = da.hstack((top, bottom)).flatten().compute()
    return xs, ys


def get_ranks(
    mat: da.array, n_vals_used: int = 20
) -> tuple[list[da.array], list[da.array]]:
    """Return the lowest `n_vals_used` indices in rows and columns for mat."""
    bottom_on_y = da.argtopk(mat, -n_vals_used, axis=0)
    bottom_on_x = da.argtopk(mat, -n_vals_used, axis=1)

    return (
        bottom_on_x,
        bottom_on_y,
    )
