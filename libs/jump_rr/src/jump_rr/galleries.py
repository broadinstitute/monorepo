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
from jump_rr.formatters import format_value
from jump_rr.mappers import get_external_mappers

# %% Setup Local
## Paths
output_dir = Path("./databases")

## Column names
jcp_short = "JCP2022"  # Shortened input data frame
jcp_col = f"Metadata_{jcp_short}"  # Traditional JUMP metadata colname
std_outname = "Gene/Compound"  # Standard item name
ext_links_col = "External Links"  # Link to external resources (e.g., NCBI)


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
    formats existing columns into #site urls, wraps the urls into html, and writes the results.

    """
    # %% Load Metadata
    df = pl.scan_parquet(get_dataset(dset, return_pooch=False))

    # %% Translate genes names to standard
    collected_df = df.select("Metadata_JCP2022").unique().collect()
    jcp_std_mapper, jcp_entrez_mapper, std_to_mim, std_to_ensembl = (
        get_external_mappers(collected_df, "Metadata_JCP2022", dset)
    )

    df = df.with_columns(  # Wrap the urls into html
        *[
            pl.format(
                format_value("img", "phenaid", tuple("{}" for _ in range(8))),
                *[pl.col(f"Metadata_{x}") for x in ("Source", "Plate", "Well")],
                site,
                *[pl.col(f"Metadata_{x}") for x in ("Source", "Plate", "Well")],
                site,
            ).alias(f"Site {site}")
            for site in get_range(dset)
        ],
        pl.col(jcp_col).replace_strict(jcp_std_mapper, default="").alias(std_outname),
        pl.col(jcp_col).replace(jcp_entrez_mapper).alias("entrez"),
    )

    # Add the Plate id for convenient filtering of controls
    order = [
        pl.col(x)
        for x in (
            std_outname,
            ext_links_col,
            jcp_col,
            "^Site.*$",
            "Metadata_Source",
            "Metadata_Plate",
        )
    ]
    df = df.select(order).collect().rename(lambda c: c.removeprefix("Metadata_"))

    # %% Write results
    if write:
        output_dir.mkdir(parents=True, exist_ok=True)
        final_output = output_dir / f"{dset}_gallery.parquet"
        df.write_parquet(final_output, compression="zstd")
    return df


# %% Processing starts
for dset in ("orf", "crispr", "compound"):
    tmp = generate_gallery(dset, write=True)
    break


def add_external_sites(df: pl.DataFrame, std_outname: str, entrez_col: str = "entrez"):
    # Add other names and links that depend on standard ids
    external_sites = dict(omim=std_to_mim, ensembl=std_to_ensembl)
    df = df.with_columns(
        [
            pl.col(std_outname).replace_strict(v, default="").alias(k)
            for k, v in external_sites.items()
        ]
    )

    # Format all links to create the column that links to external sites

    cols_to_aggregate = (
        ("entrez", "entrez"),
        ("genecards", std_outname),
        *list(zip(external_sites, external_sites)),
    )

    df = df.with_columns(
        pl.concat_str(
            [
                pl.format(format_value("href", k, "{}"), pl.col(v))
                for k, v in cols_to_aggregate
            ]
        ).alias(ext_links_col),
        separator=", ",
    )
    return df
