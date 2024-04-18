from pathlib import Path

import pandas as pd
from tqdm import tqdm

from jump.biokg import get_gene_interactions as get_biokg
from jump.hetionet import get_gene_interactions as get_hetionet
from jump.ncbi import get_synonyms
from jump.openbiolink import get_gene_interactions as get_openbiolink
from jump.pharmebinet import get_gene_interactions as get_pharmebinet
from jump.primekg import get_gene_interactions as get_primekg
from jump.utils import load_gene_ids


def concat_annotations(output_dir: str, overwrite: bool = False) -> pd.DataFrame:
    """Aggregate gene interactions from all sources
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
    filepath = Path(output_dir) / "gene_interactions.parquet"
    if filepath.is_file() and not overwrite:
        return pd.read_parquet(filepath)
    datasets_d = {}
    annots = (
        "biokg",
        "primekg",
        "pharmebinet",
        "openbiolink",
        "hetionet",
        # "drkg",
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

    # Fill genes with synonyms from ncbi
    synonyms = get_synonyms(output_dir)
    gene_ids = load_gene_ids()
    for colname in "target_a", "target_b":
        query = (
            f'not {colname} in @gene_ids["Approved_symbol"] '
            f'and {colname} in @synonyms["Synonyms"]'
        )
        mappable = annotations.query(query)
        mapper = synonyms.query(f"Synonyms.isin(@mappable.{colname})")
        mapper = mapper.set_index("Synonyms")["Symbol"]
        mappable = mappable[colname].map(mapper)
        annotations.loc[mappable.index, colname] = mappable.values
    annotations = annotations.reset_index(drop=True).copy()
    annotations.to_parquet(filepath, index=False)
    return annotations
