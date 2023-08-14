import json
import tarfile
from pathlib import Path

import pandas as pd

from jump.utils import download_file, load_jump_ids


def open_gz(output_path: Path, redownload=False):
    filepath = output_path / 'pharmebinet/pharmebinet.tar.gz'
    url = 'https://zenodo.org/record/7011027/files/pharmebinet_tsv_2022_08_19_v2.tar.gz?download=1'
    download_file(url, filepath, redownload)

    nodes_fpath = output_path / 'pharmebinet/nodes.parquet'
    edges_fpath = output_path / 'pharmebinet/edges.parquet'

    if any([not nodes_fpath.is_file(), not edges_fpath.is_file(), redownload]):
        with tarfile.open(filepath, 'r:gz') as fread:
            edges = pd.read_csv(fread.extractfile('edges.tsv'),
                                sep='\t',
                                low_memory=False)
            nodes = pd.read_csv(fread.extractfile('nodes.tsv'),
                                sep='\t',
                                low_memory=False)
        nodes.to_parquet(nodes_fpath)
        edges.to_parquet(edges_fpath)
    else:
        nodes = pd.read_parquet(nodes_fpath)
        edges = pd.read_parquet(edges_fpath)
    return edges, nodes

def get_compound_annotations(output_dir: str):
    output_path = Path(output_dir)
    jump_ids = load_jump_ids(output_path)
    edges, nodes = open_gz(output_path)

    cpd_nodes = nodes.query('labels=="Chemical|Compound"')
    cpd_node_props = pd.DataFrame(cpd_nodes['properties'].apply(
        json.loads).tolist())
    for col in 'node_id', 'identifier', 'name':
        cpd_node_props[col] = cpd_nodes[col].values
    jump_nodes = cpd_node_props.query('inchikey.isin(@jump_ids.inchikey)')

    jump_edges = edges.query('start_id.isin(@jump_nodes.node_id)')
    jump_edges_gene = jump_edges.query('type.str.endswith("G")')

    gene_nodes = nodes.query('node_id.isin(@jump_edges_gene.end_id)')
    gene_node_props = pd.DataFrame(gene_nodes['properties'].apply(
        json.loads).tolist())
    gene_node_props['node_id'] = gene_nodes['node_id'].values

    rel = jump_edges_gene[['type', 'start_id', 'end_id']]

    annotations = (rel.merge(jump_nodes,
                             left_on='start_id',
                             right_on='node_id').merge(
                                 gene_node_props,
                                 left_on='end_id',
                                 right_on='node_id').pivot_table(
                                     index='inchikey',
                                     columns='type_x',
                                     values='gene_symbols',
                                     aggfunc=sum))
    annotations.columns.name = None
    return annotations
