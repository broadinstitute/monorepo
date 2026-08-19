"""Lazy, byte-range-backed access to complete JUMP imaging sites."""

from __future__ import annotations

import io
import math
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import BinaryIO, cast

import numpy as np
import xarray as xr
from obspec_utils.protocols import ReadableStore
from obspec_utils.registry import ObjectStoreRegistry
from obspec_utils.wrappers import RequestTrace, TracingReadableStore
from obstore.store import from_url
from tifffile import TiffFile, TiffFileError, TiffPage
from virtualizarr import open_virtual_mfdataset
from virtualizarr.manifests import (
    ChunkManifest,
    ManifestArray,
    ManifestGroup,
    ManifestStore,
)
from zarr.codecs import BytesCodec
from zarr.core.dtype import parse_data_type
from zarr.core.metadata.v3 import ArrayV3Metadata

from jump_portrait._index import (
    CHANNELS,
    DEFAULT_INDEX_ORIGIN,
    _get_index_scan_origin,
    _get_site_urls,
    get_index_file,
)

__all__ = [
    "CHANNELS",
    "RequestTrace",
    "UnsupportedTIFFLayoutError",
    "get_jump_image_site",
    "get_jump_image_site_from_metadata",
]

GALLERY_ORIGIN = "s3://cellpainting-gallery/"
MAX_TIFF_METADATA_BYTES = 1024 * 1024
TARGET_CHUNK_ROWS = 128


class UnsupportedTIFFLayoutError(ValueError):
    """Report a TIFF layout that cannot be represented by the lazy loader."""


class _BoundedRangeReader(io.RawIOBase):
    """Expose random-access object ranges without allowing a complete TIFF read."""

    def __init__(self, store: ReadableStore, path: str) -> None:
        self._store = store
        self._path = path
        self._position = 0
        self._size = int(store.head(path)["size"])
        self._requested_bytes = 0
        self.name = path

    def readable(self) -> bool:
        """Report that the reader supports reads."""
        return True

    def seekable(self) -> bool:
        """Report that the reader supports random access."""
        return True

    def tell(self) -> int:
        """Return the current byte position."""
        return self._position

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        """Move to an absolute, relative, or end-relative byte position."""
        if whence == io.SEEK_SET:
            position = offset
        elif whence == io.SEEK_CUR:
            position = self._position + offset
        elif whence == io.SEEK_END:
            position = self._size + offset
        else:
            raise ValueError(f"Unsupported seek mode: {whence}")
        if position < 0:
            raise ValueError(f"Cannot seek to negative TIFF offset {position}")
        self._position = position
        return position

    def read(self, size: int = -1) -> bytes:
        """Read one bounded range at the current position."""
        if size < 0:
            raise ValueError("Unbounded TIFF reads are not supported")
        length = min(size, max(0, self._size - self._position))
        if length == 0:
            return b""

        budget = min(MAX_TIFF_METADATA_BYTES, max(0, self._size - 1))
        if self._requested_bytes + length > budget:
            raise ValueError(
                "TIFF metadata parsing exceeded the bounded range budget: "
                f"requested more than {budget} bytes from a {self._size}-byte object"
            )

        data = bytes(
            self._store.get_range(
                self._path,
                start=self._position,
                length=length,
            )
        )
        self._position += len(data)
        self._requested_bytes += len(data)
        return data


