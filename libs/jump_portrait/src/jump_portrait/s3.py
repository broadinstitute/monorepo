#!/usr/bin/env jupyter

import io
import os
import re
from io import BytesIO

import boto3
import matplotlib.image as mpimg
import numpy as np
import polars as pl
import pyarrow as pa
from botocore import UNSIGNED
from botocore.config import Config
from matplotlib import pyplot as plt
from pyarrow.dataset import dataset
from s3fs import S3FileSystem
from s3path import PureS3Path, S3Path

"""
Tools to Search for files in AWS's CellPainting Gallery
S3_BUCKET_NAME = "cellpainting-gallery"
prefix = "/cpg0020-varchamp/broad/images/"

"""


def s3client(use_credentials: bool = False):
    if use_credentials:
        if not all(key in os.environ for key in [
                    "AWS_ACCESS_KEY_ID",
                    "AWS_SECRET_ACCESS_KEY",
                    "AWS_SESSION_TOKEN"]):
            raise Exception("AWS credentials not found."
                            "Please set them in the environment, or use"
                            "data that does not require credentials.")

        return boto3.client(
            "s3", region_name='us-east-1',
            aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
            aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
            aws_session_token=os.environ['AWS_SESSION_TOKEN'])
    else:
        return boto3.client("s3", config=Config(signature_version=UNSIGNED))


def get_image_from_s3uri(s3_image_uri,
                         bucket_name='cellpainting-gallery',
                         staging: bool = False) -> np.ndarray:

    s3_image_uri = str(s3_image_uri)  # if instance is S3Path

    # Remove all possible prefixes
    s3_image_uri = s3_image_uri.removeprefix(f"s3://{bucket_name}/")
    s3_image_uri = s3_image_uri.removeprefix(f"/{bucket_name}/")
    s3_image_uri = s3_image_uri.removeprefix(f"{bucket_name}/")

    try:
        response = s3client(
            use_credentials=staging
        ).get_object(Bucket=bucket_name, Key=s3_image_uri)
        response_body = BytesIO(response["Body"].read())
    except Exception as e:
        print(f"Failed to fetch s3://{bucket_name}/{s3_image_uri}. Is the file"
              f"path correct and accessible?")
        raise e


    if s3_image_uri.endswith(".tif") or s3_image_uri.endswith(".tiff"):
        result = mpimg.imread(response_body, format="tiff")
    elif s3_image_uri.endswith(".npy"):
        result = np.load(response_body)
    elif s3_image_uri.endswith(".png"):
        result = plt.imread(response_body)
    else:
        raise Exception(f"Format not supported for {s3_image_uri}")

    return result


def get_corrected_image(
    images_location: dict,
    channel: str,
    correction: str or None,
    apply_correction: bool = True,
    compressed: bool = False,
    staging: bool = False,
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
        row=images_location,
        channel=channel,
        correction=correction,
        compressed=compressed,
        staging=staging
    )

    result = get_image_from_s3uri(s3_image_path, s3_image_path.bucket, staging=staging)

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
    row: dict[str, str], channel: str,
    correction: None or str = None,
    compressed: bool = False,
    staging: bool = False,
) -> PureS3Path:
    """ """
    if correction is None:
        correction = "Orig"

    use_bf_channel = None
    # Special case to fetch bright field images
    if channel == "bf":
        use_bf_channel = True
        channel, correction = "DNA", "Orig"

    index_suffix = correction + channel

    directory = row["_".join(("PathName", index_suffix))]
    filename = row["_".join(("FileName", index_suffix))]

    if staging:
        directory = directory.replace("cellpainting-gallery", "staging-cellpainting-gallery")
    if compressed:
        pattern = r"(images/[^/]+)/(images)/.*"
        replacement = r"\1/\2_compressed/" + row['Metadata_Plate'] + "/"
        directory = re.sub(pattern, replacement, directory)
        filename = os.path.splitext(filename)[0] + ".png"
    if use_bf_channel: # Replace the image with the bright field channel
        channel_ids = [int(v[-5]) for k,v in row.items() if k.startswith("FileName_Orig")]
        # the one channel not present  
        bf_id = list(set(range(1, 7)).difference(channel_ids))[0]
        filename_as_lst = list(filename)
        filename_as_lst[-5] = str(bf_id)
        filename_as_lst[-11] = "4" # I found that C06 finishes with A04
        filename = "".join(filename_as_lst)


    final_path = S3Path.from_uri(directory) / filename

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
        raise Exception(
            "Lazy-loading does not currently work for image location parquets."
        )
        fs = S3FileSystem(anon=True)
        ds = dataset(path, filesystem=fs)
        # Replace schema to remove metadata, bypassing the fringe case
        # where it is corrupted, see here for details:
        # https://github.com/broadinstitute/monorepo/issues/21
        schema = pa.schema([pa.field(k, pa.utf8()) for k in ds.schema.names])
        result = pl.scan_pyarrow_dataset(ds.replace_schema(schema))  # .collect()
    else:
        # Read whole dataframe
        result = pl.read_parquet(
            path,
            use_pyarrow=True,
            storage_options={"anon": True},
        )
    return result
