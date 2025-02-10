#!/usr/bin/env jupyter
"""
Functions to get JUMP-CP images from AWS's s3://cellpainting-gallery.

Based on github.com/jump-cellpainting/datasets/blob/baacb8be98cfa4b5a03b627b8cd005de9f5c2e70/sample_notebook.ipynb

The general workflow is a bit contrived but it works:
a) If you have an item of interest and want to see them:
- Use broad_babel to convert item name to jump id (get_item_location_metadata)
- Use JUMP identifier to fetch the metadata dataframe with image locations (TODO isolate this)
- Use this location dataframe to build a full path and fetch it from there

Current problems:
- Control info is murky, requires using broad_babel
- More controls than individual samples, thus we must resample.
"""

from itertools import product, starmap

import numpy as np
import polars as pl
from broad_babel import query
from broad_babel.data import get_table

from jump_portrait.s3 import (
    get_corrected_image,
    read_ldcsv_s3,
)
from jump_portrait.utils import batch_processing, parallel, try_function


def format_cellpainting_s3(dataset: str = "cpg0016-jump", suffix: str = "csv") -> str:
    """
    Return a formatted string for an S3 path to Cell Painting data.

    Parameters
    ----------
    dataset : str, optional
        The dataset name (default is "cpg0016-jump").
    suffix : str, optional
        The file suffix (default is "csv").

    Returns
    -------
    str
        A formatted string representing the S3 path with placeholders for metadata fields.

    Notes
    -----
    The placeholders in the path are:
    - {Metadata_Source}
    - {Metadata_Batch}
    - {Metadata_Plate}

    Examples
    --------
    >>> format_cellpainting_s3()
    'https://cellpainting-gallery.s3.amazonaws.com/cpg0016-jump/{Metadata_Source}/workspace/load_data_csv/{Metadata_Batch}/{Metadata_Plate}/load_data_with_illum.csv'

    """
    ldcsv = "load_data_csv"
    if suffix == "parquet":
        ldcsv += "_orig"
    return (
        f"https://cellpainting-gallery.s3.amazonaws.com/{dataset}/"
        "{Metadata_Source}/"
        f"workspace/{ldcsv}/"
        "{Metadata_Batch}/"
        "{Metadata_Plate}/"
        f"load_data_with_illum.{suffix}"
    )


def get_sample(n: int = 2, seed: int = 42) -> pl.DataFrame:
    """
    Retrieve a sample of cell painting data from S3.

    Parameters
    ----------
    n : int, optional
        Number of samples to retrieve (default is 2).
    seed : int, optional
        Random seed used for shuffling the data (default is 42).

    Returns
    -------
    parquet_meta : pl.DataFrame
        Retrieved parquet metadata.

    """
    sample = (
        get_table("plate")
        .filter(pl.col("Metadata_PlateType") == "TARGET2")
        .filter(
            pl.int_range(0, pl.len()).shuffle(seed=seed).over("Metadata_Source") < n
        )
    )

    s3_path = format_cellpainting_s3().format(**sample.to_dicts()[0])

    ldcsv = read_ldcsv_s3(s3_path)
    return ldcsv


