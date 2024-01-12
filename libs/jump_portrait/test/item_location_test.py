#!/usr/bin/env jupyter
import pytest
from jump_portrait.fetch import get_item_location_info


@pytest.mark.parametrize("gene", ["MYT1"])
@pytest.mark.parametrize("control", [True, False])
def test_get_item_location(gene, control):
    # Check that finding image locations from gene or compoundsa works
    result = get_item_location_info(gene, control).shape
    assert result[0] > 1
    assert result[1] == 28
