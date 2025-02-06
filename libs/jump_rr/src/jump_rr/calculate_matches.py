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

import cupy as cp
import cupyx.scipy.spatial as spatial
import numpy as np
import polars as pl
import polars.selectors as cs
from jump_rr.consensus import add_sample_images, get_consensus_meta_urls, get_range
from jump_rr.datasets import get_dataset
from jump_rr.formatters import add_external_sites
from jump_rr.index_selection import get_bottom_top_indices
from jump_rr.mappers import get_external_mappers, get_synonym_mapper
from jump_rr.metadata import write_metadata
from jump_rr.replicability import add_replicability

assert cp.cuda.get_current_stream().done, "GPU not available"

# %% Setup
## Paths
output_dir = Path("./databases")
datasets = ("crispr", "orf")

## Parameters
n_vals_used = 25  # Number of top and bottom matches used
dist_as_sim = True  # Display distance as integers instead of floats

## Column names
jcp_short = "JCP2022 ID"  # Shortened input data frame
jcp_col = f"Metadata_{jcp_short[:7]}"  # Traditional JUMP metadata colname
std_outname = "Gene/Compound"  # Standard item name
img_col = f"{std_outname} example image"
rep_col = "Phenotypic activity"
match_col = "Match"  # Highest matches
match_jcp_col = f"Match {jcp_short}"
match_img_col = f"{match_col} example image"  # URL with image examples
match_rep_col = f"{rep_col} {match_col}"
dist_col = "Perturbation-Match Similarity"  # Metric name
ext_links_col = f"{match_col} resources"  # Link to external resources (e.g., NCBI)
replicability_cols = {"corrected_p_value":"Corrected p-value", "mean_average_precision": "Phenotypic activity"}


with cp.cuda.Device(1):  # Specify the GPU device
    # %% Processing starts
    for dset in datasets:
        # %% Load Metadata
        df = pl.read_parquet(get_dataset(dset))

        # %% add build url from individual wells
        med, _ = get_consensus_meta_urls(df, "Metadata_JCP2022")

        vals = cp.array(med.select(cs.by_dtype(pl.Float32)).to_numpy())

        # %% Calculate cosine distance
        cosine_dist = spatial.distance.cdist(vals, vals, metric="cosine")

        # Get most correlated and anticorrelated indices
        xs, ys = get_bottom_top_indices(cosine_dist, n_vals_used, skip_first=True)

        jcp_ids = med[jcp_col].to_numpy().astype("<U15")

        # Build a dataframe containing matches
        jcp_df = pl.DataFrame(
            {
                jcp_short: np.repeat(jcp_ids, n_vals_used * 2),
                match_jcp_col: jcp_ids[ys].astype("<U15"),
                dist_col: cosine_dist[xs, ys].get(),
            }
        )

        # Add images for both queries and matches
        df_meta = df.select("^Metadata.*$")
        side_a = add_sample_images(
            jcp_df,
            df_meta,
            get_range(dset),
            img_col,
            left_col="JCP2022 ID",
            right_col="Metadata_JCP2022",
        )
        side_b = add_sample_images(
            jcp_df,
            df_meta,
            get_range(dset),
            match_img_col,
            left_col="Match JCP2022 ID",
            right_col="Metadata_JCP2022",
        )
        jcp_cols = (jcp_short, match_jcp_col)
        jcp_df = jcp_df.join(side_a.select(pl.col((*jcp_cols, img_col))), on=jcp_cols)
        jcp_df = jcp_df.join(
            side_b.select(pl.col((*jcp_cols, match_img_col))), on=jcp_cols
        )

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

        if dset != "compound":
            # Define the external references to use in genetic or chemical datasets
            # TODO Add databases for compounds and ensure that 0-case works
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
            jcp_df = add_external_sites(
                jcp_df, ext_links_col, key_source_mapper
            )

            order.insert(5, ext_links_col)
            order = (*order, *[f"{v}{suffix}" for suffix in ("", " Match") for v in replicability_cols.values()])

        if dist_as_sim:  # Convert cosine distance to similarity
            jcp_df = jcp_df.with_columns(1 - pl.col(dist_col))

        matches_translated = jcp_df.select(order)

        # %% Save results
        output_dir.mkdir(parents=True, exist_ok=True)
        final_output = output_dir / f"{dset}.parquet"
        matches_translated.write_parquet(final_output, compression="zstd")

        write_metadata(dset, "matches", (*order, "(*)"))

        # Save cosine distance matrix with JCP IDS
        pl.DataFrame(
            data=cosine_dist.get(), schema=med.get_column("Metadata_JCP2022").to_list()
        ).write_parquet(output_dir / f"{dset}_cosinesim_full.parquet")
