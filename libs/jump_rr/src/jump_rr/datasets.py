"""Import morphological profiles using the manifest on github."""

import json
from urllib.request import urlopen

import polars as pl
import pooch


def get_dataset(dataset: str, return_pooch: bool = True) -> pl.DataFrame or str:
    """
    Retrieve the latest morphological profiles using standard names.

    Available datasets can be found on the "subset" column on
    https://github.com/jump-cellpainting/datasets/blob/main/manifests/profile_index.json

    Parameters
    ----------
    dataset : str
        The name of the dataset to be retrieved.
    return_pooch : bool, optional
        Whether to download the result to a temporal directory result. Defaults to True.

    Returns
    -------
    pl.DataFrame or str
        The retrieved dataframe or the path to the file if return_pooch is False.

    Notes
    -----
    This function uses a predefined manifest and md5s dictionary to filter and retrieve the dataset.

    """
    md5s = {
        "compound": "1dd9b76ce9635cc98ea2c6a58f4c1d6ed6aafc1a3990ddcb997162d16582c00f",
        "crispr": "019cd1b767db48dad6fbab5cbc483449a229a44c2193d2341a8d331d067204c8",
        "orf": "32f25ee6fdc4dcfa3349397ddf0e1f6ca2594001b8266c5dc0644fa65944f193",
        "crispr_interpretable": "6153c9182faf0a0a9ba22448dfa5572bd7de9b943007356830304834e81a1d05",
        "orf_interpretable": "ae3fea5445022ebd0535fcbae3cfbbb14263f63ea6243f4bac7e4c384f8d3bbf",
        "compound_interpretable": "42028e8c60692df545e0b1dd087fc9b911f5117c318a8819d768cff251e4edda",
    }
    result = get_profiles_url(dataset)

    if return_pooch:
        result = pooch.retrieve(result, md5s[dataset])

    return result


def get_profiles_url(dataset: str) -> str:
    """Select the correct url."""
    with urlopen(
        "https://raw.githubusercontent.com/jump-cellpainting/datasets/99b8501e2da16bb01792124df22d23ce7aa93668/manifests/profile_index.json"
    ) as url:
        data = json.load(url)
    for entry in data:
        if entry["subset"] == dataset:
            return entry["url"]
