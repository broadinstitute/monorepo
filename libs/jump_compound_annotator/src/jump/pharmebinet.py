import json
import re
import tarfile
from pathlib import Path

import numpy as np
import pandas as pd

from jump.utils import download_file


def open_gz(output_path: Path, redownload: bool):
    filepath = output_path / "pharmebinet/pharmebinet.tar.gz"
    url = "https://zenodo.org/record/7011027/files/pharmebinet_tsv_2022_08_19_v2.tar.gz?download=1"
    download_file(url, filepath, redownload)

    nodes_fpath = output_path / "pharmebinet/nodes.parquet"
    edges_fpath = output_path / "pharmebinet/edges.parquet"

    if any([not nodes_fpath.is_file(), not edges_fpath.is_file(), redownload]):
        with tarfile.open(filepath, "r:gz") as fread:
            edges = pd.read_csv(
                fread.extractfile("edges.tsv"), sep="\t", low_memory=False
            )
            nodes = pd.read_csv(
                fread.extractfile("nodes.tsv"), sep="\t", low_memory=False
            )
        nodes.to_parquet(nodes_fpath)
        edges.to_parquet(edges_fpath)
    else:
        nodes = pd.read_parquet(nodes_fpath)
        edges = pd.read_parquet(edges_fpath)
    return edges, nodes


def get_compound_annotations(output_dir: str, redownload: bool):
    output_path = Path(output_dir)
    edges, nodes = open_gz(output_path, redownload)
    nodes = nodes.set_index("node_id")
    chem_ids = nodes.query('labels=="Chemical|Compound"').index  # noqa: F841
    edges = edges.query("start_id in @chem_ids")
    edges = edges.query('type.str.endswith("G")')
    edges = edges[["start_id", "end_id", "type"]]
    trgt_ids = edges["end_id"].drop_duplicates()
    tgt_nodes = get_node_props(nodes.loc[trgt_ids])
    edges["source"] = edges["start_id"].map(nodes["identifier"])
    edges["target"] = edges["end_id"].map(tgt_nodes["gene_symbols"])
    edges.rename(columns={"type": "rel_type"}, inplace=True)
    edges["source_id"] = "drugbank"
    edges = edges[["source", "target", "rel_type", "source_id"]]
    return edges.explode("target")


def get_node_props(nodes: pd.DataFrame) -> pd.DataFrame:
    node_props = pd.DataFrame(
        nodes["properties"].apply(json.loads).tolist(), index=nodes.index
    )
    for col in "identifier", "name":
        node_props[col] = nodes[col].values
    return node_props


def get_compound_interactions(output_dir: str, redownload: bool):
    output_path = Path(output_dir)
    edges, nodes = open_gz(output_path, redownload)
    nodes = nodes.set_index("node_id")
    rgx_c = re.compile(r".*_(C[a-z]+C)$")
    rgx_ch = re.compile(r".*_(CH[a-z]+CH)$")

    types_c = [c.group() for c in map(rgx_c.match, edges.type.unique()) if c]  # noqa: F841
    types_ch = [c.group() for c in map(rgx_ch.match, edges.type.unique()) if c]  # noqa: F841

    edges_ch = edges.query("type in @types_ch")[["type", "start_id", "end_id"]]
    edges_c = edges.query("type in @types_c")[["type", "start_id", "end_id"]]

    nodes_ch = nodes.loc[np.unique(edges_ch[["start_id", "end_id"]].values)]
    nodes_c = nodes.loc[np.unique(edges_c[["start_id", "end_id"]].values)]

    nodes_feat_ch = get_node_props(nodes_ch)
    nodes_feat_c = get_node_props(nodes_c)

    edges_ch["source_a"] = edges_ch["start_id"].map(nodes_feat_ch.identifier)
    edges_ch["source_b"] = edges_ch["end_id"].map(nodes_feat_ch.identifier)
    edges_c["source_a"] = edges_c["start_id"].map(nodes_feat_c.identifier)
    edges_c["source_b"] = edges_c["end_id"].map(nodes_feat_c.identifier)

    edges_all = pd.concat(
        [
            edges_c[["source_a", "source_b", "type"]],
            edges_ch[["source_a", "source_b", "type"]],
        ]
    )
    edges_all["source_id"] = "drugbank"
    edges_all.rename(columns={"type": "rel_type"}, inplace=True)
    edges_all.reset_index(drop=True, inplace=True)
    return edges_all[["source_a", "source_b", "rel_type", "source_id"]]


def get_gene_interactions(output_dir: str, redownload: bool):
    output_path = Path(output_dir)
    edges, nodes = open_gz(output_path, redownload)
    nodes = nodes.set_index("node_id")
    rgx_g = re.compile(r".*_(G[a-z]+G)$")
    types_g = [c.group() for c in map(rgx_g.match, edges.type.unique()) if c]  # noqa: F841
    edges_g = edges.query("type in @types_g")[["type", "start_id", "end_id"]]
    nodes_g = nodes.loc[np.unique(edges_g[["start_id", "end_id"]].values)]
    nodes_feat_g = get_node_props(nodes_g)
    edges_g["target_a"] = edges_g["start_id"].map(nodes_feat_g["gene_symbols"])
    edges_g["target_b"] = edges_g["end_id"].map(nodes_feat_g["gene_symbols"])
    edges_g["target_a"] = edges_g["target_a"].apply(lambda x: x[0])
    edges_g["target_b"] = edges_g["target_b"].apply(lambda x: x[0])
    edges_g.rename(columns={"type": "rel_type"}, inplace=True)
    edges_g = edges_g[["target_a", "target_b", "rel_type"]]
    edges_g.reset_index(drop=True, inplace=True)
    return edges_g
