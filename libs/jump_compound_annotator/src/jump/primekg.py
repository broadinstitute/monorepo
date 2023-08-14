from pathlib import Path
from jump.utils import download_file, load_jump_ids
import pandas as pd


def load_kg(output_path: Path, redownload=False):
    filepath = output_path / 'primekg/data.csv'
    url = 'https://dataverse.harvard.edu/api/access/datafile/6180620'
    download_file(url, filepath, redownload)
    kg = pd.read_csv(filepath, low_memory=False)
    return kg


def get_compound_annotations(output_dir: str):
    output_path = Path(output_dir)
    jump_ids = load_jump_ids(output_path).query('src_name=="drugbank"')
    kg = load_kg(output_path)

    rels = kg.query('x_type=="drug" and y_type=="gene/protein"')
    rels = rels.merge(jump_ids, left_on='x_id', right_on='src_compound_id')
    rels = rels.pivot_table(index='inchikey',
                            columns='display_relation',
                            values='y_name',
                            aggfunc=list)
    rels.columns.name = None
    return rels
