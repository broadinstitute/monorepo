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

### Pipeline mechanics (entirely manual, no automation)

**Step 1: Generate** — Run `generate_databases.sh` from `src/tools/` on a CUDA GPU server. It calls three Python scripts sequentially. Output parquets land in a local `./databases/` directory.

**Step 2: Upload** — Run `upload_parquets.sh <directory>` with a `ZENODO_TOKEN` env variable. This script:
1. Finds the latest version of Zenodo record `12775236`
2. Creates a new version via the Zenodo API
3. Uploads all `.parquet` files from the given directory
4. Attaches metadata from `metadata/jump_rr.json`
5. The publish step (line 63) is **commented out** — must uncomment or publish manually on Zenodo's web UI

**What's missing from the pipeline:**
- No CI/CD (no GitHub Actions, no Makefile)
- No shebang or comments in `generate_databases.sh`
- No versioning strategy linking profile versions to output parquets
- The `db_mapper/` sub-pipeline (compound->PubChem->ChEMBL mapping) is documented only in an Org-mode literate file and has its own Zenodo record (`15644588`)

**Implications for new tables:** Adding a new table type means modifying `generate_databases.sh` and the upload script, then manually re-running on a GPU server. The new feature-ranking table itself should NOT require GPU.

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
