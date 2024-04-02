#!/usr/bin/env jupyter
from functools import cache

import polars as pl
import pooch


@cache
def get_table(table_name: str) -> pl.DataFrame:
    # Obtained from broad_portrait
    METADATA_LOCATION = (
        "https://github.com/jump-cellpainting/datasets/raw/"
        "baacb8be98cfa4b5a03b627b8cd005de9f5c2e70/metadata/"
        "{}.csv.gz"
    )
    METAFILE_HASH = {
        "compound": "a6e18f8728ab018bd03fe83e845b6c623027c3baf211e7b27fc0287400a33052",
        "well": "677d3c1386d967f10395e86117927b430dca33e4e35d9607efe3c5c47c186008",
        "crispr": "979f3c4e863662569cc36c46eaff679aece2c4466a3e6ba0fb45752b40d2bd43",
        "orf": "fbd644d8ccae4b02f623467b2bf8d9762cf8a224c169afa0561fedb61a697c18",
        "plate": "745391d930627474ec6e3083df8b5c108db30408c0d670cdabb3b79f66eaff48",
    }

    return pl.read_csv(
        pooch.retrieve(
            url=METADATA_LOCATION.format(table_name),
            known_hash=METAFILE_HASH[table_name],
        ),
        use_pyarrow=True,
    )
