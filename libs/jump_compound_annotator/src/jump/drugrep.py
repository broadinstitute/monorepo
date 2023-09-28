from pathlib import Path

import pandas as pd

from jump.utils import download_file


def open_data(output_path: Path, redownload=False):
    for fname in ['drugs', 'samples']:
        url = f'https://s3.amazonaws.com/data.clue.io/repurposing/downloads/repurposing_{fname}_20200324.txt'
        filepath = output_path / f'drugrep/{fname}.txt'
        download_file(url, filepath, redownload)

    drugs = pd.read_csv(output_path / 'drugrep/drugs.txt',
                        sep='\t',
                        skiprows=9,
                        dtype=str)
    samples = pd.read_csv(output_path / 'drugrep/samples.txt',
                          sep='\t',
                          skiprows=9,
                          dtype=str)
    dframe = drugs.merge(samples, on='pert_iname')
    return dframe


def get_compound_annotations(output_dir: str):
    edges = open_data(Path(output_dir))
    edges = edges[['pubchem_cid', 'target']].dropna()
    edges['target'] = edges['target'].str.split('|')
    edges = edges.explode('target').drop_duplicates()
    edges.columns = ['pubchem_id', 'target']
    return edges


def broad_id_to_pubchem_mapper(output_dir):
    edges = open_data(Path(output_dir))
    edges['dbid'] = edges['deprecated_broad_id'].apply(
        lambda x: x.split('-')[1] if isinstance(x, str) else None)
    edges['bid'] = edges['broad_id'].apply(lambda x: x.split('-')[1])
    mapper = edges[['bid', 'dbid', 'pubchem_cid']]
    mapper = mapper.melt(['pubchem_cid'], value_name='broad_id')
    mapper = mapper.dropna().drop('variable', axis=1).drop_duplicates()
    mapper = mapper.groupby('broad_id')['pubchem_cid'].apply(list)
    return mapper
