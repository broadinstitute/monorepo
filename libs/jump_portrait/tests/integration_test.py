#!/usr/bin/env jupyter
"""
Test integration of multiple `jump_portrait` components.

Pending tests:
- def test_get_corrected_image() -> None:
- def test_download_image() -> None:
"""

from itertools import product

import pytest

from jump_portrait.fetch import get_item_location_info, get_jump_image


@pytest.mark.parametrize(
    ("source", "batch", "plate", "well"),
    [
        ("source_10", "2021_08_17_U2OS_48_hr_run16", "Dest210809-134534", "A01"),
        ("source_3", "CP_32_all_Phenix1", "B40803aW", "B15"),
        ("source_8", "J4", "A1166132", "B21"),
        ("source_5", "JUMPCPE-20210702-Run04_20210703_060202", "APTJUM128", "O04"),
    ],
)
@pytest.mark.parametrize("channel", ["DNA", "AGP", "Mito", "ER", "RNA", "Brightfield"])
@pytest.mark.parametrize("site", [1])
@pytest.mark.parametrize(
    "correction,apply_correction", product(("Orig", "Illum"), ("True", "False"))
)
def test_get_jump_image(
    source: str,
    batch: str,
    plate: str,
    well: str,
    channel: str,
    site: str,
    correction: str,
    apply_correction: bool,
    staging: str = False,  # We do not test the staging prefix
) -> None:
    """
    Tests that finding image locations from gene or compounds works.

    Parameters
    ----------
    source : str
        The source of the image.
    batch : str
        The batch number of the image.
    plate : str
        The plate number of the image.
    well : str
        The well number of the image.
    channel : str
        The channel number of the image.
    site : str
        The site number of the image.
    correction : str
        The correction to be applied to the image.
    apply_correction : bool
        Whether or not to apply the correction.
    staging : str
        The staging area for the image.

    Returns
    -------
    None

    Notes
    -----
    This function checks that the get_jump_image function returns a valid 2D image.

    """
    # This source does not have brightfield
    if source == "source_8" and channel == "Brightfield":
        return None

    # Check that finding image locations from gene or compounds works
    image = get_jump_image(
        source,
        batch,
        plate,
        well,
        channel,
        site,
        correction,
        apply_correction,
        staging,
    )
    assert len(image.shape) == 2  # Two-dimensional image
    assert len(image) > 10  # It is large-ish
    assert image.sum() > 0  # Not empty nor nulls

    return None


@pytest.mark.xfail
@pytest.mark.xfail
def test_negcon_image_metadata(item_name: str = "JCP2022_033924") -> None:
    """
    Test that all the negative controls (DMSO) can be located.

    This ensures that the number of negative controls do not crash the program.

    Parameters
    ----------
    item_name : str
        The name of the item to test (default is "JCP2022_03924").

    Returns
    -------
    None

    Notes
    -----
    Calls get_item_location_info function with input_column as "JCP2022".
    FIXME: Add support to this function.

    """
    get_item_location_info(item_name, input_column="JCP2022")

    return None
