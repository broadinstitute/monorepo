#!/usr/bin/env python3
"""
Compound-Target Annotation Analysis and Filtering

This script:
1. Standardizes relationship types
2. Removes hub compounds
3. Analyzes relationship co-occurrences
4. Generates a filtered dataset for downstream use

Usage:
    python filter_annotations.py
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict

from jump_compound_annotator.collate import concat_annotations

# =============================================================================
# Constants & Configuration
# =============================================================================

PROJECT_ROOT = Path(__file__).parent
OUTPUT_DIR = PROJECT_ROOT / "outputs"

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


# =============================================================================
# Helper Functions
# =============================================================================


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


def calculate_cooccurrence(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate co-occurrence matrix for relationship types.
    """
    crosstab = (
        pd.pivot_table(
            df, index="link_id", columns="rel_type", values="inchikey", aggfunc=len
        )
        .fillna(0)
        .astype(int)
    )
    return crosstab.T.dot(crosstab)


def calculate_normalized_cooccurrence(cooc: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate normalized co-occurrence and create edge list.
    """
    n_cooc = cooc / np.diagonal(cooc)
    mask = np.triu(np.ones(n_cooc.shape), k=1).astype(bool)

    m_edges = n_cooc.where(mask)
    m_edges = (
        m_edges.melt(ignore_index=False)
        .sort_values(by="value", ascending=False)
        .dropna()
    )

    m_edges.index.name = "source"
    m_edges.columns = ["target", "weight"]
    return m_edges.query("weight > 0").reset_index()


def main():
    # -------------------------------------------------------------------------
    # Load raw annotations
    # -------------------------------------------------------------------------
    annotations = concat_annotations(str(OUTPUT_DIR), redownload=False)
    print(f"Initial annotations shape: {annotations.shape}")

    # -------------------------------------------------------------------------
    # Clean and standardize
    # -------------------------------------------------------------------------
    annotations = standardize_relationship_types(annotations, RELATIONSHIP_TYPE_MAPPING)

    # Remove excluded relationships
    annotations = annotations.query("not rel_type.isin(@EXCLUDED_RELATIONSHIPS)")

    # Remove duplicates
    annotations = annotations.drop_duplicates(
        ["inchikey", "rel_type", "target"]
    ).reset_index(drop=True)
    print(f"Shape after initial cleaning: {annotations.shape}")

    # -------------------------------------------------------------------------
    # Analyze Relationship Co-occurrences
    # -------------------------------------------------------------------------
    annotations = create_link_ids(annotations)
    cooc = calculate_cooccurrence(annotations)
    m_edges = calculate_normalized_cooccurrence(cooc)
    # Uncomment to inspect or visualize if needed:
    # print(cooc)
    # print(m_edges.head())

    # -------------------------------------------------------------------------
    # Filter Hub Compounds
    # -------------------------------------------------------------------------
    annotations = filter_hub_compounds(annotations, HUB_COMPOUND_THRESHOLD)
    print(f"Shape after hub filtering: {annotations.shape}")

    # -------------------------------------------------------------------------
    # Final Statistics
    # -------------------------------------------------------------------------
    final_stats = {
        "Total Annotations": len(annotations),
        "Unique Targets": annotations["target"].nunique(),
        "Unique Compounds": annotations.inchikey.nunique(),
        "Relationship Types": annotations.rel_type.nunique(),
    }
    print("\nFinal Dataset Statistics:")
    for key, value in final_stats.items():
        print(f"{key}: {value}")

    # -------------------------------------------------------------------------
    # Save Filtered Dataset
    # -------------------------------------------------------------------------
    output_file = OUTPUT_DIR / "filtered_annotations.parquet"
    annotations.to_parquet(output_file, index=False)
    print(f"Saved filtered annotations to: {output_file}")


if __name__ == "__main__":
    main()
