"""Import morphological profiles using the manifest on github."""

import polars as pl
import pooch

# Mirror of https://github.com/jump-cellpainting/datasets/blob/main/manifests/profile_index.json
# Embedded so dataset resolution does not require a network round-trip.
_PROFILE_INDEX = [
    {
        "subset": "orf",
        "url": "https://cellpainting-gallery.s3.amazonaws.com/cpg0016-jump-assembled/source_all/workspace/profiles_assembled/ORF/v1.0a/profiles_wellpos_cc_var_mad_outlier_featselect_sphering_harmony.parquet",
        "etag": "064759b3a850dc351b357116b3e7b32d",
    },
    {
        "subset": "crispr",
        "url": "https://cellpainting-gallery.s3.amazonaws.com/cpg0016-jump-assembled/source_all/workspace/profiles_assembled/CRISPR/v1.0a/profiles_wellpos_cc_var_mad_outlier_featselect_sphering_harmony_PCA_corrected.parquet",
        "etag": "5903af59605b2037190ff64c1f87c530",
    },
    {
        "subset": "compound",
        "url": "https://cellpainting-gallery.s3.amazonaws.com/cpg0016-jump-assembled/source_all/workspace/profiles_assembled/COMPOUND/v1.0/profiles_var_mad_int_featselect_harmony.parquet",
        "etag": "c9371af57a36a51e021935c9ca78e506",
    },
    {
        "subset": "orf_interpretable",
        "url": "https://cellpainting-gallery.s3.amazonaws.com/cpg0016-jump-assembled/source_all/workspace/profiles_assembled/ORF/v1.0a/profiles_wellpos_cc_var_mad_outlier.parquet",
        "etag": "a2ca4063bbfcee09ac303cf48eb8bafd",
    },
    {
        "subset": "crispr_interpretable",
        "url": "https://cellpainting-gallery.s3.amazonaws.com/cpg0016-jump-assembled/source_all/workspace/profiles_assembled/CRISPR/v1.0a/profiles_wellpos_cc_var_mad_outlier.parquet",
        "etag": "0009a142e5d132d007696ed8f71f2da8",
    },
    {
        "subset": "compound_interpretable",
        "url": "https://cellpainting-gallery.s3.amazonaws.com/cpg0016-jump-assembled/source_all/workspace/profiles_assembled/COMPOUND/v1.0/profiles_var_mad_int.parquet",
        # Multipart-upload etag — not a plain MD5, so hash verification is skipped.
        "etag": "67212e3cbdaa25de511f318cdd0503dc-3",
    },
    {
        "subset": "all",
        "url": "https://cellpainting-gallery.s3.amazonaws.com/cpg0016-jump-assembled/source_all/workspace/profiles_assembled/ALL/v1.0b/profiles_wellpos_cc_var_mad_outlier_featselect_sphering_harmony.parquet",
        "etag": "96eeaeb01ac8eab9845111bd34a6c82d",
    },
    {
        "subset": "all_interpretable",
        "url": "https://cellpainting-gallery.s3.amazonaws.com/cpg0016-jump-assembled/source_all/workspace/profiles_assembled/ALL/v1.0b/profiles_wellpos_cc_var_mad_outlier_featselect.parquet",
        "etag": "29cafe5726408773300eb53619281a1d",
    },
]


def _etag_to_pooch_hash(etag: str) -> str | None:
    """Convert an S3 etag into a pooch-compatible hash string.

    Single-part etags are plain MD5; multipart etags carry a "-N" suffix and
    cannot be verified against the file contents, so they map to None.
    """
    if "-" in etag:
        return None
    return f"md5:{etag}"


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
    Hashes are derived from the S3 etag in the upstream manifest.

    """
    entry = _get_entry(dataset)
    url = entry["url"]

    if return_pooch:
        return pooch.retrieve(url, _etag_to_pooch_hash(entry["etag"]))

    return url


def get_profiles_url(dataset: str) -> str:
    """Select the correct url."""
    return _get_entry(dataset)["url"]


def _get_entry(dataset: str) -> dict:
    for entry in _PROFILE_INDEX:
        if entry["subset"] == dataset:
            return entry
    raise KeyError(f"Unknown dataset subset: {dataset!r}")
