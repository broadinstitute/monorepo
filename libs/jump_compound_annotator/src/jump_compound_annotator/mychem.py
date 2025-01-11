import json
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from tqdm.contrib.concurrent import thread_map


def inchis_from_chembl(ids: np.ndarray):
    data = {
        "q": ids.tolist(),
        "scopes": ["chembl.molecule_chembl_id"],
        "fields": ["chembl.inchikey"],
    }
    response = requests.post("https://mychem.info/v1/query?size=500", json=data)
    return response.json()


def save_chembl_mapper(output_dir, codes):
    output_path = Path(output_dir)
    output_file = output_path / "mychem_chembl_mapper.parquet"
    batches = np.split(codes, np.arange(500, len(codes), 500))
    result = thread_map(inchis_from_chembl, batches, max_workers=8)
    result = sum(result, [])

    mapper = {}
    for dbid, rs in zip(codes, result):
        if "error" not in rs and "notfound" not in rs:
            mapper[dbid] = rs["_id"]
        else:
            mapper[dbid] = json.dumps(rs)

    mapper = pd.Series(mapper, name="inchikey")
    mapper.index.name = "chembl"
    mapper.reset_index().to_parquet(output_file)


def inchis_from_pubchem(ids: np.ndarray):
    data = {
        "q": ids.tolist(),
        "scopes": ["pubchem.cid"],
        "fields": ["pubchem.inchikey"],
    }
    response = requests.post("https://mychem.info/v1/query?size=500", json=data)
    return response.json()


def save_pubchem_mapper(output_dir, codes):
    output_path = Path(output_dir)
    output_file = output_path / "mychem_pubchem_mapper.parquet"
    batches = np.split(codes, np.arange(500, len(codes), 500))
    result = thread_map(inchis_from_pubchem, batches, max_workers=8)
    result = sum(result, [])

    mapper = {}
    for dbid, rs in zip(codes, result):
        if "error" not in rs and "notfound" not in rs:
            mapper[dbid] = rs["_id"]
        else:
            mapper[dbid] = json.dumps(rs)

    mapper = pd.Series(mapper, name="inchikey")
    mapper.index.name = "pubchem"
    mapper.reset_index().to_parquet(output_file)


def inchis_from_drugbank(ids: np.ndarray):
    data = {
        "q": ids.tolist(),
        "scopes": ["drugbank.id"],
        "fields": ["drugbank.inchikey"],
    }
    response = requests.post("https://mychem.info/v1/query?size=500", json=data)
    return response.json()


def save_drugbank_mapper(output_dir, codes):
    output_path = Path(output_dir)
    output_file = output_path / "mychem_drugbank_mapper.parquet"
    batches = np.split(codes, np.arange(500, len(codes), 500))
    result = thread_map(inchis_from_drugbank, batches, max_workers=8)
    result = sum(result, [])

    mapper = {}
    for dbid, rs in zip(codes, result):
        if "error" not in rs and "notfound" not in rs:
            mapper[dbid] = rs["_id"]
        else:
            mapper[dbid] = json.dumps(rs)

    mapper = pd.Series(mapper, name="inchikey")
    mapper.index.name = "drugbank"
    mapper["DB01361"] = "LQCLVBQBTUVCEQ-QTFUVMRISA-N"
    mapper["DB01398"] = "YGSDEFSMJLZEOE-UHFFFAOYSA-N"
    mapper["DB00667"] = "NTYJJOPFIAHURM-UHFFFAOYSA-N"
    mapper["DB00729"] = "BREMLQBSKCSNNH-UHFFFAOYSA-M"
    mapper["DB08866"] = "LRHSUZNWLAJWRT-GAJBHWORSA-N"
    mapper.reset_index().to_parquet(output_file)


def save_mapper(output_dir, codes, source_id):
    if source_id == "pubchem":
        save_pubchem_mapper(output_dir, codes)
    if source_id == "chembl":
        save_chembl_mapper(output_dir, codes)
    if source_id == "drugbank":
        save_drugbank_mapper(output_dir, codes)


def get_mapper(output_dir, source_id):
    output_path = Path(output_dir)
    output_file = output_path / f"mychem_{source_id}_mapper.parquet"
    return pd.read_parquet(output_file).set_index(source_id)["inchikey"]


def get_inchikeys(output_dir, source_ids, codes):
    db_mapper = get_mapper(output_dir, "drugbank")
    ch_mapper = get_mapper(output_dir, "chembl")
    pc_mapper = get_mapper(output_dir, "pubchem")

    drugbank_mask = source_ids == "drugbank"
    chembl_mask = source_ids == "chembl"
    pubchem_mask = source_ids == "pubchem"

    inchikeys = pd.Series(index=codes.index, dtype=str)
    inchikeys[drugbank_mask] = codes.map(db_mapper)
    inchikeys[chembl_mask] = codes.map(ch_mapper)
    inchikeys[pubchem_mask] = codes.map(pc_mapper)

    inchi_regex = r"^([A-Z]{14}\-[A-Z]{10})(\-[A-Z])$"
    inchi_match = inchikeys.fillna("").str.fullmatch(inchi_regex)
    inchikeys[~inchi_match] = None
    return inchikeys
