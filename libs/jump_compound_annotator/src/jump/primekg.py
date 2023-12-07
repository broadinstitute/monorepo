from pathlib import Path
from jump.utils import download_file
import pandas as pd


def load_kg(output_path: Path, redownload=False):
    filepath = output_path / 'primekg/data.csv'
    url = 'https://dataverse.harvard.edu/api/access/datafile/6180620'
    download_file(url, filepath, redownload)
    kg = pd.read_csv(filepath, low_memory=False)
    return kg


def get_compound_annotations(output_dir: str) -> pd.DataFrame:
    output_path = Path(output_dir)
    edges = load_kg(output_path)
    edges = edges.query('x_type=="drug" and y_type=="gene/protein"').copy()
    edges.rename(columns=dict(x_id='source',
                              y_name='target',
                              display_relation='rel_type'),
                 inplace=True)
    edges['source_id'] = 'drugbank'
    edges = edges[['source', 'target', 'rel_type', 'source_id']]
    edges = edges.dropna().drop_duplicates()
    return edges
