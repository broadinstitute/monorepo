"""
Tools to produce labels and explanations for jump_rr web interfaces.

To get columns:
import polars as pl.

paths = {
    "simile": "https://zenodo.org/api/records/14751826/files/crispr.parquet/content#/data/content",
    "feature": "https://zenodo.org/api/records/14751826/files/crispr_features.parquet/content#/data/content",
    "gallery": "https://zenodo.org/api/records/14751826/files/orf_gallery.parquet/content#/data/content",
}
columns = sorted(set(col for x in paths.values() for col in pl.scan_parquet(x).columns))
"""

import json
from importlib.resources import files
from typing import Optional

# %% Fetch dataset columns

_DESCRIPTIONS = {
    "Channel": "Image channel, which shows the stain for DNA, Mito (mitochondria), RNA, AGP (actin, Golgi, plasma membrane) or ER (Endoplasmic Reticulum).",
    "Resources": "External links that provide further information on the gene or chemical perturbation (e.g., NCBI, ChEMBL).",
    "Feature": "Morphological feature obtained from CellProfiler. This value is the result after data normalization. Its units are the number of median absolute deviations (MAD) from the median.",
    "Gene/Compound": "Chemical or genetic perturbation. If genetic (overexpression or knock-out) it is the NCBI gene symbol. If it is a chemical perturbation this is the InChiKey. ",
    "Gene/Compound example image": "Sample image of the perturbation. It cycles over the available images for every occurrence of the perturbation.",
    "JCP2022 ID": "JUMP internal id. This identifier is unique for any given reagent for a genetic or chemical perturbation across all three datasets (ORF, CRISPR and compounds) and is only repeated for biological replicates.",
    "Compartment": "Mask used to calculate the feature. It can be Nuclei, Cytoplasm or Cells (the union of both Nuclei and Cytoplasm).",
    "Match": "Perturbations with the highest correlation or anti-correlation relative to 'Gene/Compound'.",
    "Match Example": "Sample image of the matched perturbation. It cycles over the available images.",
    "Match JCP2022 ID": "JUMP internal id for the matched perturbation. This identifier is unique for any given perturbation across all three datasets (ORF, CRISPR and compounds) and is only repeated for biological replicates.",
    "Match resources": "External links that provide further information on the matched perturbation (e.g., NCBI, ChEMBL).",
    "Median": "Median value of the feature for the perturbation when aggregating all replicates.",
    "Match example image": "Sample image of the perturbation’s match. It cycles over the available images for every occurrence of the perturbation.",
    "Perturbation-Match Similarity": "Cosine similarity between the normalized morphological profiles of the two perturbations. Negative values indicate the perturbations’ profiles are anti-correlated. Ranges from -1 to 1.",
    "Suffix": "Suffix associated with a CellProfiler feature.",
    "Phenotypic activity": "Mean average precision of the matched perturbation. It determines how different a perturbation is relative to the negative control. An empty value indicates that the value was discarded due to low infection efficiency.",
    "Feature significance": "Adjusted p-value (*) indicating the statistical significance of the difference between a specific morphological feature in the perturbed condition compared to the control condition. Lower values suggest a stronger effect of the perturbation on that particular feature.",
    "Phenotypic activity Match": "Phenotypic activity of the matched perturbation.",
    "Corrected p-value": "Statistical significance of how distinctive a perturbation is relative to the negative control. It is negatively correlated to mean average precision, but adjusted based on its composition of positive and negative values.",
    "Corrected p-value Match": "Corrected p-value of the matched perturbation.",
    "Synonyms": "Other names of the perturbation. If it is a number it indicates that the gene name was not found.",
    "Feature Rank": "The rank of feature significance when compared to all the features for a given perturbation.",
    "Gene Rank": "The rank of the feature for a given gene when compared to that feature in all other genes.",
    "Match differential activity": "P-value indicating the statistical significance of the difference between the perturbation's morphological profile and its closest match's profile. Lower values suggest stronger dissimilarity between the perturbation and its best match.",  # <2024-07-17 Wed> This is currently unused
    "Source": "Identifier of the partner that produced the data numbered between 1 and 15.",
    "Plate": "Identifier of the plate.",
    "Well": "Identifier of the well. Generally 384-well plates, ranging from A01 to P24.",
    "Site X": "Identifier of the Field of View (FoV). Ranging from 0 to 9 (depending on the dataset).",
    "(*)": "Benjamini-Hochberg FDR correction",
}


def get_col_desc(key: str) -> str:
    """
    Fetch the description for a given key.

    Parameters
    ----------
    key : str
        column key from which to fetch a brief description.

    Returns
    -------
    str
        Description of input key that should make it clearer for the
        user of jump_rr web interfaces what the column values mean.

    Examples
    --------
    FIXME: Add docs.

    """
    return _DESCRIPTIONS.get(key)


def write_metadata(dset: str, table_type: str, colnames: tuple[str]) -> None:
    """
    Write metadata file to customize Datasette.

    Parameters
    ----------
    dset : str
        dataset (orf, crispr, compound)
    table_type : str
        Data processing type ("simile", "feature", "gallery")
    colnames : [tuple[str]]
        Names of the columns to insert (pass the columns of the
        dataframe in the desired order).

    """
    prefix = ""
    if table_type == "matches":
        prefix = "Only top 50 matches for each perturbation are shown. "

    if table_type != "gallery":  # Add statistical method for non-galleries
        valid_names = (*colnames, ("(*)"))
    else:  # Reduce "Site X' redundancy for galleries
        valid_names = (*[x for x in colnames if not x.startswith("Site")], "Site X")

    data = {
        "databases": {
            "data": {
                "source": "JUMP Consortium",
                "source_url": "http://broad.io/jump",
                "tables": {
                    "content": {
                        "description_html": f"{prefix}<a href = https://github.com/jump-cellpainting/datasets/blob/main/manifests/profile_index.csv> Data sources.</a> The latest version can be found <a href = http://broad.io/{dset if table_type=='matches' else '_'.join((dset,table_type))}>here</a>.",
                        "title": f"{dset.upper()} {table_type_to_suffix(table_type)}",
                    }
                },
            }
        }
    }

    with open(
        str(files("jump_rr") / ".." / ".." / "metadata" / f"{dset}_{table_type}.json"),
        "w",
    ) as f:
        data["databases"]["data"]["tables"]["content"]["columns"] = {
            x: get_col_desc(x) for x in valid_names
        }

        json.dump(data, f, indent=4)


def table_type_to_suffix(table_type: str) -> Optional[str]:
    """
    Convert a table type to a title suffix.

    This function takes a string representing the type of table and returns the corresponding title suffix.

    Parameters
    ----------
    table_type : str
        The type of table, e.g., "matches" or "feature".

    Returns
    -------
    str
        The title suffix for the given table type.

    """
    match table_type:
        case "matches":
            return "Matches"
        case "feature":
            return "Feature Ranking"
        case "gallery":
            return "Gallery"
