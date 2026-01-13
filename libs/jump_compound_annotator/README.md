# JUMP DTI Annotations Pipeline

Tools to collect and standardize drug-target interaction (DTI) annotations for JUMP compounds from multiple public databases.

> **Using MOTIVE for ML?** See the [MOTIVE wiki](https://github.com/carpenter-singh-lab/2024_Arevalo_NeurIPS_MotiVE/wiki) for dataset documentation and processed data.
>
> **Want pre-computed annotations?** See the [Zenodo deposit](https://doi.org/10.5281/zenodo.XXXXXXX) for ready-to-use outputs with full schema documentation.

This repository contains the **pipeline code** to regenerate DTI annotations from scratch or extend to other compound sets.

## Prerequisites

- Python 3.8+
- Poetry (Python package manager)
- Storage space for downloads and processed data (size varies based on selected databases)

## Installation

This project uses Poetry for dependency management. If you don't have Poetry installed, install it first:

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

Then install the project and its dependencies:

```bash
# Install dependencies
poetry install

# Activate the virtual environment
poetry shell
```

## Usage

### 1. Create Compound ID Mappings

First, create standardized mappings between different compound ID systems (DrugBank, ChEMBL, PubChem). This is a two-step process:

```bash
# Step 1: Pull compound mappings from UniChem API (may take several hours)
python -m jump_compound_annotator.unichem pull outputs

# Step 2: Combine all mappings into a single reference table
python -m jump_compound_annotator.unichem collate outputs
```

The `pull` command will:
- Download a master list of compound InChIKeys from the JUMP Cell Painting dataset (https://github.com/jump-cellpainting/datasets)
- Query the UniChem API to get corresponding database IDs
- Save results in batches as CSV files in `outputs/ids/` directory
- Save any failed queries in `outputs/errors/` directory

The `collate` command will:
- Read all the batch files from `outputs/ids/`
- Combine them into a single comprehensive mapping table
- Save the result as `outputs/pointers.csv`

The final `pointers.csv` maps each compound's InChIKey to its corresponding IDs in different databases (DrugBank, ChEMBL, PubChem, etc.). This mapping is essential for merging data across different databases in later steps.

Note: The `pull` command may need to be run multiple times due to API timeouts. Each run will create new batch files without overwriting previous progress.

### 2. Get Database Annotations

After creating ID mappings, collect, standardize, and optionally curate drug-target annotations:

```python
from jump_compound_annotator.collate import concat_annotations
from jump_compound_annotator.collate_gene import concat_annotations as concat_gene_annotations
from jump_compound_annotator.collate_compounds import concat_annotations as concat_compound_annotations

# Collect drug-gene annotations
annotations = concat_annotations('./outputs', redownload=False)

# Collect gene-gene interactions
gene_interactions = concat_gene_annotations('./outputs', redownload=False)

# Collect drug-drug interactions
compound_interactions = concat_compound_annotations('./outputs', redownload=False)

# Add standardized InChIKeys to annotations
from jump_compound_annotator.find_inchikeys import add_inchikeys
add_inchikeys('./outputs')
```

### 3. Curate Annotations

Curation standardizes relationship type names, removes ambiguous/generic relationships, and filters out hub compounds (promiscuous binders). See `curate.py` for the mapping and thresholds, and `notebooks/Filtering annotations.ipynb` for the exploratory analysis that motivated these choices.

```python
from pathlib import Path
from jump_compound_annotator.curate import curate_annotations
import pandas as pd
import logging
logging.basicConfig(level=logging.INFO)

# Load annotations
annotations = pd.read_parquet(Path('./outputs') / "annotations.parquet")

# Curate annotations
curated_annotations = curate_annotations(annotations)

# Save curated annotations
curated_annotations.to_parquet('./outputs/filtered_annotations.parquet')
```

### 4. Export External IDs (Optional)

To get plain text files of compound IDs by source:

```bash
python -m jump_compound_annotator.collect_external_ids ./outputs
```

### 5. Prepare Zenodo Deposit (Optional)

To create a structured directory for Zenodo deposit with compressed raw sources:

```bash
python -m jump_compound_annotator.prepare_zenodo ./outputs ./zenodo_deposit
```

To regenerate only the README.md (e.g., after updating the template):

```bash
python -m jump_compound_annotator.prepare_zenodo ./outputs ./zenodo_deposit --readme-only
```

#### Uploading to Zenodo

1. Create a new deposit at https://zenodo.org/deposit/new
2. Fill in metadata (title, description, creators, etc.)
3. Get your deposit ID from the URL (e.g., `zenodo.org/deposit/12345` → ID is `12345`)
4. Get your access token from https://zenodo.org/account/settings/applications/
5. Get the bucket URL:
   ```bash
   curl -s -H "Authorization: Bearer $TOKEN" \
     "https://zenodo.org/api/deposit/depositions/$DEPOSIT_ID" | \
     python3 -c "import sys,json; print(json.load(sys.stdin)['links']['bucket'])"
   ```
6. Upload files:
   ```bash
   # Upload each file to the bucket
   curl -H "Authorization: Bearer $TOKEN" -X PUT \
     -H "Content-Type: application/octet-stream" \
     --data-binary @zenodo_deposit/README.md \
     "$BUCKET_URL/README.md"
   ```
7. Publish the deposit on the Zenodo web interface

## Output Files

The pipeline produces these main outputs in `outputs/`:

| File | Description |
|------|-------------|
| `annotations.parquet` | Raw drug-gene annotations from all databases |
| `filtered_annotations.parquet` | Curated annotations (see `curate.py` for details) |
| `compound_interactions.parquet` | Drug-drug interactions |
| `gene_interactions.parquet` | Gene-gene interactions |
| `pointers.csv` | UniChem ID mappings (InChIKey → DrugBank/ChEMBL/PubChem) |
| `*_mapper.parquet` | InChIKey resolution mappers (UniChem + MyChem) |

Raw database downloads are stored in subdirectories (`biokg/`, `dgidb/`, etc.).

For detailed schemas and column descriptions, see the Zenodo README.

## Data Sources

Annotations are collected from 8 public databases:
BioKG, DGIdb, DrugRep, Hetionet, OpenBioLink, OpenTargets, PharmeBiNet, PrimeKG

## Adding New Databases

Each database module in `src/jump_compound_annotator/` follows a consistent pattern:

1. Create a new module (e.g., `newdb.py`) with a `get_compound_annotations(output_dir, redownload)` function
2. Return a DataFrame with columns: `source`, `target`, `rel_type`, `source_id`
3. Register it in `collate.py`

See existing modules like `dgidb.py` or `hetionet.py` for examples.
