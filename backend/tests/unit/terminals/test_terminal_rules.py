"""Domain rules of terminals: pairing codes, approval, revocation, the return
to pending, the pending cap, the access policy and clone detection."""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

import pytest

from src.modules.operations.domain.entities.terminal import Terminal
from src.modules.operations.domain.errors import PairingCodeExpiredError
from src.modules.operations.domain.errors import PairingCodeMismatchError
from src.modules.operations.domain.errors import PendingTerminalLimitError
from src.modules.operations.domain.errors import TerminalIpNotAllowedError
from src.modules.operations.domain.errors import TerminalModeNotSupportedError
from src.modules.operations.domain.errors import TerminalNotPendingError
from src.modules.operations.domain.errors import TerminalsDisabledError
from src.modules.operations.domain.services import terminal_rules
from src.modules.operations.domain.value_objects.terminal import MAX_PENDING_TERMINALS
from src.modules.operations.domain.value_objects.terminal import PAIRING_CODE_ALPHABET
from src.modules.operations.domain.value_objects.terminal import PAIRING_CODE_LENGTH
from src.modules.operations.domain.value_objects.terminal import PAIRING_CODE_TTL
from src.modules.operations.domain.value_objects.terminal import TERMINAL_TOKEN_TTL
from src.modules.operations.domain.value_objects.terminal import TerminalMode
from src.modules.operations.domain.value_objects.terminal import TerminalStatus
from src.modules.platform.domain.entities.admin_settings.maintenance import AdminMaintenanceSettings
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import MaintenanceModeError
from src.modules.platform.domain.exceptions import TerminalPermissionNotAssignableError
from src.modules.platform.domain.services.user_rules import UserRules
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)


def _terminal(**overrides: object) -> Terminal:
    fields: dict[str, object] = {
        "id": 7,
        "public_key": "k",
        "public_key_fingerprint": "0123456789abcdef",
        "status": TerminalStatus.PENDING,
        "mode": TerminalMode.INFOSCREEN,
        "name": None,
        "pairing_code": "ABC234",
        "pairing_expires_at": NOW + timedelta(minutes=30),
        "infoscreen_id": None,
        "api_key_id": 1,
        "first_seen_at": NOW,
        "last_seen_at": NOW,
    }
    fields.update(overrides)
    return Terminal(**fields)  # type: ignore[arg-type]


def _security(**overrides: object) -> AdminSecuritySettings:
    fields: dict[str, object] = {
        "id": 1,
        "enforce_totp": False,
        "allow_rfid_login": True,
        "allow_local_login": True,
        "enable_api_key_auth": False,
        "min_password_length": 8,
        "session_timeout_minutes": 0,
        "totp_trusted_device_days": 30,
        "max_login_attempts": 0,
        "lockout_duration_minutes": 15,
        "token_max_lifetime_days": 3650,
    }
    fields.update(overrides)
    return AdminSecuritySettings(**fields)  # type: ignore[arg-type]


def _approve(
    terminal: Terminal, code: str = "ABC234", mode: TerminalMode = TerminalMode.INFOSCREEN
) -> None:
    terminal_rules.approve(
        terminal,
        pairing_code=code,
        name="Hall 1",
        mode=mode,
        infoscreen_id=3,
        actor=make_user(id=5),
        now=NOW,
    )


def test_terminal_pairing_code_uses_the_unambiguous_alphabet() -> None:
    for _ in range(200):
        code = terminal_rules.new_pairing_code(set())
        assert len(code) == PAIRING_CODE_LENGTH
        assert set(code) <= set(PAIRING_CODE_ALPHABET)
    assert not set("0O1IL") & set(PAIRING_CODE_ALPHABET)


def test_terminal_pairing_code_avoids_codes_already_taken(monkeypatch) -> None:
    draws = iter("AAAAAA" + "BBBBBB")
    monkeypatch.setattr(terminal_rules.secrets, "choice", lambda _alphabet: next(draws))
    assert terminal_rules.new_pairing_code({"AAAAAA"}) == "BBBBBB"


def test_terminal_issue_pairing_code_sets_its_lifetime() -> None:
    terminal = _terminal(pairing_code=None, pairing_expires_at=None)
    terminal_rules.issue_pairing_code(terminal, set(), NOW)
    assert terminal.pairing_code is not None
    assert terminal.pairing_expires_at == NOW + PAIRING_CODE_TTL


def test_terminal_approve_accepts_the_code_in_any_case_and_spacing() -> None:
    terminal = _terminal(duplicate_detected_at=NOW)
    _approve(terminal, code=" abc 234 ")
    assert terminal.status == "approved"
    assert terminal.name == "Hall 1"
    assert terminal.infoscreen_id == 3
    assert terminal.approved_by_id == 5
    assert terminal.approved_at == NOW
    assert terminal.pairing_code is None
    assert terminal.duplicate_detected_at is None


def test_terminal_approve_refuses_a_mismatched_code() -> None:
    terminal = _terminal()
    with pytest.raises(PairingCodeMismatchError):
        _approve(terminal, code="ZZZ999")
    assert terminal.status == "pending"


