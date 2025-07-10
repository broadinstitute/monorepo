# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "pandas",
#     "numpy",
#     "copairs",
#     "omegaconf",
#     "hydra-core",
#     "pyarrow",
#     "matplotlib",
#     "seaborn",
#     "polars",
# ]
# ///

"""Generic runner for copairs analyses with configuration support."""

import logging
from typing import Any, Dict, Union
from pathlib import Path

import hydra
from omegaconf import DictConfig, OmegaConf
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

from copairs import map
from copairs.matching import assign_reference_index

logger = logging.getLogger(__name__)


class CopairsRunner:
    """YAML-driven runner for copairs analyses.

    Usage: python copairs_runner.py --config-name=<config_name>

    Key features:
    - Lazy filtering for large parquet files (SQL syntax, before loading)
    - Standard preprocessing pipeline (pandas syntax, after loading)
    - All config parameters passed through to copairs functions
    - Automatic mAP vs -log10(p-value) plotting

    See configs/ directory for examples.
    """

    def __init__(self, config: DictConfig):
        """Initialize runner with Hydra configuration.

        Parameters
        ----------
        config : DictConfig
            Hydra configuration object
        """
        self.config = config
        self._validate_config()

    def _validate_config(self):
        """Validate configuration paths and settings."""
        # Check output configuration
        output_config = self.config.get("output", {})
        if not output_config:
            raise ValueError("output section must be configured")

        if "directory" not in output_config:
            raise ValueError("output.directory must be configured")

        if "name" not in output_config:
            raise ValueError("output.name must be configured")

    def resolve_path(self, path_str: Union[str, Path]) -> Union[str, Path]:
        """Resolve path from config, handling URLs and local paths.

        Parameters
        ----------
        path_str : str or Path
            Path string from configuration

        Returns
        -------
        str or Path
            URL strings are returned as-is, local paths are converted to Path objects
        """
        # Already a Path object
        if isinstance(path_str, Path):
            return path_str

        # URLs and S3 paths stay as strings
        if isinstance(path_str, str) and path_str.startswith(
            ("http://", "https://", "s3://")
        ):
            return path_str

        # Convert local paths to Path objects
        return Path(path_str).expanduser().resolve()

    def load_data(self) -> pd.DataFrame:
        """Load data from configured path.

        Returns
        -------
        pd.DataFrame
            Loaded dataframe
        """
        input_config = self.config["input"]
        path = input_config["path"]
        logger.info(f"Loading data from {path}")

        # Check file extension (works for both Path objects and URL strings)
        path_str = str(path)
        columns = input_config.get("columns")  # Optional column selection

        # Check if lazy filtering is requested for parquet files
        use_lazy = input_config.get("use_lazy_filter", False)
        filter_query = input_config.get("filter_query")

        if path_str.endswith(".parquet") and use_lazy and filter_query:
            # Use polars for lazy filtering
            import polars as pl

            logger.info(f"Using lazy filter: {filter_query}")

            # Lazy load with polars
            lazy_df = pl.scan_parquet(path)

            # Apply filter
            lazy_df = lazy_df.filter(pl.sql_expr(filter_query))

            # Select columns if specified
            if columns:
                lazy_df = lazy_df.select(columns)

            # Collect and convert to pandas
            df = lazy_df.collect().to_pandas()

            # Log column information
            metadata_cols = [col for col in df.columns if col.startswith("Metadata_")]
            feature_cols = [
                col for col in df.columns if not col.startswith("Metadata_")
            ]

            logger.info(
                f"Loaded {len(df)} rows after filtering with {len(df.columns)} columns"
            )
            logger.info(f"  Metadata columns (first 5): {metadata_cols[:5]}")
            logger.info(f"  Feature columns (first 5): {feature_cols[:5]}")

        elif path_str.endswith(".parquet"):
            df = pd.read_parquet(path, columns=columns)
        else:
            df = pd.read_csv(path, usecols=columns)

        if not use_lazy or not filter_query:
            logger.info(f"Loaded {len(df)} rows with {len(df.columns)} columns")

        return df

    def run(self) -> Dict[str, Any]:
        """Run the complete analysis pipeline.

        Returns
        -------
        dict
            Dictionary containing all analysis outputs
        """
        logger.info("Starting copairs analysis")

        # 1. Load and preprocess data
        df = self.load_data()
        df = self.preprocess_data(df)

        # 2. Extract metadata and features
        metadata = df.filter(regex="^Metadata")
        feature_cols = [col for col in df.columns if not col.startswith("Metadata")]
        features = df[feature_cols].values
        logger.info(
            f"Extracted {metadata.shape[1]} metadata columns and {features.shape[1]} features"
        )

        # 3. Run analyses
        ap_results = self.run_average_precision(metadata, features)
        map_results = self.run_mean_average_precision(ap_results)

        # 4. Collect all outputs
        outputs = {
            "ap_scores": ap_results,
            "map_results": map_results,
        }

        # 5. Create plot if mAP results exist
        if "mean_average_precision" in map_results.columns:
            outputs["map_plot"] = self.create_map_plot(map_results)

        # 6. Save everything
        output_config = self.config["output"]
        self.save_results(outputs, output_config["name"])

        logger.info("Analysis complete")
        return outputs

    def run_average_precision(
        self, metadata: pd.DataFrame, features: np.ndarray
    ) -> pd.DataFrame:
        """Run average precision calculation.

        Parameters
        ----------
        metadata : pd.DataFrame
            Metadata dataframe
        features : np.ndarray
            Feature array

        Returns
        -------
        pd.DataFrame
            Average precision results
        """
        ap_config = self.config["average_precision"]
        # Convert OmegaConf to regular dict to avoid ListConfig issues
        params = OmegaConf.to_container(ap_config["params"], resolve=True)

        # Check if multilabel
        if ap_config.get("multilabel", False):
            logger.info("Running multilabel average precision")
            results = map.multilabel.average_precision(metadata, features, **params)
        else:
            logger.info("Running average precision")
            results = map.average_precision(metadata, features, **params)

        return results

    def run_mean_average_precision(self, ap_results: pd.DataFrame) -> pd.DataFrame:
        """Run mean average precision if configured.

        Parameters
        ----------
        ap_results : pd.DataFrame
            Average precision results

        Returns
        -------
        pd.DataFrame
            Mean average precision results with p-values
        """
        if "mean_average_precision" not in self.config:
            return ap_results

        map_config = self.config["mean_average_precision"]
        # Convert OmegaConf to regular dict to avoid ListConfig issues
        params = OmegaConf.to_container(map_config["params"], resolve=True)

        logger.info("Running mean average precision")
        map_results = map.mean_average_precision(ap_results, **params)

        # Add -log10(p-value) column if not present
        if "corrected_p_value" in map_results.columns:
            map_results["-log10(p-value)"] = -map_results["corrected_p_value"].apply(
                np.log10
            )

        return map_results

    def save_results(self, outputs: Dict[str, Any], name: str) -> None:
        """Save all outputs with consistent naming: {name}_{key}.{ext}

        Parameters
        ----------
        outputs : dict
            Dictionary with string keys and DataFrame/Figure values
        name : str
            Base name for all output files
        """
        output_config = self.config["output"]
        output_dir = self.resolve_path(output_config["directory"])
        output_dir.mkdir(parents=True, exist_ok=True)

        for key, value in outputs.items():
            if isinstance(value, pd.DataFrame):
                path = output_dir / f"{name}_{key}.csv"
                value.to_csv(path, index=False)
                logger.info(f"Saved {key} to {path}")

            elif isinstance(value, plt.Figure):
                path = output_dir / f"{name}_{key}.png"
                value.savefig(path, dpi=100, bbox_inches="tight")
                plt.close(value)
                logger.info(f"Saved {key} to {path}")

    def create_map_plot(self, map_results: pd.DataFrame) -> plt.Figure:
        """Create scatter plot of mean average precision vs -log10(p-value).

        Parameters
        ----------
        map_results : pd.DataFrame
            Results from mean_average_precision containing 'mean_average_precision',
            'corrected_p_value', and 'below_corrected_p' columns

        Returns
        -------
        plt.Figure
            The matplotlib figure object
        """
        # Fixed settings for consistency
        sns.set_style("whitegrid", {"axes.grid": False})
        fig, ax = plt.subplots(figsize=(8, 6), dpi=100)

        # Calculate percentage of significant results
        significant_ratio = map_results["below_corrected_p"].mean()

        # Fixed color scheme
        colors = map_results["below_corrected_p"].map(
            {True: "#2166ac", False: "#969696"}
        )

        # Create scatter plot
        ax.scatter(
            data=map_results,
            x="mean_average_precision",
            y="-log10(p-value)",
            c=colors,
            s=40,
            alpha=0.6,
            edgecolors="none",
        )

        # Add significance threshold line
        ax.axhline(
            -np.log10(0.05), color="#d6604d", linestyle="--", linewidth=1.5, alpha=0.8
        )

        # Add annotation (top left)
        ax.text(
            0.02,
            0.98,
            f"Significant: {100 * significant_ratio:.1f}%",
            transform=ax.transAxes,
            va="top",
            ha="left",
            fontsize=11,
            color="#525252",
        )

        # Remove top and right spines
        sns.despine()

        # Set x-axis limits to always show 0-1.05 range
        ax.set_xlim(0, 1.05)

        # Set y-axis limits based on the null size
        map_config = self.config["mean_average_precision"]
        null_size = map_config["params"]["null_size"]
        ymax = -np.log10(1 / (1 + null_size))
        ax.set_ylim(0, ymax)

        # Set labels with fixed formatting
        ax.set_xlabel("mAP", fontsize=12)
        ax.set_ylabel("-log10(p-value)", fontsize=12)
        ax.set_title("Phenotypic Assessment", fontsize=14, pad=20)

        # Customize grid
        ax.grid(True, alpha=0.2, linestyle="-", linewidth=0.5)
        ax.set_axisbelow(True)

        # Adjust layout
        plt.tight_layout()

        return fig

    def preprocess_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply preprocessing steps to data.

        Parameters
        ----------
        df : pd.DataFrame
            Input dataframe

        Returns
        -------
        pd.DataFrame
            Preprocessed dataframe

        Notes
        -----
        Available preprocessing steps (all parameters must be under 'params'):

        - filter: Filter rows using pandas query syntax
        - dropna: Drop rows with NaN values in specified columns
        - remove_nan_features: Remove feature columns containing NaN
        - split_multilabel: Split pipe-separated values into lists
        - add_column: Add boolean column based on query expression
        - filter_active: Filter based on activity CSV with below_corrected_p column
        - aggregate_replicates: Aggregate by taking median of features
        - merge_metadata: Merge external CSV metadata
        - filter_single_replicates: Remove groups with < min_replicates members
        - apply_assign_reference: Apply copairs.matching.assign_reference_index

        Design Note: Preprocessing uses a list-based configuration to maintain explicit
        step ordering and allow multiple steps of the same type. While this makes
        command-line overrides more complex (e.g., preprocessing[0].params.query="new"),
        it aligns with the philosophy of keeping preprocessing minimal - most data
        transformations should happen upstream before reaching this runner.
        ```
        """
        if "preprocessing" not in self.config:
            return df

        for step in self.config["preprocessing"]:
            step_type = step["type"]
            logger.info(f"Applying preprocessing: {step_type}")

            # Get parameters from the params section
            params = step.get("params", {})
            if not params and step_type != "remove_nan_features":
                # remove_nan_features doesn't require params
                raise ValueError(
                    f"Preprocessing step '{step_type}' requires a 'params' section"
                )

            # Convert OmegaConf to regular dict to avoid ListConfig issues
            params = OmegaConf.to_container(params, resolve=True) if params else {}

            # Use getattr to call the appropriate preprocessing method
            method_name = f"_preprocess_{step_type}"
            if hasattr(self, method_name):
                try:
                    df = getattr(self, method_name)(df, params)
                except KeyError as e:
                    raise ValueError(
                        f"Missing required parameter {e} for preprocessing step '{step_type}'"
                    ) from e
            else:
                logger.warning(f"Unknown preprocessing type: {step_type}")

        return df

    def _get_feature_columns(self, df: pd.DataFrame) -> list:
        """Get non-metadata columns."""
        return [col for col in df.columns if not col.startswith("Metadata")]

    def _preprocess_filter(
        self, df: pd.DataFrame, params: Dict[str, Any]
    ) -> pd.DataFrame:
        """Filter rows using pandas query syntax."""
        df = df.query(params["query"])
        logger.info(f"After filter '{params['query']}': {len(df)} rows")
        return df

    def _preprocess_apply_assign_reference(
        self, df: pd.DataFrame, params: Dict[str, Any]
    ) -> pd.DataFrame:
        """Apply copairs.matching.assign_reference_index."""
        return assign_reference_index(df, **params)

    def _preprocess_dropna(
        self, df: pd.DataFrame, params: Dict[str, Any]
    ) -> pd.DataFrame:
        """Drop rows with NaN values."""
        columns = params.get("columns")
        df = df.dropna(subset=columns)
        logger.info(f"After dropna: {len(df)} rows")
        return df

    def _preprocess_remove_nan_features(
        self, df: pd.DataFrame, params: Dict[str, Any]
    ) -> pd.DataFrame:
        """Remove feature columns containing NaN."""
        feature_cols = self._get_feature_columns(df)
        nan_cols = df[feature_cols].isna().any()
        nan_cols = nan_cols[nan_cols].index.tolist()

        if nan_cols:
            df = df.drop(columns=nan_cols)
            logger.info(f"Removed {len(nan_cols)} features with NaN values")
        return df

    def _preprocess_split_multilabel(
        self, df: pd.DataFrame, params: Dict[str, Any]
    ) -> pd.DataFrame:
        """Split pipe-separated values into lists."""
        column = params["column"]
        separator = params.get("separator", "|")
        df[column] = df[column].str.split(separator)
        logger.info(f"Split multilabel column '{column}' by '{separator}'")
        return df

    def _preprocess_add_column(
        self, df: pd.DataFrame, params: Dict[str, Any]
    ) -> pd.DataFrame:
        """Add column based on query expression."""
        query = params["query"]
        column = params["column"]

        # Create boolean mask from query
        mask = df.query(query).index
        df[column] = False
        df.loc[mask, column] = True

        logger.info(f"Added column '{column}' with {len(mask)} True values")
        return df

    def _preprocess_filter_active(
        self, df: pd.DataFrame, params: Dict[str, Any]
    ) -> pd.DataFrame:
        """Filter to active perturbations based on below_corrected_p column."""
        activity_csv = self.resolve_path(params["activity_csv"])
        on_columns = params["on_columns"]
        filter_column = params.get("filter_column", "below_corrected_p")

        # Load activity data
        activity_df = pd.read_csv(activity_csv)

        # Get active perturbations
        active_values = activity_df[activity_df[filter_column]][on_columns].unique()

        df = df[df[on_columns].isin(active_values)]

        logger.info(
            f"Filtered to {len(df)} rows corresponding to {len(active_values)} perturbations from {activity_csv}"
        )

        return df

    def _preprocess_aggregate_replicates(
        self, df: pd.DataFrame, params: Dict[str, Any]
    ) -> pd.DataFrame:
        """Aggregate replicates by taking median of features."""
        groupby_cols = params["groupby"]
        feature_cols = self._get_feature_columns(df)

        df = df.groupby(groupby_cols, as_index=False, observed=True)[
            feature_cols
        ].median()

        logger.info(f"Aggregated to {len(df)} rows by grouping on {groupby_cols}")
        return df

    def _preprocess_merge_metadata(
        self, df: pd.DataFrame, params: Dict[str, Any]
    ) -> pd.DataFrame:
        """Merge external metadata from CSV file."""
        source_path = self.resolve_path(params["source"])
        on_columns = (
            params["on_columns"]
            if isinstance(params["on_columns"], list)
            else [params["on_columns"]]
        )
        how = params.get("how", "left")

        # Load external metadata
        metadata_df = pd.read_csv(source_path)
        logger.info(f"Loaded metadata from {source_path}: {len(metadata_df)} rows")

        original_len = len(df)
        df = df.merge(metadata_df, on=on_columns, how=how)

        logger.info(
            f"Merged metadata on {on_columns} ({how} join): "
            f"{original_len} -> {len(df)} rows"
        )
        return df

    def _preprocess_filter_single_replicates(
        self, df: pd.DataFrame, params: Dict[str, Any]
    ) -> pd.DataFrame:
        """Remove groups with insufficient replicates."""
        groupby_cols = params["groupby"]
        min_replicates = params.get("min_replicates", 2)

        # Count replicates per group
        group_counts = df.groupby(groupby_cols).size()

        # Keep only groups with enough replicates
        valid_groups = group_counts[group_counts >= min_replicates].index

        # Filter to valid groups
        original_len = len(df)
        if len(groupby_cols) == 1:
            df = df[df[groupby_cols[0]].isin(valid_groups)]
        else:
            valid_df = pd.DataFrame(list(valid_groups), columns=groupby_cols)
            df = df.merge(valid_df, on=groupby_cols, how="inner")

        filtered_count = original_len - len(df)
        logger.info(
            f"Filtered {filtered_count} rows with < {min_replicates} replicates, "
            f"kept {len(df)} rows"
        )
        return df


@hydra.main(version_base=None, config_path="configs", config_name=None)
def main(cfg: DictConfig) -> None:
    """Main function for Hydra-based execution."""
    runner = CopairsRunner(cfg)
    results = runner.run()
    logger.info(f"Analysis complete. Generated {len(results)} outputs.")


if __name__ == "__main__":
    main()
