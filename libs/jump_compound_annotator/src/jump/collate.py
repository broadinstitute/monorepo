from pathlib import Path

import pandas as pd
from tqdm import tqdm

from jump.biokg import get_compound_annotations as get_biokg
from jump.dgidb import get_compound_annotations as get_dgidb
from jump.drkg import get_compound_annotations as get_drkg
from jump.drugrep import get_compound_annotations as get_drugrep
from jump.hetionet import get_compound_annotations as get_hetionet
from jump.mychem import get_inchi_annotations as mychem_annotations
from jump.ncbi import get_synonyms
from jump.openbiolink import get_compound_annotations as get_openbiolink
from jump.pharmebinet import get_compound_annotations as get_pharmebinet
from jump.primekg import get_compound_annotations as get_primekg
from jump.unichem import get_inchi_annotations as unichem_annotations
from jump.utils import load_gene_ids


def concat_annotations(
    output_dir: str, overwrite: bool = False
) -> pd.DataFrame:
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
    annots = (
        "biokg",
        "primekg",
        "pharmebinet",
        "openbiolink",
        "hetionet",
        "dgidb",
        "drugrep",
    )
    # "drkg",
    pbar = tqdm(annots)
    for annot in pbar:
        pbar.set_description(f"Downloading {annot}")
        datasets_d[annot] = eval(f"get_{annot}(output_dir)")

    annotations = []
    for name, ds in datasets_d.items():
        ds["database"] = name
        annotations.append(ds)
    annotations = pd.concat(annotations).reset_index(drop=True)

    # Fill genes with synonyms from ncbi
    synonyms = get_synonyms(output_dir)
    gene_ids = load_gene_ids()
    query = (
        'not target in @gene_ids["Approved_symbol"] '
        'and target in @synonyms["Synonyms"]'
    )
    mappable = annotations.query(query)
    mapper = synonyms.query("Synonyms.isin(@mappable.target)")
    mapper = mapper.set_index("Synonyms")["Symbol"]
    mappable = mappable["target"].map(mapper)
    annotations.loc[mappable.index, "target"] = mappable.values
    annotations = annotations.query('target in @gene_ids["Approved_symbol"]')
    annotations = annotations.reset_index(drop=True).copy()
    annotations.to_parquet(filepath)
    return annotations


def get_inchi_annotations(output_dir):
    df_unichem = unichem_annotations(output_dir)
    df_mychem = mychem_annotations(output_dir)
    df = pd.concat([df_mychem, df_unichem]).drop_duplicates()
    df = df.drop_duplicates(["inchikey", "rel_type", "target"])
    df = df.reset_index(drop=True).copy()

    return df
