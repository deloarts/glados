"""
Unit tests for the Pillow-based docket renderer. Structural assertions
(sizes, warnings, non-crash) rather than pixel-perfect ones, matching
test_zpl_rasterizer.py's approach. Critically, no printer of any
kind is involved anywhere here: render_pdf/render_preview_png/render_qr_png
take no printer argument at all, only take-it-or-leave-it bytes out.
"""

import io
import re

from PIL import Image

from src.modules.quality.adapters.outbound.rendering.docket_renderer import DocketRenderer
from src.modules.quality.adapters.outbound.rendering.docket_renderer import _mm
from src.modules.quality.application.services.docket_spec import parse_docket_spec
from src.modules.quality.ports.outbound.docket_spec_dto import RenderPage

_MEDIABOX_RE = re.compile(rb"/MediaBox\s*\[\s*[\d.]+\s+[\d.]+\s+([\d.]+)\s+([\d.]+)\s*\]")

_A5_SPEC = """
{
  "page": {"width_mm": 148, "height_mm": 210},
  "blocks": [
    {"type": "rect", "x": 8, "y": 8, "w": 132, "h": 194, "stroke_mm": 0.5},
    {"type": "line", "x": 8, "y": 24, "x2": 140, "y2": 24, "stroke_mm": 0.5},
    {"type": "text", "x": 14, "y": 12, "size_mm": 6, "bold": true, "text": "TITLE"},
    {"type": "text", "x": 14, "y": 34, "size_mm": 7, "bold": true, "field": "part_number"},
    {"type": "text", "x": 14, "y": 55, "size_mm": 5, "field": "article_name",
     "max_width_mm": 80, "max_lines": 2},
    {"type": "qr", "x": 102, "y": 29, "size_mm": 30, "field": "qr_payload"},
    {"type": "image", "x": 14, "y": 94, "w": 120, "h": 97, "field": "part_image",
     "fallback_text": "no part image on file"}
  ]
}
"""


def _pages(spec, values: dict | None = None, images: dict | None = None) -> list[RenderPage]:
    """A parsed spec as the one-page list the renderer takes.
    Pagination is upstream (docket_pagination.py); these tests are about
    drawing one page, so they build the page directly."""
    return [
        RenderPage(page=spec.page, blocks=spec.blocks, values=values or {}, images=images or {})
    ]


def _open(png: bytes) -> Image.Image:
    return Image.open(io.BytesIO(png))


def _mm_of(px: int, dpi: int = 300) -> float:
    return round(px * 25.4 / dpi, 1)


def _pdf_size_mm(pdf_bytes: bytes) -> tuple[float, float]:
    """Pillow writes PDFs but cannot read them back, so parse the page size
    straight out of the /MediaBox (in points, 1/72in) rather than adding a
    PDF-reading dependency just for tests."""
    match = _MEDIABOX_RE.search(pdf_bytes)
    assert match is not None
    width_pt, height_pt = float(match.group(1)), float(match.group(2))
    return round(width_pt * 25.4 / 72, 1), round(height_pt * 25.4 / 72, 1)


