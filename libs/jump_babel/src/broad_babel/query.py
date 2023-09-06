"""
Basic querying logic using Python's sqlite
"""
import csv
import sqlite3
import typing as t

import importlib_resources

DB_NAME = "names.db"
TABLE = "names"

with importlib_resources.files("broad_babel") as f:
    DB_FILE = f / "data" / DB_NAME


def run_query(
    query: str or t.List[str], input_column: str, output_column: str or t.List[str]
) -> str or t.Dict[str, str]:
    """Query one or multiple values to the database.

    Parameters
    ----------
    query : str or t.List[str]
        Input identifiers
    input_column : str
        Type of name the input belongs to. It can be jump_id, broad_sample or standard_key.
    output_column : str or t.List[str]
        Desired name translation.

    Returns
    -------
    str or t.Dict[str, str]
        Translated name (str) if query is string.
        Dictionary with input->output names if the input is a collection of strings.

    """
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    expression_prefix = (
        expression
    ) = f"SELECT {output_column} FROM {TABLE} WHERE {input_column} "
    placeholder = "?"  # For SQLite. See DBAPI paramstyle.
    if isinstance(query, str):
        operator = "="
        query = (query,)
    else:
        operator = "IN"
        placeholder = ", ".join(placeholder for _ in query)
    expression = expression_prefix + operator + " (%s)" % placeholder
    return cur.execute(expression, query).fetchall()


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
    assert len(query) == len(result), "Not all entries are present"
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
    with open(output, "w", newline="") as f:
        con = sqlite3.connect(DB_FILE)
        cur = con.cursor()
        data = cur.execute(f"SELECT * FROM {table}").fetchall()
        data = [[x if x is not None else "" for x in row] for row in data]
        writer = csv.writer(f)

        writer.writerow(
            [x[1] for x in cur.execute(f"PRAGMA table_info({TABLE})").fetchall()]
        )
        writer.writerows(data)
