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

import jump_portrait._index as index
import jump_portrait.fetch as fetch
import jump_portrait.virtual as virtual
from jump_portrait import (
    CHANNELS,
    UnsupportedTIFFLayoutError,
    get_jump_image_site,
    get_jump_image_site_from_metadata,
)


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

    monkeypatch.setattr(index, "retrieve", fake_retrieve)
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


def test_contiguous_strips_are_coalesced_to_128_rows() -> None:
    offsets = np.arange(256, dtype=np.uint64) * 8192
    lengths = np.full(256, 8192, dtype=np.uint64)

    result_offsets, result_lengths, chunk_rows = virtual._coalesce_strips(
        offsets,
        lengths,
        4,
    )

    np.testing.assert_array_equal(result_offsets, offsets[::32])
    np.testing.assert_array_equal(result_lengths, np.full(8, 262144))
    assert chunk_rows == 128


def test_noncontiguous_strips_are_not_coalesced() -> None:
    offsets = np.array([0, 8, 17, 25], dtype=np.uint64)
    lengths = np.full(4, 8, dtype=np.uint64)

    result_offsets, result_lengths, chunk_rows = virtual._coalesce_strips(
        offsets,
        lengths,
        4,
    )

    np.testing.assert_array_equal(result_offsets, offsets)
    np.testing.assert_array_equal(result_lengths, lengths)
    assert chunk_rows == 4


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

    monkeypatch.setattr(
        virtual,
        "get_index_file",
        lambda *args: pytest.fail("default site lookup fell back to Pooch"),
    )
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


def test_public_loader_range_scans_remote_index_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin = "https://example.org/jump_index.parquet"
    urls = {channel: f"s3://cellpainting-gallery/{channel}.tif" for channel in CHANNELS}
    lazy_image = xr.DataArray(
        np.zeros((5, 4, 3), dtype=np.uint16),
        dims=("channel", "y", "x"),
        coords={"channel": list(CHANNELS)},
    )
    manifest = SimpleNamespace(manifest=[], nbytes_virtual=0)
    scan_origins: list[str | Path] = []

    monkeypatch.setattr(
        virtual,
        "get_index_file",
        lambda *args: pytest.fail("default site lookup fell back to Pooch"),
    )

    def fake_get_site_urls(index_origin: str | Path, *args: object) -> dict[str, str]:
        scan_origins.append(index_origin)
        return urls

    monkeypatch.setattr(virtual, "_get_site_urls", fake_get_site_urls)
    monkeypatch.setattr(
        virtual,
        "_open_virtual_site",
        lambda source, channel_urls, trace: (lazy_image, manifest),
    )

    get_jump_image_site("source_8", "J3", "A1166127", "A01", index_origin=origin)

    assert scan_origins == [origin]


def test_metadata_loader_uses_returned_urls_without_index_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    urls = {channel: f"s3://cellpainting-gallery/{channel}.tif" for channel in CHANNELS}
    record: dict[str, object] = {
        "Metadata_Source": "source_8",
        "Metadata_Batch": "J3",
        "Metadata_Plate": "A1166127",
        "Metadata_Well": "A01",
        "Metadata_Site": 1,
    }
    record.update({f"URL_Orig{channel}": url for channel, url in urls.items()})
    lazy_image = xr.DataArray(
        np.zeros((5, 4, 3), dtype=np.uint16),
        dims=("channel", "y", "x"),
        coords={"channel": list(CHANNELS)},
    )
    manifest = SimpleNamespace(manifest=[object()], nbytes_virtual=32)
    opened: list[tuple[str, dict[str, str]]] = []

    monkeypatch.setattr(
        virtual,
        "_get_site_urls",
        lambda *args: pytest.fail("metadata loader rescanned the image index"),
    )

    def fake_open(
        source: str,
        channel_urls: dict[str, str],
        trace: object,
    ) -> tuple[xr.DataArray, object]:
        opened.append((source, channel_urls))
        return lazy_image, manifest

    monkeypatch.setattr(virtual, "_open_virtual_site", fake_open)

    result = get_jump_image_site_from_metadata(record)

    assert opened == [("source_8", urls)]
    assert result.attrs == {
        "source": "source_8",
        "batch": "J3",
        "plate": "A1166127",
        "well": "A01",
        "site": 1,
        "source_urls": urls,
        "image_index_origin": None,
        "virtual_reference_count": 1,
        "virtual_reference_bytes": 32,
    }


def test_metadata_loader_rejects_missing_public_channel_url() -> None:
    with pytest.raises(ValueError, match="Gallery URL.*RNA"):
        get_jump_image_site_from_metadata(
            {
                "Metadata_Source": "source_8",
                "Metadata_Batch": "J3",
                "Metadata_Plate": "A1166127",
                "Metadata_Well": "A01",
                "Metadata_Site": 1,
                **{
                    f"URL_Orig{channel}": f"s3://cellpainting-gallery/{channel}.tif"
                    for channel in CHANNELS[:-1]
                },
            }
        )


def test_public_loader_explicit_hash_downloads_complete_index(
    image_index: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin = "https://example.org/jump_index.parquet"
    index_hash = "sha256:abc"
    urls = {channel: f"s3://cellpainting-gallery/{channel}.tif" for channel in CHANNELS}
    lazy_image = xr.DataArray(
        np.zeros((5, 4, 3), dtype=np.uint16),
        dims=("channel", "y", "x"),
        coords={"channel": list(CHANNELS)},
    )
    manifest = SimpleNamespace(manifest=[], nbytes_virtual=0)
    downloads: list[tuple[str | Path, str | None]] = []
    scan_origins: list[str | Path] = []

    def fake_get_index_file(
        index_origin: str | Path,
        known_hash: str | None,
    ) -> Path:
        downloads.append((index_origin, known_hash))
        return image_index

    def fake_get_site_urls(index_origin: str | Path, *args: object) -> dict[str, str]:
        scan_origins.append(index_origin)
        return urls

    monkeypatch.setattr(virtual, "get_index_file", fake_get_index_file)
    monkeypatch.setattr(virtual, "_get_site_urls", fake_get_site_urls)
    monkeypatch.setattr(
        virtual,
        "_open_virtual_site",
        lambda source, channel_urls, trace: (lazy_image, manifest),
    )

    get_jump_image_site(
        "source_8",
        "J3",
        "A1166127",
        "A01",
        index_origin=origin,
        index_hash=index_hash,
    )

    assert downloads == [(origin, index_hash)]
    assert scan_origins == [str(image_index)]
