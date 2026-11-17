"""
Finds the record an uploaded document belongs to and checks that the actor
may see it, so nobody can print a report of a record that is hidden from
them, such as another user's personal calculation or checklist. Each UploadedPrintDocument
belongs to one root type; a new kind of report adds an enum value, a branch
here and the repository it needs.
"""

from dataclasses import dataclass
from typing import assert_never
from uuid import UUID

from src.modules.fulfillment.domain.errors import LotNotFoundError
from src.modules.fulfillment.ports.outbound.fulfillment_queries import IProductionLotQueries
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.quality.domain.errors import CalculationNotFoundError
from src.modules.quality.domain.errors import ChecklistNotFoundError
from src.modules.quality.domain.services.calculation_rules import CalculationRules
from src.modules.quality.domain.services.checklist_rules import ChecklistRules
from src.modules.quality.domain.value_objects.print_classifier import PrintRootType
from src.modules.quality.domain.value_objects.print_classifier import UploadedPrintDocument
from src.modules.quality.ports.outbound.repositories.calculation_repository import (
    ICalculationRepository,
)
from src.modules.quality.ports.outbound.repositories.checklist_repository import (
    IChecklistRepository,
)
from src.modules.workspace.domain.errors import MeetingNotFoundError
from src.modules.workspace.ports.outbound.workspace_queries import IMeetingQueries


@dataclass(frozen=True)
class UploadedDocumentRoot:
    """The record a report shows, as a print job and the export journal name
    it. A record without revisions has an empty revision."""

    root_type: PrintRootType
    root_id: int
    lineage: UUID
    revision: str


class UploadedDocumentRoots:
    def __init__(
        self,
        calculation_repo: ICalculationRepository,
        checklist_repo: IChecklistRepository,
        lot_repo: IProductionLotQueries | None = None,
        meeting_repo: IMeetingQueries | None = None,
    ) -> None:
        self._calculations = calculation_repo
        self._checklists = checklist_repo
        self._lots = lot_repo
        self._meetings = meeting_repo

    async def resolve(
        self, actor: User, document: UploadedPrintDocument, root_public_id: UUID
    ) -> tuple[PrintRootType, int]:
        """Return the root type and id the print job records. Raises the
        record's not-found error when it is missing or hidden from the actor."""
        root = await self.describe(actor, document, root_public_id)
        return root.root_type, root.root_id

    async def describe(
        self, actor: User, document: UploadedPrintDocument, root_public_id: UUID
    ) -> UploadedDocumentRoot:
        """The record with its revision, checked like resolve()."""
        match document:
            case UploadedPrintDocument.CALCULATION_REPORT:
                calculation = found_or_raise(
                    await self._calculations.get_by_public_id(root_public_id),
                    CalculationNotFoundError,
                    f"Calculation {root_public_id} not found.",
                )
                CalculationRules.assert_can_view(actor, calculation)
                return UploadedDocumentRoot(
                    PrintRootType.CALCULATION,
                    calculation.id,
                    calculation.lineage,
                    calculation.revision,
                )
            case UploadedPrintDocument.CHECKLIST_REPORT:
                checklist = found_or_raise(
                    await self._checklists.get_by_public_id(root_public_id),
                    ChecklistNotFoundError,
                    f"Checklist {root_public_id} not found.",
                )
                ChecklistRules.assert_can_view(actor, checklist)
                return UploadedDocumentRoot(
                    PrintRootType.CHECKLIST, checklist.id, checklist.lineage, checklist.revision
                )
            case UploadedPrintDocument.INSPECTION_REPORT:
                # Every logged-in user may see a lot. A lot has no revisions;
                # it is its own lineage, and the report shows its state on
                # the day it is exported.
                lot = found_or_raise(
                    await self._lots.get_by_public_id(root_public_id) if self._lots else None,
                    LotNotFoundError,
                    f"Lot {root_public_id} not found.",
                )
                return UploadedDocumentRoot(PrintRootType.PRODUCTION_LOT, lot.id, lot.public_id, "")
            case UploadedPrintDocument.MEETING_NOTES:
                # Every signed-in user sees every meeting that is not
                # deleted. A meeting is its own lineage; the revision of
                # each export is the issue its PDF carried, which the
                # meeting names when it journals the export.
                meeting = (
                    await self._meetings.get_by_public_id(root_public_id)
                    if self._meetings
                    else None
                )
                if meeting is None or meeting.deleted:
                    raise MeetingNotFoundError(f"Meeting {root_public_id} not found.")
                return UploadedDocumentRoot(
                    PrintRootType.MEETING, meeting.id, meeting.public_id, ""
                )
            case _:
                assert_never(document)
