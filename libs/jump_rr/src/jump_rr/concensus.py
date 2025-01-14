#!/usr/bin/env jupyter
"""Functions to group multiple wells."""

from itertools import cycle

import numpy as np
import polars as pl
from jump_rr.formatters import add_url_col
from jump_rr.parse_features import get_feature_groups

# Names
jcp_short = "JCP2022"  # Shortened input data frame
jcp_col = f"Metadata_{jcp_short}"  # Traditional JUMP metadata colname


def get_concensus_meta_urls(profiles: pl.DataFrame, url_colname: str) -> tuple:
    """
    Compute aggregated median values and metadata with urls for a given dataframe.

    Parameters
    ----------
    profiles : pl.DataFrame
        Input dataframe containing profile information.
    url_colname : str
        Name of the column in the dataframe that contains urls.

    Returns
    -------
    med : pl.DataFrame
        Dataframe containing aggregated median values.
    meta : pl.DataFrame
        Dataframe containing metadata composed of cycling iterators for grouped contents during concensus.
    urls : pl.DataFrame
        Dataframe containing urls composed of cycling iterators for grouped contents during concensus.

    """
    profiles = add_url_col(profiles, url_colname=url_colname)

    grouped = profiles.group_by(jcp_col, maintain_order=True)
    med = grouped.median()
    meta = grouped.agg(pl.col("^Metadata_.*$").map_elements(cycle))
    urls = grouped.agg(pl.col(url_colname).map_elements(cycle))

    for srs in meta.iter_columns():
        med.replace_column(med.columns.index(srs.name), srs)

    return med, meta, urls


def get_group_median(
    med: pl.DataFrame, group_by: list[str] or None = None
) -> pl.DataFrame:
    """
    Calculate the median of a set of features grouped by their metadata.

    Parameters
    ----------
    med : pl.DataFrame
        The input DataFrame containing the feature values and metadata.
    group_by : list[str] or None, optional
        A list of column names to group the features by. If None, the
        `get_feature_groups` is used to assign groups (default is None).

    Returns
    -------
    pl.DataFrame
        A DataFrame with the median value for each group.

    Notes
    -----
    The function first selects all columns that do not start with "Metadata.".
    Then it concatenates these values horizontally with their respective metadata.
    Finally, it groups these features by their metadata and calculates the median
    of each group.

    """
    med_vals = med.select(pl.exclude("^Metadata.*$"))
    if group_by is None:
        feature_meta = get_feature_groups(tuple(med_vals.columns))
    else:
        feature_meta = pl.DataFrame(group_by)
    features = pl.concat((feature_meta, med_vals.transpose()), how="horizontal")

    grouped = features.group_by(feature_meta.columns, maintain_order=True)

    return grouped.median()


def get_range(dataset: str) -> range:
    """
    Generate a range of indices based on the dataset.

    Parameters
    ----------
    dataset : str
        The type of dataset. It can be 'crispr', 'orf', or 'compound'.

    Returns
    -------
    rng : range
        A range object representing the cycle of indices for the given dataset.

    """
    offset = dataset != "crispr"
    max_offset = (dataset == "compound") * (-3)
    rng = range(offset, 9 + offset + max_offset)
    return rng


def get_cycles(dataset: str) -> cycle:
    """
    Obtain cycled ranges based on which dataset we are using.

    Parameters
    ----------
    dataset : str
        The input dataset string.

    Returns
    -------
    cycles : Iterable[list[int]]
        The calculated cycles. Iterable of lists containing indices.

    Notes
    -----
    This function uses the get_range and cycle functions to generate cycled ranges.

    """
    return cycle(get_range(dataset))


def repeat_cycles(n: int, dataset: str) -> np.ndarray:
    """
    Repeat cycles to iterate over multiple next() while keeping track of each individual cycle.

    The main goal is to randomise the same range independently so we ensure that we are
    displaying all the images of a perturbation independently of each other.

    Parameters
    ----------
    n : int
        Number of times to repeat the cycles.
    dataset : str
        Input dataset used to generate cycles.

    Returns
    -------
    cycled_indices : ndarray
        Array of repeated cycle indices.

    """
    cycles = get_cycles(dataset)
    cycled_indices = np.repeat(cycles, n)
    return cycled_indices
