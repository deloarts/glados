"""
Raw-TCP/JetDirect gateway for Zebra-style ZPL printers: sends ZPL text
over port 9100 and queries printer status via ~HI/~HS.

Every socket step (connect, write, each read) is bounded by the printer's
own timeout_seconds through asyncio.wait_for. A timeout surfaces as
TimeoutError, which is an OSError and so maps to PrinterUnreachableError
like any other transport failure.
"""

import asyncio
import contextlib

from src.modules.quality.domain.entities.printer import Printer
from src.modules.quality.domain.errors import PrinterUnreachableError
from src.modules.quality.domain.services.zpl_status import HEAD_DPI_DEFAULT
from src.modules.quality.domain.services.zpl_status import describe_zpl_identity
from src.modules.quality.domain.services.zpl_status import describe_zpl_status
from src.modules.quality.domain.value_objects.print_classifier import PrintSides
from src.modules.quality.ports.outbound.printer_gateway_port import PrintDelivery


def describe_connection_error(exc: OSError) -> str:
    """The reason shown after the printer address. asyncio's timeouts carry
    no message, so they get a readable one instead of an empty string."""
    if str(exc):
        return str(exc)
    return "timed out" if isinstance(exc, TimeoutError) else type(exc).__name__


async def send_raw_tcp(printer: Printer, payload: bytes) -> None:
    """Write `payload` to the printer's raw port and close the connection.
    Shared by the ZPL gateway and the IPP gateway's raw-9100 fallback."""
    timeout = printer.timeout_seconds
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(printer.host, printer.port), timeout
        )
        try:
            writer.write(payload)
            await asyncio.wait_for(writer.drain(), timeout)
        finally:
            await _close(writer, timeout)
    except OSError as exc:
        raise PrinterUnreachableError(
            f"{printer.host}:{printer.port} - {describe_connection_error(exc)}"
        ) from exc


async def _close(writer: asyncio.StreamWriter, grace_seconds: float) -> None:
    writer.close()
    # The payload is already flushed; a printer that is slow to acknowledge
    # the close must not turn a delivered job into a failure.
    with contextlib.suppress(OSError):
        await asyncio.wait_for(writer.wait_closed(), grace_seconds)


_MAX_REPLY_BYTES = 16 * 1024


class ZplSocketPrinterGateway:
    """Implements IPrinterGateway for Printer.kind == "zpl_label"."""

    async def send(
        self,
        printer: Printer,
        payload: bytes,
        content_type: str,
        copies: int,
        *,
        sides: PrintSides = PrintSides.ONE_SIDED,
    ) -> PrintDelivery:
        # A label has one side; `sides` exists for document printers only.
        await send_raw_tcp(printer, payload * copies)
        return PrintDelivery()

    async def identify(self, printer: Printer) -> str:
        return describe_zpl_identity(await self._query(printer, "~HI"))

    async def status(self, printer: Printer) -> list[str]:
        return describe_zpl_status(
            await self._query(printer, "~HS"), head_dpi=printer.head_dpi or HEAD_DPI_DEFAULT
        )

    async def _query(self, printer: Printer, command: str) -> str:
        """Send a host query and read the printer's reply.

        ``~HI``/``~HS`` print nothing; the printer keeps the socket open
        after replying, so a read timeout is the expected end of the reply,
        not a failure.
        """
        timeout = printer.timeout_seconds
        chunks: list[bytes] = []
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(printer.host, printer.port), timeout
            )
            try:
                writer.write(command.encode("ascii"))
                await asyncio.wait_for(writer.drain(), timeout)
                received = 0
                try:
                    # A printer's reply is a few hundred bytes; the cap ends
                    # the read when the host is something that keeps talking.
                    while received < _MAX_REPLY_BYTES:
                        data = await asyncio.wait_for(reader.read(4096), timeout)
                        if not data:
                            break
                        chunks.append(data)
                        received += len(data)
                except TimeoutError:
                    pass  # printer sent its reply and simply keeps the socket open
            finally:
                await _close(writer, timeout)
        except OSError as exc:
            raise PrinterUnreachableError(
                f"{printer.host}:{printer.port} - {describe_connection_error(exc)}"
            ) from exc

        return b"".join(chunks).decode("ascii", errors="replace").strip()
