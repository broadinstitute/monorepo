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

"""
Generate a table with the most correlated and anticorrelated pairs.

Calculate cosine distance of CRISPR and ORF profiles using a GPU,
then wrangle information and produce an explorable data frame.
This is intended for use on a server with GPUs and high RAM to analyse data massively.
"""

from pathlib import Path
from time import perf_counter

import cupy as cp
import dask.array as da
import numpy as np
import polars as pl
import polars.selectors as cs
from jump_rr.consensus import add_sample_images, get_consensus_meta_urls, get_range
from jump_rr.datasets import get_dataset
from jump_rr.formatters import add_external_sites
from jump_rr.index_selection import get_bottom_top_indices
from jump_rr.mappers import (
    get_compound_mappers,
    get_external_mappers,
    get_synonym_mapper,
)
from jump_rr.metadata import write_metadata
from jump_rr.replicability import add_replicability

assert cp.cuda.get_current_stream().done, "GPU not available"


def pairwise_cosine_sim(x: da.array, y: da.array) -> da.array:
    """
    Compute pairwise cosine similarity between two sets of vectors.

    Parameters
    ----------
    x : da.array
        The first set of vectors.
    y : da.array
        The second set of vectors.

    Returns
    -------
    matmul : da.array
        Upper triangular matrix containing the pairwise cosine distances.

    Notes
    -----
    This function computes the dot product of normalized vectors and returns the
    resulting matrix.

    """
    x_norm = x / da.linalg.norm(x, axis=1)[:, da.newaxis]
    y_norm = y / da.linalg.norm(y, axis=1)[:, da.newaxis]

    # Compute the dot product of normalized vectors
    matmul = da.matmul(x_norm, y_norm.T)
    return matmul


# %% Setup
## Paths
output_dir = Path("./databases")

## Parameters
datasets_nvals = (
    ("crispr", 25),
    ("orf", 25),
    ("compound", 10),
)  # Number of top and bottom matches used
dist_as_sim = True  # Display distance as integers instead of floats

## Column names
jcp_short = "JCP2022"  # Shortened input data frame
jcp_col = f"Metadata_{jcp_short[:7]}"  # Traditional JUMP metadata colname
std_outname = "Perturbation"  # Standard item name
img_col = f"{std_outname} example image"
rep_col = "Phenotypic activity"
match_col = "Match"  # Highest matches
match_jcp_col = f"Match {jcp_short}"
match_img_col = f"{match_col} example image"  # URL with image examples
match_rep_col = f"{rep_col} {match_col}"
dist_col = "Perturbation-Match Similarity"  # Metric name
ext_links_col = f"{match_col} resources"  # Link to external resources (e.g., NCBI)
replicability_cols = {
    "corrected_p_value": "Corrected p-value",
    "mean_average_precision": "Phenotypic activity",
}

