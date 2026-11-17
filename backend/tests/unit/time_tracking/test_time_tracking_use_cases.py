"""
The user's time tracking use cases against in-memory fakes: saving
credentials (sealed for the confirmed key, verified by the service before
storing, rights returned but not stored, refused for non-personal accounts,
without consent, for a user name linked elsewhere, after too many failed
checks, without a password where the stored value may not be re-verified),
checking access, and the month and year views (nothing written, rights,
future periods, throttling, the bookkeeping after a rejection or a changed
binding). The guards are checked to run before any request reaches the
time tracking service.
"""

from datetime import date

import pytest
from pydantic import SecretStr

from src.modules.operations.application.dto.time_tracking_dto import (
    SaveTimeTrackingCredentialsCommand,
)
from src.modules.operations.application.use_cases.time_tracking.check_my_time_tracking_access import (
    CheckMyTimeTrackingAccess,
)
from src.modules.operations.application.use_cases.time_tracking.delete_my_time_tracking_credentials import (
    DeleteMyTimeTrackingCredentials,
)
from src.modules.operations.application.use_cases.time_tracking.get_my_time_tracking_credentials import (
    GetMyTimeTrackingCredentials,
)
from src.modules.operations.application.use_cases.time_tracking.get_my_time_tracking_month import (
    GetMyTimeTrackingMonth,
)
from src.modules.operations.application.use_cases.time_tracking.get_my_time_tracking_year import (
    GetMyTimeTrackingYear,
)
from src.modules.operations.application.use_cases.time_tracking.save_my_time_tracking_credentials import (
    SaveMyTimeTrackingCredentials,
)
from src.modules.operations.domain.errors import TimeTrackingAuthenticationFailedError
from src.modules.operations.domain.errors import TimeTrackingBindingChangedError
from src.modules.operations.domain.errors import TimeTrackingConsentRequiredError
from src.modules.operations.domain.errors import TimeTrackingCredentialsMissingError
from src.modules.operations.domain.errors import TimeTrackingNotEnabledError
from src.modules.operations.domain.errors import TimeTrackingPeriodInvalidError
from src.modules.operations.domain.errors import TimeTrackingProviderError
from src.modules.operations.domain.errors import TimeTrackingRateLimitedError
from src.modules.operations.domain.errors import TimeTrackingUserAlreadyLinkedError
from src.modules.operations.domain.services.time_tracking_rules import TIME_TRACKING_CONSENT_VERSION
from src.modules.operations.domain.services.time_tracking_rules import VERIFY_FAILURE_LIMIT
from src.modules.operations.domain.services.time_tracking_rules import fingerprint_subject
from src.modules.operations.infrastructure.security.time_tracking_fingerprint import (
    time_tracking_fingerprint,
)
from src.modules.operations.ports.outbound.time_tracking_provider_port import (
    TimeTrackingServiceConnection,
)
from src.modules.platform.domain.exceptions import TimeTrackingCredentialsNotAllowedError
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.time_tracking._helpers import API_KEY
from tests.unit.time_tracking._helpers import BINDING
from tests.unit.time_tracking._helpers import KEY_ID
from tests.unit.time_tracking._helpers import NOW
from tests.unit.time_tracking._helpers import PASSWORD
from tests.unit.time_tracking._helpers import SEALED
from tests.unit.time_tracking._helpers import SERVICE_URL
from tests.unit.time_tracking._helpers import make_credentials
from tests.unit.time_tracking._helpers import make_settings
from tests.unit.time_tracking._helpers import make_user
from tests.unit.time_tracking._helpers import open_sealed
from tests.unit.time_tracking.fakes import FakeCredentialsRepo
from tests.unit.time_tracking.fakes import FakeProvider
from tests.unit.time_tracking.fakes import FakeSettingsRepo
from tests.unit.time_tracking.fakes import FakeTracker


