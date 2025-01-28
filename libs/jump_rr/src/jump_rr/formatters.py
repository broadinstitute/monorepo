#!/usr/bin/env jupyter
"""Format strings to deal with nested URLs and HTML elements."""

import json
from collections.abc import Iterable
from functools import cache

import polars as pl


@cache
def get_url_label(key: str) -> tuple[str, str]:
    """
    Retrieve a URL template and label for a given url source (vendor).

    Parameters
    ----------
    key : str
        The identifier of the vendor (e.g., 'entrez', 'genecards', etc.).

    Returns
    -------
    tuple[str, str]
        A tuple containing the URL template and the label for the specified vendor.

    Notes
    -----
    The supported vendors are:
    - entrez: NCBI entry. Requires an Entrez Id
    - genecards: GeneCards entry. Requires a gene symbol.
    - omim: OMIM entry. Requires an OMIM id.
    - ensembl: Ensembl entry. Requires an Ensmbl id.
    - phenaid: Images from the Phenaid platform.

    Raises
    ------
    KeyError
        If the provided key is not a valid vendor identifier.

    """
    vendors = dict(
        entrez=("https://www.ncbi.nlm.nih.gov/gene/{}", "NCBI"),
        genecards=(
            "https://www.genecards.org/cgi-bin/carddisp.pl?gene={}",
            "GeneCards",
        ),
        omim=("https://www.omim.org/entry/{}", "OMIM"),
        ensembl=("https://useast.ensembl.org/Homo_sapiens/Gene/Splice?g={}", "Ensembl"),
        phenaid=(
            "https://phenaid.ardigen.com/static-jumpcpexplorer/images/{}/{}/{}_{}.jpg",
            None,
        ),
    )
    return vendors[key]

def build_dict(fmt: str, vendor: str, value: str or int or Iterable) -> dict[str, str]:
    """
    Construct a dictionary containing URL and label information.

    Parameters
    ----------
    fmt : str
        Format of the output dictionary (e.g., "href" or "img").
    vendor : str
        Vendor identifier.
    value : str or int or Iterable
        Value to be used in constructing the URL.

    Returns
    -------
    dict[str, str]
        Dictionary containing URL and label information.

    Notes
    -----
    The function uses the `get_url_label` function to obtain the URL template and label for the given vendor.

    """
    url_template, label = get_url_label(vendor)
    if isinstance(value, (str, int)):
        url = url_template.format(value)
    else:
        url = url_template.format(*value)
    match fmt:
        case "href":
            return {"href": url, "label": label}
        case "img":
            return {"img_src": url, "href": url, "width": 200}

@cache
def format_value(fmt: str, vendor: str, value: str or int or Iterable) -> str:
    """
    Format a given url according to a format and vendor of info (specific url).

    Parameters
    ----------
    fmt : str
        The format string.
    vendor : str
        The vendor name. See `get_url_label` for available vendors.
    value : str or int
        The value to be formatted.

    Returns
    -------
    html : str
        The formatted value as an HTML string.

    """
    d = build_dict(fmt, vendor, value)
    html = str(json.dumps(d))
    return html

def add_phenaid_url_col(
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
    profiles = profiles.with_columns(
        pl.concat_str(
            pl.col("Metadata_Source"),
            pl.col("Metadata_Plate"),
            pl.col("Metadata_Well"),
            separator="/",
        )
        .map_elements(lambda x: format_value("url", *x), return_dtype=pl.String)
        .alias(url_colname)
    )
    return profiles

def add_external_sites(df: pl.DataFrame or pl.LazyFrame, ext_links_col:str, key_source_mapper: tuple[str,str,dict[str,str]]) -> pl.DataFrame or pl.LazyFrame:
    """
    Add external site information to a given DataFrame.

    Parameters
    ----------
    df : polars.DataFrame or polars.LazyFrame
        Input DataFrame containing standard identifiers.
    ext_links_col : str
        Name of the column that will contain links to external sites.
    key_source_mapper : tuple[str, str, dict[str, str]]
        Tuple containing the key, source column, and a dictionary mapping
        identifiers to their corresponding external site URLs.

    Returns
    -------
    df : polars.DataFrame or polars.LazyFrame
        The input DataFrame with additional columns containing links to external sites.

    Notes
    -----
    The function uses a dictionary to map standard identifiers to their corresponding
    external site URLs. It then constructs the URLs by replacing the standard identifiers
    in the input DataFrame and aggregating them into a single column.

    """
    df = df.with_columns(
        [
            pl.col(source).replace_strict(mapper, default="").alias(key)
            for key, source, mapper in key_source_mapper
        ]
    )

    df = df.with_columns(
        ("[" + pl.concat_str(
            [
                pl.format(format_value("href", key, "{}"), pl.col(key))
                for key, _, _ in key_source_mapper
            ],
        separator=", "
        ) + "]").alias(ext_links_col),
    )
    return df
