"""
Basic querying logic using Python's sqlite
"""
import csv
import sqlite3
import typing as t
from functools import cache

import pooch

DB_FILE = pooch.retrieve(
    # Temporarily  using URL out due to Zenodo API change
    # https://github.com/zenodo/zenodo/issues/2506
    url=("https://zenodo.org/records/11623418/files/" "babel.db"),
    known_hash="md5:7b23bfafbbfc9920a47e304e7096ef9c",
)
TABLE = "babel"


@cache
def run_query(
    query: str or tuple[str],
    input_column: str,
    output_columns: str or str,
    operator: None or str = None,
    predicate: None or str = None,
) -> str or t.Dict[str, str]:
    """Query one or multiple values to the database.

    Parameters
    ----------
    query : str or t.List[str]
        Input identifiers
    input_column : str
        Type of name the input belongs to. It can be  standard_key,JCP2022,plate_type,NCBI_Gene_ID,broad_sample or pert_type.
    output_columns : str or t.List[str]
        Desired name translation.
    operator : None or str
        Type of comparison to use, default is "=", but use "LIKE" to match an expression.
    predicate : None or str
        Additional expressions

    Returns
    -------
    str, t.List[t.Tuple[str]] or t.Dict[str, str]
        - Translated name (str) if query is string and only one occurrence is found.
        - List of tuples with all fields if output_column is not one column or multiple occurrnces are found.
        - Dictionary with input->output names if the input is a collection of strings.
    """

    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    expression_prefix = (
        expression
    ) = f"SELECT {output_columns} FROM {TABLE} WHERE {input_column} "
    placeholder = "?"  # For SQLite. See DBAPI paramstyle.
    if isinstance(query, str):
        operator = operator or "="
        query = (query,)
    else:
        operator = "IN"
        placeholder = ", ".join(placeholder for _ in query)
    expression = expression_prefix + operator + " (%s)" % placeholder
    if predicate is not None:
        expression += f" {predicate}"

    result = cur.execute(expression, query).fetchall()
    # Remove duplicates (e.g., different broad ids, same JUMP ids)
    no_duplicates = list(set(result))

    return no_duplicates


def get_mapper(
    query: list or tuple, input_column: str, output_columns: str
) -> dict[str, str]:
    """
    Convenience function to generate a mapper from a set of queries.
    It delegates matching to sqlite3 and ensures prefixes are removed.
    Unlike "run_query", this returns a one-to-one relationship by compressing
    the repeated inputs into a dictionary.

    Parameters
    ----------
    query : str or t.List[str]
        Input identifiers
    input_column : str
        Type of name the input belongs to. It can be JCP2022, broad_sample or standard_key.
    output_columns : str or t.List[str]
        Desired value of resulting dictionary

    Returns
    -------
    Dictionary where keys are input_column items and values are their equivalent
    """
    assert len(output_columns.split(","))==2, "Incorrect number of output columns"

    input_column = input_column.removeprefix("Metadata_")
    output_columns = input_column.removeprefix("Metadata_")
    # return dict(
    tmp = run_query(
            query,
            input_column=input_column,
            output_columns=output_columns,
        )
    # )


def broad_to_standard(query: str or t.List[str]) -> str or t.Dict[str, str]:
    """Convert broad ids to standard, either InChiKey or Entrez Gene name.

    Parameters
    ----------
    query : str or t.List[str]
    Input, if str it returns string, if List it returns a dictionary. Function fails if not al queries are found

    """
    result = run_query(query, "broad_sample", "standard_key")
    if len(result) == 1:
        return result[0][0]

    assert len(query) == len(
        result
    ), f"Value {query} for broad_sample led to {len(result)} results"

    for broad_sample, results in zip(query, result):
        assert (
            len(results) == 1
        ), f"Invalid number of results for broad_sample {broad_sample}"

    return {brd: std[0] for brd, std in zip(query, result)}


def export_csv(output: str = "exported.csv", table: str = TABLE):
    """Export entire translation table as csv.

    Parameters
    ----------
    table : str
        (optional) table name, if multiple ones. Default is "names"
    output : str
        filepath of resultant file

    Examples
    --------
    from broad_babel import query

    query.export_csv("my_file.csv")
    """
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    with open(output, "w", newline="") as f:
        data = cur.execute(f"SELECT * FROM {table}").fetchall()
        data = [[x if x is not None else "" for x in row] for row in data]
        writer = csv.writer(f)

        headers = [x[1] for x in cur.execute(f"PRAGMA table_info({TABLE})").fetchall()]
        writer.writerow(headers)
        writer.writerows(data)

