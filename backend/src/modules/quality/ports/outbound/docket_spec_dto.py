"""
The declarative block-list format a docket (PDF document) template's
`source` column holds as JSON: the docket's answer to a label's ZPL text.
Coordinates are millimetres, not pixels, so a spec is resolution-independent
(see docket_renderer.py, which rasterises at its own DPI).

Lives in ports, not domain: the import-linter contract forbids src.domain
from importing pydantic. Not in application either, even though that is
where it is parsed and validated (see application/services/docket_spec.py):
IDocketRenderer's methods take a DocketSpec directly, and the layered
architecture contract (adapters -> application -> ports -> domain) forbids
a port importing an application-layer module, so the shared vocabulary
between the port and its caller has to sit at the ports layer or below.
Nothing here is printer-specific either way: these blocks describe a
page of content, never a device.
"""

from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Annotated
from typing import Literal

from pydantic import BaseModel
from pydantic import Field
from pydantic import model_validator

# Which pages of a paginated docket a block is drawn on. "all" is the
# default and the only behaviour that existed before dockets could span
# more than one page, so every pre-table spec keeps rendering unchanged.
PageScope = Literal["all", "first", "continuation"]


class PageScoped(BaseModel):
    """Mixin, not a block type: the one field every block shares."""

    pages: PageScope = "all"


class TextBlock(PageScoped):
    type: Literal["text"] = "text"
    x: float
    y: float
    size_mm: float
    bold: bool = False
    text: str | None = None  # literal content, mutually exclusive with `field`
    field: str | None = None  # a field_map key, resolved to a string value
    max_width_mm: float | None = None  # enables word-wrap when set
    max_lines: int = 1
    align: Literal["left", "center", "right"] = "left"  # non-left needs max_width_mm

    @model_validator(mode="after")
    def _exactly_one_content_source(self) -> "TextBlock":
        if (self.text is None) == (self.field is None):
            raise ValueError("A text block needs exactly one of `text` or `field`.")
        return self


class ImageBlock(PageScoped):
    type: Literal["image"] = "image"
    x: float
    y: float
    w: float
    h: float
    field: str  # an image-valued source (e.g. "@part_image", "@company_logo")
    fallback_text: str | None = None  # shown when the image cannot be resolved
    # Where the scaled image sits inside the box horizontally; it is always
    # centred vertically. "center" keeps the behaviour every pre-align
    # template was drawn against.
    align: Literal["left", "center", "right"] = "center"


class QrBlock(PageScoped):
    type: Literal["qr"] = "qr"
    x: float
    y: float
    size_mm: float
    field: str  # a field_map key resolved to the string payload to encode


class RectBlock(PageScoped):
    type: Literal["rect"] = "rect"
    x: float
    y: float
    w: float
    h: float
    stroke_mm: float = 0.3


class LineBlock(PageScoped):
    type: Literal["line"] = "line"
    x: float
    y: float
    x2: float
    y2: float
    stroke_mm: float = 0.3


DocketBlock = Annotated[
    TextBlock | ImageBlock | QrBlock | RectBlock | LineBlock, Field(discriminator="type")
]


class DocketColumn(BaseModel):
    """One column of a repeating positions table. `fields` is a STACK: the
    first entry is the cell's primary line, the rest are smaller secondary
    lines beneath it (article over part number over dimension). A field
    that resolves to nothing leaves its line blank rather than reflowing
    the ones below, so every row keeps the same height and the capacity
    arithmetic in docket_pagination stays exact."""

    header: str
    fields: list[str] = Field(min_length=1)
    width_mm: float = Field(gt=0)
    kind: Literal["text", "image"] = "text"
    align: Literal["left", "center", "right"] = "left"

    @model_validator(mode="after")
    def _image_columns_hold_one_field(self) -> "DocketColumn":
        if self.kind == "image" and len(self.fields) != 1:
            raise ValueError("An image column takes exactly one field.")
        return self


class DocketTable(BaseModel):
    """The repeating positions table. Deliberately declarative: columns,
    widths and band geometry only, never individual blocks. Cell layout is
    code (docket_pagination.py) so an admin reordering columns in the
    editor cannot misalign a header from its column or lose a separator.

    There is deliberately no "which list do I repeat over" setting: that is
    fixed by the classifier (ClassifierSpec.row_source), because an admin
    cannot meaningfully point an order docket at anything but the order's
    own positions. One source of truth, in code."""

    x_mm: float = 14.0  # left edge of the first column
    row_height_mm: float = Field(gt=0)
    first_page_top_mm: float  # top of the band on page 1
    next_page_top_mm: float  # top of the band on continuation pages
    bottom_mm: float  # last usable y; a row may not cross it
    header_height_mm: float = 8.0
    separator_stroke_mm: float | None = 0.15
    columns: list[DocketColumn] = Field(min_length=1)

    @model_validator(mode="after")
    def _band_fits_at_least_one_row(self) -> "DocketTable":
        for name, top in (
            ("first_page_top_mm", self.first_page_top_mm),
            ("next_page_top_mm", self.next_page_top_mm),
        ):
            usable = self.bottom_mm - top - self.header_height_mm
            if usable < self.row_height_mm:
                raise ValueError(
                    f"No room for a single row below {name}: "
                    f"{usable:g}mm usable, row_height_mm is {self.row_height_mm:g}."
                )
        return self


class DocketPage(BaseModel):
    width_mm: float
    height_mm: float


class DocketSpec(BaseModel):
    page: DocketPage
    blocks: list[DocketBlock] = Field(default_factory=list)
    # None = a plain one-page docket, the only shape that existed before
    # orders needed a positions list.
    table: DocketTable | None = None


@dataclass(frozen=True)
class RenderPage:
    """One fully-resolved page handed to the renderer: blocks with every
    coordinate already absolute and every repeat already expanded. The
    renderer never sees a DocketTable: pagination happens upstream in
    docket_pagination.py, so drawing stays the adapter's only job."""

    page: DocketPage
    blocks: list[DocketBlock]
    values: dict[str, str] = dataclass_field(default_factory=dict)
    images: dict[str, bytes | None] = dataclass_field(default_factory=dict)