def _coalesce_strips(
    offsets: np.ndarray,
    byte_counts: np.ndarray,
    rows_per_strip: int,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Combine contiguous strips into complete chunks of at most 128 rows."""
    strips_per_chunk = math.gcd(
        offsets.size,
        max(1, TARGET_CHUNK_ROWS // rows_per_strip),
    )
    contiguous = np.all(offsets[1:] == offsets[:-1] + byte_counts[:-1])
    if strips_per_chunk == 1 or not contiguous:
        return offsets, byte_counts, rows_per_strip
    return (
        offsets[::strips_per_chunk],
        byte_counts.reshape(-1, strips_per_chunk).sum(axis=1),
        rows_per_strip * strips_per_chunk,
    )


def _manifest_from_page(page: TiffPage, url: str, byteorder: str) -> ManifestArray:
    shape = tuple(int(length) for length in page.shape)
    if len(shape) != 2 or int(page.samplesperpixel) != 1:
        raise NotImplementedError(
            f"expected one two-dimensional sample plane, got shape={shape} "
            f"and samples_per_pixel={page.samplesperpixel}"
        )
    if page.is_tiled:
        raise NotImplementedError("tiled TIFFs are not yet supported")
    if int(page.compression) != 1:
        raise NotImplementedError(
            f"TIFF compression {int(page.compression)} is not yet supported"
        )
    if int(page.predictor) != 1:
        raise NotImplementedError(
            f"TIFF predictor {int(page.predictor)} is not yet supported"
        )

    image_height, image_width = shape
    rows_per_strip = int(page.rowsperstrip)
    if rows_per_strip <= 0 or image_height % rows_per_strip:
        raise NotImplementedError(
            f"partial TIFF strips are not supported: height={image_height}, "
            f"rows_per_strip={rows_per_strip}"
        )

    dtype = np.dtype(page.dtype).newbyteorder("=")
    offsets = np.asarray(page.dataoffsets, dtype=np.uint64)
    byte_counts = np.asarray(page.databytecounts, dtype=np.uint64)
    expected_strips = image_height // rows_per_strip
    expected_strip_bytes = rows_per_strip * image_width * dtype.itemsize
    if offsets.size != expected_strips or byte_counts.size != expected_strips:
        raise ValueError(
            f"expected {expected_strips} TIFF strips, got "
            f"{offsets.size} offsets and {byte_counts.size} byte counts"
        )
    if not np.all(byte_counts == expected_strip_bytes):
        raise NotImplementedError(
            "variable or padded TIFF strip byte counts are not yet supported"
        )

    offsets, byte_counts, chunk_rows = _coalesce_strips(
        offsets,
        byte_counts,
        rows_per_strip,
    )
    manifest_shape = (offsets.size, 1)
    offsets = offsets.reshape(manifest_shape)
    byte_counts = byte_counts.reshape(manifest_shape)
    paths = np.full(offsets.shape, url, dtype=np.dtypes.StringDType())
    chunk_manifest = ChunkManifest.from_arrays(
        paths=paths,
        offsets=offsets,
        lengths=byte_counts,
    )
    zarr_dtype = parse_data_type(dtype, zarr_format=3)
    endian = "little" if byteorder == "<" else "big"
    metadata = ArrayV3Metadata(
        shape=shape,
        data_type=zarr_dtype,
        chunk_grid={
            "name": "regular",
            "configuration": {"chunk_shape": (chunk_rows, image_width)},
        },
        chunk_key_encoding={"name": "default"},
        fill_value=zarr_dtype.default_scalar(),
        codecs=[BytesCodec(endian=endian)],
        attributes={},
        dimension_names=("y", "x"),
        storage_transformers=None,
    )
    return ManifestArray(metadata=metadata, chunkmanifest=chunk_manifest)


def _manifest_from_tiff(
    url: str,
    registry: ObjectStoreRegistry,
) -> ManifestArray:
    store, path = registry.resolve(url)
    reader = _BoundedRangeReader(store, path)
    with TiffFile(cast("BinaryIO", reader)) as tiff:
        if len(tiff.pages) != 1:
            raise NotImplementedError(
                f"multi-page TIFFs are not yet supported; found {len(tiff.pages)} pages"
            )
        page = cast("TiffPage", tiff.pages[0])
        return _manifest_from_page(page, url, tiff.byteorder)


class _BoundedTIFFParser:
    """Build a VirtualiZarr store from bounded TIFF metadata ranges."""

    def __call__(
        self,
        url: str,
        registry: ObjectStoreRegistry,
    ) -> ManifestStore:
        manifest_array = _manifest_from_tiff(url, registry)
        return ManifestStore(
            group=ManifestGroup(arrays={"0": manifest_array}),
            registry=registry,
        )


def _gallery_registry(trace: RequestTrace | None) -> ObjectStoreRegistry:
    store = from_url(GALLERY_ORIGIN, region="us-east-1", skip_signature=True)
    if trace is not None:
        store = TracingReadableStore(store, trace)
    return ObjectStoreRegistry({GALLERY_ORIGIN: store})


def _open_virtual_site(
    source: str,
    channel_urls: dict[str, str],
    trace: RequestTrace | None,
) -> tuple[xr.DataArray, ManifestArray]:
    registry = _gallery_registry(trace)
    channel_coordinate = xr.DataArray(
        list(CHANNELS),
        dims="channel",
        name="channel",
    )
    try:
        virtual_dataset = open_virtual_mfdataset(
            [channel_urls[channel] for channel in CHANNELS],
            registry=registry,
            parser=_BoundedTIFFParser(),
            concat_dim=channel_coordinate,
            combine="nested",
            coords="minimal",
            compat="override",
        )
    except (NotImplementedError, TiffFileError, ValueError) as error:
        raise UnsupportedTIFFLayoutError(
            f"Unsupported TIFF layout for source {source!r}: "
            f"{type(error).__name__}: {error}"
        ) from error

    manifest_array = virtual_dataset["0"].data
    if not isinstance(manifest_array, ManifestArray):
        raise TypeError(
            "The bounded TIFF parser did not produce a VirtualiZarr ManifestArray for "
            f"source {source!r}; got {type(manifest_array).__name__}"
        )

    manifest_array = ManifestArray(
        metadata=replace(
            manifest_array.metadata,
            dimension_names=("channel", "y", "x"),
        ),
        chunkmanifest=manifest_array.manifest,
    )
    manifest_store = ManifestStore(
        group=ManifestGroup(arrays={"image": manifest_array}),
        registry=registry,
    )
    image = xr.open_zarr(
        manifest_store,
        zarr_format=3,
        consolidated=False,
        chunks=None,  # pyright: ignore[reportArgumentType]
        mask_and_scale=False,
        decode_times=False,
    )["image"].assign_coords(channel=list(CHANNELS))
    image.attrs.update(
        {
            "source_layout": "uncompressed strips",
            "virtual_chunk_shape": tuple(
                int(length) for length in image.encoding["chunks"]
            ),
        }
    )
    return image, manifest_array


def _finish_site(
    image: xr.DataArray,
    manifest_array: ManifestArray,
    *,
    source: str,
    batch: str,
    plate: str,
    well: str,
    site: int,
    channel_urls: dict[str, str],
    index_origin: str | None,
) -> xr.DataArray:
    image.name = "image"
    image.attrs.update(
        {
            "source": source,
            "batch": batch,
            "plate": plate,
            "well": well,
            "site": site,
            "source_urls": channel_urls,
            "image_index_origin": index_origin,
            "virtual_reference_count": len(manifest_array.manifest),
            "virtual_reference_bytes": manifest_array.nbytes_virtual,
        }
    )
    return image


def get_jump_image_site(
    source: str,
    batch: str,
    plate: str,
    well: str,
    site: int | str = 1,
    *,
    index_origin: str | Path = DEFAULT_INDEX_ORIGIN,
    index_hash: str | None = None,
    trace: RequestTrace | None = None,
) -> xr.DataArray:
    """
    Expose one five-channel JUMP site as a lazy labeled array.

    The image index, TIFF metadata, and selected pixels are read using byte-range
    requests by default. Constructing the array creates no local index or TIFF
    files and does not download complete remote objects. Pixel reads remain lazy
    until the returned array is indexed and materialized.

    Parameters
    ----------
    source, batch, plate, well, site
        Image-index coordinates for a single JUMP imaging site.
    index_origin
        URL or local path for ``jump_index.parquet``.
    index_hash
        Optional Pooch-compatible content hash. Supplying a hash explicitly
        downloads and verifies the complete remote image index instead of using
        the default partial Range-scan path.
    trace
        Optional request trace that records TIFF metadata and pixel byte ranges.

    Returns
    -------
    xarray.DataArray
        Lazy original-intensity pixels with dimensions ``(channel, y, x)``.

    Raises
    ------
    UnsupportedTIFFLayoutError
        If VirtualTIFF cannot represent the source's TIFF layout.
    ValueError
        If the image index does not contain exactly one matching site.

    """
    site_number = int(site)
    index_scan_origin = (
        str(get_index_file(index_origin, index_hash))
        if index_hash is not None
        else _get_index_scan_origin(index_origin)
    )
    channel_urls = _get_site_urls(
        index_scan_origin,
        source,
        batch,
        plate,
        well,
        site_number,
    )
    image, manifest_array = _open_virtual_site(source, channel_urls, trace)
    return _finish_site(
        image,
        manifest_array,
        source=source,
        batch=batch,
        plate=plate,
        well=well,
        site=site_number,
        channel_urls=channel_urls,
        index_origin=str(index_origin),
    )


def get_jump_image_site_from_metadata(
    record: Mapping[str, object],
    *,
    trace: RequestTrace | None = None,
) -> xr.DataArray:
    """Open one site directly from a returned image-index metadata record."""
    fields = {
        field.lower(): record.get(f"Metadata_{field}")
        for field in ("Source", "Batch", "Plate", "Well", "Site")
    }
    missing = [field for field, value in fields.items() if value is None]
    if missing:
        raise ValueError(f"Metadata record is missing location fields: {missing}")

    channel_urls = {channel: record.get(f"URL_Orig{channel}") for channel in CHANNELS}
    invalid = [
        channel
        for channel, url in channel_urls.items()
        if not isinstance(url, str) or not url.startswith(GALLERY_ORIGIN)
    ]
    if invalid:
        raise ValueError(
            "Metadata record has no public Cell Painting Gallery URL for "
            f"channels: {invalid}"
        )

    source = str(fields["source"])
    urls = {channel: str(url) for channel, url in channel_urls.items()}
    image, manifest_array = _open_virtual_site(source, urls, trace)
    return _finish_site(
        image,
        manifest_array,
        source=source,
        batch=str(fields["batch"]),
        plate=str(fields["plate"]),
        well=str(fields["well"]),
        site=int(str(fields["site"])),
        channel_urls=urls,
        index_origin=None,
    )
