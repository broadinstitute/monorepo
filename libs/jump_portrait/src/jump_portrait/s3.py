#!/usr/bin/env jupyter

import io
from io import BytesIO

import boto3
import matplotlib.image as mpimg
import numpy as np
import polars as pl
import pyarrow as pa
from botocore import UNSIGNED
from botocore.config import Config
from pyarrow.dataset import dataset
from s3fs import S3FileSystem
from s3path import PureS3Path, S3Path

"""
Tools to Search for files in AWS's CellPainting Gallery
S3_BUCKET_NAME = "cellpainting-gallery"
prefix = "/cpg0020-varchamp/broad/images/"

"""


def s3client():
    return boto3.client("s3", config=Config(signature_version=UNSIGNED))


def get_image_from_s3uri(s3_image_uri) -> np.ndarray:
    # Assumes we are accessing cellpainting-gallery

    s3_image_uri = str(s3_image_uri)  # if instance is S3Path

    # Remove all possible prefixes
    bucket_name = "cellpainting-gallery"
    s3_image_uri = s3_image_uri.removeprefix(f"s3://{bucket_name}/")
    s3_image_uri = s3_image_uri.removeprefix(f"/{bucket_name}/")
    s3_image_uri = s3_image_uri.removeprefix(f"{bucket_name}/")

    response = s3client().get_object(Bucket="cellpainting-gallery", Key=s3_image_uri)
    response_body = BytesIO(response["Body"].read())

    if s3_image_uri.endswith(".tif") or s3_image_uri.endswith(".tiff"):
        result = mpimg.imread(response_body, format="tiff")

    elif s3_image_uri.endswith(".npy"):
        result = np.load(response_body)
    else:
        raise Exception(f"Format not supported for {s3_image_uri}")

    return result


def get_corrected_image(
    images_location: dict,
    channel: str,
    correction: str or None,
    apply_correction: bool = True,
) -> np.ndarray:
    """Correct the image from a given location when appropriate by dividing it by another image in the same location dictionary.

    Parameters
    ----------
    images_location : dict
    channel : str
    correction : str or None

    Returns
    -------
    np.ndarray Corrected or raw image

    Examples
    --------
    FIXME: Add docs.


    """
    s3_image_path = build_s3_image_path(
        row=images_location, channel=channel, correction=correction
    )
    result = get_image_from_s3uri(s3_image_path)

    if apply_correction and not correction in ("Orig", None):
        original_image_path = build_s3_image_path(
            row=images_location, channel=channel, correction="Orig"
        )
        result = get_image_from_s3uri(original_image_path) / result

    return result


def keys(Bucket, Prefix="", StartAfter="", Delimiter="/"):
    Prefix = Prefix[1:] if Prefix.startswith(Delimiter) else Prefix
    if not StartAfter:
        del StartAfter
        if Prefix.endswith(Delimiter):
            StartAfter = Prefix
    del Delimiter
    for page in (
        boto3.client("s3", config=Config(signature_version=UNSIGNED))
        .get_paginator("list_objects_v2")
        .paginate(**locals())
    ):
        for content in page.get("Contents", ()):
            yield content["Key"]


def build_s3_image_path(
    row: dict[str, str], channel: str, correction: None or str = None
) -> PureS3Path:
    """ """
    if correction is None:
        correction = "Orig"
    index_suffix = correction + channel
    final_path = (
        S3Path.from_uri(row["_".join(("PathName", index_suffix))])
        / row["_".join(("FileName", index_suffix))]
    )
    return final_path


def read_parquet_s3(path: str, lazy: bool = False):
    """Read parquet file from S3 onto memory.

    Parameters
    ----------
    path : str
        S3 path location.
    lazy : bool
        Whether to load lazily or not. The mechanisms changes depending on how
        the data is to be loaded. Warning: Lazy-loading does not work
        specifically for the datasets that contain image information.

    Examples
    --------
    FIXME: Add docs.

    """

    if lazy:
        # TODO Raise issue and find the problem with the image location datasets.
        # It seems to be related related to UTF8 encoding.
        # Example path failing:
        # 's3a://cellpainting-gallery/cpg0016-jump/source_10/workspace/load_data_csv/2021_08_17_U2OS_48_hr_run16/Dest210809-134534/load_data_with_illum.parquet'
        raise Exception(
            "Lazy-loading does not currently work for image location parquets."
        )
        fs = S3FileSystem(anon=True)
        ds = dataset(path, filesystem=fs)
        result = pl.scan_pyarrow_dataset(ds).collect()
    else:
        # Read whole dataframe
        result = pl.read_parquet(
            path,
            use_pyarrow=True,
            storage_options={"anon": True},
        )
    return result
