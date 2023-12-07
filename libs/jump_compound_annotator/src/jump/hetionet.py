import gzip
from zipfile import ZipFile
from pathlib import Path

import pandas as pd

from jump.utils import download_file, load_jump_ids


def open_zip(output_path: Path, redownload=False):
    filepath = output_path / 'hetionet/hetionet.zip'
    url = 'https://zenodo.org/record/268568/files/dhimmel/hetionet-v1.0.0.zip?download=1'
    download_file(url, filepath, redownload)

    zip_path = 'dhimmel-hetionet-4933ca1/hetnet/tsv'
    with ZipFile(filepath, 'r') as zipfile:
        fread = zipfile.open(f'{zip_path}/hetionet-v1.0-nodes.tsv')
        nodes = pd.read_csv(fread, sep='\t', low_memory=False)
        fread = zipfile.open(f'{zip_path}/hetionet-v1.0-edges.sif.gz')
        edges = pd.read_csv(gzip.open(fread), sep='\t', low_memory=False)
    return edges, nodes


def get_compound_annotations(output_dir: str):
    output_path = Path(output_dir)
    edges, nodes = open_zip(output_path)
    query = 'source.str.startswith("Compound") and target.str.startswith("Gene")'
    edges = edges.query(query).copy()
    edges['source'] = edges['source'].str[len('Compound::'):]
    edges['target'] = edges['target'].map(nodes.set_index('id').name)
    edges.rename(columns={'metaedge': 'rel_type'}, inplace=True)
    edges['source_id'] = 'drugbank'
    return edges[['source', 'target', 'rel_type', 'source_id']]
