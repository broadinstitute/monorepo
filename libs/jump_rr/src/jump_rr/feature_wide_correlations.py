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
Calculate all the feature correlations at the global level.
(e.g., all features vs all features).
"""

from pathlib import Path

import cupy as cp
import numpy as np
import polars as pl
from jump_rr.parse_features import get_feature_groups
from polars.selectors import numeric


def map_back(k, n):
    # Map from a linear index to an upper triangle
    i = int(n - 2 - np.floor(np.sqrt(-8 * k + 4 * n * (n - 1) - 7) / 2.0 - 0.5))
    j = int(k + i + 1 - n * (n - 1) / 2 + (n - i) * ((n - i) - 1) / 2)

    return i, j


dir_path = Path("/ssd/data/shared/morphmap_profiles/")
output_dir = Path("./databases")
datasets = ("crispr", "orf")
for dset in datasets:
    precor_path = dir_path / f"{dset}_interpretable.parquet"
    prof = pl.read_parquet(precor_path)

    # Get the mapper that will be used later
    feats = tuple(prof.select(numeric()).columns)
    mapper = {
        k: "~".join(v) for k, v in zip(feats, get_feature_groups(feats).iter_rows())
    }

    med = prof.group_by(by="Metadata_JCP2022", maintain_order=True).median()
    arr = cp.array(med.select(numeric()), dtype=cp.float32)

    # Calculate the Perason correlation coefficient of all vs all features
    corr_cp = cp.corrcoef(arr, rowvar=False)
    corr = pl.DataFrame(corr_cp.get())
    corr.columns = prof.select(numeric()).columns
    corr.write_parquet(output_dir / f"{dset}_feature_wide.parquet", compression="zstd")

    # %% Add the grouped features
    name = "Full Feat"
    melted = corr.with_columns(pl.Series(corr.columns).alias(f"{name} A")).melt(
        id_vars=f"{name} A", variable_name=f"{name} B", value_name="Pearson Corr"
    )
    for feat in ("Full Feat A", "Full Feat B"):
        melted = melted.with_columns(
            pl.col(feat).replace(mapper).str.split_exact("~", 3).alias("Feat_A")
        ).unnest("Feat_A")
        melted = melted.rename(
            {
                f"field_{x}": f"{feat[-1]} {y}"
                for x, y in enumerate(("Object", "Feat", "Channel", "Suffix"))
            }
        )

    # Select upper diag to avoid repeats
    index_mat = np.arange(len(corr) ** 2).reshape((len(corr), len(corr)))
    idx_for_uniq = index_mat[np.triu_indices(len(corr), k=1)]
    uniq = (
        melted.with_row_count()
        .filter(pl.col("row_nr").is_in(idx_for_uniq))
        .select(pl.exclude("row_nr"))
    )
    w_equals = uniq.with_columns(
        [
            (pl.col(f"A {subfeat}") == pl.col(f"B {subfeat}")).alias(f"Equal {subfeat}")
            for subfeat in ("Object", "Feat", "Channel")
        ]
    )
    dropped_subfeats = w_equals.select(pl.exclude("^[AB] .*$"))
    # Save all the non-repeated p values
    dropped_subfeats.write_parquet(
        output_dir / f"{dset}_feature_correlation.parquet", compression="zstd"
    )

    # save the edges for biologists to explore the most interesting correlations
    nsaved = 10000
    sorted_edges = (
        dropped_subfeats.sort(by="Pearson Corr")
        .with_row_count()
        .filter((pl.col("row_nr") < nsaved) | (pl.col("row_nr") > len(uniq) - nsaved))
        .select(pl.exclude("row_nr"))
    )
    sorted_edges.write_parquet(
        output_dir / f"{dset}_selected_edges.parquet", compression="zstd"
    )
