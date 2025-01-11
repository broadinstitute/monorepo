#!/usr/bin/env python3
"""
Compound-Target Annotation Analysis and Filtering

1. Standardizes relationship types
2. Removes hub compounds
3. Analyzes relationship co-occurrences
4. Generates a filtered dataset for downstream use
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
    """Curate compound-target annotations by standardizing relationships and filtering hub compounds."""
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
