import json
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from tqdm.contrib.concurrent import thread_map


def inchis_from_chembl(ids: np.ndarray):
    data = {
        'q': ids.tolist(),
        'scopes': ['chembl.molecule_chembl_id'],
        'fields': ['chembl.inchikey']
    }
    response = requests.post('https://mychem.info/v1/query?size=500',
                             json=data)
    return response.json()


def get_chembl_mapper(output_dir):
    output_path = Path(output_dir)
    output_file = output_path / 'mychem_chembl_mapper.csv'
    if output_file.is_file():
        return pd.read_csv(output_file,
                           dtype=str).set_index('chembl')['inchikey']

    df = pd.read_parquet(output_path / 'annotations.parquet')
    chembl_ids = df.query('source_id=="chembl"').source.unique()
    batches = np.split(chembl_ids, np.arange(500, len(chembl_ids), 500))
    result = thread_map(inchis_from_chembl, batches, max_workers=8)
    result = sum(result, [])

    mapper = {}
    for dbid, rs in zip(chembl_ids, result):
        if 'error' not in rs and 'notfound' not in rs:
            mapper[dbid] = rs['_id']
        else:
            mapper[dbid] = json.dumps(rs)

    mapper = pd.Series(mapper, name='inchikey')
    mapper.index.name = 'chembl'
    mapper.to_csv(output_file)
    return mapper


def inchis_from_pubchem(ids: np.ndarray):
    data = {
        'q': ids.tolist(),
        'scopes': ['pubchem.cid'],
        'fields': ['pubchem.inchikey']
    }
    response = requests.post('https://mychem.info/v1/query?size=500',
                             json=data)
    return response.json()


def get_pubchem_mapper(output_dir):
    output_path = Path(output_dir)
    output_file = output_path / 'mychem_pubchem_mapper.csv'
    if output_file.is_file():
        return pd.read_csv(output_file,
                           dtype=str).set_index('pubchem')['inchikey']

    df = pd.read_parquet(output_path / 'annotations.parquet')
    pubchem_ids = df.query('source_id=="pubchem"').source.unique()
    batches = np.split(pubchem_ids, np.arange(500, len(pubchem_ids), 500))
    result = thread_map(inchis_from_pubchem, batches, max_workers=8)
    result = sum(result, [])

    mapper = {}
    for dbid, rs in zip(pubchem_ids, result):
        if 'error' not in rs and 'notfound' not in rs:
            mapper[dbid] = rs['_id']
        else:
            mapper[dbid] = json.dumps(rs)

    mapper = pd.Series(mapper, name='inchikey')
    mapper.index.name = 'pubchem'
    mapper.to_csv(output_file)
    return mapper


def inchis_from_drugbank(ids: np.ndarray):
    data = {
        'q': ids.tolist(),
        'scopes': ['drugbank.id'],
        'fields': ['drugbank.inchikey']
    }
    response = requests.post('https://mychem.info/v1/query?size=500',
                             json=data)
    return response.json()


def get_drugbank_mapper(output_dir):
    output_path = Path(output_dir)
    output_file = output_path / 'mychem_drugbank_mapper.csv'
    if output_file.is_file():
        return pd.read_csv(output_file,
                           dtype=str).set_index('drugbank')['inchikey']

    df = pd.read_parquet(output_path / 'annotations.parquet')
    drugbank_ids = df.query('source_id=="drugbank"').source.unique()
    batches = np.split(drugbank_ids, np.arange(500, len(drugbank_ids), 500))
    result = thread_map(inchis_from_drugbank, batches, max_workers=8)
    result = sum(result, [])

    mapper = {}
    for dbid, rs in zip(drugbank_ids, result):
        if 'error' not in rs and 'notfound' not in rs:
            mapper[dbid] = rs['_id']
        else:
            mapper[dbid] = json.dumps(rs)

    mapper = pd.Series(mapper, name='inchikey')
    mapper.index.name = 'drugbank'
    mapper['DB01361'] = 'LQCLVBQBTUVCEQ-QTFUVMRISA-N'
    mapper['DB01398'] = 'YGSDEFSMJLZEOE-UHFFFAOYSA-N'
    mapper['DB00667'] = 'NTYJJOPFIAHURM-UHFFFAOYSA-N'
    mapper['DB00729'] = 'BREMLQBSKCSNNH-UHFFFAOYSA-M'
    mapper['DB08866'] = 'LRHSUZNWLAJWRT-GAJBHWORSA-N'
    mapper.to_csv(output_file)
    return mapper


def get_inchi_annotations(output_dir):
    df = pd.read_parquet(Path(output_dir) / 'annotations.parquet')
    db_mapper = get_drugbank_mapper(output_dir)
    ch_mapper = get_chembl_mapper(output_dir)
    pc_mapper = get_pubchem_mapper(output_dir)

    drugbank_mask = df['source_id'] == 'drugbank'
    chembl_mask = df['source_id'] == 'chembl'
    pubchem_mask = df['source_id'] == 'pubchem'

    df['inchikey'] = None
    df.loc[drugbank_mask, 'inchikey'] = df['source'].map(db_mapper)
    df.loc[chembl_mask, 'inchikey'] = df['source'].map(ch_mapper)
    df.loc[pubchem_mask, 'inchikey'] = df['source'].map(pc_mapper)
    return df
