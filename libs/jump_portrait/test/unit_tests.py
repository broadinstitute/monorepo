#!/usr/bin/env jupyter
import pytest
from jump_portrait.fetch import get_item_location_info
from jump_portrait.s3 import get_image_from_s3uri


@pytest.mark.parametrize("gene", ["MYT1"])
@pytest.mark.parametrize("control", [True, False])
def test_get_item_location(gene, control):
    # Check that finding image locations from gene or compounds works
    result = get_item_location_info(gene, control).shape
    assert result[0] > 1
    assert result[1] == 28


@pytest.mark.parametrize(
    "s3_image_uri",
    [
        "s3://cellpainting-gallery/cpg0016-jump/source_10/images/2021_08_17_U2OS_48_hr_run16/images/Dest210809-134534/Dest210809-134534_P24_T0001F006L01A02Z01C02.tif",
        "s3://cellpainting-gallery/cpg0016-jump/source_10/images/2021_08_17_U2OS_48_hr_run16/illum/Dest210809-134534/Dest210809-134534_IllumMito.npy",
    ],
)
def test_get_image(s3_image_uri):
    assert len(get_image_from_s3uri(s3_image_uri)), "Image fetched is empty"
