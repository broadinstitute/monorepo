from pathlib import Path

import pandas as pd
from tqdm import tqdm

from jump.biokg import get_compound_annotations as get_biokg
from jump.collate_compounds import get_inchikeys
from jump.collate_gene import fill_with_synonyms
from jump.dgidb import get_compound_annotations as get_dgidb
from jump.drugrep import get_compound_annotations as get_drugrep
from jump.hetionet import get_compound_annotations as get_hetionet
from jump.openbiolink import get_compound_annotations as get_openbiolink
from jump.pharmebinet import get_compound_annotations as get_pharmebinet
from jump.primekg import get_compound_annotations as get_primekg


def concat_annotations(output_dir: str, overwrite: bool = False) -> pd.DataFrame:
    """Aggregate annotations from all sources

    Parameters
    ----------
    output_dir : str
        Where to store output files.
    overwrite : bool
        If True do not redownload files

    Returns
    -------
    pd.Dataframe

    Examples
    --------
    FIXME: Add docs.
    """
    filepath = Path(output_dir) / "annotations.parquet"
    if filepath.is_file() and not overwrite:
        return pd.read_parquet(filepath)

    datasets_d = {}
    pbar = tqdm(
        [
            "biokg",
            "primekg",
            "pharmebinet",
            "openbiolink",
            "hetionet",
            "dgidb",
            "drugrep",
        ]
    )
    for annot in pbar:
        pbar.set_description(f"Downloading {annot}")
        datasets_d[annot] = eval(f"get_{annot}(output_dir)")
        datasets_d[annot]["database"] = annot
    dframe = pd.concat(datasets_d.values()).reset_index(drop=True)
    dframe["target"] = fill_with_synonyms(output_dir, dframe["target"])
    dframe["inchikey"] = get_inchikeys(
        output_dir, dframe["source_id"], dframe["source"]
    )
    dframe.to_parquet(filepath)
    return dframe
