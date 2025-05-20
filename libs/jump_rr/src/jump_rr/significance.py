"""
Generate aggregated statistics for the values of features.

Based on discussion https://github.com/broadinstitute/2023_12_JUMP_data_only_vignettes/issues/4#issuecomment-1918019212.

1. Calculate essential metrics for t-value using duckdb
2. Calculate the p value of all features
3. Correct the p values (fdr_bh)

Implementation details:
The rules of the game is to perform all the grouping and stats calculation with duckdb
Then we use cupy + dask for the broadcastable operations (though it may not be needed)
In theory this approach should work for any data size, as long as
the statistics array fits in memory (nprofiles, nfeatures*3)
If it does not then dask comes in and chunks it, though it will run more slowly

"""

from concurrent.futures import ThreadPoolExecutor

import dask.array as da
import duckdb
import numpy as np
import polars as pl
from broad_babel.query import get_mapper
from scipy.stats import t
from statsmodels.stats.multitest import multipletests

np.seterr(divide="ignore")


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


def pvals_from_profile(
    profile: pl.DataFrame or duckdb.duckdb.DuckDBPyRelation,
) -> da.Array:
    """
    Compute p-values for every feature in a given profile.

    Parameters
    ----------
    profile : object
        Input profile to compute p-values from.

    Returns
    -------
    corrected_p_values : array_like
        Array of p-values corrected for multiple testing using FDR.

    """
    metrics = get_metrics_for_ttest(profile)
    t_, df = t_from_metrics(metrics)
    # Here it is numpy again. If we can remain in dask there's speed to be gained
    # scipy.stats allows for broadcasting but not dask arrays

    # On the p value calculation:
    # If you only looked at the probability of the observed direction after seeing
    # the data (a practice called "post-hoc directionality"), you'd effectively be
    # performing a one-tailed test without the proper adjustment to your significance
    # threshold, which introduces bias.
    # The p value is thus 2*min(cdf,sf) for every t statistic
    cdf = t.cdf(t_, df)
    sf = t.sf(t_, df)
    p_value = np.minimum(sf, cdf) * 2

    corrected_p_values = correct_multitest_threaded(p_value)

    # Back to dask to find the significant values
    return da.asarray(corrected_p_values).T


def correct_multitest_threaded(p_values: np.ndarray) -> list[np.ndarray]:
    """
    Correct p-values for multiple testing using Benjamini-Hochberg FDR.

    Parameters
    ----------
    p_values : np.ndarray
        Array of p-values to be corrected.

    Returns
    -------
    corrected_p_values : list[np.ndarray]
        List of arrays containing the corrected p-values.

    """
    # Correct p values
    with ThreadPoolExecutor() as ex:
        corrected_p_values = list(
            ex.map(lambda x: multipletests(x, method="fdr_bh")[1], p_values)
        )

    return corrected_p_values


