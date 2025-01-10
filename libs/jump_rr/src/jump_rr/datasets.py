"""Import morphological profiles using the manifest on github."""

import polars as pl
import pooch


def get_dataset(dataset: str, return_pooch: bool = True):
    # Convenience function to retrieve pooched dataframes
    manifest = pl.read_csv(
        "https://raw.githubusercontent.com/jump-cellpainting/datasets/50cd2ab93749ccbdb0919d3adf9277c14b6343dd/manifests/profile_index.csv"
    )

    md5s = {
        "crispr": "019cd1b767db48dad6fbab5cbc483449a229a44c2193d2341a8d331d067204c8",
        "orf": "32f25ee6fdc4dcfa3349397ddf0e1f6ca2594001b8266c5dc0644fa65944f193",
        "crispr_interpretable": "6153c9182faf0a0a9ba22448dfa5572bd7de9b943007356830304834e81a1d05",
        "orf_interpretable": "ae3fea5445022ebd0535fcbae3cfbbb14263f63ea6243f4bac7e4c384f8d3bbf",
    }
    result = manifest.filter(pl.col("subset") == dataset)[0, 1]
    if return_pooch:
        result = pooch.retrieve(result, md5s[dataset])

    return result
