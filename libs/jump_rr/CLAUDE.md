# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`jump_rr` produces browsable databases of morphological profile similarities from the [JUMP Cell Painting](https://jump-cellpainting.broadinstitute.org/) consortium. It computes pairwise cosine similarities, feature significance (t-tests with FDR correction), and image galleries, outputting parquet files served via [datasette-lite](https://github.com/simonw/datasette-lite).

## Build & Development

```bash
# Install (dev)
uv sync --all-extras --group test

# Run tests (fast only)
uv run pytest tests/

# Run tests including slow (network-dependent downloads)
uv run pytest tests/ --runslow

# Run a single test
uv run pytest tests/test_t.py::test_pvalue

# Lint
uv run ruff check src/
uv run ruff format --check src/
```

**Python version**: >3.10, <3.12 (required by pylibraft-cu12 dependency).

**GPU requirement**: `calculate_matches.py` and `index_selection.py` require CUDA GPUs (CuPy + pylibraft). The Nix flake provides a reproducible dev shell with CUDA support.

## Architecture

### Data Pipeline

Three scripts in `src/jump_rr/` run sequentially via `src/tools/generate_databases.sh`:

1. **`galleries.py`** — Generates per-well image browser tables (ORF, CRISPR, compound). Uses `pl.scan_parquet` for lazy evaluation.
2. **`calculate_matches.py`** — Computes GPU-accelerated pairwise cosine similarity between consensus profiles, selects top/bottom N matches per perturbation.
3. **`calculate_features.py`** — Identifies statistically significant features per perturbation using plate-matched t-tests with Benjamini-Hochberg FDR correction.

All three output zstd-compressed parquet files to `./databases/` and write JSON metadata to `metadata/` for datasette configuration.

### Key Modules

| Module | Purpose |
|---|---|
| `consensus.py` | Aggregates well-level profiles to perturbation-level medians; adds sample images |
| `datasets.py` | Fetches JUMP profiles from GitHub manifest + Pooch caching |
| `significance.py` | T-test pipeline: DuckDB groups plate-matched controls, Dask/NumPy computes t-stats, statsmodels corrects p-values. `pvals_from_profile()` returns `(corrected_p_values, t_statistics)` |
| `index_selection.py` | GPU-based top-k/bottom-k index selection using `da.argtopk` |
| `mappers.py` | Translates JCP2022 IDs to gene names, NCBI/OMIM/Ensembl IDs, and compound database IDs via `broad-babel` |
| `formatters.py` | Builds JSON-encoded HTML links/images for datasette rendering |
| `replicability.py` | Joins precomputed phenotypic activity (MAP) and corrected p-values from external datasets |
| `metadata.py` | Writes datasette JSON config with column descriptions and table titles |
| `parse_features.py` | Regex-based decomposition of CellProfiler feature names into Compartment/Feature/Channel/Suffix |

### Data Conventions

- **Metadata columns** are prefixed with `Metadata_` (e.g., `Metadata_JCP2022`, `Metadata_Plate`)
- **Feature columns** are everything without the `Metadata_` prefix
- Three dataset types: `crispr`, `orf`, `compound` (plus `*_interpretable` variants for feature analysis)
- JCP2022 IDs uniquely identify reagents; the 9th character distinguishes dataset type (`8`=CRISPR, `9`=ORF, `0`=compound)

### Key Dependencies

- **Polars**: Primary DataFrame library (not pandas)
- **DuckDB**: SQL-based grouping and statistics in `significance.py` and `mappers.py`
- **Dask + CuPy**: GPU-accelerated array operations for distance matrices
- **broad-babel**: Maps JCP2022 IDs to standard gene/compound identifiers
- **Pooch**: Downloads and caches remote datasets with hash verification

## Data Exploration

- **DuckDB CLI**: Available for SQL-based parquet exploration (e.g., `duckdb -c "SELECT ... FROM 'databases/file.parquet'"`)
- **S3 uploads**: Use `aws s3 cp <file> s3://cellpainting-gallery/cpg0042-chandrasekaran-jump/source_all/workspace/publication_data/ --profile cpg`
- **Zenodo record**: Published parquets are on Zenodo record `12775236` (upload script) / `15660683` (latest data)
- **Local parquets**: Generated files go to `./databases/` (gitignored)

## Ruff Configuration

Enabled rule sets: ANN, C90, D, E, F, I, N, NPY, PTH, TID, UP, W. Docstrings use D213 convention (D212 ignored). Tests are exempt from docstring rules.
