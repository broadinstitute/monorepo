from pathlib import Path

import pandas as pd
from tqdm import tqdm

from jump_compound_annotator.biokg import get_compound_interactions as get_biokg  # noqa: F401
from jump_compound_annotator.hetionet import get_compound_interactions as get_hetionet  # noqa: F401
from jump_compound_annotator.pharmebinet import (
    get_compound_interactions as get_pharmebinet,  # noqa: F401
)
from jump_compound_annotator.primekg import get_compound_interactions as get_primekg  # noqa: F401


def concat_annotations(output_dir: str, redownload: bool = False) -> pd.DataFrame:
    """Aggregate compound interactions from all sources"""
    filepath = Path(output_dir) / "compound_interactions.parquet"
    if filepath.is_file() and not redownload:
        return pd.read_parquet(filepath)

    datasets_d = {}
    pbar = tqdm(["biokg", "primekg", "pharmebinet", "hetionet"])
    for annot in pbar:
        pbar.set_description(f"Processing {annot}")
        datasets_d[annot] = eval(f"get_{annot}(output_dir, redownload)")
        datasets_d[annot]["database"] = annot
    df = pd.concat(datasets_d.values()).reset_index(drop=True)

    df.reset_index(inplace=True, drop=True)
    df.to_parquet(filepath, index=False)
    return df
