from pathlib import Path

import pandas as pd

from jump.utils import download_file


def open_tsv_files(output_path: Path, redownload: bool):
    node_types = ["drugs", "genes", "interactions", "categories"]
    dframes = []
    for node_type in node_types:
        filepath = output_path / f"dgidb/{node_type}.tsv"
        url = f"https://www.dgidb.org/data/2022-Feb/{node_type}.tsv"
        download_file(url, filepath, redownload)
        dframes.append(pd.read_csv(filepath, sep="\t", low_memory=False))
    return tuple(dframes)


def get_compound_annotations(output_dir: str, redownload: bool):
    output_path = Path(output_dir)
    drugs, genes, edges, categories = open_tsv_files(output_path, redownload)
    edges["drug_concept_id"] = edges["drug_concept_id"].fillna("")
    edges = edges.query('drug_concept_id.str.match("chembl:")').copy()
    edges["drug_concept_id"] = edges.drug_concept_id.str[len("chembl:") :]

    # from https://www.dgidb.org/interaction_types
    # "DGIdb assigns this (n/a) label to any drug-gene interaction for which
    # the interaction type is not specified by the reporting source."
    edges["interaction_types"] = edges["interaction_types"].fillna("unknown")

    edges = edges[["drug_concept_id", "gene_name", "interaction_types"]]
    edges = edges.dropna().drop_duplicates()

    edges.columns = ["source", "target", "rel_type"]
    edges["source_id"] = "chembl"

    return edges
