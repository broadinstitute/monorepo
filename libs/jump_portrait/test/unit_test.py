#!/usr/bin/env jupyter
from itertools import groupby, starmap

import numpy as np
import pytest

from jump_portrait.fetch import get_item_location_info, get_jump_image_batch
from jump_portrait.s3 import get_image_from_s3uri


@pytest.mark.parametrize("gene", ["MYT1"])
def test_get_item_location(gene) -> None:
    # Check that finding image locations from gene or compounds works
    result = get_item_location_info(gene).shape
    assert result[0] > 1
    assert result[1] == 28


@pytest.mark.parametrize(
    "s3_image_uri",
    [
        "s3://cellpainting-gallery/cpg0016-jump/source_10/images/2021_08_17_U2OS_48_hr_run16/images/Dest210809-134534/Dest210809-134534_P24_T0001F006L01A02Z01C02.tif",
        "s3://cellpainting-gallery/cpg0016-jump/source_10/images/2021_08_17_U2OS_48_hr_run16/illum/Dest210809-134534/Dest210809-134534_IllumMito.npy",
    ],
)
def test_get_image(s3_image_uri) -> None:
    assert len(get_image_from_s3uri(s3_image_uri)), "Image fetched is empty"


@pytest.fixture
def get_metadata():
    metadata = get_item_location_info("MYT1")
    return metadata.select(
        [
            "Metadata_Source",
            "Metadata_Batch",
            "Metadata_Plate",
            "Metadata_Well",
        ]
    ).unique()


@pytest.mark.parametrize(
    "channel,site", [(["DNA", "AGP", "Mito", "ER", "RNA"], [str(i) for i in range(8)])]
)
@pytest.mark.parametrize("correction", ["Orig", "Illum"])
def test_get_jump_image_batch(get_metadata, channel, site, correction) -> None:
    iterable, img_list = get_jump_image_batch(
        get_metadata, channel, site, correction, verbose=False
    )
    mask = [x is not None for x in img_list]

    # verify that there is an output for every input parameter stored in iterable
    assert len(iterable) == len(img_list)

    # verify that images retrieved are not all None
    assert sum(mask) != len(img_list)

    # verify we retrieve 2d img
    iterable_filt = [param for i, param in enumerate(iterable) if mask[i]]
    img_list_filt = [param for i, param in enumerate(img_list) if mask[i]]
    assert sum([len(img.shape) == 2 for img in img_list_filt]) == len(iterable_filt)

    # caution with the following test:
    # it might be too restrictive as there could be one channel missing for an img (Should not happen theoretically)
    # stack img per channel and assert img.shape[0] == len(channel)
    zip_iter_img = sorted(
        zip(iterable_filt, img_list_filt),
        key=lambda x: (x[0][0], x[0][1], x[0][2], x[0][3], x[0][5], x[0][4]),
    )
    iterable_stack, img_stack = map(
        lambda tup: list(tup),
        zip(
            *starmap(
                lambda key, param_img: (
                    key,
                    np.stack(list(map(lambda x: x[1], param_img))),
                ),
                # grouped image are returned as the common key, and then the zip of param and img, so we retrieve the img then we stack
                groupby(
                    zip_iter_img,
                    key=lambda x: (x[0][0], x[0][1], x[0][2], x[0][3], x[0][5]),
                ),
            )
        ),
    )

    assert sum([img.shape[0] == len(channel) for img in img_stack]) == len(
        iterable_stack
    )

    # NB: no test is done on the number of image retrieved per sample to assess if it is equal
    # to the number of site as this is not always the case.
