import json
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from jump.biokg import open_zip as open_biokg
from jump.dgidb import open_tsv_files as open_dgidb
from jump.drugrep import open_data as open_drugrep
from jump.hetionet import open_zip as open_hetionet
from jump.openbiolink import open_zip as open_openbiolink
from jump.pharmebinet import open_gz as open_pharmebinet
from jump.primekg import load_kg as open_kg


def export(output_path):
    biokg = open_biokg(output_path)
    rel_types = [  # noqa: F841
        "DPI",
        "DRUG_CARRIER",
        "DRUG_DISEASE_ASSOCIATION",
        "DRUG_ENZYME",
        "DRUG_PATHWAY_ASSOCIATION",
        "DRUG_TARGET",
        "DRUG_TRANSPORTER",
    ]
    biokg_drugbank_id = pd.concat(
        [
            biokg.query('rel_type=="DDI"')[["source", "target"]].melt()["value"],
            biokg.query("rel_type in @rel_types").source,
        ]
    )

    drugs, genes, edges, categories = open_dgidb(output_path)
    edges["drug_concept_id"] = edges["drug_concept_id"].fillna("")
    edges = edges.query('drug_concept_id.str.match("chembl:")').copy()
    edges["drug_concept_id"] = edges.drug_concept_id.str[len("chembl:") :]
    dgidb_chembl_id = edges["drug_concept_id"].dropna().drop_duplicates()

    edges = open_drugrep(output_path)
    drugrep_pubchem_id = edges["pubchem_cid"].dropna().drop_duplicates()

    edges, nodes = open_hetionet(output_path)
    query = 'source.str.startswith("Compound") and target.str.startswith("Gene")'
    edges = edges.query(query).copy()
    edges["source"] = edges["source"].str[len("Compound::") :]
    hetionet_drugbank_id = edges["source"].dropna().drop_duplicates()

    edges, nodes = open_openbiolink(output_path)
    query = 'source.str.startswith("PUBCHEM") and target.str.startswith("NCBIGENE")'
    edges = edges.query(query).copy()
    edges["pubchem_id"] = edges["source"].str.split(":", expand=True)[1]
    edges["ncbi_id"] = edges["target"].str.split(":", expand=True)[1]
    openbiolink_pubchem_id = edges["pubchem_id"].dropna().drop_duplicates()

    edges, nodes = open_pharmebinet(output_path)
    cpd_nodes = nodes.query('labels=="Chemical|Compound"')
    cpd_node_props = pd.DataFrame(cpd_nodes["properties"].apply(json.loads).tolist())
    for col in "node_id", "identifier", "name":
        cpd_node_props[col] = cpd_nodes[col].values
    pharmebinet_drugbank_id = cpd_node_props.identifier.dropna().drop_duplicates()

    kg = open_kg(output_path)
    annotations = kg.query('x_type=="drug" and y_type=="gene/protein"')
    primekg_drugbank_id = annotations.x_id.dropna().drop_duplicates()

    drugbank_id = np.unique(
        np.concatenate(
            [
                biokg_drugbank_id,
                hetionet_drugbank_id,
                pharmebinet_drugbank_id,
                primekg_drugbank_id,
            ]
        )
    )

    pubchem_id = np.unique(
        np.concatenate(
            [
                openbiolink_pubchem_id,
                drugrep_pubchem_id,
            ]
        )
    )

    chembl_id = dgidb_chembl_id.values

    external_id_path = output_path / "external_ids"
    external_id_path.mkdir(parents=True, exist_ok=True)
    np.savetxt(external_id_path / "pubchem.txt", pubchem_id, fmt="%s")
    np.savetxt(external_id_path / "chembl.txt", chembl_id, fmt="%s")
    np.savetxt(external_id_path / "drugbank.txt", drugbank_id, fmt="%s")


def main():
    parser = argparse.ArgumentParser(description="export all external_ids in txt files")
    parser.add_argument("output_path")
    args = parser.parse_args()
    export(Path(args.output_path))


if __name__ == "__main__":
    main()
