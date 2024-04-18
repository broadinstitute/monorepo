from pathlib import Path

import pandas as pd
from tqdm import tqdm

from jump.biokg import get_compound_interactions as get_biokg
from jump.hetionet import get_compound_interactions as get_hetionet
from jump.mychem import get_inchi_annotations as mychem_annotations
from jump.pharmebinet import get_compound_interactions as get_pharmebinet
from jump.primekg import get_compound_interactions as get_primekg
from jump.unichem import get_inchi_annotations as unichem_annotations


def concat_annotations(output_dir: str, overwrite: bool = False) -> pd.DataFrame:
    """Aggregate compound interactions from all sources

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
    filepath = Path(output_dir) / "compound_interactions.parquet"
    if filepath.is_file() and not overwrite:
        return pd.read_parquet(filepath)
    datasets_d = {}
    annots = (
        "biokg",
        "primekg",
        "pharmebinet",
        # "drkg",
        "hetionet",
    )
    pbar = tqdm(annots)
    for annot in pbar:
        pbar.set_description(f"Downloading {annot}")
        datasets_d[annot] = eval(f"get_{annot}(output_dir)")

    annotations = []
    for name, ds in datasets_d.items():
        ds["database"] = name
        annotations.append(ds)
    annotations = pd.concat(annotations).reset_index(drop=True)

    # Map IDs from source_a to inchikeys
    df_unichem = unichem_annotations(output_dir, annotations.copy(), "source_a")
    df_mychem = mychem_annotations(output_dir, annotations.copy(), "source_a")
    df_a = pd.concat([df_mychem, df_unichem])
    df_a.rename(columns={"inchikey": "inchikey_a"}, inplace=True)

    # Map IDs from source_b to inchikeys
    df_unichem = unichem_annotations(output_dir, annotations.copy(), "source_b")
    df_mychem = mychem_annotations(output_dir, annotations.copy(), "source_b")
    df_b = pd.concat([df_mychem, df_unichem])
    df_b.rename(columns={"inchikey": "inchikey_b"}, inplace=True)

    df = df_a.drop_duplicates().merge(
        df_b.drop_duplicates(),
        on=["source_a", "source_b", "rel_type", "source_id", "database"],
    )
    df.reset_index(inplace=True, drop=True)
    df.to_parquet(filepath, index=False)
    return df
