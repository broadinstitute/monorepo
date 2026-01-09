#!/usr/bin/env python3
"""
Prepare jump_compound_annotator outputs for Zenodo deposit.

Creates a structured directory with:
- Renamed annotation files (matching S3 naming convention)
- Mapping files (pointers.csv, UniChem/MyChem mappers)
- Compressed intermediate files (ids, errors, external_ids)
- Compressed raw database sources

Usage:
    python -m jump_compound_annotator.prepare_zenodo outputs zenodo_deposit
"""

import argparse
import shutil
import subprocess
import tarfile
from pathlib import Path

# File renaming mapping (source -> destination)
ANNOTATION_RENAMES = {
    "annotations.parquet": "compound_gene.parquet",
    "gene_interactions.parquet": "gene_gene.parquet",
    "compound_interactions.parquet": "compound_compound.parquet",
    "filtered_annotations.parquet": "compound_gene_curated.parquet",
}

# Mapper files to include
MAPPER_FILES = [
    "pointers.csv",
    "unichem_chembl_mapper.parquet",
    "unichem_drugbank_mapper.parquet",
    "unichem_pubchem_mapper.parquet",
    "mychem_chembl_mapper.parquet",
    "mychem_drugbank_mapper.parquet",
    "mychem_pubchem_mapper.parquet",
]

# Intermediate directories to compress
INTERMEDIATE_DIRS = ["ids", "errors", "external_ids"]

# Raw source directories to compress
RAW_SOURCE_DIRS = [
    "biokg",
    "dgidb",
    "drugrep",
    "hetionet",
    "hgnc",
    "ncbi",
    "openbiolink",
    "opentargets",
    "pharmebinet",
    "primekg",
]

README_TEMPLATE = """# Supplementary Data for MOTIVE: Drug-Target Interaction Annotations

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
{structure}
```

## annotations/

Drug-target interaction annotations collected from 8 databases:
BioKG, DGIdb, DrugRep, Hetionet, OpenBioLink, OpenTargets, PharmeBiNet, PrimeKG

| File | Description | Rows |
|------|-------------|------|
| compound_gene.parquet | Drug-gene annotations | {compound_gene_rows:,} |
| gene_gene.parquet | Gene-gene interactions | {gene_gene_rows:,} |
| compound_compound.parquet | Drug-drug interactions | {compound_compound_rows:,} |
| compound_gene_curated.parquet | Curated drug-gene (standardized rel_types, hub compounds removed) | {curated_rows:,} |

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
"""


def compress_directory(source_dir: Path, output_file: Path) -> None:
    """Compress a directory to tar.gz."""
    print(f"  Compressing {source_dir.name}...")
    with tarfile.open(output_file, "w:gz") as tar:
        tar.add(source_dir, arcname=source_dir.name)


def get_parquet_row_count(filepath: Path) -> int:
    """Get row count from a parquet file using duckdb CLI."""
    try:
        result = subprocess.run(
            ["duckdb", "-csv", "-c", f"SELECT COUNT(*) FROM '{filepath}';"],
            capture_output=True,
            text=True,
            check=True,
        )
        # Output is "count_star()\n<number>\n"
        lines = result.stdout.strip().split("\n")
        return int(lines[1]) if len(lines) > 1 else 0
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return 0


def get_directory_tree(base_path: Path, prefix: str = "") -> str:
    """Generate a simple directory tree string."""
    lines = []
    items = sorted(base_path.iterdir())
    for i, item in enumerate(items):
        is_last = i == len(items) - 1
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{item.name}")
        if item.is_dir():
            extension = "    " if is_last else "│   "
            lines.append(get_directory_tree(item, prefix + extension))
    return "\n".join(lines)


def regenerate_readme(output_path: Path) -> None:
    """Regenerate only the README.md file for an existing Zenodo deposit."""
    from datetime import datetime

    annotations_dir = output_path / "annotations"

    print("Gathering statistics...")
    compound_gene_rows = get_parquet_row_count(annotations_dir / "compound_gene.parquet")
    gene_gene_rows = get_parquet_row_count(annotations_dir / "gene_gene.parquet")
    compound_compound_rows = get_parquet_row_count(
        annotations_dir / "compound_compound.parquet"
    )
    curated_rows = get_parquet_row_count(
        annotations_dir / "compound_gene_curated.parquet"
    )

    structure = get_directory_tree(output_path)

    print("Generating README.md...")
    readme_content = README_TEMPLATE.format(
        date=datetime.now().strftime("%Y-%m-%d"),
        structure=structure,
        compound_gene_rows=compound_gene_rows,
        gene_gene_rows=gene_gene_rows,
        compound_compound_rows=compound_compound_rows,
        curated_rows=curated_rows,
    )
    (output_path / "README.md").write_text(readme_content)
    print(f"Done! README.md regenerated at {output_path / 'README.md'}")


