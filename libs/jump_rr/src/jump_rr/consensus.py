#!/usr/bin/env jupyter
"""Functions to group multiple wells."""


import polars as pl
from jump_rr.formatters import format_value
from jump_rr.parse_features import get_feature_groups


def get_consensus_meta_urls(profiles: pl.DataFrame, col:str) -> tuple:
    """
    Compute aggregated median values and metadata with urls for a given dataframe.

    Parameters
    ----------
    profiles : pl.DataFrame
        Input dataframe containing profile information.
    col : str
        Name of the column to group by.

    Returns
    -------
    med : pl.DataFrame
        Dataframe containing aggregated median values.
    meta : pl.DataFrame
        Dataframe containing metadata composed of cycling iterators for grouped contents during consensus.

    """
    # profiles = add_phenaid_url_col(profiles, url_colname=url_colname)

    grouped = profiles.group_by(col, maintain_order=True)
    med = grouped.median()
    meta = grouped.agg(pl.col("^Metadata_.*$"))

    for srs in meta.iter_columns():
        med.replace_column(med.columns.index(srs.name), srs)

    return med, meta


def get_group_median(
    med: pl.DataFrame, group_by: list[str] or None = None
) -> pl.DataFrame:
    """
    Calculate the median of a set of features grouped by their metadata.

    Parameters
    ----------
    med : pl.DataFrame
        The input DataFrame containing the feature values and metadata.
    group_by : list[str] or None, optional
        A list of column names to group the features by. If None, the
        `get_feature_groups` is used to assign groups (default is None).

    Returns
    -------
    pl.DataFrame
        A DataFrame with the median value for each group.

    Notes
    -----
    The function first selects all columns that do not start with "Metadata.".
    Then it concatenates these values horizontally with their respective metadata.
    Finally, it groups these features by their metadata and calculates the median
    of each group.

    """
    med_vals = med.select(pl.exclude("^Metadata.*$"))
    if group_by is None:
        feature_meta = get_feature_groups(tuple(med_vals.columns))
    else:
        feature_meta = pl.DataFrame(group_by)
    features = pl.concat((feature_meta, med_vals.transpose()), how="horizontal")

    grouped = features.group_by(feature_meta.columns, maintain_order=True)

    return grouped.median()

def get_range(dataset: str) -> range:
    """
    Generate a range of indices based on the dataset.

    Parameters
    ----------
    dataset : str
        The type of dataset. It can be 'crispr', 'orf', or 'compound'.

    Returns
    -------
    rng : range
        A range object representing the cycle of indices for the given dataset.

    Notes
    -----
    The number of images per well in the data is as follows:
    - crispr: 9 (0-8)
    - orf: 9 (1-9)
    - compound: 7 ()

    """
    offset = dataset != "crispr"
    max_offset = (dataset == "compound") * (-3)
    rng = range(offset, 9 + offset + max_offset)
    return rng
def add_sample_images(df: pl.DataFrame, meta_df: pl.DataFrame, rng: range, col_outname: str, left_col: str = "JCP2022", right_col: str = "Metadata_JCP2022", sorter_col: str = "modulo", seed: int = 2) -> pl.DataFrame:
    """
    Add sample images to a Polars DataFrame.

    This function takes in two DataFrames, `df` and `meta_df`, as well as a range object `rng`. It joins the two DataFrames based on
    the columns specified by `left_col` and `right_col`, then samples the resulting DataFrame. The sampled DataFrame is then
    grouped by the columns specified by `left_col` and `sorter_col`, and the first row of each group is selected.

    Parameters
    ----------
    df : pl.DataFrame
        The input DataFrame.
    meta_df : pl.DataFrame
        The metadata DataFrame to join with the input DataFrame.
    rng : range
        A range object used to generate sample site values.
    col_outname : str
        The name of the output column.
    left_col : str, optional
        The column in `df` to use for joining with `meta_df`. Defaults to "JCP2022".
    right_col : str, optional
        The column in `meta_df` to use for joining with `df`. Defaults to "Metadata_JCP2022".
    sorter_col : str, optional
        The column to use for sorting the sampled DataFrame. Defaults to "modulo".
    seed : int, optional
        The seed to use for shuffling the DataFrame. Defaults to 2.

    Returns
    -------
    pl.DataFrame
        The resulting DataFrame with sample images added.

    """
    df = df.with_columns(modulo=pl.int_range(pl.len()).over(left_col))
    df = df.join_where(meta_df, pl.col(left_col) == pl.col(right_col))
    df = df.sample(fraction=1.0, shuffle=True, seed=seed).group_by((left_col, sorter_col), maintain_order=True).first()
    df = df.with_columns(sample_site=pl.col(sorter_col) % max(rng) + min(rng))
    df = df.with_columns(pl.format(
        format_value("img", "phenaid", tuple("{}" for _ in range(8))),
        *[pl.col(x) for _ in range(2) for x in ("Metadata_Source", "Metadata_Plate", "Metadata_Well", "sample_site")],
    ).alias(col_outname))
    return df
