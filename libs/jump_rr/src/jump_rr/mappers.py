#!/usr/bin/env jupyter
"""Functions to get and use mappers."""

import duckdb
import polars as pl
from broad_babel.query import run_query
from pooch import retrieve

"""Generate a dictionary of synonyms mapping an Entrez Gene ID to its other names."""

MAPPERS = {
    "omim": (
        "https://www.omim.org/static/omim/data/mim2gene.txt",
        "835396a88350b0487d9c45f1eb1321c158777275a0faedf863a07d7d02b88f5e",
    ),
    "synonym": (
        "https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz",
        "19acf7198587fde68e7922e3501303078514a4e5c995afcf0fd11d8e6446ffa1",
    ),
    "compound": (
        "https://zenodo.org/api/records/15644946/files/jcp_to_dbs.parquet/content",
        "04cda85280b512ffde836ec2aa1d9fd7114e9b5cf6f9c395c648b0eaba4497ca",
    ),
}


def get_mapper(
    ids: tuple[str],
    plate_type: str,
    input_col: str = "JCP2022",
    output_cols: tuple[str] = ("standard_key", "NCBI_Gene_ID"),
    format_output: bool = True,
) -> dict:
    """
    Generate translators based on an identifier using broad-babel.

    Parameters
    ----------
    ids : tuple[str]
        A tuple of identifiers.
    plate_type : str
        The type of plate (crispr, orf or compound).
    input_col : str, optional
        The name of the input column (default is "JCP2022").
    output_cols : list[str], optional
        A list of names for the output columns (default is ["standard_key", "NCBI_Gene_ID"]).
    format_output : bool, optional
        Whether to format the output to link to external ids, such as NCBI/Entrez ids (default is True).

    Returns
    -------
    dict
        A dictionary containing the mappers.

    """
    mapper_values = run_query(
        query=ids,
        input_column=input_col,
        output_columns=",".join((input_col, *output_cols)),
        predicate=f"AND plate_type = '{plate_type}'",
    )

    mappers = {k: {} for k in output_cols}
    for input_id, *output_ids in mapper_values:
        for k, new_id in zip(mappers.keys(), output_ids):
            mappers[k][input_id] = new_id
    return list(mappers.values())


def get_external_mappers(
    profiles: pl.DataFrame, col: str, dset: str
) -> tuple[dict[str, str]]:
    """
    Generate external mappers for a given column of the provided DataFrame.

    The mappers link JCP ids to gene names/InChiKeys, urls of external ids and
    the raw external id.

    Parameters
    ----------
    profiles : pl.DataFrame
        Input dataframe containing profiles.
    col : str
        Column name to generate mappers for.
    dset : str
        Dataset type for which to generate mapper (crispr, orf or compound).

    Returns
    -------
    jcp_to_std : dict[str, str]
        Standard mapper for JCP values to Gene Names or InChiKeys.
    jcp_to_external : dict[str, str]
        External mapper for JCP values to a formatted URL of the Entrez id.
    jcp_to_external_raw : dict[str, str]
        Raw external mapper for JCP values to the numeric NCBI id.

    Notes
    -----
    `dset` is used to avoid uncertainty because crispr and orf share some gene names.

    """
    uniq = tuple(profiles.get_column(col).unique())
    jcp_to_std, jcp_to_entrez = get_mapper(uniq, dset)
    assert len(jcp_to_std), f"No mappers were found {col=}, {dset=}"

    entrez_to_omim = {}
    entrez_to_ensembl = {}

    other_ids = pl.DataFrame({
        "entrez": jcp_to_entrez.values(),
        "std": jcp_to_std.values(),
    })

    if any(jcp_to_entrez.values()):
        other_ids = other_ids.filter(~pl.col("entrez").str.contains("[A-Z]")).unique()
        entrez_to_omim, entrez_to_ensembl = get_omim_mappers(other_ids)

    return jcp_to_std, jcp_to_entrez, entrez_to_omim, entrez_to_ensembl


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

    """
    url, known_hash = MAPPERS["synonym"]
    mapper = pl.read_csv(
        retrieve(url, known_hash),
        separator="\t",
    )
    nonempty = mapper.filter(pl.col("Synonyms") != "-")
    res = nonempty.with_columns(
        pl.concat_str(("Symbol", "Synonyms"), separator="|").alias("Synonyms")
    ).select(pl.col(["GeneID", "Synonyms"]).cast(str))
    return dict(res.iter_rows())


def get_omim_mappers(other_ids: pl.DataFrame) -> tuple[dict, dict]:
    """
    Retrieve omim and ensembl mappers from a dataframe.

    Parameters
    ----------
    other_ids : pl.DataFrame
        A DataFrame containing gene identifiers.

    Returns
    -------
    tuple[dict, dict]
        Two dictionaries containing the mapped OMIM data.

    """

    url, known_hash = MAPPERS["omim"]
    with duckdb.connect(":memory:"):
        duckdb.execute(
            f"""
            CREATE OR REPLACE TABLE gene_names AS
            SELECT #1, #3, #4, #5 FROM read_csv_auto('{retrieve(url, known_hash)}', normalize_names=True)
        """
        )
        # Remove letter entries in ncbi id
        duckdb.sql(
            """
            CREATE OR REPLACE TABLE match_ids AS
            SELECT * FROM other_ids
        """
        )
        # Joining with gene symbols gives more hits than entrez ids
        valid_entries = duckdb.sql(
            """
            SELECT * FROM gene_names A
            INNER JOIN match_ids B
            on A.approved_gene_symbol_hgnc = B.std;
        """
        ).pl()

    return [
        dict(valid_entries.select(pl.col("approved_gene_symbol_hgnc", x)).rows())
        for x in ("mim_number", "ensembl_gene_id_ensembl")
    ]


# %%
def get_compound_mappers() -> tuple[tuple[str, dict[str, str or int]]]:
    """Get mapping between jcp ids and compound ids from different databases."""
    url, known_hash = MAPPERS["compound"]
    with duckdb.connect(":memory:") as con:
        tb = con.sql(
            f"""select Metadata_JCP2022,COLUMNS("id.*") from read_parquet(
            '{retrieve(url, known_hash)}')
            where Metadata_JCP2022 IS NOT NULL;"""
        )
        unpiv = con.sql(
            "unpivot tb on CAST(columns(* exclude(Metadata_JCP2022)) as VARCHAR)"
        ).pl()
        return {
            k[0][3:]: dict(v.rows())
            for k, v in unpiv.partition_by(
                "name", as_dict=True, include_key=False
            ).items()
        }.items()
