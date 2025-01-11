from pathlib import Path

import pandas as pd
from tqdm import tqdm

from jump.biokg import get_compound_interactions as get_biokg
from jump.hetionet import get_compound_interactions as get_hetionet
from jump.pharmebinet import get_compound_interactions as get_pharmebinet
from jump.primekg import get_compound_interactions as get_primekg


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
