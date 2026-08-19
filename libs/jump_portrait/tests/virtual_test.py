import sys
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

if sys.version_info < (3, 11):
    pytest.skip("lazy image loading requires Python 3.11+", allow_module_level=True)

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import xarray as xr
from obspec_utils.protocols import ReadableStore

import jump_portrait.fetch as fetch
import jump_portrait.virtual as virtual
from jump_portrait import CHANNELS, UnsupportedTIFFLayoutError, get_jump_image_site


class MemoryStore:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def head(self, path: str) -> dict[str, int]:
        return {"size": len(self.data)}

    def get_range(
        self,
        path: str,
        *,
        start: int,
        length: int,
    ) -> bytes:
        return self.data[start : start + length]


@pytest.fixture
def image_index(tmp_path: Path) -> Path:
    path = tmp_path / "jump_index.parquet"
    row: dict[str, list[str | int]] = {
        "Metadata_Source": ["source_8"],
        "Metadata_Batch": ["J3"],
        "Metadata_Plate": ["A1166127"],
        "Metadata_Well": ["A01"],
        "Metadata_Site": [1],
    }
    row.update(
        {
            f"URL_Orig{channel}": [f"s3://cellpainting-gallery/{channel}.tif"]
            for channel in CHANNELS
        }
    )
    pq.write_table(pa.table(row), path)
    return path


def test_get_index_file_accepts_local_path(image_index: Path) -> None:
    fetch.get_index_file.cache_clear()
    assert fetch.get_index_file(image_index) == image_index


def test_get_index_file_uses_configured_remote_origin(
    image_index: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str | None]] = []

    def fake_retrieve(origin: str, known_hash: str | None) -> Path:
        calls.append((origin, known_hash))
        return image_index

    monkeypatch.setattr(fetch, "retrieve", fake_retrieve)
    fetch.get_index_file.cache_clear()
    origin = "https://example.org/jump_index.parquet"
    assert fetch.get_index_file(origin, "sha256:abc") == image_index
    assert calls == [(origin, "sha256:abc")]


def test_bounded_range_reader_cannot_cover_complete_object() -> None:
    store = cast("ReadableStore", MemoryStore(b"12345678"))
    reader = virtual._BoundedRangeReader(store, "image.tif")

    assert reader.read(7) == b"1234567"
    with pytest.raises(ValueError, match="bounded range budget"):
        reader.read(1)


def test_bounded_range_reader_rejects_unbounded_read() -> None:
    store = cast("ReadableStore", MemoryStore(b"12345678"))
    reader = virtual._BoundedRangeReader(store, "image.tif")

    with pytest.raises(ValueError, match="Unbounded TIFF reads"):
        reader.read()


def test_get_site_urls_returns_notebook_channel_order(image_index: Path) -> None:
    urls = virtual._get_site_urls(
        image_index,
        "source_8",
        "J3",
        "A1166127",
        "A01",
        1,
    )
    assert tuple(urls) == CHANNELS
    assert urls["AGP"] == "s3://cellpainting-gallery/AGP.tif"


def test_get_site_urls_requires_one_matching_row(image_index: Path) -> None:
    with pytest.raises(ValueError, match="found 0"):
        virtual._get_site_urls(
            image_index,
            "source_8",
            "J3",
            "A1166127",
            "A02",
            1,
        )


def test_unsupported_layout_error_names_source_and_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_to_open(*args: object, **kwargs: object) -> None:
        raise NotImplementedError("partial final strip")

    monkeypatch.setattr(virtual, "open_virtual_mfdataset", fail_to_open)
    urls = {channel: f"s3://cellpainting-gallery/{channel}.tif" for channel in CHANNELS}
    with pytest.raises(
        UnsupportedTIFFLayoutError,
        match="source_99.*NotImplementedError: partial final strip",
    ):
        virtual._open_virtual_site("source_99", urls, None)


def test_public_loader_sets_location_and_reference_evidence(
    image_index: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    urls = {channel: f"s3://cellpainting-gallery/{channel}.tif" for channel in CHANNELS}
    lazy_image = xr.DataArray(
        np.zeros((5, 4, 3), dtype=np.uint16),
        dims=("channel", "y", "x"),
        coords={"channel": list(CHANNELS)},
    )
    manifest = SimpleNamespace(manifest=[object(), object()], nbytes_virtual=64)

    monkeypatch.setattr(virtual, "get_index_file", lambda *args: image_index)
    monkeypatch.setattr(virtual, "_get_site_urls", lambda *args: urls)
    monkeypatch.setattr(
        virtual,
        "_open_virtual_site",
        lambda source, channel_urls, trace: (lazy_image, manifest),
    )

    result = get_jump_image_site(
        "source_8",
        "J3",
        "A1166127",
        "A01",
        "1",
        index_origin=image_index,
    )

    assert result.name == "image"
    assert result.dims == ("channel", "y", "x")
    assert result.coords["channel"].values.tolist() == list(CHANNELS)
    assert result.attrs == {
        "source": "source_8",
        "batch": "J3",
        "plate": "A1166127",
        "well": "A01",
        "site": 1,
        "source_urls": urls,
        "image_index_origin": str(image_index),
        "virtual_reference_count": 2,
        "virtual_reference_bytes": 64,
    }
