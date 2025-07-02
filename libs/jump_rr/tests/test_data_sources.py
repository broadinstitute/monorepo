"""
Test urls and (optionally) that the downloaded files match the expected hashes.
"""

import pytest
import requests

from jump_rr.datasets import get_dataset, get_profiles_url


@pytest.mark.parametrize(
    "subset",
    [
        "orf",
        "crispr",
        "compound",
        "orf_interpretable",
        "crispr_interpretable",
        "compound_interpretable",
    ],
)
def test_url_exists(subset: str):
    url = get_profiles_url(subset)
    response = requests.head(url)
    assert response.status_code == 200


@pytest.mark.slow
@pytest.mark.parametrize(
    "subset",
    [
        "orf",
        "crispr",
        "compound",
        "orf_interpretable",
        "crispr_interpretable",
        "compound_interpretable",
    ],
)
def test_data_download(subset: str):
    """
    Pull data using Pooch and cache it.

    NOTE:
    Requires '--runslow' flag to run.
    """
    path_to_local_data = get_dataset(subset)