class TestRenderPreviewPng:
    def test_page_size_matches_spec_mm_at_300dpi(self):
        spec = parse_docket_spec(_A5_SPEC)
        png, warnings = DocketRenderer().render_preview_png(
            _pages(
                spec, {"part_number": "MI-1", "article_name": "x", "qr_payload": "https://x"}, {}
            )
        )
        width, height = _open(png).size
        assert _mm_of(width) == 148.0
        assert _mm_of(height) == 210.0
        assert warnings == []

    def test_missing_image_falls_back_to_text_without_raising(self):
        spec = parse_docket_spec(_A5_SPEC)
        png, warnings = DocketRenderer().render_preview_png(
            _pages(
                spec,
                {"part_number": "MI-1", "article_name": "x", "qr_payload": "https://x"},
                {"part_image": None},
            )
        )
        assert _open(png).size[0] > 0
        assert warnings == []

    def test_empty_qr_payload_warns_and_skips_rather_than_raising(self):
        spec = parse_docket_spec(_A5_SPEC)
        _, warnings = DocketRenderer().render_preview_png(
            _pages(spec, {"part_number": "MI-1", "article_name": "x", "qr_payload": ""}, {})
        )
        assert len(warnings) == 1
        assert "qr_payload" in warnings[0]

    def test_corrupt_image_bytes_are_skipped_without_raising(self):
        spec = parse_docket_spec(_A5_SPEC)
        png, warnings = DocketRenderer().render_preview_png(
            _pages(
                spec,
                {"part_number": "MI-1", "article_name": "x", "qr_payload": "https://x"},
                {"part_image": b"not a real image"},
            )
        )
        assert _open(png).size[0] > 0
        assert warnings == []

    def test_corrupt_image_bytes_log_a_warning_naming_the_field(self, glados_caplog):
        spec = parse_docket_spec(_A5_SPEC)
        DocketRenderer().render_preview_png(
            _pages(
                spec,
                {"part_number": "MI-1", "article_name": "x", "qr_payload": "https://x"},
                {"part_image": b"not a real image"},
            )
        )

        (record,) = [r for r in glados_caplog.records if r.levelname == "WARNING"]
        assert "part_image" in record.getMessage()
        assert record.exc_info is not None

    def test_long_text_wraps_within_max_lines(self):
        spec = parse_docket_spec(_A5_SPEC)
        # Must not raise even when the text is far longer than max_width_mm
        # allows across max_lines: the ellipsis path.
        png, _ = DocketRenderer().render_preview_png(
            _pages(
                spec,
                {
                    "part_number": "MI-1",
                    "article_name": "a very long article name that will not fit on two lines",
                    "qr_payload": "https://x",
                },
                {},
            )
        )
        assert _open(png).size[0] > 0


class TestRenderPdf:
    def test_a5_page_on_a4_paper_is_centred_on_a_larger_sheet(self):
        spec = parse_docket_spec(_A5_SPEC)
        pdf_bytes, _ = DocketRenderer().render_pdf(
            _pages(
                spec, {"part_number": "MI-1", "article_name": "x", "qr_payload": "https://x"}, {}
            ),
            paper="a4",
        )
        assert _pdf_size_mm(pdf_bytes) == (210.0, 297.0)

    def test_a5_page_on_a5_paper_stays_1to1(self):
        spec = parse_docket_spec(_A5_SPEC)
        pdf_bytes, _ = DocketRenderer().render_pdf(
            _pages(
                spec, {"part_number": "MI-1", "article_name": "x", "qr_payload": "https://x"}, {}
            ),
            paper="a5",
        )
        assert _pdf_size_mm(pdf_bytes) == (148.0, 210.0)

    def test_unknown_paper_falls_back_to_1to1(self):
        spec = parse_docket_spec(_A5_SPEC)
        pdf_bytes, _ = DocketRenderer().render_pdf(
            _pages(
                spec, {"part_number": "MI-1", "article_name": "x", "qr_payload": "https://x"}, {}
            ),
            paper="letter",
        )
        assert _pdf_size_mm(pdf_bytes) == (148.0, 210.0)

    def test_page_larger_than_requested_sheet_stays_1to1(self):
        big_spec = parse_docket_spec('{"page": {"width_mm": 250, "height_mm": 300}, "blocks": []}')
        pdf_bytes, _ = DocketRenderer().render_pdf(_pages(big_spec), paper="a4")
        assert _pdf_size_mm(pdf_bytes) == (250.0, 300.0)

    def test_a4_aligned_sheet_is_landscape_297x210(self):
        spec = parse_docket_spec(_A5_SPEC)
        pdf_bytes, _ = DocketRenderer().render_pdf(
            _pages(
                spec, {"part_number": "MI-1", "article_name": "x", "qr_payload": "https://x"}, {}
            ),
            paper="a4_aligned",
        )
        assert _pdf_size_mm(pdf_bytes) == (297.0, 210.0)

    def test_a5_page_too_wide_for_an_a4_aligned_half_stays_1to1(self):
        # Wider than 148.5mm doesn't fit in one half of a landscape A4 sheet.
        wide_spec = parse_docket_spec('{"page": {"width_mm": 200, "height_mm": 210}, "blocks": []}')
        pdf_bytes, _ = DocketRenderer().render_pdf(_pages(wide_spec), paper="a4_aligned")
        assert _pdf_size_mm(pdf_bytes) == (200.0, 210.0)


