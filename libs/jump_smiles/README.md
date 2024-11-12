# JUMP-SMILES Documentation

A Python library for standardizing chemical structures using RDKit. Designed to standardize SMILES strings for consistency with the [JUMP Cell Painting datasets](https://github.com/jump-cellpainting/datasets).

## Installation

Requires Python 3.11+ and Poetry package manager.

```bash
git clone <repository-url>
cd jump-smiles
poetry install
poetry shell
```

Core dependencies (managed by Poetry):
- rdkit 2023.9.5
- pandas 2.2.2
- numpy 2.1.1
- fire 0.4.0+
- tqdm 4.64.1
- requests 2.28.2

## Usage

### Command Line
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

# With file input
standardizer = StandardizeMolecule(
    input="molecules.csv",
    output="standardized_molecules.csv",
    num_cpu=4
)
standardized_df = standardizer.run()

# With DataFrame input
import pandas as pd
df = pd.DataFrame({
    'SMILES': [
        'CC(=O)OC1=CC=CC=C1C(=O)O',  # Aspirin
        'CN1C=NC2=C1C(=O)N(C(=O)N2C)C'  # Caffeine
    ]
})
standardized_df = StandardizeMolecule(input=df).run()
```

## Parameters

- `input`: CSV/TSV file path or pandas DataFrame with 'SMILES'/'smiles' column
- `output`: Output file path (optional)
- `num_cpu`: Number of CPU cores (default: 1)
- `limit_rows`: Maximum rows to process (optional)
- `augment`: Include original columns in output (default: False)
- `method`: Standardization method (default: "jump_canonical")
- `random_seed`: For reproducibility (default: 42)

## Standardization Methods

### jump_canonical
The default method used in JUMP Cell Painting datasets. Performs iterative steps until convergence (max 5 iterations):
- Charge parent normalization
- Isotope removal
- Stereo parent normalization
- Tautomer parent normalization
- General standardization

If no convergence, selects most common form.

### jump_alternate_1
Recommended for tautomer-heavy datasets. Performs sequential steps:
1. InChI-based standardization
2. Structure cleanup
3. Fragment handling
4. Charge neutralization
5. Tautomer canonicalization

## Output Format
Returns DataFrame with columns:
- `SMILES_original`: Input SMILES
- `SMILES_standardized`: Standardized SMILES
- `InChI_standardized`: Standardized InChI
- `InChIKey_standardized`: Standardized InChIKey

If `augment=True`, includes all original columns.

## Limitations
1. No 3D structure processing
2. May not find most chemically relevant tautomer
3. Limited handling of complex metal-organic structures
