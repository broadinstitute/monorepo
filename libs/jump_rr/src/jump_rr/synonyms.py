"""
Functions to get gene synonyms.
"""
import polars as pl
from functools import cache

@cache
def get_synonym_mapper():
    mapper = pl.read_csv("https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz", separator="\t")
    nonempty = mapper.filter(pl.col("Synonyms")!="-")
    res = nonempty.select(pl.col(["GeneID", "Synonyms"]))
    return dict(res.iter_rows())

def get_synonyms(gene_id:int):
    synonyms = get_synonym_mapper().get(gene_id)
    if synonyms is not None:
        synonyms = synonyms.split("|")
    return synonyms

