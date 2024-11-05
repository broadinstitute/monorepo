#!/usr/bin/env jupyter
import re
from functools import cache

import polars as pl


@cache
def get_feature_groups(
    feature_fullnames: tuple[str], feature_names: tuple[str]
) -> pl.DataFrame:
    """
    Group features in a consistent manner
    apples with apples, oranges with oranges
    Two cases
    - Channel-based
    - Non-channel based shape

    Apply regular expressions
    Convert to format MASK,FEATURE,CHANNEL(opt),SUFFIX, merging channels
    where necessary
    NOTE: CURRENTLY UNUSED in favour of processing all features
    """
    masks = "|".join(("Cells", "Nuclei", "Cytoplasm", "Image"))
    channels = "|".join(
        (
            "DNA",
            "AGP",
            "RNA",
            "ER",
            "Mito",
            "Image",
        )
    )
    chless_feats = "|".join(
        (
            "AreaShape",
            "Neighbors",
            "RadialDistribution",
            "Location",
            "Count",
            "Number",
            "Parent",
            "Children",
            "ObjectSkeleton",
            "Threshold",
        )
    )

    std = re.compile(f"({masks})_(\S+)_(Orig)?({channels})(_.*)?")
    chless = re.compile(f"({masks})_({chless_feats})_?([a-zA-Z]+)?(.*)?")

    results = [(std.findall(x) or chless.findall(x))[0] for x in feature_fullnames]
    results = [
        (x[0], "".join(x[1:3]), "", x[3])
        if len(x) < 5
        else (*x[:2], "".join(x[2:4]), x[4])
        for x in results
    ]

    # Select Mask, Feature and Channel features
    feature_meta = pl.DataFrame(
        [x for x in results],
        schema=[(col, str) for col in feature_names],
    )

    return feature_meta
