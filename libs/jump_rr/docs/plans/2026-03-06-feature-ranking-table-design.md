# Feature Ranking Table Design

Status: **In progress - brainstorming phase**

## Goal

Create a new table where users can pick a specific morphological feature (e.g., cell area, nuclear intensity) and see all perturbations ranked by their consensus value for that feature (top and bottom).

This is the **inverse** of the existing Feature Ranking table:
- Existing: "Which features are significant for perturbation X?"
- New: "Which perturbations have the highest/lowest value for feature X?"

## Context

### How jump_rr tables work
1. Python scripts in `src/jump_rr/` generate zstd-compressed parquet files
2. `src/tools/generate_databases.sh` runs 3 scripts sequentially: `galleries.py`, `calculate_matches.py`, `calculate_features.py`
3. `src/tools/upload_parquets.sh` manually uploads parquets to Zenodo (record `12775236`)
4. Tables are served via datasette-lite, which loads parquets from Zenodo URLs in the browser
5. Documentation lives in the jump_hub repo at `/Users/shsingh/Documents/GitHub/jump/jump_hub/`

### Existing tables (per dataset: crispr, orf, compound)
| Table | File | Purpose |
|-------|------|---------|
| Matches | `{dset}.parquet` | Top/bottom-N similar perturbation pairs (cosine similarity) |
| Feature Ranking | `{dset}_features.parquet` | Significant features per perturbation (FDR-corrected t-tests) |
| Gallery | `{dset}_gallery.parquet` | Per-well image browser |
| Full cosine sim | `{dset}_cosinesim_full.parquet` | Complete pairwise similarity matrix |
| Full significance | `{dset_type}_significance_full.parquet` | Complete significance results |

### Pipeline characteristics
- No CI/CD automation - fully manual process
- Requires CUDA GPU for `calculate_matches.py` and parts of `calculate_features.py`
- The new feature-ranking table should NOT require GPU

### Key data patterns
- Profiles use `Metadata_` prefix convention for metadata columns
- Feature columns are everything without the `Metadata_` prefix
- `_interpretable` dataset variants retain original feature meanings (pre-batch-correction)
- Consensus profiles are computed as per-perturbation medians via `consensus.py`

## Design questions (to resolve on Linux server)

1. **Output format**: Pre-computed datasette-lite parquet (like existing tables) vs. on-demand CLI tool vs. both?
   - Recommendation: datasette-lite parquet fits the existing ecosystem
2. **Which profiles to use**: `_interpretable` variants (features retain original meaning) seem most appropriate since users want to reason about specific features like "cell area"
3. **What to include per row**: perturbation name, feature name, consensus median value, significance, sample image, external links?
4. **Top/bottom N**: How many perturbations to show per feature? All? Top/bottom 30 (like existing feature table)?
5. **Feature grouping**: Use raw CellProfiler feature names or the decomposed (Compartment/Feature/Channel/Suffix) groups from `parse_features.py`?

## Completed so far

- [x] Explored project context (jump_rr codebase + jump_hub docs)
- [x] Fixed pre-existing bug: `duckdb.duckdb.DuckDBPyRelation` -> `duckdb.DuckDBPyRelation` in `significance.py`
- [x] Verified all non-slow tests pass (7 passed, 6 skipped)
- [x] Confirmed core deps work on macOS without GPU
- [ ] Resolve design questions
- [ ] Propose 2-3 approaches with trade-offs
- [ ] Get design approval
- [ ] Implement
