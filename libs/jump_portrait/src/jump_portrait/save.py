#!/usr/bin/env jupyter
"""Functions to save images of genes into files."""

from itertools import product
from pathlib import Path

import numpy as np
import polars as pl
from joblib import Parallel, delayed
from tqdm import tqdm

from jump_portrait.fetch import (
    build_s3_image_path,
    get_item_location_info,
)
from jump_portrait.s3 import get_corrected_image


def download_item_images(
    item_name: str,
    channels: list[str],
    sites: None or list[int] = None,
    corrections: list[str] = ["Orig"],
    output_dir: str = "imgs",
    controls: bool or int = True,
) -> None:
    """
    Download images for a given item across different channels and corrections.

    Parameters
    ----------
    item_name : str
        The name of the item to download images for.
    channels : list[str]
        A list of channel names to download images from.
    sites : list[int], optional
        A list of site IDs to filter by. If None, all sites are used.
    corrections : list[str], default=["Orig"]
        A list of correction types to apply to the images.
    output_dir : str, default="imgs"
        The directory to save the downloaded images in.
    controls : bool or int, default=True
        Whether to also download images from controls in the same plates as the item.

    Returns
    -------
    None

    """
    item_location_info = get_item_location_info(item_name, controls=controls)

    # Select channels if specified
    if sites is not None:
        item_location_info = item_location_info.filter(
            pl.col("Metadata_Site").is_in(sites)
        )

    item_location_tups = item_location_info.with_row_count(name="ix").rows(named=True)

    # Joblib requires we convert to list to know how to partition the data for threading
    item_ch_corr_combinations = list(product(item_location_tups, channels, corrections))

    Parallel(n_jobs=-1)(
        delayed(save_image)(*item) for item in tqdm(item_ch_corr_combinations)
    )


def save_image(
    image_metadata: dict[str, str],
    channel: str,
    correction: str = "Orig",
    output_dir: str = "imgs",
    pad: int = 5,
    apply_correction: bool = False,
) -> None:
    """
    Saves an image to a file after applying the specified corrections.

    Parameters
    ----------
    image_location : dict[str, str]
        Dictionary containing the location of images on `cellpainting-gallery`.
        It contains keys like 'PathNameOrigDNA", necessary to locate specific images.
        It is a single row of the location DataFrames.
    channel : str
        Channel of the image to be saved.
    correction : str, optional
        Type of correction to apply (default is "Orig").
    output_dir : str, optional
        Directory where the image will be saved (default is "imgs").
    pad : int, optional
        Number of zeros to pad the index with (default is 5).
    apply_correction : bool, optional
        Whether to apply corrections to the image (default is False).

    Returns
    -------
    None

    """
    build_s3_image_path(image_metadata=image_metadata, channel=channel, correction=correction)
    image = get_corrected_image(image_metadata, channel, correction, apply_correction)
    image_metadata["padded_ix"] = str(image_metadata["ix"]).rjust(pad, "0")
    out_file = "{standard_key}_{Metadata_PlateType}_{Metadata_Plate}_{padded_ix}"

    out_path = Path(output_dir) / out_file.format(**image_metadata)
    out_path.parent.mkdir(exist_ok=True, parents=True)

    np.savez_compressed(
        out_path,
        image,
    )
