"""Functions to get gene synonyms."""

from functools import cache

import polars as pl

"""Generate a dictionary of synonyms mapping an Entrez Gene ID to its other names."""


@cache
def get_synonym_mapper() -> dict[str, str]:
    """
    Retrieve a dictionary mapping GeneIDs to their corresponding synonyms.

    This function reads a csv file from a specified URL, filters out rows with empty Synonyms,
    selects only the GeneID and Synonyms columns, casts them to strings, and returns the result as a dictionary.

    Returns
    -------
    dict
        A dictionary where keys are GeneIDs and values are their corresponding synonyms.

    Notes
    -----
    The synonyms data is sourced from the National Center for Biotechnology Information (NCBI).
    The results are cached in-memory.

    """
    mapper = pl.read_csv(
        "https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz",
        separator="\t",
    )
    nonempty = mapper.filter(pl.col("Synonyms") != "-")
    res = nonempty.select(pl.col(["GeneID", "Synonyms"]).cast(str))
    return dict(res.iter_rows())
