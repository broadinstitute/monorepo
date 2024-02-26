#!/usr/bin/env jupyter
import pytest
from jump_portrait.fetch import get_item_location_info, get_jump_image


@pytest.mark.parametrize("gene", ["MYT1"])
@pytest.mark.parametrize("control", [True, False])
def test_get_item_location(gene, control):
    # Check that finding image locations from gene or compoundsa works
    result = get_item_location_info(gene, control).shape
    assert result[0] > 1
    assert result[1] == 28


@pytest.mark.parametrize("source", ["source_10"])
@pytest.mark.parametrize("batch", ["2021_08_17_U2OS_48_hr_run16"])
@pytest.mark.parametrize("plate", ["Dest210809-134534"])
@pytest.mark.parametrize("well", ["A01"])
@pytest.mark.parametrize("channel", ["DNA"])
@pytest.mark.parametrize("site", [1])
@pytest.mark.parametrize("correction", ["Orig", "Illum"])
@pytest.mark.parametrize("apply_correction", [True, False])
def test_get_jump_image(
    source, batch, plate, well, channel, site, correction, apply_correction
):
    # Check that finding image locations from gene or compoundsa works
    image = get_jump_image(
        source, batch, plate, well, channel, site, correction, apply_correction
    )
    assert len(image.shape) == 2  # Two-dimensional image
    assert len(image) > 10  # Check that it is a large-ish image
