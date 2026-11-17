"""
Completeness tripwire for exception_handlers._STATUS.

A DomainError subclass with no entry in _STATUS (and no mapped ancestor's
entry, since the lookup walks the MRO, see domain_error_handler) would
silently fall through to a 500 with no warning anywhere. This test
enforces that every domain exception the application can raise resolves
to a deliberate HTTP status, so that omission fails CI instead of
surfacing as a client-visible, unexplained 500 in production.

INTENTIONALLY_UNMAPPED is the only escape hatch, and it must name a real
reason: either the exception is caught locally by an endpoint before it
ever reaches domain_error_handler, or it is only ever raised from a
background code path (an APScheduler job, an event-bus worker) that has
no HTTP response to shape in the first place. A new DomainError subclass
that is neither must inherit a semantic base from Platform's
domain/exceptions.py, not get an allowlist entry.
"""

import importlib
import json
import logging
from pathlib import Path

from src.modules.platform.adapters.inbound.api.exception_handlers import _LOG_ERROR
from src.modules.platform.adapters.inbound.api.exception_handlers import _SELF_LOGGED
from src.modules.platform.adapters.inbound.api.exception_handlers import _STATUS
from src.modules.platform.adapters.inbound.api.exception_handlers import domain_error_handler
from src.modules.platform.domain.exceptions import BackupError
from src.modules.platform.domain.exceptions import CredentialsUnverifiableError
from src.modules.platform.domain.exceptions import DomainError
from src.modules.platform.domain.exceptions import InvalidTokenError
from src.modules.platform.domain.exceptions import MailRateLimitedError
from src.modules.platform.domain.exceptions import MaintenanceModeError
from src.modules.platform.domain.exceptions import ServiceUnreachableError
from src.modules.platform.domain.exceptions import SmtpDeliveryError
from src.modules.platform.domain.exceptions import StoragePublicUrlUnavailableError
from src.modules.platform.domain.exceptions import UserNotFoundError
from src.modules.platform.domain.exceptions import WebhookDeliveryFailedError

SRC = Path(__file__).resolve().parents[2] / "src"

# Every entry here must justify itself, see the module docstring for what
# counts as a legitimate reason.
INTENTIONALLY_UNMAPPED: frozenset[type[DomainError]] = frozenset(
    {
        # Raised only inside DispatchEventToWebhooks, which runs on the
        # "webhooks" event-bus worker (see main.py's _handle_webhook_event)
        # a background consumer loop with no HTTP request to answer.
        WebhookDeliveryFailedError,
        # Raised only by LocalStorageAdapter.get_url (local storage never
        # has a public URL, since no unauthenticated `/media` mount
        # exists). Its only caller,
        # get_storage_url_best_effort (storage_asset.py), catches this
        # specific type ahead of its broad handler and returns None before
        # it would ever reach domain_error_handler.
        StoragePublicUrlUnavailableError,
    }
)


def _all_domain_exception_types() -> set[type[DomainError]]:
    """Every DomainError subclass currently defined. Platform's
    domain/exceptions.py is loaded by the imports above, and every module's
    domain/errors.py is imported here, so __subclasses__() sees the complete
    set, unlike relying on exception_handlers' own imports, which would only
    ever see the subset it already imports and could never catch a
    forgotten one."""
    for path in sorted(SRC.glob("modules/*/domain/errors.py")):
        importlib.import_module(f"src.modules.{path.parts[-3]}.domain.errors")

    def _recurse(cls: type[DomainError]) -> set[type[DomainError]]:
        subclasses = set(cls.__subclasses__())
        for sub in list(subclasses):
            subclasses |= _recurse(sub)
        return subclasses

    return _recurse(DomainError)


def _resolves_via_mro(exc_type: type[DomainError]) -> bool:
    """Mirrors domain_error_handler's own lookup exactly, see
    exception_handlers.py."""
    return any(k in _STATUS for k in exc_type.__mro__)


