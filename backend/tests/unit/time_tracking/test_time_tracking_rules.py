"""
Pure rules around time tracking: input limits for values the time tracking
system receives, the usable-credentials check and its reasons, the consent
version, the settings validation (service URL shape, what enabling and
readiness need), the sealing of credentials and the support checks for the
service's contract, and the personal-account rule on UserRules.
"""

import pytest

from src.modules.operations.application.services.time_tracking_service import contract_supported
from src.modules.operations.application.services.time_tracking_service import (
    credential_fields_supported,
)
from src.modules.operations.domain.entities.admin_settings.time_tracking import (
    normalize_privacy_policy_url,
)
from src.modules.operations.domain.entities.admin_settings.time_tracking import (
    normalize_service_url,
)
from src.modules.operations.domain.entities.user_time_tracking_credentials import (
    UserTimeTrackingCredentials,
)
from src.modules.operations.domain.errors import TimeTrackingAuthenticationFailedError
from src.modules.operations.domain.errors import TimeTrackingConsentRequiredError
from src.modules.operations.domain.errors import TimeTrackingCredentialsMissingError
from src.modules.operations.domain.errors import TimeTrackingNotConfiguredError
from src.modules.operations.domain.services.time_tracking_rules import TIME_TRACKING_CONSENT_VERSION
from src.modules.operations.domain.services.time_tracking_rules import CredentialsInvalidReason
from src.modules.operations.domain.services.time_tracking_rules import assert_consent_current
from src.modules.operations.domain.services.time_tracking_rules import assert_credentials_usable
from src.modules.operations.domain.services.time_tracking_rules import credentials_invalid_reason
from src.modules.operations.domain.services.time_tracking_rules import fingerprint_subject
from src.modules.operations.domain.services.time_tracking_rules import (
    validate_time_tracking_password,
)
from src.modules.operations.domain.services.time_tracking_rules import validate_time_tracking_user
from src.modules.operations.infrastructure.security.time_tracking_sealer import (
    InvalidCredentialKeyError,
)
from src.modules.operations.infrastructure.security.time_tracking_sealer import seal_credentials
from src.modules.operations.ports.outbound.time_tracking_provider_port import (
    TimeTrackingCredentialField,
)
from src.modules.platform.domain.exceptions import TimeTrackingCredentialsNotAllowedError
from src.modules.platform.domain.services.user_rules import UserRules
from tests.unit.time_tracking._helpers import KEY_ID
from tests.unit.time_tracking._helpers import NOW
from tests.unit.time_tracking._helpers import PUBLIC_KEY
from tests.unit.time_tracking._helpers import make_credentials
from tests.unit.time_tracking._helpers import make_settings
from tests.unit.time_tracking._helpers import make_user
from tests.unit.time_tracking._helpers import open_sealed

# ── input limits ─────────────────────────────────────────────────────


def test_user_name_is_trimmed() -> None:
    assert validate_time_tracking_user("  jane.doe ") == "jane.doe"


@pytest.mark.parametrize("value", ["", "   ", "jane:doe", "jane\ndoe", "j" * 129])
def test_invalid_user_names_are_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        validate_time_tracking_user(value)


@pytest.mark.parametrize("value", ["", "pw\x00x", "pw\tx", "p" * 257])
def test_invalid_passwords_are_rejected_without_echoing_them(value: str) -> None:
    with pytest.raises(ValueError) as exc_info:
        validate_time_tracking_password(value)
    if value:
        assert value not in str(exc_info.value)


def test_password_keeps_spaces_and_non_ascii() -> None:
    assert validate_time_tracking_password(" Grüße ß ") == " Grüße ß "


def test_fingerprint_subject_normalises_case_and_spacing() -> None:
    assert fingerprint_subject(" Jane.Doe ") == fingerprint_subject("jane.doe")
    assert fingerprint_subject("jane.doe") != fingerprint_subject("john.roe")


# ── usable credentials ───────────────────────────────────────────────


def test_usable_credentials_have_no_reason() -> None:
    credentials = make_credentials()
    assert credentials_invalid_reason(credentials, current_key_id=KEY_ID) is None
    assert assert_credentials_usable(credentials, current_key_id=KEY_ID) is credentials


@pytest.mark.parametrize(
    ("credentials", "reason", "error"),
    [
        (None, CredentialsInvalidReason.MISSING, TimeTrackingCredentialsMissingError),
        (
            make_credentials(time_tracking_user=None),
            CredentialsInvalidReason.UNDECRYPTABLE,
            TimeTrackingCredentialsMissingError,
        ),
        (
            make_credentials(time_tracking_credential_key_id="another-key"),
            CredentialsInvalidReason.BINDING_CHANGED,
            TimeTrackingCredentialsMissingError,
        ),
        (
            make_credentials(time_tracking_sealed_credentials=None),
            CredentialsInvalidReason.BINDING_CHANGED,
            TimeTrackingCredentialsMissingError,
        ),
        (
            make_credentials(time_tracking_auth_failed_at=NOW),
            CredentialsInvalidReason.AUTH_FAILED,
            TimeTrackingAuthenticationFailedError,
        ),
        (
            make_credentials(time_tracking_consent_version=TIME_TRACKING_CONSENT_VERSION - 1),
            CredentialsInvalidReason.CONSENT_OUTDATED,
            TimeTrackingConsentRequiredError,
        ),
    ],
)
def test_unusable_credentials_report_their_reason(
    credentials: UserTimeTrackingCredentials | None,
    reason: CredentialsInvalidReason,
    error: type[Exception],
) -> None:
    assert credentials_invalid_reason(credentials, current_key_id=KEY_ID) is reason
    with pytest.raises(error):
        assert_credentials_usable(credentials, current_key_id=KEY_ID)


