#!/usr/bin/env jupyter
"""
Functions to save images of genes into files.
- TODO Associate each sample to a control in its plate
- TODO Save to tiff

"""

from itertools import product
from pathlib import Path

import numpy as np
import polars as pl

from jump_portrait.fetch import (
    build_s3_image_path,
    get_item_location_info,
)
from jump_portrait.s3 import get_corrected_image
from jump_portrait.utils import batch_processing, parallel
from joblib import Parallel, delayed
from tqdm import tqdm

def download_item_images(
    item_name: str,
    channels: list[str],
    sites: None or list[int] = None,
    corrections: list[str] = ["Orig"],
    output_dir: str = "imgs",
    controls: bool or int = True,
) -> None:
    item_location_info = get_item_location_info(item_name, controls=controls)

    # Select channels if specified
    if sites is not None:
        item_location_info = item_location_info.filter(
            pl.col("Metadata_Site").is_in(sites)
        )

    item_location_tups = item_location_info.with_row_count(name="ix").rows(named=True)

    item_ch_corr_combinations = list(product(item_location_tups, channels, corrections))

    # parallel(item_ch_corr_combinations, save_image, output_dir=output_dir)
    Parallel(n_jobs=-1)(delayed(save_image)(*item) for item in tqdm(item_ch_corr_combinations))

def save_image(
    row,
    channel: str,
    correction: str = "Orig",
    output_dir: str = "imgs",
    pad: int = 5,
    apply_correction: bool = False,
):
    s3_image_path = build_s3_image_path(row=row, channel=channel, correction=correction)
    image = get_corrected_image(row, channel, correction, apply_correction)
    row["padded_ix"] = str(row["ix"]).rjust(pad, "0")
    out_file = "{standard_key}_{Metadata_PlateType}_{Metadata_Plate}_{padded_ix}"

    out_path = Path(output_dir) / out_file.format(**row)
    out_path.parent.mkdir(exist_ok=True, parents=True)

    np.savez_compressed(
        out_path,
        image,
    )
