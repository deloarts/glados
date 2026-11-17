"""
Sends a built-in self-test job, no template required, used to verify a
printer is reachable and correctly configured before wiring any real
template to it.
"""

import io

from PIL import Image
from PIL import ImageDraw

from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.domain.errors import PrinterKindMismatchError
from src.modules.quality.domain.errors import PrinterNotFoundError
from src.modules.quality.domain.services.printer_rules import PrinterRules
from src.modules.quality.ports.outbound.printer_gateway_port import IPrinterGateway
from src.modules.quality.ports.outbound.repositories.printer_repository import IPrinterRepository
from src.shared_kernel.domain.services.clock import now_utc

_ZPL_SELF_TEST = (
    "^XA^CI28^PW413^LL189^LH0,0"
    "^FO6,6^GB401,177,2^FS"
    "^FO15,20^A0N,26,26^FDGLADOS TEST PRINT^FS"
    "^FO15,60^A0N,18,18^FD{stamp}^FS"
    "^XZ"
)


def _self_test_pdf(stamp: str) -> bytes:
    """A minimal single-page PDF, built with Pillow so no new dependency is needed."""
    page = Image.new("RGB", (826, 1169), "white")  # A4 @ 100dpi
    draw = ImageDraw.Draw(page)
    draw.text((40, 40), "GLADOS TEST PRINT", fill="black")
    draw.text((40, 70), stamp, fill="black")
    buffer = io.BytesIO()
    page.save(buffer, format="PDF")
    return buffer.getvalue()


class TestPrintPrinter:
    def __init__(
        self,
        printer_repo: IPrinterRepository,
        *,
        gateway: IPrinterGateway,
        uow: IUnitOfWork | None = None,
    ) -> None:
        self._printers = printer_repo
        self._gateway = gateway
        self._uow = uow

    async def execute(self, actor: User, printer_id: int) -> None:
        PrinterRules.assert_can_print(actor)

        printer = found_or_raise(
            await self._printers.get_by_id(printer_id),
            PrinterNotFoundError,
            f"Printer #{printer_id} not found.",
        )

        stamp = f"{actor.username} · {now_utc():%Y-%m-%d %H:%M UTC}"
        # Nothing is written here; free the connection while the printer answers.
        if self._uow is not None:
            await self._uow.commit()

        if printer.kind == "zpl_label":
            payload = _ZPL_SELF_TEST.format(stamp=stamp).encode("utf-8")
            await self._gateway.send(printer, payload, "application/x-zpl", copies=1)
        elif printer.kind == "ipp_document":
            await self._gateway.send(printer, _self_test_pdf(stamp), "application/pdf", copies=1)
        else:
            raise PrinterKindMismatchError(f"Unknown printer kind {printer.kind.value!r}.")

        log.info(f"Sent a test print to printer {printer.name!r}.")
