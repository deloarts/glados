"""
The parts of a PLC environment (see plc_environment.py) that say how tags
are named and exported: a prefix per signal type, the character
conversion, the export columns, and the settings of Siemens TIA Portal that
a new environment starts from.
"""

from dataclasses import dataclass
from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum

# The prefix keys: one per signal type, and one per type that can be a
# safety signal, picked when the signal carries the safety flag.
PREFIX_KEYS: tuple[str, ...] = (
    "di",
    "do",
    "ai",
    "ao",
    "bus",
    "safety_di",
    "safety_do",
    "safety_ai",
    "safety_ao",
)


@dataclass(frozen=True)
class CharConversion:
    """Replaces `source` with `target` when a tag is built; an empty target
    removes the source."""

    source: str
    target: str


@unique
class ExportColumnSource(StrValueEnum):
    TAG_NAME = "tag_name"
    TAG_TABLE = "tag_table"
    DATA_TYPE = "data_type"
    ADDRESS = "address"
    COMMENT = "comment"
    DEVICE_NAME = "device_name"
    DEVICE_NAME_ASCII = "device_name_ascii"
    SIGNAL_TYPE = "signal_type"
    SAFETY = "safety"
    # The same text in every row, such as "True" for TIA's HMI columns.
    CONSTANT = "constant"


@dataclass(frozen=True)
class ExportColumn:
    header: str
    source: ExportColumnSource
    # The text of a CONSTANT column; None for the others.
    value: str | None = None


TIA_NAME = "Siemens TIA Portal"
TIA_PREFIXES: dict[str, str] = {
    "di": "di_",
    "do": "dq_",
    "ai": "ai_",
    "ao": "aq_",
    "bus": "",
    "safety_di": "fdi_",
    "safety_do": "fdq_",
    "safety_ai": "fai_",
    "safety_ao": "faq_",
}
TIA_MAX_TAG_LENGTH = 128
TIA_CONVERSIONS: tuple[CharConversion, ...] = (
    CharConversion("ä", "ae"),
    CharConversion("ö", "oe"),
    CharConversion("ü", "ue"),
    CharConversion("Ä", "Ae"),
    CharConversion("Ö", "Oe"),
    CharConversion("Ü", "Ue"),
    CharConversion("ß", "ss"),
    *(CharConversion(c, "_") for c in " -.+,/\\()&#';:%"),
)
TIA_TAG_TABLE = "Standard-Variablentabelle"
TIA_EXPORT_SHEET = "PLC Tags"
TIA_EXPORT_COLUMNS: tuple[ExportColumn, ...] = (
    ExportColumn("Name", ExportColumnSource.TAG_NAME),
    ExportColumn("Path", ExportColumnSource.TAG_TABLE),
    ExportColumn("Data Type", ExportColumnSource.DATA_TYPE),
    ExportColumn("Logical Address", ExportColumnSource.ADDRESS),
    ExportColumn("Comment", ExportColumnSource.COMMENT),
    ExportColumn("Hmi Visible", ExportColumnSource.CONSTANT, "True"),
    ExportColumn("Hmi Accessible", ExportColumnSource.CONSTANT, "True"),
    ExportColumn("Hmi Writeable", ExportColumnSource.CONSTANT, "True"),
)
