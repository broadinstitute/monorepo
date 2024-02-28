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
from s3path import PureS3Path, S3Path

"""
Tools to Search for files in AWS's CellPainting Gallery
S3_BUCKET_NAME = "cellpainting-gallery"
prefix = "/cpg0020-varchamp/broad/images/"

"""


def s3client():
    return boto3.client("s3", config=Config(signature_version=UNSIGNED))


def get_image_from_s3path(s3_image_path) -> np.ndarray:
    # Assumes we are accessing cellpainting-gallery

    s3_image_path = str(s3_image_path)  # if instance is S3Path

    # Remove all possible prefixes
    bucket_name = "cellpainting-gallery"
    s3_image_path = s3_image_path.removeprefix(f"s3:/{bucket_name}/")
    s3_image_path = s3_image_path.removeprefix(f"/{bucket_name}/")
    s3_image_path = s3_image_path.removeprefix(f"{bucket_name}/")

    response = s3client().get_object(Bucket="cellpainting-gallery", Key=s3_image_path)
    response_body = BytesIO(response["Body"].read())

    if s3_image_path.endswith(".tif") or s3_image_path.endswith(".tiff"):
        result = mpimg.imread(response_body, format="tiff")

    elif s3_image_path.endswith(".npy"):
        result = np.load(response_body)
    else:
        raise Exception(f"Format not supported for {s3_image_path}")
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
    row: dict[str, str], channel: str, correction: None or str = None, compressed: bool = False
) -> PureS3Path:
    """ """
    if correction is None:
        correction = "Orig"
    index_suffix = correction + channel
    directory = row["_".join(("PathName", index_suffix))]
    filename = row["_".join(("FileName", index_suffix))]

    # TODO: Temporary fix, eventually should create load_data_compressed files on s3
    if compressed:
        directory = directory.replace("images", "images_compressed", 1)

    final_path = (
        S3Path.from_uri(directory)
        / filename
    )
    return final_path


def read_parquet_s3(path: str):
    return pl.read_parquet(
        path,
        use_pyarrow=True,
        # Temporarily removed due to them not enabling anonymous fetching
        # from s3fs import S3FileSystem
        # pyarrow_options={"filesystem": S3FileSystem(anonymous=True)},
    )
