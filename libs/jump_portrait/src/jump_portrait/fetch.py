#!/usr/bin/env jupyter
"""
Functions to get JUMP-CP images from AWS's s3://cellpainting-gallery.

Based on github.com/jump-cellpainting/datasets/blob/baacb8be98cfa4b5a03b627b8cd005de9f5c2e70/sample_notebook.ipynb
"""
import os
from io import BytesIO

import boto3
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import pandas as pd
import pooch
import requests
from botocore import UNSIGNED
from botocore.config import Config
from s3path import S3Path

METADATA_LOCATION = (
    "https://github.com/jump-cellpainting/datasets/raw/"
    "baacb8be98cfa4b5a03b627b8cd005de9f5c2e70/metadata/"
    "{}.csv.gz"
)
METAFILE_HASH = {
    "compound": "a6e18f8728ab018bd03fe83e845b6c623027c3baf211e7b27fc0287400a33052",
    "well": "677d3c1386d967f10395e86117927b430dca33e4e35d9607efe3c5c47c186008",
    "crispr": "979f3c4e863662569cc36c46eaff679aece2c4466a3e6ba0fb45752b40d2bd43",
    "orf": "fbd644d8ccae4b02f623467b2bf8d9762cf8a224c169afa0561fedb61a697c18",
    "plate": "745391d930627474ec6e3083df8b5c108db30408c0d670cdabb3b79f66eaff48",
}

METADATA = {
    _file: pd.read_csv(
        pooch.retrieve(url=METADATA_LOCATION.format(_file), known_hash=_hash)
    )
    for _file, _hash in METAFILE_HASH.items()
}


profile_formatter = (
    "s3://cellpainting-gallery/cpg0016-jump/"
    "{Metadata_Source}/workspace/profiles/"
    "{Metadata_Batch}/{Metadata_Plate}/{Metadata_Plate}.parquet"
)

loaddata_formatter = (
    "s3://cellpainting-gallery/cpg0016-jump/"
    "{Metadata_Source}/workspace/load_data_csv/"
    "{Metadata_Batch}/{Metadata_Plate}/load_data_with_illum.parquet"
)
sample = (
    METADATA["plate"]
    .query('Metadata_PlateType=="TARGET2"')
    .groupby("Metadata_Source")
    .sample(2, random_state=42)
)
s3_path = loaddata_formatter.format(**sample.iloc[0].to_dict())
parquet_meta = pd.read_parquet(s3_path, storage_options={"anon": True})

S3_client = boto3.client("s3", config=Config(signature_version=UNSIGNED))


def build_s3_image_path(
    row: pd.Series, channel: str, correction: str or None = None
) -> S3Path:
    """ """
    if correction is None:
        correction = "Orig"
    index_suffix = correction + channel
    return (
        S3Path.from_uri(row["_".join(("PathName", index_suffix))])
        / row["_".join(("FileName", index_suffix))]
    )


def get_image_from_s3path(s3_image_path):
    response = s3_client.get_object(Bucket=s3_image_path.bucket, Key=s3_image_path.key)
    return mpimg.imread(BytesIO(response["Body"].read()), format="tiff")


def get_jump_image(
    source: str,
    batch: str,
    plate: str,
    well: str,
    site: int,
    channel: str,
    correction: str = None,
):
    s3_location_frame_uri = loaddata_formatter.format(
        Metadata_Source=source, Metadata_Batch=batch, Metadata_Plate=plate
    )
    location_frame = pd.read_parquet(
        s3_location_frame_uri, storage_options={"anon": True}
    )
    unique_site = location_frame.loc[
        (location_frame["Metadata_Well"] == well)
        & (location_frame["Metadata_Site"] == str(site))
    ]
    assert len(unique_site) == 1, "More than one site found"
    s3_image_path = build_s3_image_path(
        row=unique_site.iloc[0], channel=channel, correction=correction
    )
    return get_image_from_s3path(s3_image_path)
