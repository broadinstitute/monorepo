"""
Functions to get gene synonyms.
"""

from functools import cache

import polars as pl


@cache
def get_synonym_mapper():
    mapper = pl.read_csv(
        "https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz",
        separator="\t",
    )
    nonempty = mapper.filter(pl.col("Synonyms") != "-")
    res = nonempty.select(pl.col(["GeneID", "Synonyms"]).cast(str))
    return dict(res.iter_rows())