class TestExceptionStatusMappingIsComplete:
    def test_every_domain_exception_resolves_to_a_status_or_is_allowlisted(self):
        all_types = _all_domain_exception_types()
        unresolved = {
            exc_type
            for exc_type in all_types
            if not _resolves_via_mro(exc_type) and exc_type not in INTENTIONALLY_UNMAPPED
        }
        assert not unresolved, (
            f"{sorted(t.__name__ for t in unresolved)} have no _STATUS entry "
            "(direct or inherited) and are not in INTENTIONALLY_UNMAPPED. "
            "Inherit a semantic base from domain/exceptions.py, or, only if this "
            "exception genuinely never reaches domain_error_handler, add it "
            "to INTENTIONALLY_UNMAPPED with a reason."
        )

    def test_allowlist_entries_are_still_genuinely_unmapped(self):
        """Catches the inverse mistake: an allowlist entry that quietly
        became mapped without the allowlist being updated, dead
        documentation is worse than none."""
        stale = {exc_type for exc_type in INTENTIONALLY_UNMAPPED if _resolves_via_mro(exc_type)}
        assert not stale, (
            f"{sorted(t.__name__ for t in stale)} are in INTENTIONALLY_UNMAPPED "
            "but now resolve to a real status, remove them from the allowlist."
        )

    def test_allowlist_entries_are_still_real_domain_exceptions(self):
        """Catches a typo'd or removed exception name inside
        INTENTIONALLY_UNMAPPED silently going unnoticed."""
        all_types = _all_domain_exception_types()
        assert all_types >= INTENTIONALLY_UNMAPPED


class TestMaintenanceModeErrorMapsTo503:
    """Maintenance mode's whole backend gate (auth_deps.py, web_login.py,
    totp_login.py) relies on raising MaintenanceModeError and letting this
    handler turn it into the response the frontend keys on.
    """

    async def test_maps_to_503_with_the_message_and_a_stable_code(self, glados_caplog):
        exc = MaintenanceModeError("Back in 10 minutes.")

        response = await domain_error_handler(None, exc)  # type: ignore[arg-type]

        assert response.status_code == 503
        assert json.loads(response.body) == {
            "detail": "Back in 10 minutes.",
            "code": "MaintenanceModeError",
        }

    def test_not_in_self_logged(self):
        """No raise site for MaintenanceModeError logs its own contextual
        line (see the module docstring's _SELF_LOGGED membership rule), so
        it must not be opted out of the handler's own log call: doing so
        would silently drop the only log line a blocked request produces."""
        assert MaintenanceModeError not in _SELF_LOGGED

    async def test_still_produces_exactly_one_warning_record(self, glados_caplog):
        """Expected, frequent traffic while maintenance mode is on, not an
        application fault, the default warning level (not _LOG_ERROR) is
        enough."""
        exc = MaintenanceModeError("Back in 10 minutes.")

        response = await domain_error_handler(None, exc)  # type: ignore[arg-type]

        assert response.status_code == 503
        assert len(glados_caplog.records) == 1
        assert glados_caplog.records[0].levelno == logging.WARNING


class TestInvalidTokenErrorMapsTo401:
    """Every raise site (ValidateWebToken, ValidateApiKey, ValidatePat) is
    a missing, invalid, revoked or expired credential, an authentication
    failure. All four call sites in auth_deps.py already catch this
    locally and answer their own 401, this test only pins the fallback
    _STATUS entry a future caller would land on if it forgot to.
    """

    async def test_maps_to_401_with_the_message_and_a_stable_code(self, glados_caplog):
        exc = InvalidTokenError("Session expired")

        response = await domain_error_handler(None, exc)  # type: ignore[arg-type]

        assert response.status_code == 401
        assert json.loads(response.body) == {
            "detail": "Session expired",
            "code": "InvalidTokenError",
        }


class TestBackupErrorMapsTo500:
    """RunClaimedBackup wraps every backup job call in a bare except
    Exception and never lets a BackupError reach an HTTP response, this
    test only pins the fallback status for the case where it did.
    """

    async def test_maps_to_500_with_the_message_and_a_stable_code(self, glados_caplog):
        exc = BackupError("pg_dump failed: connection refused")

        response = await domain_error_handler(None, exc)  # type: ignore[arg-type]

        assert response.status_code == 500
        assert json.loads(response.body) == {
            "detail": "pg_dump failed: connection refused",
            "code": "BackupError",
        }


