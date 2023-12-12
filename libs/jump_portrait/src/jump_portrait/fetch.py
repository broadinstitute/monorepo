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
import numpy as np
import pandas as pd
import pooch
import requests
from botocore import UNSIGNED
from botocore.config import Config
from s3path import S3Path

S3_client = boto3.client("s3", config=Config(signature_version=UNSIGNED))

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

METADATA = {}


def get_table(table_name: str) -> pd.DataFrame:
    if "table_name" not in METADATA:
        METADATA[table_name] = pd.read_csv(
            pooch.retrieve(
                url=METADATA_LOCATION.format(table_name),
                known_hash=METAFILE_HASH[table_name],
            )
        )
    return METADATA[table_name]


loaddata_formatter = (
    "s3://cellpainting-gallery/cpg0016-jump/"
    "{Metadata_Source}/workspace/load_data_csv/"
    "{Metadata_Batch}/{Metadata_Plate}/load_data_with_illum.parquet"
)


def get_sample(n: int = 2, seed: int = 42):
    sample = (
        get_table("plate")
        .query('Metadata_PlateType=="TARGET2"')
        .groupby("Metadata_Source")
        .sample(n, random_state=seed)
    )

    s3_path = loaddata_formatter.format(**sample.iloc[0].to_dict())

    parquet_meta = pd.read_parquet(s3_path, storage_options={"anon": True})
    return parquet_meta


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


def get_image_from_s3path(s3_image_path: S3Path) -> np.array:
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
) -> np.ndarray:
    """Main function to fetch a JUMP image for AWS.
    Metadata for most files can be obtained from a set of data frames,
    or generated using (TODO make metadata accessible) from this module.

    Parameters
    ----------
    source : str
        Which collaborator (data source) generated the images.
    batch : str
        Batch name.
    plate : str
        Plate name.
    well : str
        Well number (e.g., A01).
    site : int
        Site identifier (also called foci)
    channel : str
        Channel to fetch, the standard ones are DNA, Mito, ER and AGP.
    correction : str
        Whether or not to use corrected data. It does not by default.

    Returns
    -------
    np.ndarray
        Selected image as a numpy array.

    Examples
    --------
    FIXME: Add docs.

    """
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


from broad_babel import query


def get_gene_location_metadata(gene_name: str) -> pd.DataFrame:
    """
    First search for datasets in which this gene was present.
    Return tuple with its Metadata location in order source, batch, plate,
    well and site.
    """

    # Get plates
    jcp_ids = query.run_query(
        query=gene_name,
        input_column="standard_key",
        output_column="JCP2022,standard_key",
    )
    jcp_gene = {x[0]: x[1] for x in jcp_ids}
    meta_wells = get_table("well")
    found_rows = meta_wells[meta_wells["Metadata_JCP2022"].isin(jcp_gene.keys())].copy()
    found_rows.loc[:, "gene"] = gene_name

    # Get plate metadata with no reference to well and below
    s3_path = loaddata_formatter.format(**sample.iloc[0].to_dict())
    plate_level_metadata = get_table("plate").loc[
        METADATA["plate"]["Metadata_Plate"].isin(found_rows["Metadata_Plate"])
    ]
    merged_metadata = pd.merge(
        plate_level_metadata,
        found_rows.drop("Metadata_Source", axis=1),
        on="Metadata_Plate",
    )
    merged_metadata.columns = [
        x.replace("Metadata_", "").lower() for x in merged_metadata.columns
    ]
    return merged_metadata

    # parquet_meta = pd.read_parquet(s3_path, storage_options={"anon": True})
