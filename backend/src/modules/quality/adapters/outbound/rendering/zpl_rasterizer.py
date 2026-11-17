"""
Pillow-only interpreter for the ZPL subset the templates actually use:
^XA ^XZ ^CI ^PW ^LL ^LH ^FO ^FS ^FX ^GB ^A0N ^FB ^FD ^FH ^BQN. Anything else
is reported as a warning rather than silently dropped or guessed at.

Tokenizing relies on a property render_zpl() guarantees: a rendered
template never contains a literal ^ or ~ inside field data (see
zpl_template.py's zpl_escape), so splitting the whole string on ^/~ is
safe and correctly isolates each command's raw parameters, including a
^FD field's data up to the next command.

The preview is approximate: ^A0 is Zebra's own scalable sans, so glyph
metrics differ from the vendored Liberation Sans substitute. A test print
stays the source of truth for exact sizing.
"""

import io
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import segno
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

_FONT_DIR = Path(__file__).parent / "fonts"
_FONT_REGULAR = _FONT_DIR / "LiberationSans-Regular.ttf"
_FONT_BOLD = _FONT_DIR / "LiberationSans-Bold.ttf"

_FH_ESCAPE_RE = re.compile(r"_([0-9A-Fa-f]{2})")

_KNOWN_COMMANDS = (
    "XA",
    "XZ",
    "CI",
    "PW",
    "LL",
    "LH",
    "FO",
    "FS",
    "FX",
    "GB",
    "FB",
    "FD",
    "FH",
    "BQ",
    "MN",
    "MM",
    "PO",
    "PR",
)
# Recognised but deliberately not rendered: printer-configuration commands
# (media tracking, print mode, orientation, print rate) with no visual
# effect on the label itself. Listing them here means a template that
# uses them (nearly all real Zebra templates do) doesn't produce spurious
# "unsupported command" warnings for something that was never going to
# draw anything anyway.
_NO_VISUAL_EFFECT = ("XA", "CI", "MN", "MM", "PO", "PR")


def _decode_fh(text: str) -> str:
    """Reverse zpl_escape's _XX hex codes back to literal bytes, matching
    ^FH's default `_` indicator."""
    return _FH_ESCAPE_RE.sub(lambda m: chr(int(m.group(1), 16)), text)


def _split_commands(zpl: str) -> list[str]:
    """Every ^/~-prefixed command as one token (code + raw params),
    dropping whatever precedes the first command marker."""
    return re.split(r"[\^~]", zpl)[1:]


@dataclass
class _FieldState:
    x: int = 0
    y: int = 0
    font_height: int = 20
    font_width: int = 20
    bold: bool = False
    block_width: int | None = None
    block_max_lines: int = 1
    block_justify: str = "L"
    is_qr: bool = False
    qr_magnification: int = 3
    hex_mode: bool = False


class _RasterizerState:
    """Mutable state threaded through one rasterize() call: the page built
    so far, the current field/cursor, and warnings collected along the way.
    A command handler reads and mutates this in place rather than closing
    over rasterize()'s local variables."""

    def __init__(self, scale: int) -> None:
        self.scale = scale
        self.width_dots = 400 * scale
        self.height_dots = 200 * scale
        self.origin_x = 0
        self.origin_y = 0
        self.field = _FieldState()
        self.page: Image.Image | None = None
        self.draw: ImageDraw.ImageDraw | None = None
        self.warnings: list[str] = []

    def ensure_page(self) -> tuple[Image.Image, ImageDraw.ImageDraw]:
        if self.page is None:
            self.page = Image.new("RGB", (self.width_dots, self.height_dots), "white")
            self.draw = ImageDraw.Draw(self.page)
        assert self.draw is not None
        return self.page, self.draw


