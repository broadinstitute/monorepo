# JUMP-SMILES

Python library for standardizing chemical structures using RDKit. Designed for consistency with [JUMP Cell Painting datasets](https://github.com/jump-cellpainting/datasets).

## Installation

Requires Python 3.11 or 3.12 (RDKit 2023.9.5 constraint).

```bash
# Clone and install
git clone <repository-url>
cd jump-smiles
uv sync --python 3.11

# Or add to your project
uv add jump-smiles
```

## Usage

### Command Line

```bash
# If installed locally
uv run jump-smiles --input molecules.csv --output standardized.csv

# Without installation
uvx --python 3.11 --from jump-smiles jump-smiles --input molecules.csv --output standardized.csv
```

### Python API

```python
from jump_smiles.standardize_smiles import StandardizeMolecule

# File input
standardizer = StandardizeMolecule(
    input="molecules.csv",
    output="standardized.csv",
    num_cpu=4
)
result = standardizer.run()

# DataFrame input
import pandas as pd
df = pd.DataFrame({'SMILES': ['CC(=O)OC1=CC=CC=C1C(=O)O']})
result = StandardizeMolecule(input=df).run()
```

## Parameters

- `input`: CSV/TSV file or DataFrame with SMILES column
- `output`: Output file path (optional)
- `num_cpu`: Number of CPU cores (default: 1)
- `limit_rows`: Maximum rows to process (optional)
- `augment`: Include original columns in output (default: False)
- `method`: Standardization method - "jump_canonical" (default) or "jump_alternate_1"
- `random_seed`: For reproducibility (default: 42)

## Standardization Methods

**jump_canonical** (default): The method used in JUMP Cell Painting datasets. Performs iterative normalization until convergence.

**jump_alternate_1**: Sequential InChI-based standardization, recommended for tautomer-heavy datasets.

See the class docstring for detailed method descriptions.

## Output Format

Returns DataFrame with standardized SMILES, InChI, and InChIKey. Use `augment=True` to include original columns.

## Development

```bash
# Install with dev dependencies
uv sync --python 3.11 --extra dev

# Run tests
uv run pytest

# Lint and format
uv run ruff check src/
uv run ruff format src/
```

## Important Notes

- **RDKit 2023.9.5** is strictly required for reproducibility with JUMP datasets
- Must use Python 3.11 or 3.12 due to RDKit compatibility