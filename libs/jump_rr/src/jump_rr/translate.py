#!/usr/bin/env jupyter
"""Generate mapper to translate standard keys to Entrez IDs."""

import polars as pl
from broad_babel.query import run_query
from jump_rr.formatters import format_val


def get_mapper(
    ids: tuple[str],
    plate_type: str,
    input_col: str = "JCP2022",
    output_cols: tuple[str] = ("standard_key", "NCBI_Gene_ID"),
    format_output: bool = True,
) -> dict:
    """
    Generate translators based on an identifier using broad-babel.

    Parameters
    ----------
    ids : tuple[str]
        A tuple of identifiers.
    plate_type : str
        The type of plate (crispr, orf or compound).
    input_col : str, optional
        The name of the input column (default is "JCP2022").
    output_cols : list[str], optional
        A list of names for the output columns (default is ["standard_key", "NCBI_Gene_ID"]).
    format_output : bool, optional
        Whether to format the output to link to external ids, such as NCBI/Entrez ids (default is True).

    Returns
    -------
    dict
        A dictionary containing the mappers.

    """
    mapper_values = run_query(
        query=ids,
        input_column=input_col,
        output_columns=",".join((input_col, *output_cols)),
        predicate=f"AND plate_type = '{plate_type}'",
    )

    mappers = {k: {} for k in output_cols}
    for input_id, *output_ids in mapper_values:
        for k, new_id in zip(mappers.keys(), output_ids):
            if format_output:
                new_id = (
                    format_val("external", new_id) if k == "NCBI_Gene_ID" else new_id
                )
            mappers[k][input_id] = new_id
    return list(mappers.values())

def get_external_mappers(profiles: pl.DataFrame, col: str, dset:str) -> tuple[dict[str, str]]:
    """
    Generate external mappers for a given column of the provided DataFrame.

    The mappers link JCP ids to gene names/InChiKeys, urls of external ids and
    the raw external id.

    Parameters
    ----------
    profiles : pl.DataFrame
        Input dataframe containing profiles.
    col : str
        Column name to generate mappers for.
    dset : str
        Dataset type for which to generate mapper (crispr, orf or compound).

    Returns
    -------
    jcp_std_mapper : dict[str, str]
        Standard mapper for JCP values to Gene Names or InChiKeys.
    jcp_external_mapper : dict[str, str]
        External mapper for JCP values to a formatted URL of the NCBI id.
    jcp_external_raw_mapper : dict[str, str]
        Raw external mapper for JCP values to the numeric NCBI id.

    Notes
    -----
    `dset` is used to avoid uncertainty because crispr and orf share some gene names.

    """
    uniq = tuple(profiles.get_column(col).unique())
    jcp_std_mapper, jcp_external_mapper = get_mapper(uniq, dset)
    _, jcp_external_raw_mapper = get_mapper(uniq, dset, format_output=False)


    assert len(jcp_std_mapper), f"No mappers were found {col=}, {dset=}"
    return jcp_std_mapper, jcp_external_mapper, jcp_external_raw_mapper
