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

import dask
import dask.array as da
import duckdb
import numpy as np
import polars as pl
import polars.selectors as cs
from broad_babel.query import get_mapper
from pathos.multiprocessing import Pool
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
    con = duckdb.connect(":memory:")
    # Group the plates for any given perturbation (trt)
    plates_trt = duckdb.sql(
        (
            "SELECT Metadata_JCP2022,list(DISTINCT Metadata_Plate) AS Metadata_plates"
            " FROM df WHERE Metadata_pert_type = 'trt'"
            " GROUP BY Metadata_JCP2022,Metadata_pert_type"
        )
    )
    # Attach the profiles based on two conditions:
    # 1. The profile belongs to that perturbation (trt)
    # 2. The profile belongs to a negative control present in the same plate as trt
    merged = duckdb.sql(
        (
            "SELECT A.Metadata_JCP2022 AS"
            " Metadata_JCP2022,B.Metadata_pert_type as Metadata_pert_type,"
            "COLUMNS(c->c NOT LIKE 'Metadata%') FROM plates_trt A"
            " JOIN df B on (list_contains(A.Metadata_plates, B.Metadata_Plate)"
            " AND A.Metadata_JCP2022 = B.Metadata_JCP2022)"
            " OR (B.Metadata_pert_type = 'negcon'"
            " AND list_contains(A.Metadata_plates, B.Metadata_Plate))"
        )
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
        (
            f"SELECT Metadata_JCP2022,Metadata_pert_type,{stats_str}"
            " FROM merged GROUP BY Metadata_JCP2022,Metadata_pert_type"
            " ORDER BY Metadata_pert_type,Metadata_JCP2022"
        )
    )

    return stats


def t_from_metrics(
    metrics: duckdb.duckdb.DuckDBPyRelation,
) -> duckdb.duckdb.DuckDBPyRelation:
    """
    Compute the t statistic from the average, count and variance of two distributions.

        Reference: https://stats.libretexts.org/Workbench/PSYC_2200%3A_Elementary_Statistics_for_Behavioral_and_Social_Science_(Oja)_WITHOUT_UNITS/09%3A_Independent_Samples_t-test/9.02%3A_Independent_Samples_t-test_Equation
    """
    # Convert the resulting table (minus the first two columns)
    # into a numpy and then dask matrix withdimensions (3*nfeatures, 2*ntrts)
    # Here we use broadcasting to implement the t student calculation
    with dask.config.set({"array.backend": "cupy"}):  # Dask should use cupy
        # M = da.asarray(tuple(x for k,x in stats.fetchnumpy().items() if not k.startswith("Meta")), dtype=da.float32)
        M = da.asarray(
            tuple(
                x for k, x in metrics.fetchnumpy().items() if not k.startswith("Meta")
            ),
            dtype=da.float32,
        )

        # Slices makes isolating metrics and treatment blocks simpler
        mt, trt = M.shape
        mt = int(mt / 3)
        trt = int(trt / 2)
        n = slice(0, mt)
        avg = slice(mt, mt * 2)
        var = slice(mt * 2, mt * 3)

        # Assign the blocks into variables so the equations are clear later on
        (n2, avg2, var2), (n1, avg1, var1) = [
            [M[x, y] for x in (n, avg, var)]
            for y in (slice(0, trt), slice(trt, trt * 2))
        ]

        df = n1 + n2 - 2
        # pooled variance
        svar = ((n1 - 1) * var1 + (n2 - 1) * var2) / df
        denom = da.sqrt(svar * (1 / n1 + 1 / n2))
        t_ = (avg1 - avg2) / denom

    t = t_.compute()
    df_ = df.astype(int).compute()
    # Return also the df for p value calculations
    return df_, t


def pvals_from_profile(profile):
    """
    Compute p-values from a given profile.

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
    df, t_values = t_from_metrics(metrics)
    p_values = t.cdf(t_values, df)

    # Correct p values
    with Pool() as p:
        corrected_p_values = p.map(
            lambda x: multipletests(x, method="fdr_bh")[1], p_values
        )

    return corrected_p_values
