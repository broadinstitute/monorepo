import json
import tarfile
from pathlib import Path

import pandas as pd

from jump.utils import download_file


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
    edges, nodes = open_gz(output_path)
    nodes = nodes.set_index('node_id')
    chem_ids = nodes.query('labels=="Chemical|Compound"').index
    edges = edges.query('start_id in @chem_ids')
    edges = edges.query('type.str.endswith("G")')
    edges = edges[['start_id', 'end_id', 'type']]
    trgt_ids = edges['end_id'].drop_duplicates()
    tgt_nodes = get_node_props(nodes.loc[trgt_ids])
    edges['source'] = edges['start_id'].map(nodes['identifier'])
    edges['target'] = edges['end_id'].map(tgt_nodes['gene_symbols'])
    edges.rename(columns={'type': 'rel_type'}, inplace=True)
    edges['source_id'] = 'drugbank'
    edges = edges[['source', 'target', 'rel_type', 'source_id']]
    return edges.explode('target')


def get_node_props(nodes: pd.DataFrame) -> pd.DataFrame:
    node_props = pd.DataFrame(nodes['properties'].apply(json.loads).tolist(),
                              index=nodes.index)
    for col in 'identifier', 'name':
        node_props[col] = nodes[col].values
    return node_props
