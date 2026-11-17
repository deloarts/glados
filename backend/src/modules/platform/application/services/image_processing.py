"""
Post-processing for uploaded product images (the made-item and bought-item
"thumbnail" and "image" categories). The background is made transparent by
flood-filling the white regions connected to the image corners. The cleared
margin is then trimmed, which never removes subject pixels and keeps a small
subject from being dwarfed by padding. Finally the canvas is enlarged, never
cropped, to a square with the subject centred on a transparent backdrop.

Always returns PNG-encoded bytes, since JPEG can't carry an alpha
channel and the result must be square with a transparent background.
"""

import io

from PIL import Image
from PIL import ImageDraw
from PIL import UnidentifiedImageError

__all__ = [
    "IMAGE_DECODE_ERRORS",
    "MAX_IMAGE_PIXELS",
    "ImageTooLargeError",
    "UnidentifiedImageError",
    "process_image_for_upload",
    "shrink_image",
]

# The largest image a product picture may have, in pixels: 8000 x 5000. A
# few megabytes of a highly compressible file can describe far more, and
# each copy the processing makes costs four bytes per pixel, so a larger
# one is refused before it is decoded.
MAX_IMAGE_PIXELS = 40_000_000

_WHITE_BACKGROUND_TOLERANCE = 24
_TRANSPARENT: tuple[int, int, int, int] = (0, 0, 0, 0)


class ImageTooLargeError(ValueError):
    """The image has more pixels than MAX_IMAGE_PIXELS."""


# What decoding an upload can raise: not an image, a broken one, or one
# with more pixels than allowed, by this module's check or Pillow's own.
IMAGE_DECODE_ERRORS: tuple[type[Exception], ...] = (
    UnidentifiedImageError,
    OSError,
    ImageTooLargeError,
    Image.DecompressionBombError,
)


def _open_rgba(data: bytes) -> Image.Image:
    """The image in `data` as RGBA, after checking its size from the header,
    so an oversized image is refused before any pixel is decoded."""
    with Image.open(io.BytesIO(data)) as opened:
        width, height = opened.size
        if width * height > MAX_IMAGE_PIXELS:
            raise ImageTooLargeError(
                f"The image is {width} x {height} pixels; at most {MAX_IMAGE_PIXELS} pixels"
                " are accepted."
            )
        return opened.convert("RGBA")


def process_image_for_upload(data: bytes) -> bytes:
    """Remove a white background and pad the canvas to a square.
    Raises one of IMAGE_DECODE_ERRORS if `data` is not a decodable image,
    even though its content type passed validation, or is too large.
    """
    image = _open_rgba(data)

    _remove_white_background(image)
    image = _trim_transparent_margin(image)
    image = _pad_to_square(image)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def shrink_image(data: bytes, max_side: int) -> bytes:
    """Scale an image down, keeping its aspect ratio, until neither side
    exceeds `max_side`, and return it as PNG. A smaller image is only
    re-encoded. Used to derive a thumbnail from a full-size image, which
    the thumbnail category's smaller size limit would otherwise reject.
    Raises like `process_image_for_upload` for data that is not an image.
    """
    image = _open_rgba(data)
    image.thumbnail((max_side, max_side))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _remove_white_background(image: Image.Image) -> None:
    """Flood-fill white regions reachable from each corner to
    transparent, in place. Only background connected to an edge is
    cleared, so white pixels enclosed within the subject (e.g. text,
    highlights) are left untouched.
    """
    width, height = image.size
    if width == 0 or height == 0:
        return

    corners = {(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)}
    for corner in corners:
        pixel = image.getpixel(corner)
        if isinstance(pixel, tuple) and _is_near_white(pixel):
            ImageDraw.floodfill(image, corner, _TRANSPARENT, thresh=_WHITE_BACKGROUND_TOLERANCE)


def _is_near_white(pixel: tuple[int, ...]) -> bool:
    r, g, b, a = pixel
    threshold = 255 - _WHITE_BACKGROUND_TOLERANCE
    return bool(a) and r >= threshold and g >= threshold and b >= threshold


def _trim_transparent_margin(image: Image.Image) -> Image.Image:
    """Crop away fully-transparent border rows/columns. Only touches
    pixels that background removal already cleared, so the subject
    itself is never cropped.
    """
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        return image
    return image.crop(bbox)


def _pad_to_square(image: Image.Image) -> Image.Image:
    width, height = image.size
    size = max(width, height)
    if width == size and height == size:
        return image

    canvas = Image.new("RGBA", (size, size), _TRANSPARENT)
    offset = ((size - width) // 2, (size - height) // 2)
    canvas.paste(image, offset, image)
    return canvas
