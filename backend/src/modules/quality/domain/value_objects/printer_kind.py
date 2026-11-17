"""
A printer cannot render both output kinds: a ZPL label printer speaks raw
ZPL over a socket, an IPP document printer speaks PDF over IPP. `kind`
decides which gateway handles a printer and which template output kinds it
accepts (see PrinterKindMismatchError, raised when they disagree).
"""

from enum import Enum
from enum import unique


@unique
class PrinterKind(str, Enum):
    ZPL_LABEL = "zpl_label"
    IPP_DOCUMENT = "ipp_document"


@unique
class PrinterTransport(str, Enum):
    RAW = "raw"
    IPP = "ipp"
