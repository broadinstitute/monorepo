"""
Test urls and (optionally) that the downloaded files match the expected hashes.
"""

from pathlib import Path

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
        "compound_no_source7",
    ],
)
def test_url_exists(subset: str) -> None:
    url = get_profiles_url(subset)
    response = requests.head(url)
    assert response.status_code == 200


def test_production_profile_uses_unique_cache_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_url = get_profiles_url("compound_no_source7")
    captured = {}

    def fake_retrieve(url: str, known_hash: str, fname: str) -> Path:
        captured.update(url=url, known_hash=known_hash, fname=fname)
        return Path("/tmp") / fname

    monkeypatch.setattr("jump_rr.datasets.pooch.retrieve", fake_retrieve)

    path = get_dataset("compound_no_source7")

    assert path.name == "compound_no_source7.parquet"
    assert captured["url"] == source_url
    assert captured["known_hash"].startswith("8e1e5d9e")


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
        "compound_no_source7",
    ],
)
def test_data_download(subset: str) -> Path:
    """
    Pull data using Pooch and cache it.

    NOTE:
    Requires '--runslow' flag to run.
    """
    path_to_local_data = get_dataset(subset)

    return path_to_local_data
