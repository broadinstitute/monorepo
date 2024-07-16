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
Calculate cosine distance of CRISPR and ORF profiles using a GPU,
then wrangle information and produce an explorable data frame.

This is intended for use on a server with GPUs and high RAM to analyse data massively.
"""
from pathlib import Path

import cupy as cp
import cupyx.scipy.spatial as spatial
import numpy as np
import polars as pl
from jump_rr.concensus import (
    get_concensus_meta_urls,
    get_cycles,
    repeat_cycles,
)
from jump_rr.formatters import format_val
from jump_rr.index_selection import get_bottom_top_indices
from jump_rr.replicability import add_replicability
from jump_rr.translate import get_mappers

assert cp.cuda.get_current_stream().done, "GPU not available"

# %% Setup
## Paths
dir_path = Path("/dgx1nas1/storage/data/shared/morphmap_profiles/")
# datasets = ("crispr", "orf", "compound")
datasets = ("crispr", "orf")
output_dir = Path("./databases")

## Parameters
n_vals_used = 25  # Number of top and bottom matches used
dist_as_sim = True  # Display distance as integers instead of floats

## Column names
jcp_short = "JCP2022"  # Shortened input data frame
jcp_col = f"Metadata_{jcp_short}"  # Traditional JUMP metadata colname
url_col = "Metadata_image"  # Must start with "Metadata" for URL grouping to work
match_col = "Match"  # Highest matches
match_jcp_col = "Match JCP"
match_url_col = f"{match_col} Example"  # URL with image examples
dist_col = "Similarity"  # Metric name
std_outname = "Gene/Compound"  # Standard item name
ext_links_col = f"{match_col} resources"  # Link to external resources (e.g., NCBI)

# HTML formatters
img_formatter = '{{"img_src": {}, "href": {}, "width": 200}}'

# %% Processing starts
for dataset in datasets:
    profiles_path = dir_path / f"{dataset}.parquet"

    # %% Load Metadata
    print(dataset)
    df = pl.read_parquet(profiles_path)

    # %% add build url from individual wells
    med, mrys, urls = get_concensus_meta_urls(df)

    vals = cp.array(med.select(pl.all().exclude("^Metadata.*$")))

    # %% Calculate cosine distance
    cosine_sim = spatial.distance.cdist(vals, vals, metric="cosine")

    # Get most correlated and anticorrelated indices
    xs, ys = get_bottom_top_indices(cosine_sim, n_vals_used, skip_first=True)

    # Build a dataframe containing matches
    jcp_ids = urls.select(pl.col(jcp_col)).to_series().to_numpy().astype("<U15")
    url_vals = urls.get_column(url_col).to_numpy()
    cycles = get_cycles(dataset)
    cycled_indices = repeat_cycles(len(xs), dataset)

    jcp_df = pl.DataFrame(
        {
            jcp_short: np.repeat(jcp_ids, n_vals_used * 2),
            match_jcp_col: jcp_ids[ys].astype("<U15"),
            dist_col: cosine_sim[xs, ys].get(),
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
    uniq_jcp = tuple(jcp_df.unique(subset=jcp_short).to_numpy()[:, 0])
    jcp_std_mapper, jcp_external_mapper = get_mappers(uniq_jcp, dataset)

    # %% Add replicability
    jcp_df = add_replicability(jcp_df, left_on=jcp_short, right_on=jcp_col)
    jcp_df = add_replicability(
        jcp_df, left_on=match_jcp_col, right_on=jcp_col, suffix=" Match"
    )

    jcp_translated = jcp_df.with_columns(
        pl.col(jcp_short).replace(jcp_std_mapper).alias(std_outname),
        pl.col(match_jcp_col).replace(jcp_std_mapper).alias(match_col),
        pl.col(match_jcp_col).replace(jcp_external_mapper).alias(ext_links_col),
    )

    if dist_as_sim:  # Convert cosine distance to similarity
        jcp_translated = jcp_translated.with_columns(
            (1 - pl.col(dist_col)).alias(dist_col)
        )

    matches = jcp_translated.rename({url_col: f"{std_outname} Example"})

    # Sort columns
    order = [
        std_outname,
        match_col,
        f"{std_outname} Example",
        match_url_col,
        dist_col,
        ext_links_col,
        jcp_short,
        match_jcp_col,
        "corrected_p_value",
        "corrected_p_value Match",
    ]
    matches_translated = matches.select(order)

    # %% Save results
    output_dir.mkdir(parents=True, exist_ok=True)
    final_output = output_dir / f"{dataset}.parquet"
    matches_translated.write_parquet(final_output, compression="zstd")

    # - TODO add Average precision metrics
