# JUMP-SMILES Documentation

JUMP-SMILES is a Python library for standardizing chemical structure representations using RDKit. It provides robust molecular standardization with support for parallel processing and multiple standardization methods.

## Installation

### Prerequisites

- Python 3.11 or newer
- [Poetry](https://python-poetry.org/docs/#installation) package manager

### Dependencies

The project uses Poetry for dependency management with the following core requirements:
- rdkit 2023.9.5
- pandas 2.2.2
- numpy 2.1.1
- fire 0.4.0 or newer
- tqdm 4.64.1
- requests 2.28.2

### Installation Steps

1. Clone the repository:
```bash
git clone <repository-url>
cd libs/jump_smiles
```

2. Install dependencies using Poetry:
```bash
poetry install
```

3. Activate the Poetry virtual environment:
```bash
poetry shell
```

### Development Installation

For development, additional dependencies are included:
- pytest 8.1.1
- jupyter
- ipykernel
- jupytext
- ipdb
- ruff (for linting)

Install with development dependencies:
```bash
poetry install --with dev
```

## Basic Usage

### Command Line Interface

```bash
poetry run python standardize_smiles.py \
  --input molecules.csv \
  --output standardized_molecules.csv \
  --num_cpu 4 \
  --method jump_canonical
```

### Python API

```python
from smiles.standardize_smiles import StandardizeMolecule

# Basic usage with a CSV file
standardizer = StandardizeMolecule(
    input="molecules.csv",
    output="standardized_molecules.csv",
    num_cpu=4
)
standardized_df = standardizer.run()

# Using with a pandas DataFrame
import pandas as pd
df = pd.DataFrame({
    'SMILES': [
        'CC(=O)OC1=CC=CC=C1C(=O)O',  # Aspirin
        'CN1C=NC2=C1C(=O)N(C(=O)N2C)C'  # Caffeine
    ]
})

standardizer = StandardizeMolecule(
    input=df,
    num_cpu=1,
    method="jump_canonical"
)
standardized_df = standardizer.run()
```

## Input Format

The library accepts:
1. CSV/TSV files with a 'SMILES' or 'smiles' column
2. pandas DataFrames with a 'SMILES' or 'smiles' column

## Parameters

- `input`: Input file path (CSV/TSV) or pandas DataFrame
- `output`: Output file path (optional)
- `num_cpu`: Number of CPU cores for parallel processing (default: 1)
- `limit_rows`: Maximum number of rows to process (optional)
- `augment`: Whether to include original columns in output (default: False)
- `method`: Standardization method to use (default: "jump_canonical")
  - "jump_canonical": Iterative standardization with consensus
  - "jump_alternate_1": Simplified standardization with tautomer normalization
- `random_seed`: Random seed for reproducibility (default: 42)

## Standardization Methods

### jump_canonical

This method performs iterative standardization with consensus:
1. Applies multiple standardization steps:
   - Charge parent normalization
   - Isotope removal
   - Stereo parent normalization
   - Tautomer parent normalization
   - General standardization
2. Repeats process up to 5 times until convergence
3. If no convergence, selects most common form

Example:
```python
standardizer = StandardizeMolecule(
    input="molecules.csv",
    method="jump_canonical",
    num_cpu=4
)
results = standardizer.run()
```

### jump_alternate_1

This method offers simplified standardization:
1. InChI-based standardization
2. Structure cleanup
3. Fragment handling
4. Charge neutralization
5. Tautomer canonicalization

Example:
```python
standardizer = StandardizeMolecule(
    input="molecules.csv",
    method="jump_alternate_1",
    num_cpu=4
)
results = standardizer.run()
```

## Output Format

The standardizer returns a pandas DataFrame with the following columns:
- `SMILES_original`: Original input SMILES
- `SMILES_standardized`: Standardized SMILES
- `InChI_standardized`: Standardized InChI
- `InChIKey_standardized`: Standardized InChIKey

When `augment=True`, the output includes all original columns from the input file.

## Advanced Usage Examples

### Processing Large Files with Memory Constraints

```python
standardizer = StandardizeMolecule(
    input="large_molecule_set.csv",
    output="standardized_large_set.csv",
    num_cpu=8,
    limit_rows=10000  # Process in batches
)
results = standardizer.run()
```

### Augmenting Existing Dataset

```python
standardizer = StandardizeMolecule(
    input="compounds_with_properties.csv",
    output="compounds_standardized.csv",
    augment=True,  # Preserve original columns
    method="jump_canonical"
)
results = standardizer.run()
```

### Error Handling

The library handles invalid SMILES gracefully:
```python
df = pd.DataFrame({
    'SMILES': [
        'CC(=O)OC1=CC=CC=C1C(=O)O',  # Valid SMILES
        'INVALID_SMILES',  # Invalid SMILES
        'CN1C=NC2=C1C(=O)N(C(=O)N2C)C'  # Valid SMILES
    ]
})

standardizer = StandardizeMolecule(input=df)
results = standardizer.run()
# Invalid SMILES will have NA values in standardized columns
```

## Best Practices

1. **Method Selection**:
   - Use `jump_canonical` for general-purpose standardization
   - Use `jump_alternate_1` when dealing with tautomer-heavy datasets

2. **Performance Optimization**:
   - Adjust `num_cpu` based on available resources
   - Use `limit_rows` for initial testing
   - Consider processing large files in batches

3. **Quality Control**:
   - Always verify standardization results for critical compounds
   - Check for NA values in output to identify failed standardizations
   - Consider using both methods and comparing results for critical applications

4. **Reproducibility**:
   - Set `random_seed` for reproducible results
   - Document standardization parameters used

## Limitations

1. Cannot process 3D structure information
2. Tautomer standardization may not always find the most chemically relevant form
3. Some complex metal-organic structures may not be handled optimally

## Common Issues and Solutions

1. **Memory Issues with Large Files**
   ```python
   # Process in batches
   for chunk in pd.read_csv("large_file.csv", chunksize=10000):
       standardizer = StandardizeMolecule(
           input=chunk,
           output=f"standardized_chunk_{chunk.index[0]}.csv"
       )
       standardizer.run()
   ```

2. **Handling Special Characters in SMILES**
   ```python
   # Clean SMILES strings before processing
   df['SMILES'] = df['SMILES'].str.strip()
   standardizer = StandardizeMolecule(input=df)
   ```

3. **Validation of Results**
   ```python
   results = standardizer.run()
   
   # Check for failed standardizations
   failed = results[results['SMILES_standardized'].isna()]
   print(f"Failed standardizations: {len(failed)}")
   
   # Verify InChIKey format
   invalid_keys = results[
       ~results['InChIKey_standardized'].str.match('^[A-Z]{14}-[A-Z]{10}-[A-Z]$')
   ]
   print(f"Invalid InChIKeys: {len(invalid_keys)}")
   ```
