#!/usr/bin/env jupyter
"""
Functions to group multiple wells
"""
from itertools import cycle

import numpy as np
import polars as pl
from jump_rr.formatters import add_url_col
from jump_rr.parse_features import get_feature_groups

# Names
jcp_short = "JCP2022"  # Shortened input data frame
jcp_col = f"Metadata_{jcp_short}"  # Traditional JUMP metadata colname


def get_concensus_meta_urls(prof: pl.DataFrame, url_colname: str) -> tuple:
    """
    Returns the data frame as the aggregated median values, metadata and urls.
    Metadata and urls are composed of cycling iterators for the contents that were grouped during concensus.
    """
    prof = add_url_col(prof, url_colname=url_colname)

    grouped = prof.group_by(jcp_col)
    med = grouped.median()
    meta = grouped.agg(pl.col("^Metadata_.*$").map_elements(cycle))
    urls = grouped.agg(pl.col(url_colname).map_elements(cycle))

    for srs in meta.iter_columns():
        med.replace_column(med.columns.index(srs.name), srs)

    return med, meta, urls


def get_group_median(med, group_by: list[str] or None = None):
    """Group columns by their names"""
    med_vals = med.select(pl.exclude("^Metadata.*$"))
    if group_by is None:
        feature_meta = get_feature_groups(tuple(med_vals.columns))
    features = pl.concat((feature_meta, med_vals.transpose()), how="horizontal")

    grouped = features.group_by(feature_meta.columns)

    return grouped.median()


def get_range(dataset: str) -> range:
    """
    Generate a cycle of indices based on the dataset
    0-8 if CRISPR; 1-9 if ORF, 1-6 if compounds
    """
    offset = dataset != "crispr"
    max_offset = (dataset == "compound") * (-3)
    rng = range(offset, 9 + offset + max_offset)
    return rng


def get_cycles(dataset: str) -> cycle:
    return cycle(get_range(dataset))


def repeat_cycles(n: int, dataset: str) -> np.ndarray:
    # Use multiple cycles to iterate over multiple next()
    # while keeping track of each individual cycle
    cycles = get_cycles(dataset)
    cycled_indices = np.repeat(cycles, n)
    return cycled_indices
