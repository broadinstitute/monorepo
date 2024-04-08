import os
import pandas as pd
import tempfile
from src.smiles.standardize_smiles import StandardizeMolecule
import pytest

from pathlib import Path

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
        method="jump_alternate_1",
        random_seed=42,
    )

    # Run the standardization process
    standardizer.run()

    # Read the generated output file
    output_df = pd.read_csv(temp_output_file)

    # Read the expected output file
    expected_df = pd.read_csv(expected_output_file)

    # Compare the generated output with the expected output
    pd.testing.assert_frame_equal(output_df, expected_df)

    # Clean up the temporary output file
    os.remove(temp_output_file)
