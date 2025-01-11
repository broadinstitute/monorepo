from pathlib import Path

import pandas as pd
from tqdm import tqdm

from jump_compound_annotator.ncbi import get_synonyms
from jump_compound_annotator.utils import ncbi_to_symbol
from jump_compound_annotator.biokg import get_gene_interactions as get_biokg  # noqa: F401
from jump_compound_annotator.hetionet import get_gene_interactions as get_hetionet  # noqa: F401
from jump_compound_annotator.openbiolink import get_gene_interactions as get_openbiolink  # noqa: F401
from jump_compound_annotator.pharmebinet import get_gene_interactions as get_pharmebinet  # noqa: F401
from jump_compound_annotator.primekg import get_gene_interactions as get_primekg  # noqa: F401


def fill_with_synonyms(output_dir, codes, redownload: bool):
    """Fill in-place missing gene_ids with synonyms from ncbi"""
    codes = codes.copy()
    synonyms = get_synonyms(output_dir, redownload)
    symbols = ncbi_to_symbol(Path(output_dir), redownload).values
    mask = codes.isin(synonyms["Synonyms"]) & (~codes.isin(symbols))
    synmask = synonyms["Synonyms"].isin(codes[mask])
    mapper = synonyms[synmask].set_index("Synonyms")["Symbol"]
    codes[mask] = codes[mask].apply(lambda x: mapper.get(x, x))
    return codes


def concat_annotations(output_dir: str, redownload: bool) -> pd.DataFrame:
    """Aggregate gene interactions from all sources"""
    filepath = Path(output_dir) / "gene_interactions.parquet"
    if filepath.is_file() and not redownload:
        return pd.read_parquet(filepath)

    datasets_d = {}
    pbar = tqdm(["biokg", "primekg", "pharmebinet", "openbiolink", "hetionet"])
    for annot in pbar:
        pbar.set_description(f"Downloading {annot}")
        datasets_d[annot] = eval(f"get_{annot}(output_dir, {redownload})")
        datasets_d[annot]["database"] = annot
    dframe = pd.concat(datasets_d.values()).reset_index(drop=True)
    dframe["target_a"] = fill_with_synonyms(output_dir, dframe["target_a"], redownload)
    dframe["target_b"] = fill_with_synonyms(output_dir, dframe["target_b"], redownload)
    dframe.to_parquet(filepath, index=False)

    return dframe
