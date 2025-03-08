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
Generate aggregated statistics for the values of features.

Based on discussion https://github.com/broadinstitute/2023_12_JUMP_data_only_vignettes/issues/4#issuecomment-1918019212.

1. Calculate the p value of all features
2. then adjust the p value to account for multiple testing https://www.statsmodels.org/dev/generated/statsmodels.stats.multitest.multipletests.html (fdr_bh)
3. Group features based on their hierarchy and compute combined p-value per group using https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.combine_pvalues.html (fisher); this will give you a p-value per group
4. then correct the p values from step 5 (fdr_bh)
"""

from collections.abc import Iterable
from time import perf_counter

import numpy as np
import polars as pl
import polars.selectors as cs
from broad_babel.query import get_mapper
from cachier import cachier
from pathos.multiprocessing import Pool
from scipy.stats import mannwhitneyu
from statsmodels.stats.multitest import multipletests
from tqdm import tqdm

try:
    pass
except Exception:
    pass


np.seterr(divide="ignore")


@cachier()
def partition_parquet_by_trt(
    path: str,
    dataset: str,
    column: str = "Metadata_JCP2022",
    negcons_per_plate: int = 2,
    seed: int = 42,
) -> dict[str, tuple[pl.DataFrame, pl.DataFrame]]:
    """
    Partitions a Parquet file by treatment.

    Parameters
    ----------
    path : str
        Path to the Parquet file.
    dataset : str
        Name of the dataset.
    column : str, optional
        Column name for treatment information (default is "Metadata_JCP2022").
    negcons_per_plate : int, optional
        Number of negative controls per plate (default is 2).
    seed : int, optional
        Random seed for reproducibility (default is 42).

    Returns
    -------
    dict[str, tuple[pl.DataFrame, pl.DataFrame]]
        Dictionary with treatment as key and a tuple of DataFrames as value.

    """
    profiles = pl.read_parquet(path)
    profiles = add_pert_type(profiles, dataset=dataset)
    return partition_by_trt(profiles, dataset, column, negcons_per_plate, seed)


def partition_by_trt(
    df: pl.DataFrame,
    dataset: str,
    column: str = "Metadata_JCP2022",
    negcons_per_plate: int = 2,
    seed: int = 42,
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """
    Partition a dataframe by using the identifier column.

    Parameters
    ----------
    df : pl.DataFrame
        Input dataframe to be partitioned.
    dataset : str
        Name of the dataset.
    column : str, optional
        Column name used for partitioning (default is "Metadata_JCP2022").
    negcons_per_plate : int, optional
        Number of negative controls to sample per plate (default is 2).
    seed : int, optional
        Random seed for shuffling (default is 42).

    Returns
    -------
    dict[str, tuple[np.ndarray, np.ndarray]]
        A dictionary where each key is an identifier and the value is a tuple
        containing the treatment profile as a numpy array and the negative control
        profiles as a numpy array.

    """
    meta_cols = (column, "Metadata_pert_type", "Metadata_Plate")
    partitions = {
        k[0]: v
        for k, v in df.select(
            pl.col(meta_cols),
            pl.all().exclude("^Metadata.*$").cast(pl.Float32),
        )
        .partition_by("Metadata_pert_type", include_key=False, as_dict=True)
        .items()
    }

    partitions["negcon"] = partitions["negcon"].drop(column)
    if negcons_per_plate:  # Sample $negcons_per_plate elements from each plate
        partitions["negcon"] = partitions["negcon"].filter(
            pl.int_range(0, pl.count()).shuffle(seed=seed).over("Metadata_Plate")
            < negcons_per_plate
        )

    ids_plates = dict(
        partitions["trt"].group_by(column).agg("Metadata_Plate").iter_rows()
    )

    ids_prof = {
        k[0]: v
        for k, v in partitions["trt"]
        .drop("Metadata_Plate")
        .partition_by(column, include_key=False, as_dict=True)
        .items()
    }

    # TODO is there a better way to return only float values?
    id_trt_negcon = {
        id_: (
            ids_prof[id_].to_numpy(),
            partitions["negcon"]
            .filter(pl.col("Metadata_Plate").is_in(plates))
            .select(cs.by_dtype(pl.Float32))
            .to_numpy(),
        )
        for id_, plates in ids_plates.items()
    }
    return id_trt_negcon


def get_pvalue_mwu(a: np.ndarray, b: np.ndarray, axis: int = 0) -> float:
    """
    Calculate the p-value using the Mann-Whitney U test.

    This function is a wrapper around scipy.stats.mannwhitneyu and returns
    the p-value of the two-sample Mann-Whitney rank test on the provided input arrays.

    Parameters
    ----------
    a : np.ndarray
        Input array 1.
    b : np.ndarray
        Input array 2.
    axis : int, optional
        Axis over which to compute the statistic. By default, the statistic is
        computed over all the values given (axis=0).

    Returns
    -------
    pvalue : float
        The p-value of the two-sample Mann-Whitney rank test.

    Notes
    -----
    This function assumes that the input arrays are not empty and contain at least one element.

    """
    return mannwhitneyu(a, b, axis=axis).pvalue


def calculate_pvals(
    partitioned: dict[str, tuple[np.ndarray, np.ndarray]],
) -> tuple[tuple[str], pl.DataFrame]:
    """
    Calculate the pvalues of each feature against a sample of their negative controls.

    1. Calculate the p value of all features
    2. then adjust the p value to account for multiple testing.
    """
    # Remove perturbations that have an excessive number of entries (usually controls/errors)
    partitioned = {
        k: v for k, v in partitioned.items() if len(v[0]) < 50 and len(v[1]) < 50
    }
    print("Calculating and adjusting p values")
    timer = perf_counter()
    if False:  # Unthreaded by default
        timer = perf_counter()
        with Pool() as p:
            corrected = p.map(
                lambda x: multipletests(get_pvalue_mwu(*x), method="fdr_bh")[1],
                partitioned.values(),
            )
        print(f"Threaded: {perf_counter() - timer}")
    else:
        timer = perf_counter()
        corrected = [
            multipletests(get_pvalue_mwu(a, b), method="fdr_bh")[1]
            for a, b in tqdm(partitioned.values())
        ]
        print(f"Linear: {perf_counter() - timer}")

    return (tuple(partitioned.keys()), corrected)


def add_pert_type(
    profiles: pl.DataFrame, dataset: str, poscons: bool = False
) -> pl.DataFrame:
    """
    Add metadata with perturbation type from the JCP2022 identifier.

    Parameters
    ----------
    profiles : pl.DataFrame
        Input DataFrame containing metadata.
    dataset : str
        Name of the dataset to use for mapping (crispr, orf or compound).
    poscons : bool, optional
        Ensure all outputs are 'trt' or 'negcon'. Drop nulls. Defaults to False.

    Returns
    -------
    pl.DataFrame
        Updated DataFrame with perturbation type metadata.

    Notes
    -----
    If "Metadata_pert_type" is not present in the input profiles, it will be added.

    """
    pert_type = "Metadata_pert_type"
    if "Metadata_pert_type" not in profiles.select(pl.col("^Metadata.*$")).columns:
        # Add perturbation type metadata (new profiles exclude it)
        jcp_to_pert_type = get_mapper(
            dataset,
            input_column="plate_type",
            output_columns="JCP2022,pert_type",
        )

        profiles = profiles.with_columns(
            pl.col("Metadata_JCP2022").replace(jcp_to_pert_type).alias(pert_type)
        )

    profiles = profiles.filter(pl.col(pert_type) != "null")
    if not poscons:
        profiles = profiles.with_columns(
            pl.when(pl.col(pert_type) != "negcon")
            .then(pl.lit("trt"))
            .otherwise(pl.lit("negcon"))
            .alias(pert_type)
        )
    return profiles


@cachier()
def pvals_from_path(
    path: str, dataset: str, *args: Iterable, **kwargs: dict
) -> pl.DataFrame:
    """
    Calculate p-values from the path of a set of profiles.

    Calculate p values from a profiles file to cache p-values.
    To clean cache run `clean_cache()` function.

    Parameters
    ----------
    path : str
        Path to the profiles parquet file.
    dataset : str
        Name of the dataset (orf, crispr or compound).
    *args
        Additional positional arguments passed to `calculate_pvals` function.
    **kwargs
        Additional keyword arguments passed to `calculate_pvals` function.

    Returns
    -------
    pl.DataFrame
        DataFrame containing p-values with added metadata column 'Metadata_JCP2022'.

    Notes
    -----
    This function uses local caching for efficient computation of p-values.

    """
    timer = perf_counter()
    partitioned = partition_parquet_by_trt(path, dataset)
    print(f"Partitioning took {perf_counter() - timer}")

    ids, pvals = calculate_pvals(partitioned, *args, **kwargs)
    return pl.DataFrame(
        pvals,
        schema={
            k: pl.Float32
            for k in pl.scan_parquet(path).select(pl.exclude("^Metadata.*$")).columns
        },
    ).with_columns(Metadata_JCP2022=pl.Series(ids))
