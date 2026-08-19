"""Resolve and query the JUMP image index."""

from functools import cache
from pathlib import Path

import duckdb
from pooch import retrieve

ZENODO_INDEX_ORIGIN = (
    "https://zenodo.org/api/records/19373370/files/jump_index.parquet/content"
)
CLOUDFRONT_INDEX_ORIGIN = (
    "https://d3dw4c1b79pj57.cloudfront.net/19373370/jump_index.parquet/content"
)
DEFAULT_INDEX_ORIGIN = CLOUDFRONT_INDEX_ORIGIN
DEFAULT_INDEX_SIZE = 145_197_890
DEFAULT_INDEX_HASH = (
    "sha256:f45ea1a5de091e43caf35358370abf843bd2be47b2810283fd76db472b5acc6a"
)
CHANNELS: tuple[str, ...] = ("AGP", "DNA", "ER", "Mito", "RNA")


def _local_index_path(index_origin: str | Path) -> Path | None:
    """Validate and return a local index origin, if supplied."""
    if isinstance(index_origin, Path) or "://" not in index_origin:
        path = Path(index_origin).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Image index does not exist: {path}")
        return path
    return None


@cache
def get_index_file(
    index_origin: str | Path = DEFAULT_INDEX_ORIGIN,
    index_hash: str | None = DEFAULT_INDEX_HASH,
) -> Path:
    """Return a local index or download and verify a remote index."""
    local_path = _local_index_path(index_origin)
    if local_path is not None:
        return local_path
    return Path(retrieve(str(index_origin), known_hash=index_hash))


def _get_index_scan_origin(index_origin: str | Path) -> str:
    """Resolve an index for a DuckDB scan without downloading it."""
    local_path = _local_index_path(index_origin)
    return str(local_path if local_path is not None else index_origin)


def _get_site_urls(
    index_origin: str | Path,
    source: str,
    batch: str,
    plate: str,
    well: str,
    site: int,
) -> dict[str, str]:
    """Return the five original TIFF URLs for one indexed site."""
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
            [str(index_origin), source, batch, plate, well, site],
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
