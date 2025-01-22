#!/usr/bin/env jupyter
"""Format strings to deal with nested URLs and HTML elements."""

import json
from collections.abc import Iterable
from functools import cache

import polars as pl


@cache
def get_url_label(key: str) -> tuple[str, str]:
    vendors = dict(
        entrez=("https://www.ncbi.nlm.nih.gov/gene/{}", "NCBI"),
        genecards=(
            "https://www.genecards.org/cgi-bin/carddisp.pl?gene={}",
            "GeneCards",
        ),
        omim=("https://www.omim.org/entry/{}", "OMIM"),
        ensembl=("https://useast.ensembl.org/Homo_sapiens/Gene/Splice?g={}", "Ensembl"),
        # ugb="USCB Genome Browser",
        # url='"https://phenaid.ardigen.com/static-jumpcpexplorer/images/{}_{{}}.jpg"',
        phenaid=(
            "https://phenaid.ardigen.com/static-jumpcpexplorer/images/{}/{}/{}_{}.jpg",
            None,
        ),
    )
    return vendors[key]


def build_dict(fmt: str, vendor: str, value: str or int or Iterable) -> dict[str, str]:
    url_template, label = get_url_label(vendor)
    if isinstance(value, (str, int)):
        url = url_template.format(value)
    else:
        url = url_template.format(*value)
    match fmt:
        case "href":
            return {"href": url, "label": label}
        case "img":
            return {"img": url, "href": url, "width": 200}


@cache
def format_value(fmt: str, vendor: str, value: str or int):
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
