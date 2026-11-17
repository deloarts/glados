"""
Repository interface for the export journal. Append only, except that
anonymising a person blanks their address among the recipients.
"""

from typing import Protocol
from typing import runtime_checkable
from uuid import UUID

from src.modules.quality.domain.entities.report_journal_entry import ReportJournalEntry


@runtime_checkable
class IReportJournalRepository(Protocol):
    async def save(self, item: ReportJournalEntry) -> ReportJournalEntry: ...

    async def list_for_lineage(self, root_type: str, lineage: UUID) -> list[ReportJournalEntry]:
        """Every entry of any revision of one document, newest first."""
        ...

    async def count_for_lineages(self, root_type: str, lineages: list[UUID]) -> int:
        """How many entries name any revision of these documents."""
        ...

    async def set_recipients_blank(self, entry_ids: list[int], addresses: set[str]) -> None:
        """Replaces the addresses, given in lower case and compared without
        case, among the recipients of the entries with an empty one."""
        ...
