"""
Pillow-only renderer for the declarative docket block-list format
(docket_spec_dto.py): draws arbitrary block specs at arbitrary page sizes,
not tied to one hardcoded layout.

Nothing here is tied to one printer or even one output path: render_pdf()
produces a plain PDF any "ipp_document" printer can be given, or that can
be handed straight back to a user as a file download (see
download_print_document.py) with no printer involved at all.
"""

import io
from pathlib import Path

import segno
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

from src.modules.platform.infrastructure.logging.logger import log
from src.modules.quality.ports.outbound.docket_spec_dto import DocketPage
from src.modules.quality.ports.outbound.docket_spec_dto import ImageBlock
from src.modules.quality.ports.outbound.docket_spec_dto import LineBlock
from src.modules.quality.ports.outbound.docket_spec_dto import QrBlock
from src.modules.quality.ports.outbound.docket_spec_dto import RectBlock
from src.modules.quality.ports.outbound.docket_spec_dto import RenderPage
from src.modules.quality.ports.outbound.docket_spec_dto import TextBlock

_FONT_DIR = Path(__file__).parent / "fonts"
_FONT_REGULAR = _FONT_DIR / "LiberationSans-Regular.ttf"
_FONT_BOLD = _FONT_DIR / "LiberationSans-Bold.ttf"

_RENDER_DPI = 300

# Preview only (never printing): how many pages the stacked PNG shows, and
# the white gap between them.
_PREVIEW_PAGE_LIMIT = 4
_PREVIEW_GAP_MM = 6.0

# Sheet a "paper" value centres the page on, when the page is smaller than
# the sheet. Not a page size in itself; see _to_sheet.
_SHEET_SIZES_MM: dict[str, tuple[float, float]] = {
    "a4": (210.0, 297.0),
    "a5": (148.0, 210.0),
}

# "a4_aligned" is handled separately from _SHEET_SIZES_MM: landscape, and
# the page is placed flush left rather than centred. See _to_a4_aligned_sheet.
_A4_LANDSCAPE_MM: tuple[float, float] = (297.0, 210.0)


def _mm(millimeters: float, dpi: int = _RENDER_DPI) -> int:
    return round(millimeters * dpi / 25.4)


def _font(bold: bool, size_mm: float) -> ImageFont.FreeTypeFont:
    path = _FONT_BOLD if bold else _FONT_REGULAR
    return ImageFont.truetype(str(path), max(_mm(size_mm), 1))


def _fit_lines(
    draw: ImageDraw.ImageDraw,
    value: str,
    font: ImageFont.FreeTypeFont,
    max_width_px: int,
    max_lines: int,
) -> list[str]:
    """Greedy word wrap, ellipsising whatever no longer fits."""
    words, lines, current = value.split(), [], ""

    for word in words:
        probe = f"{current} {word}".strip()
        if draw.textlength(probe, font=font) <= max_width_px or not current:
            current = probe
            continue
        lines.append(current)
        current = word
        if len(lines) == max_lines:
            break

    if current and len(lines) < max_lines:
        lines.append(current)

    if len(lines) == max_lines and len(" ".join(lines).split()) < len(words):
        while lines[-1] and draw.textlength(lines[-1] + " …", font=font) > max_width_px:
            lines[-1] = lines[-1][:-1]
        lines[-1] += " …"

    return lines or [""]


def _qr_image(payload: str, size_px: int) -> Image.Image:
    qr = segno.make(payload, error="q")
    buffer = io.BytesIO()
    qr.save(buffer, kind="png", scale=10, border=0)
    return Image.open(buffer).convert("RGB").resize((size_px, size_px), Image.Resampling.NEAREST)


def _align_offset(align: str, slack: float) -> int:
    """Horizontal offset of a piece of content inside the space left over
    beside it; shared by text lines and images."""
    if align == "left":
        return 0
    return int(slack if align == "right" else slack / 2)


def _flatten(image: Image.Image) -> Image.Image:
    """CAD exports and logos are often RGBA; put them on white so the PDF
    stays clean rather than showing a black background for transparency."""
    flattened = Image.new("RGB", image.size, "white")
    flattened.paste(image, mask=image.split()[-1] if image.mode in {"RGBA", "LA"} else None)
    return flattened


