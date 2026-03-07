# Feature Ranking Table Design

Status: **Done (v1) -- data on S3, enrichments pending (v2)**

## Goal

Create a new table where users can pick a specific morphological feature (e.g., cell area, nuclear intensity) and see all perturbations ranked by their effect size for that feature (top and bottom).

This is the **inverse** of the existing Feature Ranking table:
- Existing: "Which features are significant for perturbation X?"
- New: "Which perturbations have the strongest effect on feature X?"

## Decision: New table needed, using t-statistics

We decided to build a new table rather than reuse the existing one. The approach:

1. **Save t-statistic matrices** from the pipeline (code change done, needs GPU re-run)
2. **Generate the ranking table via pure SQL** (DuckDB) from the t-stat matrix -- no GPU needed
3. **Top 50 compounds per feature**, filtered to p < 0.05, ranked by |t-statistic| descending
4. **Start with compounds**, extend to CRISPR/ORF later

### Why t-statistics instead of p-values

The existing `compound_significance_full.parquet` contains BH-corrected p-values rounded to 5 decimals (`da.around(featstat, 5)` in `calculate_features.py:146`). This creates massive ties: for the compound dataset, 99.9% of the top-50-per-feature rows have p = 0.0. Ranking by p-value is effectively alphabetical sorting by JCP2022 ID -- not meaningful.

The t-statistic captures **direction and magnitude** of the effect without the rounding problem. Larger |t| = stronger effect. The sign indicates direction (positive = treatment > control, negative = treatment < control).

### SQL query to generate the table (from t-stat matrix)

```sql
COPY (
    WITH long AS (
        UNPIVOT '{dset_type}_tstat_full.parquet'
        ON COLUMNS(* EXCLUDE Metadata_JCP2022)
        INTO NAME feature VALUE t_statistic
    ),
    -- Join with significance matrix for p-value filter
    sig_long AS (
        UNPIVOT '{dset_type}_significance_full.parquet'
        ON COLUMNS(* EXCLUDE Metadata_JCP2022)
        INTO NAME feature VALUE p_value
    ),
    combined AS (
        SELECT l.Metadata_JCP2022, l.feature, l.t_statistic, s.p_value
        FROM long l
        JOIN sig_long s
          ON l.Metadata_JCP2022 = s.Metadata_JCP2022
         AND l.feature = s.feature
        WHERE s.p_value < 0.05
    ),
    ranked AS (
        SELECT *,
               row_number() OVER (
                   PARTITION BY feature
                   ORDER BY abs(t_statistic) DESC, Metadata_JCP2022
               ) as perturbation_rank
        FROM combined
    )
    SELECT
        split_part(feature, '_', 1) as Compartment,
        feature as Feature,
        Metadata_JCP2022 as JCP2022,
        round(t_statistic, 3) as "Effect size (t)",
        round(p_value, 5) as "Feature significance",
        perturbation_rank as "Perturbation Rank"
    FROM ranked
    WHERE perturbation_rank <= 50
) TO 'compound_perturbation_ranking.parquet' (FORMAT PARQUET, COMPRESSION ZSTD);
```

### Expected output

| Metric | Value |
|--------|-------|
| Rows | 3,180 features x 50 = 159,000 (max) |
| File size | ~500 KB compressed |
| Columns | Compartment, Feature, JCP2022, Effect size (t), Feature significance, Perturbation Rank |

Later enrichments (v2): perturbation names, sample images, external links, replicability scores.

## Code changes made

### `src/jump_rr/significance.py`

`pvals_from_profile()` now returns `(corrected_p_values, t_statistics)` instead of just `corrected_p_values`. The t-statistics were already computed internally but discarded; they are now returned as a dask array.

### `src/jump_rr/calculate_features.py`

- Unpacks the new tuple return from `pvals_from_profile`
- After saving `{dset_type}_significance_full.parquet`, also saves `{dset_type}_tstat_full.parquet` -- same shape `(n_compounds x n_features)` with `Metadata_JCP2022` column

