#!/usr/bin/env jupyter

import pytest
from jump_portrait.fetch import get_jump_image


@pytest.mark.parametrize(("source", "batch", "plate", "well"), [
    ("source_10", "2021_08_17_U2OS_48_hr_run16", "Dest210809-134534", "A01"),
    ("source_3", "CP_32_all_Phenix1", "B40803aW", "B15"),
    ("source_8", "J4", "A1166132", "B21"),
    ("source_5", "JUMPCPE-20210702-Run04_20210703_060202", "APTJUM128", "O04")
])
@pytest.mark.parametrize("channel", ["DNA", "AGP", "Mito", "ER", "RNA"])
@pytest.mark.parametrize("site", [1])
@pytest.mark.parametrize(("correction", "apply_correction"), [
    ("Orig", False), ("Illum", False), ("Illum", True)
])
@pytest.mark.parametrize(
    ("compressed", "staging"),
    [(True, True), (False, False)]
)
def test_get_jump_image(
    source, batch, plate, well, channel, site, correction, apply_correction, compressed, staging
):
    # Check that finding image locations from gene or compounds works
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
