"""
Tools to Search for files in AWS's CellPainting Gallery.

S3_BUCKET_NAME = "cellpainting-gallery"
prefix = "/cpg0020-varchamp/broad/images/".

"""

import os
import re
from io import BytesIO
from pathlib import Path

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
        response = s3client(use_credentials=staging).get_object(
            Bucket=bucket_name, Key=s3_image_uri
        )
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
    image_paths: dict,
    channel: str,
    correction: str or None,
    apply_correction: bool = True,
    compressed: bool = False,
    staging: bool = False,
) -> np.ndarray:
    """
    Retrieve and correct an image from a specified location.

    Parameters
    ----------
    image_paths : dict
        Dictionary containing image locations.
    channel : str
        Channel of the image to retrieve.
    correction : str or None
        Type of correction to apply (or None for no correction).
    apply_correction : bool, optional
        Whether to apply the correction (default is True).
    compressed : bool, optional
        Whether the image is compressed (default is False).
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
        image_paths=image_paths,
        channel=channel,
        correction=correction,
        compressed=compressed,
        staging=staging,
    )

    result = get_image_from_s3uri(s3_image_path, s3_image_path.bucket, staging=staging)

    if apply_correction and correction not in ("Orig", None):
        original_image_path = build_s3_image_path(
            image_paths=image_paths, channel=channel, correction="Orig"
        )
        result = get_image_from_s3uri(original_image_path) / result

    return result


def build_s3_image_path(
    image_paths: dict[str, str],
    channel: str,
    correction: None or str = None,
    compressed: bool = False,
    staging: bool = False,
) -> PureS3Path:
    """
    Build the path for an image on cellpainting gallery's S3 bucket.

    image_location : dict[str, str]
        Dictionary containing the location of images on `cellpainting-gallery`.
    It contains keys like 'PathNameOrigDNA", necessary to locate specific images.
    It is a single row of the location DataFrames.
    channel : str
        Channel of the image to retrieve.
    correction : str or None
        Type of correction to apply (or None for no correction).
    compressed : bool, optional
        Whether the image is compressed (default is False).
    staging : bool, optional
        Whether to use the "staging-cellpainting-gallery" instead of the public one.
    Default is False. If True, it requires valid credentials in the environment.
    """
    if correction is None:
        correction = "Orig"

    use_bf_channel = None
    # Special case to fetch bright field images (Fails if non-existent)
    if channel == "bf":
        use_bf_channel = True
        channel, correction = "DNA", "Orig"

    index_suffix = correction + channel

    directory = image_paths["_".join(("PathName", index_suffix))]
    filename = Path(image_paths["_".join(("FileName", index_suffix))])

    if staging:
        directory = directory.replace(
            "cellpainting-gallery", "staging-cellpainting-gallery"
        )
    if compressed:
        pattern = r"(images/[^/]+)/(images)/.*"
        replacement = r"\1/\2_compressed/" + image_paths["Metadata_Plate"] + "/"
        directory = re.sub(pattern, replacement, directory)
        filename = filename.parent / filename.stem + ".png"
    if use_bf_channel:  # Replace the image with the bright field channel
        channel_ids = [
            int(v[-5]) for k, v in image_paths.items() if k.startswith("FileName_Orig")
        ]
        # the one channel not present
        bf_id = list(set(range(1, 7)).difference(channel_ids))[0]
        filename_as_lst = list(filename)
        filename_as_lst[-5] = str(bf_id)
        filename_as_lst[-11] = "4"  # I found that C06 finishes with A04
        filename = "".join(filename_as_lst)

    final_path = S3Path.from_uri(directory) / filename

    return final_path


def read_parquet_s3(path: str, lazy: bool = False) -> pl.DataFrame or pl.LazyFrame:
    """
    Read parquet file from S3 onto memory.

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
        # This can be simplified once the datasets are fixed:
        # https://github.com/jump-cellpainting/datasets-private/issues/83
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