def test_without_a_confirmed_key_no_credentials_are_usable() -> None:
    assert (
        credentials_invalid_reason(make_credentials(), current_key_id=None)
        is CredentialsInvalidReason.BINDING_CHANGED
    )


def test_consent_must_be_the_current_version() -> None:
    # Intentionally only checks that the current version is accepted.
    assert_consent_current(TIME_TRACKING_CONSENT_VERSION)
    for version in (None, 0, TIME_TRACKING_CONSENT_VERSION + 1):
        with pytest.raises(TimeTrackingConsentRequiredError):
            assert_consent_current(version)


# ── settings ─────────────────────────────────────────────────────────


def test_service_url_is_normalised_and_http_is_accepted() -> None:
    assert normalize_service_url(" http://time-tracking:3100/ ") == "http://time-tracking:3100"
    assert normalize_service_url("https://time.example.test/api/") == (
        "https://time.example.test/api"
    )
    assert normalize_service_url("  ") == ""


@pytest.mark.parametrize(
    "url",
    [
        "ftp://time.example.test",
        "time.example.test",
        "https://",
        "https://user:pw@time.example.test",
        "https://time.example.test/?x=1",
        "https://time.example.test/#frag",
        "https://time.example.test:99999",
    ],
)
def test_invalid_service_urls_are_rejected(url: str) -> None:
    with pytest.raises(ValueError):
        normalize_service_url(url)


def test_privacy_policy_url() -> None:
    assert normalize_privacy_policy_url(" ") is None
    assert normalize_privacy_policy_url("https://intranet.example.test/privacy") == (
        "https://intranet.example.test/privacy"
    )
    with pytest.raises(ValueError):
        normalize_privacy_policy_url("javascript:alert(1)")


def test_enabling_requires_a_service_url_and_an_api_key() -> None:
    for overrides in ({"service_url": ""}, {"api_key": None}):
        with pytest.raises(TimeTrackingNotConfiguredError):
            make_settings(**overrides).assert_valid()
    # Disabled without them is a valid, unconfigured state.
    make_settings(service_url="", api_key=None, enabled=False).assert_valid()


def test_a_missing_key_keeps_the_settings_valid_but_not_ready() -> None:
    settings = make_settings(credential_public_key=None, credential_key_id=None)

    settings.assert_valid()
    assert settings.is_configured
    assert not settings.is_ready
    assert make_settings().is_ready
    assert not make_settings(enabled=False).is_ready


# ── sealing and contract support ─────────────────────────────────────


def test_sealed_credentials_open_with_the_service_key_only() -> None:
    sealed = seal_credentials({"user": "jane.doe", "password": "s3cret-pw"}, PUBLIC_KEY)

    assert "s3cret-pw" not in sealed and "=" not in sealed
    assert open_sealed(sealed) == {"user": "jane.doe", "password": "s3cret-pw"}
    assert seal_credentials({"user": "jane.doe", "password": "s3cret-pw"}, PUBLIC_KEY) != sealed


@pytest.mark.parametrize("key", ["", "not base64 !", "c2hvcnQ"])
def test_sealing_needs_a_valid_public_key(key: str) -> None:
    with pytest.raises(InvalidCredentialKeyError):
        seal_credentials({"user": "jane.doe", "password": "pw"}, key)


@pytest.mark.parametrize(("version", "supported"), [("0.1", True), ("0.1.3", True), ("0.2", False)])
def test_contract_support(version: str, supported: bool) -> None:
    assert contract_supported(version) is supported


def _field(name: str, kind: str = "text", required: bool = True) -> TimeTrackingCredentialField:
    return TimeTrackingCredentialField(name=name, kind=kind, required=required, max_length=64)


def test_credential_field_support() -> None:
    user, password = _field("user"), _field("password", "secret")

    assert credential_fields_supported((user, password))
    assert credential_fields_supported((user, password, _field("project", required=False)))
    assert not credential_fields_supported((user, password, _field("token")))
    assert not credential_fields_supported((user, _field("password", "text")))


# ── personal accounts only ───────────────────────────────────────────


@pytest.mark.parametrize(
    "flags",
    [{"is_shared_account": True}, {"is_service_account": True}, {"is_systemuser": True}],
)
def test_non_personal_accounts_cannot_hold_credentials(flags: dict[str, bool]) -> None:
    user = make_user(**flags)  # type: ignore[arg-type]
    with pytest.raises(TimeTrackingCredentialsNotAllowedError):
        UserRules.assert_time_tracking_credentials_allowed(user, has_credentials=True)
    # Without credentials there is nothing to forbid.
    UserRules.assert_time_tracking_credentials_allowed(user, has_credentials=False)


def test_personal_accounts_may_hold_credentials() -> None:
    user = make_user()
    assert UserRules.is_personal_account(user)
    # Must not raise for a personal account.
    UserRules.assert_time_tracking_credentials_allowed(user, has_credentials=True)
