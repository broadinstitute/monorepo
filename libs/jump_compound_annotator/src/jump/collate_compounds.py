from pathlib import Path

import pandas as pd
from tqdm import tqdm

from jump.biokg import get_compound_interactions as get_biokg
from jump.hetionet import get_compound_interactions as get_hetionet
from jump.mychem import get_inchikeys as mychem_inchikeys
from jump.pharmebinet import get_compound_interactions as get_pharmebinet
from jump.primekg import get_compound_interactions as get_primekg
from jump.unichem import get_inchikeys as unichem_inchikeys


def get_inchikeys(output_dir, source_ids, codes):
    """Map ids to inchikeys using unichem and mychem"""
    unichem = unichem_inchikeys(output_dir, source_ids, codes)
    mychem = mychem_inchikeys(output_dir, source_ids, codes)
    inchikeys = unichem.where(~unichem.isna(), mychem)
    return inchikeys


def concat_annotations(output_dir: str, overwrite: bool = False) -> pd.DataFrame:
    """Aggregate compound interactions from all sources"""
    filepath = Path(output_dir) / "compound_interactions.parquet"
    if filepath.is_file() and not overwrite:
        return pd.read_parquet(filepath)

    datasets_d = {}
    pbar = tqdm(["biokg", "primekg", "pharmebinet", "hetionet"])
    for annot in pbar:
        pbar.set_description(f"Processing {annot}")
        datasets_d[annot] = eval(f"get_{annot}(output_dir)")
        datasets_d[annot]["database"] = annot
    df = pd.concat(datasets_d.values()).reset_index(drop=True)

    df["inchikey_a"] = get_inchikeys(output_dir, df["source_id"], df["source_a"])
    df["inchikey_b"] = get_inchikeys(output_dir, df["source_id"], df["source_b"])

    df.reset_index(inplace=True, drop=True)
    df.to_parquet(filepath, index=False)
    return df
