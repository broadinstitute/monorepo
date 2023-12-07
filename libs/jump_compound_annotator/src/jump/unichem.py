from functools import partial
import logging
import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from tqdm.contrib.concurrent import thread_map
from tqdm.auto import tqdm

logger = logging.getLogger(__name__)
SOURCE_IDS = pd.read_csv(
    'https://ftp.ebi.ac.uk/pub/databases/chembl/UniChem/data/table_dumps/source.tsv.gz',
    sep='\t').set_index('SRC_ID')['NAME']
REV_SOURCE_IDS = pd.read_csv(
    'https://ftp.ebi.ac.uk/pub/databases/chembl/UniChem/data/table_dumps/source.tsv.gz',
    sep='\t').set_index('NAME')['SRC_ID']
JUMP_INCHIKEYS = pd.read_csv(
    'https://github.com/jump-cellpainting/datasets/raw/main/metadata/compound.csv.gz'
).Metadata_InChIKey.dropna().drop_duplicates()


def inchi_from_id(compound_id, source_id):
    url = 'https://www.ebi.ac.uk/unichem/api/v1/compounds'
    payload = {
        'compound': compound_id,
        'sourceID': int(REV_SOURCE_IDS[source_id]),
        'type': 'sourceID'
    }
    headers = {'Content-Type': 'application/json'}
    num_tries = 5
    for _ in range(num_tries):
        try:
            response = requests.request('POST',
                                        url,
                                        json=payload,
                                        headers=headers).json()
            inchikey = None
            if response['compounds']:
                inchikey = response['compounds'][0]['standardInchiKey']
            return compound_id, inchikey
        except Exception as ex:
            last_error_msg = str(ex)
    return compound_id, last_error_msg


def get_mapper(output_dir, source_id):
    output_path = Path(output_dir)
    output_file = output_path / f'unichem_{source_id}_mapper.csv'
    if output_file.is_file():
        return pd.read_csv(output_file,
                           dtype=str).set_index(source_id)['inchikey']
    df = pd.read_parquet(output_path / 'annotations.parquet')
    database_ids = df.query('source_id==@source_id').source.unique()
    par_func = partial(inchi_from_id, source_id=source_id)
    mapper = dict(thread_map(par_func, database_ids))
    mapper = pd.Series(mapper, name='inchikey')
    mapper.index.name = source_id
    mapper.to_csv(output_file)
    return mapper


def get_unichem_id(inchikey):
    url = f'https://www.ebi.ac.uk/unichem/rest/inchikey/{inchikey}'
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return inchikey, response.json()
        else:
            return inchikey, response.status_code
    except Exception as ex:
        return inchikey, str(ex)


def ids_to_dframes(ids, errors, output_path: Path):
    curr_dt = datetime.now()
    ts_string = str(int(round(curr_dt.timestamp())))
    if ids:
        ids = pd.concat(ids)
        ids['src_id'] = ids['src_id'].astype(int)
        ids['src_name'] = ids['src_id'].map(SOURCE_IDS)
        (output_path / 'ids').mkdir(parents=True, exist_ok=True)
        ids.to_csv(f'{output_path}/ids/ids_{ts_string}.csv', index=False)
    if errors:
        errors = pd.DataFrame(errors, columns=['inchikey', 'message'])
        (output_path / 'errors').mkdir(parents=True, exist_ok=True)
        errors.to_csv(f'{output_path}/errors/errors_{ts_string}.csv',
                      index=False)


def pull(output_path: Path, batch_size: int = 1000):
    known_ids = list(map(pd.read_csv, output_path.glob('ids/ids_*.csv')))
    inchikeys = JUMP_INCHIKEYS
    if known_ids:
        known_ids = pd.concat(known_ids).inchikey
        inchikeys = inchikeys[~inchikeys.isin(known_ids)]
    for i in tqdm(range(0, len(inchikeys), batch_size)):
        batch = inchikeys[i:i + batch_size]
        output = thread_map(get_unichem_id, batch, leave=False)
        ids, errors = [], []
        for inchikey, response in output:
            if isinstance(response, int):
                errors.append((inchikey, response))
            elif 'error' in response:
                errors.append((inchikey, response['error']))
            else:
                df = pd.DataFrame(response)
                df['inchikey'] = inchikey
                ids.append(df)
        ids_to_dframes(ids, errors, output_path)


def collate(output_path: Path):
    ids = list(map(pd.read_csv, output_path.glob('ids/ids_*.csv')))
    if not ids:
        raise ValueError('IDs files not found')
    ids = pd.concat(ids).drop_duplicates()
    ids = ids.sort_values(['inchikey', 'src_name', 'src_compound_id'])
    total = len(ids)
    ids.drop_duplicates(['inchikey', 'src_name'], inplace=True)
    dups = total - len(ids)
    if dups > 0:
        logger.warning(f'{dups} duplicates removed.')
    ids = ids.pivot(index='inchikey',
                    columns='src_name',
                    values='src_compound_id')
    ids.fillna('', inplace=True)
    ids.to_csv(output_path / 'pointers.csv')


def main():
    parser = argparse.ArgumentParser(
        description='Create maps between compounds and unique IDs.')
    parser.add_argument('action', choices=['pull', 'collate'])
    parser.add_argument('output_path')
    args = parser.parse_args()
    if args.action == 'pull':
        pull(Path(args.output_path))
    elif args.action == 'collate':
        collate(Path(args.output_path))


def get_inchi_annotations(output_dir):
    df = pd.read_parquet(Path(output_dir) / 'annotations.parquet')
    db_mapper = get_mapper(output_dir, 'drugbank')
    ch_mapper = get_mapper(output_dir, 'chembl')
    pc_mapper = get_mapper(output_dir, 'pubchem')

    drugbank_mask = df['source_id'] == 'drugbank'
    chembl_mask = df['source_id'] == 'chembl'
    pubchem_mask = df['source_id'] == 'pubchem'

    df['inchikey'] = None
    df.loc[drugbank_mask, 'inchikey'] = df['source'].map(db_mapper)
    df.loc[chembl_mask, 'inchikey'] = df['source'].map(ch_mapper)
    df.loc[pubchem_mask, 'inchikey'] = df['source'].map(pc_mapper)

    inchi_regex = r'^([A-Z]{14}\-[A-Z]{10})(\-[A-Z])$'
    df = df.query('inchikey.fillna("").str.fullmatch(@inchi_regex)')
    df = df.drop_duplicates().reset_index(drop=True).copy()
    return df


if __name__ == '__main__':
    main()
