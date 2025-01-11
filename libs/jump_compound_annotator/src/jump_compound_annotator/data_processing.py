from typing import Dict
import pandas as pd
import numpy as np
from pathlib import Path


class AnnotationProcessor:
    """Process and filter compound-target annotations."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir

    def load_annotations(self) -> pd.DataFrame:
        """Load raw annotations from the output directory."""
        from jump_compound_annotator.collate import concat_annotations

        return concat_annotations(str(self.output_dir), redownload=False)

    @staticmethod
    def create_link_ids(df: pd.DataFrame) -> pd.DataFrame:
        """Create unique identifiers for compound-target pairs."""
        df = df.copy()
        df["link_id"] = df["target"] + "_" + df["inchikey"]
        return df

    @staticmethod
    def standardize_relationship_types(
        df: pd.DataFrame, mapping: Dict[str, str]
    ) -> pd.DataFrame:
        """Standardize relationship type names using provided mapping."""
        df = df.copy()
        df["rel_type"] = df["rel_type"].apply(lambda x: mapping.get(x, x))
        return df

    @staticmethod
    def filter_hub_compounds(
        df: pd.DataFrame, threshold_quantile: float
    ) -> pd.DataFrame:
        """Remove compounds that appear more frequently than the threshold."""
        threshold = df.inchikey.value_counts().quantile(threshold_quantile)
        nohub_cpds = df.inchikey.value_counts()[lambda x: x < threshold].index  # noqa: F841
        return df.query("inchikey.isin(@nohub_cpds)")

    @staticmethod
    def calculate_cooccurrence(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate co-occurrence matrix for relationship types."""
        crosstab = (
            pd.pivot_table(
                df, index="link_id", columns="rel_type", values="inchikey", aggfunc=len
            )
            .fillna(0)
            .astype(int)
        )

        return crosstab.T.dot(crosstab)

    @staticmethod
    def calculate_normalized_cooccurrence(cooc: pd.DataFrame) -> pd.DataFrame:
        """Calculate normalized co-occurrence and create edge list."""
        n_cooc = cooc / np.diagonal(cooc)
        mask = np.triu(np.ones(n_cooc.shape), k=1).astype(np.bool_)

        m_edges = n_cooc.where(mask)
        m_edges = (
            m_edges.melt(ignore_index=False)
            .sort_values(by="value", ascending=False)
            .dropna()
        )

        m_edges.index.name = "source"
        m_edges.columns = ["target", "weight"]
        return m_edges.query("weight > 0").reset_index()
