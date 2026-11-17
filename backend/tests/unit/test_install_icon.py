import struct

from src.modules.platform.domain.services.install_icon import install_icon_sizes
from src.modules.platform.domain.services.install_icon import png_size


def _png(width: int, height: int) -> bytes:
    """The first bytes of a PNG: the signature and the size in its IHDR chunk."""
    return (
        b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height)
    )


def test_png_size_reads_the_header() -> None:
    assert png_size(_png(512, 256)) == (512, 256)
    assert png_size(b"not a png at all, just some bytes") is None


def test_an_svg_favicon_scales_to_any_size() -> None:
    assert install_icon_sizes("image/svg+xml", b"<svg/>") == "any"


def test_a_square_png_of_192_pixels_or_more_serves_with_its_size() -> None:
    assert install_icon_sizes("image/png", _png(192, 192)) == "192x192"
    assert install_icon_sizes("image/png", _png(512, 512)) == "512x512"


def test_a_small_or_oblong_png_and_an_ico_do_not_serve() -> None:
    assert install_icon_sizes("image/png", _png(32, 32)) is None
    assert install_icon_sizes("image/png", _png(512, 256)) is None
    assert install_icon_sizes("image/png", b"broken") is None
    assert install_icon_sizes("image/x-icon", b"\x00\x00\x01\x00") is None
