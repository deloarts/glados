"""
Abstract docket-to-document renderer. It only produces bytes, a PDF or a
preview PNG, which the caller sends to any "ipp_document" printer or hands
back as a download, so no implementation may depend on a particular device.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.quality.ports.outbound.docket_spec_dto import RenderPage


@runtime_checkable
class IDocketRenderer(Protocol):
    def render_pdf(self, pages: list[RenderPage], *, paper: str) -> tuple[bytes, list[str]]:
        """Renders already paginated pages (docket_pagination.py) into one PDF,
        each sized to `paper`: "a4" centres a smaller page with cut marks and
        "a5" keeps it 1:1. Returns (pdf_bytes, warnings)."""
        ...

    def render_preview_png(self, pages: list[RenderPage]) -> tuple[bytes, list[str]]:
        """Renders the pages without sheet centring as one PNG for the
        preview.png endpoint, stacked vertically so one <img> shows them all.
        Returns (png_bytes, warnings)."""
        ...

    def render_qr_png(self, payload: str, *, size_mm: float = 25.0) -> bytes:
        """A standalone QR code PNG for the "@qr_image" computed source, so a
        template can place a QR code with image-block letterboxing instead of
        the fixed square of the "qr" block."""
        ...
