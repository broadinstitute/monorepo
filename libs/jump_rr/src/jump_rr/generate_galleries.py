#!/usr/bin/env jupyter
# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.15.2
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

"""
Generate an interface to browse all available JUMP images.
"""
from pathlib import Path

import numpy as np
import polars as pl
from jump_rr.concensus import get_range
from jump_rr.formatters import get_formatter
from jump_rr.translate import get_mappers

# %% Setup
## Paths
dir_path = Path("/dgx1nas1/storage/data/shared/morphmap_profiles/")
platetype_filename = (
    ("crispr", "harmonized_no_sphering_profiles"),
    ("orf", "transformed_inf_eff_filtered"),
)
output_dir = Path("./databases")

## Column names
jcp_short = "JCP2022"  # Shortened input data frame
jcp_col = f"Metadata_{jcp_short}"  # Traditional JUMP metadata colname
std_outname = "Gene/Compound"  # Standard item name
ext_links_col = "External resources"  # Link to external resources (e.g., NCBI)


# %% Processing starts
for plate_type, filename in platetype_filename:
    profiles_path = dir_path / plate_type / f"{filename}.parquet"

    # %% Load Metadata
    df = pl.scan_parquet(profiles_path)

    # %% Translate genes names to standard
    uniq_jcp = tuple(df.select("Metadata_JCP2022").unique().collect().to_numpy()[:, 0])
    jcp_std_mapper, jcp_external_mapper = get_mappers(
        uniq_jcp, plate_type, format_output=False
    )

    df = df.with_columns(  # Format existing columns into #foci urls
        [
            pl.format(
                get_formatter("url_flat"),
                *[pl.col(f"Metadata_{x}") for x in ("Source", "Plate", "Well")],
                foci,
            ).alias(f"Foci {foci}")
            for foci in get_range(plate_type)
        ]
    )
    df = df.with_columns(  # Wrap the urls into html
        [
            pl.format(
                get_formatter("img_flat"),
                pl.col(f"Foci {foci}"),
                pl.col(f"Foci {foci}"),
            ).alias(f"Foci {foci}")
            for foci in get_range(plate_type)
        ]
    )
    df = df.with_columns(
        [
            pl.col(jcp_col).replace(jcp_std_mapper).alias(std_outname),
            pl.format(
                get_formatter("external_flat"),
                pl.col(jcp_col).replace(jcp_external_mapper),
            ).alias(ext_links_col),
        ]
    )

    order = [pl.col(x) for x in (std_outname, ext_links_col, jcp_col, "^Foci.*$")]
    df = df.select(order).collect()

    # %% Save results
    output_dir.mkdir(parents=True, exist_ok=True)
    final_output = output_dir / f"{plate_type}_gallery.parquet"
    df.write_parquet(final_output, compression="zstd")
