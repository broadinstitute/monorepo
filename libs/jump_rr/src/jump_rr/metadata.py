"""
Tools to produce labels and explanations for jump_rr web interfaces.
To get columns:
import polars as pl

paths = {
    "simile": "https://zenodo.org/api/records/11188477/files/crispr.parquet/content#/data/content",
    "feature": "https://zenodo.org/api/records/11188477/files/crispr_features.parquet/content#/data/content",
    "gallery": "https://zenodo.org/api/records/11188477/files/orf_gallery.parquet/content#/data/content",
}
columns = sorted(set(col for x in paths.values() for col in pl.scan_parquet(x).columns))
"""

import json
from importlib.resources import files

# %% Fetch dataset columns

_DESCRIPTIONS = {
    "Channel": "Image channel, which shows the stain for DNA, Mito (mitochondria), RNA, AGP (actin, Golgi, plasma membrane) or ER (Endoplasmic Reticulum).",
    "Resources": "External links that provide further information on the gene or chemical perturbation (e.g., NCBI, ChEMBL).",
    "Feature": "Morphological feature obtained from CellProfiler. This value is the result after data normalization. Its units are the number of standard deviations from the median.",
    "Gene/Compound": "Chemical or genetic perturbation. If genetic (overexpression or knock-out) it is the NCBI gene symbol. If it is a chemical perturbation this is the InChiKey.",
    "Gene/Compound example image": " Sample image of the perturbation. It cycles over the available images for every occurrence of the perturbation.",
    "JCP2022 ID": "JUMP internal id. This identifier is unique for any given reagent for a genetic or chemical perturbation across all three datasets (ORF, CRISPR and compounds) and is only repeated for biological replicates.",
    "Cell region": "Mask used to calculate the feature. It can be Nuclei, Cytoplasm or Cells (the union of both Nuclei and Cytoplasm).",
    "Match": " Values with the highest correlation or anti-correlation relative to 'Gene/Compound'.",
    "Match Example": "Sample image of the matched perturbation. It cycles over the available images.",
    "Match JCP2022 ID": "JUMP internal id for the matched perturbation. This identifier is unique for any given perturbation across all three datasets (ORF, CRISPR and compounds) and is only repeated for biological replicates.",
    "Match resources": "Like 'Resources' but for the matched perturbation.",
    "Median": "Median value of the feature for the perturbation when aggregating all replicates.",
    "Gene/Compound example image": "Sample image of the perturbation. It cycles over the available images for every occurrence of the perturbation.",
    "Perturbation-Match Similarity": "Cosine similarity between the normalized morphological profiles of the two perturbations. Negative values indicate the perturbations’ profiles are anti-correlated.",
    "Phenotypic activity": "P-value indicating that the perturbation profile is significantly different from its control. It is corrected using post-FDR Benjamini/Hochberg. ",
    "Feature significance": "P-value indicating that the feature is significantly different from the feature in the controls. It is corrected using post-FDR Benjamini/Hochberg.",
    "Suffix": "Suffix associated with a CellProfiler feature.",
    "Match phenotypic activity": "P-value indicating that the feature is significantly different from the feature in the controls (for the match). It is corrected using post-FDR Benjamini/Hochberg.",
}


def get_col_desc(key: str) -> str:
    """Fetch the description for a given key.

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
    return _DESCRIPTIONS[key]


def write_metadata(dset: str, table_type: str, colnames: [tuple[str]]):
    """Writes metadata file to customize datasette.

    Parameters
    ----------
    dset : str
        dataset (orf, crispr, compound)
    table_type : str
        Data processing type ("simile", "feature", "gallery")
    colnames : [tuple[str]]
        Names of the columns to insert (pass the columns of the
        dataframe in the desired order).

    Examples
    --------
    FIXME: Add docs.

    """
    data = {"databases": {"data": {"tables": {"content": {}}}}}
    with open(
        str(files("jump_rr") / ".." / ".." / "metadata" / f"{dset}_{table_type}.json")
    ) as f:
        data["databases"]["data"]["tables"]["content"]["columns"] = {
            x: get_col_desc(x) for x in colnames
        }
        json.dump(data, f)
