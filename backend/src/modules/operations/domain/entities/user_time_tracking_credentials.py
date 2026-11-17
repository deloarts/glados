"""
Pure domain entity. No SQLAlchemy, no Pydantic, no FastAPI.

One Glados user's credentials for the time tracking system, plus the Glados
state that decides whether they may be used: the key they were sealed for,
the binding the time tracking service returned when it verified them, an
earlier authentication failure and the consent the user gave. Nothing read
from the time tracking system is ever stored here.

The password exists only inside `time_tracking_sealed_credentials`, sealed
for the time tracking service's public key, so Glados itself cannot read it.
The user name is kept separately, plaintext in memory and encrypted at rest
by the ORM column type, to show it to its owner and to compute the
one-account-per-user fingerprint; a value no configured key can decrypt
loads as None.
"""

from dataclasses import dataclass
from datetime import datetime

from src.shared_kernel.domain.entities.base import Entity


@dataclass
class UserTimeTrackingCredentials(Entity):
    user_id: int
    time_tracking_user: str | None
    # The user name and password sealed for the service's credential key.
    # None once the service reported that the server or key has changed,
    # since Glados cannot re-seal them; the user enters the password again.
    time_tracking_sealed_credentials: str | None
    # Returned by the service's verification and sent with every request,
    # so the service refuses credentials verified for another server.
    time_tracking_binding: str
    # The id of the credential key the values were sealed for. A different
    # confirmed key blocks every call until the user saves again.
    time_tracking_credential_key_id: str
    # Keyed hash of the normalised user name, unique across all rows, so one
    # time tracking account belongs to one Glados user. The key id records
    # which key produced it, for recomputation after a rotation.
    time_tracking_user_fingerprint: str
    time_tracking_user_fingerprint_key_id: str
    # Set when the time tracking system rejected the stored credentials; no
    # further call is made with them until the user saves again.
    time_tracking_auth_failed_at: datetime | None
    time_tracking_consent_at: datetime
    time_tracking_consent_version: int
    created_at: datetime
    updated_at: datetime
