#!/usr/bin/env python3
import sqlite3
from importlib import resources

con = sqlite3.connect("names.db")
TABLE = "names"


def run_query(query: str, input_column: str, output_column: str) -> str:
    cur = con.cursor()
    return cur.execute(
        f"SELECT {output_column} FROM {TABLE} WHERE {input_column} = ?",
        (query,),
    ).fetchall()
