# JUMP production paper: jump_rr-compatible compound tables

This directory documents the frozen, paper-consistent JUMP production compound tables. They are a historical supplement for the JUMP production paper, not the living JUMP Hub / jump_rr release.

## Scope

- Profile: `compound_no_source7`
- Modalities: compound only
- Tables: compound matches and CellProfiler feature rankings
- Excluded: `source_7`
- No ORF, CRISPR, gallery, or production-specific `_interpretable` profile
- Feature space: 758 feature-aligned Harmony dimensions, restored positionally to their CellProfiler names using the pre-Harmony parquet schema

The original public `compound` profile and its standard feature workflow remain separate living resources.

## Archived files

| File | Description | Rows | Columns |
|---|---|---:|---:|
| `compound_no_source7.parquet` | Ten most similar and ten most dissimilar compounds per query | 2,252,080 | 13 |
| `compound_no_source7_features.parquet` | Distinctive CellProfiler features by compound and compounds by feature | 1,154,530 | 17 |
| `compound_no_source7_matches.json` | Datasette metadata for the matches table | — | — |
| `compound_no_source7_feature.json` | Datasette metadata for the feature table | — | — |
| `manifest.json` | Machine-readable provenance, dimensions, and checksums | — | — |
| `SHA256SUMS` | SHA256 checksums for the data and metadata files | — | — |

The recalculated activity artifact contains 112,462 of the 112,604 compounds in the profile. Consequently, 142 profile compounds have no activity value (141 after negative controls are excluded from feature ranking).

## Online access

- Permanent archive: [Zenodo record 21515641](https://doi.org/10.5281/zenodo.21515641)
- Interactive matches: [open `compound_no_source7` matches in Datasette Lite](https://lite.datasette.io/?metadata=https://zenodo.org/api/records/21515641/files/compound_no_source7_matches.json/content&install=datasette-json-html&parquet=https://zenodo.org/api/records/21515641/files/compound_no_source7.parquet/content#/data/content)
- Interactive feature rankings: [open `compound_no_source7` features in Datasette Lite](https://lite.datasette.io/?metadata=https://zenodo.org/api/records/21515641/files/compound_no_source7_feature.json/content&install=datasette-json-html&parquet=https://zenodo.org/api/records/21515641/files/compound_no_source7_features.parquet/content#/data/content)
- Direct matches download: <https://zenodo.org/api/records/21515641/files/compound_no_source7.parquet/content>
- Direct feature-ranking download: <https://zenodo.org/api/records/21515641/files/compound_no_source7_features.parquet/content>

## Provenance

- Generator branch: <https://github.com/broadinstitute/monorepo/tree/jump-rr-production-profiles/libs/jump_rr>
- Generator commit: `f95ac3e03e2e700f0bd8719fe18e236c3bbaf891`
- Profile manifest change: <https://github.com/jump-cellpainting/datasets/pull/174>
- Source profile: <https://cellpainting-gallery.s3.amazonaws.com/cpg0042-chandrasekaran-jump/source_all/workspace/profiles_assembled/compound_no_source7/v1.0/profiles_var_mad_int_featselect_harmony.parquet>
- Source profile SHA256: `8e1e5d9e50c8c7c95ed406981b02adb57c7ff9d253192ed52e661115379be6f1`
- Recalculated activity source: <https://imaging-platform.s3.amazonaws.com/projects/cpg0042-chandrasekaran-jump/workspace/publication_data/2025_Chandrasekaran/jump_production_datastore/processed/copairs/runs/activity/compound_no_source7__feat_all__activity_no_target2__all_sources__default/results/activity_map_results.csv>

## Regeneration

From `libs/jump_rr/src/tools` on the generator branch:

```bash
./generate_production_databases.sh
```

The generated parquets are written to `libs/jump_rr/src/tools/databases/` and intentionally remain gitignored.
