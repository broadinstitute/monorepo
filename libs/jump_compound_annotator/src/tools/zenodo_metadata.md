# Supplementary Data for MOTIVE: Drug-Target Interaction Annotations

## Overview

This is supplementary material for *Arevalo, Su et al., NeurIPS 2024,* which presents a drug-target interaction graph dataset combining annotations from 8 public databases with Cell Painting image features.

The processed dataset ("MOTI*VE*") is available on the Cell Painting Gallery S3 bucket.

This Zenodo deposit provides the raw annotation pipeline outputs that were used to create the dataset, including:

* The ID mapping infrastructure (InChIKey resolution via UniChem/MyChem)
* The original database downloads

This supplementary data enables researchers to reproduce the annotation collection process and understand how cross-database ID mapping was performed

The *annotations* files here have slightly different row counts than the [*annotations*](https://cellpainting-gallery.s3.amazonaws.com/index.html#cpg0034-arevalo-su-motive/broad/workspace/publication_data/2024_MOTIVE/inputs/annotations/) on CPG because this is a 2026-01-09 regeneration, and databases may have updated since the original 2024-06 run.

## Directory Structure

```
├── annotations/
├── mappings/
├── intermediate/
└── raw_sources/
```

## annotations/

Drug-target interaction annotations collected from 8 databases:
BioKG, DGIdb, DrugRep, Hetionet, OpenBioLink, OpenTargets, PharmeBiNet, PrimeKG

| File | Description |
|------|-------------|
| compound_gene.parquet | Drug-gene annotations |
| gene_gene.parquet | Gene-gene interactions |
| compound_compound.parquet | Drug-drug interactions |
| compound_gene_curated.parquet | Curated drug-gene (standardized rel_types, hub compounds removed) |

Please see the MOTIVE GitHub repo [wiki](https://github.com/carpenter-singh-lab/2024_Arevalo_NeurIPS_MotiVE/wiki) for additional details.

### Schema: compound_gene.parquet

| Column | Description |
|--------|-------------|
| source | Drug ID (DrugBank/ChEMBL/PubChem format) |
| target | Gene symbol |
| rel_type | Relationship type (e.g., DRUG_TARGET, DRUG_ENZYME) |
| source_id | ID type (drugbank/chembl/pubchem) |
| database | Source database name |
| inchikey | Standardized InChIKey identifier |

### Schema: compound_gene_curated.parquet

Same as compound_gene.parquet, plus:

| Column | Description |
|--------|-------------|
| link_id | Unique identifier (target_inchikey) |

Curation steps applied:
- Standardized relationship types (e.g., "DRUG_TARGET" -> "targets")
- Removed excluded relationships ("DPI", "DRUG_BINDINH_GENE")
- Removed duplicate (inchikey, rel_type, target) combinations
- Filtered hub compounds (top 0.1% most connected)

### Schema: gene_gene.parquet

| Column | Description |
|--------|-------------|
| target_a | First gene symbol |
| target_b | Second gene symbol |
| rel_type | Interaction type |
| database | Source database name |

### Schema: compound_compound.parquet

| Column | Description |
|--------|-------------|
| source_a | First drug ID |
| source_b | Second drug ID |
| rel_type | Interaction type |
| source_id | ID type (drugbank/chembl/pubchem) |
| database | Source database name |
| inchikey_a | First drug's InChIKey |
| inchikey_b | Second drug's InChIKey |

## mappings/

ID mapping files for cross-database linking:

| File | Description |
|------|-------------|
| pointers.csv | UniChem mappings from InChIKey to database IDs (DrugBank, ChEMBL, PubChem, etc.) |
| unichem_*_mapper.parquet | InChIKey resolution via UniChem API |
| mychem_*_mapper.parquet | InChIKey resolution via MyChem API |

These files enable mapping between different compound identifier systems and are essential for reproducing the annotation pipeline.

## intermediate/

Compressed intermediate files from the UniChem API queries:

| File | Description |
|------|-------------|
| ids.tar.gz | Batch results from UniChem API queries |
| errors.tar.gz | Failed lookups (compounds not found in UniChem) |
| external_ids.tar.gz | Exported external IDs by database |

## raw_sources/

Compressed raw downloads from each source database. These can also be re-downloaded from original sources using the jump_compound_annotator pipeline.

| File | Source |
|------|--------|
| biokg.tar.gz | BioKG knowledge graph |
| dgidb.tar.gz | Drug Gene Interaction Database |
| drugrep.tar.gz | Drug Repurposing Hub |
| hetionet.tar.gz | Hetionet integrative network |
| hgnc.tar.gz | HUGO Gene Nomenclature Committee |
| ncbi.tar.gz | NCBI Gene |
| openbiolink.tar.gz | OpenBioLink benchmark |
| opentargets.tar.gz | Open Targets Platform |
| pharmebinet.tar.gz | PharmeBiNet knowledge graph |
| primekg.tar.gz | Precision Medicine Knowledge Graph |

## Code

The annotation pipeline is available at:
https://github.com/broadinstitute/monorepo/tree/main/libs/jump_compound_annotator

Note: Annotation files were renamed for consistency with the S3 dataset:

* annotations.parquet \-\> compound\_gene.parquet
* gene\_interactions.parquet \-\> gene\_gene.parquet
* compound\_interactions.parquet \-\> compound\_compound.parquet
* filtered\_annotations.parquet \-\> compound\_gene\_curated.parquet

## Citation

If you use this data, please cite:

1. **MOTIVE paper:** Arevalo J, Su E, Carpenter AE, Singh S (2024) MOTIVE: A Drug-Target Interaction Graph For Inductive Link Prediction, Proceedings of The Thirty-Eighth Annual Conference on Neural Information Processing Systems, Arxiv. doi: 10.48550/arXiv.2406.08649
https://github.com/carpenter-singh-lab/2024_Arevalo_NeurIPS_MotiVE
2. **Original database sources:** Please also cite the individual databases as described in the MOTIVE paper.

## License

The annotations are derived from multiple public databases. Please refer to the original database licenses when using this data. See the MOTIVE paper for details on data sources and their terms of use.
