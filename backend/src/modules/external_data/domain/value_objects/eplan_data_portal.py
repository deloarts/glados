"""
What Glados reads from the EPLAN Data Portal, independent of its JSON:API
wire format. A part carries its texts per language (keys like de_DE,
en_US), its manufacturer's Data Portal code (SIE for Siemens), the EPLAN
product group path from the top group down, and the links Glados can use:
the manufacturer's support page, the part's own Data Portal page and the
512 px product picture.
"""

from dataclasses import dataclass
from dataclasses import field

EDP_LANGUAGES = ("de_DE", "en_US")


@dataclass(frozen=True)
class EdpNumberMatch:
    """The parts one searched number (order, type or EPLAN part number)
    matches. Empty when it matches none, several when it is ambiguous."""

    search: str
    part_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class EdpPart:
    part_id: int
    part_number: str
    order_number: str | None
    type_number: str | None
    designation: dict[str, str] = field(default_factory=dict)
    description: dict[str, str] = field(default_factory=dict)
    ean: str | None = None
    manufacturer_code: str | None = None
    manufacturer_name: str | None = None
    product_groups: tuple[str, ...] = ()
    support_url: str | None = None
    part_page_url: str | None = None
    picture_url: str | None = None

    def text_in(self, language: str) -> str | None:
        """The designation in `language`, else in the other supported
        language, else the description the same way."""
        order = [language, *[lang for lang in EDP_LANGUAGES if lang != language]]
        for texts in (self.designation, self.description):
            for lang in order:
                text = (texts.get(lang) or "").strip()
                if text:
                    return text
        return None

    @property
    def product_family_name(self) -> str | None:
        """The deepest EPLAN product group, the name a Glados product family
        is matched by."""
        return self.product_groups[-1] if self.product_groups else None


@dataclass(frozen=True)
class EdpConnectionInfo:
    """The answer of a connection test: whether the PAT was accepted."""

    authenticated: bool
