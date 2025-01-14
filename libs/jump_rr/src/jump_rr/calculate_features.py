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
Generate a table with the most important feature values.

Select the CRISPR and ORF highest and lowest feature values,
then wrangle information and produce an explorable data frame.
This is intended for use on a server with GPUs and high RAM to analyse
data en masse.

Steps:
- Group feature names using regular expression
- Get median from the grouped subfeatures
- Build DataFrame
- Add reproducibility metric (Phenotypic activity)
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
from jump_rr.datasets import get_dataset
from jump_rr.formatters import format_val
from jump_rr.index_selection import get_edge_indices
from jump_rr.metadata import write_metadata
from jump_rr.parse_features import get_feature_groups
from jump_rr.replicability import add_replicability
from jump_rr.significance import add_pert_type, pvals_from_path
from jump_rr.synonyms import get_synonym_mapper
from jump_rr.translate import get_mapper

assert cp.cuda.get_current_stream().done, "GPU not available"

# %% Setup
## Paths
output_dir = Path("./databases")
datasets = (
    "crispr_interpretable",
    "orf_interpretable",
)

## Parameters
n_vals_used = 200  # Number of top and bottom matches used
feat_decomposition = ("Compartment", "Feature", "Channel", "Suffix")

## Column names
jcp_short = "JCP2022 ID"  # Shortened input data frame
jcp_col = f"Metadata_{jcp_short[:7]}"  # Traditional JUMP metadata colname
std_outname = "Gene/Compound"  # Standard item name
ext_links_col = "Resources"  # Link to external resources (e.g., NCBI)
url_col = "Gene/Compound example image"
rep_col = "Phenotypic activity"  # Column containing reproducibility
val_col = "Median"  # Value col
stat_col = "Feature significance"

with cp.cuda.Device(1): # Specify the GPU device
    for dset in datasets:
        print(f"Processing features for {dset} dataset")

        # %% Loading
        precor = pl.read_parquet(get_dataset(dset))
        dset_type = dset.removesuffix("_interpretable")
        precor = add_pert_type(precor, dataset=dset_type)

        # %% Split data into med (concensus), meta and urls
        # Note that we remove the negcons from these analysis, as they are used to produce p-values on significance.py
        med, _, urls = get_concensus_meta_urls(
            precor.filter(pl.col("Metadata_pert_type") != "negcon"),
            url_colname="Metadata_placeholder",
        )
        urls = urls.rename({"Metadata_placeholder": url_col})

        # This function also performs a filter to remove controls (as there are too many)
        corrected_pvals = pvals_from_path(get_dataset(dset), dataset=dset_type)
        # Ensure that the perturbation numbers match
        filtered_med = med.filter(
            pl.col(jcp_col).is_in(corrected_pvals.get_column(jcp_col))
        )
        median_vals = cp.array(
            filtered_med.select(pl.exclude("^Metadata.*$")).to_numpy()
        )

        phenact = cp.array(corrected_pvals.select(pl.exclude(jcp_col)).to_numpy())

        # Find bottom $n_values_used
        xs, ys = get_edge_indices(
            phenact.T,
            n_vals_used,
        )

        decomposed_feats = get_feature_groups(
            tuple(filtered_med.select(pl.exclude("^Metadata.*$")).columns),
            feat_decomposition,
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
                stat_col: phenact[xs, ys].get(),
                val_col: median_vals[xs, ys].get(),
                jcp_short: med[jcp_col][ys],
                url_col: [  # Use indices to fetch matches
                    format_val("img", (img_src, img_src))
                    for url, idx in zip(url_vals[ys], cycled_indices[ys])
                    if (img_src := next(url).format(next(idx)))
                ],
            }
        )

        uniq = tuple(df.get_column(jcp_short).unique())
        jcp_std_mapper, jcp_external_mapper = get_mapper(uniq, dset)
        _, jcp_external_raw_mapper = get_mapper(uniq, dset, format_output=False)

        # Add phenotypic activity from a previously-calculated
        df = add_replicability(
            df, left_on=jcp_short, right_on=jcp_col, replicability_col=rep_col
        )

        # Add aliases and external links
        jcp_translated = df.with_columns(
            pl.col(jcp_short).replace(jcp_std_mapper).alias(std_outname),
            pl.col(jcp_short).replace(jcp_external_mapper).alias(ext_links_col),
            pl.col(jcp_short)  # Add synonyms
            .replace(jcp_external_raw_mapper)  # Map to NCBI ID
            .replace(get_synonym_mapper())  # Map synonyms
            .alias("Synonyms"),
        )

        # Reorder columns
        order = [
            *decomposed_feats.columns,
            stat_col,
            std_outname,
            url_col,
            val_col,
            rep_col,
            "Synonyms",
            jcp_short,
            ext_links_col,
        ]
        sorted_df = jcp_translated.select(order)

        # Output
        output_dir.mkdir(parents=True, exist_ok=True)
        jcp_translated.write_parquet(
            output_dir / f"{dset}_features.parquet", compression="zstd"
        )

        # Update metadata
        write_metadata(dset_type, "feature", (*jcp_translated.columns, "(*)"))

        # Save phenotypic activity matrix in case it is of use to others
        pl.DataFrame(
            data=phenact.get(),
            schema=filtered_med.select(pl.exclude("^Metadata.*$")).columns,
        ).with_columns(filtered_med.get_column("Metadata_JCP2022")).write_parquet(
            output_dir / f"{dset_type}_significance_full.parquet"
        )
