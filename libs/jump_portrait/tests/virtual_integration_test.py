import sys
from pathlib import Path

import pytest

if sys.version_info < (3, 11):
    pytest.skip("lazy image loading requires Python 3.11+", allow_module_level=True)

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from jump_portrait import CHANNELS, RequestTrace, get_jump_image_site
from jump_portrait.fetch import get_jump_image

SOURCE_8_FIELD = ("source_8", "J3", "A1166127", "A01", 1)
SOURCE_8_URLS = {
    "AGP": (
        "s3://cellpainting-gallery/cpg0016-jump/source_8/images/J3/images/"
        "A1166127/Images/HTS_A01_s1_w29D9B15E0-0F42-4A59-A2F8-619BD017D1D1.tif"
    ),
    "DNA": (
        "s3://cellpainting-gallery/cpg0016-jump/source_8/images/J3/images/"
        "A1166127/Images/HTS_A01_s1_w52C47F0FB-BD5E-465A-8A92-9E2ED9E72A12.tif"
    ),
    "ER": (
        "s3://cellpainting-gallery/cpg0016-jump/source_8/images/J3/images/"
        "A1166127/Images/HTS_A01_s1_w4194CE2FF-40C4-45F0-B9D7-AE81D0047EEA.tif"
    ),
    "Mito": (
        "s3://cellpainting-gallery/cpg0016-jump/source_8/images/J3/images/"
        "A1166127/Images/HTS_A01_s1_w1250BC2CE-02B0-48F6-9533-69E9CAC91BF5.tif"
    ),
    "RNA": (
        "s3://cellpainting-gallery/cpg0016-jump/source_8/images/J3/images/"
        "A1166127/Images/HTS_A01_s1_w30A163325-7B23-4E3C-BC17-E995BCF8818D.tif"
    ),
}


@pytest.fixture
def frozen_source_8_index(tmp_path: Path) -> Path:
    index_path = tmp_path / "jump_index.parquet"
    row: dict[str, list[str | int]] = {
        "Metadata_Source": [SOURCE_8_FIELD[0]],
        "Metadata_Batch": [SOURCE_8_FIELD[1]],
        "Metadata_Plate": [SOURCE_8_FIELD[2]],
        "Metadata_Well": [SOURCE_8_FIELD[3]],
        "Metadata_Site": [SOURCE_8_FIELD[4]],
    }
    row.update({f"URL_Orig{channel}": [url] for channel, url in SOURCE_8_URLS.items()})
    pq.write_table(pa.table(row), index_path)
    return index_path


def test_get_jump_image_site_matches_eager_source_8(
    frozen_source_8_index: Path,
) -> None:
    image = get_jump_image_site(
        *SOURCE_8_FIELD,
        index_origin=frozen_source_8_index,
        index_hash=None,
    )

    assert image.dims == ("channel", "y", "x")
    assert image.coords["channel"].values.tolist() == list(CHANNELS)
    assert image.shape == (5, 1024, 1024)
    assert image.dtype == np.dtype("uint16")

    for channel in CHANNELS:
        eager = get_jump_image(
            *SOURCE_8_FIELD[:4],
            channel,
            SOURCE_8_FIELD[4],
            index_origin=frozen_source_8_index,
            index_hash=None,
        )
        np.testing.assert_array_equal(image.sel(channel=channel).values, eager)


def test_get_jump_image_site_crop_uses_ranges_without_local_tiffs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    frozen_source_8_index: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    trace = RequestTrace()
    image = get_jump_image_site(
        *SOURCE_8_FIELD,
        index_origin=frozen_source_8_index,
        index_hash=None,
        trace=trace,
    )

    assert trace.requests
    assert all(request.method != "get" for request in trace.requests)
    trace.clear()

    crop = image.isel(y=slice(0, 8), x=slice(0, 8)).values

    assert crop.shape == (5, 8, 8)
    assert trace.requests
    assert all(
        request.method in {"get_range", "get_ranges"} for request in trace.requests
    )
    assert trace.total_bytes < image.nbytes // 10
    assert not list(tmp_path.rglob("*.tif"))
    assert not list(tmp_path.rglob("*.tiff"))
