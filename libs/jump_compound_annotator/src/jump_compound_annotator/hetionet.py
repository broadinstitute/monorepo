import gzip
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from jump_compound_annotator.utils import download_file


def open_zip(output_path: Path, redownload: bool):
    filepath = output_path / "hetionet/hetionet.zip"
    url = (
        "https://zenodo.org/record/268568/files/dhimmel/hetionet-v1.0.0.zip?download=1"
    )
    download_file(url, filepath, redownload)

    zip_path = "dhimmel-hetionet-4933ca1/hetnet/tsv"
    with ZipFile(filepath, "r") as zipfile:
        fread = zipfile.open(f"{zip_path}/hetionet-v1.0-nodes.tsv")
        nodes = pd.read_csv(fread, sep="\t", low_memory=False)
        fread = zipfile.open(f"{zip_path}/hetionet-v1.0-edges.sif.gz")
        edges = pd.read_csv(gzip.open(fread), sep="\t", low_memory=False)
    return edges, nodes


def get_compound_annotations(output_dir: str, redownload: bool):
    output_path = Path(output_dir)
    edges, nodes = open_zip(output_path, redownload)
    query = 'source.str.startswith("Compound") and target.str.startswith("Gene")'
    edges = edges.query(query).copy()
    edges["source"] = edges["source"].str[len("Compound::") :]
    edges["target"] = edges["target"].map(nodes.set_index("id").name)
    edges.rename(columns={"metaedge": "rel_type"}, inplace=True)
    edges["source_id"] = "drugbank"
    return edges[["source", "target", "rel_type", "source_id"]]


def get_compound_interactions(output_dir: str, redownload: bool):
    output_path = Path(output_dir)
    edges, nodes = open_zip(output_path, redownload)
    query = 'source.str.startswith("Compound") and target.str.startswith("Compound")'
    edges = edges.query(query).copy()
    edges["source_a"] = edges["source"].str[len("Compound::") :]
    edges["source_b"] = edges["target"].str[len("Compound::") :]
    edges["rel_type"] = edges["metaedge"].map({"CrC": "resembles"})
    edges["source_id"] = "drugbank"
    return edges[["source_a", "source_b", "rel_type", "source_id"]]


def get_gene_interactions(output_dir: str, redownload: bool):
    output_path = Path(output_dir)
    edges, nodes = open_zip(output_path, redownload)
    query = 'source.str.startswith("Gene") and target.str.startswith("Gene")'
    edges = edges.query(query).copy()
    edges["rel_type"] = edges["metaedge"].map(
        {
            "Gr>G": "regulates",
            "GiG": "interacts",
            "GcG": "covaries",
        }
    )
    edges["target_a"] = edges["source"].map(nodes.set_index("id").name)
    edges["target_b"] = edges["target"].map(nodes.set_index("id").name)
    return edges[["target_a", "target_b", "rel_type"]]
