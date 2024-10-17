from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from jump.utils import download_file, ncbi_to_symbol


def open_zip(output_path: Path, redownload=False):
    filepath = output_path / "openbiolink/openbiolink.zip"
    url = "https://zenodo.org/record/5361324/files/HQ_UNDIR.zip?download=1"
    download_file(url, filepath, redownload)

    zip_path = "HQ_UNDIR/graph_files"
    with ZipFile(filepath, "r") as zipfile:
        fread = zipfile.open(f"{zip_path}/nodes.csv")
        nodes = pd.read_csv(fread, sep="\t", low_memory=False, names=["id", "type"])
        fread = zipfile.open(f"{zip_path}/edges.csv")
        edges = pd.read_csv(
            fread,
            sep="\t",
            low_memory=False,
            names=["source", "rel_type", "target", "quality", "database"],
        )
    return edges, nodes


def get_compound_annotations(output_dir: str):
    output_path = Path(output_dir)
    gene_mapper = ncbi_to_symbol(output_path)
    edges, nodes = open_zip(output_path)
    query = 'source.str.startswith("PUBCHEM") and target.str.startswith("NCBIGENE")'
    edges = edges.query(query).copy()
    edges["source"] = edges["source"].str.split(":", expand=True)[1]
    edges["ncbi_id"] = edges["target"].str.split(":", expand=True)[1]
    edges["gene_name"] = edges["ncbi_id"].astype(int).map(gene_mapper)
    missing = edges.query("gene_name.isna()").drop_duplicates(subset="ncbi_id")
    if len(missing) > 0:
        before = len(edges)
        edges = edges.dropna(subset="gene_name")
        after = len(edges)
        nans = before - after
        print(
            f"{len(missing)} NCBI Gene IDs could not be found. "
            f"Dropping {nans} annotations"
        )

    edges = edges[["source", "gene_name", "rel_type"]].copy()
    edges = edges.dropna().drop_duplicates()
    edges.rename(columns={"gene_name": "target"}, inplace=True)
    edges["source_id"] = "pubchem"
    return edges


def get_gene_interactions(output_dir: str):
    output_path = Path(output_dir)
    gene_mapper = ncbi_to_symbol(output_path)
    edges, nodes = open_zip(output_path)
    query = 'rel_type.str.startswith("GENE") and rel_type.str.endswith("GENE")'
    edges = edges.query(query).copy()
    edges["gene_a"] = edges["source"].str.split(":", expand=True)[1]
    edges["gene_b"] = edges["target"].str.split(":", expand=True)[1]
    edges["target_a"] = edges["gene_a"].astype(int).map(gene_mapper)
    edges["target_b"] = edges["gene_b"].astype(int).map(gene_mapper)
    missing = edges.query("target_a.isna() or target_b.isna()").drop_duplicates(
        subset=["gene_a", "gene_b"]
    )
    if len(missing) > 0:
        before = len(edges)
        edges = edges.dropna(subset=["target_a", "target_b"])
        after = len(edges)
        nans = before - after
        percent = nans / before
        print(
            f"{len(missing)} NCBI Gene IDs could not be found. "
            f"Dropping {nans} annotations ({percent:0.2%})"
        )

    edges = edges[["target_a", "target_b", "rel_type"]].copy()
    edges = edges.dropna().drop_duplicates()
    return edges


def get_compound_interactions(output_dir: str):
    raise NotImplementedError(
        "openbiolink does not have compound-compound interactions"
    )
