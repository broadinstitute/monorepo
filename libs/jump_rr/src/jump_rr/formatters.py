#!/usr/bin/env jupyter

from functools import cache

import polars as pl


@cache
def get_formatter(kind: str) -> str:
    formatters = dict(
        external='{{"href": "https://www.ncbi.nlm.nih.gov/gene/{}", "label":"External"}}',
        url='"https://phenaid.ardigen.com/static-jumpcpexplorer/' 'images/{}_{{}}.jpg"',
        img='{{"img_src": {}, "href": {}, "width": 200}}',
        external_flat='{"href": "https://www.ncbi.nlm.nih.gov/gene/{}", "label":"External"}',
        url_flat='"https://phenaid.ardigen.com/static-jumpcpexplorer/'
        'images/{}/{}/{}_{}.jpg"',
        img_flat='{"img_src": {}, "href": {}, "width": 200}',
    )
    return formatters[kind]


def format_val(kind: str, input_value: str or int or list):
    # Apply html formating for Datasette hyperlinks and visualisation
    if isinstance(input_value, str) or isinstance(input_value, int):
        input_value = [input_value]

    return get_formatter(kind).format(*input_value)


def add_url_col(
    prof: pl.DataFrame, url_colname: str = "Metadata_image"
) -> pl.DataFrame:
    """
    Add url column to profiles DataFrame.

    Parameters
    ----------
    prof : pl.DataFrame
        input profiles DataFrame containing 'Metadata_Source', 'Metadata_Plate'
        and 'Metadata_Well'
    url_colname : str
        Name for new column. It must contain the 'Metadata' prefix.

    Returns
    -------
    prof:pl.DataFrame
        DataFrame with new column added.

    Examples
    --------
    FIXME: Add docs.

    """
    assert url_colname.startswith(
        "Metadata"
    ), "New URL column must start with 'Metadata'"

    prof = prof.with_columns(
        pl.concat_str(
            pl.col("Metadata_Source"),
            pl.col("Metadata_Plate"),
            pl.col("Metadata_Well"),
            separator="/",
        )
        .map_elements(lambda x: format_val("url", x))
        .alias(url_colname)
    )
    return prof
