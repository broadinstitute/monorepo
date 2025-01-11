from pathlib import Path

import pandas as pd
from tqdm import tqdm

from jump_compound_annotator.collate_gene import fill_with_synonyms


def concat_annotations(output_dir: str, redownload: bool) -> pd.DataFrame:
    """Aggregate annotations from all sources

    Parameters
    ----------
    output_dir : str
        Where to store output files.
    redownload : bool
        If True redownload files

    Returns
    -------
    pd.Dataframe

    Examples
    --------
    FIXME: Add docs.
    """
    filepath = Path(output_dir) / "annotations.parquet"
    if filepath.is_file() and not redownload:
        return pd.read_parquet(filepath)

    datasets_d = {}
    pbar = tqdm(
        [
            "biokg",
            "primekg",
            "pharmebinet",
            "openbiolink",
            "opentargets",
            "hetionet",
            "dgidb",
            "drugrep",
        ]
    )
    for annot in pbar:
        pbar.set_description(f"Downloading {annot}")
        datasets_d[annot] = eval(f"get_{annot}(output_dir, {redownload})")
        datasets_d[annot]["database"] = annot
    dframe = pd.concat(datasets_d.values()).reset_index(drop=True)
    dframe["target"] = fill_with_synonyms(output_dir, dframe["target"], redownload)
    dframe.to_parquet(filepath)
    return dframe
