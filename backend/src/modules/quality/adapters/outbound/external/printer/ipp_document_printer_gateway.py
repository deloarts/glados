"""
IPP gateway for document (PDF) printers: builds and parses IPP
Print-Job/Get-Printer-Attributes/Identify-Printer requests over HTTP.
Falls back to raw-9100 PDF direct print when Printer.transport == "raw",
kept as a fallback, not the default: it gives no acknowledgement and no
media selection.

The IPP round trip stays on urllib (plain HTTP, no client state worth
pooling) and runs on a worker thread; the raw fallback shares the ZPL
gateway's asyncio socket helper.
"""

import struct
import urllib.error
import urllib.request

from anyio import to_thread

from src.modules.quality.adapters.outbound.external.printer.zpl_socket_printer_gateway import (
    describe_connection_error,
)
from src.modules.quality.adapters.outbound.external.printer.zpl_socket_printer_gateway import (
    send_raw_tcp,
)
from src.modules.quality.domain.entities.printer import Printer
from src.modules.quality.domain.errors import PrinterUnreachableError
from src.modules.quality.domain.errors import PrintRejectedError
from src.modules.quality.domain.services.ipp_status import describe_ipp_identity
from src.modules.quality.domain.services.ipp_status import describe_ipp_print_result
from src.modules.quality.domain.services.ipp_status import describe_ipp_status
from src.modules.quality.domain.services.ipp_status import ipp_attributes_substituted
from src.modules.quality.domain.services.ipp_status import parse_ipp_reply
from src.modules.quality.domain.value_objects.print_classifier import PrintSides
from src.modules.quality.ports.outbound.printer_gateway_port import PrintDelivery


def _ipp_attr(tag: int, name: str, value: bytes) -> bytes:
    return (
        bytes([tag])
        + struct.pack(">H", len(name))
        + name.encode()
        + struct.pack(">H", len(value))
        + value
    )


def _ipp_request(operation: int, uri: str, attributes: bytes, extra_group: bytes = b"") -> bytes:
    """IPP 2.0 request envelope: version, operation, request id, attribute groups."""
    request = b"\x02\x00" + struct.pack(">H", operation) + struct.pack(">I", 1)
    request += b"\x01"  # operation-attributes-tag
    request += _ipp_attr(0x47, "attributes-charset", b"utf-8")
    request += _ipp_attr(0x48, "attributes-natural-language", b"en-us")
    request += _ipp_attr(0x45, "printer-uri", uri.encode())
    request += attributes
    request += extra_group
    request += b"\x03"  # end-of-attributes-tag
    return request


# An IPP attributes reply is a few kilobytes; a larger one is not a printer.
_MAX_REPLY_BYTES = 1024 * 1024


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    """A printer answers where it is asked. Following a redirect would let
    the host send the request, and show its answer, somewhere else."""

    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


_OPENER = urllib.request.build_opener(_NoRedirects)


def _url_host(host: str) -> str:
    """The host as it goes into a URL, with an IPv6 address in brackets."""
    return f"[{host}]" if ":" in host else host


class IppDocumentPrinterGateway:
    """Implements IPrinterGateway for Printer.kind == "ipp_document"."""

    async def send(
        self,
        printer: Printer,
        payload: bytes,
        content_type: str,
        copies: int,
        *,
        sides: PrintSides = PrintSides.ONE_SIDED,
    ) -> PrintDelivery:
        if printer.transport == "raw":
            await send_raw_tcp(printer, payload * copies)
            return PrintDelivery(attributes_substituted=sides is not PrintSides.ONE_SIDED)

        operation = _ipp_attr(0x42, "requesting-user-name", b"glados")
        operation += _ipp_attr(0x42, "job-name", b"glados print job")
        operation += _ipp_attr(0x49, "document-format", content_type.encode())

        job = b"\x02"  # job-attributes-tag
        job += _ipp_attr(0x21, "copies", struct.pack(">I", copies))
        if printer.default_media:
            job += _ipp_attr(0x44, "media", printer.default_media.encode())
        job += _ipp_attr(0x44, "sides", sides.value.encode())

        uri = f"ipp://{_url_host(printer.host)}{printer.ipp_uri_path}"
        body = _ipp_request(0x0002, uri, operation, job) + payload
        status, attributes = await self._post(printer, uri, body)

        try:
            describe_ipp_print_result(status, attributes)
        except ValueError as exc:
            raise PrintRejectedError(str(exc)) from exc
        return PrintDelivery(attributes_substituted=ipp_attributes_substituted(status))

    async def identify(self, printer: Printer) -> str:
        uri = f"ipp://{_url_host(printer.host)}{printer.ipp_uri_path}"
        status, attributes = await self._post(printer, uri, _ipp_request(0x000B, uri, b""))
        return describe_ipp_identity(status, attributes)

    async def status(self, printer: Printer) -> list[str]:
        # A second Get-Printer-Attributes round trip, not a reuse of
        # identify()'s reply: ZPL's ~HI/~HS are the same shape (two
        # separate queries), and identify() and status() must not show
        # identical content.
        uri = f"ipp://{_url_host(printer.host)}{printer.ipp_uri_path}"
        status, attributes = await self._post(printer, uri, _ipp_request(0x000B, uri, b""))
        return describe_ipp_status(status, attributes)

    async def _post(
        self, printer: Printer, uri: str, body: bytes
    ) -> tuple[int, list[tuple[str, bytes]]]:
        reply = await to_thread.run_sync(self._post_blocking, printer, body)
        return parse_ipp_reply(reply)

    def _post_blocking(self, printer: Printer, body: bytes) -> bytes:
        request = urllib.request.Request(
            f"http://{_url_host(printer.host)}:{printer.port}/",
            data=body,
            headers={"Content-Type": "application/ipp"},
        )
        try:
            with _OPENER.open(request, timeout=printer.timeout_seconds) as response:
                reply: bytes = response.read(_MAX_REPLY_BYTES + 1)
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise PrinterUnreachableError(
                f"{printer.host}:{printer.port} - {describe_connection_error(exc)}"
            ) from exc
        if len(reply) > _MAX_REPLY_BYTES:
            raise PrinterUnreachableError(
                f"{printer.host}:{printer.port} - the reply is larger than an IPP printer sends."
            )
        return reply
