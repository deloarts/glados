"""Unit tests for image upload post-processing (white-background removal
and square-canvas padding). No storage, no HTTP, pure Pillow round-trips.
"""

import io

import pytest
from PIL import Image
from PIL import UnidentifiedImageError

from src.modules.platform.application.services.image_processing import ImageTooLargeError
from src.modules.platform.application.services.image_processing import process_image_for_upload
from src.modules.platform.application.services.image_processing import shrink_image


def _to_bytes(image: Image.Image, fmt: str = "PNG") -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


class TestProcessImageForUpload:
    def test_returns_png_with_alpha_channel(self):
        source = Image.new("RGB", (40, 40), (255, 255, 255))
        result = process_image_for_upload(_to_bytes(source))

        image = Image.open(io.BytesIO(result))
        assert image.format == "PNG"
        assert image.mode == "RGBA"

    def test_white_background_becomes_transparent_and_is_trimmed(self):
        # a small subject on a much larger white canvas: the cleared
        # background is trimmed away, so the output tracks the subject
        # (10x10), not the original 40x40 canvas.
        source = Image.new("RGB", (40, 40), (255, 255, 255))
        for x in range(15, 25):
            for y in range(15, 25):
                source.putpixel((x, y), (200, 30, 30))

        image = Image.open(io.BytesIO(process_image_for_upload(_to_bytes(source))))

        assert image.size == (10, 10)
        assert image.getpixel((5, 5)) == (200, 30, 30, 255)

    def test_enclosed_white_region_is_preserved(self):
        # A red square with a white hole in its center: the hole isn't
        # connected to any corner, so it must stay opaque even though
        # the surrounding canvas background is trimmed away.
        source = Image.new("RGB", (40, 40), (255, 255, 255))
        for x in range(5, 35):
            for y in range(5, 35):
                source.putpixel((x, y), (200, 30, 30))
        for x in range(18, 22):
            for y in range(18, 22):
                source.putpixel((x, y), (255, 255, 255))

        image = Image.open(io.BytesIO(process_image_for_upload(_to_bytes(source))))

        assert image.size == (30, 30)
        assert image.getpixel((15, 15)) == (255, 255, 255, 255)

    def test_non_square_image_is_padded_not_cropped(self):
        # fully opaque, no white pixels to remove/trim: isolates the
        # square-padding behavior on its own.
        source = Image.new("RGB", (60, 20), (10, 10, 200))

        image = Image.open(io.BytesIO(process_image_for_upload(_to_bytes(source))))

        assert image.size == (60, 60)
        # original content should be centered vertically, untouched.
        assert image.getpixel((0, 30))[3] == 255
        assert image.getpixel((59, 30))[3] == 255
        # padded margins are transparent.
        assert image.getpixel((30, 0))[3] == 0
        assert image.getpixel((30, 59))[3] == 0

    def test_square_image_is_left_unpadded(self):
        source = Image.new("RGB", (30, 30), (10, 10, 200))
        image = Image.open(io.BytesIO(process_image_for_upload(_to_bytes(source))))
        assert image.size == (30, 30)

    def test_excess_background_margin_is_trimmed_before_padding(self):
        # subject occupies a small fraction of an oversized canvas; the
        # output must not be dwarfed by padding based on the original
        # canvas size.
        source = Image.new("RGB", (400, 400), (255, 255, 255))
        for x in range(180, 220):
            for y in range(190, 210):
                source.putpixel((x, y), (200, 30, 30))

        image = Image.open(io.BytesIO(process_image_for_upload(_to_bytes(source))))

        assert image.size == (40, 40)
        assert image.getpixel((image.size[0] // 2, image.size[1] // 2))[3] == 255

    def test_invalid_bytes_raise_unidentified_image_error(self):
        with pytest.raises(UnidentifiedImageError):
            process_image_for_upload(b"not an image")


def _png_of(width: int, height: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("1", (width, height), 1).save(buffer, format="PNG")
    return buffer.getvalue()


def test_an_image_above_the_pixel_limit_is_refused_before_decoding() -> None:
    # A one-bit white PNG of this size compresses to a few kilobytes.
    data = _png_of(8001, 5000)
    assert len(data) < 1_000_000

    with pytest.raises(ImageTooLargeError):
        process_image_for_upload(data)
    with pytest.raises(ImageTooLargeError):
        shrink_image(data, 64)


def test_an_image_below_the_pixel_limit_is_accepted() -> None:
    # Returns PNG bytes; the check counts pixels, not the file size.
    assert process_image_for_upload(_png_of(40, 30)).startswith(b"\x89PNG")
