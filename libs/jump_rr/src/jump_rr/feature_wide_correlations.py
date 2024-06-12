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

import numpy as np
import cupy as cp
import cupyx.scipy.spatial as spatial
import polars as pl
from jump_rr.concensus import get_group_median

def map_back(k , n):
    # Map from a linear index to an upper triangle 
    i = int( n - 2 - np.floor(np.sqrt(-8*k + 4*n*(n-1)-7)/2.0 - 0.5) )
    j = int( k + i + 1 - n*(n-1)/2 + (n-i)*((n-i)-1)/2 )

    return i,j

dir_path = Path("/ssd/data/shared/morphmap_profiles/")
output_dir = Path("./databases")
datasets = ("CRISPR", "ORF")
for dset in datasets:
    precor_path = dir_path / f"{dset}_interpretable.parquet"
    prof = pl.read_parquet(precor_path)
    med = get_group_median(prof)

    arr = cp.array(med.select(pl.col("^column.*$")), dtype=cp.float32 )
    features = med.select(pl.exclude("^column.*$"))
     
    # Calculate the Perason correlation coefficient of all vs all features
    corr_cp = cp.corrcoef(arr)
    corr = pl.DataFrame(corr_cp.get())
    corr = pl.concat(( features, corr ), how="horizontal")
    corr.write_parquet(output_dir / f"{dset}_feature_wide.parquet", compression="zstd")
    

    # Get the 100 highest (+anti)correlated features across all of JUMP
    upper_tri = np.triu_indices(len(corr_cp), k=1) 
    flat = corr_cp[upper_tri]
    bottom_sorted = flat.argpartition(100)
    bottom_idx = bottom_sorted[:100]
    top_sorted = flat.argpartition(-100)
    top_idx = top_sorted[-100:]
    top = flat[top_idx]
    bottom = flat[bottom_idx]

    names = features.select(pl.concat_str(pl.all())).to_numpy()
    bottom_coords = list(map(lambda x: map_back(x, len(corr_cp)), bottom_idx ) )
    top_coords = list(map(lambda x: map_back(x, len(corr_cp)), top_idx ) )


    a, b = map(list, names[np.concatenate((bottom_coords,top_coords))][...,0].T )
    highest_correlated = pl.DataFrame(
       {"correlation":cp.concatenate((bottom,top )).get(),
        "feature_A": a,
        "feature_B": b,
        } ,
    )

    highest_correlated.write_csv(output_dir / f"{dset}_feature_correlations.csv")