def test_terminal_approve_refuses_an_expired_code() -> None:
    with pytest.raises(PairingCodeExpiredError):
        _approve(_terminal(pairing_expires_at=NOW - timedelta(seconds=1)))


def test_terminal_approve_refuses_a_terminal_that_is_not_pending() -> None:
    with pytest.raises(TerminalNotPendingError):
        _approve(_terminal(status=TerminalStatus.APPROVED))
    with pytest.raises(TerminalNotPendingError):
        _approve(_terminal(status=TerminalStatus.REVOKED))


def test_terminal_kiosk_mode_is_refused() -> None:
    with pytest.raises(TerminalModeNotSupportedError):
        _approve(_terminal(), mode=TerminalMode.KIOSK)
    with pytest.raises(TerminalModeNotSupportedError):
        terminal_rules.assert_mode_supported("kiosk")


def test_terminal_revoke_then_return_to_pending_issues_a_new_code() -> None:
    terminal = _terminal()
    _approve(terminal)
    terminal_rules.revoke(terminal, NOW)
    assert terminal.status == "revoked"
    assert terminal.revoked_at == NOW
    assert terminal.infoscreen_id == 3

    terminal_rules.return_to_pending(terminal, set(), NOW)
    assert terminal.status == "pending"
    assert terminal.approved_by_id is None
    assert terminal.pairing_code is not None
    assert terminal.pairing_expires_at == NOW + PAIRING_CODE_TTL


def test_terminal_pending_cap() -> None:
    terminal_rules.assert_pending_capacity(MAX_PENDING_TERMINALS - 1)
    with pytest.raises(PendingTerminalLimitError):
        terminal_rules.assert_pending_capacity(MAX_PENDING_TERMINALS)


def test_terminal_manage_needs_the_permission() -> None:
    terminal_rules.assert_can_manage(make_user(permissions=[Permission.MANAGE_TERMINALS]))
    with pytest.raises(InsufficientPermissionsError):
        terminal_rules.assert_can_manage(make_user(permissions=[]))


def test_terminal_access_policy() -> None:
    terminal_rules.assert_access_allowed(_security(), None)
    with pytest.raises(TerminalsDisabledError):
        terminal_rules.assert_access_allowed(_security(enable_terminals=False), "10.0.0.5")
    allowlisted = _security(terminal_allowed_ips=["10.0.0.0/24"])
    terminal_rules.assert_access_allowed(allowlisted, "10.0.0.5")
    with pytest.raises(TerminalIpNotAllowedError):
        terminal_rules.assert_access_allowed(allowlisted, "192.168.1.5")


def test_terminal_maintenance_holds_devices_back_unless_allowlisted() -> None:
    settings = AdminMaintenanceSettings(id=1, enabled=True, message=None, allowed_ips=["10.0.0.5"])
    terminal_rules.assert_maintenance_allows_device(settings, "10.0.0.5")
    with pytest.raises(MaintenanceModeError):
        terminal_rules.assert_maintenance_allows_device(settings, "10.0.0.6")


def test_terminal_clone_detected_for_another_address_within_the_token_lifetime() -> None:
    terminal = _terminal()
    assert not terminal_rules.detect_clone(terminal, "10.0.0.5", NOW)
    assert not terminal_rules.detect_clone(terminal, "10.0.0.5", NOW + timedelta(minutes=5))
    assert terminal.duplicate_detected_at is None

    later = NOW + timedelta(minutes=10)
    assert terminal_rules.detect_clone(terminal, "10.0.0.9", later)
    assert terminal.duplicate_detected_at == later
    assert terminal.last_session_ip == "10.0.0.9"


def test_terminal_no_clone_once_the_previous_token_expired() -> None:
    terminal = _terminal(last_session_at=NOW, last_session_ip="10.0.0.5")
    after = NOW + TERMINAL_TOKEN_TTL + timedelta(seconds=1)
    assert not terminal_rules.detect_clone(terminal, "10.0.0.9", after)
    assert terminal.duplicate_detected_at is None


def test_terminal_connect_permission_is_not_assignable_to_users() -> None:
    with pytest.raises(TerminalPermissionNotAssignableError):
        UserRules.assert_permissions_assignable(None, [Permission.CONNECT_TERMINALS])
    with pytest.raises(TerminalPermissionNotAssignableError):
        UserRules.assert_permissions_assignable(
            make_user(permissions=[Permission.WRITE_ORDERS]), [Permission.CONNECT_TERMINALS]
        )
    terminal_account = make_user(permissions=[Permission.CONNECT_TERMINALS])
    UserRules.assert_permissions_assignable(terminal_account, [Permission.CONNECT_TERMINALS])
    with pytest.raises(TerminalPermissionNotAssignableError):
        UserRules.assert_permissions_assignable(terminal_account, [Permission.WRITE_ORDERS])
    UserRules.assert_permissions_assignable(None, [Permission.WRITE_ORDERS])
