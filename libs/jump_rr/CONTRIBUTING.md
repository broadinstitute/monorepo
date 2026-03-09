# Contributing to jump_rr

This guide covers everything you need to get productive in the codebase: setup, architecture, conventions, and known pitfalls.

## Project Overview

`jump_rr` produces browsable databases of morphological profile similarities from the [JUMP Cell Painting](https://jump-cellpainting.broadinstitute.org/) consortium. It computes pairwise cosine similarities, feature significance (t-tests with FDR correction), and image galleries, outputting parquet files served via [datasette-lite](https://github.com/simonw/datasette-lite).

## Getting Started

```bash
# Install (dev) — requires Linux with CUDA GPU (see "Testing on macOS" below for local dev)
uv sync --all-extras --group test

# Run tests (fast only)
pytest tests/

# Run tests including slow (network-dependent downloads)
pytest tests/ --runslow

# Run a single test
uv run pytest tests/test_t.py::test_pvalue

# Lint and format
ruff check src/
ruff format src/
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

### Data Conventions

- **Metadata columns** are prefixed with `Metadata_` (e.g., `Metadata_JCP2022`, `Metadata_Plate`)
- **Feature columns** are everything without the `Metadata_` prefix
- Three dataset types: `crispr`, `orf`, `compound` (plus `*_interpretable` variants for feature analysis)
- JCP2022 IDs uniquely identify reagents; the 9th character distinguishes dataset type (`8`=CRISPR, `9`=ORF, `0`=compound)

## Code Style & Conventions

- **Format before pushing**: always run `ruff format src/` using the pyproject.toml config
- **Prefer DuckDB over Polars for data joins/grouping** — the project is deliberately moving toward DuckDB for memory spill benefits. Fix bugs within the existing technology; don't swap to Polars.
- **Split chained expressions when debugging matters** — assign intermediate results to variables so breakpoints can inspect them, especially for multi-step data transformations

## Known Pitfalls

- **Dask `.compute()` re-executes the full graph** — compute once into numpy, then derive variants (rounding, abs) from the materialized result
- **Pooch hashes go stale** — upstream files (OMIM, NCBI) update periodically; fix by downloading the new file and updating the SHA256 in `mappers.py`
- **`significance.py` DuckDB variables (`plates_trt`, `merged`) trigger F841 lint warnings** — these are false positives; DuckDB SQL references them implicitly

## Data Exploration & Deployment

- **DuckDB CLI**: Available for SQL-based parquet exploration (e.g., `duckdb -c "SELECT ... FROM 'databases/file.parquet'"`)
- **S3 uploads (for quick testing only)**: Parquets can be uploaded to S3 for testing with datasette-lite, but the production S3 bucket requires authorized access. Coordinate with the team before uploading.
- **Zenodo record**: Published parquets are on Zenodo record `12775236` (upload script) / `15660683` (latest data)
- **Local parquets**: Generated files go to `./databases/` (gitignored)

### Datasette-lite URLs

- Use `?parquet=` (not `?url=`, which expects SQLite and errors with "file is not a database")
- Add `&install=datasette-json-html` for images/links to render
- Datasette-lite derives the table name from the URL: Zenodo's `/files/foo.parquet/content` endpoint produces a table called `content`, while S3 uses the filename (e.g., `orf_interpretable_features`). The `"tables"` key in the metadata JSON must match this derived name, otherwise column descriptions and titles silently won't apply.
- Metadata JSON must be served from a URL accessible to the browser (e.g., raw GitHub link)
