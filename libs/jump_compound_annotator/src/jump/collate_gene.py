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


def fill_with_synonyms(output_dir, codes):
    """Fill in-place missing gene_ids with synonyms from ncbi"""
    codes = codes.copy()
    synonyms = get_synonyms(output_dir)
    gene_ids = load_gene_ids()
    mask = codes.isin(synonyms["Synonyms"]) & (~codes.isin(gene_ids["Approved_symbol"]))
    synmask = synonyms["Synonyms"].isin(codes[mask])
    mapper = synonyms[synmask].set_index("Synonyms")["Symbol"]
    codes[mask] = codes[mask].apply(lambda x: mapper.get(x, x))
    return codes


def concat_annotations(output_dir: str, overwrite: bool = False) -> pd.DataFrame:
    """Aggregate gene interactions from all sources"""
    filepath = Path(output_dir) / "gene_interactions.parquet"
    if filepath.is_file() and not overwrite:
        return pd.read_parquet(filepath)

    datasets_d = {}
    pbar = tqdm(["biokg", "primekg", "pharmebinet", "openbiolink", "hetionet"])
    for annot in pbar:
        pbar.set_description(f"Downloading {annot}")
        datasets_d[annot] = eval(f"get_{annot}(output_dir)")
        datasets_d[annot]["database"] = annot
    dframe = pd.concat(datasets_d.values()).reset_index(drop=True)
    dframe["target_a"] = fill_with_synonyms(output_dir, dframe["target_a"])
    dframe["target_b"] = fill_with_synonyms(output_dir, dframe["target_b"])
    dframe.to_parquet(filepath, index=False)

    return dframe
