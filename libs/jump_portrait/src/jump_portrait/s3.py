#!/usr/bin/env jupyter

from io import BytesIO

import boto3
import matplotlib.image as mpimg
import numpy as np
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
    s3_image_path = s3_image_path.lstrip("s3://cellpainting-gallery/")
    response = s3client().get_object(Bucket="cellpainting-gallery", Key=s3_image_path)
    return mpimg.imread(BytesIO(response["Body"].read()), format="tiff")


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