class DocketRenderer:
    """Implements IDocketRenderer."""

    def render_pdf(self, pages: list[RenderPage], *, paper: str) -> tuple[bytes, list[str]]:
        sheets, warnings = [], []
        for page_spec in pages:
            image, page_warnings = self._render_page(page_spec)
            sheets.append(self._to_sheet(image, page_spec.page, paper))
            warnings.extend(page_warnings)

        buffer = io.BytesIO()
        sheets[0].save(
            buffer,
            format="PDF",
            resolution=_RENDER_DPI,
            save_all=True,
            append_images=sheets[1:],
        )
        return buffer.getvalue(), warnings

    def render_preview_png(self, pages: list[RenderPage]) -> tuple[bytes, list[str]]:
        """Only the first _PREVIEW_PAGE_LIMIT pages are drawn: a preview is
        an on-screen sanity check in the editor dialog, and a 30-position
        order would otherwise rasterise several full pages at 300 dpi to
        produce an image nobody scrolls to the bottom of. The omission is
        reported as a warning rather than passed off as the whole document."""
        warnings: list[str] = []
        shown = pages[:_PREVIEW_PAGE_LIMIT]
        if len(pages) > len(shown):
            warnings.append(f"docket has {len(pages)} pages, preview shows the first {len(shown)}")

        images = []
        for page_spec in shown:
            image, page_warnings = self._render_page(page_spec)
            images.append(image)
            warnings.extend(page_warnings)

        buffer = io.BytesIO()
        self._stack(images).save(buffer, format="PNG")
        return buffer.getvalue(), warnings

    def _stack(self, pages: list[Image.Image]) -> Image.Image:
        """Pages one above the other, separated by a grey rule, so a
        multi-page docket is still one preview image."""
        if len(pages) == 1:
            return pages[0]

        gap = _mm(_PREVIEW_GAP_MM)
        width = max(page.width for page in pages)
        height = sum(page.height for page in pages) + gap * (len(pages) - 1)
        canvas = Image.new("RGB", (width, height), "white")

        draw, y = ImageDraw.Draw(canvas), 0
        for index, page in enumerate(pages):
            canvas.paste(page, ((width - page.width) // 2, y))
            y += page.height
            if index < len(pages) - 1:
                rule_y = y + gap // 2
                draw.line([0, rule_y, width, rule_y], fill="grey", width=max(_mm(0.3), 1))
                y += gap
        return canvas

    def render_qr_png(self, payload: str, *, size_mm: float = 25.0) -> bytes:
        symbol = _qr_image(payload, _mm(size_mm))
        buffer = io.BytesIO()
        symbol.save(buffer, format="PNG")
        return buffer.getvalue()

    # ── Page rendering ───────────────────────────────────────────────

    def _render_page(self, spec: RenderPage) -> tuple[Image.Image, list[str]]:
        values, images = spec.values, spec.images
        page = Image.new("RGB", (_mm(spec.page.width_mm), _mm(spec.page.height_mm)), "white")
        draw = ImageDraw.Draw(page)
        warnings: list[str] = []

        for block in spec.blocks:
            if isinstance(block, RectBlock):
                self._draw_rect(draw, block)
            elif isinstance(block, LineBlock):
                self._draw_line(draw, block)
            elif isinstance(block, TextBlock):
                self._draw_text(draw, block, values)
            elif isinstance(block, QrBlock):
                self._draw_qr(page, block, values, warnings)
            elif isinstance(block, ImageBlock):
                self._draw_image(page, draw, block, images)

        return page, warnings

    def _draw_rect(self, draw: ImageDraw.ImageDraw, block: RectBlock) -> None:
        draw.rectangle(
            [_mm(block.x), _mm(block.y), _mm(block.x + block.w), _mm(block.y + block.h)],
            outline="black",
            width=max(_mm(block.stroke_mm), 1),
        )

    def _draw_line(self, draw: ImageDraw.ImageDraw, block: LineBlock) -> None:
        draw.line(
            [_mm(block.x), _mm(block.y), _mm(block.x2), _mm(block.y2)],
            fill="black",
            width=max(_mm(block.stroke_mm), 1),
        )

    def _draw_text(
        self, draw: ImageDraw.ImageDraw, block: TextBlock, values: dict[str, str]
    ) -> None:
        text = block.text if block.field is None else values.get(block.field, "")
        font = _font(block.bold, block.size_mm)
        x, y = _mm(block.x), _mm(block.y)

        if block.max_width_mm:
            lines = _fit_lines(draw, text or "", font, _mm(block.max_width_mm), block.max_lines)
            line_height = _mm(block.size_mm * 1.3)
            for i, line in enumerate(lines):
                self._draw_one_line(
                    draw, line, font, x, y + i * line_height, block, _mm(block.max_width_mm)
                )
            return

        self._draw_one_line(draw, text or "", font, x, y, block, None)

    def _draw_one_line(
        self,
        draw: ImageDraw.ImageDraw,
        line: str,
        font: ImageFont.FreeTypeFont,
        x: int,
        y: int,
        block: TextBlock,
        width_px: int | None,
    ) -> None:
        if width_px:
            x = x + _align_offset(block.align, width_px - draw.textlength(line, font=font))
        draw.text((x, y), line, font=font, fill="black")

    def _draw_qr(
        self, page: Image.Image, block: QrBlock, values: dict[str, str], warnings: list[str]
    ) -> None:
        payload = values.get(block.field, "")
        if not payload:
            warnings.append(f"qr block '{block.field}' has no value to encode, skipped")
            return
        symbol = _qr_image(payload, _mm(block.size_mm))
        page.paste(symbol, (_mm(block.x), _mm(block.y)))

    def _draw_image(
        self,
        page: Image.Image,
        draw: ImageDraw.ImageDraw,
        block: ImageBlock,
        images: dict[str, bytes | None],
    ) -> None:
        raw = images.get(block.field)
        left, top = _mm(block.x), _mm(block.y)
        width, height = _mm(block.w), _mm(block.h)

        if raw is None:
            if block.fallback_text:
                font = _font(False, 3.0)
                text_width = draw.textlength(block.fallback_text, font=font)
                draw.text(
                    (left + _align_offset(block.align, width - text_width), top + height / 2),
                    block.fallback_text,
                    font=font,
                    fill="black",
                )
            return

        try:
            image = Image.open(io.BytesIO(raw))
            image.load()
        except Exception:  # a corrupt/unreadable file must not kill the print
            log.warning(
                "Docket image for field %r is unreadable; leaving its block empty.",
                block.field,
                exc_info=True,
            )
            return

        flattened = _flatten(image)
        inner = (max(width - _mm(2), 1), max(height - _mm(2), 1))
        flattened.thumbnail(inner, Image.Resampling.LANCZOS)
        page.paste(
            flattened,
            (
                left + _align_offset(block.align, width - flattened.width),
                top + (height - flattened.height) // 2,
            ),
        )

    # ── Sheet placement ──────────────────────────────────────────────

    def _to_sheet(self, page: Image.Image, page_mm: DocketPage, paper: str) -> Image.Image:
        if paper == "a4_aligned":
            return self._to_a4_aligned_sheet(page, page_mm)

        sheet_mm = _SHEET_SIZES_MM.get(paper)
        if not sheet_mm or sheet_mm[0] < page_mm.width_mm or sheet_mm[1] < page_mm.height_mm:
            return page  # requested sheet unknown or not larger, print the page 1:1

        sheet = Image.new("RGB", (_mm(sheet_mm[0]), _mm(sheet_mm[1])), "white")
        origin = ((sheet.width - page.width) // 2, (sheet.height - page.height) // 2)
        sheet.paste(page, origin)
        self._draw_cut_marks(sheet, origin, page.size)
        return sheet

    def _to_a4_aligned_sheet(self, page: Image.Image, page_mm: DocketPage) -> Image.Image:
        """A4 in landscape (297x210mm): an A4 sheet is exactly two A5
        sheets side by side, so the page sits flush against the left half
        with a single cut line down the sheet's midpoint. One straight cut
        turns the printed sheet into two A5-portrait halves: the docket,
        already finished with no further trimming, and a blank twin.
        Falls back to the page unchanged (1:1) if it does not fit in an A5
        half to begin with."""
        sheet_w_mm, sheet_h_mm = _A4_LANDSCAPE_MM
        if page_mm.width_mm > sheet_w_mm / 2 or page_mm.height_mm > sheet_h_mm:
            return page

        sheet = Image.new("RGB", (_mm(sheet_w_mm), _mm(sheet_h_mm)), "white")
        origin = (0, (sheet.height - page.height) // 2)
        sheet.paste(page, origin)

        draw = ImageDraw.Draw(sheet)
        mid_x = sheet.width // 2
        draw.line([mid_x, 0, mid_x, sheet.height], fill="black", width=max(_mm(0.2), 1))
        return sheet

    def _draw_cut_marks(
        self, sheet: Image.Image, origin: tuple[int, int], size: tuple[int, int]
    ) -> None:
        draw = ImageDraw.Draw(sheet)
        length, x0, y0 = _mm(5), origin[0], origin[1]
        x1, y1 = x0 + size[0], y0 + size[1]

        for x in (x0, x1):
            for y in (y0, y1):
                draw.line([x - length, y, x + length, y], fill="black", width=_mm(0.2))
                draw.line([x, y - length, x, y + length], fill="black", width=_mm(0.2))
