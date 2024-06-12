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
import cupyx.scipy.spatial as spatial
import polars as pl
from jump_rr.concensus import get_group_median

dir_path = Path("/ssd/data/shared/morphmap_profiles/")
output_dir = Path("./databases")
# datasets = ("orf", "crispr")
datasets = ("crispr", "orf", "compound")
for dset in datasets:
    precor_path = dir_path / f"{dset}_interpretable.parquet"
    prof = pl.read_parquet(precor_path)
    med = get_group_median(prof)

    arr = cp.array(med.select(pl.col("^column.*$")), dtype=cp.float32 )

    corr = pl.DataFrame(cp.corrcoef(arr).get())
    corr = pl.concat((med.select(pl.exclude("^column.*$")), corr), how="horizontal")
    corr.write_parquet(output_dir / f"{dset}_feature_wide.parquet", compression="zstd")