# %% Processing starts
for dset, n_vals_used in datasets_nvals:
    print(f"Processing {dset}")
    # %% Load Metadata
    df = pl.read_parquet(get_dataset(dset))

    # %% add build url from individual wells
    med, _ = get_consensus_meta_urls(df, "Metadata_JCP2022")
    median_np = med.select(cs.by_dtype(pl.Float32)).to_numpy()
    nrows, ncols = median_np.shape

    t = perf_counter()

    vals = da.array(median_np)
    if dset != "compound":
        vals = vals.map_blocks(cp.asarray)

    # %% Calculate cosine distance
    cosine_sim = pairwise_cosine_sim(vals, vals)
    if dset != "compound":
        cosine_sim = cosine_sim.map_blocks(cp.asnumpy)

    # Get most correlated and anticorrelated indices
    cosine_sim_computed = cosine_sim.compute()
    t1 = perf_counter()
    xs, ys = get_bottom_top_indices(cosine_sim, n_vals_used, skip_first=True)
    print(f"xs,ys computed in {perf_counter() - t1} seconds")

    jcp_ids = med[jcp_col].to_numpy().astype("<U15")

    # Build a dataframe containing matches
    jcp_df = pl.DataFrame({
        jcp_short: np.repeat(jcp_ids, n_vals_used * 2),
        match_jcp_col: jcp_ids[ys].astype("<U15"),
        dist_col: cosine_sim_computed[xs, ys],
    })

    # Add images for both queries and matches
    df_meta = df.select("^Metadata.*$")
    side_a = add_sample_images(
        jcp_df,
        df_meta,
        get_range(dset),
        img_col,
        left_col="JCP2022",
        right_col="Metadata_JCP2022",
    )
    side_b = add_sample_images(
        jcp_df,
        df_meta,
        get_range(dset),
        match_img_col,
        left_col="Match JCP2022",
        right_col="Metadata_JCP2022",
    )
    jcp_cols = (jcp_short, match_jcp_col)
    jcp_df = jcp_df.join(side_a.select(pl.col((*jcp_cols, img_col))), on=jcp_cols)
    jcp_df = jcp_df.join(side_b.select(pl.col((*jcp_cols, match_img_col))), on=jcp_cols)

    # %% Translate genes names to standard
    jcp_to_std, jcp_to_entrez, std_to_omim, std_to_ensembl = get_external_mappers(
        df, jcp_col, dset
    )

    jcp_df = jcp_df.with_columns(
        pl.col(jcp_short).replace(jcp_to_std).alias(std_outname),
        pl.col(match_jcp_col).replace(jcp_to_std).alias(match_col),
        pl.col(jcp_short)  # Add synonyms
        .replace(jcp_to_entrez)  # Map to NCBI ID
        .replace(get_synonym_mapper())  # Map synonyms
        .alias("Synonyms"),
    )

    # Sort columns
    order = [
        std_outname,
        match_col,
        img_col,
        match_img_col,
        dist_col,
        "Synonyms",
        jcp_short,
        match_jcp_col,
    ]

    jcp_df = add_replicability(
        jcp_df,
        left_on=jcp_short,
        right_on=jcp_col,
        cols_to_add=replicability_cols,
    )
    jcp_df = add_replicability(
        jcp_df,
        left_on=match_jcp_col,
        right_on=jcp_col,
        suffix=" Match",
        cols_to_add=replicability_cols,
    )

    if dset != "compound":
        # Define the external references to use in genetic or chemical datasets
        # TODO Add databases for compounds
        key_source_mapper = (
            ("entrez", match_jcp_col, jcp_to_entrez),
            ("omim", match_col, std_to_omim),
            (
                "genecards",
                match_col,
                dict(zip(jcp_to_std.values(), jcp_to_std.values())),
            ),
            ("ensembl", match_col, std_to_ensembl),
        )
    else:
        key_source_mapper = [(k, jcp_short, v) for k, v in get_compound_mappers()]

    jcp_df = add_external_sites(jcp_df, ext_links_col, key_source_mapper)

    order.insert(5, ext_links_col)

    order = (
        *order,
        *[
            f"{v}{suffix}"
            for suffix in ("", " Match")
            for v in replicability_cols.values()
        ],
    )

    # res = np.around((jcp_df[dist_col].to_numpy().astype(np.float64)), 3)
    jcp_df = jcp_df.with_columns(
        pl.col(dist_col).cast(pl.Float64).round(3).alias(dist_col)
    )

    matches_translated = jcp_df.select(order)

    # %% Save results
    output_dir.mkdir(parents=True, exist_ok=True)
    final_output = output_dir / f"{dset}.parquet"
    matches_translated.write_parquet(final_output, compression="zstd")

    write_metadata(dset, "matches", order)

    # Save cosine similarity matrix with JCP IDS
    pl.DataFrame(
        data=cosine_sim_computed,
        schema=med.get_column("Metadata_JCP2022").to_list(),
    ).write_parquet(output_dir / f"{dset}_cosinesim_full.parquet")
    print(f"Matched pairwise {dset} in {perf_counter() - t} seconds")
