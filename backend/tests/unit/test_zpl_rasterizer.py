"""
Unit tests for the Pillow-based ZPL preview rasterizer. No printer
involved: these assert on the PNG's structural properties (size, pixel
presence), not exact glyph rendering, since the preview is explicitly
approximate (see zpl_rasterizer.py's docstring).
"""

import io

from PIL import Image

from src.modules.quality.adapters.outbound.rendering.zpl_rasterizer import ZplRasterizer

_SEED_TEMPLATE = (
    "^XA\n^CI28\n^PW827\n^LL378\n^LH0,0\n^MNY\n^MMT\n^PON\n^PR4\n\n"
    "^FO12,12^GB803,354,3^FS\n\n"
    "^FO592,20^BQN,2,6^FH^FDQA,https://example.test/resolve/1^FS\n\n"
    "^FO32,28^A0N,24,24^FDPART NO.^FS\n"
    "^FO32,56^A0N,52,52^FB390,1,0,L^FH^FDMI-004871^FS\n"
    "^XZ"
)


def _open(png: bytes) -> Image.Image:
    return Image.open(io.BytesIO(png))


class TestDimensions:
    def test_pw_ll_set_output_size_at_scale_1(self):
        png, _ = ZplRasterizer().rasterize(_SEED_TEMPLATE, design_dpi=300, format_convert_factor=1)
        assert _open(png).size == (827, 378)

    def test_format_convert_factor_scales_output(self):
        # ^PW413^LL189 authored at 150 dpi, doubled by format_convert_factor=2:
        # this is the exact mechanism that made the first two prototype
        # labels overshoot the stock when it was computed wrong.
        template = "^XA^PW413^LL189^XZ"
        png, _ = ZplRasterizer().rasterize(template, design_dpi=150, format_convert_factor=2)
        assert _open(png).size == (826, 378)

    def test_seed_template_is_70x32mm_at_300dpi(self):
        png, _ = ZplRasterizer().rasterize(_SEED_TEMPLATE, design_dpi=300, format_convert_factor=1)
        width, height = _open(png).size
        assert round(width * 25.4 / 300, 1) == 70.0
        assert round(height * 25.4 / 300, 1) == 32.0

    def test_missing_pw_ll_falls_back_to_a_default_size(self):
        png, _ = ZplRasterizer().rasterize(
            "^XA^FO0,0^FD x ^FS^XZ", design_dpi=300, format_convert_factor=1
        )
        assert _open(png).size[0] > 0
        assert _open(png).size[1] > 0


class TestWarnings:
    def test_seed_template_produces_no_warnings(self):
        _, warnings = ZplRasterizer().rasterize(
            _SEED_TEMPLATE, design_dpi=300, format_convert_factor=1
        )
        assert warnings == []

    def test_unrecognised_command_is_reported_not_dropped(self):
        _, warnings = ZplRasterizer().rasterize(
            "^XA^ZZfoo^XZ", design_dpi=300, format_convert_factor=1
        )
        assert any("ZZ" in w for w in warnings)

    def test_barcode_command_is_reported_as_unsupported(self):
        template = "^XA^FO10,10^BY2,3.0,50^BCN,50,Y,N,N^FD12345^FS^XZ"
        _, warnings = ZplRasterizer().rasterize(template, design_dpi=300, format_convert_factor=1)
        assert any("BY" in w or "BC" in w for w in warnings)


class TestDrawing:
    def test_box_command_draws_non_white_pixels(self):
        template = "^XA^PW100^LL100^FO10,10^GB80,80,4^FS^XZ"
        png, _ = ZplRasterizer().rasterize(template, design_dpi=300, format_convert_factor=1)
        img = _open(png).convert("RGB")
        colors = {img.getpixel((x, 10)) for x in range(10, 90)}
        assert colors != {(255, 255, 255)}

    def test_qr_field_draws_non_white_region(self):
        template = "^XA^PW200^LL200^FO10,10^BQN,2,4^FDQA,https://example.test/1^FS^XZ"
        png, _ = ZplRasterizer().rasterize(template, design_dpi=300, format_convert_factor=1)
        img = _open(png).convert("RGB")
        region = img.crop((10, 10, 100, 100))
        colors = set(region.getdata())
        assert colors != {(255, 255, 255)}

    def test_text_field_draws_non_white_pixels(self):
        template = "^XA^PW300^LL100^FO10,10^A0N,30,30^FDHELLO^FS^XZ"
        png, _ = ZplRasterizer().rasterize(template, design_dpi=300, format_convert_factor=1)
        img = _open(png).convert("RGB")
        region = img.crop((10, 10, 150, 50))
        colors = set(region.getdata())
        assert colors != {(255, 255, 255)}

    def test_empty_template_still_returns_valid_png(self):
        png, _ = ZplRasterizer().rasterize("^XA^XZ", design_dpi=300, format_convert_factor=1)
        img = _open(png)
        assert img.format == "PNG"