class World:
    def __init__(self, *rows: object, settings: object | None = None) -> None:
        self.settings = FakeSettingsRepo(settings)  # type: ignore[arg-type]
        self.credentials = FakeCredentialsRepo(*rows)  # type: ignore[arg-type]
        self.provider = FakeProvider()
        self.tracker = FakeTracker()
        self.uow = FakeUnitOfWork()

    def deps(self) -> tuple[object, ...]:
        return (self.settings, self.credentials, self.provider.factory, self.tracker)

    def save(self) -> SaveMyTimeTrackingCredentials:
        return SaveMyTimeTrackingCredentials(*self.deps(), uow=self.uow, clock=lambda: NOW)  # type: ignore[arg-type]

    def check(self) -> CheckMyTimeTrackingAccess:
        return CheckMyTimeTrackingAccess(*self.deps(), uow=self.uow, clock=lambda: NOW)  # type: ignore[arg-type]

    def month(self) -> GetMyTimeTrackingMonth:
        return GetMyTimeTrackingMonth(*self.deps(), uow=self.uow, clock=lambda: NOW)  # type: ignore[arg-type]

    def year(self) -> GetMyTimeTrackingYear:
        return GetMyTimeTrackingYear(*self.deps(), uow=self.uow, clock=lambda: NOW)  # type: ignore[arg-type]


def save_cmd(**overrides: object) -> SaveTimeTrackingCredentialsCommand:
    values: dict[str, object] = {
        "time_tracking_user": "jane.doe",
        "time_tracking_password": SecretStr(PASSWORD),
        "time_tracking_consent_version": TIME_TRACKING_CONSENT_VERSION,
    }
    values.update(overrides)
    return SaveTimeTrackingCredentialsCommand(**values)  # type: ignore[arg-type]


# ── save ─────────────────────────────────────────────────────────────


async def test_save_seals_has_the_service_verify_then_stores_and_returns_rights(
    glados_caplog,
) -> None:
    world = World()

    result = await world.save().execute(make_user(), save_cmd())

    assert world.provider.names() == ["verify"]
    assert world.provider.connections == [
        TimeTrackingServiceConnection(service_url=SERVICE_URL, api_key=API_KEY)
    ]
    sealed = world.provider.calls[0][1][0]
    assert isinstance(sealed, str)
    assert PASSWORD not in sealed
    assert open_sealed(sealed) == {"user": "jane.doe", "password": PASSWORD}
    stored = world.credentials.rows[7]
    assert stored.time_tracking_user == "jane.doe"
    assert stored.time_tracking_sealed_credentials == sealed
    assert stored.time_tracking_binding == BINDING
    assert stored.time_tracking_credential_key_id == KEY_ID
    assert stored.time_tracking_user_fingerprint == time_tracking_fingerprint(
        fingerprint_subject("jane.doe")
    )
    assert stored.time_tracking_consent_version == TIME_TRACKING_CONSENT_VERSION
    assert stored.time_tracking_auth_failed_at is None
    assert world.uow.commits == 2
    assert result.time_tracking_employee_name == "Doe, Jane"
    assert result.time_tracking_rights is not None
    assert result.time_tracking_rights.model_dump() == {"days": False, "month": True, "year": True}
    assert result.time_tracking_credentials_valid
    assert result.time_tracking_provider_label == "Example Time"
    assert PASSWORD not in result.model_dump_json()
    assert all(PASSWORD not in record.getMessage() for record in glados_caplog.records)


async def test_save_with_rejected_credentials_stores_nothing_and_counts_the_failure(
    glados_caplog,
) -> None:
    world = World()
    world.provider.reject_credentials = True

    with pytest.raises(TimeTrackingAuthenticationFailedError):
        await world.save().execute(make_user(), save_cmd())

    assert world.credentials.saves == []
    assert world.credentials.auth_failed == []
    assert world.tracker.failures == {"time-tracking-verify:7": 1}
    assert all(PASSWORD not in record.getMessage() for record in glados_caplog.records)


