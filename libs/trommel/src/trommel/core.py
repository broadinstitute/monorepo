"""
Types of processing steps:
1. Do not change x nor y axis (e.g., MAD robustize)
2. Change column number (e.g., drop_outliers, drop_correlations)
3. Remove rows (no examples yet)
"""

import numpy
import polars as pl


def get_nan_inf_indices(
    arr: numpy.ndarray, axis: int = 0, threshold: int or float = 0
) -> numpy.ndarray:
    # Use threshold as fraction if 0 < x < size
    if 0 < threshold < 1:
        threshold = arr.shape[axis] * threshold

    return numpy.where(
        (numpy.isnan(arr) | numpy.isinf(arr)).sum(axis=axis) > threshold
    )[0]


def median_abs_deviation(arr: numpy.ndarray, axis=None, keepdims=True) -> numpy.ndarray:
    """
    Calculate median absolute deviation
    """
    median = numpy.median(arr, axis=axis, keepdims=True)
    mad = numpy.median(numpy.abs(arr - median), axis=axis, keepdims=keepdims)
    return mad


def calculate_mad(X: numpy.ndarray, epsilon: float = 1e-18) -> numpy.ndarray:
    # Get the mean of the features (columns) and center if specified
    # median = numpy.median(X, axis=1)

    return (X - numpy.median(X, axis=0)) / (median_abs_deviation(X) + epsilon)


def find_outliers(arr: numpy.ndarray, outlier_cutoff: float = 500) -> numpy.ndarray:
    """
    Return indices that are outliers.
    """
    max_vals = numpy.abs(numpy.max(arr, axis=0))
    min_vals = numpy.abs(numpy.min(arr, axis=0))
    vals_beyond_cutoff = (max_vals > outlier_cutoff) | (min_vals > outlier_cutoff)
    indices = numpy.where(vals_beyond_cutoff)[0]

    return indices


def greedy_independent_set(adj_graph):
    """
    Finds an independent set from the adjacency matrix of a graph using a greedy algorithm. This can be used to disconnect a similarity graph (and thus reducing redundancy)

    Parameters:
        adj_graph (numpy.ndarray): A binary 2D array representing the graph's adjacency matrix.

    Returns:
        list: Indices of the vertices in the independent set.
    """
    adj_graph = adj_graph.copy()

    # Ensure the diagonal is zero (no self-loops)
    numpy.fill_diagonal(adj_graph, 0)

    # Remaining nodes to process
    remaining_nodes = set(range(adj_graph.shape[0]))
    independent_set = []

    while remaining_nodes:
        # Calculate degrees of remaining nodes
        degrees = numpy.sum(adj_graph, axis=1)

        # Find the node with the smallest degree
        min_degree_node = min(remaining_nodes, key=lambda node: degrees[node])

        # Add it to the independent set
        independent_set.append(min_degree_node)

        # Remove this node and its neighbors from the remaining nodes
        neighbors = set(numpy.where(adj_graph[min_degree_node] == 1)[0])
        remaining_nodes -= neighbors | {min_degree_node}

        # Set rows and columns of removed nodes to 0 to avoid processing
        adj_graph[min_degree_node, :] = 0
        adj_graph[:, min_degree_node] = 0
        for neighbor in neighbors:
            adj_graph[neighbor, :] = 0
            adj_graph[:, neighbor] = 0

    return list(set(numpy.arange(len(adj_graph))).difference(independent_set))


def get_redundant_features(arr: numpy.ndarray, thresh: float = 0.9) -> list[int]:
    correlations = numpy.corrcoef(arr, rowvar=False)
    adj_graph = correlations > thresh
    corr_dropables = greedy_independent_set(adj_graph)
    return corr_dropables


def drop_indices(values: numpy.ndarray, indices: list[int], axis=1):
    mask = numpy.ones(values.shape[axis], dtype=bool)
    mask[indices] = False

    if axis:  # Filter-out dropped indices
        result = values[:, mask]
    else:
        result = values[mask]

    return result


def basic_cleanup(
    df: pl.DataFrame,
    meta_selector: pl.selectors,
    params: dict[str, int] = {"nan_rows": 0.5, "redundancy": 0.9, "outliers": 500},
) -> tuple[pl.DataFrame, dict[str, int]]:
    """
    df: data+metadata data frame.
    meta_selector: metadata it determines which columns are metadata and which are data.
    """
    ndropped = {}
    values_df = df.select(~meta_selector)
    current_vals = values_df.to_numpy()

    # Drop rows firstk iwth a threshold, then columns.
    # Remove NaN rows
    nan_indices_rows = get_nan_inf_indices(
        current_vals, axis=1, threshold=params["nan_rows"]
    )
    current_vals = drop_indices(current_vals, nan_indices_rows, axis=0)
    ndropped["nan_rows"] = len(nan_indices_rows)

    # Remove NaNs columns
    nan_indices_cols = get_nan_inf_indices(current_vals, threshold=0)
    current_vals = drop_indices(current_vals, nan_indices_cols, axis=1)
    ndropped["nan_cols"] = len(nan_indices_cols)

    # MAD-robustize
    current_vals = calculate_mad(current_vals)

    # Drop outlier features
    outlier_indices = find_outliers(current_vals, params["outliers"])
    current_vals = drop_indices(current_vals, outlier_indices)
    ndropped["outliers"] = len(outlier_indices)

    # Drop redundant features
    redundant_indices = get_redundant_features(current_vals, params["redundancy"])
    current_vals = drop_indices(current_vals, redundant_indices)
    ndropped["redundant"] = len(redundant_indices)

    assert len(current_vals), "Data preprocessing emptied out matrix."
    # Adjust column indices
    colnames = numpy.array(values_df.columns)
    for indices_to_drop in (
        nan_indices_cols,
        outlier_indices,
        redundant_indices,
    ):
        colnames = drop_indices(colnames, indices_to_drop, axis=0)

    new_values_df = pl.DataFrame(current_vals, schema=colnames.tolist())
    processed = pl.concat(
        (
            df.select(meta_selector)
            .with_row_index(name="nr")
            .filter(~pl.col("nr").is_in(nan_indices_rows)),
            new_values_df,
        ),
        how="horizontal",
    )

    return processed, ndropped
