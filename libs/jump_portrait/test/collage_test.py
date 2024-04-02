#!/usr/bin/env jupyter

import pytest
from jump_portrait.fetch import get_collage


@pytest.mark.parametrize("gene", ["MYT1"])
@pytest.mark.parametrize("channel", ["DNA"])
@pytest.mark.parametrize("plate_type", ["ORF", "CRISPR"])
def test_get_collage(gene: str, channel: str, plate_type: str):
    result = get_collage(gene, channel, plate_type, input_column="standard_key")
    rows, cols = result.shape
    assert not rows % 2, "Rows are not paired"
    assert cols > 1000, "y-axis is smaller than expected of multiple images"
