import logging
import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from tqdm.contrib.concurrent import thread_map
from tqdm.auto import tqdm

SOURCE_IDS = pd.read_csv('https://ftp.ebi.ac.uk/pub/databases/chembl/UniChem/data/table_dumps/source.tsv.gz', sep='\t').set_index('SRC_ID')['NAME']
JUMP_INCHIKEYS = pd.read_csv('https://github.com/jump-cellpainting/datasets/raw/main/metadata/compound.csv.gz').Metadata_InChIKey.dropna().drop_duplicates()

def get_unichem_id(inchikey):
    url = "https://www.ebi.ac.uk/unichem/rest/inchikey/{}".format(inchikey)
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
        errors.to_csv(f'{output_path}/errors/errors_{ts_string}.csv', index=False)

def map_inchikeys(output_path: Path, batch_size:int = 1000):
    known_ids = list(map(pd.read_csv, output_path.glob('ids/ids_*.csv')))
    inchikeys = JUMP_INCHIKEYS
    if known_ids:
        known_ids = pd.concat(known_ids).inchikey
        inchikeys = inchikeys[~inchikeys.isin(known_ids)]
    for i in tqdm(range(0, len(inchikeys), batch_size)):
        batch = inchikeys[i:i+batch_size]
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

def main():
    parser = argparse.ArgumentParser(description='Create maps between compounds and unique IDs.')
    parser.add_argument('output_path')
    args = parser.parse_args()
    map_inchikeys(Path(args.output_path))

if __name__=='__main__':
    main()