def get_jump_image(
    source: str,
    batch: str,
    plate: str,
    well: str,
    channel: str,
    site: str = "1",
    correction: str = "Orig",
    apply_correction: bool = True,
    staging: bool = False,
    lazy: bool = True,
    dataset: str = "cpg0016-jump",
) -> np.ndarray:
    """
    Fetch a single image from JUMP from Cellpainting Gallery's AWS bucket.

    Parameters
    ----------
    source : str
        The collaborator (data source) that contributed the images.
    batch : str
        The name of the batch.
    plate : str
        The name of the plate.
    well : str
        The well number (e.g., A01).
    channel : str
        The channel to fetch, standard channels include DNA, Mito, ER, and AGP.
    site : str or int, optional
        Site identifier (also called foci), by default "1". It is casted if needed.
    correction : str, optional
        Whether or not to use corrected data ("Orig" or "Illum"), by default "Orig".
    apply_correction : bool, optional
        When correction is "Illum", apply Illum correction on the original image, by default True.
    staging : bool, optional
        Whether or not to use the staging prefix on S3, by default False.
    lazy : bool, optional
        Whether or not to load data lazily, by default True.
    dataset: string, optional
        Which Cell Painting Gallery to download from, by default None, which results in cpg00016-jump.

    Returns
    -------
    np.ndarray
        The selected image as a numpy array.

    Raises
    ------
    AssertionError
        If no valid site is found or if more than one site is found.

    Notes
    -----
    Metadata for most files can be obtained from a set of data frames,
    or retrieved using `get_item_location_metadata` from this module.

    """
    s3_location_frame_uri = format_cellpainting_s3(dataset=dataset).format(
        Metadata_Source=source, Metadata_Batch=batch, Metadata_Plate=plate
    )
    location_frame = read_ldcsv_s3(s3_location_frame_uri, lazy=lazy)
    unique_site = location_frame.filter(
        (pl.col("Metadata_Well") == well) & (pl.col("Metadata_Site") == str(site))
    )
    if lazy:
        unique_site = unique_site.collect()

    assert (
        len(unique_site) > 0
    ), f"No valid site was found: {source, batch, plate, well, site}"
    assert (
        len(unique_site) < 2
    ), f"More than one site found: {source, batch, plate, well, site}"

    first_row = unique_site.row(0, named=True)

    result = get_corrected_image(
        first_row, channel, correction, apply_correction, staging
    )
    return result


def get_jump_image_batch(
    metadata: pl.DataFrame,
    channel: list[str],
    site: list[str],
    correction: str = "Orig",
    verbose: bool = True,
) -> tuple[list[tuple], list[np.ndarray]]:
    """
    Load jump image associated to metadata in a threaded fashion.

    Parameters
    ----------
    metadata : pl.DataFrame
        must have the column in this specific order ("Metadata_Source", "Metadata_Batch", "Metadata_Plate", "Metadata_Well")
    channel : list of string
        list of channel desired
        Must be in ['DNA', 'ER', 'AGP', 'Mito', 'RNA', 'Brightfield']
    site : list of int or str
        list of site desired
        - For compound, must be in [1 - 6]
        - For ORF, CRISPR, must be in [1 - 9]
    correction : str
        Must be 'Illum' or 'Orig'
    verbose : bool
        Whether to enable tqdm or not.

    Return:
    ----------
    iterable : list of tuple
        list containing the metadata, channel, site and correction
    img_list : list of array
        list containing the images

    """
    iterable = list(
        starmap(
            lambda *x: (*x[0], *x[1:]),
            product(metadata.rows(), channel, site, [correction]),
        )
    )

    img_list = parallel(
        iterable, batch_processing(try_function(get_jump_image)), verbose=verbose
    )

    return iterable, img_list


def get_item_location_metadata(
    item_name: str,
    operator: str or None = None,
    input_column: str = "standard_key",
) -> pl.DataFrame:
    """
    Get metadata location for an item (gene or compound) by its name.

    Search for datasets where the item is present and return a tuple
    with its metadata location in order of source, batch, plate, well, and site.

    Parameters
    ----------
    item_name : str
        The name of the item to search for.
    operator : str or None, optional
        The operator to use for the query (default is None).
    input_column : str, optional
        The input column to use for the query (default is "standard_key").

    Returns
    -------
    pl.DataFrame
        A DataFrame containing the metadata location of the item.

    Raises
    ------
    AssertionError
        If the item_name is "JCP2022_033924", which is not supported as it is a negative control and fills the memory of most computers.

    """
    assert (
        item_name != "JCP2022_033924"
    ), "The negative control is not supported, please use a smaller selection before fetching plate information"

    # Get plates
    jcp_ids = query.run_query(
        query=item_name,
        input_column=input_column,
        output_columns="JCP2022,standard_key",
        operator=operator,
    )
    jcp_item = {x[0]: x[1] for x in jcp_ids}
    meta_wells = get_table("well")
    found_rows = meta_wells.filter(pl.col("Metadata_JCP2022").is_in(jcp_item.keys()))
    found_rows = found_rows.with_columns(pl.lit(item_name).alias("standard_key"))

    # Get full plate metadata with (contains no info reference about wells)
    plate_level_metadata = get_table("plate").filter(
        pl.col("Metadata_Plate").is_in(found_rows.select("Metadata_Plate").to_series())
    )
    well_level_metadata = plate_level_metadata.join(
        found_rows,
        on=("Metadata_Source", "Metadata_Plate"),
    )
    return well_level_metadata


