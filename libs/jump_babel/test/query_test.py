#!/usr/bin/env python3
"""Test queries of JUMP data."""

from collections.abc import Iterable
from pathlib import Path

import pytest
from broad_babel.query import broad_to_standard, export_csv, run_query


def test_export() -> None:
    """
    Test the export_csv function by checking if a CSV file is generated.

    This test creates a temporary CSV file and checks if it exists after calling
    the export_csv function. If the file does not exist before the test and
    exists after the test, then the test passes.
    """
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
def test_basic_query_broad(query: str or Iterable, output_columns: str) -> None:
    """
    Test the run_query function with different input queries and output columns.

    This test checks if the run_query function works correctly for different
    types of input queries (e.g., empty tuple, single string, multiple strings)
    and output columns.
    """
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
def test_broad_to_standard(query: str or Iterable) -> None:
    """
    Test the broad_to_standard function with different input queries.

    This test checks if the broad_to_standard function works correctly for
    different types of input queries (e.g., empty string, single string,
    multiple strings).
    """
    broad_to_standard(query)


@pytest.mark.parametrize(
    "query",
    ("ccsbBroad304_1616%", "ccsbBroad304_1613%"),
)
def test_like_query(query: str) -> None:
    """
    Test the run_query function with a LIKE operator.

    This test checks if the run_query function works correctly when using
    the LIKE operator for queries that contain a wildcard character.
    """
    run_query(
        query,
        input_column="broad_sample",
        output_columns="*",
        operator="LIKE",
    )
