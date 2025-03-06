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

import dask.array as da
import duckdb
import polars as pl
from jump_rr.consensus import (
    add_sample_images,
    get_consensus_meta_urls,
    get_range,
)
from jump_rr.datasets import get_dataset
from jump_rr.formatters import add_external_sites
from jump_rr.index_selection import get_ranks
from jump_rr.mappers import get_external_mappers, get_synonym_mapper
from jump_rr.metadata import write_metadata
from jump_rr.parse_features import get_feature_groups
from jump_rr.replicability import add_replicability
from jump_rr.significance import add_pert_type, pvals_from_path

# %% Setup
## Paths
output_dir = Path("./databases")
datasets = (
    "crispr_interpretable",
    "orf_interpretable",
)

## Parameters
n_vals_used = 30  # Number of top and bottom matches used
feat_decomposition = ("Compartment", "Feature", "Channel", "Suffix")

## Column names
jcp_short = "JCP2022 ID"  # Shortened input data frame
jcp_col = f"Metadata_{jcp_short[:7]}"  # Traditional JUMP metadata colname
std_outname = "Gene/Compound"  # Standard item name
ext_links_col = "Resources"  # Link to external resources (e.g., NCBI)
img_col = "Gene/Compound example image"
rep_col = "Phenotypic activity"  # Column containing reproducibility
val_col = "Median"  # Value col
stat_col = "Feature significance"
rank_feat_col = "Feature Rank"
rank_gene_col = "Gene Rank"
replicability_cols = {
    "corrected_p_value": "Corrected p-value",
    "mean_average_precision": "Phenotypic activity",
}

for dset in datasets:
    print(f"Processing features for {dset} dataset")

    # %% Loading
    precor = pl.read_parquet(get_dataset(dset))
    dset_type = dset.removesuffix("_interpretable")
    precor = add_pert_type(precor, dataset=dset_type)

    # %% Split data into med (consensus), meta and urls
    # Note that we remove the negcons from these analysis, as they are used to produce p-values on significance.py
    med, _ = get_consensus_meta_urls(
        precor.filter(pl.col("Metadata_pert_type") != "negcon"),
        "Metadata_JCP2022",
    )

    # This function also performs a filter to remove controls (as there are too many)
    corrected_pvals = pvals_from_path(get_dataset(dset), dataset=dset_type)
    # Ensure that the perturbation numbers match
    filtered_med = med.filter(
        pl.col(jcp_col).is_in(corrected_pvals.get_column(jcp_col))
    )
    median_vals = da.array(filtered_med.select(pl.exclude("^Metadata.*$")).to_numpy())

    phenact = da.array(corrected_pvals.select(pl.exclude(jcp_col)).to_numpy())

    lowest_x, lowest_y = get_ranks(phenact, n_vals_used)
    index_lowest_rank_x = da.vstack(
        (
            da.indices((len(lowest_x), n_vals_used)).reshape((2, -1)),
            lowest_x.flatten(),
        ),
    ).compute()
    index_lowest_rank_y = da.vstack(
        (
            da.indices((lowest_y.shape[1], n_vals_used)).reshape((2, -1)),
            lowest_y.flatten(),
        ),
    ).compute()

    # Unify Gene and Feature ranks
    with duckdb.connect(":memory:") as conn:
        table = duckdb.sql(
            "SELECT x,y,any_value(rank_feat) AS rank_feat,any_value(rank_gene) AS rank_gene"
            " FROM (SELECT * FROM (SELECT column0 as x,column1 as rank_feat,column2 as y"
            " FROM index_lowest_rank_x) UNION ALL BY NAME"
            " (SELECT column0 AS y,column1 AS rank_gene, column2 AS x"
            " FROM index_lowest_rank_y)) GROUP By x,y"
        )
        items = table.fetchnumpy()
        xs = items["x"]
        ys = items["y"]
        rank_feat = items["rank_feat"].filled()
        rank_gene = items["rank_gene"].filled()

    # Get the Gene Rank and Feature Rank
    decomposed_feats = get_feature_groups(
        tuple(filtered_med.select(pl.exclude("^Metadata.*$")).columns),
        feat_decomposition,
    )
    phenact_computed = phenact.compute()

    # %% Build Data Frame
    df = pl.DataFrame({
        **{
            k: v
            for k, v in zip(decomposed_feats.columns, decomposed_feats.to_numpy()[ys].T)
        },
        stat_col: phenact_computed[xs, ys],
        val_col: median_vals.compute()[xs, ys],
        jcp_short: med[jcp_col][xs],
        rank_gene_col: rank_gene,
        rank_feat_col: rank_feat,
    })

    # Add images
    df_meta = precor.select("^Metadata.*$")
    df = add_sample_images(
        df,
        df_meta,
        get_range(dset.removesuffix("_interpretable")),
        img_col,
        left_col="JCP2022 ID",
        right_col="Metadata_JCP2022",
    )

    jcp_to_std, jcp_to_entrez, std_to_omim, std_to_ensembl = get_external_mappers(
        precor, jcp_col, dset.removesuffix("_interpretable")
    )

    # Add phenotypic activity from a previously-calculated
    df = add_replicability(
        df,
        left_on=jcp_short,
        right_on=jcp_col,
        cols_to_add=replicability_cols,
    )

    # Add aliases and external links
    jcp_translated = df.with_columns(
        pl.col(jcp_short).replace(jcp_to_std).alias(std_outname),
        pl.col(jcp_short)  # Add synonyms
        .replace(jcp_to_entrez)  # Map to entrez ID
        .replace(get_synonym_mapper())  # Map synonyms
        .alias("Synonyms"),
    )

    # Reorder columns
    order = [
        *decomposed_feats.columns,
        stat_col,
        std_outname,
        img_col,
        val_col,
        *replicability_cols.values(),
        rank_gene_col,
        rank_feat_col,
        jcp_short,
        # ext_links_col,
        "Synonyms",
    ]

    key_source_mapper = (
        ("entrez", jcp_short, jcp_to_entrez),
        ("omim", std_outname, std_to_omim),
        (
            "genecards",
            std_outname,
            dict(zip(jcp_to_std.values(), jcp_to_std.values())),
        ),
        ("ensembl", std_outname, std_to_ensembl),
    )
    w_external_sites = add_external_sites(
        jcp_translated, ext_links_col, key_source_mapper
    )
    order.insert(-1, ext_links_col)

    sorted_df = w_external_sites.select(order)

    # Output
    output_dir.mkdir(parents=True, exist_ok=True)
    sorted_df.write_parquet(output_dir / f"{dset}_features.parquet", compression="zstd")

    # Update metadata
    write_metadata(dset_type, "feature", (*sorted_df.columns, "(*)"))

    # Save phenotypic activity matrix in case it is of use to others
    out_df = pl.DataFrame(
        data=phenact_computed,
        schema=filtered_med.select(pl.exclude("^Metadata.*$")).columns,
    ).with_columns(filtered_med.get_column("Metadata_JCP2022"))
    out_df.write_parquet(output_dir / f"{dset_type}_significance_full.parquet")
