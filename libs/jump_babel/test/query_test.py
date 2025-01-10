#!/usr/bin/env python3

from pathlib import Path

import pytest
from broad_babel.query import broad_to_standard, export_csv, run_query


def test_export() -> None:
    filepath = Path("_test_export.csv")
    assert not filepath.exists(), "Test cannot be performed, file exists"
    export_csv(filepath)
    assert filepath.exists(), "CSV was not generated"
    filepath.unlink()


@pytest.mark.parametrize(
    "query",
    [
        tuple(),
        "",
        "ccsbBroad304_16164",
        ("ccsbbroad304_11164",),
        ("ccsbBroad304_16164", "ccsbBroad304_16165"),
        ("ccsbbroad304_16164", "ccsbBroad304_16165"),
    ],
)
@pytest.mark.parametrize(
    "output_columns", ["standard_key", "broad_sample", "pert_type", "JCP2022"]
)
def test_basic_query_broad(query, output_columns) -> None:
    run_query(query, input_column="broad_sample", output_columns=output_columns)


@pytest.mark.parametrize(
    "query",
    [
        "",
        "ccsbBroad304_16164",
        ("ccsbBroad304_16164",),
        ("ccsbBroad304_16164", "ccsbBroad304_16165"),
        ("ccsbBroad304_16164", "ccsbBroad304_16165"),
    ],
)
def test_broad_to_standard(query) -> None:
    broad_to_standard(query)


@pytest.mark.parametrize(
    "query",
    ("ccsbBroad304_1616%", "ccsbBroad304_1613%"),
)
def test_like_query(query) -> None:
    run_query(
        query,
        input_column="broad_sample",
        output_columns="*",
        operator="LIKE",
    )
