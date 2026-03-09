#!/usr/bin/env python
"""
JUMP-CP Data Access and Image Retrieval Tools.

This module facilitates querying the JUMP-CP dataset index, retrieving metadata
for specific genes or compounds, and downloading or loading microscopy images
directly from S3 storage using DuckDB and PyArrow.

Use cases:
# Fetch single image into python
img = get_jump_image("source_4", "2021_04_26_Batch1", "BR00121565", "A01", "DNA", 1)
# Fetch or download all the images of a given perturbation
# Pull the s3 locations of a perturbation
metadata = get_item_location_metadata("MYT1")
metadata = get_item_location_metadata("CLETVKMYAXARPO-UHFFFAOYSA-N")

# Load into memory
metadata_dicts, result = get_jump_image_batch(metadata)

# Download into a folder
downloaded = download_jump_image_batch(metadata, output_dir="/tmp/deleteme")

"""

from functools import cache, partial
from pathlib import Path

import duckdb
import numpy as np
import pyarrow as pa
from broad_babel import query
from broad_babel.data import get_table
from joblib import Parallel, delayed
from pooch import retrieve

from jump_portrait.s3 import download_s3uri, get_image_from_s3uri


@cache
def get_index_file() -> Path:
    """
    Retrieve the index file of the JUMP-CP dataset.

    Returns
    -------
    Path
        The path to the downloaded index file.

    """
    jump_index = (
        "https://zenodo.org/api/records/18729301/files/jump_index.parquet/content"
    )

    return retrieve(
        jump_index,
        known_hash="6dddbda730650a079005565ce7f1418555cbb0ac77f0e3ecbf9a538f11c9a156",
    )


def get_sample(n: int = 2, seed: int = 42) -> pa.Table:
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
    parquet_meta : pa.Table
        Retrieved parquet metadata.

    """
    if seed is None:
        sampler = f"{n}"
    else:
        sampler = f"reservoir({n} ROWS) REPEATABLE ({seed})"
    index_file = get_index_file()
    with duckdb.connect() as con:
        sample = con.sql(
            f"FROM read_parquet('{index_file}') USING SAMPLE {sampler}"
        ).to_arrow_table()

    return sample


def get_item_location_metadata(
    item_name: str,
    operator: str or None = None,
    input_column: str = "standard_key",
) -> list[dict[str, str | int]]:
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
    pyarrow table
        A DataFrame containing the metadata location of the item and the URLs for its images.

    Raises
    ------
    AssertionError
        If the item_name is "JCP2022_033924", which is not supported as it is a negative control and fills the memory of most computers.

    """
    assert input_column in (
        "standard_key",
        "JCP2022",
    ), "Only standard_key and JCP2022 are valid input_columns."

    # Get plates
    jcp_ids = query.run_query(
        query=item_name,
        input_column=input_column,
        output_columns="JCP2022,standard_key",
        operator=operator,
    )
    jcp_item = dict(jcp_ids)

    assert len(jcp_item), f"No JCP id found for {jcp_item}"

    index_file = get_index_file()

    with duckdb.connect() as con:
        meta_wells = get_table("well")  # noqa: F841
        found_rows = con.sql(  # noqa: F841
            f"SELECT *, '{item_name}' AS standard_key FROM meta_wells WHERE Metadata_JCP2022 IN {list(jcp_item.keys())}"
        )

        well_metadata = con.sql(
            f"FROM found_rows JOIN (FROM read_parquet('{index_file}')) USING(Metadata_Source,Metadata_Plate,Metadata_Well)"
        ).to_arrow_table()

    return well_metadata


def get_metadata_dicts(
    metadata: pa.Table | dict[str, str | int] | list[dict[str, str | int]],
    channels: list[str] = ("DNA", "RNA", "Mito", "AGP", "ER"),
    site: list[int] = None,
) -> list[dict[str, str | int]]:
    """
    Transform image metadata into a list of dictionaries with unpivoted channel information.

    This function processes metadata from multiple formats, filters it by site if
    requested, and unpivots URL columns into a normalized format containing
    channel names and their corresponding URIs using DuckDB.

    Parameters
    ----------
    metadata : pyarrow.lib.Table or dict[str, str | int] or list[dict[str, str | int]]
        The input metadata. Can be a PyArrow Table, a dictionary of lists,
        or a list of dictionaries. Must contain 'standard_key', JCP2022
        identifiers, and URL columns corresponding to the requested channels.
    channels : list of str, default ("DNA", "RNA", "Mito", "AGP", "ER")
        The specific imaging channels to extract. Must be a subset of the
        standard five channels: DNA, RNA, Mito, AGP, ER.
    site : list of int, optional
        A list of site IDs (Metadata_Site) to filter the results by.
        If None (default), all sites are processed.

    Returns
    -------
    list of dict[str, str | int]
        A list of dictionaries where each dictionary represents one channel
        per site/well, including keys for metadata identifiers,
        'Metadata_Channel', and 'Metadata_uri'.

    Raises
    ------
    AssertionError
        If any of the provided channel names are not in the valid set
        ("DNA", "RNA", "Mito", "AGP", "ER").

    """
    if isinstance(metadata, dict):
        metadata = pa.Table.from_pydict(metadata)
    elif isinstance(metadata, list):
        metadata = pa.Table.from_pylist(metadata)

    if site is None:
        site_filter = ""
    else:
        site_filter = f"WHERE Metadata_Site IN {site}"

    valid_channels = set(channels).intersection(("DNA", "RNA", "Mito", "AGP", "ER"))
    assert (
        len(valid_channels) == len(channels)
    ), f"Invalid channel name(s): {channels}, only {len(valid_channels)} are valid: {valid_channels}"

    with duckdb.connect() as con:
        joint = con.sql(  # noqa: F841
            f"SELECT standard_key,COLUMNS('Metadata_(JCP2022|Source|Batch|Plate|Well|Site)'),COLUMNS('URL_Orig({'|'.join(channels)})') FROM metadata {site_filter}"
        )
        metadata_dicts = (
            con.sql(
                "UNPIVOT joint ON COLUMNS('URL_Orig(.+)') AS \"\\1\" INTO NAME Metadata_Channel VALUE Metadata_uri"
            )
            .to_arrow_table()
            .to_pylist()
        )
    return metadata_dicts


