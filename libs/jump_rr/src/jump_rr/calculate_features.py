#!/usr/bin/env jupyter
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
Select the perturbations with highest and lowest feature values
for CRISPR and ORF datasets using a GPU,
then wrangle information and produce an explorable data frame.

This is intended for use on a server with GPUs and high RAM to analyse
 data massively.

Steps:
- Group feature names using regular expression
- Get median from the grouped subfeatures
- Build dataframe
"""
from pathlib import Path

import cupy as cp
import numpy as np
import polars as pl
from jump_rr.concensus import (
    get_concensus_meta_urls,
    get_cycles,
    repeat_cycles,
)
from jump_rr.formatters import format_val
from jump_rr.index_selection import get_edge_indices
from jump_rr.parse_features import get_feature_groups
from jump_rr.replicability import add_replicability
from jump_rr.significance import add_pert_type, pvals_from_path
from jump_rr.translate import get_mappers

assert cp.cuda.get_current_stream().done, "GPU not available"

# %% Setup
## Paths
dir_path = Path("/datastore/shared/morphmap_profiles/")
output_dir = Path("./databases")
datasets = ("crispr", "orf")

for dset in datasets:
    precor_path = dir_path / f"{dset}_interpretable.parquet"

    ## Parameters
    n_vals_used = 50  # Number of top and bottom matches used

    ## Column names
    jcp_short = "JCP2022"  # Shortened input data frame
    jcp_col = f"Metadata_{jcp_short}"  # Traditional JUMP metadata colname
    match_col = "Match"  # Highest matches
    match_url_col = f"{match_col} Example"  # URL with image examples
    std_outname = "Gene/Compound"  # Standard item name
    ext_links_col = "Resources"  # Link to external resources (e.g., NCBI)
    url_col = "Metadata_image"  # Must start with "Metadata" for URL grouping to work
    feature_names = ("Mask", "Feature", "Channel")

    # %% Loading
    precor = pl.read_parquet(precor_path)
    precor = add_pert_type(precor, dataset=dset)

    # %% Split data into med (concensus), meta and urls

    # Note that we remove the negcons from these analysis, as they are used to
    # produce p values on significance.py
    med, _, urls = get_concensus_meta_urls(
        precor.filter(pl.col("Metadata_pert_type") != "negcon")
    )

    # This function also performs a filter to remove controls (as there are too many)
    corrected_pvals = pvals_from_path(precor_path, dataset=dset)
    # Ensure that the perturbation numbers match
    filtered_med = med.filter(
        pl.col(jcp_col).is_in(corrected_pvals.get_column(jcp_col))
    )
    median_vals = cp.array(filtered_med.select(pl.exclude("^Metadata.*$")).to_numpy())

    phenact = cp.array(corrected_pvals.select(pl.exclude(jcp_col)).to_numpy())

    # Find bottom $n_values_used
    xs, ys = get_edge_indices(
        phenact.T,
        n_vals_used,
    )

    decomposed_feats = get_feature_groups(
        tuple(filtered_med.select(pl.exclude("^Metadata.*$")).columns)
    )

    url_vals = urls.get_column(url_col).to_numpy()
    cycles = get_cycles(dset)
    cycled_indices = repeat_cycles(len(xs), dset)

    # %% Build Data Frame
    df = pl.DataFrame(
        {
            **{
                col: np.repeat(vals, n_vals_used)
                for col, vals in decomposed_feats.to_dict().items()
            },
            "Phenotypic Activity": phenact[xs, ys].get(),
            "Median": median_vals[xs, ys].get(),
            jcp_short: med[jcp_col][ys],
            url_col: [  # Use indices to fetch matches
                format_val("img", (img_src, img_src))
                for url, idx in zip(url_vals[ys], cycled_indices[ys])
                if (img_src := next(url).format(next(idx)))
            ],
        }
    )

    uniq = tuple(df.get_column(jcp_short).unique())
    jcp_std_mapper, jcp_external_mapper = get_mappers(uniq, dset)

    df = add_replicability(df, left_on=jcp_short, right_on=jcp_col)

    jcp_translated = df.with_columns(
        pl.col(jcp_short).replace(jcp_std_mapper).alias(std_outname),
        pl.col(jcp_short).replace(jcp_external_mapper).alias(ext_links_col),
    )

    # Reorder columns
    order = [
        "Mask",
        "Feature",
        "Channel",
        "Suffix",
        "Phenotypic Activity",
        std_outname,
        url_col,
        "Median",
        "corrected_p_value",
        jcp_short,
        ext_links_col,
    ]
    sorted_df = jcp_translated.select(order)

    # Output
    output_dir.mkdir(parents=True, exist_ok=True)
    sorted_df.write_parquet(output_dir / f"{dset}_features.parquet", compression="zstd")
