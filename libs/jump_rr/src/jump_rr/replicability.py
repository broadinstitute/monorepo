#!/usr/bin/env jupyter
"""Fetch replicability information from existing databases or recalculate it."""

import polars as pl
from cachier import cachier


def match_jcp(jcp: str) -> str:
    """
    Use the 8th character in a JCP id to fetch its corresponding dataframe.

    Parameters
    ----------
    jcp : str
        The JCP id to check.

    Returns
    -------
    str
        The filename of the corresponding dataframe.

    Raises
    ------
    Exception
        If the JCP id is invalid or compound replicability has not been precomputed.

    """
    match jcp[8]:
        case "8" | "crispr":
            return "phenotypic-activity-wellpos_cc_var_mad_outlier_featselect_sphering_harmony_PCA_corrected.csv.gz"
        case "9" | "orf":
            return "phenotypic-activity-wellpos_cc_var_mad_outlier_featselect_sphering_harmony.csv.gz"
        case "0" | "compound":
            raise Exception("Compound replicability not precomputed")
        case _:
            raise Exception("Invalid JCP")

@cachier()
def df_from_jcp(jcp: str) -> pl.LazyFrame:
    """
    Retrieve a DataFrame from a given JCP.

    Parameters
    ----------
    jcp : str
        The JCP id for which to retrieve the DataFrame.

    Returns
    -------
    pl.DataFrame or pl.LazyFrame
        A Polars DataFrame containing the data for the given JCP.

    """
    filename = match_jcp(jcp)
    base_url = "https://github.com/jump-cellpainting/2024_Chandrasekaran_Morphmap/raw/c47ad6c953d70eb9e6c9b671c5fe6b2c82600cfc/03.retrieve-annotations/output/{}"
    url = base_url.format(filename)

    return pl.scan_csv(url)


def add_replicability(
    profiles: pl.DataFrame,
    left_on: str,
    right_on: str = "Metadata_JCP2022",
    cols_to_add: dict = {
        "Phenotypic activity": "Phenotypic activity",
        "corrected_p_value": " Corrected p-value",
    },
    **kwargs: dict,
) -> pl.DataFrame or pl.LazyFrame:
    """
    Add a column indicating replicability to the input DataFrame.

    This function fetches replicability data from publicly available datasets.
    Note that this function may provide a distinct number of values for ORF with respect to CRISPR,
    probably due to missing entries being dropped when merging tables.

    Parameters
    ----------
    profiles : pl.DataFrame
        Input DataFrame containing the data to be enriched with replicability information.
    left_on : str
        Column name in the input DataFrame used for joining with the replicability data.
    right_on : str, optional
        Column name in the replicability data used for joining (default is "Metadata_JCP2022").
    cols_to_add : dict[str,str], optional
         Names and final names of the columns to pull from external replicability datasets
         (default is  {"Phenotypic activity": "Phenotypic activity",
          "corrected_p_value":"Corrected p-value"}).
    **kwargs
        Additional keyword arguments passed to the join operation.

    Returns
    -------
    pl.DataFrame
        The input DataFrame with an additional column indicating replicability.

    """
    jcp_sample = profiles.select(pl.col(left_on)).head(1)
    if hasattr(jcp_sample, "collect"):
        jcp_sample = jcp_sample.collect()
    data = df_from_jcp(jcp_sample[0,0]).rename(cols_to_add)

    if isinstance(profiles, pl.DataFrame):
        data = data.collect()
    return profiles.join(
        data.select(pl.col(right_on), pl.col(cols_to_add.values())),
        how="left",
        left_on=left_on,
        right_on=right_on,
        **kwargs,
    )