class TestA4AlignedSheet:
    """A4 aligned mode: a landscape A4 sheet, the page flush against the
    left half, one cut line at the sheet's midpoint. One straight cut
    yields two A5-portrait halves, one already the finished docket."""

    def test_page_sits_flush_against_the_left_edge(self):
        spec = parse_docket_spec(_A5_SPEC)
        values = {"part_number": "MI-1", "article_name": "x", "qr_payload": "https://x"}
        renderer = DocketRenderer()
        page, _ = renderer._render_page(_pages(spec, values)[0])
        sheet = renderer._to_sheet(page, spec.page, "a4_aligned")

        # The spec's rect border sits at x=8mm in page-local coordinates.
        # Flush-left placement puts it at exactly that sheet x; centred
        # placement would put it much further right instead.
        assert sheet.getpixel((_mm(8), _mm(100))) == (0, 0, 0)

    def test_cut_line_sits_at_the_sheet_midpoint(self):
        spec = parse_docket_spec(_A5_SPEC)
        values = {"part_number": "MI-1", "article_name": "x", "qr_payload": "https://x"}
        renderer = DocketRenderer()
        page, _ = renderer._render_page(_pages(spec, values)[0])
        sheet = renderer._to_sheet(page, spec.page, "a4_aligned")

        mid_x = sheet.width // 2
        # The cut line itself is drawn black at the midpoint.
        assert sheet.getpixel((mid_x, sheet.height // 2)) == (0, 0, 0)

    def test_right_half_is_blank(self):
        spec = parse_docket_spec(_A5_SPEC)
        values = {"part_number": "MI-1", "article_name": "x", "qr_payload": "https://x"}
        renderer = DocketRenderer()
        page, _ = renderer._render_page(_pages(spec, values)[0])
        sheet = renderer._to_sheet(page, spec.page, "a4_aligned")

        right_quarter_x = sheet.width * 3 // 4
        assert sheet.getpixel((right_quarter_x, sheet.height // 2)) == (255, 255, 255)


class TestMultiPage:
    """render_pdf takes a LIST of pages: one PDF, one page per entry."""

    def _spec(self):
        return parse_docket_spec('{"page": {"width_mm": 210, "height_mm": 297}, "blocks": []}')

    def test_three_pages_produce_three_mediaboxes(self):
        spec = self._spec()
        pages = _pages(spec) * 3
        pdf_bytes, _ = DocketRenderer().render_pdf(pages, paper="a4")
        assert len(_MEDIABOX_RE.findall(pdf_bytes)) == 3

    def test_each_page_carries_its_own_values(self):
        spec = parse_docket_spec(
            '{"page": {"width_mm": 60, "height_mm": 20},'
            ' "blocks": [{"type": "text", "x": 2, "y": 2, "size_mm": 6, "field": "n"}]}'
        )
        renderer = DocketRenderer()
        first, _ = renderer._render_page(_pages(spec, {"n": "1"})[0])
        second, _ = renderer._render_page(_pages(spec, {"n": "8"})[0])
        assert list(first.getdata()) != list(second.getdata())

    def test_preview_stacks_pages_into_one_taller_png(self):
        spec = self._spec()
        renderer = DocketRenderer()
        single, _ = renderer.render_preview_png(_pages(spec))
        stacked, warnings = renderer.render_preview_png(_pages(spec) * 2)

        assert _open(stacked).height > _open(single).height
        assert warnings == []

    def test_preview_caps_pages_and_says_so(self):
        spec = self._spec()
        _, warnings = DocketRenderer().render_preview_png(_pages(spec) * 9)
        assert any("9 pages" in warning for warning in warnings)


class TestRenderQrPng:
    def test_produces_a_square_png_at_the_requested_size(self):
        png = DocketRenderer().render_qr_png("https://glados.test/resolve/abc", size_mm=25.0)
        image = _open(png)
        assert image.format == "PNG"
        assert image.size[0] == image.size[1]
        assert _mm_of(image.size[0]) == 25.0

    def test_default_size_is_25mm(self):
        png = DocketRenderer().render_qr_png("payload")
        assert _mm_of(_open(png).size[0]) == 25.0
