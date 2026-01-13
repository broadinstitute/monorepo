#!/usr/bin/env python3
"""
Compound-Target Annotation Curation

This module curates raw drug-target annotations by standardizing relationship
types and removing noisy data. The curation logic was developed through
exploratory analysis documented in `notebooks/Filtering annotations.ipynb`.

Curation Steps
--------------
1. **Standardize relationship types**: Different databases use different names
   for the same relationship (e.g., "DRUG_BINDING_GENE", "BINDS_CHbG", "CbG"
   all mean "binds"). We map these to canonical names using
   RELATIONSHIP_TYPE_MAPPING.

2. **Exclude ambiguous relationships**: Some relationship types like "DPI"
   (Drug-Protein Interaction) are too generic - they co-occur 100% with more
   specific types and add no information. These are removed via
   EXCLUDED_RELATIONSHIPS.

3. **Deduplicate**: After standardization, remove duplicate
   (inchikey, rel_type, target) tuples that arose from merging databases.

4. **Filter hub compounds**: Some compounds (e.g., ATP, zinc, NAD+) interact
   with thousands of targets and dominate the dataset. We remove compounds
   above the 99.9th percentile in annotation count (HUB_COMPOUND_THRESHOLD).
   This typically removes ~80 compounds but ~290K annotations.

Why These Choices?
------------------
The notebook `notebooks/Filtering annotations.ipynb` contains:
- Co-occurrence analysis showing DPI is redundant with other types
- Distribution analysis showing hub compounds are outliers
- Mapping analysis showing which relationship names are synonymous

See the notebook for visualizations and detailed statistics that motivated
these filtering decisions.
"""

import pandas as pd
from typing import Dict
import logging

logger = logging.getLogger(__name__)

RELATIONSHIP_TYPE_MAPPING = {
    "DOWNREGULATES_CHdG": "downregulates",
    "CdG": "downregulates",
    "UPREGULATES_CHuG": "upregulates",
    "CuG": "upregulates",
    "DRUG_TARGET": "targets",
    "target": "targets",
    "DRUG_CARRIER": "carries",
    "carrier": "carries",
    "DRUG_ENZYME": "enzyme",
    "enzyme": "enzyme",
    "DRUG_TRANSPORTER": "transports",
    "transporter": "transports",
    "BINDS_CHbG": "binds",
    "CbG": "binds",
    "DRUG_BINDING_GENE": "binds",
}

EXCLUDED_RELATIONSHIPS = ["DPI", "DRUG_BINDINH_GENE"]
HUB_COMPOUND_THRESHOLD = 0.999  # 99.9th percentile for filtering hub compounds


def create_link_ids(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create unique identifiers for compound-target pairs.
    """
    df = df.copy()
    df["link_id"] = df["target"] + "_" + df["inchikey"]
    return df


def standardize_relationship_types(
    df: pd.DataFrame, mapping: Dict[str, str]
) -> pd.DataFrame:
    """
    Standardize relationship type names using provided mapping.
    """
    df = df.copy()
    df["rel_type"] = df["rel_type"].apply(lambda x: mapping.get(x, x))
    return df


def filter_hub_compounds(df: pd.DataFrame, threshold_quantile: float) -> pd.DataFrame:
    """
    Remove compounds that appear more frequently than the threshold.
    """
    threshold = df.inchikey.value_counts().quantile(threshold_quantile)
    nohub_cpds = df.inchikey.value_counts()[lambda x: x < threshold].index  # noqa: F841
    return df.query("inchikey.isin(@nohub_cpds)")


def curate_annotations(
    annotations: pd.DataFrame,
    relationship_mapping: Dict[str, str] = RELATIONSHIP_TYPE_MAPPING,
    excluded_relationships: list = EXCLUDED_RELATIONSHIPS,
    hub_threshold: float = HUB_COMPOUND_THRESHOLD,
) -> pd.DataFrame:
    """
    Curate compound-target annotations.

    Applies standardization and filtering to raw annotations. See module
    docstring for detailed explanation of each step.

    Parameters
    ----------
    annotations : pd.DataFrame
        Raw annotations with columns: source, target, rel_type, source_id,
        database, inchikey.
    relationship_mapping : dict, optional
        Mapping from raw relationship names to standardized names.
        Default: RELATIONSHIP_TYPE_MAPPING.
    excluded_relationships : list, optional
        Relationship types to exclude (too generic/ambiguous).
        Default: ["DPI", "DRUG_BINDINH_GENE"].
    hub_threshold : float, optional
        Quantile threshold for hub compound filtering. Compounds with more
        annotations than this percentile are removed. Default: 0.999.

    Returns
    -------
    pd.DataFrame
        Curated annotations with added 'link_id' column (target_inchikey).

    Examples
    --------
    >>> from jump_compound_annotator.curate import curate_annotations
    >>> import pandas as pd
    >>> annotations = pd.read_parquet('outputs/annotations.parquet')
    >>> curated = curate_annotations(annotations)
    >>> curated.to_parquet('outputs/filtered_annotations.parquet')
    """
    initial_rows = len(annotations)
    logger.info(f"Initial number of annotations: {initial_rows}")

    # Clean and standardize
    df = standardize_relationship_types(annotations, relationship_mapping)

    # Remove excluded relationships
    df = df.query("not rel_type.isin(@excluded_relationships)")
    after_exclusion = len(df)
    logger.info(
        f"Rows after removing excluded relationships: {after_exclusion} ({initial_rows - after_exclusion} removed)"
    )

    # Remove duplicates
    df = df.drop_duplicates(["inchikey", "rel_type", "target"]).reset_index(drop=True)
    after_dedup = len(df)
    logger.info(
        f"Rows after removing duplicates: {after_dedup} ({after_exclusion - after_dedup} removed)"
    )

    # Create link IDs and filter hub compounds
    df = create_link_ids(df)
    df = filter_hub_compounds(df, hub_threshold)
    final_rows = len(df)
    logger.info(
        f"Final rows after filtering hub compounds: {final_rows} ({after_dedup - final_rows} removed)"
    )

    return df
