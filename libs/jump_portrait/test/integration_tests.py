#!/usr/bin/env jupyter

import pytest
from jump_portrait.fetch import get_jump_image


@pytest.mark.parametrize("source", ["source_10"])
@pytest.mark.parametrize("batch", ["2021_08_17_U2OS_48_hr_run16"])
@pytest.mark.parametrize("plate", ["Dest210809-134534"])
@pytest.mark.parametrize("well", ["A01"])
@pytest.mark.parametrize("channel", ["DNA", "AGP", "Mito", "ER", "RNA"])
@pytest.mark.parametrize("site", [1])
@pytest.mark.parametrize("correction", ["Orig", "Illum"])
@pytest.mark.parametrize("apply_correction", [True, False])
@pytest.mark.parametrize(
    ("compressed", "staging"),
    [(True, True), (False, False)]
)
def test_get_jump_image(
    source, batch, plate, well, channel, site, correction, apply_correction, compressed, staging
):
    # Check that finding image locations from gene or compoundsa works
    image = get_jump_image(
        source, batch, plate, well, channel, site, correction,
        apply_correction, compressed, staging
    )
    assert len(image.shape) == 2  # Two-dimensional image
    assert len(image) > 10  # It is large-ish
    assert image.sum() > 0  # Not empty nor nulls


def test_get_corrected_image():
    # TODO add test
    pass


def test_download_image():
    # TODO add test
    pass
