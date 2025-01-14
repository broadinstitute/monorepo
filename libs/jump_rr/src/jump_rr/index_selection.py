#!/usr/bin/env jupyter
"""Find indices corresponding to the largest and smallest values."""

import cupy as cp


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


def get_edge_indices(mat: cp.array, n: int, which: str = "bottom") -> tuple[cp.array]:
    """
    Get the top n or bottom n indices from a matrix for each row.

    Parameters
    ----------
    mat : cp.array
        The input matrix.
    n : int
        The number of top or bottom indices to get.
    which : str, optional
        Whether to get 'top' or 'bottom' indices. Defaults to "bottom".

    Returns
    -------
    xs : np.ndarray
        The row indices of the top or bottom indices.
    ys : np.ndarray
        The column indices of the top or bottom indices.

    Raises
    ------
    AssertionError
        If `which` is not either 'top' or 'bottom'.

    """
    mask = cp.ones(mat.shape[1], dtype=bool)

    assert which in ("top", "bottom"), "which must be either top or bottom"

    if which == "bottom":
        mask[n:] = False
    else:
        mask[: -n - 1] = False

    indices = mat.argsort(axis=1)[:, mask]

    xs = cp.indices(indices.shape)[0].flatten().get()
    ys = indices.flatten().get()
    return xs, ys
