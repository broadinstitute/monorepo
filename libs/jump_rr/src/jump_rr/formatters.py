#!/usr/bin/env jupyter
"""Format strings to deal with nested URLs and HTML elements."""

from functools import cache

import polars as pl


@cache
def get_formatter(kind: str) -> str:
    """
    Return a formatter string based on the given kind.

    Parameters
    ----------
    kind : str
        The type of formatter to return. Options are 'external', 'url', 'img',
        'external_flat', 'url_flat', and 'img_flat'.

    Returns
    -------
    str
        A formatter string corresponding to the given kind.

    Notes
    -----
    The available formatters are:
    - external: NCBI gene id
    - url: URL of the image where the field of view space is double-nested ({{}}).
    - img: href of the image surrounded by double nesting ({{}}).
    - external_flat: Raw href of the ncbi id.
    - url_flat: Raw URL of the image.
    - img_flat: href with no nesting.

    Raises
    ------
    KeyError
        If the given kind is not one of the available formatters.

    """
    formatters = dict(
        external='{{"href": "https://www.ncbi.nlm.nih.gov/gene/{}", "label":"NCBI"}}',
        url='"https://phenaid.ardigen.com/static-jumpcpexplorer/images/{}_{{}}.jpg"',
        img='{{"img_src": {}, "href": {}, "width": 200}}',
        external_flat='{"href": "https://www.ncbi.nlm.nih.gov/gene/{}", "label":"NCBI"}',
        url_flat='"https://phenaid.ardigen.com/static-jumpcpexplorer/images/{}/{}/{}_{}.jpg"',
        img_flat='{"img_src": {}, "href": {}, "width": 200}',
    )
    return formatters[kind]


def format_val(kind: str, input_value: str or int or list or None) -> str:
    """
    Apply html formatting for Datasette hyperlinks and visualisation.

    Parameters
    ----------
    kind : str
        The type of formatting to apply.
    input_value : str or int or list or None
        The value to be formatted. Can be a string, integer, list or None.

    Returns
    -------
    str
        The formatted value as a string.

    Notes
    -----
    If input_value is None, an empty string is returned.
    If input_value is not a list, it is converted to a list before formatting.

    """
    if input_value is None:
        return ""
    elif isinstance(input_value, str) or isinstance(input_value, int):
        input_value = [input_value]

    result = get_formatter(kind).format(*input_value)

    return result


def add_url_col(
    profiles: pl.DataFrame, url_colname: str = "Metadata_image"
) -> pl.DataFrame:
    """
    Add an url column to profiles DataFrame.

    Parameters
    ----------
    profiles : pl.DataFrame
        input profilesiles DataFrame containing 'Metadata_Source', 'Metadata_Plate'
        and 'Metadata_Well'
    url_colname : str
        Name for new column. It must contain the 'Metadata' prefix.

    Returns
    -------
    profiles:pl.DataFrame
        DataFrame with new column added.

    """
    # assert url_colname.startswith(
    #     "Metadata"
    # ), "New URL column must start with 'Metadata'"

    profiles = profiles.with_columns(
        pl.concat_str(
            pl.col("Metadata_Source"),
            pl.col("Metadata_Plate"),
            pl.col("Metadata_Well"),
            separator="/",
        )
        .map_elements(lambda x: format_val("url", x), return_dtype=pl.String)
        .alias(url_colname)
    )
    return profiles
