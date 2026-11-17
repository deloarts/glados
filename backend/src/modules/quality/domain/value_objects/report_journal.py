"""How a PDF report left Glados, as the export journal records it."""

from enum import Enum


class ReportJournalAction(str, Enum):
    DOWNLOAD = "download"
    PRINT = "print"
    # Sent as the attachment of a mail, to the recipients the entry names.
    MAIL = "mail"
