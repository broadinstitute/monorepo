from zipfile import ZipFile
from pathlib import Path

import pandas as pd
from jump.uniprot import get_gene_names

from jump.utils import download_file, load_jump_ids


def open_zip(output_path: Path, redownload=False):
    filepath = output_path / 'biokg/biokg.zip'
    url = 'https://github.com/dsi-bdi/biokg/releases/download/v1.0.0/biokg.zip'
    download_file(url, filepath, redownload)

    with ZipFile(filepath, 'r') as zipfile:
        fread = zipfile.open('biokg.links.tsv')
        edges = pd.read_csv(fread,
                            sep='\t',
                            low_memory=False,
                            names=['source', 'rel_type', 'target'])
    return edges


def get_compound_annotations(output_dir: str):
    output_path = Path(output_dir)
    jump_ids = load_jump_ids(output_path).query('src_name=="drugbank"')
    edges = open_zip(output_path)
    edges = edges.query('source.isin(@jump_ids.src_compound_id)').copy()
    uniprot_ids = edges['target'].drop_duplicates().tolist()
    results = get_gene_names(uniprot_ids)
    uniprot_to_gene = {r['from']: r['to'] for r in results['results']}
    edges['target'] = edges['target'].map(uniprot_to_gene)
    edges.dropna(subset=['target'], inplace=True)
    annotations = jump_ids.merge(edges,
                                 left_on='src_compound_id',
                                 right_on='source')
    annotations = annotations.pivot_table(index='inchikey',
                                          columns='rel_type',
                                          values='target',
                                          aggfunc=list)
    return annotations
