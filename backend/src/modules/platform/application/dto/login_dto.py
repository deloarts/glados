"""
Input commands and outcomes of the two interactive login steps, PasswordLogin
and TotpLogin. The inbound adapter fills the commands from the request and
turns each outcome into its response and cookies.

Secrets (password, codes, tokens) are kept out of repr so a logged or
printed DTO never carries them.
"""

from pydantic import BaseModel
from pydantic import Field

# ── Commands (inbound) ────────────────────────────────────────────────


class PasswordLoginCommand(BaseModel):
    """`username` is the raw identifier as typed, a username or an e-mail
    address. `trusted_device_secret` is the trusted-device cookie, if the
    browser sent one."""

    username: str
    password: str = Field(repr=False)
    client_ip: str | None
    user_agent: str | None
    trusted_device_secret: str | None = Field(default=None, repr=False)


class TotpLoginCommand(BaseModel):
    """The second login step. `trust_device` asks for a trusted-device grant
    so later logins from this browser skip the code."""

    partial_token: str = Field(repr=False)
    totp_code: str = Field(repr=False)
    trust_device: bool = False
    client_ip: str | None
    user_agent: str | None


# ── Outcomes (outbound) ───────────────────────────────────────────────


class TrustedDeviceGrant(BaseModel):
    """A new trusted-device grant. `secret` goes into the browser cookie and
    is never stored; `max_age_seconds` is the grant's whole lifetime."""

    secret: str = Field(repr=False)
    max_age_seconds: int


class SessionIssued(BaseModel):
    """The login is complete and a session row exists. `cookie_max_age` is
    the session cookie's browser-side lifetime for this user."""

    access_token: str = Field(repr=False)
    cookie_max_age: int
    trusted_device: TrustedDeviceGrant | None = None


class TotpChallengeIssued(BaseModel):
    """The password was right and the account has 2FA on. The partial token
    is redeemed at the TOTP step; `trusted_device_days` is how long trusting
    this device would skip the prompt, 0 when the feature is off."""

    partial_token: str = Field(repr=False)
    trusted_device_days: int


class TotpSetupRequired(BaseModel):
    """The password was right but 2FA is mandatory and not set up yet. The
    setup token is good only for the enrolment endpoints."""

    setup_token: str = Field(repr=False)
    username: str


PasswordLoginResult = SessionIssued | TotpChallengeIssued | TotpSetupRequired
