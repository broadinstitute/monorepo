from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from jump.utils import download_file, load_jump_ids


def open_zip(output_path: Path, redownload=False):
    filepath = output_path / 'openbiolink/openbiolink.zip'
    url = 'https://zenodo.org/record/3834052/files/HQ_UNDIR.zip?download=1'
    download_file(url, filepath, redownload)

    zip_path = 'HQ_UNDIR/graph_files'
    with ZipFile(filepath, 'r') as zipfile:
        fread = zipfile.open(f'{zip_path}/nodes.csv')
        nodes = pd.read_csv(fread,
                            sep='\t',
                            low_memory=False,
                            names=['id', 'type'])
        fread = zipfile.open(f'{zip_path}/edges.csv')
        edges = pd.read_csv(
            fread,
            sep='\t',
            low_memory=False,
            names=['source', 'rel_type', 'target', 'quality', 'database'])
    return edges, nodes


def get_compound_annotations(output_dir: str):
    output_path = Path(output_dir)
    jump_ids = load_jump_ids(output_path).query('src_name=="pubchem"')
    edges, nodes = open_zip(output_path)
    query = 'source.str.startswith("PUBCHEM") and target.str.startswith("NCBIGENE")'
    edges = edges.query(query).copy()
    edges['pubchem_id'] = edges['source'].str.split(':', expand=True)[1]
    edges['ncbi_id'] = edges['target'].str.split(':', expand=True)[1]
    annotations = jump_ids.merge(edges,
                                 left_on='src_compound_id',
                                 right_on='pubchem_id')
    annotations = annotations.pivot_table(index='inchikey',
                                          columns='rel_type',
                                          values='ncbi_id',
                                          aggfunc=list)
    annotations.columns.name = None
    return annotations
