#!/usr/bin/env jupyter
"""
Group multiple wells
"""
from itertools import cycle

import numpy as np
import polars as pl

# Names
url_col = "Metadata_image"  # Must start with "Metadata" for URL grouping to work
jcp_short = "JCP2022"  # Shortened input data frame
jcp_col = f"Metadata_{jcp_short}"  # Traditional JUMP metadata colname
# HTML formatters
external_formatter = (
    '{{"href": "https://www.ncbi.nlm.nih.gov/gene/{}", "label":"External"}}'
)
url_template = (
    '"https://phenaid.ardigen.com/static-jumpcpexplorer/' 'images/{}_{{}}.jpg"'
)
img_formatter = '{{"img_src": {}, "href": {}, "width": 200}}'


def get_concensus_meta_urls(prof: pl.DataFrame) -> tuple:
    """
    Returns the data frame as the aggregated median values, metadata and urls.
    Metadata and urls are composed of cycling iterators for the contents that were grouped during concensus.
    """
    prof = prof.with_columns(
        pl.concat_str(
            pl.col("Metadata_Source"),
            pl.col("Metadata_Plate"),
            pl.col("Metadata_Well"),
            separator="/",
        )
        .map_elements(lambda x: url_template.format(x))
        .alias(url_col)
    )
    grouped = prof.group_by(jcp_col)
    med = grouped.median()
    meta = grouped.agg(pl.col("^Metadata_.*$").map_elements(cycle))
    urls = grouped.agg(pl.col(url_col).map_elements(cycle))

    for srs in meta.iter_columns():
        med.replace_column(med.columns.index(srs.name), srs)

    return med, meta, urls


def get_cycles(dataset: str) -> cycle:
    # Generate a cycle of indices based on the dataset
    offset = dataset != "crispr"
    cycles = cycle(range(offset, 9 + offset))  # 0-8 if CRISPR; 1-9 if ORF
    return cycles


def repeat_cycles(n: int, dataset: str) -> np.ndarray:
    # Use mnultiple cycles to iterate over multiple next()
    # while keeping track of each individual cycle
    cycles = get_cycles(dataset)
    cycled_indices = np.repeat(cycles, n)
    return cycled_indices
