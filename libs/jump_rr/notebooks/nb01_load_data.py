# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
#     "polars",
#     "jump-rr",
# ]
# ///

"""Centralized data loading and name-mapping helpers for the JUMP pipeline."""

import marimo

__generated_with = "0.23.1"
app = marimo.App(width="medium")

with app.setup:
    import polars as pl

    from jump_rr.consensus import get_consensus_meta_urls
    from jump_rr.datasets import get_dataset
    from jump_rr.mappers import (
        get_compound_mappers,
        get_external_mappers,
    )

    SUBSETS = ("crispr", "orf", "compound")
    JCP_COL = "Metadata_JCP2022"
    JCP_SHORT = "JCP2022"
    STD_OUTNAME = "Perturbation"
    REPLICABILITY_COLS = {
        "corrected_p_value": "Corrected p-value",
        "mean_average_precision": "Phenotypic activity",
    }


@app.function
def load_profiles(dset: str) -> pl.DataFrame:
    """Load morphological profiles eagerly for a named JUMP subset."""
    return pl.read_parquet(get_dataset(dset))


@app.function
def load_profiles_lazy(dset: str) -> pl.LazyFrame:
    """Lazy-scan the parquet file for a named JUMP subset."""
    return pl.scan_parquet(get_dataset(dset, return_pooch=False))


@app.function
def build_mappers(
    df: pl.DataFrame, jcp_col: str, dset: str
) -> tuple[dict, dict, dict, dict]:
    """Build JCP-to-standard, JCP-to-entrez, std-to-omim, std-to-ensembl mappers."""
    return get_external_mappers(df, jcp_col, dset)


@app.function
def build_key_source_mapper(
    dset: str,
    jcp_col: str,
    jcp_to_std: dict,
    jcp_to_entrez: dict,
    std_to_omim: dict,
    std_to_ensembl: dict,
) -> list:
    """Build the key-source-mapper list for external links (genetic vs compound)."""
    if dset != "compound" and not dset.startswith("compound"):
        return [
            ("entrez", jcp_col, jcp_to_entrez),
            ("omim", STD_OUTNAME, std_to_omim),
            (
                "genecards",
                STD_OUTNAME,
                dict(zip(jcp_to_std.values(), jcp_to_std.values())),
            ),
            ("ensembl", STD_OUTNAME, std_to_ensembl),
        ]
    return [(k, jcp_col, v) for k, v in get_compound_mappers()]


@app.function
def compute_consensus(df: pl.DataFrame, col: str) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Compute aggregated median values and metadata for a given dataframe."""
    return get_consensus_meta_urls(df, col)


# --- Interactive UI ---


@app.cell
def _(mo):
    mo.md("# JUMP Data Loader\nSelect a dataset to inspect its profiles.")
    return ()


@app.cell
def _(mo):
    subset_selector = mo.ui.dropdown(
        options=list(SUBSETS),
        value="crispr",
        label="Dataset",
    )
    subset_selector
    return (subset_selector,)


@app.cell
def _(mo, subset_selector):
    run_btn = mo.ui.run_button(label="Load dataset")
    run_btn
    return (run_btn,)


@app.cell
def _(mo, run_btn, subset_selector):
    mo.stop(not run_btn.value)
    data = load_profiles_lazy(subset_selector.value)
    schema = data.collect_schema()
    meta_cols = [c for c in schema.names() if c.startswith("Metadata_")]
    feat_cols = [c for c in schema.names() if not c.startswith("Metadata_")]
    mo.md(
        f"**{subset_selector.value}** — "
        f"{len(meta_cols)} metadata columns, {len(feat_cols)} feature columns"
    )
    return ()


if __name__ == "__main__":
    app.run()