@pytest.mark.parametrize(
    "flags",
    [{"is_shared_account": True}, {"is_service_account": True}, {"is_systemuser": True}],
)
async def test_save_is_refused_for_non_personal_accounts_without_a_call(
    flags: dict[str, bool],
) -> None:
    world = World()

    with pytest.raises(TimeTrackingCredentialsNotAllowedError):
        await world.save().execute(make_user(**flags), save_cmd())  # type: ignore[arg-type]

    assert world.provider.calls == []
    assert world.credentials.saves == []


@pytest.mark.parametrize("version", [None, TIME_TRACKING_CONSENT_VERSION - 1])
async def test_save_without_current_consent_is_refused_without_a_call(version: int | None) -> None:
    world = World()

    with pytest.raises(TimeTrackingConsentRequiredError):
        await world.save().execute(make_user(), save_cmd(time_tracking_consent_version=version))

    assert world.provider.calls == []


@pytest.mark.parametrize(
    "settings",
    [
        make_settings(enabled=False),
        make_settings(api_key=None),
        make_settings(credential_public_key=None, credential_key_id=None),
    ],
)
async def test_save_is_refused_unless_time_tracking_is_ready(settings: object) -> None:
    world = World(settings=settings)

    with pytest.raises(TimeTrackingNotEnabledError):
        await world.save().execute(make_user(), save_cmd())
    assert world.provider.calls == []


async def test_save_of_a_user_name_linked_to_another_user_is_refused_without_a_call() -> None:
    other = make_credentials(
        user_id=8,
        time_tracking_user_fingerprint=time_tracking_fingerprint(fingerprint_subject("jane.doe")),
    )
    world = World(other)

    with pytest.raises(TimeTrackingUserAlreadyLinkedError) as exc_info:
        await world.save().execute(make_user(), save_cmd(time_tracking_user="  JANE.DOE "))

    assert world.provider.calls == []
    assert "8" not in str(exc_info.value)


async def test_save_is_locked_after_repeated_failures() -> None:
    world = World()
    world.provider.reject_credentials = True
    use_case = world.save()

    for _ in range(VERIFY_FAILURE_LIMIT):
        with pytest.raises(TimeTrackingAuthenticationFailedError):
            await use_case.execute(make_user(), save_cmd())
    verifications = world.provider.names().count("verify")

    with pytest.raises(TimeTrackingRateLimitedError):
        await use_case.execute(make_user(), save_cmd())
    assert world.provider.names().count("verify") == verifications


async def test_successful_checks_do_not_lift_the_lockout_count() -> None:
    world = World()
    world.provider.reject_credentials = True
    with pytest.raises(TimeTrackingAuthenticationFailedError):
        await world.save().execute(make_user(), save_cmd())
    world.provider.reject_credentials = False

    await world.save().execute(make_user(), save_cmd())

    assert world.tracker.failures == {"time-tracking-verify:7": 1}


async def test_save_without_a_password_re_verifies_the_stored_value_and_renews_consent() -> None:
    world = World(make_credentials(time_tracking_consent_version=TIME_TRACKING_CONSENT_VERSION - 1))

    await world.save().execute(make_user(), save_cmd(time_tracking_password=None))

    assert world.provider.calls == [("verify", (SEALED,))]
    stored = world.credentials.rows[7]
    assert stored.time_tracking_sealed_credentials == SEALED
    assert stored.time_tracking_consent_version == TIME_TRACKING_CONSENT_VERSION


@pytest.mark.parametrize(
    "stored",
    [
        make_credentials(time_tracking_credential_key_id="another-key"),
        make_credentials(time_tracking_sealed_credentials=None),
        make_credentials(time_tracking_auth_failed_at=NOW),
        make_credentials(time_tracking_user=None),
        make_credentials(time_tracking_user="john.roe"),
    ],
)
async def test_save_requires_the_password_again_when_the_stored_value_may_not_be_reused(
    stored: object,
) -> None:
    world = World(stored)

    with pytest.raises(TimeTrackingCredentialsMissingError):
        await world.save().execute(make_user(), save_cmd(time_tracking_password=None))
    assert world.provider.calls == []


