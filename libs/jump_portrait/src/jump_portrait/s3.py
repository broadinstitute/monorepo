"""
Tools to Search for files in AWS's CellPainting Gallery.

S3_BUCKET_NAME = "cellpainting-gallery"
prefix = "/cpg0020-varchamp/broad/images/".

"""

import os
from functools import lru_cache
from io import BytesIO

import boto3
import matplotlib.image as mpimg
import numpy as np
import polars as pl
from botocore import UNSIGNED
from botocore.config import Config
from matplotlib import pyplot as plt
from s3path import PureS3Path


def s3client(use_credentials: bool = False) -> boto3.client:
    """
    Create an S3 client with or without credentials.

    Parameters
    ----------
    use_credentials : bool, optional
        Whether to use AWS credentials. If True, the function will look for
         'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', and 'AWS_SESSION_TOKEN' in
        the environment variables. If False, it will create a client without
         credentials (default is False).

    Returns
    -------
    boto3.client
        An S3 client object.

    Raises
    ------
    Exception
        If use_credentials is True but the required AWS credentials are not found
         in the environment variables.

    """
    if use_credentials:
        if not all(
            key in os.environ
            for key in [
                "AWS_ACCESS_KEY_ID",
                "AWS_SECRET_ACCESS_KEY",
                "AWS_SESSION_TOKEN",
            ]
        ):
            raise Exception(
                "AWS credentials not found. "
                "Please set them in the environment, or use "
                "data that does not require credentials."
            )

        return boto3.client(
            "s3",
            region_name="us-east-1",
            aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
            aws_session_token=os.environ["AWS_SESSION_TOKEN"],
        )
    else:
        return boto3.client("s3", config=Config(signature_version=UNSIGNED))


def get_image_from_s3uri(
    s3_image_uri: str, bucket_name: str = "cellpainting-gallery", staging: bool = False
) -> np.ndarray:
    """
    Retrieve an image from Amazon S3 based on its URI.

    Parameters
    ----------
    s3_image_uri : str
        The S3 URI of the image to retrieve.
    bucket_name : str, optional
        The name of the S3 bucket containing the image. Default is "cellpainting-gallery".
    staging : bool, optional
        Whether to use the "staging-cellpainting-gallery" instead of the public one.
    Default is False. If True, it requires valid credentials.

    Returns
    -------
    np.ndarray
        The retrieved image as a NumPy array.

    Raises
    ------
    Exception
        If the file path is incorrect or inaccessible, or if the image format is not supported.

    """
    s3_image_uri = str(s3_image_uri)  # if instance is S3Path

    # Remove all possible prefixes
    s3_image_uri = s3_image_uri.removeprefix(f"s3://{bucket_name}/")
    s3_image_uri = s3_image_uri.removeprefix(f"/{bucket_name}/")
    s3_image_uri = s3_image_uri.removeprefix(f"{bucket_name}/")

    try:
        client = s3client(use_credentials=staging)
        response = client.get_object(Bucket=bucket_name, Key=s3_image_uri)
        response_body = BytesIO(response["Body"].read())
    except Exception as e:
        print(
            f"Failed to fetch s3://{bucket_name}/{s3_image_uri}. Is the file"
            f"path correct and accessible?"
        )
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
    image_metadata: dict,
    channel: str,
    correction: str or None,
    apply_correction: bool = True,
    staging: bool = False,
) -> np.ndarray:
    """
    Retrieve and correct an image from a specified location.

    Parameters
    ----------
    image_metadata : dict
        Dictionary containing image locations.
    channel : str
        Channel of the image to retrieve.
    correction : str or None
        Type of correction to apply (or None for no correction).
    apply_correction : bool, optional
        Whether to apply the correction (default is True).
    staging : bool, optional
        Whether to use the "staging-cellpainting-gallery" instead of the public one.
    Default is False. If True, it requires valid credentials in the environment.

    Returns
    -------
    np.ndarray
        The corrected or raw image.

    Notes
    -----
    If `apply_correction` is True and `correction` is not "Orig" or None,
    the function divides the original image by the correction image.

    """
    s3_image_path = build_s3_image_path(
        image_metadata=image_metadata,
        channel=channel,
        correction=correction,
        staging=staging,
    )

    result = get_image_from_s3uri(s3_image_path, staging=staging)

    if apply_correction and correction not in ("Orig", None):
        original_image_path = build_s3_image_path(
            image_metadata=image_metadata, channel=channel, correction="Orig"
        )
        result = get_image_from_s3uri(original_image_path) / result

    return result


def build_s3_image_path(
    image_metadata: dict[str, str],
    channel: str,
    correction: None or str = None,
    staging: bool = False,
) -> PureS3Path:
    """
    Build the path for an image on cellpainting gallery's S3 bucket.

    image_metadata : dict[str, str]
        Dictionary containing the location of images on `cellpainting-gallery`.
    It contains keys like 'PathNameOrigDNA", necessary to locate specific images.
    It is a single row of the location DataFrames.
    channel : str
        Channel of the image to retrieve.
    correction : str or None
        Type of correction to apply (or None for no correction).
    staging : bool, optional
        Whether to use the "staging-cellpainting-gallery" instead of the public one.
    Default is False. If True, it requires valid credentials in the environment.
    """
    if correction is None:
        correction = "Orig"

    key = correction + channel
    url = image_metadata.get(f"URL_{key}")

    assert url, f"{key} not available for {image_metadata.values}"

    if staging:
        url = url.replace("cellpainting-gallery", "staging-cellpainting-gallery")

    return url


@lru_cache
def read_ldcsv_s3(path: str, lazy: bool = False) -> pl.DataFrame or pl.LazyFrame:
    """
    Read `load data csv` file from S3 onto memory.

    Parameters
    ----------
    path : str
        S3 path location.
    lazy : bool
        Whether to load lazily or not. The mechanisms changes depending on how
        the data is to be loaded. Warning: Lazy-loading does not work
        specifically for the datasets that contain image information.

    Notes
    -----
    Returns all columns as strings. See below for details:
    `https://github.com/jump-cellpainting/datasets/issues/147#issuecomment-2648272358`

    """
    if lazy:
        result = pl.scan_csv(path)
    else:
        result = pl.read_csv(path)

    return result.with_columns(pl.all().cast(pl.String))
