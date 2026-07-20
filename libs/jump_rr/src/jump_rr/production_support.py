"""Helpers for the opt-in JUMP production-paper compound tables."""

import json
from functools import cache
from importlib.resources import files
from pathlib import Path

import polars as pl

from jump_rr.datasets import get_profiles_url
from jump_rr.metadata import get_col_desc, table_type_to_suffix

PRODUCTION_DATASET = "compound_no_source7"
_FEATURE_SCHEMA_URL = "https://cellpainting-gallery.s3.amazonaws.com/cpg0042-chandrasekaran-jump/source_all/workspace/profiles_assembled/compound_no_source7/v1.0/profiles_var_mad_int_featselect.parquet"
_ACTIVITY_URL = (
    "https://imaging-platform.s3.amazonaws.com/projects/"
    "cpg0042-chandrasekaran-jump/workspace/publication_data/"
    "2025_Chandrasekaran/jump_production_datastore/processed/copairs/runs/"
    "activity/compound_no_source7__feat_all__activity_no_target2__"
    "all_sources__default/results/activity_map_results.csv"
)
_PROFILE_INDEX_URL = "https://github.com/jump-cellpainting/datasets/blob/main/manifests/profile_index.json"


def build_feature_rename_mapping(
    harmony_features: list[str], cellprofiler_features: list[str]
) -> dict[str, str]:
    """Validate positional alignment and build an ``X_i`` rename mapping."""
    expected = [f"X_{index}" for index in range(1, len(harmony_features) + 1)]
    if harmony_features != expected:
        raise ValueError(
            "Harmony features must be ordered consecutively as X_1..X_N; "
            f"received {harmony_features[:3]}..."
        )
    if len(harmony_features) != len(cellprofiler_features):
        raise ValueError(
            "Harmony and CellProfiler schemas have different feature counts: "
            f"{len(harmony_features)} != {len(cellprofiler_features)}"
        )
    if len(cellprofiler_features) != len(set(cellprofiler_features)):
        raise ValueError("CellProfiler schema contains duplicate feature names")
    return dict(zip(harmony_features, cellprofiler_features, strict=True))


@cache
def get_feature_rename_mapping() -> dict[str, str]:
    """Read the pre-Harmony schema and return its positional rename mapping."""
    original_columns = pl.scan_parquet(_FEATURE_SCHEMA_URL).collect_schema().names()
    cellprofiler_features = [
        column for column in original_columns if not column.startswith("Metadata_")
    ]
    harmony_columns = (
        pl.scan_parquet(get_profiles_url(PRODUCTION_DATASET)).collect_schema().names()
    )
    harmony_features = [
        column for column in harmony_columns if not column.startswith("Metadata_")
    ]
    return build_feature_rename_mapping(harmony_features, cellprofiler_features)


def rename_production_features(profile: pl.DataFrame) -> pl.DataFrame:
    """Restore CellProfiler names on the feature-aligned Harmony profile."""
    mapping = get_feature_rename_mapping()
    profile_features = [
        column for column in profile.columns if not column.startswith("Metadata_")
    ]
    if profile_features != list(mapping):
        raise ValueError(
            "Loaded production profile does not match its registered schema"
        )
    return profile.rename(mapping)


@cache
def _get_production_activity() -> pl.DataFrame:
    """Load activity statistics recalculated from the production profile."""
    return pl.read_csv(
        _ACTIVITY_URL,
        columns=["Metadata_JCP2022", "corrected_p_value", "mean_average_precision"],
    )


def add_production_activity(
    profiles: pl.DataFrame,
    left_on: str,
    columns: dict[str, str],
    right_on: str = "Metadata_JCP2022",
    suffix: str = "",
) -> pl.DataFrame:
    """Join production-profile phenotypic-activity values onto a table."""
    activity = (
        _get_production_activity()
        .rename(columns)
        .with_columns(pl.col(list(columns.values())).round(5))
    )
    return profiles.join(
        activity.select(right_on, *columns.values()),
        how="left",
        left_on=left_on,
        right_on=right_on,
        suffix=suffix,
    )


def write_production_metadata(table_type: str, colnames: list[str]) -> None:
    """Write Datasette metadata for a production-paper compound table."""
    if table_type == "matches":
        prefix = (
            "Explore the most similar production-profile compound perturbations. "
            'Click the "Perturbation-Match Similarity" header to sort the matches.'
        )
    elif table_type == "feature":
        prefix = "Explore statistically significant production-profile features."
    else:
        raise ValueError(f"Unsupported production table type: {table_type!r}")

    source_url = get_profiles_url(PRODUCTION_DATASET)
    description = (
        f"{prefix} This paper-specific table uses the JUMP production "
        f"<code>{PRODUCTION_DATASET}</code> profile and does not replace the "
        "<a href = http://broad.io/compound>standard all-source compound table</a>. "
        f"<a href = {_PROFILE_INDEX_URL}>Data Index</a>. "
        f"<a href = {source_url}>Download source profiles</a>. "
        "<a href = https://broad.io/jump>JUMP Hub</a> for more information."
    )
    data = {
        "databases": {
            "data": {
                "source": "JUMP Consortium",
                "source_url": "http://broad.io/jump",
                "tables": {
                    "content": {
                        "description_html": description,
                        "title": (
                            "JUMP PRODUCTION COMPOUND "
                            f"{table_type_to_suffix(table_type)}"
                        ),
                        "columns": {name: get_col_desc(name) for name in colnames},
                    }
                },
            }
        }
    }
    metadata_path = Path(
        str(
            files("jump_rr")
            / ".."
            / ".."
            / "metadata"
            / f"{PRODUCTION_DATASET}_{table_type}.json"
        )
    )
    with metadata_path.open("w") as metadata_file:
        print(json.dumps(data, indent=4), file=metadata_file)
