import polars as pl
import pytest

from jump_rr.production_support import (
    add_production_activity,
    build_feature_rename_mapping,
    rename_production_features,
)


def test_build_feature_rename_mapping() -> None:
    mapping = build_feature_rename_mapping(
        ["X_1", "X_2"],
        ["Cells_AreaShape_Area", "Nuclei_Intensity_MeanIntensity_DNA"],
    )

    assert mapping == {
        "X_1": "Cells_AreaShape_Area",
        "X_2": "Nuclei_Intensity_MeanIntensity_DNA",
    }


@pytest.mark.parametrize(
    ("harmony", "cellprofiler"),
    [
        (["X_2", "X_1"], ["Cells_A", "Cells_B"]),
        (["X_1"], ["Cells_A", "Cells_B"]),
        (["X_1", "X_2"], ["Cells_A", "Cells_A"]),
    ],
)
def test_build_feature_rename_mapping_rejects_invalid_schemas(
    harmony: list[str], cellprofiler: list[str]
) -> None:
    with pytest.raises(ValueError):
        build_feature_rename_mapping(harmony, cellprofiler)


def test_rename_production_features(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "jump_rr.production_support.get_feature_rename_mapping",
        lambda: {"X_1": "Cells_A", "X_2": "Nuclei_B"},
    )
    profile = pl.DataFrame(
        {
            "Metadata_JCP2022": ["JCP2022_000001"],
            "X_1": [1.0],
            "X_2": [2.0],
        }
    )

    renamed = rename_production_features(profile)

    assert renamed.columns == ["Metadata_JCP2022", "Cells_A", "Nuclei_B"]


def test_add_production_activity(monkeypatch: pytest.MonkeyPatch) -> None:
    activity = pl.DataFrame(
        {
            "Metadata_JCP2022": ["JCP2022_000001"],
            "corrected_p_value": [0.123456],
            "mean_average_precision": [0.654321],
        }
    )
    monkeypatch.setattr(
        "jump_rr.production_support._get_production_activity", lambda: activity
    )
    profiles = pl.DataFrame({"JCP2022": ["JCP2022_000001"]})

    result = add_production_activity(
        profiles,
        left_on="JCP2022",
        columns={
            "corrected_p_value": "Corrected p-value",
            "mean_average_precision": "Phenotypic activity",
        },
    )

    assert result.to_dicts() == [
        {
            "JCP2022": "JCP2022_000001",
            "Corrected p-value": 0.12346,
            "Phenotypic activity": 0.65432,
        }
    ]
