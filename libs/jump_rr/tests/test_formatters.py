"""External resource links are JSON for the datasette-json-html plugin."""

import json
from pathlib import Path

import polars as pl
import pytest

from jump_rr.formatters import add_external_sites, format_value


@pytest.mark.parametrize("ensembl_id", ["ENSG00000141510", "ENSG00000166851"])
def test_hpa_link(ensembl_id: str) -> None:
    assert json.loads(format_value("href", "hpa", ensembl_id)) == {
        "href": f"https://www.proteinatlas.org/{ensembl_id}",
        "label": "HPA",
    }


def test_empty_hpa_link() -> None:
    assert format_value("href", "hpa", "") == ""


@pytest.mark.parametrize("lazy", [False, True])
@pytest.mark.parametrize(
    ("source_col", "resources_col"),
    [("Perturbation", "Resources"), ("Match", "Match resources")],
)
def test_hpa_resources(
    lazy: bool, source_col: str, resources_col: str, tmp_path: Path
) -> None:
    genes = ["TP53", "PLK1", "unmapped", "empty", "null", None]
    df = pl.DataFrame({source_col: genes})
    if source_col == "Match":
        # Match resources must describe the match, not the query perturbation.
        df = df.with_columns(pl.lit("PLK1").alias("Perturbation"))
    ensembl = {
        "TP53": "ENSG00000141510",
        "PLK1": "ENSG00000166851",
        "empty": "",
        "null": None,
    }
    mappers = (
        ("entrez", source_col, {"TP53": "7157", "PLK1": "5347"}),
        ("omim", source_col, {"TP53": "191170"}),
        ("genecards", source_col, {"TP53": "TP53", "PLK1": "PLK1"}),
        ("ensembl", source_col, ensembl),
        ("hpa", source_col, ensembl),
    )
    result = add_external_sites(df.lazy() if lazy else df, resources_col, mappers)
    assert isinstance(result, pl.LazyFrame if lazy else pl.DataFrame)
    if lazy:
        result = result.collect()

    resources = result[resources_col].to_list()
    for gene, raw in zip(genes[:2], resources[:2]):
        links = json.loads(raw)
        expected_labels = ["NCBI", "OMIM", "GeneCards", "Ensembl", "HPA"]
        if gene == "PLK1":
            expected_labels.remove("OMIM")
        assert [link["label"] for link in links] == expected_labels
        assert links[-1] == {
            "href": f"https://www.proteinatlas.org/{ensembl[gene]}",
            "label": "HPA",
        }
    assert resources[2:] == ["", "", "", ""]

    # The published parquet retains the renderable JSON rather than raw HTML.
    output = tmp_path / "resources.parquet"
    result.select(source_col, resources_col).write_parquet(output)
    assert pl.read_parquet(output)[resources_col].to_list() == resources


@pytest.mark.parametrize("missing_id", ["", None])
def test_missing_hpa_preserves_other_resources(missing_id: str | None) -> None:
    df = pl.DataFrame({"Perturbation": ["TP53"]})
    mappers = (
        ("entrez", "Perturbation", {"TP53": "7157"}),
        ("ensembl", "Perturbation", {"TP53": missing_id}),
        ("hpa", "Perturbation", {"TP53": missing_id}),
    )
    result = add_external_sites(df, "Resources", mappers)
    assert json.loads(result["Resources"][0]) == [
        {"href": "https://www.ncbi.nlm.nih.gov/gene/7157", "label": "NCBI"}
    ]


def test_compound_resources_unchanged() -> None:
    df = pl.DataFrame({"JCP2022": ["compound", "unmapped"]})
    mappers = (
        ("chembl", "JCP2022", {"compound": "CHEMBL25"}),
        ("drugbank", "JCP2022", {"compound": "DB00945"}),
        ("pubchem", "JCP2022", {"compound": "2244"}),
    )
    result = add_external_sites(df, "Resources", mappers)
    assert json.loads(result["Resources"][0]) == [
        {
            "href": "https://www.ebi.ac.uk/chembl/explore/compound/CHEMBL25",
            "label": "CHEMBL",
        },
        {"href": "https://go.drugbank.com/drugs/DB00945", "label": "DrugBank"},
        {"href": "https://pubchem.ncbi.nlm.nih.gov/compound/2244", "label": "PubChem"},
    ]
    assert result["Resources"][1] == ""