def prepare_zenodo(input_path: Path, output_path: Path, readme_only: bool = False) -> None:
    """Prepare Zenodo deposit structure from jump_compound_annotator outputs."""

    if readme_only:
        if not output_path.exists():
            print(f"Error: Output path {output_path} does not exist. Run without --readme-only first.")
            return
        regenerate_readme(output_path)
        return

    if output_path.exists():
        print(f"Error: Output path {output_path} already exists. Remove it first.")
        return

    print(f"Preparing Zenodo deposit from {input_path} to {output_path}")

    # Create directory structure
    annotations_dir = output_path / "annotations"
    mappings_dir = output_path / "mappings"
    intermediate_dir = output_path / "intermediate"
    raw_sources_dir = output_path / "raw_sources"

    for d in [annotations_dir, mappings_dir, intermediate_dir, raw_sources_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Copy and rename annotation files
    print("\nCopying annotation files...")
    for src_name, dst_name in ANNOTATION_RENAMES.items():
        src_file = input_path / src_name
        if src_file.exists():
            print(f"  {src_name} -> {dst_name}")
            shutil.copy2(src_file, annotations_dir / dst_name)
        else:
            print(f"  {src_name} not found, skipping")

    # Copy mapper files
    print("\nCopying mapping files...")
    for filename in MAPPER_FILES:
        src_file = input_path / filename
        if src_file.exists():
            print(f"  {filename}")
            shutil.copy2(src_file, mappings_dir / filename)
        else:
            print(f"  {filename} not found, skipping")

    # Compress intermediate directories
    print("\nCompressing intermediate directories...")
    for dirname in INTERMEDIATE_DIRS:
        src_dir = input_path / dirname
        if src_dir.exists() and src_dir.is_dir():
            compress_directory(src_dir, intermediate_dir / f"{dirname}.tar.gz")
        else:
            print(f"  {dirname}/ not found, skipping")

    # Compress raw source directories
    print("\nCompressing raw source directories...")
    for dirname in RAW_SOURCE_DIRS:
        src_dir = input_path / dirname
        if src_dir.exists() and src_dir.is_dir():
            compress_directory(src_dir, raw_sources_dir / f"{dirname}.tar.gz")
        else:
            print(f"  {dirname}/ not found, skipping")

    # Get row counts for README
    print("\nGathering statistics...")
    compound_gene_rows = get_parquet_row_count(annotations_dir / "compound_gene.parquet")
    gene_gene_rows = get_parquet_row_count(annotations_dir / "gene_gene.parquet")
    compound_compound_rows = get_parquet_row_count(
        annotations_dir / "compound_compound.parquet"
    )
    curated_rows = get_parquet_row_count(
        annotations_dir / "compound_gene_curated.parquet"
    )

    # Generate directory tree
    structure = get_directory_tree(output_path)

    # Generate README
    print("\nGenerating README.md...")
    from datetime import datetime

    readme_content = README_TEMPLATE.format(
        date=datetime.now().strftime("%Y-%m-%d"),
        structure=structure,
        compound_gene_rows=compound_gene_rows,
        gene_gene_rows=gene_gene_rows,
        compound_compound_rows=compound_compound_rows,
        curated_rows=curated_rows,
    )
    (output_path / "README.md").write_text(readme_content)

    # Calculate total size
    print("\nCalculating sizes...")
    total_size = sum(f.stat().st_size for f in output_path.rglob("*") if f.is_file())
    print(f"\nDone! Total deposit size: {total_size / (1024**2):.1f} MB")
    print(f"Output directory: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Prepare jump_compound_annotator outputs for Zenodo deposit"
    )
    parser.add_argument(
        "input_path",
        type=Path,
        help="Path to jump_compound_annotator outputs directory",
    )
    parser.add_argument(
        "output_path",
        type=Path,
        help="Path for Zenodo deposit directory (will be created)",
    )
    parser.add_argument(
        "--readme-only",
        action="store_true",
        help="Only regenerate the README.md file (output_path must already exist)",
    )
    args = parser.parse_args()

    prepare_zenodo(args.input_path, args.output_path, readme_only=args.readme_only)


if __name__ == "__main__":
    main()
