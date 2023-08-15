from pathlib import Path

import pandas as pd

from jump.utils import download_file, load_jump_ids


def open_tsv_files(output_path: Path, redownload=False):
    node_types = ['drugs', 'genes', 'interactions', 'categories']
    dframes = []
    for node_type in node_types:
        filepath = output_path / f'dgidb/{node_type}.tsv'
        url = f'https://www.dgidb.org/data/monthly_tsvs/2022-Feb/{node_type}.tsv'
        download_file(url, filepath, redownload)
        dframes.append(pd.read_csv(filepath, sep='\t', low_memory=False))
    return tuple(dframes)


def get_compound_annotations(output_dir: str):
    output_path = Path(output_dir)
    jump_ids = load_jump_ids(output_path).query('src_name=="chembl"')
    drugs, genes, edges, categories = open_tsv_files(output_path)
    edges.drug_concept_id.fillna("", inplace=True)
    edges = edges.query('drug_concept_id.str.match("chembl:")').copy()
    edges['drug_concept_id'] = edges.drug_concept_id.str[len('chembl:'):]
    annotations = edges.merge(jump_ids,
                              left_on='drug_concept_id',
                              right_on='src_compound_id')
    annotations = annotations.pivot_table(index='inchikey',
                                          columns='interaction_types',
                                          values='gene_name',
                                          aggfunc=list)
    return annotations