def load_filter_well_metadata(well_level_metadata: pl.DataFrame) -> pl.DataFrame:
    """
    Load and filter a DataFrame by using metadata of the well location.

    Loading and filtering happens in a threaded manner. Note that it does not check for whole row duplication.

    Parameters
    ----------
    well_level_metadata : pl.DataFrame
        Contains the data, contaning, containing these columns
            - Metadata_Source
            - Metadata_Batch
            - Metadata_Plate
            - Metadata_Well


    Returns
    -------
    pl.DataFrame
        DataFrame with location of item

    """
    core_cols = (
        "Metadata_Source",
        "Metadata_Batch",
        "Metadata_Plate",
        "Metadata_PlateType",
    )
    metadata_fields = well_level_metadata.unique(
        subset=(
            *core_cols,
            "Metadata_Well",
            "standard_key",
        )
    )
    groups = metadata_fields.group_by(core_cols).agg("Metadata_Well").to_dicts()

    s3_locations_uri = [format_cellpainting_s3().format(**x) for x in groups]

    # Get uris for the specific wells in the fetched plates
    iterable = list(
        zip(
            s3_locations_uri,
            map(lambda x: x["Metadata_Well"], groups),
        )
    )
    well_images_uri = parallel(iterable, get_well_image_uris)

    selected_uris = pl.concat(well_images_uri, how="diagonal")

    return selected_uris


@batch_processing
def get_well_image_uris(s3_location_uri: str, wells: list[str]) -> pl.DataFrame:
    """
    Return a dataframe indicating the image location of specific wells for a given parquet file.

    The function reads a parquet file from S3, filters it by well names and returns the result as a DataFrame.


    Parameters
    ----------
    s3_location_uri : str
        The S3 URI location of the parquet file.
    wells : list[str]
        A list of well names to filter by.

    Returns
    -------
    pl.DataFrame
        A dataframe containing the image locations of the specified wells.

    Notes
    -----
    It uses a decorator for batch processing.

    """
    locations_df = read_ldcsv_s3(s3_location_uri)
    return locations_df.filter(pl.col("Metadata_Well").is_in(wells))


def get_item_location_info(
    item_name: str,
    input_column: str = "standard_key",
) -> pl.DataFrame:
    """
    Obtain a DataFrame of the metadata with the location (batch, plate, etc.) of an item.

    This wraps `get_item_location_metadata` and gets rid of duplicated entries.

    Parameters
    ----------
    item_name : str
        Item of interest to query
    input_column : str
        Name of the column where `item_name` is to be looked for.

    Returns
    -------
    pl.DataFrame
        DataFrame with location of item

    Examples
    --------
    FIXME: Add docs.

    """
    well_level_metadata = get_item_location_metadata(
        item_name, input_column=input_column
    )
    assert len(
        well_level_metadata
    ), f"Item {item_name} was not found in column {input_column}"

    # Note that this breaks if we pass item_name="JCP2022_033924" and
    # input_column="JCP2022", as it is the negative control. There is an assertion on the top
    # level to avoid this situation
    item_selected_meta = load_filter_well_metadata(well_level_metadata)
    joint = item_selected_meta.join(
        well_level_metadata.drop("Metadata_Well"),
        on=("Metadata_Source", "Metadata_Batch", "Metadata_Plate"),
    )
    # Cast Plate to string
    # See https://github.com/jump-cellpainting/datasets/issues/147
    return joint.unique()