def get_metrics_for_ttest(df: duckdb.DuckDBPyRelation) -> duckdb.DuckDBPyRelation:
    """
    Calculate metrics for t-test from a given dataframe.

    Parameters
    ----------
    df : duckdb.DuckDBPyRelation
        Input dataframe containing metadata and profiles.

    Returns
    -------
    stats : duckdb.DuckDBPyRelation
        Dataframe with calculated metrics, including count, average, and variance.

    """
    duckdb.connect(":memory:")
    # Group the plates for any given perturbation (trt)
    plates_trt = duckdb.sql(
        "SELECT Metadata_JCP2022,list(DISTINCT Metadata_Plate) AS Metadata_plates"
        " FROM df WHERE Metadata_pert_type = 'trt'"
        " GROUP BY Metadata_JCP2022,Metadata_pert_type"
    )
    # Attach the profiles based on two conditions:
    # 1. The profile belongs to that perturbation (trt)
    # 2. The profile belongs to a negative control present in the same plate as trt
    merged = duckdb.sql(
        "SELECT A.Metadata_JCP2022 AS"
        " Metadata_JCP2022,B.Metadata_pert_type as Metadata_pert_type,"
        "COLUMNS(c->c NOT LIKE 'Metadata%') FROM plates_trt A"
        " JOIN df B on (list_contains(A.Metadata_plates, B.Metadata_Plate)"
        " AND A.Metadata_JCP2022 = B.Metadata_JCP2022)"
        " OR (B.Metadata_pert_type = 'negcon'"
        " AND list_contains(A.Metadata_plates, B.Metadata_Plate))"
    )

    # Generate COLUMNS expressions to ignore metadata columns
    stats_str = ",".join([
        metric
        + "(COLUMNS(c -> c NOT LIKE 'Metadata%')) AS "
        + metric.split("_")[0]
        + "_col"
        for metric in ("count", "avg", "var_samp")
    ])
    # Calculate the metrics
    # This table is split in six sections: three on columns and two on rows:
    # The left-right halves are controls or perturbations (because 'negcon' < 'trt')
    # The top-bottom splits are counts, average and variance (as sorted above)
    stats = duckdb.sql(
        f"SELECT Metadata_JCP2022,Metadata_pert_type,{stats_str}"
        " FROM merged GROUP BY Metadata_JCP2022,Metadata_pert_type"
        " ORDER BY Metadata_pert_type,Metadata_JCP2022"
    )

    return stats


def t_from_metrics(
    metrics: duckdb.duckdb.DuckDBPyRelation,
) -> duckdb.duckdb.DuckDBPyRelation:
    """
    Compute the t statistic from the mean, count and variance of two distributions.

    Parameters
    ----------
    metrics : duckdb.duckdb.DuckDBPyRelation
        A DuckDB table containing the mean, count and variance of two distributions.

    Returns
    -------
    df_ : numpy.ndarray
        The degrees of freedom for p value calculations.
    t : numpy.ndarray
        The computed t statistic.

    """
    # Convert the resulting table (minus the first two columns)
    # into a numpy and then dask matrix with dimensions (3*nfeatures, 2*ntrts)
    # Here we use broadcasting to implement the t student calculation
    stats = da.asarray(
        tuple(x for k, x in metrics.fetchnumpy().items() if not k.startswith("Meta")),
        # dtype=da.float32, # It doesn't work
        dtype=da.float64,
    )

    # Slices makes isolating metrics and treatment blocks simpler
    mt, trt = stats.shape
    mt = int(mt / 3)
    trt = int(trt / 2)
    n = slice(0, mt)
    m = slice(mt, mt * 2)
    v = slice(mt * 2, mt * 3)

    # Assign the blocks into variables so the equations are clear later on
    (n2, m2, v2), (n1, m1, v1) = [
        [stats[x, y] for x in (n, m, v)] for y in (slice(0, trt), slice(trt, trt * 2))
    ]

    t, df = t_from_stats(n1, m1, v1, n2, m2, v2)

    # Return also the df for p value calculations
    return t, df


def t_from_stats(
    n1: da.Array, m1: da.Array, v1: da.Array, n2: da.Array, m2: da.Array, v2: da.Array
) -> tuple[da.Array, da.Array]:
    """
    Calculate degrees of freedom and t-statistic for two sample comparison.

    Parameters
    ----------
    n1 : da.Array
        Sample size of the first group.
    m1 : da.Array
        Mean of the first group.
    v1 : da.Array
        Variance of the first group.
    n2 : da.Array
        Sample size of the second group.
    m2 : da.Array
        Mean of the second group.
    v2 : da.Array
        Variance of the second group.

    Returns
    -------
    df : da.Array
        Degrees of freedom for the t-test.
    t : da.Array
        T-statistic value.

    """
    df = n1 + n2 - 2
    # pooled variance
    sv = ((n1 - 1) * v1 + (n2 - 1) * v2) / df
    denom = da.sqrt(sv * (1 / n1 + 1 / n2))
    t = (m1 - m2) / denom
    return t, df
