"""
HTTP round trip for POST /print/document: a calculation and a document
printer are created through their own routes, the printer gateway is
replaced so no device is contacted, and the job row is read back through
the print jobs route.
"""

import hashlib
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Iterator
from datetime import UTC
from datetime import datetime
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.main import app
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.quality.adapters.inbound.api.deps.services import get_printer_gateway
from src.modules.quality.domain.entities.printer import Printer
from src.modules.quality.domain.value_objects.print_classifier import PrintSides
from src.modules.quality.ports.outbound.printer_gateway_port import PrintDelivery
from src.modules.workspace.adapters.outbound.persistence.repositories.product_repository import (
    SqlAlchemyProductRepository,
)
from src.modules.workspace.domain.entities.product import Product

ClientFactory = Callable[..., Awaitable[httpx.AsyncClient]]

URL = "/api/v1/web/print/document"
PDF = b"%PDF-1.7\n% calculation report\n"


class FakePrinterGateway:
    def __init__(self) -> None:
        self.sent: list[tuple[str, bytes, int, PrintSides]] = []

    async def send(
        self,
        printer: Printer,
        payload: bytes,
        content_type: str,
        copies: int,
        *,
        sides: PrintSides = PrintSides.ONE_SIDED,
    ) -> PrintDelivery:
        self.sent.append((printer.name, payload, copies, sides))
        return PrintDelivery()


@pytest.fixture
def gateway() -> Iterator[FakePrinterGateway]:
    fake = FakePrinterGateway()
    app.dependency_overrides[get_printer_gateway] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_printer_gateway, None)


