# JUMP DTI annotations

Tools to collect and standardize drug-target interaction (DTI) annotations for JUMP compounds from multiple public databases.

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

After creating ID mappings, collect and standardize drug-target annotations:

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

This creates three main output files in parquet format:
- `annotations.parquet`: Drug-gene relationships
- `compound_interactions.parquet`: Drug-drug interactions  
- `gene_interactions.parquet`: Gene-gene interactions

### 3. Export External IDs (Optional)

To get plain text files of compound IDs by source:

```bash
python -m jump_compound_annotator.collect_external_ids ./outputs
```

## Output Files

### Directory Structure

```
outputs/
├── annotations.parquet           # Main drug-gene annotations
├── compound_interactions.parquet # Drug-drug interactions
├── gene_interactions.parquet    # Gene-gene interactions
├── pointers.csv                # Compound ID mappings from UniChem
├── ids/                        # UniChem mapping batch files
│   └── ids_*.csv
├── errors/                     # Failed UniChem queries
│   └── errors_*.csv
├── external_ids/               # Plain text ID files by source
│   ├── pubchem.txt
│   ├── chembl.txt
│   └── drugbank.txt
├── biokg/                      # BioKG data
│   └── biokg.zip
├── dgidb/                      # DGIdb data
│   ├── drugs.tsv
│   ├── genes.tsv  
│   ├── interactions.tsv
│   └── categories.tsv
├── drugrep/                    # Drug repurposing data
│   ├── drugs.txt
│   └── samples.txt
├── hetionet/                   # Hetionet data
│   └── hetionet.zip
├── hgnc/                       # HGNC gene data
│   └── complete_set.txt
├── ncbi/                       # NCBI gene data
│   └── gene_info.gz
├── openbiolink/               # OpenBioLink data
│   └── HQ_UNDIR.zip
├── opentargets/               # OpenTargets data
│   └── molecule/              # Contains multiple parquet files
├── pharmebinet/               # PharmeBiNet data
│   ├── nodes.parquet
│   ├── edges.parquet
│   └── pharmebinet.tar.gz
└── primekg/                   # PrimeKG data
    └── data.csv
```

### Data Sources
Currently supports annotations from:
- BioKG
- DrugRep 
- DGIdb
- Hetionet
- OpenBioLink
- OpenTargets
- PharmeBiNet
- PrimeKG

## Output File Details

### annotations.parquet
Contains drug-gene relationships with the following columns:
- `source`: Drug ID from original database
- `target`: Standardized gene name
- `rel_type`: Type of relationship
- `source_id`: Original database ID type (drugbank/chembl/pubchem)
- `database`: Source database name
- `inchikey`: Standardized chemical identifier

### compound_interactions.parquet
Contains drug-drug interactions with columns:
- `source_a`: First drug ID
- `source_b`: Second drug ID
- `rel_type`: Interaction type
- `source_id`: Original database ID type
- `database`: Source database name
- `inchikey_a`: First drug's InChIKey
- `inchikey_b`: Second drug's InChIKey

### gene_interactions.parquet
Contains gene-gene interactions with columns:
- `target_a`: First gene name
- `target_b`: Second gene name
- `rel_type`: Interaction type
- `database`: Source database name