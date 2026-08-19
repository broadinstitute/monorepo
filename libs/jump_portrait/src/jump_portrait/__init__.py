"""Fetch cell images from JUMP using either gene or their unique identifiers."""

import sys
from typing import TYPE_CHECKING

from jump_portrait.fetch import get_item_location_metadata, get_jump_image

if TYPE_CHECKING:
    from jump_portrait.virtual import (
        CHANNELS,
        RequestTrace,
        UnsupportedTIFFLayoutError,
        get_jump_image_site,
        get_jump_image_site_from_metadata,
    )

__all__ = [
    "CHANNELS",
    "RequestTrace",
    "UnsupportedTIFFLayoutError",
    "get_item_location_metadata",
    "get_jump_image",
    "get_jump_image_site",
    "get_jump_image_site_from_metadata",
]

_LAZY_EXPORTS = {
    "CHANNELS",
    "RequestTrace",
    "UnsupportedTIFFLayoutError",
    "get_jump_image_site",
    "get_jump_image_site_from_metadata",
}


def __getattr__(name: str) -> object:
    """Import the Python 3.11+ lazy image API only when requested."""
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    if sys.version_info < (3, 11):
        raise RuntimeError("The lazy JUMP image API requires Python 3.11 or newer")

    from jump_portrait import virtual

    value = getattr(virtual, name)
    globals()[name] = value
    return value