async def test_resaving_seals_for_the_current_key_and_clears_the_failure_mark() -> None:
    world = World(
        make_credentials(
            time_tracking_credential_key_id="old-key",
            time_tracking_binding="old-binding",
            time_tracking_auth_failed_at=NOW,
        )
    )

    await world.save().execute(make_user(), save_cmd())

    stored = world.credentials.rows[7]
    assert stored.time_tracking_credential_key_id == KEY_ID
    assert stored.time_tracking_binding == BINDING
    assert stored.time_tracking_auth_failed_at is None


# ── get, check and delete ────────────────────────────────────────────


async def test_get_reports_the_state_without_a_call() -> None:
    world = World(make_credentials(time_tracking_credential_key_id="old-key"))

    result = await GetMyTimeTrackingCredentials(world.settings, world.credentials).execute(  # type: ignore[arg-type]
        make_user()
    )

    assert world.provider.calls == []
    assert result.time_tracking_user == "jane.doe"
    assert result.time_tracking_password_configured
    assert not result.time_tracking_credentials_valid
    assert result.time_tracking_credentials_invalid_reason == "binding_changed"
    assert result.time_tracking_provider_label == "Example Time"


async def test_check_with_another_key_makes_no_call() -> None:
    world = World(make_credentials(time_tracking_credential_key_id="old-key"))

    with pytest.raises(TimeTrackingCredentialsMissingError, match="server or key has changed"):
        await world.check().execute(make_user())
    assert world.provider.calls == []


async def test_check_rejection_marks_the_credentials_and_blocks_the_next_call() -> None:
    world = World(make_credentials())
    world.provider.reject_credentials = True

    with pytest.raises(TimeTrackingAuthenticationFailedError):
        await world.check().execute(make_user())
    assert world.credentials.auth_failed == [(7, NOW)]
    assert world.tracker.failures == {"time-tracking-verify:7": 1}
    calls = len(world.provider.calls)

    with pytest.raises(TimeTrackingAuthenticationFailedError, match="Please enter them again"):
        await world.check().execute(make_user())
    assert len(world.provider.calls) == calls


async def test_check_returns_rights_without_storing_them() -> None:
    world = World(make_credentials())

    result = await world.check().execute(make_user())

    assert world.provider.calls == [("verify", (SEALED,))]
    assert result.time_tracking_rights is not None
    assert result.time_tracking_rights.days is False
    assert world.credentials.saves == []


async def test_delete_removes_credentials_even_when_disabled() -> None:
    world = World(make_credentials(), settings=make_settings(enabled=False))

    await DeleteMyTimeTrackingCredentials(world.credentials, uow=world.uow).execute(make_user())  # type: ignore[arg-type]

    assert 7 not in world.credentials.rows
    assert world.uow.committed


# ── month ────────────────────────────────────────────────────────────


async def test_month_reads_without_writing() -> None:
    world = World(make_credentials())

    result = await world.month().execute(make_user(), 2026, 9)

    assert world.provider.calls == [("month", (SEALED, BINDING, 2026, 9))]
    assert world.credentials.saves == [] and world.credentials.auth_failed == []
    assert result.rights.model_dump() == {"days": None, "month": True, "year": None}
    assert result.employee_name == "Doe, Jane"
    assert [d.date for d in result.days] == [date(2026, 9, 29), date(2026, 9, 30)]
    assert result.accounts[0].format == "duration_clock"
    assert result.totals is not None and result.totals.today is not None
    assert result.totals.today.clocked_in
    # 07:58 to 10:15 Vienna time.
    assert result.totals.today.worked_seconds == 2 * 3600 + 17 * 60
    assert result.fetched_at == NOW


