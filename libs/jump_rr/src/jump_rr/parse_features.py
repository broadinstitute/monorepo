#!/usr/bin/env jupyter
import re

import polars as pl


def get_feature_groups(cols):
    """
    Group features in a consistent manner
    apples with apples, oranges with oranges
    Two cases
    - Channel-based
    - Non-channel based shape

    Apply regular expressions
    Convert to format MASK,FEATURE,CHANNEL(opt),SUFFIX, merging channels
    where necessary
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

    results = [(std.findall(x) or chless.findall(x))[0] for x in cols]
    results = [
        (x[0], "".join(x[1:3]), "", x[3])
        if len(x) < 5
        else (*x[:2], "".join(x[2:4]), x[4])
        for x in results
    ]

    # Select Mask, Feature and Channel features
    feature_meta = pl.DataFrame(
        [x[:3] for x in results],
        schema=[("Mask", str), ("Feature", str), ("Channel", str)],
    )

    return feature_meta
