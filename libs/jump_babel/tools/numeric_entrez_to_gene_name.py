#!/usr/bin/env python3
"""
Convert NCBI Gene ids to gene names. This is not currently used, but is likely to prove handy.

Requires biopython and tqdm (or just install dev dependencies via poetry)
"""
import csv
import json
from pathlib import Path

from Bio import Entrez
from more_itertools import sliced
from tqdm import tqdm

source_path = Path("./data/crispr.csv")

with open(source_path, newline="") as csvfile:
    reader = csv.DictReader(csvfile)
    keys = []
    missing_indices = []
    clean_keys = []
    for i, row in enumerate(reader):
        keys.append(row["Metadata_NCBI_Gene_ID"])
        if row["Metadata_NCBI_Gene_ID"] == "NA":
            missing_indices.append(i)
        else:
            clean_keys.append(row["Metadata_NCBI_Gene_ID"])


Entrez.email = "A.N.Other@example.com"
keys_query = ",".join(clean_keys)
# Chunked based on maximum UID request
chunked = [",".join(x) for x in sliced(clean_keys, 500)]

keys_vals = {}
for chunk in tqdm(chunked):
    handle = Entrez.esummary(db="gene", id=chunk, retmode="json")
    tmp = "".join([x.decode("UTF-8") for x in handle.readlines()])
    val = json.loads(tmp)

    for k, v in val["result"].items():
        if k != "uids":
            # Double-check for duplicates
            assert k not in keys_vals, "Duplicated names"
            keys_vals[int(k)] = v["name"]