class ZplRasterizer:
    """Implements IZplRasterizer."""

    def rasterize(
        self, zpl: str, *, design_dpi: int, format_convert_factor: int
    ) -> tuple[bytes, list[str]]:
        state = _RasterizerState(max(format_convert_factor, 1))
        handlers = self._command_handlers()

        for token in _split_commands(zpl):
            if not token:
                continue
            parsed = self._identify_command(token)
            if parsed is None:
                state.warnings.append(f"unsupported command: ^{token[:2]}")
                continue
            code, params = parsed
            if code == "XZ":
                break
            handlers[code](state, params)

        if state.page is None:
            state.page = Image.new("RGB", (state.width_dots, state.height_dots), "white")

        buffer = io.BytesIO()
        state.page.save(buffer, format="PNG")
        return buffer.getvalue(), state.warnings

    @staticmethod
    def _identify_command(token: str) -> tuple[str, str] | None:
        """The command code a token starts with, and its raw remaining
        params, or None when the token matches none of them. ^A0N etc.
        aren't in _KNOWN_COMMANDS since the font/orientation letter that
        follows varies, so it is matched by its leading "A" instead."""
        code = next((c for c in _KNOWN_COMMANDS if token.startswith(c)), None)
        if code is not None:
            return code, token[len(code) :]
        if token[0] == "A":
            return "A", token[1:]
        return None

    def _command_handlers(self) -> dict[str, Callable[[_RasterizerState, str], None]]:
        """XZ is deliberately absent: rasterize() ends the token loop on it
        rather than dispatching, since a handler has no way to break that
        loop."""
        handlers: dict[str, Callable[[_RasterizerState, str], None]] = dict.fromkeys(
            _NO_VISUAL_EFFECT, self._cmd_noop
        )
        handlers.update(
            PW=self._cmd_pw,
            LL=self._cmd_ll,
            LH=self._cmd_lh,
            FO=self._cmd_fo,
            A=self._cmd_a,
            FB=self._cmd_fb,
            BQ=self._cmd_bq,
            GB=self._cmd_gb,
            FH=self._cmd_fh,
            FX=self._cmd_fx,
            FD=self._cmd_fd,
            FS=self._cmd_fs,
        )
        return handlers

    def _cmd_noop(self, state: _RasterizerState, params: str) -> None:
        """Printer-configuration commands with no visual effect, see
        _NO_VISUAL_EFFECT."""

    def _cmd_pw(self, state: _RasterizerState, params: str) -> None:
        state.width_dots = self._int(params, state.width_dots // state.scale) * state.scale

    def _cmd_ll(self, state: _RasterizerState, params: str) -> None:
        state.height_dots = self._int(params, state.height_dots // state.scale) * state.scale

    def _cmd_lh(self, state: _RasterizerState, params: str) -> None:
        x, y = self._xy(params)
        state.origin_x, state.origin_y = x * state.scale, y * state.scale

    def _cmd_fo(self, state: _RasterizerState, params: str) -> None:
        x, y = self._xy(params)
        state.field.x, state.field.y = x * state.scale, y * state.scale

    def _cmd_a(self, state: _RasterizerState, params: str) -> None:
        field = state.field
        field.bold = params[:1] not in ("0", "")
        parts = params[2:].split(",")
        field.font_height = self._int(parts[0] if parts else "", 20) * state.scale
        field.font_width = (
            self._int(parts[1], field.font_height) * state.scale
            if len(parts) > 1
            else field.font_height
        )

    def _cmd_fb(self, state: _RasterizerState, params: str) -> None:
        field = state.field
        parts = params.split(",")
        field.block_width = self._int(parts[0], 0) * state.scale if parts and parts[0] else None
        field.block_max_lines = self._int(parts[1], 1) if len(parts) > 1 else 1
        field.block_justify = parts[3] if len(parts) > 3 and parts[3] else "L"

    def _cmd_bq(self, state: _RasterizerState, params: str) -> None:
        parts = params.split(",")
        state.field.is_qr = True
        state.field.qr_magnification = self._int(parts[1], 3) if len(parts) > 1 else 3

    def _cmd_gb(self, state: _RasterizerState, params: str) -> None:
        _, draw = state.ensure_page()
        self._draw_box(draw, state.field, params, state.origin_x, state.origin_y, state.scale)

    def _cmd_fh(self, state: _RasterizerState, params: str) -> None:
        state.field.hex_mode = True

    def _cmd_fx(self, state: _RasterizerState, params: str) -> None:
        """Comment; its text is discarded, nothing to render."""

    def _cmd_fd(self, state: _RasterizerState, params: str) -> None:
        page, draw = state.ensure_page()
        data = _decode_fh(params) if state.field.hex_mode else params
        self._draw_field(page, draw, state.field, data, state.origin_x, state.origin_y)
        state.field = _FieldState()

    def _cmd_fs(self, state: _RasterizerState, params: str) -> None:
        pass

    @staticmethod
    def _int(text: str, default: int) -> int:
        text = text.strip()
        return int(text) if text.lstrip("-").isdigit() else default

    @staticmethod
    def _xy(params: str) -> tuple[int, int]:
        parts = params.split(",")
        x = ZplRasterizer._int(parts[0], 0) if parts else 0
        y = ZplRasterizer._int(parts[1], 0) if len(parts) > 1 else 0
        return x, y

    def _draw_box(
        self,
        draw: ImageDraw.ImageDraw,
        field: _FieldState,
        params: str,
        origin_x: int,
        origin_y: int,
        scale: int,
    ) -> None:
        parts = params.split(",")
        w = self._int(parts[0], 1) * scale if parts else scale
        h = self._int(parts[1], 1) * scale if len(parts) > 1 else scale
        thickness = self._int(parts[2], 1) * scale if len(parts) > 2 else scale
        x, y = origin_x + field.x, origin_y + field.y
        draw.rectangle([x, y, x + w, y + h], outline="black", width=max(thickness, 1))

    def _font(self, field: _FieldState) -> ImageFont.FreeTypeFont:
        path = _FONT_BOLD if field.bold else _FONT_REGULAR
        size = max(field.font_height, 1)
        return ImageFont.truetype(str(path), size)

    def _draw_field(
        self,
        page: Image.Image,
        draw: ImageDraw.ImageDraw,
        field: _FieldState,
        data: str,
        origin_x: int,
        origin_y: int,
    ) -> None:
        x, y = origin_x + field.x, origin_y + field.y

        if field.is_qr:
            self._draw_qr(page, data, x, y, field.qr_magnification)
            return

        font = self._font(field)
        lines = self._wrap(draw, data, font, field.block_width, field.block_max_lines)
        line_height = int(field.font_height * 1.2)
        for i, line in enumerate(lines):
            draw.text((x, y + i * line_height), line, font=font, fill="black")

    def _wrap(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.FreeTypeFont,
        max_width: int | None,
        max_lines: int,
    ) -> list[str]:
        if not max_width or max_width <= 0:
            return [text]

        words, lines, current = text.split(), [], ""
        for word in words:
            probe = f"{current} {word}".strip()
            if draw.textlength(probe, font=font) <= max_width or not current:
                current = probe
                continue
            lines.append(current)
            current = word
            if len(lines) == max_lines:
                break
        if current and len(lines) < max_lines:
            lines.append(current)
        return lines or [""]

    def _draw_qr(self, page: Image.Image, data: str, x: int, y: int, magnification: int) -> None:
        # ZPL ^BQ field data conventionally carries a 2-char mode/error
        # prefix before a comma (e.g. "QA,<payload>" in the seeded
        # templates), stripped here since it is not part of the payload.
        payload = data.split(",", 1)[1] if "," in data[:3] else data
        qr = segno.make(payload, error="q")
        buffer = io.BytesIO()
        qr.save(buffer, kind="png", scale=max(magnification, 1) * 3, border=0)
        symbol = Image.open(buffer).convert("RGB")
        page.paste(symbol, (x, y))
