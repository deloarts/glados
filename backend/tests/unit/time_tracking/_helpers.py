"""
Factory functions with synthetic values for the time tracking unit tests:
users, time tracking settings, stored credentials, month data and a
credential key pair generated per test run, so sealed values can be opened
again to check what Glados sealed. No real host, project, person or account
name appears here.
"""

import base64
import json
from datetime import UTC
from datetime import date
from datetime import datetime
from typing import Any

from cryptography.hazmat.primitives import hpke
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from src.modules.operations.domain.entities.admin_settings.time_tracking import (
    AdminTimeTrackingSettings,
)
from src.modules.operations.domain.entities.user_time_tracking_credentials import (
    UserTimeTrackingCredentials,
)
from src.modules.operations.domain.services.time_tracking_rules import TIME_TRACKING_CONSENT_VERSION
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingAccount
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingAccountFormat
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingBooking
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingBookingDirection
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingDay
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingDayStatus
from src.modules.operations.domain.value_objects.time_tracking import TimeTrackingMonth
from src.modules.operations.infrastructure.security.time_tracking_sealer import INFO
from src.modules.platform.domain.entities.user import User
from tests import factories

SERVICE_URL = "http://time-tracking.example.test:3100"
API_KEY = "test-service-api-key"
PASSWORD = "s3cret-pw"
KEY_ID = "0123456789abcdef"
BINDING = "b" * 32
SEALED = "sealed-value-for-jane"
NOW = datetime(2026, 9, 30, 8, 15, tzinfo=UTC)

_PRIVATE_KEY = X25519PrivateKey.generate()
PUBLIC_KEY = (
    base64.urlsafe_b64encode(
        _PRIVATE_KEY.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
    )
    .rstrip(b"=")
    .decode("ascii")
)
_SUITE = hpke.Suite(hpke.KEM.X25519, hpke.KDF.HKDF_SHA256, hpke.AEAD.CHACHA20_POLY1305)


def open_sealed(sealed: str) -> dict[str, str]:
    """What a sealed value holds, opened with the test key as the service would."""
    raw = base64.urlsafe_b64decode(sealed + "=" * (-len(sealed) % 4))
    result: dict[str, str] = json.loads(_SUITE.decrypt(raw, _PRIVATE_KEY, info=INFO))
    return result


def make_user(*, id: int = 7, username: str = "jane", **overrides: Any) -> User:
    """Jane, user 7, whose id the fake credential rows and the verify counters are keyed by."""
    return factories.make_user(id=id, username=username, full_name="Jane Doe", **overrides)


def make_settings(**overrides: object) -> AdminTimeTrackingSettings:
    values: dict[str, object] = {
        "id": 1,
        "enabled": True,
        "service_url": SERVICE_URL,
        "api_key": API_KEY,
        "credential_public_key": PUBLIC_KEY,
        "credential_key_id": KEY_ID,
        "provider_label": "Example Time",
        "privacy_policy_url": None,
    }
    values.update(overrides)
    return AdminTimeTrackingSettings(**values)  # type: ignore[arg-type]


def make_credentials(user_id: int = 7, **overrides: object) -> UserTimeTrackingCredentials:
    values: dict[str, object] = {
        "id": user_id,
        "user_id": user_id,
        "time_tracking_user": "jane.doe",
        "time_tracking_sealed_credentials": SEALED,
        "time_tracking_binding": BINDING,
        "time_tracking_credential_key_id": KEY_ID,
        "time_tracking_user_fingerprint": f"fp-{user_id}",
        "time_tracking_user_fingerprint_key_id": "abcd1234",
        "time_tracking_auth_failed_at": None,
        "time_tracking_consent_at": NOW,
        "time_tracking_consent_version": TIME_TRACKING_CONSENT_VERSION,
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return UserTimeTrackingCredentials(**values)  # type: ignore[arg-type]


def make_month(
    first_day: date = date(2026, 9, 1), last_day: date = date(2026, 9, 30)
) -> TimeTrackingMonth:
    """A small synthetic month: one closed day and today's open day."""
    closed = TimeTrackingDay(
        day=date(2026, 9, 29),
        shift_name="Full time 38.5h",
        shift_short_name="FT",
        target_seconds=27720,
        worked_seconds=30000,
        running_balance_seconds=5880,
        first_in=datetime(2026, 9, 29, 6, 43, tzinfo=UTC),
        last_out=datetime(2026, 9, 29, 15, 3, tzinfo=UTC),
        status=TimeTrackingDayStatus.NORMAL,
        bookings=(),
    )
    today = TimeTrackingDay(
        day=date(2026, 9, 30),
        shift_name="Full time 38.5h",
        shift_short_name="FT",
        target_seconds=27720,
        worked_seconds=None,
        running_balance_seconds=None,
        first_in=None,
        last_out=None,
        status=TimeTrackingDayStatus.OPEN,
        bookings=(
            TimeTrackingBooking(
                at=datetime(2026, 9, 30, 5, 58, tzinfo=UTC),
                direction=TimeTrackingBookingDirection.IN,
            ),
        ),
    )
    days = tuple(d for d in (closed, today) if first_day <= d.day <= last_day)
    return TimeTrackingMonth(
        first_day=first_day,
        last_day=last_day,
        days=days,
        accounts=(
            TimeTrackingAccount(
                account_id=11,
                name="Running balance",
                short_name="BAL",
                format=TimeTrackingAccountFormat.DURATION_CLOCK,
                pre=3600.0,
                sum=2280.0,
                post=5880.0,
            ),
        ),
    )
