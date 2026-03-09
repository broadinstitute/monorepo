#!/usr/bin/env jupyter
"""Test the unit components."""

from itertools import groupby, product, starmap

import numpy as np
import pyarrow
import pytest
from jump_portrait.fetch import (
    get_item_location_metadata,
    get_jump_image,
    get_jump_image_batch,
)
from jump_portrait.s3 import get_image_from_s3uri


@pytest.mark.parametrize(
    "pert",
    ["MYT1", "CLETVKMYAXARPO-UHFFFAOYSA-N"],
)
def test_get_item_location(pert: str) -> None:
    """Check that finding image locations from pert."""
    result_shape = get_item_location_metadata(pert).shape
    assert result_shape[0] > 1


@pytest.mark.parametrize(
    "s3_image_uri",
    [
        "s3://cellpainting-gallery/cpg0016-jump/source_10/images/2021_08_17_U2OS_48_hr_run16/images/Dest210809-134534/Dest210809-134534_P24_T0001F006L01A02Z01C02.tif",
        "s3://cellpainting-gallery/cpg0016-jump/source_10/images/2021_08_17_U2OS_48_hr_run16/illum/Dest210809-134534/Dest210809-134534_IllumMito.npy",
    ],
)
def test_get_image(s3_image_uri: str) -> None:
    """Tests whether an image can be successfully retrieved from S3."""
    result_len = len(get_image_from_s3uri(s3_image_uri))
    assert result_len, "Image fetched is empty"


@pytest.fixture
def get_sample_location(item: str = "MYT1") -> pyarrow.lib.RecordBatch:
    metadata = get_item_location_metadata(item)
    return metadata.to_batches()[0]


@pytest.mark.parametrize(
    "channel,site",
    product(
        ["DNA", "AGP", "Mito", "ER", "RNA"],
        (1, 5, 8),
    ),
)
def test_get_jump_image(
    get_sample_location: dict[str, str],
    channel: str,
    site: str,
) -> None:
    unique_sample_location = [
        get_sample_location.to_pylist()[0][f"Metadata_{x}"]
        for x in ("Source", "Batch", "Plate", "Well")
    ]
    image = get_jump_image(*unique_sample_location, channel, site)
    x, y = image.shape

    assert x == 1080, "Wrong x axis size"
    assert y >= 1080, "Wrong y axis size"


@pytest.mark.parametrize(
    "channel,site", [(["DNA", "AGP", "Mito", "ER", "RNA"], [x for x in (1, 5, 8)])]
)
def test_get_jump_image_batch(
    get_sample_location: dict[str, str], channel: str, site: str
) -> None:
    """Test pulling images in batches and dealing with potentially missing values."""
    iterable, img_list = get_jump_image_batch(get_sample_location, channel, site)

    mask = [x is not None for x in img_list]
    # verify that there is an output for every input parameter stored in iterable
    assert len(iterable) == len(img_list)

    # verify that images retrieved are not all None
    assert sum(mask) == len(img_list)

    # verify we retrieve 2d images
    iterable_filt = [param for i, param in enumerate(iterable) if mask[i]]
    img_list_filt = [param for i, param in enumerate(img_list) if mask[i]]
    assert sum([img.ndim == 2 for img in img_list_filt]) == len(iterable_filt)

    # NOTE: @HugoHakem: Caution with the following test:
    # it might be too restrictive as there could be one channel missing
    # Though in theory this should not happen
    # stack img per channel and assert img.shape[0] == len(channel)
    identifiers = ("Source", "Batch", "Plate", "Well", "Site")
    zip_iter_img = sorted(
        zip(iterable_filt, img_list_filt),
        key=lambda x: (*[x[0][f"Metadata_{k}"] for k in identifiers],),
    )
    iterable_stack, img_stack = map(
        lambda tup: list(tup),
        zip(
            *starmap(
                lambda key, param_img: (
                    key,
                    np.stack(list(map(lambda x: x[1], param_img))),
                ),
                # grouped images are returned as the common key, and then the zip of param and img, so we retrieve the img then we stack
                groupby(
                    zip_iter_img,
                    key=lambda x: (*[x[0][f"Metadata_{k}"] for k in identifiers],),
                ),
            )
        ),
    )

    assert sum([img.shape[0] == len(channel) for img in img_stack]) == len(
        iterable_stack
    )

    # NB: no test is done on the number of image retrieved per sample to assess if it is
    # equal to the number of site as this is not always the case.
