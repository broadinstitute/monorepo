#!/usr/bin/env python3

from pathlib import Path

import pytest
from broad_babel.query import broad_to_standard, export_csv, run_query


def test_export():
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
        "BRD-K18895904-001-16-1",
        ("BRD-K36461289-001-05-8",),
        ("BRD-K36461289-001-05-8", "ccsbBroad304_16164"),
        ("ccsbBroad304_16164", "BRD-K48830578-001-01-9"),
    ],
)
@pytest.mark.parametrize(
    "output_column", ["standard_key", "broad_sample", "pert_type", "JCP2022"]
)
def test_basic_query_broad(query, output_column):
    run_query(query, input_column="broad_sample", output_column=output_column)


@pytest.mark.parametrize(
    "query",
    [
        "",
        "BRD-K18895904-001-16-1",
        ("BRD-K36461289-001-05-8",),
        ("BRD-K36461289-001-05-8", "ccsbBroad304_16164"),
        ("ccsbBroad304_16164", "BRD-K48830578-001-01-9"),
    ],
)
def test_broad_to_standard(query):
    broad_to_standard(query)


@pytest.mark.parametrize(
    "query",
    ("BRD-K18895904%", "BRD-K21728777%"),
)
def test_like_query(query):
    run_query(
        query,
        input_column="broad_sample",
        output_column="*",
        operator="LIKE",
    )
