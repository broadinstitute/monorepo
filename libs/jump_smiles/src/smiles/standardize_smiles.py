from collections import Counter
from multiprocessing import Pool
from rdkit import RDLogger
from rdkit.rdBase import BlockLogs
from rdkit.Chem import (
    MolFromSmiles,
    MolToSmiles,
    MolToInchi,
    MolToInchiKey,
    MolFromInchi,
)
from rdkit.Chem.MolStandardize import Standardizer, rdMolStandardize, tautomer
from typing import Union
import fire
import logging
import numpy as np
import pandas as pd
import tqdm
from pathlib import Path

RDLogger.DisableLog("rdApp.*")

# Credits: [Lewis Mervin](https://github.com/lewismervin1) for the orignal source code.


class StandardizeMolecule:
    def __init__(
        self,
        input: Union[str, pd.DataFrame],
        output: str = None,
        num_cpu: int = 1,
        limit_rows: int = None,
        augment: bool = False,
        method: str = "jump_canonical",
        random_seed: int = 42,
    ):
        """
        Initialize the class.

        :param input: Input file name (TSV/TXT/CSV) or a pandas dataframe containing the SMILES
        :param output: Output file name (optional)
        :param num_cpu: Number of CPUs to use (default: 1)
        :param limit_rows: Limit the number of rows to be processed (optional)
        :param augment: The output is the input file augmented with the standardized SMILES, InChI, and InChIKey (default: False)
        :param method: Standardization method to use: "jump_canonical" or "jump_alternate_1" (default: "jump_canonical")

        """
        self.input = input
        self.output = output
        self.num_cpu = num_cpu
        self.limit_rows = limit_rows
        self.augment = augment
        self.method = method
        self.random_seed = random_seed

        # check if method is valid

        if self.method not in ["jump_canonical", "jump_alternate_1"]:
            raise ValueError(
                "Method must be either 'jump_canonical' or 'jump_alternate_1'."
            )

    def _standardize_structure(self, smiles):
        """
        Standardize the given SMILES using MolVS and RDKit.

        :param smiles: Input SMILES from the given structure data file
        :return: dataframe: Pandas dataframe containing the original SMILES, standardized SMILES, InChI, and InChIKey

        """
        standardizer = Standardizer()

        smiles_original = smiles

        # Disable RDKit logging
        block = BlockLogs()  # noqa: F841

        # Set the random seed for reproducibility within each task
        np.random.seed(self.random_seed)

        # Read SMILES and convert it to RDKit mol object
        mol = MolFromSmiles(smiles)

        # Check if the input SMILES has been converted into a mol object
        if mol is None:
            logging.error(f"Reading Error, {smiles}")
            return pd.DataFrame(
                {
                    "SMILES_original": [smiles_original],
                    "SMILES_standardized": [pd.NA],
                    "InChI_standardized": [pd.NA],
                    "InChIKey_standardized": [pd.NA],
                }
            )

        smiles_clean_counter = Counter()
        mol_dict = {}
        is_finalize = False

        if self.method == "jump_canonical":
            for _ in range(5):
                # standardize molecules using MolVS and RDKit
                mol = standardizer.charge_parent(mol)
                mol = standardizer.isotope_parent(mol)
                mol = standardizer.stereo_parent(mol)
                mol = standardizer.tautomer_parent(mol)
                mol = standardizer.standardize(mol)
                mol_standardized = mol

                # convert mol object back to SMILES
                smiles_standardized = MolToSmiles(mol_standardized)

                if smiles == smiles_standardized:
                    is_finalize = True
                    break

                smiles_clean_counter[smiles_standardized] += 1
                if smiles_standardized not in mol_dict:
                    mol_dict[smiles_standardized] = mol_standardized

                smiles = smiles_standardized
                mol = MolFromSmiles(smiles)

            if not is_finalize:
                # If the standardization process is not finalized, we choose the most common SMILES from the counter
                smiles_standardized = smiles_clean_counter.most_common()[0][0]
                # ... and the corresponding mol object
                mol_standardized = mol_dict[smiles_standardized]

        elif self.method == "jump_alternate_1":
            # Note from @srijitseal:
            # This is a simpler way to standardize smiles
            # Tautomers are often difficult to canonicalize, if more runs are allowed, one could find more duplicates.
            # In this case, we found 6 compounds with dual entries.
            # I would recommend running standardization according to the problem in question when using this dataset,
            # protonating at the required pH etc, and evaluating on a case by case basis for the endpoint considered.

            # This solved phosphate oxidation in most cases but introduces a problem for some compounds: eg. geldanamycin where the stable strcutre is returned
            inchi_standardised = MolToInchi(mol)
            mol = MolFromInchi(inchi_standardised)

            # removeHs, disconnect metal atoms, normalize the molecule, reionize the molecule
            mol = rdMolStandardize.Cleanup(mol)

            # if many fragments, get the "parent" (the actual mol we are interested in)
            mol = rdMolStandardize.FragmentParent(mol)

            # try to neutralize molecule
            uncharger = (
                rdMolStandardize.Uncharger()
            )  # annoying, but necessary as no convenience method exists

            mol = uncharger.uncharge(mol)  # standardize molecules using MolVS and RDKit
            mol = standardizer.charge_parent(mol)
            mol = standardizer.isotope_parent(mol)
            mol = standardizer.stereo_parent(mol)

            # Normalize tautomers
            normalizer = tautomer.TautomerCanonicalizer()
            mol = normalizer.canonicalize(mol)

            # Final Rules
            mol = standardizer.standardize(mol)
            mol_standardized = mol

            # convert mol object back to SMILES
            smiles_standardized = MolToSmiles(mol_standardized)

        else:
            raise ValueError(
                "Method must be either 'jump_canonical' or 'jump_alternate_1'"
            )

        # Convert the mol object to InChI
        inchi_standardized = MolToInchi(mol_standardized)

        # Convert the InChI to InChIKey
        inchikey_standardized = MolToInchiKey(mol_standardized)

        # return as a dataframe
        return pd.DataFrame(
            {
                "SMILES_original": [smiles_original],
                "SMILES_standardized": [smiles_standardized],
                "InChI_standardized": [inchi_standardized],
                "InChIKey_standardized": [inchikey_standardized],
            }
        )

    def _run_standardize(self, smiles_list):
        """
        Run the standardization process in parallel using multiprocessing.

        :param smiles_list: List of SMILES to be standardized
        :param num_cpu: Number of CPUs to use

        """

        with Pool(processes=self.num_cpu) as pool:
            standardized_dfs = list(
                tqdm.tqdm(
                    pool.imap(self._standardize_structure, smiles_list),
                    total=len(smiles_list),
                )
            )

        return pd.concat(standardized_dfs, ignore_index=True)

    def _load_input(self):
        """
        Read the input and return a pandas dataframe containing the SMILES.

        :return: dataframe: Pandas dataframe containing the SMILES
        """
        if isinstance(self.input, (str, Path)):
            input_path = Path(self.input)

            # Check the file extension and determine the separator
            if input_path.suffix in [".csv", ".csv.gz"]:
                sep = ","
            elif input_path.suffix in [".tsv", ".txt", ".tsv.gz", ".txt.gz"]:
                sep = "\t"
            else:
                raise ValueError("Input file must be either a CSV or a TSV/TXT file.")

            self.input = pd.read_csv(
                self.input,
                sep=sep,
                comment="!",
                compression="infer",
                low_memory=False,
            )

        elif isinstance(self.input, pd.DataFrame):
            pass
        else:
            raise ValueError("Input must be either a filename or a pandas dataframe.")

        # if there are no rows, raise an error
        if len(self.input) == 0:
            raise ValueError("Input file must contain at least one row.")

        # if both SMILES and smiles are present, raise an error
        if "SMILES" in self.input.columns and "smiles" in self.input.columns:
            raise ValueError("Input file must contain only one column named SMILES.")

        # if the columns SMILES or smiles is not present, raise an error
        if "SMILES" not in self.input.columns and "smiles" not in self.input.columns:
            raise ValueError("Input file must contain a column named SMILES or smiles.")

        # if the column SMILES is not present, rename the column smiles to SMILES
        if "SMILES" not in self.input.columns:
            self.input = self.input.rename(columns={"smiles": "SMILES"})

        # if self.limit_rows is not None, limit the number of rows to self.limit_rows
        if self.limit_rows is not None:
            self.input = self.input.head(self.limit_rows)

        # save the self.input to self.input_original
        self.input_original = self.input.copy()

        # select only the SMILES column
        self.input = self.input[["SMILES"]]

        # drop missing values
        self.input = self.input.dropna()

        # drop duplicates
        self.input = self.input.drop_duplicates()

    def run(self):
        """
        Run the standardization process.
        """
        self._load_input()

        logging.info(f"Number of CPUs: {self.num_cpu}")

        standardized_df = self._run_standardize(self.input["SMILES"])

        # if self.augment is True, merge the original dataframe with the standardized dataframe

        if self.augment:
            # if any of these columns are already present in the original dataframe, drop them
            new_columns = [
                "SMILES_original",
                "SMILES_standardized",
                "InChI_standardized",
                "InChIKey_standardized",
            ]
            self.input_original.drop(columns=new_columns, inplace=True, errors="ignore")

            standardized_df = pd.merge(
                standardized_df,
                self.input_original,
                left_on="SMILES_original",
                right_on="SMILES",
                how="left",
            )

            standardized_df.drop("SMILES", axis=1, inplace=True)

        # if self.output is not None, save the standardized dataframe to a csv file
        if self.output is not None:
            standardized_df.to_csv(self.output, index=False)
            logging.info(f"Standardized data saved to {self.output}")

        return standardized_df


if __name__ == "__main__":
    fire.Fire(StandardizeMolecule)