async def _calculation(client: httpx.AsyncClient) -> dict[str, Any]:
    resp = await client.post(
        "/api/v1/web/calculations",
        json={
            "tool": "drive_sizing",
            "title": "Vertical axis, 140 kg, i = 12",
            "inputs": {"o": "vertical"},
            "results": {"ok": True},
            "input_version": 1,
            "engine_version": 1,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _printer(client: httpx.AsyncClient) -> dict[str, Any]:
    resp = await client.post(
        "/api/v1/web/printers/",
        json={
            "name": "Office printer",
            "kind": "ipp_document",
            "host": "192.0.2.20",
            "port": 631,
            "transport": "ipp",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _form(calculation: dict[str, Any], printer: dict[str, Any], **overrides: str) -> dict[str, str]:
    return {
        "document": "calculation_report",
        "root_public_id": calculation["public_id"],
        "printer_id": str(printer["id"]),
        "copies": "2",
        "two_sided": "true",
    } | overrides


async def test_print_uploaded_document_round_trip(
    auth_client: ClientFactory, gateway: FakePrinterGateway
) -> None:
    client = await auth_client(
        permissions=[
            Permission.WRITE_CALCULATIONS,
            Permission.WRITE_PRINTERS,
            Permission.PRINT_DOCUMENTS,
            Permission.READ_SETTINGS,
        ]
    )
    calculation = await _calculation(client)
    printer = await _printer(client)

    resp = await client.post(
        URL,
        data=_form(calculation, printer),
        files={"file": ("report.pdf", PDF, "application/pdf")},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "sent"
    assert body["attributes_substituted"] is False
    assert gateway.sent == [("Office printer", PDF, 2, PrintSides.TWO_SIDED_LONG_EDGE)]

    jobs = await client.get(
        "/api/v1/web/print-jobs/",
        params={"root_type": "calculation", "root_id": calculation["id"]},
    )
    assert jobs.status_code == 200, jobs.text
    [job] = jobs.json()["items"]
    assert job["classifier"] == "calculation_report"
    assert job["printer_id"] == printer["id"]
    assert job["copies"] == 2


async def test_print_uploaded_document_hides_another_users_personal_calculation(
    auth_client: ClientFactory, gateway: FakePrinterGateway
) -> None:
    owner = await auth_client(
        permissions=[Permission.WRITE_CALCULATIONS, Permission.WRITE_PRINTERS],
        username="owner",
        email="owner@example.com",
    )
    calculation = await _calculation(owner)
    printer = await _printer(owner)
    other = await auth_client(
        permissions=[Permission.PRINT_DOCUMENTS], username="other", email="other@example.com"
    )

    resp = await other.post(
        URL,
        data=_form(calculation, printer),
        files={"file": ("report.pdf", PDF, "application/pdf")},
    )

    assert resp.status_code == 404, resp.text
    assert gateway.sent == []


async def test_print_uploaded_document_rejects_a_file_that_is_not_a_pdf(
    auth_client: ClientFactory, gateway: FakePrinterGateway
) -> None:
    client = await auth_client(
        permissions=[
            Permission.WRITE_CALCULATIONS,
            Permission.WRITE_PRINTERS,
            Permission.PRINT_DOCUMENTS,
        ]
    )
    calculation = await _calculation(client)
    printer = await _printer(client)

    resp = await client.post(
        URL,
        data=_form(calculation, printer),
        files={"file": ("report.pdf", b"<html></html>", "application/pdf")},
    )

    assert resp.status_code == 415, resp.text
    assert resp.json()["code"] == "PrintDocumentInvalidTypeError"
    assert gateway.sent == []


async def test_print_uploaded_document_needs_print_permission(
    auth_client: ClientFactory, gateway: FakePrinterGateway
) -> None:
    client = await auth_client(
        permissions=[Permission.WRITE_CALCULATIONS, Permission.WRITE_PRINTERS]
    )
    calculation = await _calculation(client)
    printer = await _printer(client)

    resp = await client.post(
        URL,
        data=_form(calculation, printer),
        files={"file": ("report.pdf", PDF, "application/pdf")},
    )

    assert resp.status_code == 403, resp.text
    assert gateway.sent == []


async def test_print_uploaded_document_prints_a_checklist_report(
    auth_client: ClientFactory,
    gateway: FakePrinterGateway,
    db: AsyncSession,
    create_user: Callable[..., Awaitable[User]],
) -> None:
    client = await auth_client(
        permissions=[
            Permission.WRITE_CHECKLISTS,
            Permission.WRITE_PRINTERS,
            Permission.PRINT_DOCUMENTS,
            Permission.READ_SETTINGS,
        ]
    )
    # A hydraulics checklist belongs to the product that describes the machine.
    product_creator = await create_user(username="product-owner", email="product@example.com")
    product = await SqlAlchemyProductRepository(db).save(
        Product(
            id=0,
            created=datetime.now(UTC),
            creator_id=product_creator.id,
            product_number="PR-PRINT-1",
        )
    )
    await db.commit()
    created = await client.post(
        "/api/v1/web/checklists",
        json={
            "type": "hydraulics",
            "title": "Press 12",
            "product_id": product.id,
            "header": {"designation": "Press 12", "legalBasis": "regulation"},
            "answers": {},
            "remarks": {},
            "definition_version": 1,
            "item_count": 3,
        },
    )
    assert created.status_code == 201, created.text
    checklist = created.json()
    printer = await _printer(client)

    resp = await client.post(
        URL,
        data=_form(checklist, printer, document="checklist_report", two_sided="false"),
        files={"file": ("report.pdf", PDF, "application/pdf")},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "sent"
    jobs = await client.get(
        "/api/v1/web/print-jobs/", params={"root_type": "checklist", "root_id": checklist["id"]}
    )
    [job] = jobs.json()["items"]
    assert job["classifier"] == "checklist_report"
    assert gateway.sent == [("Office printer", PDF, 2, PrintSides.ONE_SIDED)]


async def test_report_journal_records_downloads_and_prints(
    auth_client: ClientFactory, gateway: FakePrinterGateway
) -> None:
    client = await auth_client(
        permissions=[
            Permission.WRITE_CALCULATIONS,
            Permission.WRITE_PRINTERS,
            Permission.PRINT_DOCUMENTS,
        ]
    )
    calculation = await _calculation(client)
    printer = await _printer(client)
    facts = {"language": "deAT", "options": {"appendix": True}, "report_version": "0.1.0"}

    downloaded = await client.post(
        "/api/v1/web/report-journal/downloads",
        json={
            "document": "calculation_report",
            "root_public_id": calculation["public_id"],
            "facts": facts | {"engine_version": 1},
            "byte_size": 1234,
            "sha256": "AB" * 32,
        },
    )
    assert downloaded.status_code == 201, downloaded.text
    assert downloaded.json()["sha256"] == "ab" * 32

    printed = await client.post(
        URL,
        data=_form(
            calculation,
            printer,
            language="enGB",
            options='{"appendix": false}',
            report_version="0.1.0",
        ),
        files={"file": ("report.pdf", PDF, "application/pdf")},
    )
    assert printed.status_code == 200, printed.text

    journal = await client.get(
        "/api/v1/web/report-journal",
        params={"document": "calculation_report", "root_public_id": calculation["public_id"]},
    )
    assert journal.status_code == 200, journal.text
    rows = journal.json()
    assert [row["action"] for row in rows] == ["print", "download"]
    print_row, download_row = rows
    assert print_row["print_job_id"] == printed.json()["id"]
    assert print_row["copies"] == 2
    assert print_row["byte_size"] == len(PDF)
    assert print_row["sha256"] == hashlib.sha256(PDF).hexdigest()
    assert (print_row["language"], print_row["options"]) == ("enGB", {"appendix": False})
    assert download_row["revision"] == calculation["revision"]
    assert download_row["engine_version"] == 1
    assert download_row["actor_full_name"]


async def test_report_journal_rejects_a_hash_that_is_not_sha256(auth_client: ClientFactory) -> None:
    client = await auth_client(permissions=[Permission.WRITE_CALCULATIONS])
    calculation = await _calculation(client)
    resp = await client.post(
        "/api/v1/web/report-journal/downloads",
        json={
            "document": "calculation_report",
            "root_public_id": calculation["public_id"],
            "facts": {"language": "enGB", "options": {}, "report_version": "0.1.0"},
            "byte_size": 10,
            "sha256": "not-a-hash",
        },
    )
    assert resp.status_code == 422
