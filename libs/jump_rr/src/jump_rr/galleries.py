#!/usr/bin/env jupyter
# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.15.2
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

"""Generate an interface to browse all available JUMP images."""

from pathlib import Path

import polars as pl
from jump_rr.concensus import get_range
from jump_rr.datasets import get_dataset
from jump_rr.formatters import get_formatter
from jump_rr.translate import get_mapper

# %% Setup Local
## Paths
output_dir = Path("./databases")

## Column names
jcp_short = "JCP2022"  # Shortened input data frame
jcp_col = f"Metadata_{jcp_short}"  # Traditional JUMP metadata colname
std_outname = "Gene/Compound"  # Standard item name
ext_links_col = "NCBI"  # Link to external resources (e.g., NCBI)


def generate_gallery(dset: str, write: bool = True) -> pl.DataFrame:
    """
    Generate a gallery from a remote dataset using only its.

    Parameters
    ----------
    dset : str
        The name of the dataset.
    write : bool, optional
        Whether to write the results to a file (default is True).

    Returns
    -------
    df : pl.DataFrame
        A DataFrame containing the generated gallery.

    Notes
    -----
    This function loads metadata from a parquet file, translates gene names to standard,
    formats existing columns into #foci urls, wraps the urls into html, and writes the results.

    """
    # %% Load Metadata
    df = pl.scan_parquet(get_dataset(dset, return_pooch=False))

    # %% Translate genes names to standard
    uniq_jcp = tuple(df.select("Metadata_JCP2022").unique().collect().to_numpy()[:, 0])
    jcp_std_mapper, jcp_external_mapper = get_mapper(
        uniq_jcp, dset, format_output=False
    )

    df = df.with_columns(  # Format existing columns into #foci urls
        [
            pl.format(
                get_formatter("url_flat"),
                *[pl.col(f"Metadata_{x}") for x in ("Source", "Plate", "Well")],
                foci,
            ).alias(f"Site {foci}")
            for foci in get_range(dset)
        ]
    )
    df = df.with_columns(  # Wrap the urls into html
        [
            pl.format(
                get_formatter("img_flat"),
                pl.col(f"Site {foci}"),
                pl.col(f"Site {foci}"),
            ).alias(f"Site {foci}")
            for foci in get_range(dset)
        ]
    )
    df = df.with_columns(
        [
            pl.col(jcp_col).replace(jcp_std_mapper).alias(std_outname),
            pl.format(
                get_formatter("external_flat"),
                pl.col(jcp_col).replace(jcp_external_mapper),
            ).alias(ext_links_col),
        ]
    )

    order = [pl.col(x) for x in (std_outname, ext_links_col, jcp_col, "^Site.*$")]
    df = df.select(order).collect()

    # %% Write results
    if write:
        output_dir.mkdir(parents=True, exist_ok=True)
        final_output = output_dir / f"{dset}_gallery.parquet"
        df.write_parquet(final_output, compression="zstd")
    return df


# %% Processing starts
for dset in ("orf", "crispr", "compound"):
    generate_gallery(dset, write=True)