def get_jump_image(
    source: str,
    batch: str,
    plate: str,
    well: str,
    channel: str,
    site: str = "1",
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

    Returns
    -------
    np.ndarray
        The selected image as a numpy array.

    Raises
    ------
    AssertionError
        If no valid site is found or if more than one site is found.

    """
    index_path = get_index_file()
    with duckdb.connect() as con:
        url_field = f"URL_Orig{channel}"
        query_result = con.sql(
            f"SELECT {url_field} "
            f"FROM read_parquet('{index_path}') WHERE Metadata_Source = '{source}'"
            f"AND Metadata_Batch = '{batch}'"
            f"AND Metadata_Plate = '{plate}'"
            f"AND Metadata_Well = '{well}'"
            f"AND Metadata_Site = {int(site)}"
        )
        table = query_result.to_arrow_table()
        assert len(table) == 1, "Incorrect query results of length {len(table)}"
        url = table[url_field][0].as_py()
    return get_image_from_s3uri(url)


def get_jump_image_batch(
    metadata: pa.Table | dict[str, str | int] | list[dict[str, str | int]],
    channels: list[str] = ("DNA", "RNA", "Mito", "AGP", "ER"),
    site: list[int] = None,
) -> tuple[list[dict[str, str | int]], list[np.ndarray]]:
    """
    Load jump image associated to metadata in a threaded fashion.

    Parameters
    ----------
    metadata : pa.Table, dict or list of dict.
        must have the columns ("Metadata_Source", "Metadata_Batch", "Metadata_Plate", "Metadata_Well"), as well as the URIs.
    channels : list of string
        list of channel desired
        Must be in ['DNA', 'ER', 'AGP', 'Mito', 'RNA']
    site : list of int or str
        list of site desired
        - For compound, must be in [1 - 6]
        - For ORF, CRISPR, must be in [1 - 9]

    Returns
    -------
    metadata_dicts : list of dict
        list containing the metadata, channel, site and correction
    img_list : list of array
        list containing the images

    """
    metadata_dicts = get_metadata_dicts(metadata, channels, site)

    result = list(
        Parallel()(
            delayed(get_image_from_s3uri)(x["Metadata_uri"]) for x in metadata_dicts
        )
    )
    return metadata_dicts, result


def download_jump_image_batch(
    metadata: pa.Table | dict[str, str | int] | list[dict[str, str | int]],
    output_dir: Path,
    path_to_name: bool = True,
    channels: list[str] = ("DNA", "RNA", "Mito", "AGP", "ER"),
    site: list[int] = None,
) -> list[bool]:
    """
    Download a batch of JUMP images from S3 based on provided metadata.

    Parameters
    ----------
    metadata : pa.Table or dict or list of dict
        The metadata containing image information, including S3 URIs and
        identifiers (Source, Batch, Plate, Well, Site, Channel).
    output_dir : Path
        The local directory where the downloaded images will be stored.
    path_to_name : bool, default True
        If True, the S3 path structure is used to generate the local filename.
    channels : list of str, default ("DNA", "RNA", "Mito", "AGP", "ER")
        List of image channels to be included in the download batch.
    site : list of int, optional
        Specific sites to filter for download. If None, all sites in the
        metadata are processed.

    Returns
    -------
    list of bool
        A list of boolean values indicating whether each individual file
        download was successful.

    """
    output_dir = Path(output_dir)

    metadata_dicts = get_metadata_dicts(metadata, channels, site)

    identifiers = ("Source", "Batch", "Plate", "Well", "Site", "Channel")
    curried = partial(download_s3uri, output_dir=output_dir, path_to_name=path_to_name)
    result = list(
        Parallel()(
            delayed(curried)(
                (
                    *[x[f"Metadata_{y}"] for y in identifiers],
                    x["Metadata_uri"],
                )
            )
            for x in metadata_dicts
        )
    )

    return result
