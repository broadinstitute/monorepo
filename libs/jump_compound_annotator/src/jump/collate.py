from pathlib import Path

import pandas as pd

from jump import mychem
from jump.biokg import get_compound_annotations as get_biokg
from jump.dgidb import get_compound_annotations as get_dgidb
from jump.drkg import get_compound_annotations as get_drkg
from jump.drugrep import get_compound_annotations as get_drugrep
from jump.hetionet import get_compound_annotations as get_hetionet
from jump.ncbi import get_synonyms
from jump.openbiolink import get_compound_annotations as get_openbiolink
from jump.pharmebinet import get_compound_annotations as get_pharmebinet
from jump.primekg import get_compound_annotations as get_primekg
from jump.utils import load_gene_ids


def concat_annotations(output_dir: str, overwrite: bool = False):
    filepath = Path(output_dir) / 'annotations.parquet'
    if filepath.is_file() and not overwrite:
        return pd.read_parquet(filepath)
    biokg = get_biokg(output_dir)
    dgidb = get_dgidb(output_dir)
    # drkg = get_drkg(output_dir)
    hetionet = get_hetionet(output_dir)
    openbiolink = get_openbiolink(output_dir)
    pharmebinet = get_pharmebinet(output_dir)
    primekg = get_primekg(output_dir)
    drugrep = get_drugrep(output_dir)

    annotations = []
    names = 'biokg', 'dgidb', 'drugrep', 'hetionet', 'openbiolink', 'pharmebinet', 'primekg'
    datasets = biokg, dgidb, drugrep, hetionet, openbiolink, pharmebinet, primekg
    for name, ds in zip(names, datasets):
        ds['database'] = name
        annotations.append(ds)
    annotations = pd.concat(annotations).reset_index(drop=True)

    # Fill genes with synonyms from ncbi
    synonyms = get_synonyms(output_dir)
    gene_ids = load_gene_ids()
    query = ('not target in @gene_ids["Approved_symbol"] '
             'and target in @synonyms["Synonyms"]')
    mappable = annotations.query(query)
    mapper = synonyms.query('Synonyms.isin(@mappable.target)')
    mapper = mapper.set_index('Synonyms')['Symbol']
    mappable = mappable['target'].map(mapper)
    annotations.loc[mappable.index, 'target'] = mappable.values
    annotations = annotations.query('target in @gene_ids["Approved_symbol"]')
    annotations = annotations.reset_index(drop=True).copy()
    annotations.to_parquet(filepath)
    return annotations


def get_inchi_annotations(output_dir):
    df = concat_annotations(output_dir)
    db_mapper = mychem.get_drugbank_mapper(output_dir)
    ch_mapper = mychem.get_chembl_mapper(output_dir)
    pc_mapper = mychem.get_pubchem_mapper(output_dir)

    drugbank_mask = df['source_id'] == 'drugbank'
    chembl_mask = df['source_id'] == 'chembl'
    pubchem_mask = df['source_id'] == 'pubchem'

    df['inchikey'] = None
    df.loc[drugbank_mask, 'inchikey'] = df['source'].map(db_mapper)
    df.loc[chembl_mask, 'inchikey'] = df['source'].map(ch_mapper)
    df.loc[pubchem_mask, 'inchikey'] = df['source'].map(pc_mapper)
    return df