### `tests/test_t.py`

Updated to unpack the tuple from `pvals_from_profile`. Test verified passing via `uv run pytest tests/test_t.py`.

## Data uploaded

All files on `s3://cellpainting-gallery/cpg0042-chandrasekaran-jump/source_all/workspace/publication_data/`:
- `compound_significance_full.parquet` (1.2G) — also on Zenodo record 15660683
- `compound_tstat_full.parquet` (2.7G) — 115,794 compounds × 3,180 features
- `compound_perturbation_ranking.parquet` (1.6M) — top 50 compounds per feature by |t-statistic|, p < 0.05

## Key Finding: The Existing Table Partially Does This

The existing `compound_interpretable_features.parquet` already contains per-feature rankings via the "Gene Rank" column, but with significant limitations.

### How the existing table is built

**Statistical testing.** The script `calculate_features.py` loads well-level morphological profiles (the `_interpretable` variant, which uses pre-batch-correction features so they retain biological meaning). Each well is labeled as treatment or negative control (`negcon`) using `broad_babel`. Then for every (compound x feature) pair, a plate-matched t-test is performed: each compound's wells are compared to the negative control wells *from the same plates*, producing a p-value matrix of shape `(n_compounds, n_features)`. These p-values are corrected for multiple testing using Benjamini-Hochberg FDR, independently per feature. In parallel, consensus profiles are computed by taking the median of each feature across all replicates of each compound.

**Selection.** The full p-value matrix is too large to serve in a browser (115k compounds x 3,180 features = 368M cells). So `get_ranks()` selects a subset from two directions: (1) for each compound, the 10 features with the lowest p-values -- these get a "Feature Rank" 0-9, and (2) for each feature, the 10 compounds with the lowest p-values -- these get a "Gene Rank" 0-9. The two sets of (compound, feature) index pairs are combined with a UNION and deduplicated, yielding ~1.2M rows. If a cell was selected by only one axis, the other rank shows 999999 (a filled null from NumPy masked arrays).

**Enrichment and output.** Each selected (compound, feature) row is annotated with: the decomposed feature name (Compartment/Feature/Channel/Suffix from regex parsing), the BH-corrected p-value, the consensus median value, a sample well image URL, external resource links (PubChem, ChEMBL, DrugBank), replicability scores (MAP and corrected p-value from precomputed external data), and compound synonyms. The result is written as a zstd-compressed parquet file, alongside a JSON metadata file that configures column descriptions and titles for datasette-lite.

### Naming issue: "Gene Rank" is a misnomer

"Gene Rank" is a name inherited from the CRISPR/ORF context where perturbations are genes. What it actually means is: "the rank of this perturbation among all perturbations, for a given feature, ordered by statistical significance." For the compound dataset, it should be called something like **"Perturbation Rank"** -- it answers "how does this compound rank relative to all other compounds for this specific feature?"

### What the existing table contains (compound dataset, verified from Zenodo record 15660683)

| Metric | Value |
|--------|-------|
| Total rows | 1,189,398 |
| Unique features (Compartment/Feature/Channel/Suffix) | 3,180 |
| Unique compounds (JCP2022) | 115,794 |
| Rows from per-feature axis (Gene Rank 0-9) | 31,800 (exactly 10 per feature) |
| Rows from per-compound axis (Feature Rank 0-9) | 1,157,940 (exactly 10 per compound) |
| Perturbations per feature: min / median / mean / max | 10 / 99 / 374 / 35,897 |

### Why the existing table is not sufficient for the per-feature use case

1. **Only 10 compounds per feature are specifically selected** via Gene Rank. The rest (up to 35,897) appear incidentally from the compound-side selection, making counts per feature wildly variable and unpredictable.
2. **P-value ties**: The top 10 are all p=0 for most features due to 5-decimal rounding, so Gene Rank 1-10 is effectively arbitrary.
3. **The 999999 sentinel value** for Gene Rank / Feature Rank is confusing -- it means "not ranked on this axis" but displays as an integer.
4. **No effect size**: The table has p-values and medians but not t-statistics, so you can't rank by how strongly a compound affects a feature.

