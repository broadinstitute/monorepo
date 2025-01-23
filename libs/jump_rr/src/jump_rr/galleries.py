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
from jump_rr.formatters import add_external_sites, format_value
from jump_rr.mappers import get_external_mappers

# %% Setup Local
## Paths
output_dir = Path("./databases")

## Column names
jcp_short = "JCP2022"  # Shortened input data frame
jcp_col = f"Metadata_{jcp_short}"  # Traditional JUMP metadata colname
std_outname = "Gene/Compound"  # Standard item name
entrez_col = "entrez" #transient col to hold entrez id
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
    jcp_to_std, jcp_to_entrez, std_to_omim, std_to_ensembl = (
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
        pl.col(jcp_col).replace_strict(jcp_to_std, default="").alias(std_outname),
        # pl.col(jcp_col).replace(jcp_entrez_mapper).alias(entrez_col),
    )
    
    # Add the Plate id for convenient filtering of controls
    order = [
            std_outname,
            jcp_col,
            "^Site.*$",
            "Metadata_Source",
            "Metadata_Plate",
        ]

    # Define the external references to use in genetic or chemical datasets
    if dset != "compound": # TODO Add databases for compounds and ensure that 0-case works
        key_source_mapper = (("entrez", jcp_col, jcp_to_entrez),
                             ("omim", std_outname, std_to_omim),
                             ("genecards", std_outname, dict(zip(jcp_to_std.values(), jcp_to_std.values()))),
                             ("ensembl", std_outname, std_to_ensembl),
                             )
        df = add_external_sites(df, ext_links_col, key_source_mapper)
        order.insert(1, ext_links_col)

    df = df.select(pl.col(order)).collect().rename(lambda c: c.removeprefix("Metadata_"))

    # %% Write results
    if write:
        output_dir.mkdir(parents=True, exist_ok=True)
        final_output = output_dir / f"{dset}_gallery.parquet"
        df.write_parquet(final_output, compression="zstd")
    return df


# %% Processing starts
for dset in ("orf", "crispr", "compound"):
    tmp = generate_gallery(dset, write=True)
    
