import os
import pandas as pd
import tempfile
from src.smiles.standardize_smiles import StandardizeMolecule
import pytest

from pathlib import Path
from rdkit import Chem

test_data_dir = Path(__file__).resolve().parent / "test_data"


@pytest.mark.parametrize(
    "method",
    [
        "jump_canonical",
        "jump_alternate_1",
    ],
)
def test_standardize_molecule(method):
    input_file = str(
        (
            test_data_dir
            / "smiles_data"
            / "JUMP-Target-2_compound_metadata_trimmed_input.tsv"
        ).resolve()
    )

    expected_output_file = str(
        (
            test_data_dir
            / "smiles_data"
            / f"JUMP-Target-2_compound_metadata_trimmed_output_{method}.csv"
        ).resolve()
    )

    tmpdir = tempfile.gettempdir()

    temp_output_file = os.path.join(tmpdir, "test.csv")

    # Create an instance of StandardizeMolecule with the desired parameters
    standardizer = StandardizeMolecule(
        input=input_file,
        output=temp_output_file,
        num_cpu=4,
        augment=True,
        method=method,
        random_seed=42,
    )

    # Run the standardization process
    output_df = standardizer.run()

    # Validate that each standardized SMILES is valid
    for smiles in output_df["SMILES_standardized"]:
        mol = Chem.MolFromSmiles(smiles)
        assert mol is not None, f"Invalid standardized SMILES: {smiles}"

    # Validate that each standardized InChI can be converted back to a molecule
    for inchi in output_df["InChI_standardized"]:
        mol = Chem.MolFromInchi(inchi)
        assert mol is not None, f"Invalid standardized InChI: {inchi}"

    # Validate that each InChIKey is 27 characters and follows the format
    for inchikey in output_df["InChIKey_standardized"]:
        assert len(inchikey) == 27, f"Invalid InChIKey length: {inchikey}"
        assert inchikey.count("-") == 2, f"Invalid InChIKey format: {inchikey}"
        parts = inchikey.split("-")
        assert all(
            len(part) == length for part, length in zip(parts, [14, 10, 1])
        ), f"Incorrect InChIKey sections length: {inchikey}"

    # Read the expected output file
    expected_df = pd.read_csv(expected_output_file)

    # Compare the generated output with the expected output
    pd.testing.assert_frame_equal(output_df, expected_df)

    # Clean up the temporary output file
    if os.path.exists(temp_output_file):
        os.remove(temp_output_file)
