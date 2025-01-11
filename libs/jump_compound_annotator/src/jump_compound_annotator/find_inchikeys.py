from pathlib import Path

import pandas as pd

from jump_compound_annotator.mychem import get_inchikeys as mychem_inchikeys
from jump_compound_annotator.mychem import save_mapper as save_mychem_mapper
from jump_compound_annotator.unichem import get_inchikeys as unichem_inchikeys
from jump_compound_annotator.unichem import save_mapper as save_unichem_mapper


def pull_inchikeys(output_dir, source_ids, codes):
    for source_id in source_ids.unique():
        mask = source_id == source_ids
        unique_codes = codes[mask].drop_duplicates()
        save_unichem_mapper(output_dir, unique_codes, source_id)
        save_mychem_mapper(output_dir, unique_codes, source_id)


def get_inchikeys(output_dir, source_ids, codes):
    """Map ids to inchikeys using unichem and mychem"""
    unichem = unichem_inchikeys(output_dir, source_ids, codes)
    mychem = mychem_inchikeys(output_dir, source_ids, codes)
    inchikeys = unichem.where(~unichem.isna(), mychem)
    return inchikeys


def add_inchikeys(output_dir, redownload=False):
    output_path = Path(output_dir)
    st_labels = pd.read_parquet(output_path / "annotations.parquet")
    ss_labels = pd.read_parquet(output_path / "compound_interactions.parquet")

    all_codes = pd.concat(
        [
            st_labels[["source_id", "source"]],
            ss_labels[["source_id", "source_a", "source_b"]].melt(
                id_vars="source_id",
                value_vars=["source_a", "source_b"],
                value_name="source",
            ),
        ]
    )

    if redownload:
        pull_inchikeys(output_dir, all_codes["source_id"], all_codes["source"])

    st_labels["inchikey"] = get_inchikeys(
        output_dir, st_labels["source_id"], st_labels["source"]
    )
    ss_labels["inchikey_a"] = get_inchikeys(
        output_dir, ss_labels["source_id"], ss_labels["source_a"]
    )
    ss_labels["inchikey_b"] = get_inchikeys(
        output_dir, ss_labels["source_id"], ss_labels["source_b"]
    )
    st_labels.to_parquet(output_path / "annotations.parquet")
    ss_labels.to_parquet(output_path / "compound_interactions.parquet")
