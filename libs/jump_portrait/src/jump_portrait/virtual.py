"""Lazy, byte-range-backed access to complete JUMP imaging sites."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import duckdb
import xarray as xr
from obspec_utils.registry import ObjectStoreRegistry
from obspec_utils.wrappers import RequestTrace, TracingReadableStore
from obstore.store import from_url
from virtual_tiff import VirtualTIFF
from virtualizarr import open_virtual_mfdataset
from virtualizarr.manifests import ManifestArray, ManifestGroup, ManifestStore

from jump_portrait.fetch import (
    DEFAULT_INDEX_HASH,
    DEFAULT_INDEX_ORIGIN,
    get_index_file,
)

__all__ = [
    "CHANNELS",
    "RequestTrace",
    "UnsupportedTIFFLayoutError",
    "get_jump_image_site",
]

CHANNELS: tuple[str, ...] = ("AGP", "DNA", "ER", "Mito", "RNA")
GALLERY_ORIGIN = "s3://cellpainting-gallery/"


class UnsupportedTIFFLayoutError(ValueError):
    """Report a TIFF layout that cannot be represented by the lazy loader."""


def _get_site_urls(
    index_path: Path,
    source: str,
    batch: str,
    plate: str,
    well: str,
    site: int,
) -> dict[str, str]:
    columns = ", ".join(f"URL_Orig{channel}" for channel in CHANNELS)
    statement = f"""
        SELECT {columns}
        FROM read_parquet(?)
        WHERE Metadata_Source = ?
          AND Metadata_Batch = ?
          AND Metadata_Plate = ?
          AND Metadata_Well = ?
          AND Metadata_Site = ?
    """
    with duckdb.connect() as connection:
        rows = connection.execute(
            statement,
            [str(index_path), source, batch, plate, well, site],
        ).fetchall()

    location = (
        f"source={source!r}, batch={batch!r}, plate={plate!r}, "
        f"well={well!r}, site={site}"
    )
    if len(rows) != 1:
        raise ValueError(
            f"Expected exactly one image-index row for {location}; found {len(rows)}"
        )

    urls: dict[str, object] = dict(zip(CHANNELS, rows[0], strict=True))
    missing = [channel for channel, url in urls.items() if not isinstance(url, str)]
    if missing:
        raise ValueError(
            f"Image-index row for {location} has no original TIFF URL for {missing}"
        )
    return {channel: url for channel, url in urls.items() if isinstance(url, str)}


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
            parser=VirtualTIFF(ifd=0),
            concat_dim=channel_coordinate,
            combine="nested",
            coords="minimal",
            compat="override",
        )
    except (NotImplementedError, ValueError) as error:
        raise UnsupportedTIFFLayoutError(
            f"Unsupported TIFF layout for source {source!r}: "
            f"{type(error).__name__}: {error}"
        ) from error

    manifest_array = virtual_dataset["0"].data
    if not isinstance(manifest_array, ManifestArray):
        raise TypeError(
            "VirtualTIFF did not produce a VirtualiZarr ManifestArray for "
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
    return image, manifest_array


def get_jump_image_site(
    source: str,
    batch: str,
    plate: str,
    well: str,
    site: int | str = 1,
    *,
    index_origin: str | Path = DEFAULT_INDEX_ORIGIN,
    index_hash: str | None = DEFAULT_INDEX_HASH,
    trace: RequestTrace | None = None,
) -> xr.DataArray:
    """
    Expose one five-channel JUMP site as a lazy labeled array.

    TIFF metadata and selected pixels are read using byte-range requests.
    Constructing the array creates no local TIFF files and does not download
    complete TIFF objects. Pixel reads remain lazy until the returned array is
    indexed and materialized.

    Parameters
    ----------
    source, batch, plate, well, site
        Image-index coordinates for a single JUMP imaging site.
    index_origin
        URL or local path for ``jump_index.parquet``.
    index_hash
        Pooch-compatible content hash for a remote image index.
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
    index_path = get_index_file(index_origin, index_hash)
    channel_urls = _get_site_urls(
        index_path,
        source,
        batch,
        plate,
        well,
        site_number,
    )
    image, manifest_array = _open_virtual_site(source, channel_urls, trace)
    image.name = "image"
    image.attrs.update(
        {
            "source": source,
            "batch": batch,
            "plate": plate,
            "well": well,
            "site": site_number,
            "source_urls": channel_urls,
            "image_index_origin": str(index_origin),
            "virtual_reference_count": len(manifest_array.manifest),
            "virtual_reference_bytes": manifest_array.nbytes_virtual,
        }
    )
    return image
