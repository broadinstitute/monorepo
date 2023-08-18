import pandas as pd
from pathlib import Path

from jump.biokg import get_compound_annotations as get_biokg
from jump.dgidb import get_compound_annotations as get_dgidb
from jump.drkg import get_compound_annotations as get_drkg
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

    annotations = []
    names = 'biokg', 'dgidb', 'hetionet', 'openbiolink', 'pharmebinet', 'primekg'
    datasets = biokg, dgidb, hetionet, openbiolink, pharmebinet, primekg
    for name, ds in zip(names, datasets):
        for rel_type in ds:
            labels = ds[rel_type].explode().to_frame()
            labels = labels.melt(ignore_index=False,
                                 var_name='rel_type',
                                 value_name='gene')
            labels['database'] = name
            annotations.append(labels)
    annotations = pd.concat(annotations).dropna(subset='gene').reset_index()

    # Fill genes with synonyms from ncbi
    synonyms = get_synonyms(output_dir)
    gene_ids = load_gene_ids()
    query = ('not gene.isin(@gene_ids["Approved_symbol"]) '
             'and gene.isin(@synonyms["Synonyms"])')
    mappable = annotations.query(query)
    mapper = synonyms.query('Synonyms.isin(@mappable.gene)')
    mapper = mapper.set_index('Synonyms')['Symbol']
    mappable = mappable.gene.map(mapper)
    annotations.loc[mappable.index, 'gene'] = mappable.values
    annotations = annotations.query('gene.isin(@gene_ids["Approved_symbol"])')
    annotations = annotations.reset_index(drop=True).copy()
    annotations.to_parquet(filepath)
    return annotations