async def test_month_without_the_right_returns_rights_and_no_data() -> None:
    world = World(make_credentials())
    world.provider.denied = {"month"}

    result = await world.month().execute(make_user(), 2026, 9)

    assert result.rights.month is False
    assert result.days == [] and result.totals is None


async def test_future_month_is_refused_without_a_call() -> None:
    world = World(make_credentials())

    with pytest.raises(TimeTrackingPeriodInvalidError):
        await world.month().execute(make_user(), 2026, 10)
    assert world.provider.calls == []


async def test_month_fetches_are_spaced() -> None:
    world = World(make_credentials())
    await world.month().execute(make_user(), 2026, 9)

    with pytest.raises(TimeTrackingRateLimitedError):
        await world.month().execute(make_user(), 2026, 8)
    assert world.provider.names().count("month") == 1


async def test_month_rejection_marks_the_stored_credentials() -> None:
    world = World(make_credentials())
    world.provider.reject_credentials = True

    with pytest.raises(TimeTrackingAuthenticationFailedError):
        await world.month().execute(make_user(), 2026, 9)

    assert world.credentials.auth_failed == [(7, NOW)]
    assert world.credentials.rows[7].time_tracking_auth_failed_at == NOW


async def test_a_changed_binding_drops_the_sealed_value_and_asks_for_the_password() -> None:
    world = World(make_credentials())
    world.provider.fail_on = {"month": TimeTrackingBindingChangedError("changed")}

    with pytest.raises(TimeTrackingBindingChangedError):
        await world.month().execute(make_user(), 2026, 9)

    assert world.credentials.cleared == [7]
    assert world.credentials.rows[7].time_tracking_sealed_credentials is None
    calls = len(world.provider.calls)
    world.tracker.locks.clear()
    with pytest.raises(TimeTrackingCredentialsMissingError, match="enter your password again"):
        await world.month().execute(make_user(), 2026, 9)
    assert len(world.provider.calls) == calls


async def test_a_provider_error_is_raised_on_without_bookkeeping() -> None:
    world = World(make_credentials())
    world.provider.fail_on = {"month": TimeTrackingProviderError("boom")}

    with pytest.raises(TimeTrackingProviderError):
        await world.month().execute(make_user(), 2026, 9)
    assert world.credentials.auth_failed == [] and world.credentials.cleared == []


async def test_month_with_undecryptable_credentials_needs_them_again() -> None:
    world = World(make_credentials(time_tracking_user=None))

    with pytest.raises(TimeTrackingCredentialsMissingError, match="enter them again"):
        await world.month().execute(make_user(), 2026, 9)
    assert world.provider.calls == []


# ── year ─────────────────────────────────────────────────────────────


async def test_year_is_built_from_the_months_the_service_returns() -> None:
    world = World(make_credentials())

    result = await world.year().execute(make_user(), 2026)

    assert world.provider.calls == [("year", (SEALED, BINDING, 2026))]
    assert [m.month for m in result.months] == list(range(1, 10))
    assert result.rights.year is True
    assert result.end_balance_seconds == 5880


async def test_year_without_the_right_has_no_months() -> None:
    world = World(make_credentials())
    world.provider.denied = {"year"}

    result = await world.year().execute(make_user(), 2026)

    assert result.rights.year is False
    assert result.months == []


async def test_future_year_is_refused() -> None:
    world = World(make_credentials())

    with pytest.raises(TimeTrackingPeriodInvalidError):
        await world.year().execute(make_user(), 2027)
    assert world.provider.calls == []


async def test_month_and_year_have_separate_cooldowns() -> None:
    world = World(make_credentials())

    await world.month().execute(make_user(), 2026, 9)
    await world.year().execute(make_user(), 2026)

    assert world.provider.names() == ["month", "year"]
