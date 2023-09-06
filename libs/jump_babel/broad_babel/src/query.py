#!/usr/bin/env python3
import csv
import sqlite3
import typing as t

import importlib_resources


DB_NAME = "names.db"
TABLE = "names"


with importlib_resources.files("broad_babel") as f:
    print(f / "data" / DB_NAME)


def run_query(query: str or t.List[str], input_column: str, output_column: str) -> str:
    con = sqlite3.connect("names.db")
    cur = con.cursor()
    return cur.execute(
        f"SELECT {output_column} FROM {TABLE} WHERE {input_column} = ?",
        (query,),
    ).fetchall()


def export_csv(table: str = TABLE, output: str = "exported.csv"):
    with open(output, "w", newline="") as f:
        con = sqlite3.connect("names.db")
        cur = con.cursor()
        data = cur.execute(f"SELECT * FROM {table}").fetchall()
        data = [[x if x is not None else "" for x in row] for row in data]
        writer = csv.writer(f)

        writer.writerow(
            [x[1] for x in cur.execute(f"PRAGMA table_info({TABLE})").fetchall()]
        )
        writer.writerows(data)