### Why a new table instead of fixing the existing one

1. **The ranking metric is fundamentally different.** The existing table ranks by p-value; the new table ranks by t-statistic. Swapping the metric in the existing table would change its meaning for the per-compound axis too, and existing users expect p-values there.
2. **The selection logic is coupled.** The existing table's 1.2M rows come from a UNION of two selection axes (per-compound and per-feature). You can't cleanly separate the per-feature view because rows leak between axes via the UNION, producing wildly variable counts per feature (10 to 35,897). The new table is a clean single-axis selection: exactly 50 per feature.
3. **Different audiences.** The existing table is optimized for "I have a compound, show me what it does" (per-compound workflow). The new table is optimized for "I care about cell area, show me what affects it" (per-feature workflow). Combining both into one table would make neither work well.

## Context

### How jump_rr tables work
1. Python scripts in `src/jump_rr/` generate zstd-compressed parquet files
2. `src/tools/generate_databases.sh` runs 3 scripts sequentially: `galleries.py`, `calculate_matches.py`, `calculate_features.py`
3. `src/tools/upload_parquets.sh` manually uploads parquets to Zenodo (record `12775236`)
4. Tables are served via datasette-lite, which loads parquets from Zenodo URLs in the browser
5. Documentation lives in the [jump_hub repo](https://github.com/broadinstitute/jump_hub)

### Existing tables (per dataset: crispr, orf, compound)
| Table | File | Purpose |
|-------|------|---------|
| Matches | `{dset}.parquet` | Top/bottom-N similar perturbation pairs (cosine similarity) |
| Feature Ranking | `{dset}_features.parquet` | Significant features per perturbation (FDR-corrected t-tests) |
| Gallery | `{dset}_gallery.parquet` | Per-well image browser |
| Full cosine sim | `{dset}_cosinesim_full.parquet` | Complete pairwise similarity matrix |
| Full significance | `{dset_type}_significance_full.parquet` | Complete significance results |
| **Full t-statistics** | **`{dset_type}_tstat_full.parquet`** | **T-statistic matrix (NEW, after pipeline re-run)** |

## Completed so far

- [x] Explored project context (jump_rr codebase + jump_hub docs)
- [x] Fixed pre-existing bug: `duckdb.duckdb.DuckDBPyRelation` -> `duckdb.DuckDBPyRelation` in `significance.py`
- [x] Verified all non-slow tests pass (7 passed, 6 skipped)
- [x] Confirmed core deps work on macOS without GPU
- [x] Verified existing table contents against Zenodo (record 15660683)
- [x] Traced full pipeline: `calculate_features.py` -> `significance.py` -> `index_selection.py`
- [x] Identified Gene Rank misnomer and 999999 sentinel value issues
- [x] Prototyped perturbation ranking table via DuckDB SQL (top 50 per feature, p<0.05)
- [x] Discovered p-value rounding problem (99.9% of top-50 rows are p=0)
- [x] Decided to use t-statistics for ranking instead of p-values
- [x] Modified `pvals_from_profile()` to also return t-statistics
- [x] Added t-stat matrix output to `calculate_features.py`
- [x] Updated test to match new return signature (test passes via `uv run pytest`)
- [x] Uploaded `compound_significance_full.parquet` to S3
- [x] Verified dev env works: `uv sync --group test` installs all deps including GPU packages on Linux server
- [x] Re-run pipeline on GPU server to generate `compound_tstat_full.parquet` (4x H100 NVL, ~11 min)
- [x] Generate final `compound_perturbation_ranking.parquet` from t-stat matrix via SQL (159,000 rows, no ties)
- [x] Upload to S3 (`compound_tstat_full.parquet` + `compound_perturbation_ranking.parquet`)
- [ ] Add enrichments (perturbation names, images, links) -- v2
