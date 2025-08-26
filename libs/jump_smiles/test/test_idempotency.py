"""
Test idempotency of SMILES standardization using JUMP compounds data.
"""

import pytest
import pandas as pd
from pathlib import Path
from jump_smiles.standardize_smiles import StandardizeMolecule

# Configuration
SMILES_FILE = Path(__file__).parent / "test_data/jump_compounds/smiles_only.csv.gz"
DEFAULT_SAMPLE_SIZE = 100  # Reduced for faster testing, increase for thorough testing
RANDOM_SEED = 42


def load_compounds(sample_size):
    """Load JUMP compound SMILES data with specified sample size."""
    if not SMILES_FILE.exists():
        pytest.skip(
            "SMILES data not found. Run: uv run --script scripts/download_jump_compounds.py"
        )

    df = pd.read_csv(SMILES_FILE, compression="gzip")

    if sample_size == "all":
        return df
    else:
        # Sample for speed (deterministic)
        actual_sample_size = min(sample_size, len(df))
        return df.sample(n=actual_sample_size, random_state=RANDOM_SEED)


@pytest.mark.slow
@pytest.mark.idempotency
@pytest.mark.parametrize(
    "method", ["jump_canonical"]
)  # Can add "jump_alternate_1" later
@pytest.mark.parametrize(
    "sample_size", [100, pytest.param("all", marks=pytest.mark.very_slow)]
)
def test_standardizer_idempotency(method, sample_size):
    """Test that standardization is idempotent.

    Args:
        method: Standardization method to test
        sample_size: Number of compounds to test (100 or "all" for full dataset)
    """
    compound_smiles = load_compounds(sample_size)

    print(f"\nTesting idempotency for {len(compound_smiles)} compounds using {method}")

    # First pass: standardize original SMILES
    input_df = compound_smiles[["Metadata_SMILES"]].rename(
        columns={"Metadata_SMILES": "SMILES"}
    )
    standardizer1 = StandardizeMolecule(
        input=input_df, method=method, random_seed=RANDOM_SEED
    )
    result1 = standardizer1.run()

    # Second pass: standardize the standardized SMILES
    input_df2 = result1[["SMILES_standardized"]].rename(
        columns={"SMILES_standardized": "SMILES"}
    )
    standardizer2 = StandardizeMolecule(
        input=input_df2, method=method, random_seed=RANDOM_SEED
    )
    result2 = standardizer2.run()

    # Merge results with compound IDs for better error reporting
    comparison = pd.DataFrame(
        {
            "compound_id": compound_smiles["Metadata_JCP2022"].values,
            "original": compound_smiles["Metadata_SMILES"].values,
            "pass1_smiles": result1["SMILES_standardized"].values,
            "pass2_smiles": result2["SMILES_standardized"].values,
            "pass1_inchi": result1["InChI_standardized"].values,
            "pass2_inchi": result2["InChI_standardized"].values,
            "pass1_inchikey": result1["InChIKey_standardized"].values,
            "pass2_inchikey": result2["InChIKey_standardized"].values,
        }
    )

    # Check idempotency
    failures = []

    for idx, row in comparison.iterrows():
        # Skip if standardization failed (NaN values)
        if pd.isna(row["pass1_smiles"]) or pd.isna(row["pass2_smiles"]):
            continue

        if row["pass1_smiles"] != row["pass2_smiles"]:
            failures.append(
                f"SMILES mismatch for {row['compound_id']}: {row['original'][:50]}..."
            )
        if row["pass1_inchi"] != row["pass2_inchi"]:
            failures.append(
                f"InChI mismatch for {row['compound_id']}: {row['original'][:50]}..."
            )
        if row["pass1_inchikey"] != row["pass2_inchikey"]:
            failures.append(
                f"InChIKey mismatch for {row['compound_id']}: {row['original'][:50]}..."
            )

    if failures:
        failure_msg = f"\n{len(failures)} idempotency failures found:\n"
        failure_msg += "\n".join(failures[:10])  # Show first 10
        if len(failures) > 10:
            failure_msg += f"\n... and {len(failures) - 10} more"
        pytest.fail(failure_msg)

    # Count successful standardizations
    successful = comparison[comparison["pass1_smiles"].notna()].shape[0]
    print(
        f"✅ {method}: All {successful} successfully standardized compounds passed idempotency test"
    )


@pytest.mark.slow
@pytest.mark.idempotency
def test_data_file_exists():
    """Test that the SMILES data file has been downloaded."""
    assert SMILES_FILE.exists(), (
        f"SMILES data file not found at {SMILES_FILE}\n"
        "Run: uv run --script scripts/download_jump_compounds.py"
    )
