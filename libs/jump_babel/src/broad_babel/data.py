#!/usr/bin/env jupyter
"""
Convenience function to get JUMP data tables.

The hashes of these datasets are defined in this document.
"""

from functools import cache

import polars as pl
import pooch


@cache
def get_table(table_name: str) -> pl.DataFrame:
    """
    Fetch a table from broad_portrait based on the provided name.

    The function retrieves the corresponding metadata csv file,
    checks its hash against a known value for integrity, and
    returns the contents as a polars DataFrame.

    Parameters
    ----------
    table_name : str
        The name of the table to be retrieved (e.g., 'compound', 'well', etc.).

    Returns
    -------
    pl.DataFrame
        A polars DataFrame containing the contents of the requested table.

    """
    # Obtained from broad_portrait
    metadata_location = (
        "https://github.com/jump-cellpainting/datasets/raw/"
        "c68deb2babc83747e6b14d8a77e5655138a6086a/metadata/"
        "{}.csv.gz"
    )
    metafile_hash = {
        "compound": "03c63e62145f12d7ab253333b7285378989a2f426e7c40e03f92e39554f5d580",
        "well": "677d3c1386d967f10395e86117927b430dca33e4e35d9607efe3c5c47c186008",
        "crispr": "55e36e6802c6fc5f8e5d5258554368d64601f1847205e0fceb28a2c246c8d1ed",
        "orf": "9c7ec4b0fa460a3a30f270a15f11b5e85cef9dd105c8a0ab8ab50f6cc98894b8",
        "plate": "745391d930627474ec6e3083df8b5c108db30408c0d670cdabb3b79f66eaff48",
    }

    return pl.read_csv(
        pooch.retrieve(
            url=metadata_location.format(table_name),
            known_hash=metafile_hash[table_name],
        ),
        use_pyarrow=True,
    )
