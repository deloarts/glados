"""
Abstract ZPL-to-image renderer, for print previews. The application layer
calls this, never Pillow directly, so it never has to import it.
"""

from typing import Protocol
from typing import runtime_checkable


@runtime_checkable
class IZplRasterizer(Protocol):
    def rasterize(
        self, zpl: str, *, design_dpi: int, format_convert_factor: int
    ) -> tuple[bytes, list[str]]:
        """Renders already substituted ZPL to a PNG at design_dpi times
        format_convert_factor, matching what the printer does (see
        Printer.format_convert_factor) rather than the literal ZPL size.

        Returns (png_bytes, warnings), where the warnings name each command
        the rasterizer does not understand and whose output it left out.
        """
        ...
