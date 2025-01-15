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
from jump_rr.concensus import (
    get_concensus_meta_urls,
    get_cycles,
    repeat_cycles,
)
from jump_rr.datasets import get_dataset
from jump_rr.formatters import format_val
from jump_rr.index_selection import get_bottom_top_indices
from jump_rr.metadata import write_metadata
from jump_rr.replicability import add_replicability
from jump_rr.synonyms import get_synonym_mapper
from jump_rr.translate import get_external_mappers

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
url_col = f"{std_outname} example image"
rep_col = "Phenotypic activity"
match_col = "Match"  # Highest matches
match_jcp_col = f"Match {jcp_short}"
match_url_col = f"{match_col} example image"  # URL with image examples
match_rep_col = f"{rep_col} {match_col}"
dist_col = "Perturbation-Match Similarity"  # Metric name
ext_links_col = f"{match_col} resources"  # Link to external resources (e.g., NCBI)

# HTML formatters
img_formatter = '{{"img_src": {}, "href": {}, "width": 200}}'


with cp.cuda.Device(1):  # Specify the GPU device
    # %% Processing starts
    for dset in datasets:
        # %% Load Metadata
        print(dset)
        df = pl.read_parquet(get_dataset(dset))

        # %% add build url from individual wells
        med, _, urls = get_concensus_meta_urls(df, url_colname="Metadata_placeholder")
        urls = urls.rename({"Metadata_placeholder": url_col})

        vals = cp.array(med.select(cs.by_dtype(pl.Float32)).to_numpy())

        # %% Calculate cosine distance
        cosine_dist = spatial.distance.cdist(vals, vals, metric="cosine")

        # Get most correlated and anticorrelated indices
        xs, ys = get_bottom_top_indices(cosine_dist, n_vals_used, skip_first=True)

        # Build a dataframe containing matches
        jcp_ids = urls.select(pl.col(jcp_col)).to_series().to_numpy().astype("<U15")
        url_vals = urls.get_column(url_col).to_numpy()
        cycles = get_cycles(dset)
        cycled_indices = repeat_cycles(len(xs), dset)

        jcp_df = pl.DataFrame(
            {
                jcp_short: np.repeat(jcp_ids, n_vals_used * 2),
                match_jcp_col: jcp_ids[ys].astype("<U15"),
                dist_col: cosine_dist[xs, ys].get(),
                url_col: [  # Secuentially produce multiple images
                    format_val("img", (img_src, img_src))
                    for x in url_vals
                    for j in range(n_vals_used * 2)
                    if (img_src := next(x).format(next(cycles)))
                ],
                match_url_col: [  # Use indices to fetch matches
                    format_val("img", (img_src, img_src))
                    for url, idx in zip(url_vals[ys], cycled_indices[ys])
                    if (img_src := next(url).format(next(idx)))
                ],
            }
        )

        # %% Translate genes names to standard
        jcp_std_mapper, jcp_external_mapper, jcp_external_raw_mapper = get_external_mappers(df, jcp_col, dset)

        # %% Add replicability
        jcp_df = add_replicability(
            jcp_df,
            left_on=jcp_short,
            right_on=jcp_col,
            replicability_col=rep_col,
        )
        jcp_df = add_replicability(
            jcp_df,
            left_on=match_jcp_col,
            right_on=jcp_col,
            suffix=" Match",
            replicability_col=match_rep_col,
        )

        jcp_translated = jcp_df.with_columns(
            pl.col(jcp_short).replace(jcp_std_mapper).alias(std_outname),
            pl.col(match_jcp_col).replace(jcp_std_mapper).alias(match_col),
            pl.col(match_jcp_col).replace(jcp_external_mapper).alias(ext_links_col),
            pl.col(jcp_short)  # Add synonyms
            .replace(jcp_external_raw_mapper)  # Map to NCBI ID
            .replace(get_synonym_mapper())  # Map synonyms
            .alias("Synonyms"),
        )

        if dist_as_sim:  # Convert cosine distance to similarity
            jcp_translated = jcp_translated.with_columns(
                (1 - pl.col(dist_col)).alias(dist_col)
            )

        # Sort columns
        order = [
            std_outname,
            match_col,
            url_col,
            match_url_col,
            dist_col,
            ext_links_col,
            "Synonyms",
            jcp_short,
            match_jcp_col,
            rep_col,
            match_rep_col,
        ]
        matches_translated = jcp_translated.select(order)

        # %% Save results
        output_dir.mkdir(parents=True, exist_ok=True)
        final_output = output_dir / f"{dset}.parquet"
        matches_translated.write_parquet(final_output, compression="zstd")

        write_metadata(dset, "matches", (*order, "(*)"))

        # Save cosine distance matrix with JCP IDS
        pl.DataFrame(
            data=cosine_dist.get(), schema=med.get_column("Metadata_JCP2022").to_list()
        ).write_parquet(output_dir / f"{dset}_cosinesim_full.parquet")
