#!/usr/bin/env jupyter
"""Tools to fetch replicability information from existing databases, and to recalculate it efficiently when necessary."""

import polars as pl
from cachier import cachier


def match_jcp(jcp: str) -> str:
    """Check the 8th character in a JCP id to fetch its corresponding dataframe"""
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
def df_from_jcp(jcp: str) -> pl.DataFrame:
    filename = match_jcp(jcp)
    base_url = "https://github.com/jump-cellpainting/2024_Chandrasekaran_Morphmap/raw/c47ad6c953d70eb9e6c9b671c5fe6b2c82600cfc/03.retrieve-annotations/output/{}"
    url = base_url.format(filename)

    return pl.read_csv(url)


def add_replicability(
    profiles: pl.DataFrame,
    left_on: str,
    right_on: str = "Metadata_JCP2022",
    replicability_col: str = "Phenotypic activity",
    **kwargs,
) -> pl.DataFrame:
    """
    Return the dataframe with a column indicating replicability. This is fetched from publicly available datasets.
    Note that this function seems to provide a distinct number of values for ORF with respect to CRISPR. This pa
    probably means that there are some missing entries that are being dropped when merging tables..
    """
    jcps = profiles.get_column(left_on)
    data = df_from_jcp(jcps[0]).rename({"corrected_p_value": replicability_col})

    return profiles.join(
        data.select(pl.col(right_on), pl.col(replicability_col)),
        how="left",
        left_on=left_on,
        right_on=right_on,
        **kwargs,
    )


#
