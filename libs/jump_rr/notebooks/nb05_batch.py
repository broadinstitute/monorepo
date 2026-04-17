# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
#     "duckdb>=1.1.3",
#     "cupy",
#     "dask",
#     "numpy",
# ]
# ///

"""Batch generation of all JUMP databases — replaces generate_databases.sh."""

import marimo

__generated_with = "0.23.1"
app = marimo.App(width="medium")

with app.setup:
    from pathlib import Path

    import duckdb
    import marimo as mo  # noqa: F401
    from nb02_galleries import generate_gallery
    from nb03_matches import generate_matches
    from nb04_features import generate_features

    DEFAULT_OUTPUT_DIR = Path("./databases")


@app.function
def run_all(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, duckdb.DuckDBPyRelation]:
    """
    Run the full pipeline across all datasets.

    Generates galleries, cosine similarity matches, and feature significance
    rankings for crispr, orf, and compound datasets.
    """
    results = {}

    # Phase 1: Galleries
    for dset in ("orf", "crispr", "compound"):
        print(f"Generating gallery for {dset}...")
        results[f"{dset}_gallery"] = generate_gallery(dset, output_dir)

    # Phase 2: Matches
    for dset, n_vals in (("crispr", 25), ("orf", 25), ("compound", 10)):
        print(f"Computing matches for {dset}...")
        results[dset] = generate_matches(dset, n_vals, output_dir)

    # Phase 3: Features
    for dset, n_feat, n_comp in (
        ("crispr_interpretable", 30, 50),
        ("orf_interpretable", 30, 50),
        ("compound_interpretable", 10, 50),
    ):
        print(f"Computing features for {dset}...")
        results[f"{dset}_features"] = generate_features(
            dset, n_feat, n_comp, output_dir
        )

    return results


# --- Interactive UI ---


@app.cell
def _(mo):
    mo.md(
        "# Batch Database Generation\n"
        "Run the full pipeline across all three datasets.\n\n"
        "**Warning:** This requires a GPU, significant RAM, and will take a long time."
    )
    return ()


@app.cell
def _(mo):
    batch_run = mo.ui.run_button(label="Generate all databases")
    batch_run
    return (batch_run,)


@app.cell
def _(batch_run, mo):
    mo.stop(not batch_run.value)
    _results = run_all()
    _summary = "\n".join(
        f"- **{name}**: {duckdb.sql('SELECT COUNT(*) FROM rel').fetchone()[0]} rows"
        for name, rel in _results.items()
    )
    mo.md(f"## Results\n{_summary}")
    return ()


@app.cell
def _(mo):
    mo.stop(mo.app_meta().mode != "run")
    _results = run_all()
    for _name, _rel in _results.items():
        _count = duckdb.sql("SELECT COUNT(*) FROM _rel").fetchone()[0]
        print(f"{_name}: {_count} rows")
    print("Batch generation complete.")
    return ()


if __name__ == "__main__":
    app.run()
