"""
Whether the branding favicon can stand in for the app's own icon once the app
is installed on a phone or a desktop. A launcher draws that icon at 192 pixels
and larger, so only a scalable SVG or a square PNG at least that large is
sharp enough. A smaller favicon, or an ICO, leaves the Glados icon in place.
"""

import struct

MIN_INSTALL_ICON_PX = 192

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def png_size(data: bytes) -> tuple[int, int] | None:
    """The width and height a PNG declares in its header, or None for bytes that are no PNG."""
    if len(data) < 24 or not data.startswith(_PNG_SIGNATURE) or data[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", data[16:24])
    return int(width), int(height)


def install_icon_sizes(content_type: str, data: bytes) -> str | None:
    """The `sizes` value of the favicon as an install icon, or None when it is unsuitable.

    An SVG scales to any size. A PNG serves when it is square and at least
    `MIN_INSTALL_ICON_PX` wide.
    """
    if content_type == "image/svg+xml":
        return "any"
    if content_type != "image/png":
        return None
    size = png_size(data)
    if size is None:
        return None
    width, height = size
    if width != height or width < MIN_INSTALL_ICON_PX:
        return None
    return f"{width}x{height}"
