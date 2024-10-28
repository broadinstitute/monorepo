from pathlib import Path

import pandas as pd

from jump.utils import download_file


def load_kg(output_path: Path, redownload: bool):
    filepath = output_path / "primekg/data.csv"
    url = "https://dataverse.harvard.edu/api/access/datafile/6180620"
    download_file(url, filepath, redownload)
    kg = pd.read_csv(filepath, low_memory=False)
    return kg


def get_compound_annotations(output_dir: str, redownload: bool) -> pd.DataFrame:
    output_path = Path(output_dir)
    edges = load_kg(output_path, redownload)
    edges = edges.query('x_type=="drug" and y_type=="gene/protein"').copy()
    edges.rename(
        columns=dict(x_id="source", y_name="target", display_relation="rel_type"),
        inplace=True,
    )
    edges["source_id"] = "drugbank"
    edges = edges[["source", "target", "rel_type", "source_id"]]
    edges = edges.dropna().drop_duplicates()
    return edges


def get_compound_interactions(output_dir: str, redownload: bool) -> pd.DataFrame:
    output_path = Path(output_dir)
    edges = load_kg(output_path, redownload)
    edges = edges.query('x_type=="drug" and y_type=="drug"').copy()
    edges.rename(
        columns=dict(x_id="source_a", y_id="source_b", display_relation="rel_type"),
        inplace=True,
    )
    edges["source_id"] = "drugbank"
    edges = edges[["source_a", "source_b", "rel_type", "source_id"]]
    edges = edges.dropna().drop_duplicates()
    return edges


def get_gene_interactions(output_dir: str, redownload: bool) -> pd.DataFrame:
    output_path = Path(output_dir)
    edges = load_kg(output_path, redownload)
    edges = edges.query('x_type=="gene/protein" and y_type=="gene/protein"').copy()
    edges.rename(
        columns=dict(x_name="target_a", y_name="target_b", display_relation="rel_type"),
        inplace=True,
    )
    edges = edges[["target_a", "target_b", "rel_type"]]
    edges = edges.dropna().drop_duplicates()
    return edges
