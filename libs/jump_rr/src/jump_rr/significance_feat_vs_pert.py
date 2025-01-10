#!/usr/bin/env jupyter

from pathlib import Path

import polars as pl
from jump_rr.significance import add_pert_type, partition_by_trt
from scipy.stats import mannwhitneyu
from tqdm import tqdm

dir_path = Path("/ssd/data/shared/morphmap_profiles/")
output_dir = Path("./databases")
datasets = ("crispr", "orf")
for dset in datasets:
    precor_path = dir_path / f"{dset}_interpretable.parquet"
    prof = pl.read_parquet(precor_path)
    df = add_pert_type(prof)
    partitioned = partition_by_trt(df)

    def wrapper_mwu(jcp_pair):
        key, (pos, neg) = jcp_pair
        return (key, mannwhitneyu(pos, neg).pvalue)

    result = []
    for x in tqdm(partitioned.items()):
        result.append(wrapper_mwu(x))

    feat_vs_pert_pvals = pl.DataFrame(
        {
            "Feature": prof.select(pl.exclude("^Metadata.*$")).columns,
            **dict(result),
        }
    )
    feat_vs_pert_pvals.write_parquet(
        output_dir / f"{dset}_feat_pert_pval_mwu.parquet", compression="zstd"
    )
