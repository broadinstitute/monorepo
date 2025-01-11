import tarfile
from pathlib import Path

import pandas as pd

from jump.utils import download_file, load_jump_ids


def open_gz(output_path: Path, redownload):
    filepath = output_path / 'drkg/drkg.tar.gz'
    url = 'https://dgl-data.s3-us-west-2.amazonaws.com/dataset/DRKG/drkg.tar.gz'
    download_file(url, filepath, redownload)

    edges_fpath = output_path / 'drkg/edges.parquet'

    if any([not edges_fpath.is_file(), redownload]):
        with tarfile.open(filepath, 'r:gz') as fread:
            edges = pd.read_csv(fread.extractfile('drkg.tsv'),
                                sep='\t',
                                low_memory=False,
                                names=['source', 'rel_type', 'target'])
        edges.to_parquet(edges_fpath)
    else:
        edges = pd.read_parquet(edges_fpath)
    return edges


def get_compound_annotations(output_dir: str):
    output_dir = './output'
    output_path = Path(output_dir)
    jump_ids = load_jump_ids(output_path)
    edges = open_gz(output_path)
    raise NotImplementedError(
        'DRKG does not have standardized IDs. Requires IDs preprocessing to map them to inchikeys and Gene Names'
    )
