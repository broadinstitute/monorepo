#!/usr/bin/env python
"""
Utilities for interacting with S3 buckets, specifically for the Cell Painting Gallery.
This module provides functions to create S3 clients, retrieve images as NumPy arrays,
and download files to local storage.
"""

import os
from io import BytesIO
from pathlib import Path

import boto3
import matplotlib.image as mpimg
import numpy as np
from botocore import UNSIGNED
from botocore.config import Config
from matplotlib import pyplot as plt


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


def download_s3uri(
    meta: tuple[str, ...],
    output_dir: str,
    path_to_name: bool = True,
) -> bool:
    """
    Download a file from the cellpainting-gallery S3 bucket to a local directory.

    Parameters
    ----------
    meta : tuple of str
        A tuple containing metadata components. The last element is treated
        as the S3 key, while the preceding elements are used to construct
        the local filename if `path_to_name` is True.
    output_dir : str
        The local directory where the downloaded file will be saved.
    path_to_name : bool, optional
        Determines how the local filename is generated. If True, joins the
        location components with '__' and appends '.tif'. If False, derives
        the name by removing the S3 prefix from the key. Defaults to True.

    Returns
    -------
    bool
        True if the file was downloaded successfully or already exists
        locally. False if an exception occurs during the process.
    """
    *location, key = meta
    clean_key = key.removeprefix("s3://cellpainting-gallery/")
    if path_to_name:
        local_name = "__join".join(map(str, location)) + ".tif"
    else:
        local_name = clean_key
    local_file = Path(output_dir) / local_name

    local_file.parent.mkdir(exist_ok=True, parents=True)
    s3_client = boto3.client("s3", config=Config(signature_version=UNSIGNED))

    try:
        if not local_file.exists():
            s3_client.download_file("cellpainting-gallery", clean_key, str(local_file))
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False
