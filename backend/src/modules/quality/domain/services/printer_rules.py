"""
Permission guards for Printer, and whether a printer can take an uploaded
document. No I/O. No lifecycle status, a printer is a plain catalogue row
with only an `archived` flag, mirrors machine_pool_rules.py's shape.
"""

from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.quality.domain.entities.printer import Printer
from src.modules.quality.domain.errors import InvalidPrinterHostError
from src.modules.quality.domain.services.printer_host import printer_host_problem
from src.modules.quality.domain.value_objects.printer_kind import PrinterKind


class PrinterRules:
    @staticmethod
    def assert_can_create(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_PRINTERS, "create", "printers")

    @staticmethod
    def assert_can_update(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_PRINTERS, "update", "printers")

    @staticmethod
    def assert_can_archive(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_PRINTERS, "archive", "printers")

    @staticmethod
    def assert_can_restore(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_PRINTERS, "restore", "printers")

    @staticmethod
    def assert_can_print(actor: User) -> None:
        assert_has_permission(actor, Permission.PRINT_DOCUMENTS, "print with", "printers")

    @staticmethod
    def assert_host_allowed(host: str) -> None:
        problem = printer_host_problem(host)
        if problem:
            raise InvalidPrinterHostError(problem)

    @staticmethod
    def out_of_use_problem(printer: Printer) -> str | None:
        """Why `printer` is out of use, or None when it is in use. An archived
        or disabled printer receives no print at all, so switching a printer
        off stops its labels, dockets and reports alike."""
        if printer.archived:
            return f"Printer #{printer.id} is archived."
        if not printer.enabled:
            return f"Printer #{printer.id} is disabled."
        return None

    @staticmethod
    def document_printer_problem(printer: Printer) -> str | None:
        """Why `printer` cannot take a finished PDF someone chose to print, or
        None when it can. A template print has its printer configured by an
        admin; an uploaded document names one picked from a list, so a
        printer taken out of use must not receive it."""
        problem = PrinterRules.out_of_use_problem(printer)
        if problem:
            return problem
        if printer.kind != PrinterKind.IPP_DOCUMENT.value:
            return f"Printer #{printer.id} is a {printer.kind.value!r} printer, not a document printer."
        return None