class TestCredentialsUnverifiableErrorMapsTo401NotItsParentsStatus:
    """A directory outage during login must answer with exactly the same
    401 as a wrong password, never the 404 its UserNotFoundError parent
    would otherwise contribute through the MRO, and never a 503, which
    would tell an unauthenticated caller the directory is down. See the
    reasoning on CredentialsUnverifiableError itself and on the
    _STATUS entry in exception_handlers.py.
    """

    async def test_maps_to_401_not_404(self, glados_caplog):
        exc = CredentialsUnverifiableError("Incorrect username or password.")

        response = await domain_error_handler(None, exc)  # type: ignore[arg-type]

        assert response.status_code == 401
        assert json.loads(response.body) == {
            "detail": "Incorrect username or password.",
            "code": "CredentialsUnverifiableError",
        }

    def test_is_still_a_user_not_found_error_subclass(self):
        """test_user_use_cases.py's test_a_directory_outage_raises_the_
        unverifiable_subtype asserts on this too, so every
        except UserNotFoundError also catches it."""
        assert issubclass(CredentialsUnverifiableError, UserNotFoundError)


# ───── _SELF_LOGGED opts specific types out of the handler's own log ─────


class TestSelfLoggedTypesAreNotDoubled:
    async def test_a_self_logged_member_produces_no_handler_log_line(self, glados_caplog):
        exc = MailRateLimitedError("Mail send rate limit exceeded. Try again later.")

        response = await domain_error_handler(None, exc)  # type: ignore[arg-type]

        assert response.status_code == 429
        assert json.loads(response.body) == {
            "detail": "Mail send rate limit exceeded. Try again later.",
            "code": "MailRateLimitedError",
        }
        assert glados_caplog.records == []

    async def test_a_second_self_logged_member_also_produces_no_handler_log_line(
        self, glados_caplog
    ):
        exc = SmtpDeliveryError("Connection refused")

        response = await domain_error_handler(None, exc)  # type: ignore[arg-type]

        assert response.status_code == 502
        assert glados_caplog.records == []

    async def test_a_non_member_still_produces_exactly_one_record_at_its_expected_level(
        self, glados_caplog
    ):
        """Status/body/logging for every type NOT in _SELF_LOGGED must be
        completely unaffected by its introduction."""
        exc = UserNotFoundError("Incorrect username or password.")

        response = await domain_error_handler(None, exc)  # type: ignore[arg-type]

        assert response.status_code == 404
        assert len(glados_caplog.records) == 1
        assert glados_caplog.records[0].levelno == logging.WARNING


class TestSelfLoggedMembershipIsSane:
    def test_every_self_logged_entry_is_a_real_domain_error_that_resolves_via_the_mro(self):
        """Mirrors the INTENTIONALLY_UNMAPPED hygiene tests above: an
        entry that stopped resolving to a real status (or was never a
        genuine DomainError subclass) would silently reintroduce the
        exact double-logging this set exists to prevent."""
        assert _all_domain_exception_types() >= _SELF_LOGGED
        unresolved = {t for t in _SELF_LOGGED if not _resolves_via_mro(t)}
        assert not unresolved, (
            f"{sorted(t.__name__ for t in unresolved)} are in _SELF_LOGGED but have no "
            "_STATUS entry - domain_error_handler would never take the self-logged "
            "branch for them the way the code assumes."
        )


class TestUnreachableServicesLogAsErrors:
    """Platform's handler never names a module's error, so an external
    system that cannot be reached is logged as an error through the shared
    ServiceUnreachableError base."""

    def test_every_unavailable_error_of_an_external_system_inherits_the_shared_base(self):
        names = {t.__name__ for t in _all_domain_exception_types()}
        expected = {
            "EdpUnavailableError",
            "LdapUnavailableError",
            "PdmUnavailableError",
            "StockServiceUnavailableError",
            "TimeTrackingUnavailableError",
        }
        assert expected <= names
        unreachable = {
            t.__name__
            for t in _all_domain_exception_types()
            if issubclass(t, ServiceUnreachableError)
        }
        assert unreachable >= expected

    async def test_a_module_error_on_the_shared_base_logs_one_error_record(self, glados_caplog):
        from src.modules.external_data.domain.errors import PdmUnavailableError

        assert ServiceUnreachableError in _LOG_ERROR
        response = await domain_error_handler(None, PdmUnavailableError("Vault unreachable"))  # type: ignore[arg-type]

        assert response.status_code == 503
        assert json.loads(response.body)["code"] == "PdmUnavailableError"
        assert len(glados_caplog.records) == 1
        assert glados_caplog.records[0].levelno == logging.ERROR
