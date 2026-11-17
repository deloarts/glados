"""
Manual scrap tag printing scoped to a lot, for the lot context menu's
"Scrap tag" entry: unlike every other manual print action (POST /print,
root_type + root_id supplied by the caller), the frontend only knows the
lot, not which completion or delivery record actually carries the scrap
facts the scrap_tag classifier renders from (see PrintRootResolver). This
use case resolves that record itself, then delegates to PrintDocument
exactly like any other manual print.

A lot can be scrapped more than once, across its internal positions
(ProductionOrderCompletion rows) and its external/mixed ones (a "lost"
OrderItemDelivery row) alike, so every position is scanned and the most
recently recorded scrap record wins, the same "last scrap event" a
person clicking "print the scrap tag" on a lot expects.
"""

from src.modules.fulfillment.application.facade.lot_scrap_records import LotScrapRecords
from src.modules.platform.domain.entities.user import User
from src.modules.quality.application.dto.print_template_dto import PrintJobResult
from src.modules.quality.application.use_cases.print_document.print_document import PrintDocument
from src.modules.quality.domain.errors import ScrapTagRecordNotFoundError
from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier
from src.modules.quality.domain.value_objects.print_classifier import PrintJobTrigger
from src.modules.quality.domain.value_objects.print_classifier import PrintRootType


class PrintLotScrapTag:
    def __init__(
        self,
        scrap_records: LotScrapRecords,
        print_document: PrintDocument,
    ) -> None:
        self._scrap_records = scrap_records
        self._print = print_document

    async def execute(
        self,
        actor: User,
        lot_id: int,
        *,
        printer_id: int | None = None,
        copies: int | None = None,
    ) -> PrintJobResult:
        record = await self._scrap_records.latest(lot_id)
        if record is None:
            raise ScrapTagRecordNotFoundError(
                f"Lot #{lot_id} has no scrap or lost-at-receipt record to print a scrap tag from."
            )
        root_type, root_id = PrintRootType(record.kind.value), record.id

        return await self._print.execute(
            actor,
            PrintClassifier.SCRAP_TAG.value,
            root_type.value,
            root_id,
            printer_id=printer_id,
            copies=copies,
            trigger=PrintJobTrigger.MANUAL.value,
        )
