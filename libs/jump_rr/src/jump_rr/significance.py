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
Generate aggregated statistics for feature values
Based on discussion https://github.com/broadinstitute/2023_12_JUMP_data_only_vignettes/issues/4#issuecomment-1918019212

1. Calculate the p value of all features
2. then adjust the p value to account for multiple testing https://www.statsmodels.org/dev/generated/statsmodels.stats.multitest.multipletests.html (fdr_bh)
3. Group features based on their hierarchy and compute combined p-value per group using https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.combine_pvalues.html (fisher); this will give you a p-value per group
4. then correct the p values from step 5 (fdr_bh)
"""

from math import sqrt
from pathlib import Path
from time import perf_counter

from broad_babel.query import get_mapper
from cachier import cachier

try:
    import cupy as cp
except Exception:
    import numpy as cp

import numpy as np
import polars as pl
from parse_features import get_feature_groups
from pathos.multiprocessing import Pool
from scipy.stats import combine_pvalues, t
from statsmodels.stats.multitest import multipletests
from tqdm import tqdm

# TODO try to reimplement statsmodels on cupy

np.seterr(divide="ignore")


def sample_ids(
    df: pl.DataFrame,
    column: str = "Metadata_JCP2022",
    n: int = 100,
    negcons: bool = True,
    seed: int = 42,
) -> pl.DataFrame:
    """Sample all occurrences of n ids in a given column, adding their negative controls."""
    identifiers = (
        df.filter(pl.col("Metadata_pert_type") != pl.lit("negcon"))
        .get_column(column)
        .sample(n)
    )
    index_filter = pl.col(column).is_in(identifiers)
    if negcons:
        unique_plates = (
            (
                df.filter(pl.col(column).is_in(identifiers)).select(
                    pl.col("Metadata_Plate")
                )
            )
            .to_series()
            .unique()
        )
        index_filter = index_filter | (
            pl.col("Metadata_Plate").is_in(unique_plates)
            & (pl.col("Metadata_pert_type") == pl.lit("negcon"))
        )
    result = df.filter(index_filter)
    return result


def partition_by_trt(
    df: pl.DataFrame,
    column: str = "Metadata_JCP2022",
    negcons_per_plate: int = 2,
    seed: int = 42,
) -> dict[str, tuple[pl.DataFrame, pl.DataFrame]]:
    """
    Partition a dataframe by using identifier column (by default Metadata_JCP2022)
    and then further split into two dataframes, one for positive controls and one
    for negative controls.
    """
    meta_cols = (column, "Metadata_pert_type", "Metadata_Plate")
    pos_partition, neg_partition = df.select(
        pl.col(meta_cols),
        pl.all().exclude("^Metadata.*$").cast(pl.Float32),
    ).partition_by("Metadata_pert_type", include_key=False)

    neg_partition = neg_partition.drop(column)
    if negcons_per_plate:  # Sample $negcons_per_plate elements from each plate
        neg_partition = neg_partition.filter(
            pl.int_range(0, pl.count()).shuffle(seed=seed).over("Metadata_Plate")
            < negcons_per_plate
        )

    ids_plates = dict(pos_partition.group_by(column).agg("Metadata_Plate").iter_rows())

    ids_prof = pos_partition.drop("Metadata_pert_type", "Metadata_Plate").partition_by(
        column, as_dict=True, maintain_order=False, include_key=False
    )

    # TODO is there a better way to return only float values?
    id_trt_negcon = {
        id_: (
            ids_prof[id_],
            neg_partition.filter(pl.col("Metadata_Plate").is_in(plates)).drop(
                "Metadata_Plate"
            ),
        )
        for id_, plates in ids_plates.items()
    }
    return id_trt_negcon


def get_p_value(a, b, negcons_per_plate: int = 2, seed: int = 42):
    """
    Calculate the p value of two matrices in a column fashion.
    TODO check if we should sample independently or if we can sample once and used all features from a given sample set.
    Challenge:
    - Multiple genes likely share multiple negative controls

    Solution:
    1. Find gene
    2. Find its negative controls
    3. Sample negative controls
    4. Calculate p value of both distributions
    """
    # Convert relevant values to cupy
    matrix_a = cp.array(a)
    matrix_b = cp.array(b)

    # Calculate t statistic
    mean_a, mean_b = (matrix_a.mean(axis=0), matrix_b.mean(axis=0))
    std_a, std_b = matrix_a.std(axis=0, ddof=1), matrix_b.std(axis=0, ddof=1)
    n_a, n_b = (len(a), len(b))
    se_a, se_b = std_a / sqrt(n_a), std_b / sqrt(n_b)
    sed = cp.sqrt(se_a**2 + se_b**2)
    t_stat = (mean_a - mean_b) / sed
    # Calculate p value
    df = n_a + n_b - 2
    p = (1 - t.cdf((np.abs(t_stat).get()), df)) ** 2  # TODO cupy remove scipy dep

    return np.nan_to_num(p, nan=1.0)


def calculate_pvals(
    profiles: pl.DataFrame,
    negcons_per_plate: int = 2,
    seed: int = 42,
):
    """
    Calculate the pvalues of each feature against a sample of their negative controls.
    1. Calculate the p value of all features
    2. then adjust the p value to account for multiple testing
    """
    partitioned = partition_by_trt(profiles, seed=seed)
    features = tuple(
        list(partitioned.values())[0][0]
        .select(pl.all().exclude("^Metadata.*$"))
        .columns
    )

    print("Calculating p values")
    timer = perf_counter()

    n_items = len(partitioned)
    p_values = np.ones((n_items, len(features)), dtype=np.float32)
    for i, k in tqdm(enumerate(partitioned.keys()), total=n_items):
        p_values[i, :] = get_p_value(
            *partitioned[k],
            negcons_per_plate=negcons_per_plate,
            seed=seed,
        )
    print(f"{perf_counter()-timer}")

    print("FDR correction")
    timer = perf_counter()
    corrected = pl.DataFrame([multipletests(x, method="fdr_bh")[1] for x in p_values])
    print(f"{perf_counter()-timer}")

    return corrected


def add_pert_type(profiles: pl.DataFrame, poscons: bool = False) -> pl.DataFrame:
    """
    Add metadata with perturbation type from the JCP2022 ID.
    poscons: Ensure all outputs are trt or negcon. Drop nulls.
    """
    pert_type = "Metadata_pert_type"
    if "Metadata_pert_type" not in profiles.select(pl.col("^Metadata.*$")).columns:
        # Add perturbation type metadata (new profiles exclude it)
        jcp_to_pert_type = get_mapper(
            profiles.get_column("Metadata_JCP2022"),
            input_column="JCP2022",
            output_column="JCP2022,pert_type",
        )
        profiles = profiles.with_columns(
            pl.col("Metadata_JCP2022").replace(jcp_to_pert_type).alias(pert_type)
        )

    profiles = profiles.filter(pl.col(pert_type) != "null")
    if not poscons:
        profiles = profiles.with_columns(
            pl.when(pl.col(pert_type) != "negcon").then("trt").alias(pert_type)
        )
    return profiles


@cachier()
def pvals_from_path(path: str, *args, **kwargs):
    """
    Use the path to cache pvals
    Locally cached version of pvals. To clean cache run <function>.clean_cache().
    """
    profiles = pl.read_parquet(path)
    profiles = add_pert_type(profiles)
    return calculate_pvals(profiles, *args, **kwargs)


def correct_group_feature_pvals(
    corrected: pl.DataFrame,
) -> pl.DataFrame:
    """
    1. Group features based on their hierarchy and compute combined p-value per group using
    2. then correct the p values from step 5 (fdr_bh)

    # TODO double-check if the statistics work for features that originate from the same cell
    """

    # %% Group pvalues

    groups = get_feature_groups(corrected.select(pl.all().exclude("^Metadata.*$")))
    parsed = pl.concat((corrected.transpose(), groups), how="horizontal")
    agg = parsed.group_by(groups.columns).agg(pl.all())
    # TODO think of if/how to deal with features that come empty

    # Combine p values and fill nans
    print("Combine p values using parsed features")

    np_pvals = agg.drop(groups.columns).to_numpy()

    timer = perf_counter()
    with Pool() as p:
        fully_grouped_pvals = p.map(
            lambda x: np.nan_to_num(combine_pvalues(x).pvalue, nan=1.0),
            np_pvals.flatten(),
        )

    print(f"{perf_counter()-timer}")

    print("Perform the correction for grouped features")
    second_grouping_matrix = np.reshape(fully_grouped_pvals, np_pvals.shape)
    timer = perf_counter()
    with Pool() as p:
        second_correction = p.map(
            lambda x: multipletests(x, method="fdr_bh")[1],
            second_grouping_matrix.T,
        )
    print(f"{perf_counter()-timer}")
    corrected_p_value = pl.DataFrame(
        np.transpose(second_correction), schema=agg.columns[3:]
    )

    final = pl.concat((agg.select(groups.columns), corrected_p_value), how="horizontal")
    return final


@cachier
def get_grouped_corrected_pvals(
    profiles_path: str,
    *args,
    **kwargs,
):
    print("Calculating corrected p-values")
    print("Partition data into treatment and negative control")
    timer = perf_counter()
    corrected_pvals = pvals_from_path(profiles_path, *args, **kwargs)
    corrected_grouped_pvals = calculate_pvals(corrected_pvals)
    print(f"{perf_counter()-timer}")

    return corrected_grouped_pvals


# Autogenerates the parquet file if run from command line
if __name__ == "__main__":
    dir_path = Path("/dgx1nas1/storage/data/shared/morphmap_profiles/")
    precor_file = "full_profiles_cc_adj_mean_corr.parquet"
    precor_path = dir_path / "orf" / precor_file
    corrected_pvals = pvals_from_path(precor_path, overwrite=True)
